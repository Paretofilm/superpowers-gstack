#!/usr/bin/env python3
"""Land a wt worktree on main in one command — solo landing, no pull request.

Design: docs/superpowers/specs/2026-09-29-worktrunk-integration-design.md

Contract: exit 0 = landed (possibly with warnings). Any other code = stopped, in the
state the spec's exit-code table names. The script never runs `git reset`, never
retries by itself, never passes --yes or --no-hooks to wt, and never removes the
worktree (the caller leaves it first, then runs `wt remove`).

Usage: land-worktree.py [--worktree PATH] [--main-branch NAME] [--preflight-only]
                        [--ci-wait SECONDS]
The last stdout line is a JSON verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

MODE, UNAPPROVED, MAIN_AHEAD, OVERLAP, HOOK_RED, PUSH, NO_WT, NO_HOOK, REBASE, FETCH, LOCKED, DIRTY = (
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
USAGE, UNKNOWN = 64, 70

MODE_RE = re.compile(r"^Landing mode: (solo|pr)$", re.M)
HOOK_RE = re.compile(r"^[ \t]*(\[\[?pre-merge\]\]?[ \t]*$|pre-merge[ \t]*=)", re.M)


class Stop(Exception):
    def __init__(self, code, message, state="", commands=()):
        super().__init__(message)
        self.code, self.message, self.state, self.commands = code, message, state, list(commands)


def sh(*args, cwd=None):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def git(repo, *args):
    return sh("git", "-C", str(repo), *args)


def out(repo, *args):
    r = git(repo, *args)
    return r.stdout.strip() if r.returncode == 0 else None


def landing_mode(worktree: Path):
    f = worktree / "CLAUDE.md"
    if not f.is_file():
        return None
    m = MODE_RE.search(f.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


def has_pre_merge_hook(worktree: Path) -> bool:
    f = worktree / ".config" / "wt.toml"
    return f.is_file() and bool(HOOK_RE.search(f.read_text(encoding="utf-8", errors="replace")))


def unapproved(worktree: Path) -> bool:
    r = sh("wt", "-C", str(worktree), "config", "approvals", "list")
    if r.returncode != 0:
        return False   # unknown: `wt merge` decides, and its own message maps to code 3
    parts = r.stdout.split("UNAPPROVED", 1)
    return len(parts) == 2 and "❯" in parts[1]


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


def default_branch(repo) -> str:
    ref = out(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return ref.split("/", 1)[1] if ref and "/" in ref else "main"


def dirty_files(repo) -> set[str]:
    parts = git(repo, "status", "--porcelain", "-z").stdout.split("\0")
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
    return {p for p in r.stdout.split("\0") if p} if r.returncode == 0 else set()


class Lock:
    """Atomic per-repo lock: `mkdir` either creates the directory or fails."""

    def __init__(self, common_dir: Path):
        self.dir = common_dir / "gstack-land.lock"

    def _stale(self) -> bool:
        try:
            pid = int((self.dir / "pid").read_text())
        except (OSError, ValueError):
            try:   # no pid yet: only stale if it has been that way for a while
                return time.time() - self.dir.stat().st_mtime > 5
            except OSError:
                return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        return False

    def __enter__(self):
        for _ in range(2):
            try:
                self.dir.mkdir()
                (self.dir / "pid").write_text(str(os.getpid()))
                return self
            except FileExistsError:
                if self._stale():
                    shutil.rmtree(self.dir, ignore_errors=True)
                    continue
                break
        raise Stop(LOCKED, f"another landing holds {self.dir}",
                   commands=[f"cat '{self.dir}/pid'   # the process that holds it"])

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


def _classify(r, wt) -> Stop:
    text = r.stdout + r.stderr
    tail = "\n".join(text.strip().splitlines()[-12:])
    if "Cannot prompt for approval" in text or "needs approval" in text:
        return Stop(UNAPPROVED, "the project's hooks are not approved",
                    commands=[f"wt -C '{wt}' config approvals add"])
    if "pre-merge command failed" in text:
        return Stop(HOOK_RED, "a pre-merge check failed — fix it (never --no-hooks) and land again",
                    state="the branch was rebased onto main; main was not moved; worktree and branch stand",
                    commands=[f"wt -C '{wt}' hook pre-merge"])
    if ("Rebase onto" in text and "incomplete" in text) or "CONFLICT" in text:
        return Stop(REBASE, "rebasing onto main hit a conflict",
                    state="a rebase is open in the worktree; main was not moved",
                    commands=[f"git -C '{wt}' status",
                              f"git -C '{wt}' rebase --abort   # or resolve, then: git rebase --continue"])
    if "conflicting uncommitted changes" in text:
        return Stop(OVERLAP, "the worktree holding main has uncommitted changes in a file this landing touches",
                    state="nothing moved", commands=[tail])
    return Stop(UNKNOWN, "wt merge failed for a reason this script does not recognise", state=tail)


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
            return f"gh run watch {runs[0]['databaseId']} --exit-status"
        if time.time() >= deadline:
            break
        time.sleep(3)
    warnings.append(f"no CI run found for {sha[:9]} within {wait}s")
    return None


def land(a) -> dict:
    wt = Path(a.worktree).resolve()
    common = out(wt, "rev-parse", "--path-format=absolute", "--git-common-dir")
    branch = out(wt, "rev-parse", "--abbrev-ref", "HEAD")
    if not common or not branch:
        raise Stop(USAGE, f"{wt} is not a git worktree")
    main = a.main_branch or default_branch(wt)
    if branch in ("HEAD", main):
        raise Stop(USAGE, f"{wt} is on '{branch}', not a feature branch — land from the feature worktree")
    with Lock(Path(common)):
        return _land_locked(a, wt, Path(common), branch, main)


def _land_locked(a, wt, common, branch, main) -> dict:
    mode = landing_mode(wt)
    if mode != "solo":
        raise Stop(MODE, (f"Landing mode is '{mode}', not 'solo'" if mode else
                          "CLAUDE.md has no exact 'Landing mode: solo' or 'Landing mode: pr' line (fails closed)"),
                   commands=["mode 'pr': use /ship", "no line: ask the user once, then write it under a heading the project owns"])
    if not has_pre_merge_hook(wt):
        raise Stop(NO_HOOK, "no pre-merge hook in .config/wt.toml — nothing would gate this landing",
                   commands=["propose a .config/wt.toml whose [pre-merge] runs the same commands as CI; the user approves it"])
    if not shutil.which("wt"):
        raise Stop(NO_WT, "wt (worktrunk) is not installed",
                   commands=["fall back to: git worktree add, then /superpowers:finishing-a-development-branch"])
    if unapproved(wt):
        raise Stop(UNAPPROVED, "the project's hooks are not approved",
                   commands=[f"wt -C '{wt}' config approvals add"])
    has_origin = out(wt, "remote", "get-url", "origin") is not None
    if has_origin and git(wt, "fetch", "origin").returncode != 0:
        raise Stop(FETCH, "git fetch origin failed")
    dirty = git(wt, "status", "--porcelain").stdout.strip()
    if dirty:
        raise Stop(DIRTY, "the worktree has uncommitted work — wt merge would commit it for you",
                   state=dirty, commands=["commit it, or move it: git switch -c wip/<topic>"])
    mw = next((w for w in worktrees(wt) if w.get("branch") == main), None)
    feature = changed(wt, f"{main}...{branch}")
    theirs = changed(wt, main, f"origin/{main}") if has_origin else set()
    if mw:
        clash = sorted(dirty_files(mw["path"]) & (feature | theirs))
        if clash:
            raise Stop(OVERLAP, f"uncommitted files in {mw['path']} overlap this landing: {', '.join(clash)}",
                       state="nothing moved", commands=["commit them or move them to their own branch — never stash"])
    if has_origin:
        ahead = git(wt, "log", "--oneline", f"origin/{main}..{main}").stdout.strip()
        if ahead:
            raise Stop(MAIN_AHEAD, f"local {main} has commits that are not on origin (they would ride along unchecked)",
                       state=ahead)
        r = (git(mw["path"], "merge", "--ff-only", f"origin/{main}") if mw
             else git(wt, "fetch", "origin", f"{main}:{main}"))
        if r.returncode:
            raise Stop(MAIN_AHEAD, f"local {main} cannot fast-forward to origin/{main}", state=r.stderr.strip())
    base = out(wt, "rev-parse", f"origin/{main}") if has_origin else None
    if a.preflight_only:
        return {"landed": False, "preflight": "ok", "branch": branch, "main": main,
                "main_worktree": str(mw["path"]) if mw else None}

    merge = sh("wt", "-C", str(wt), "merge", "--no-squash", "--no-remove")
    if merge.returncode:
        raise _classify(merge, wt)
    if git(wt, "merge-base", "--is-ancestor", branch, main).returncode != 0:
        raise Stop(UNKNOWN, f"wt merge reported success but '{branch}' is not in {main}")

    warnings, pushed = [], None
    if has_origin:
        git(wt, "fetch", "origin")
        stop_cmds = [f"git -C '{wt}' log --oneline origin/{main}..{main}",
                     f"resolve in the worktree that has {main} checked out: git pull --rebase",
                     f"git -C '{wt}' push origin {main}"]
        if out(wt, "rev-parse", f"origin/{main}") != base:
            raise Stop(PUSH, f"origin/{main} moved while the checks ran — nothing was pushed",
                       state=f"local {main} already contains your commits; worktree and branch stand",
                       commands=stop_cmds)
        r = git(wt, "push", "origin", main)
        if r.returncode:
            raise Stop(PUSH, f"push of {main} was rejected", state=r.stderr.strip()[-600:], commands=stop_cmds)
        pushed = out(wt, "rev-parse", main)
        if git(wt, "ls-remote", "--exit-code", "--heads", "origin", branch).returncode == 0:
            r = git(wt, "push", "origin", "--delete", branch)
            if r.returncode:
                warnings.append(f"could not delete origin/{branch}: {r.stderr.strip()[-200:]}")
    watch = _ci_watch(wt, main, pushed, a.ci_wait, warnings) if pushed else None
    if not has_origin:
        warnings.append("no origin remote: landed locally, nothing was pushed")
    primary = str(common.parent)
    remaining = ["if this session stands inside the worktree: ExitWorktree with action keep",
                 f"wt -C '{primary}' remove {branch}"]
    if watch:
        remaining.append(f"{watch}   # run in the background; a red run means fixing {main} next")
    return {"landed": True, "branch": branch, "main": main, "sha": pushed or out(wt, "rev-parse", main),
            "watch": watch, "remaining": remaining, "warnings": warnings}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Land a worktree on main (solo landing, no pull request).")
    ap.add_argument("--worktree", default=os.getcwd())
    ap.add_argument("--main-branch")
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--ci-wait", type=int, default=30)
    ap.error = lambda msg: (print(f"land-worktree: {msg}", file=sys.stderr), sys.exit(USAGE))
    a = ap.parse_args(argv)
    try:
        v = land(a)
    except Stop as s:
        print(f"STOPPED (exit {s.code}): {s.message}", file=sys.stderr)
        if s.state:
            print(f"State: {s.state}", file=sys.stderr)
        for c in s.commands:
            print(f"  {c}", file=sys.stderr)
        print(json.dumps({"landed": False, "code": s.code, "message": s.message}))
        return s.code
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
