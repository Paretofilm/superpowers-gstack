#!/usr/bin/env python3
"""Land a wt worktree on main in one command — solo landing, no pull request.

Design: docs/superpowers/specs/2026-09-29-worktrunk-integration-design.md

Contract: exit 0 = landed (possibly with warnings). Any other code = stopped, in the
state the spec's exit-code table names. The script never runs `git reset`, never
retries by itself, never passes --yes or --no-hooks to wt, and never removes the
worktree (the caller leaves it first, then runs `wt remove`). The pre-merge gate is
forced on (`--config-set merge.verify=true`), so no worktrunk config can switch it
off, and exactly the commit that passed it is pushed.

Usage: land-worktree.py [--worktree PATH] [--main-branch NAME] [--preflight-only]
                        [--ci-wait SECONDS]
The last stdout line is a JSON verdict.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import tomllib
import traceback
from pathlib import Path

MODE, UNAPPROVED, MAIN_AHEAD, OVERLAP, HOOK_RED, PUSH, NO_WT, NO_HOOK, REBASE, FETCH, LOCKED, DIRTY = (
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
USAGE, UNKNOWN = 64, 70

MODE_LINE = re.compile(r"Landing mode: (solo|pr)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")

# worktrunk's user config (`[merge] verify = false`, also per project) and the
# WORKTRUNK_MERGE__* environment skip the hooks without --no-hooks (measured on wt
# 0.79.0). --config-set outranks both. ff/rebase are pinned so that main ends up
# exactly at the rebased tip the hooks checked.
WT_MERGE = ("merge", "--config-set", "merge.verify=true", "--config-set", "merge.ff=true",
            "--config-set", "merge.rebase=true", "--no-squash", "--no-commit", "--no-remove")

q = shlex.quote
GIT_ENV: dict | None = None   # batch_env(): git never prompts
WT_ENV: dict | None = None    # the user's environment minus WORKTRUNK_MERGE__*


class Stop(Exception):
    def __init__(self, code, message, state="", commands=()):
        super().__init__(message)
        self.code, self.message, self.state, self.commands = code, message, state, list(commands)


def batch_env(repo) -> dict:
    """git must fail rather than ask: no terminal prompt, ssh in BatchMode — unless the
    user routes ssh through a command of their own, which ours would take precedence over."""
    env = scrubbed_env()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    if not env.get("GIT_SSH_COMMAND") and not env.get("GIT_SSH"):
        r = subprocess.run(["git", "-C", str(repo), "config", "--get", "core.sshCommand"],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if not r.stdout.strip():
            env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    return env


def scrubbed_env() -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith("WORKTRUNK_MERGE__")}


def sh(*args, cwd=None, env=None, pass_fds=()):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, errors="replace",
                          stdin=subprocess.DEVNULL, env=env, pass_fds=pass_fds)


def git(repo, *args):
    return sh("git", "-C", str(repo), *args, env=GIT_ENV)


def wt_cmd(worktree, *args, pass_fds=()):
    return sh("wt", "-C", str(worktree), *args, env=WT_ENV, pass_fds=pass_fds)


def out(repo, *args):
    r = git(repo, *args)
    return r.stdout.strip() if r.returncode == 0 else None


def landing_mode(worktree: Path):
    """The exact line, outside fenced code blocks. Two different values → 'conflict'."""
    f = worktree / "CLAUDE.md"
    if not f.is_file():
        return None
    found, fence = set(), None
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        m = FENCE.match(line)
        if m:
            mark = m.group(1)
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence) and line.strip() == mark:
                fence = None
            continue
        if fence is None:
            m = MODE_LINE.fullmatch(line)
            if m:
                found.add(m.group(1))
    if len(found) > 1:
        return "conflict"
    return found.pop() if found else None


def _is_command(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def has_pre_merge_hook(worktree: Path) -> bool:
    """A top-level `pre-merge` in .config/wt.toml that runs at least one command, in any
    of worktrunk's three forms: a string, a table, or a pipeline of tables."""
    f = worktree / ".config" / "wt.toml"
    try:
        hook = tomllib.loads(f.read_text(encoding="utf-8", errors="replace")).get("pre-merge")
    except (OSError, tomllib.TOMLDecodeError):
        return False
    if isinstance(hook, dict):
        return any(_is_command(v) for v in hook.values())
    if isinstance(hook, list):
        return any(isinstance(step, dict) and any(_is_command(v) for v in step.values()) for step in hook)
    return _is_command(hook)


