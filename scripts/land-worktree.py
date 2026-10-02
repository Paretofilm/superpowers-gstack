#!/usr/bin/env python3
"""Land a wt worktree on main in one command — solo landing, no pull request.

Design: docs/superpowers/specs/2026-09-29-worktrunk-integration-design.md

Contract: exit 0 = landed (possibly with warnings). Any other code = stopped, in the
state the spec's exit-code table names. The script never runs `git reset`, never
retries by itself, never passes --yes or --no-hooks to wt, and never removes the
worktree (the caller leaves it first, then runs `wt remove`). The pre-merge gate is
forced on (`--config-set merge.verify=true`), so no worktrunk config can switch it
off, and exactly the commit that passed it is pushed. The `Landing mode:` line must
read the same on the branch and on main (code 14 otherwise): a branch never sets the
policy it is landed under.

Usage: python3.11+ land-worktree.py [--worktree PATH] [--main-branch NAME] [--preflight-only]
                                    [--ci-wait SECONDS]
The last stdout line is a JSON verdict. Requires Python >= 3.11 (tomllib, to read the
pre-merge gate); an older interpreter stops with code 70 and says so.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import posixpath
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

try:   # Python >= 3.11. Older (macOS /usr/bin/python3 is 3.9) gets a code-70 verdict, not a traceback
    import tomllib
except ModuleNotFoundError:
    tomllib = None

MODE, UNAPPROVED, MAIN_AHEAD, OVERLAP, HOOK_RED, PUSH, NO_WT, NO_HOOK, REBASE, FETCH, LOCKED, DIRTY, POLICY = (
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)
USAGE, UNKNOWN = 64, 70

MODE_LINE = re.compile(r"Landing mode: (solo|pr)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")

# worktrunk's user config (`[merge] verify = false`, also per project) and the
# WORKTRUNK_MERGE__* environment skip the hooks without --no-hooks (measured on wt
# 0.79.0). --config-set outranks both. ff is pinned so that main ends up exactly at
# the tip the hooks checked. --no-rebase: wt 0.79.0 reads the hook config BEFORE its
# own rebase, so a rebase inside the gated step would check one tree with another
# tree's gate; the branch must already contain main (precheck, code 10).
WT_MERGE = ("merge", "--config-set", "merge.verify=true", "--config-set", "merge.ff=true",
            "--no-squash", "--no-commit", "--no-rebase", "--no-remove")

q = shlex.quote
GIT_ENV: dict | None = None   # batch_env(): git never prompts
WT_ENV: dict | None = None    # the user's environment minus every WORKTRUNK_* variable
PROGRESS: dict = {}           # what the landing has done so far, measured again on interrupt


class Stop(Exception):
    def __init__(self, code, message, state="", commands=()):
        super().__init__(message)
        self.code, self.message, self.state, self.commands = code, message, state, list(commands)


def batch_env(repo) -> dict:
    """git must fail rather than ask: no terminal prompt, ssh in BatchMode — unless the
    user routes ssh through a command of their own, which ours would take precedence over."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("WORKTRUNK_MERGE__")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    if not env.get("GIT_SSH_COMMAND") and not env.get("GIT_SSH"):
        r = subprocess.run(["git", "-C", str(repo), "config", "--get", "core.sshCommand"],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if not r.stdout.strip():
            env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    return env


def scrubbed_env() -> dict:
    """For wt: no WORKTRUNK_* at all. WORKTRUNK_PROJECT_CONFIG_PATH, for one, points wt at
    another project config than the .config/wt.toml this script checked."""
    return {k: v for k, v in os.environ.items() if not k.startswith("WORKTRUNK_")}


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
    """The line in the CLAUDE.md on disk at the worktree's top level."""
    f = worktree / "CLAUDE.md"
    if not f.is_file():
        return None
    return parse_mode(f.read_text(encoding="utf-8", errors="replace"))


def mode_at(repo, rev):
    """The line in CLAUDE.md as committed at `rev` (None: no line, or no readable file)."""
    found = claude_md_at(repo, rev)
    return parse_mode(found[1]) if found else None


def claude_md_at(repo, rev, path="CLAUDE.md"):
    """(path, text) of CLAUDE.md as committed at `rev`. A symlink is followed the way the
    file on disk would be (CLAUDE.md -> AGENTS.md), but only inside the repository: a link
    out of it, a missing file or an unreadable object is None."""
    for _ in range(8):
        r = git(repo, "ls-tree", "-z", "--full-tree", rev, "--", path)
        entry = r.stdout.split("\0")[0] if r.returncode == 0 else ""
        if "\t" not in entry or entry.split("\t", 1)[1] != path:
            return None
        mode, kind, obj = entry.split("\t", 1)[0].split()
        if kind != "blob":
            return None
        blob = git(repo, "cat-file", "blob", obj)
        if blob.returncode:
            return None
        if mode != "120000":
            return path, blob.stdout
        target = posixpath.normpath(posixpath.join(posixpath.dirname(path), blob.stdout))
        if target.startswith(("/", "../")) or target in ("..", "."):
            return None
        path = target
    return None


def policy_files(repo, *revs) -> list[str]:
    """CLAUDE.md plus the file a symlinked CLAUDE.md resolves to at each rev: a diff of
    CLAUDE.md alone shows nothing when the change is in the link's target."""
    return ["CLAUDE.md", *sorted({f[0] for f in (claude_md_at(repo, r) for r in revs) if f and f[0] != "CLAUDE.md"})]


def describe(mode) -> str:
    return {None: "no Landing mode line", "conflict": "both 'solo' and 'pr'"}.get(mode, f"'{mode}'")


def check_policy(wt, main, branch, main_rev, branch_mode, state):
    """Land only under the line main already has. A branch that differs from main stops:
    14 when the branch changed the line, 10 when main changed it after the branch forked
    (the rebase brings main's line). Equal but not exactly 'solo' stops at 2."""
    main_mode = mode_at(wt, main_rev)
    w = q(str(wt))
    if branch_mode != main_mode:
        said = f"{main} says {describe(main_mode)}, the branch says {describe(branch_mode)}"
        fork = out(wt, "merge-base", main_rev, f"refs/heads/{branch}")
        if fork and mode_at(wt, fork) == branch_mode:
            raise Stop(REBASE, f"rebase needed: the landing mode on {main} changed after '{branch}' forked "
                               f"({said})", state=state,
                       commands=[f"wt -C {w} step rebase {q(main)}",
                                 f"git -C {w} rebase {q(main)}   # the same without worktrunk", "then land again"])
        files = policy_files(wt, main_rev, f"refs/heads/{branch}")
        raise Stop(POLICY, f"'{branch}' changes the landing mode: {said} — a branch never sets the policy "
                           "it is landed under", state=state,
                   commands=[f"git -C {w} diff {q(f'{main}...{branch}')} -- {' '.join(map(q, files))}"
                             "   # show the user this change",
                             f"keep it: it reaches {main} on its own first, never through land; "
                             f"undo it: restore {main}'s line on the branch, commit, land again"])
    if branch_mode != "solo":
        raise Stop(MODE, ("CLAUDE.md has both 'Landing mode: solo' and 'Landing mode: pr' outside code blocks "
                          "(fails closed)" if branch_mode == "conflict" else
                          f"Landing mode is '{branch_mode}', not 'solo'" if branch_mode else
                          "CLAUDE.md has no exact 'Landing mode: solo' or 'Landing mode: pr' line outside code "
                          "blocks (fails closed)"),
                   state=state,
                   commands=["mode 'pr': use /ship",
                             f"no line: ask the user once, then commit the answer on {main} itself, not on the "
                             "branch (a line the branch adds stops at 14); rebase the branch and land again"])


def parse_mode(text: str):
    """The exact line, outside fenced code blocks. Two different values → 'conflict'."""
    found, fence = set(), None
    for line in text.splitlines():
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


def default_branch(repo) -> str | None:
    """origin/HEAD, else origin/main, origin/master, local main, local master: the order of
    verify-and-land's DEFAULT_REF, so both name the same branch. (Local first picked a
    local master beside origin/main and landed on the wrong branch; now the missing local
    main is a code-64 stop.)"""
    ref = out(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if ref and "/" in ref:
        return ref.split("/", 1)[1]
    for prefix in ("refs/remotes/origin", "refs/heads"):
        for name in ("main", "master"):
            if git(repo, "show-ref", "--verify", "--quiet", f"{prefix}/{name}").returncode == 0:
                return name
    return None


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
    return False   # a lingering REBASE_HEAD alone is no open rebase (`rebase --abort` would fail on it)


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


def push_stop_commands(wt, mw, main, base=None) -> list[str]:
    """Recovery for code 7. After pull --rebase the combination is new and UNCHECKED:
    the gate runs on it before anything is pushed. The push is by hand, so the landing-mode
    check never sees it: origin must still contain the base the checks started from (no
    rollback) and must not have changed CLAUDE.md since (perhaps the landing mode)."""
    cmds = [f"git -C {q(str(wt))} log --oneline {q(f'origin/{main}..{main}')}   # your commits, not on origin",
            pull_hint(mw, main)]
    ref = f"origin/{main}"
    files = " ".join(map(q, policy_files(wt, base, f"refs/remotes/{ref}"))) if base else ""
    checks = ([f"git -C {q(str(mw or wt))} merge-base --is-ancestor {q(base)} {q(ref)}   # REQUIRED: exit 0, "
               f"else {ref} was rolled back while the checks ran: push nothing, show the user",
               f"git -C {q(str(mw or wt))} diff {q(base)} {q(ref)} -- {files}   # REQUIRED: empty, else origin "
               "changed CLAUDE.md while the checks ran (perhaps the landing mode): push nothing, show the user"]
              if base else [])
    if mw:
        cmds += [f"wt -C {q(str(mw))} hook pre-merge   # REQUIRED: the rebased result is UNCHECKED until this passes",
                 *checks,
                 f"git -C {q(str(mw))} push origin {q(main)}   # only after the gate passed and the checks held"]
    else:
        cmds += [f"then, in that checkout: wt hook pre-merge (the rebased result is UNCHECKED until it passes), "
                 + (f"check that `git merge-base --is-ancestor {base} {ref}` exits 0 and `git diff {base} {ref} "
                    f"-- {files}` is empty (else push nothing and show the user: origin was rolled back or changed "
                    "CLAUDE.md, perhaps the landing mode), " if base else "")
                 + f"and only then: git push origin {q(main)}"]
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
    # git cherry skips merge commits, so a merge carrying its own content would read as
    # landed. Any merge commit not in the tip → not provably landed.
    merges = git(wt, "rev-list", "--merges", f"{tip}..{remote_sha}")
    if merges.returncode or merges.stdout.strip():
        return False
    r = git(wt, "cherry", tip, remote_sha)
    return r.returncode == 0 and all(line.startswith("-") for line in r.stdout.splitlines())


def land(a) -> dict:
    global GIT_ENV, WT_ENV
    PROGRESS.clear()
    if tomllib is None:
        v = sys.version_info
        raise Stop(UNKNOWN, f"Python >= 3.11 required to read the pre-merge gate (this is {v.major}.{v.minor})",
                   state="nothing was checked or moved",
                   commands=["run it with python3.11 or newer, e.g. python3.13 or /opt/homebrew/bin/python3"])
    wt = Path(a.worktree).resolve()
    GIT_ENV, WT_ENV = batch_env(wt), scrubbed_env()
    top = out(wt, "rev-parse", "--show-toplevel")
    common = out(wt, "rev-parse", "--path-format=absolute", "--git-common-dir")
    branch = out(wt, "rev-parse", "--abbrev-ref", "HEAD")
    if not top or not common or not branch:
        raise Stop(USAGE, f"{wt} is not a git worktree")
    wt = Path(top)   # called from a subdirectory: CLAUDE.md and .config/wt.toml live at the top, as wt reads them
    main = a.main_branch or default_branch(wt)
    if not main:
        raise Stop(USAGE, "no origin/HEAD, no origin/main or origin/master and no local 'main' or 'master' "
                          "— pass --main-branch NAME")
    if git(wt, "rev-parse", "--verify", "--quiet", f"refs/heads/{main}").returncode != 0:
        hint = ([f"git -C {q(str(wt))} branch --track {q(main)} {q(f'origin/{main}')}   # creates it from origin"]
                if out(wt, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{main}") else [])
        raise Stop(USAGE, f"main branch '{main}' does not exist here — pass --main-branch NAME", commands=hint)
    if rebase_open(wt):   # before the branch check: HEAD is detached while a rebase is open
        w = q(str(wt))
        raise Stop(REBASE, "a rebase is open in the worktree — finish or abort it, then land again",
                   state="nothing was moved by this landing",
                   commands=[f"git -C {w} status",
                             f"git -C {w} rebase --abort   # or resolve, then: git -C {w} rebase --continue"])
    if branch in ("HEAD", main):
        raise Stop(USAGE, f"{wt} is on '{branch}', not a feature branch — land from the feature worktree")
    PROGRESS.update(wt=wt, branch=branch, main=main)
    with Lock(Path(common)) as lock:
        return _land_locked(a, wt, branch, main, lock.fd)


def _land_locked(a, wt, branch, main, lock_fd) -> dict:
    heads = f"refs/heads/{main}"
    # Before anything moves: the line on disk here against local main. Checked again
    # below against the exact main and tip the merge uses (main may fast-forward first).
    disk, committed = landing_mode(wt), mode_at(wt, f"refs/heads/{branch}")
    unread = ("" if disk == committed else
              f"; the CLAUDE.md on disk says {describe(disk)}, the committed one {describe(committed)} "
              "(uncommitted, ignored, or a link out of the repository): only a committed line counts")
    check_policy(wt, main, branch, heads, disk, state="nothing moved" + unread)
    if not has_pre_merge_hook(wt):
        raise Stop(NO_HOOK, "no top-level pre-merge hook that runs a command in .config/wt.toml "
                            "— nothing would gate this landing",
                   commands=["propose a .config/wt.toml whose [pre-merge] runs the same commands as CI; the user approves it"])
    if not shutil.which("wt"):
        raise Stop(NO_WT, "wt (worktrunk) is not installed — it runs the pre-merge gate, so nothing lands without it",
                   state="nothing moved",
                   commands=["brew install worktrunk   # or: cargo install worktrunk — the user installs it",
                             "then land again (the project's hooks may still need approving: exit 3 says how)"])
    if unapproved(wt):
        raise Stop(UNAPPROVED, "the project's hooks are not approved (or their approval state could not be read)",
                   commands=[f"wt -C {q(str(wt))} config approvals list",
                             f"wt -C {q(str(wt))} config approvals add"])
    w = q(str(wt))
    primary = primary_worktree(wt)
    origin = f"refs/remotes/origin/{main}"
    has_origin = out(wt, "remote", "get-url", "origin") is not None
    PROGRESS.update(primary=primary, has_origin=has_origin)
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
    ff_note = ""
    if has_origin:
        ahead =git(wt, "log", "--oneline", f"{origin}..{heads}").stdout.strip()
        if ahead:
            raise Stop(MAIN_AHEAD, f"local {main} has commits that are not on origin (they would ride along unchecked)",
                       state=ahead)
        main_before_ff = out(wt, "rev-parse", heads)
        r = (git(mw["path"], "-c", "merge.autostash=false", "merge", "--ff-only", "--no-autostash", origin) if mw
             else git(wt, "fetch", "origin", f"{heads}:{heads}"))
        if r.returncode:
            raise Stop(MAIN_AHEAD, f"local {main} cannot fast-forward to origin/{main}", state=r.stderr.strip())
        if out(wt, "rev-parse", heads) != main_before_ff:
            ff_note = (f"local {main} was fast-forwarded to origin/{main}; "
                       "the branch and origin were not moved")
    count = out(wt, "rev-list", "--count", f"{heads}..refs/heads/{branch}")
    if count is None:
        raise Stop(UNKNOWN, f"git rev-list {main}..{branch} failed")
    if count == "0":
        raise Stop(USAGE, f"nothing to land: '{branch}' has no commits that are not already on {main}",
                   state=ff_note)
    if git(wt, "merge-base", "--is-ancestor", heads, f"refs/heads/{branch}").returncode != 0:
        raise Stop(REBASE, f"rebase needed: '{branch}' does not contain the current {main} — the gate must run "
                           "on the rebased tree, so the rebase happens before the landing",
                   state=ff_note or "nothing moved",
                   commands=[f"wt -C {w} step rebase {q(main)}",
                             f"git -C {w} rebase {q(main)}   # the same without worktrunk",
                             "then land again"])
    base = out(wt, "rev-parse", origin) if has_origin else None
    # The tip is captured BEFORE the gate: a commit that appears on the branch while the
    # hooks run was never checked, and wt would fast-forward main to it.
    before, tip = out(wt, "rev-parse", heads), out(wt, "rev-parse", f"refs/heads/{branch}")
    if not before or not tip:
        raise Stop(UNKNOWN, f"could not read {main} or '{branch}' before the merge")
    # The landing mode again, on exactly the main and the tip the merge will use: local
    # main may have been fast-forwarded to an origin/main whose line the first check never saw.
    check_policy(wt, main, branch, before, mode_at(wt, tip),
                 state=(ff_note or "nothing moved") + "; nothing was merged or pushed")
    if a.preflight_only:
        return {"landed": False, "preflight": "ok", "branch": branch, "main": main,
                "main_worktree": str(mw["path"]) if mw else None}

    PROGRESS.update(before=before, base=base, tip=tip)
    merge = wt_cmd(wt, *WT_MERGE, main, pass_fds=(lock_fd,))
    if merge.returncode:
        raise _classify(merge, wt, main, out(wt, "rev-parse", heads) != before, rebase_open(wt))
    branch_now, now = out(wt, "rev-parse", f"refs/heads/{branch}"), out(wt, "rev-parse", heads)
    if branch_now != tip or now != tip:
        what = ("could not read the branch after the merge" if not branch_now else
                f"'{branch}' got a new commit during the gate ({branch_now[:9]}, checked was {tip[:9]})"
                if branch_now != tip else f"{main} is not the checked tip {tip[:9]}")
        raise Stop(UNKNOWN, f"after wt merge, {what} — nothing was pushed",
                   state=(f"{main} was {before}, is now {now}; '{branch}' was {tip} when the gate started, is now "
                          f"{branch_now}; worktree and branch stand. Only {tip[:9]} passed the checks"),
                   commands=[f"git -C {q(str(wt))} log --oneline {q(f'{tip}..{branch}')} {q(f'{tip}..{main}')}"
                             "   # what was never checked"])
    # A hook that edits tracked files (a formatter before the tests) checked a tree that
    # is not the commit about to be pushed. Ignored files are build output; they don't count.
    st = git(wt, "status", "--porcelain", "--untracked-files=all")
    if st.returncode or st.stdout.strip():
        w = q(str(wt))
        raise Stop(UNKNOWN, "the pre-merge hooks changed files in the worktree — the checked tree is not the "
                            "commit, so nothing was pushed",
                   state=(f"files changed by the hooks:\n{st.stdout.rstrip() or st.stderr.strip()}\n"
                          f"local {main} is now {now} (the commit without those changes) and it is not on origin, "
                          f"so a plain re-run stops at exit 4; worktree and branch stand"),
                   commands=[f"git -C {w} diff   # what the hooks changed",
                             f"git -C {w} status",
                             "decide consciously: commit the changes on the branch and land that commit, or discard "
                             "them — and make the hook stop writing (a formatter belongs in pre-commit)"])

    warnings, pushed, remaining_extra = [], None, []
    if has_origin:
        git(wt, "fetch", "origin")
        stop_cmds = push_stop_commands(wt, mw["path"] if mw else None, main, base)
        if out(wt, "rev-parse", origin) != base:
            raise Stop(PUSH, f"origin/{main} moved while the checks ran — nothing was pushed",
                       state=(f"local {main} already contains your commits; worktree and branch stand. "
                              "After pull --rebase the combined result is UNCHECKED until the pre-merge gate "
                              "passes on it"),
                       commands=stop_cmds)
        if not base or git(wt, "merge-base", "--is-ancestor", base, tip).returncode:
            raise Stop(UNKNOWN, f"the checked tip {tip[:9]} does not contain origin/{main} as checked "
                                f"({(base or '?')[:9]}) — nothing was pushed",
                       state=f"local {main} already contains your commits; worktree and branch stand",
                       commands=stop_cmds)
        # Compare-and-swap: the push lands only while origin/main is still exactly the base the
        # gate and the landing-mode check saw. A move after the fetch above (even to an ancestor
        # of the tip, which a plain push would fast-forward over) or a push URL that is another
        # server is refused. base is an ancestor of tip, so this is never a rewrite.
        r = git(wt, "push", f"--force-with-lease={heads}:{base}", "origin", f"{tip}:{heads}")
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
    PROGRESS["pushed"] = pushed
    watch = _ci_watch(wt, main, pushed, a.ci_wait, warnings) if pushed else None
    if not has_origin:
        warnings.append("no origin remote: landed locally, nothing was pushed")
    return _landed(branch, main, pushed or tip, primary, warnings, remaining_extra, watch)


def _landed(branch, main, sha, primary, warnings, remaining_extra=(), watch=None) -> dict:
    remaining = ["if this session stands inside the worktree: ExitWorktree with action keep",
                 (f"wt -C {q(str(primary))} remove {q(branch)}" if primary else
                  f"from the main checkout (git could not name it): wt remove {q(branch)}"),
                 *remaining_extra]
    if watch:
        remaining.append(f"{watch}   # run in the background; a red run means fixing {main} next")
    return {"landed": True, "branch": branch, "main": main, "sha": sha,
            "watch": watch, "remaining": remaining, "warnings": warnings}


def _after_interrupt():
    """Measure, don't assume: where did the interrupted landing get? Returns a landed
    verdict when the push is confirmed on origin, otherwise a Stop describing the state."""
    p, msg = PROGRESS, "interrupted — check `git status` and rebase state in the worktree"
    wt, main, branch = p.get("wt"), p.get("main"), p.get("branch")
    if not wt:
        return Stop(UNKNOWN, msg, state="interrupted before the worktree was even read: nothing moved")
    w = q(str(wt))
    rebase = "a rebase is open in the worktree" if rebase_open(wt) else "no rebase is open"
    if "before" not in p:
        return Stop(UNKNOWN, msg, state=(f"interrupted during the preflight checks: nothing was merged or pushed "
                                         f"(local {main} may have been fast-forwarded to origin); {rebase}"),
                    commands=[f"git -C {w} status"])
    before, tip = p["before"], p.get("tip")   # tip: the sha the gate checked, captured before wt merge
    now = out(wt, "rev-parse", f"refs/heads/{main}")
    if not now:
        return Stop(UNKNOWN, msg, state=f"could not read {main} after the interrupt; {rebase}",
                    commands=[f"git -C {w} status", f"git -C {w} log --oneline -3 {q(main)}"])
    if now == before:
        return Stop(UNKNOWN, msg, state=f"{main} was not moved; nothing was pushed; {rebase}",
                    commands=[f"git -C {w} status", "then land again"])
    gated = bool(tip) and now == tip   # main is exactly what passed the gate
    if not p.get("has_origin"):
        if gated:
            return _landed(branch, main, now, p.get("primary"),
                           ["interrupted after the merge: landed locally (no origin remote); nothing was pushed"])
        return Stop(UNKNOWN, msg, state=f"{main} moved from {before[:9]} to {now[:9]}, which is not the checked "
                                        f"tip; {rebase}", commands=[f"git -C {w} log --oneline -3 {q(main)}"])
    git(wt, "fetch", "origin")   # best effort
    remote = out(wt, "rev-parse", f"refs/remotes/origin/{main}")
    if gated and remote == tip:
        return _landed(branch, main, now, p.get("primary"),
                       [f"interrupted after the push: origin/{main} is {now[:9]}, so this landed; "
                        "the remote-branch cleanup and the CI lookup may not have run"])
    base = p.get("base") or ""
    cmds = [f"git -C {w} log --oneline {q(f'origin/{main}..{main}')}   # what is not on origin"]
    if gated:   # only ever the sha that passed the gate
        lease = f" --force-with-lease={q(f'refs/heads/{main}:{base}')}" if base else ""
        cmds.append(f"git -C {w} push origin {tip}:{q(f'refs/heads/{main}')}{lease}"
                    f"   # finishes the landing only while origin/{main} is still {base[:9]} (the lease refuses otherwise)")
    return Stop(UNKNOWN, msg,
                state=(f"{main} moved from {before[:9]} to {now[:9]}"
                       + (" (the checked tip)" if gated else f", which is NOT the checked tip {(tip or '?')[:9]}")
                       + f", and it is not confirmed pushed: origin/{main} is {(remote or 'unknown')[:9]}; "
                       f"{rebase}. A plain re-run stops at exit 4 (local {main} ahead of origin)"),
                commands=cmds)


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
    previous_int = signal.getsignal(signal.SIGINT)
    try:
        v = land(a)
    except Stop as s:
        return _stopped(s.code, s.message, s.state, s.commands)
    except KeyboardInterrupt:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)   # one measurement, not interrupted again
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            v = _after_interrupt()
        except Exception as e:   # noqa: BLE001 — the verdict guarantee covers the measurement too
            v = Stop(UNKNOWN, "interrupted — and the state could not be measured; check `git status`, "
                              "`git log` of main and the rebase state in the worktree", state=repr(e))
        if isinstance(v, Stop):
            return _stopped(v.code, v.message, v.state, v.commands)
    except Exception as e:   # noqa: BLE001 — a verdict must always be printed; the lock is already released
        tb = traceback.format_exc()
        print(f"STOPPED (exit {UNKNOWN}): unexpected error: {e!r}", file=sys.stderr)
        print("\n".join(tb.strip().splitlines()[-12:]), file=sys.stderr)
        print(json.dumps({"landed": False, "code": UNKNOWN, "message": f"unexpected error: {e!r}"}))
        return UNKNOWN
    finally:
        signal.signal(signal.SIGTERM, previous)
        signal.signal(signal.SIGINT, previous_int)
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
