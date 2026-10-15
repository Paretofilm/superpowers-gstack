#!/usr/bin/env python3
"""scripts/work-state.py — what is landed, what is installed, and how to install it.

Standard library only, Python >= 3.11. Helpers (CLAUDE.md reading with the symlink rules,
fence regex, locking, git wrappers) are reused from land-worktree.py, never copied.

Subcommands:
  report  [--repo PATH] [--json-only]
      Print the work state of a project (landed vs. installed).
  install [--repo PATH] [--quit-running | --quit-path APP] [--accept-migration]
          [--replace-unstamped] [--applications-dir DIR]
      Install the landed build as the project's `Installable:` line says.

The project declares what installing means with one line in CLAUDE.md on origin/main,
outside fenced code blocks:
  Installable: macos-app <Scheme>   |   plugin   |   command <cmd>   |   none
A line with an unknown kind, `macos-app` without a scheme or `command` without a command
is invalid and counts as absent. Two different valid lines are a conflict.

Exit codes:
  0   ok
  64  usage error (no subcommand, unknown subcommand, bad flags)
  70  Python older than 3.11
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

INSTALLABLE_RE = re.compile(r"^Installable:[ \t]+(\S+)(?:[ \t]+(.+?))?[ \t]*$")

_land_module = None


def _load_land():
    """land-worktree.py loaded by path (hyphenated filename), once."""
    global _land_module
    if _land_module is None:
        path = Path(__file__).with_name("land-worktree.py")
        spec = importlib.util.spec_from_file_location("land_worktree", path)
        m = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("land_worktree", m)
        spec.loader.exec_module(m)
        _land_module = m
    return _land_module


def parse_installable(text: str):
    """("macos-app", scheme) | ("plugin", None) | ("command", cmd) | ("none", None);
    None when no valid line exists outside fences; "conflict" for two different valid lines."""
    land = _load_land()
    found, fence = set(), None
    for line in text.splitlines():
        m = land.FENCE.match(line)
        if m:
            mark = m.group(1)
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence) and line.strip() == mark:
                fence = None
            continue
        if fence is None:
            m = INSTALLABLE_RE.fullmatch(line)
            if not m:
                continue
            kind, rest = m.group(1), m.group(2)
            if kind in ("plugin", "none") and not rest:
                found.add((kind, None))
            elif kind in ("macos-app", "command") and rest:
                found.add((kind, rest))
    if len(found) > 1:
        return "conflict"
    return found.pop() if found else None


def installable_at(repo, rev):
    """The Installable: line of CLAUDE.md as committed at `rev` (None: no line or no file)."""
    found = _load_land().claude_md_at(Path(repo), rev)
    return parse_installable(found[1]) if found else None


def _result(status, detail, items=()):
    return {"status": status, "detail": detail, "items": list(items)}


def measure_committed(repo) -> dict:
    """Uncommitted files in this folder and in the main folder (when they differ)."""
    land = _load_land()
    repo = Path(repo)
    folders = [repo]
    primary = land.primary_worktree(repo)
    if primary and Path(primary).resolve() != repo.resolve():
        folders.append(Path(primary))
    files = set()
    for folder in folders:
        try:
            files |= land.dirty_files(folder)
        except land.Stop as e:
            return _result("unknown", f"git status failed in {folder}: {e}")
    items = sorted(files)
    if items:
        return _result("open", f"{len(items)} filer", items)
    return _result("ok", "0 filer")


def fetch_origin(repo):
    """`git fetch --quiet origin` (15 s). The error text, or None when it worked."""
    land = _load_land()
    try:
        r = subprocess.run(["git", "-C", str(repo), "fetch", "--quiet", "origin"],
                           capture_output=True, text=True, errors="replace",
                           stdin=subprocess.DEVNULL, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, timeout=15)
    except subprocess.TimeoutExpired:
        return "git fetch origin timed out after 15 s"
    if r.returncode:
        return (r.stderr.strip() or f"git fetch origin exited {r.returncode}")[-300:]
    return None


class _CountError(Exception):
    pass


def _count(land, repo, *args):
    r = land.git(repo, "rev-list", "--count", *args)
    out = r.stdout.strip()
    if r.returncode or not out.isdigit():
        raise _CountError(f"kunne ikke telle commits: {r.stderr.strip()[-200:] or 'ingen utdata'}")
    return int(out)


def measure_pushed(repo) -> dict:
    """Is everything on origin? Never proposes a force push."""
    land = _load_land()
    repo = Path(repo)
    base = {"safe_actions": [], "ask": []}
    if land.git(repo, "remote", "get-url", "origin").returncode:
        return {**_result("undefined", "– (ingen fjern-repo)"), **base}
    err = fetch_origin(repo)
    if err:
        return {**_result("unknown", f"kunne ikke hente fra origin: {err}"), **base}
    try:
        safe, ask, items = _pushed_scan(land, repo)
    except _CountError as e:
        return {**_result("unknown", str(e)), **base}
    if items:
        return {**_result("open", f"{len(items)} åpne", items), "safe_actions": safe, "ask": ask}
    return {**_result("ok", "alt er på origin"), **base}


def _pushed_scan(land, repo):
    safe, ask, items = [], [], []
    branch = land.out(repo, "symbolic-ref", "--short", "-q", "HEAD")
    if branch is None:
        n = _count(land, repo, "HEAD", "--not", "--remotes")
        if n:
            items.append(f"detached HEAD: {n} commits no remote has")
            ask.append("detached HEAD has commits no remote has; give them a branch and push it")
    else:
        upstream = land.out(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
        if upstream:
            n = _count(land, repo, "@{upstream}..HEAD")
            if n:
                items.append(f"{branch}: {n} commits not on {upstream}")
                if branch == land.default_branch(repo):
                    ask.append(f"{branch} has {n} commits not landed through land")
                elif land.git(repo, "merge-base", "--is-ancestor", upstream, "HEAD").returncode == 0:
                    safe.append(["git", "-C", str(repo), "push"])
                else:
                    ask.append(f"push of '{branch}' would need force")
        else:
            n = _count(land, repo, "HEAD", "--not", "--remotes")
            if n:
                items.append(f"{branch}: {n} commits no remote has (no upstream)")
                ask.append(f"'{branch}' has no upstream; push it with: git push -u origin {branch}")
    main = land.default_branch(repo)
    if (main and branch != main and land.git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{main}").returncode == 0
            and land.git(repo, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{main}").returncode == 0):
        n = _count(land, repo, f"origin/{main}..{main}")
        if n:
            items.append(f"{main}: {n} commits not on origin/{main}")
            ask.append(f"{main} has {n} commits not landed through land")
    return safe, ask, items


def cmd_report(args) -> int:
    raise NotImplementedError("report is implemented in a later task")


def cmd_install(args) -> int:
    raise NotImplementedError("install is implemented in a later task")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work-state", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("report", help="print the work state")
    r.add_argument("--repo", type=Path, default=Path.cwd())
    r.add_argument("--json-only", action="store_true")
    r.set_defaults(func=cmd_report)
    i = sub.add_parser("install", help="install the landed build")
    i.add_argument("--repo", type=Path, default=Path.cwd())
    g = i.add_mutually_exclusive_group()
    g.add_argument("--quit-running", action="store_true")
    g.add_argument("--quit-path", metavar="APP")
    i.add_argument("--accept-migration", action="store_true")
    i.add_argument("--replace-unstamped", action="store_true")
    i.add_argument("--applications-dir", type=Path, help=argparse.SUPPRESS)
    i.set_defaults(func=cmd_install)
    return p


def main(argv=None) -> int:
    if sys.version_info < (3, 11):
        print("Python >= 3.11 required", file=sys.stderr)
        return 70
    parser = build_parser()
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as e:
        return 0 if e.code in (0, None) else 64
    if not getattr(args, "func", None):
        parser.print_usage(sys.stderr)
        return 64
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