def unapproved(worktree: Path) -> bool:
    """Fails closed: an approval state that cannot be read counts as not approved."""
    r = wt_cmd(worktree, "config", "approvals", "list")
    if r.returncode != 0:
        return True
    heads = re.findall(r"^(APPROVED|UNAPPROVED)[ \t]*$", r.stdout, re.M)
    if heads != ["APPROVED", "UNAPPROVED"]:
        return True
    return "❯" in r.stdout.split("\nUNAPPROVED", 1)[1]


def worktrees(repo) -> list[dict]:
    items, cur = [], {}
    for line in git(repo, "worktree", "list", "--porcelain").stdout.splitlines() + [""]:
        if not line:
            if cur:
                items.append(cur)
            cur = {}
        elif line.startswith("worktree "):
            cur["path"] = Path(line[len("worktree "):])
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch "):].removeprefix("refs/heads/")
    return items


def primary_worktree(repo) -> Path | None:
    """The main worktree: git lists it first. Not `<common-dir>/..`, which is wrong
    whenever the common dir is not `<repo>/.git`. When git names the git dir itself
    (--separate-git-dir, a submodule's .git/modules/x — measured on git 2.54), only
    core.worktree knows the checkout; without it the answer is None, never a guess."""
    items = worktrees(repo)
    path = items[0].get("path") if items else None
    common = out(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if path and common and Path(path).resolve() == Path(common).resolve():
        cw = out(repo, "config", "--file", str(Path(common) / "config"), "core.worktree")
        path = (Path(common) / cw).resolve() if cw else None
    return path


def default_branch(repo) -> str:
    ref = out(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return ref.split("/", 1)[1] if ref and "/" in ref else "main"


def dirty_files(repo) -> set[str]:
    r = git(repo, "status", "--porcelain", "-z", "--untracked-files=all")
    if r.returncode:
        raise Stop(UNKNOWN, f"git status failed in {repo} — the overlap check cannot run",
                   state=r.stderr.strip()[-300:])
    parts = r.stdout.split("\0")
    files, i = set(), 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        files.add(entry[3:])
        if entry[0] in "RC" and i < len(parts):   # rename/copy: the old path follows
            files.add(parts[i])
            i += 1
    return files


def changed(repo, *rev_args) -> set[str]:
    r = git(repo, "diff", "--name-only", "-z", *rev_args)
    if r.returncode:
        raise Stop(UNKNOWN, f"git diff {' '.join(rev_args)} failed — the overlap check cannot run",
                   state=r.stderr.strip()[-300:])
    return {p for p in r.stdout.split("\0") if p}


def rebase_open(worktree) -> bool:
    for name in ("rebase-merge", "rebase-apply"):
        p = out(worktree, "rev-parse", "--path-format=absolute", "--git-path", name)
        if p and Path(p).exists():
            return True
    return git(worktree, "rev-parse", "--verify", "--quiet", "REBASE_HEAD").returncode == 0


class Lock:
    """One landing per repository: a kernel lock (flock) on a file in the common git dir.
    The kernel drops it when the last holder of the open file goes away, so there is no
    stale lock to detect. The fd is handed to `wt merge`, so a merge orphaned by a killed
    script keeps the lock until it ends."""

    def __init__(self, common_dir: Path):
        self.path = common_dir / "gstack-land.lock"
        self.fd = None

    def __enter__(self):
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise Stop(LOCKED, f"another landing holds {self.path}",
                       commands=[f"lsof {q(str(self.path))}   # the process that holds it"]) from None
        self.fd = fd
        return self

    def __exit__(self, *exc):
        try:   # explicit unlock: also releases it for children that inherited the fd
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
        return False


def pull_hint(mw, main) -> str:
    if mw:
        return f"git -C {q(str(mw))} pull --rebase origin {q(main)}"
    return (f"{main} has no worktree: {main} must be checked out somewhere first "
            f"(e.g. git worktree add <path> {q(main)}), then pull --rebase origin {q(main)} there")


def push_stop_commands(wt, mw, main) -> list[str]:
    """Recovery for code 7. After pull --rebase the combination is new and UNCHECKED:
    the gate runs on it before anything is pushed."""
    cmds = [f"git -C {q(str(wt))} log --oneline {q(f'origin/{main}..{main}')}   # your commits, not on origin",
            pull_hint(mw, main)]
    if mw:
        cmds += [f"wt -C {q(str(mw))} hook pre-merge   # REQUIRED: the rebased result is UNCHECKED until this passes",
                 f"git -C {q(str(mw))} push origin {q(main)}   # only after the gate passed"]
    else:
        cmds += [f"then, in that checkout: wt hook pre-merge (the rebased result is UNCHECKED until it passes), "
                 f"and only then: git push origin {q(main)}"]
    return cmds


def _classify(r, wt, main, moved, rebase_is_open) -> Stop:
    text = r.stdout + r.stderr
    tail = "\n".join(text.strip().splitlines()[-12:])
    w = q(str(wt))
    where = (f"{main} moved during the failed merge — look before doing anything" if moved
             else f"{main} was not moved")
    state = (f"{where}; {'a rebase is open in the worktree' if rebase_is_open else 'no rebase is open'}; "
             f"worktree and branch stand\n--- wt merge, last lines ---\n{tail}")
    if "Cannot prompt for approval" in text or "needs approval" in text:
        return Stop(UNAPPROVED, "the project's hooks are not approved", state=state,
                    commands=[f"wt -C {w} config approvals add"])
    if "pre-merge command failed" in text:
        return Stop(HOOK_RED, "a pre-merge check failed — fix it (never --no-hooks) and land again",
                    state=state, commands=[f"wt -C {w} hook pre-merge"])
    if ("Rebase onto" in text and "incomplete" in text) or "CONFLICT" in text:
        return Stop(REBASE, "rebasing onto main hit a conflict", state=state,
                    commands=[f"git -C {w} status",
                              f"git -C {w} rebase --abort   # or resolve, then: git rebase --continue"])
    if "conflicting uncommitted changes" in text:
        return Stop(OVERLAP, "the worktree holding main has uncommitted changes in a file this landing touches",
                    state=state)
    return Stop(UNKNOWN, "wt merge failed for a reason this script does not recognise", state=state)


def _ci_watch(wt, main, sha, wait, warnings):
    if not shutil.which("gh"):
        warnings.append("gh is not installed — CI status not checked")
        return None
    deadline = time.time() + wait
    while True:
        r = sh("gh", "run", "list", "--commit", sha, "--branch", main, "--json", "databaseId,url", "-L", "1",
               cwd=str(wt))
        try:
            runs = json.loads(r.stdout) if r.returncode == 0 else []
        except ValueError:
            runs = []
        if runs:
            return f"gh run watch {int(runs[0]['databaseId'])} --exit-status"
        if time.time() >= deadline:
            break
        time.sleep(3)
    warnings.append(f"no CI run found for {sha[:9]} within {wait}s")
    return None


def _all_landed(wt, remote_sha, tip) -> bool:
    """Everything on the remote branch is in the pushed tip: an ancestor, or (after the
    rebase) every commit patch-equivalent to one in it."""
    if git(wt, "cat-file", "-e", f"{remote_sha}^{{commit}}").returncode:
        return False
    if git(wt, "merge-base", "--is-ancestor", remote_sha, tip).returncode == 0:
        return True
    r = git(wt, "cherry", tip, remote_sha)
    return r.returncode == 0 and all(line.startswith("-") for line in r.stdout.splitlines())


def land(a) -> dict:
    global GIT_ENV, WT_ENV
    wt = Path(a.worktree).resolve()
    GIT_ENV, WT_ENV = batch_env(wt), scrubbed_env()
    common = out(wt, "rev-parse", "--path-format=absolute", "--git-common-dir")
    branch = out(wt, "rev-parse", "--abbrev-ref", "HEAD")
    if not common or not branch:
        raise Stop(USAGE, f"{wt} is not a git worktree")
    main = a.main_branch or default_branch(wt)
    if git(wt, "rev-parse", "--verify", "--quiet", f"refs/heads/{main}").returncode != 0:
        raise Stop(USAGE, f"main branch '{main}' does not exist here — pass --main-branch NAME")
    if branch in ("HEAD", main):
        raise Stop(USAGE, f"{wt} is on '{branch}', not a feature branch — land from the feature worktree")
    with Lock(Path(common)) as lock:
        return _land_locked(a, wt, branch, main, lock.fd)


def _land_locked(a, wt, branch, main, lock_fd) -> dict:
    mode = landing_mode(wt)
    if mode != "solo":
        raise Stop(MODE, ("CLAUDE.md has both 'Landing mode: solo' and 'Landing mode: pr' outside code blocks "
                          "(fails closed)" if mode == "conflict" else
                          f"Landing mode is '{mode}', not 'solo'" if mode else
                          "CLAUDE.md has no exact 'Landing mode: solo' or 'Landing mode: pr' line outside code "
                          "blocks (fails closed)"),
                   commands=["mode 'pr': use /ship", "no line: ask the user once, then write it under a heading the project owns"])
    if not has_pre_merge_hook(wt):
        raise Stop(NO_HOOK, "no top-level pre-merge hook that runs a command in .config/wt.toml "
                            "— nothing would gate this landing",
                   commands=["propose a .config/wt.toml whose [pre-merge] runs the same commands as CI; the user approves it"])
    if not shutil.which("wt"):
        raise Stop(NO_WT, "wt (worktrunk) is not installed",
                   commands=["fall back to: git worktree add, then /superpowers:finishing-a-development-branch"])
    if unapproved(wt):
        raise Stop(UNAPPROVED, "the project's hooks are not approved (or their approval state could not be read)",
                   commands=[f"wt -C {q(str(wt))} config approvals list",
                             f"wt -C {q(str(wt))} config approvals add"])
    primary = primary_worktree(wt)
    heads, origin = f"refs/heads/{main}", f"refs/remotes/origin/{main}"
    has_origin = out(wt, "remote", "get-url", "origin") is not None
    if has_origin and git(wt, "fetch", "origin").returncode != 0:
        raise Stop(FETCH, "git fetch origin failed")
    dirty = git(wt, "status", "--porcelain").stdout.strip()
    if dirty:
        raise Stop(DIRTY, "the worktree has uncommitted work — wt merge would commit it for you",
                   state=dirty, commands=["commit it, or move it: git switch -c wip/<topic>"])
    mw = next((w for w in worktrees(wt) if w.get("branch") == main), None)
    feature = changed(wt, f"{heads}...refs/heads/{branch}")
    theirs = changed(wt, heads, origin) if has_origin else set()
    if mw:
        clash = sorted(dirty_files(mw["path"]) & (feature | theirs))
        if clash:
            raise Stop(OVERLAP, f"uncommitted files in {mw['path']} overlap this landing: {', '.join(clash)}",
                       state="nothing moved", commands=["commit them or move them to their own branch — never stash"])
    if has_origin:
        ahead = git(wt, "log", "--oneline", f"{origin}..{heads}").stdout.strip()
        if ahead:
            raise Stop(MAIN_AHEAD, f"local {main} has commits that are not on origin (they would ride along unchecked)",
                       state=ahead)
        r = (git(mw["path"], "merge", "--ff-only", origin) if mw
             else git(wt, "fetch", "origin", f"{heads}:{heads}"))
        if r.returncode:
            raise Stop(MAIN_AHEAD, f"local {main} cannot fast-forward to origin/{main}", state=r.stderr.strip())
    count = out(wt, "rev-list", "--count", f"{heads}..refs/heads/{branch}")
    if count is None:
        raise Stop(UNKNOWN, f"git rev-list {main}..{branch} failed")
    if count == "0":
        raise Stop(USAGE, f"nothing to land: '{branch}' has no commits that are not already on {main}")
    base = out(wt, "rev-parse", origin) if has_origin else None
    if a.preflight_only:
        return {"landed": False, "preflight": "ok", "branch": branch, "main": main,
                "main_worktree": str(mw["path"]) if mw else None}

    before = out(wt, "rev-parse", heads)
    merge = wt_cmd(wt, *WT_MERGE, main, pass_fds=(lock_fd,))
    if merge.returncode:
        raise _classify(merge, wt, main, out(wt, "rev-parse", heads) != before, rebase_open(wt))
    tip, now = out(wt, "rev-parse", f"refs/heads/{branch}"), out(wt, "rev-parse", heads)
    if not tip or now != tip:
        raise Stop(UNKNOWN, f"after wt merge, local {main} is not exactly the tip of '{branch}' that passed the "
                            "checks — nothing was pushed",
                   state=f"{main} was {before}, is now {now}; {branch} is {tip}; worktree and branch stand",
                   commands=[f"git -C {q(str(wt))} log --oneline {q(f'{branch}..{main}')}   # what else is on {main}"])

    warnings, pushed, remaining_extra = [], None, []
    if has_origin:
        git(wt, "fetch", "origin")
        stop_cmds = push_stop_commands(wt, mw["path"] if mw else None, main)
        if out(wt, "rev-parse", origin) != base:
            raise Stop(PUSH, f"origin/{main} moved while the checks ran — nothing was pushed",
                       state=(f"local {main} already contains your commits; worktree and branch stand. "
                              "After pull --rebase the combined result is UNCHECKED until the pre-merge gate "
                              "passes on it"),
                       commands=stop_cmds)
        r = git(wt, "push", "origin", f"{tip}:{heads}")
        if r.returncode:
            git(wt, "fetch", "origin")
            if out(wt, "rev-parse", origin) != tip:
                raise Stop(PUSH, f"the push of {main} failed — {tip[:9]} is not confirmed pushed",
                           state=(f"{r.stderr.strip()[-600:]}\nlocal {main} already contains your commits; "
                                  "worktree and branch stand. After pull --rebase the combined result is "
                                  "UNCHECKED until the pre-merge gate passes on it"),
                           commands=stop_cmds)
            warnings.append(f"git push reported an error, but origin/{main} is {tip[:9]}: treated as pushed")
        pushed = tip
        refs = git(wt, "ls-remote", "origin", f"refs/heads/{branch}")
        remote_sha = next((ln.split("\t")[0] for ln in refs.stdout.splitlines()
                           if ln.split("\t")[-1] == f"refs/heads/{branch}"), None) if refs.returncode == 0 else None
        if remote_sha and _all_landed(wt, remote_sha, tip):
            r = git(wt, "push", f"--force-with-lease=refs/heads/{branch}:{remote_sha}",
                    "origin", "--delete", f"refs/heads/{branch}")
            if r.returncode:
                warnings.append(f"could not delete origin/{branch}: {r.stderr.strip()[-200:]}")
        elif remote_sha:
            warnings.append(f"origin/{branch} has commits that are not in {main} — left in place")
            remaining_extra.append(f"git -C {q(str(wt))} log --oneline {q(f'{tip}..{remote_sha}')}"
                                   f"   # what only origin/{branch} has")
    watch = _ci_watch(wt, main, pushed, a.ci_wait, warnings) if pushed else None
    if not has_origin:
        warnings.append("no origin remote: landed locally, nothing was pushed")
    remaining = ["if this session stands inside the worktree: ExitWorktree with action keep",
                 (f"wt -C {q(str(primary))} remove {q(branch)}" if primary else
                  f"from the main checkout (git could not name it): wt remove {q(branch)}"),
                 *remaining_extra]
    if watch:
        remaining.append(f"{watch}   # run in the background; a red run means fixing {main} next")
    return {"landed": True, "branch": branch, "main": main, "sha": pushed or tip,
            "watch": watch, "remaining": remaining, "warnings": warnings}


def _interrupted(signum, frame):
    raise KeyboardInterrupt


def _stopped(code, message, state="", commands=()) -> int:
    print(f"STOPPED (exit {code}): {message}", file=sys.stderr)
    if state:
        print(f"State: {state}", file=sys.stderr)
    for c in commands:
        print(f"  {c}", file=sys.stderr)
    print(json.dumps({"landed": False, "code": code, "message": message}))
    return code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Land a worktree on main (solo landing, no pull request).")
    ap.add_argument("--worktree", default=os.getcwd())
    ap.add_argument("--main-branch")
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--ci-wait", type=int, default=30)
    ap.error = lambda msg: (print(f"land-worktree: {msg}", file=sys.stderr), sys.exit(USAGE))
    a = ap.parse_args(argv)
    previous = signal.signal(signal.SIGTERM, _interrupted)   # SIGTERM stops like Ctrl-C: verdict, lock released
    try:
        v = land(a)
    except Stop as s:
        return _stopped(s.code, s.message, s.state, s.commands)
    except KeyboardInterrupt:
        return _stopped(UNKNOWN, "interrupted — check `git status` and rebase state in the worktree",
                        state="the running step was stopped; the lock is released",
                        commands=[f"git -C {q(str(Path(a.worktree).resolve()))} status"])
    except Exception as e:   # noqa: BLE001 — a verdict must always be printed; the lock is already released
        tb = traceback.format_exc()
        print(f"STOPPED (exit {UNKNOWN}): unexpected error: {e!r}", file=sys.stderr)
        print("\n".join(tb.strip().splitlines()[-12:]), file=sys.stderr)
        print(json.dumps({"landed": False, "code": UNKNOWN, "message": f"unexpected error: {e!r}"}))
        return UNKNOWN
    finally:
        signal.signal(signal.SIGTERM, previous)
    if v.get("landed"):
        print(f"LANDED {v['branch']} on {v['main']} ({(v['sha'] or '')[:9]})")
        for line in v["remaining"]:
            print(f"  remaining: {line}")
        for w in v["warnings"]:
            print(f"  warning: {w}")
    else:
        print("preflight ok")
    print(json.dumps(v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
