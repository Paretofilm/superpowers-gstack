#!/usr/bin/env python3
"""scripts/work-state.py — what is landed, what is installed, and how to install it.

Standard library only, Python >= 3.11. Helpers (CLAUDE.md reading with the symlink rules,
fence regex, git wrappers, quoting, the default branch and the work folders) are reused from
land-worktree.py, never copied. Locking is this script's own `_Flock`: the same kernel lock
(flock) as land's `Lock`, but it can wait a bounded time, which land's lock never does
(install waits up to 60 s for land's `gstack-land.lock`).

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

Exit codes (report; the last stdout line is the JSON object, also when the report itself fails):
  0   no part is open, unknown or stale (installable `undefined`/`none` and "no remote" count as done)
  1   something is open, unknown or stale, or the report could not be assembled
  2   --repo is not a git repository
  64  usage error (no subcommand, unknown subcommand, bad flags)
  70  Python older than 3.11
Exit codes (install; the last stdout line is {"status", "code", "reason", "commit"}, and every
run that holds the install lock stores the same object in <git dir>/gstack-install-result.json):
  0   installed ("installed"), or the stamp already proves origin/main is installed ("current")
  2   the Installable: line is not macos-app, or missing (or --repo is not a git repository)
  3   the main folder is not on main, is not clean, pull --ff-only failed, or main != origin/main
  4   the app runs (--quit-running / --quit-path ask it to quit itself; never kill)
  5   the span since the stamp may change data on disk, or cannot be measured (--accept-migration)
  6   a copy without a stamp is in the way (--replace-unstamped)
  7   another app (or one that cannot be identified) has the name; no flag helps
  8   the build failed; the reason names <git dir>/gstack-install-build.log; nothing was touched
  9   the check failed and the old copy is untouched: before the swap the temporary copy is removed;
      at the final path the swap is rolled back (R4'); nothing is stamped either way. The previous
      version goes to the Trash only after the check at the final path has passed
  10  the applications folder is missing or not writable (or macOS refused the swap); never sudo
  11  main moved during the build; nothing was swapped or stamped
  12  another install holds the lock, or land held its lock longer than 60 s
  64  usage error (no subcommand, unknown subcommand, bad flags, scheme/settings not usable)
  70  unexpected error (state printed), interrupted by SIGTERM/SIGINT ("avbrutt"), or Python < 3.11

Hidden test knobs (environment): GSTACK_QUIT_DEADLINE, GSTACK_LAND_LOCK_WAIT, GSTACK_FINDER_TIMEOUT (s),
GSTACK_LSREGISTER (the lsregister binary), GSTACK_SWAP=rename (outside macOS only: plain renames
instead of renamex_np, so the tests run on Linux CI); --applications-dir replaces /Applications.

Known limits:
  - `Installable: command <cmd>` runs shell text from the repository (`sh -c`, in the main folder,
    120 s) during `report`, without the approval step that `wt` hooks have. That command is the
    project's own responsibility: do not run `report` in an untrusted clone with such a line. The
    measurement reflects the main folder's working tree, not the landed commit.
  - When both Trash routes fail and a copy cannot be renamed back to its hidden
    `.<name>.gstack-new-<pid>` name, it stays under its visible dated name, and no later sweep
    finds it. The reason names the path; the user must move it.
  - A signal that arrives inside a critical section that then fails with another error is
    dropped: the real error's code wins.
  - The first install that replaces an old copy may trigger macOS's «wants to control Finder»
    prompt. Granting it makes trashing instant. Without it the Finder attempt gives up after
    FINDER_TIMEOUT (15 s), the reason says Finder did not answer, and the old copy goes straight to
    ~/.Trash. Privacy settings can block that too; the old copy then keeps its hidden name, and the
    next run retries.
"""
from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import glob
import importlib.util
import io
import json
import os
import plistlib
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
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


_UNFETCHED = object()


def measure_pushed(repo, fetched=_UNFETCHED) -> dict:
    """Is everything on origin? Never proposes a force push. `fetched` is the outcome of a
    fetch the caller already made (None: worked, else the error text); by default this fetches."""
    land = _load_land()
    repo = Path(repo)
    base = {"safe_actions": [], "ask": []}
    if land.git(repo, "remote", "get-url", "origin").returncode:
        return {**_result("undefined", "– (ingen fjern-repo)"), **base}
    err = fetch_origin(repo) if fetched is _UNFETCHED else fetched
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


CACHE_DIRS = (".gstack/", "node_modules/", ".build/", "DerivedData/", "__pycache__/", ".pytest_cache/")
_CACHE_NAMES = frozenset(d.rstrip("/") for d in CACHE_DIRS)


def _landed_state(land, repo, branch) -> bool:
    """Proven landed: ancestor of origin/<default> AND a commit in the branch's own reflog.
    Raises _CountError when git itself fails (that is unknown, never 'not landed')."""
    main = land.default_branch(repo)
    if not main or land.git(repo, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{main}").returncode:
        return False
    r = land.git(repo, "merge-base", "--is-ancestor", f"refs/heads/{branch}", f"origin/{main}")
    if r.returncode == 1:
        return False
    if r.returncode:
        raise _CountError(f"kunne ikke avgjøre om {branch} er landet: {r.stderr.strip()[-200:]}")
    log = land.git(repo, "reflog", "show", "--format=%gs", f"refs/heads/{branch}")
    if log.returncode:
        raise _CountError(f"kunne ikke lese reflog for {branch}: {log.stderr.strip()[-200:]}")
    return any(line.startswith("commit") for line in log.stdout.splitlines())


def _cwds() -> list[str]:
    """Working directories of all processes (`lsof -d cwd -Fn`). Raises when lsof cannot run."""
    try:
        r = subprocess.run(["lsof", "-d", "cwd", "-Fn"], capture_output=True, text=True, errors="replace",
                           stdin=subprocess.DEVNULL, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise _CountError(f"kunne ikke kjøre lsof: {e}")
    if not r.stdout.strip():   # lsof always lists at least itself: nothing means it failed
        raise _CountError(f"lsof ga ingen utdata (exit {r.returncode})")
    return [line[1:] for line in r.stdout.splitlines() if line.startswith("n")]


def in_use(path, cwds=None) -> bool:
    """Does a process have its working directory in `path`? Whole path components only.
    `cwds` is a list already read with _cwds(); without it, lsof runs now."""
    cands = {str(path), str(Path(path).resolve())}
    prefixes = tuple(c.rstrip(os.sep) + os.sep for c in cands)
    return any((c.rstrip(os.sep) + os.sep).startswith(prefixes) for c in (_cwds() if cwds is None else cwds))


def _status_entries(land, path):
    # Explicit flags: status.showUntrackedFiles=no must not hide untracked work (as land.dirty_files).
    r = land.git(path, "status", "--porcelain", "-z", "--ignored", "--untracked-files=all", "--ignore-submodules=none")
    if r.returncode:
        raise _CountError(f"git status failed in {path}: {r.stderr.strip()[-200:]}")
    return [e for e in r.stdout.split("\0") if e]


def _is_clean(land, path) -> bool:
    """Empty `git status --porcelain --ignored`, or only ignored cache content."""
    for e in _status_entries(land, path):
        if not e.startswith("!! ") or not _is_cache_path(e[3:]):
            return False
    return True


def _is_cache_path(rel: str) -> bool:
    """A relative path lies under a cache directory (the directory itself may be listed)."""
    parts = rel.rstrip("/").split("/")
    dirs = parts if rel.endswith("/") else parts[:-1]
    return any(p in _CACHE_NAMES for p in dirs)


def all_cache(path) -> bool:
    """Every file below `path` lies under a cache directory (an empty folder has nothing to lose)."""
    root = Path(path)

    def unreadable(e):
        raise _CountError(f"kunne ikke lese {e.filename}: {e.strerror}")

    for dirpath, dirnames, filenames in os.walk(root, onerror=unreadable):
        rel = Path(dirpath).relative_to(root)
        if any(p in _CACHE_NAMES for p in rel.parts):
            dirnames[:] = []
            continue
        if filenames:
            return False
    return True


def _worktree_entries(land, repo) -> list[dict]:
    """`git worktree list --porcelain` with the `prunable` and `locked` markers that
    land.worktrees() drops. Raises when git fails or lists nothing."""
    r = land.git(repo, "worktree", "list", "--porcelain")
    if r.returncode:
        raise _CountError(f"git worktree list failed: {r.stderr.strip()[-200:]}")
    items, cur = [], {}
    for line in r.stdout.splitlines() + [""]:
        if not line:
            if cur:
                items.append(cur)
            cur = {}
        elif line.startswith("worktree "):
            cur["path"] = Path(line[len("worktree "):])
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch "):].removeprefix("refs/heads/")
        elif line == "prunable" or line.startswith("prunable "):
            cur["prunable"] = True
        elif line == "locked" or line.startswith("locked "):
            cur["locked"] = True
    if not items:
        raise _CountError("git worktree list ga ingen utdata")
    return items


_PULL_STATE_TEXT = {
    "dirty": "hovedmappen er ikke ren",
    "not-on-main": "hovedmappen står ikke på standardgrenen",
    "diverged": "den og origin har skilt lag",
    "unknown": "hovedmappen kunne ikke måles",
}


def _main_folder_pull_state(land, primary: Path, main) -> str:
    """R12. "has-all": local main already has everything on origin/main (equal or ahead);
    "pullable": behind, clean and on main, so `pull --ff-only` there is safe; else the reason
    it is not ("dirty", "not-on-main", "diverged", "unknown")."""
    if not main:
        return "unknown"
    local = land.out(primary, "rev-parse", "--verify", "--quiet", f"refs/heads/{main}^{{commit}}")
    remote = land.out(primary, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{main}^{{commit}}")
    if not local or not remote:
        return "unknown"
    if local == remote:
        return "has-all"
    behind = land.git(primary, "merge-base", "--is-ancestor", local, remote).returncode
    if behind == 1:
        ahead = land.git(primary, "merge-base", "--is-ancestor", remote, local).returncode
        return "has-all" if ahead == 0 else ("diverged" if ahead == 1 else "unknown")
    if behind:
        return "unknown"
    if land.out(primary, "symbolic-ref", "--short", "-q", "HEAD") != main:
        return "not-on-main"
    try:
        return "dirty" if land.dirty_files(primary) else "pullable"
    except land.Stop:
        return "unknown"


def measure_tidy(repo) -> dict:
    """Work folders, local branches and leftover sibling folders. Proposes, never executes."""
    land = _load_land()
    repo = Path(repo)
    base = {"safe_actions": [], "ask": []}
    try:
        return _tidy_scan(land, repo)
    except (_CountError, land.Stop) as e:
        return {**_result("unknown", f"kunne ikke måle mapper: {e}"), **base}


def _tidy_scan(land, repo):
    primary = land.primary_worktree(repo)
    top = land.out(repo, "rev-parse", "--show-toplevel")
    if not primary or not top:
        raise _CountError("fant ikke hovedmappen")
    primary, here = Path(primary), Path(top).resolve()
    safe, ask = [], []
    trees = _worktree_entries(land, repo)
    known = {Path(t["path"]).resolve() for t in trees}
    checked_out = {t["branch"] for t in trees if t.get("branch")}
    main = land.default_branch(repo)
    have_wt = shutil.which("wt") is not None
    pull_state = _main_folder_pull_state(land, primary, main)
    cwds = []                                   # lsof once per report, only when something needs it

    def busy(path):
        if not cwds:
            cwds.append(_cwds())
        return in_use(path, cwds[0])

    def needs_pull(branch):
        """R12: the branch's only proof is origin/main; the main folder's own main lacks it."""
        if land.git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{main}").returncode:
            return True                         # no local main at all: only origin proves it
        r = land.git(repo, "merge-base", "--is-ancestor", f"refs/heads/{branch}", f"refs/heads/{main}")
        if r.returncode not in (0, 1):
            raise _CountError(f"kunne ikke avgjøre om {main} har {branch}: {r.stderr.strip()[-200:]}")
        return r.returncode == 1

    def blocked(branch, what):
        """Only an origin/main proof, and the main folder cannot be pulled: no removal (R12)."""
        if pull_state != "pullable" and needs_pull(branch):
            ask.append(f"{what}: landet på origin/{main}, men ikke i hovedmappens {main} "
                       f"({_PULL_STATE_TEXT.get(pull_state, pull_state)}); pull main i hovedmappen først")
            return True
        return False

    for t in trees:
        path = Path(t["path"])
        branch = t.get("branch")
        if path.resolve() == primary.resolve():
            continue
        if t.get("prunable"):
            ask.append(f"{path} finnes ikke lenger; rydd oppføringen med: git -C {primary} worktree prune")
            continue
        if t.get("locked"):
            ask.append(f"{path} er låst (git worktree lock); den fjernes ikke")
            continue
        if path.resolve() == here:
            if branch and _landed_state(land, repo, branch):
                ask.append(f"{path}: arbeidsmappen du står i ({branch}) ryddes etter ExitWorktree")
            continue
        if busy(path):
            ask.append(f"{path} i bruk")
        elif not branch:
            ask.append(f"{path} har ingen gren (frakoblet HEAD)")
        elif not _landed_state(land, repo, branch):
            ask.append(f"{path}: grenen {branch} er ikke bevist landet")
        elif not _is_clean(land, path):
            ask.append(f"{path}: har uncommittede eller ignorerte filer som ikke er hurtigbuffer")
        elif blocked(branch, f"{path} ({branch})"):
            pass
        elif have_wt:
            # --foreground: the removal is done when wt returns, so the next `report` does not see it.
            safe.append(["wt", "-C", str(primary), "remove", "--foreground", branch])
        else:
            safe.append(["git", "-C", str(primary), "worktree", "remove", str(path)])
            safe.append(["git", "-C", str(primary), "branch", "-d", branch])
    r = land.git(repo, "for-each-ref", "--format=%(refname:lstrip=2)", "refs/heads")
    if r.returncode:
        raise _CountError(f"kunne ikke liste grener: {r.stderr.strip()[-200:]}")
    for name in r.stdout.split():
        if name in checked_out or name == main:
            continue
        if not _landed_state(land, repo, name):
            ask.append(f"{name} er ikke bevist landet")
        elif not blocked(name, name):
            safe.append(["git", "-C", str(primary), "branch", "-d", name])
    if safe and pull_state == "pullable":       # R12: once, before the removals
        safe.insert(0, ["git", "-C", str(primary), "pull", "--ff-only"])
    if primary.parent.is_dir():
        for d in sorted(primary.parent.glob(glob.escape(primary.name) + ".*")):
            if not d.is_dir() or d.resolve() in known:
                continue
            if d.is_symlink():
                ask.append(f"{d}: er en symbolsk lenke; den flyttes ikke til papirkurven")
            elif busy(d):
                ask.append(f"{d} i bruk")
            elif all_cache(d):
                # The path is an argument, never interpolated into the AppleScript source.
                safe.append(["osascript", "-e", "on run argv", "-e",
                             'tell application "Finder" to delete (POSIX file (item 1 of argv))',
                             "-e", "end run", str(d)])
            else:
                ask.append(f"{d}: rest med annet innhold enn hurtigbuffer")
    items = [" ".join(a) for a in safe] + list(ask)
    if not safe and not ask:
        return {**_result("ok", "ingen rester"), "safe_actions": [], "ask": []}
    detail = f"{len(safe)} kan ryddes, {len(ask)} må avgjøres"
    return {**_result("open", detail, items), "safe_actions": safe, "ask": ask}


STAMP_FILE = "gstack-installed-app.json"
RESULT_FILE = "gstack-install-result.json"


def gitdir(repo) -> Path:
    """The common git directory (shared by all work folders), resolved."""
    r = _load_land().git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    out = r.stdout.strip()
    if r.returncode or not out:
        raise _CountError(f"fant ikke git-mappen: {r.stderr.strip()[-200:] or 'ingen utdata'}")
    return Path(out).resolve()


def _read_json(path):
    """(data, None) | (None, None) when the file is absent | (None, reason) when unreadable or not an object."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as e:
        return None, f"kunne ikke lese {path}: {e}"
    try:
        data = json.loads(text)
    except ValueError as e:
        return None, f"{path} er ikke gyldig JSON: {e}"
    if not isinstance(data, dict):
        return None, f"{path} har uventet innhold"
    return data, None


def _bundle_id(app_path):
    """(bundle id, None) | (None, reason). plistlib reads XML and binary plists on every platform."""
    plist = Path(app_path) / "Contents" / "Info.plist"
    try:
        with open(plist, "rb") as f:
            data = plistlib.load(f)
    except (OSError, ValueError, plistlib.InvalidFileException) as e:
        return None, f"kunne ikke lese {plist}: {e}"
    bid = data.get("CFBundleIdentifier") if isinstance(data, dict) else None
    if not isinstance(bid, str) or not bid:
        return None, f"{plist} har ingen CFBundleIdentifier"
    return bid, None


def stamp_is_current(repo, stamp, head) -> bool:
    """Does the stamp prove that the installed app is `head`? Commit, app folder and bundle id must all match."""
    try:
        if not isinstance(stamp, dict) or not head:
            return False
        r = _load_land().git(repo, "rev-parse", "--verify", "--quiet", f"{head}^{{commit}}")
        if r.returncode or stamp.get("commit") != r.stdout.strip():
            return False
        app = stamp.get("app_path")
        if not isinstance(app, str) or not app or not Path(app).is_dir():
            return False
        want = stamp.get("bundle_id")
        return bool(want) and _bundle_id(app)[0] == want
    except (OSError, ValueError):
        return False


def _inst(kind, status, detail, items=(), safe=(), ask=()):
    return {"kind": kind, **_result(status, detail, items), "safe_actions": list(safe), "ask": list(ask)}


def _line_ref(land, repo):
    """(ref, has_origin_ref, remote_without_it): the line is read from origin/<default>; the local
    default branch is the fallback only when there is no remote at all."""
    main = land.default_branch(repo)
    if not main:
        return None, False, False
    if land.git(repo, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{main}").returncode == 0:
        return f"origin/{main}", True, False
    return main, False, land.git(repo, "remote", "get-url", "origin").returncode == 0


def measure_installable(repo) -> dict:
    """Section 'installerbar': the project's own Installable: line decides what it means."""
    land = _load_land()
    repo = Path(repo)
    try:
        ref, has_origin, unpushed = _line_ref(land, repo)
        if ref is None:
            return _inst("undefined", "unknown", "fant ingen standardgren å lese Installable: fra")
        head = land.out(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        if not head:
            return _inst("undefined", "unknown", f"kunne ikke lese {ref}")
        parsed = installable_at(repo, ref)
        if parsed is None or parsed == "conflict":
            return _inst("undefined", "undefined", "ikke definert, kjør /adapt")
        kind, arg = parsed
        if kind == "none":
            return _inst("none", "na", "–")
        if unpushed:    # a remote exists but origin/<main> does not: nothing is landed there yet
            return _inst(kind, "open", "main er ikke pushet")
        if kind == "macos-app":
            return _installable_app(repo, head, ref, has_origin)
        if kind == "plugin":
            return _installable_plugin(land, repo, ref, has_origin)
        return _installable_command(land, repo, arg)
    except (_CountError, land.Stop, OSError, subprocess.SubprocessError) as e:
        return _inst("undefined", "unknown", f"kunne ikke måle: {e}")


def _installable_app(repo, head, ref, has_origin=True):
    r = _installable_app_state(repo, head, ref)
    if not has_origin and r["status"] == "stale":
        # install pulls and builds origin/main, so without an `origin` remote it always stops at 3
        r["safe_actions"] = []
        r["detail"] += "; install trenger en origin-remote"
    return r


def _installable_app_state(repo, head, ref):
    gd = gitdir(repo)
    safe = [[sys.executable, os.path.abspath(__file__), "install", "--repo", str(repo)]]
    ask = []
    result, rerr = _read_json(gd / RESULT_FILE)
    if rerr:
        ask.append(rerr)
    elif (result and isinstance(result.get("code"), int) and not isinstance(result["code"], bool)
          and result["code"] != 0):     # R10: every stored stop, 2..70, until a run succeeds
        ask.append(f"siste install stoppet (kode {result['code']}): {result.get('reason', 'ukjent årsak')}")
    stamp, serr = _read_json(gd / STAMP_FILE)
    if serr:
        return _inst("macos-app", "unknown", serr, ask=ask)
    if stamp is None:
        return _inst("macos-app", "stale", "ikke installert fra denne maskinen", safe=safe, ask=ask)
    if stamp.get("commit") != head:
        return _inst("macos-app", "stale", f"installert {str(stamp.get('commit', '?'))[:7]}, {ref} er {head[:7]}",
                     safe=safe, ask=ask)
    app = stamp.get("app_path")
    if isinstance(app, str) and app and Path(app).is_dir():
        bid, berr = _bundle_id(app)
        if berr:    # cannot tell: no install proposal until the app can be read
            return _inst("macos-app", "unknown", berr, ask=ask)
    if not stamp_is_current(repo, stamp, head):
        return _inst("macos-app", "stale", "appen mangler eller har en annen bundle-ID enn stempelet",
                     safe=safe, ask=ask)
    return _inst("macos-app", "ok", f"{stamp.get('version') or head[:7]} installert", ask=ask)


def _extract_tree(repo, ref, dest):
    r = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", ref],
                       capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
    if r.returncode:
        raise _CountError(f"git archive feilet: {r.stderr.decode(errors='replace').strip()[-200:]}")
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
        if hasattr(tarfile, "data_filter"):
            tf.extractall(dest, filter="data")
        else:   # Python 3.11 before the filter backport: plain files and folders, no escaping paths
            for m in tf.getmembers():
                if m.name.startswith("/") or ".." in Path(m.name).parts or not (m.isfile() or m.isdir()):
                    continue
                tf.extract(m, dest)


def _installed_plugin_version(name):
    """(version | None, problem | None). A registry that exists but cannot be read is a problem, not 'absent'."""
    path = Path(os.path.expanduser("~")) / ".claude" / "plugins" / "installed_plugins.json"
    reg, err = _read_json(path)
    if err:
        return None, err
    plugins = reg.get("plugins") if reg else None
    if not isinstance(plugins, dict):
        return None, None
    for key, entries in plugins.items():
        if key.startswith(f"{name}@") and isinstance(entries, list) and entries and isinstance(entries[0], dict):
            return entries[0].get("version"), None
    return None, None


def _last_line(*texts):
    for t in texts:
        lines = [x for x in (t or "").strip().splitlines() if x.strip()]
        if lines:
            return lines[-1][:200]
    return ""


def _installable_plugin(land, repo, ref, has_origin):
    claude = shutil.which("claude")
    if not claude:
        return _inst("plugin", "unknown", "claude ikke funnet")
    with tempfile.TemporaryDirectory(prefix="work-state-plugin-") as tmp:
        _extract_tree(repo, ref, tmp)
        manifest, merr = _read_json(Path(tmp) / ".claude-plugin" / "plugin.json")
        if merr or manifest is None:
            return _inst("plugin", "open", merr or f"mangler .claude-plugin/plugin.json på {ref}")
        version, name = manifest.get("version"), manifest.get("name")
        if not isinstance(version, str) or not version:
            return _inst("plugin", "open", "plugin.json har ingen versjon")
        try:
            v = subprocess.run([claude, "plugin", "validate", tmp], capture_output=True, text=True,
                               errors="replace", stdin=subprocess.DEVNULL, timeout=120)
        except subprocess.TimeoutExpired:
            return _inst("plugin", "unknown", "claude plugin validate brukte over 120 s")
        if v.returncode:
            return _inst("plugin", "open", f"claude plugin validate avviste treet: {_last_line(v.stdout, v.stderr)}")
        try:
            changelog = (Path(tmp) / "CHANGELOG.md").read_text(encoding="utf-8", errors="replace")
        except OSError:
            changelog = ""
        if not re.search(rf"^## \[{re.escape(version)}\]", changelog, re.M):
            return _inst("plugin", "open", f"CHANGELOG.md har ingen oppføring for {version}")
    if has_origin:
        main = ref.split("/", 1)[1]
        if land.git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{main}").returncode == 0:
            n = _count(land, repo, f"{ref}..{main}")
            if n:
                return _inst("plugin", "open", f"lokal {main} har {n} commits som ikke er pushet")
    installed, problem = _installed_plugin_version(name) if isinstance(name, str) else (None, None)
    mine = "installert versjon kunne ikke leses" if problem else (f"du har {installed}" if installed else "ikke installert")
    return _inst("plugin", "ok", f"{version} på main, {mine}")


def _installable_command(land, repo, cmd):
    primary = land.primary_worktree(repo)
    if not primary:
        return _inst("command", "unknown", "fant ikke hovedmappen")
    try:
        r = subprocess.run(["sh", "-c", cmd], cwd=str(primary), capture_output=True, text=True, errors="replace",
                           stdin=subprocess.DEVNULL, timeout=120)
    except subprocess.TimeoutExpired:
        return _inst("command", "unknown", "kommandoen brukte over 120 s")
    except OSError as e:
        return _inst("command", "unknown", f"kunne ikke kjøre kommandoen: {e}")
    if r.returncode == 0:
        return _inst("command", "ok", "kommandoen ga kode 0")
    return _inst("command", "open", f"kommandoen ga kode {r.returncode}: {_last_line(r.stdout, r.stderr)}")


def _mark(part, show_items=False) -> str:
    status, detail = part.get("status"), part.get("detail", "")
    if status == "ok":
        return "✓"
    if status in ("open", "stale"):
        items = part.get("items") or []
        shown = "; ".join(items[:3]) if show_items and items else ""
        more = f" +{len(items) - 3}" if show_items and len(items) > 3 else ""
        return f"✗ ({detail}{': ' + shown + more if shown else ''})"
    if status == "unknown":
        return f"? ({detail})"
    return detail if detail.startswith("–") else "–"


def build_line(parts) -> str:
    """Tilstand: committet <m> · pushet <m> · mapper ryddet <m> · installerbar <m>. A tick only for status ok."""
    inst = parts["installable"]
    if inst.get("status") == "undefined":
        last = "installerbar: ikke definert, kjør /adapt"
    elif inst.get("status") == "na":
        last = "installerbar –"
    else:
        last = f"installerbar {_mark(inst)}"
        if inst.get("status") == "ok":
            last += f" ({inst['detail']})"
    return (f"Tilstand: committet {_mark(parts['committed'], True)} · pushet {_mark(parts['pushed'], True)}"
            f" · mapper ryddet {_mark(parts['tidy'])} · {last}")


def _guard(fn, *args):
    try:
        return fn(*args)
    except Exception as e:   # a measurement that crashes is unknown, never a clean result
        return _result("unknown", f"måling feilet: {type(e).__name__}: {e}")


def cmd_report(args) -> int:
    land = _load_land()
    repo = Path(args.repo)
    if not repo.is_dir() or land.git(repo, "rev-parse", "--git-dir").returncode:
        print(f"{repo} er ikke et git-repo", file=sys.stderr)
        return 2
    parts, line = {}, ""
    try:
        fetched = _UNFETCHED
        if land.git(repo, "remote", "get-url", "origin").returncode == 0:
            fetched = fetch_origin(repo)    # once; the pushed part reuses the outcome
        parts = {
            "committed": _guard(measure_committed, repo),
            "pushed": _guard(measure_pushed, repo, fetched),
            "tidy": _guard(measure_tidy, repo),
            "installable": _guard(measure_installable, repo),
        }
        parts["installable"].setdefault("kind", "undefined")
        safe, ask = [], []
        for key in ("pushed", "tidy", "installable"):
            safe += parts[key].get("safe_actions", [])
        for key in ("committed", "pushed", "tidy", "installable"):
            ask += parts[key].get("ask", [])
        line = build_line(parts)
        payload = json.dumps({"line": line, **parts, "safe_actions": safe, "ask": ask}, ensure_ascii=False)
    except Exception as e:   # the last stdout line must stay a JSON object, whatever happened
        line = line or "Tilstand: ukjent (rapporten feilet)"
        if not args.json_only:
            print(line)
        print(json.dumps({"line": line, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 1
    if not args.json_only:
        print(line)
    print(payload)
    return 1 if any(p.get("status") in ("open", "unknown", "stale") for p in parts.values()) else 0


# --- install (Part 3 of the spec) ----------------------------------------------------------
# Fails closed everywhere: a measurement that cannot be made is a stop, never a pass. Never
# sudo, never kill, never an override of the project's signing or settings.

CLASSIFY = Path(__file__).with_name("classify-change.py")
INSTALL_LOCK = "gstack-install.lock"
LAND_LOCK = "gstack-land.lock"
_NEW_COPY_RE = re.compile(r"^\.(.+)\.gstack-new-\d+$")
BUILD_DIR = "gstack-install-build"            # -derivedDataPath, so the next build is incremental
BUILD_LOG = "gstack-install-build.log"
BUILD_TIMEOUT = 3600
RENAME_SWAP = 0x2                             # <stdio.h>: renamex_np flag that exchanges two paths
RENAME_EXCL = 0x4                             # <stdio.h>: renamex_np fails when the target exists
FINDER_TIMEOUT = 15                           # s; an unanswered automation prompt would hang longer
FINDER_SILENT = ("; Finder svarte ikke (tillat at terminalen styrer Finder: Systeminnstillinger → "
                 "Personvern og sikkerhet → Automatisering)")
LSREGISTER = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework"
              "/Support/lsregister")
_BUNDLE_ID_RE = re.compile(r"^[A-Za-z0-9.-]+$")
_SETTING_RE = re.compile(r"^\s+([A-Z_][A-Z0-9_]*) = (.*)$")
_SETTINGS = (("BUILT_PRODUCTS_DIR", "built_products_dir"), ("FULL_PRODUCT_NAME", "full_product_name"),
             ("PRODUCT_BUNDLE_IDENTIFIER", "bundle_id"), ("EXECUTABLE_NAME", "executable_name"))


class Stop(Exception):
    """A stop with an exit code from the spec's table; `state` is what was measured."""

    def __init__(self, code, message, state=""):
        super().__init__(message)
        self.code, self.message, self.state = code, message, state


def _env_seconds(name, default):
    """A hidden test knob in seconds; anything unreadable is the default."""
    try:
        v = float(os.environ.get(name, default))
    except ValueError:
        return float(default)
    return v if v >= 0 else float(default)


class _Flock:
    """A kernel lock (flock) on a file in the git dir, waited for at most `wait` seconds.
    The kernel drops it when the holder goes away, so there is no stale lock to detect."""

    def __init__(self, path: Path, wait: float, message: str):
        self.path, self.wait, self.message, self.fd = Path(path), wait, message, None

    def __enter__(self):
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        end = time.monotonic() + self.wait
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= end:
                    os.close(fd)
                    raise Stop(12, self.message,
                               state=f"lsof {_load_land().q(str(self.path))}   # the process that holds it") from None
                time.sleep(0.2)
        self.fd = fd
        return self

    def __exit__(self, *exc):
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
        return False


class InstallLock(_Flock):
    """One install at a time per repository (`gstack-install.lock`), never waited for."""

    def __init__(self, common_dir: Path):
        path = Path(common_dir) / INSTALL_LOCK
        super().__init__(path, 0, f"en annen installering holder {path}")


def _land_lock(common_dir: Path):
    """land's own lock, held only while main is pulled; land may hold it for up to 60 s."""
    wait = _env_seconds("GSTACK_LAND_LOCK_WAIT", 60)
    return _Flock(Path(common_dir) / LAND_LOCK, wait,
                  f"land holdt {LAND_LOCK} lenger enn {wait:g} s; ingenting er hentet eller bygget")


def _run(argv, cwd=None, timeout=120, env=None):
    """argv list, no shell, no terminal. OSError and timeouts are left to the caller."""
    return subprocess.run([str(a) for a in argv], cwd=cwd, capture_output=True, text=True, errors="replace",
                          stdin=subprocess.DEVNULL, timeout=timeout, env=env)


def _clean_main_folder(land, primary: Path, after_xcodegen=False):
    """Ignored local files are fine (they are Local state); anything else is not, untracked
    included (Ruling R10): a stray untracked source file would be built into the Release copy,
    and classify-change.py folds untracked files into the migration span. The reason names the
    first files, so a stop stored in the background still says what to clean."""
    r = land.git(primary, "status", "--porcelain", "-z", "--untracked-files=all", "--ignore-submodules=none")
    if r.returncode:
        raise Stop(3, f"git status feilet i hovedmappen {primary}", state=r.stderr.strip()[-300:])
    entries = [e for e in r.stdout.split("\0") if e]
    if entries:
        files, parts = [], iter(entries)
        for e in parts:
            files.append(e[3:])
            if e[:1] in ("R", "C"):         # a rename or copy: the old path follows, no status
                next(parts, None)
        shown = ", ".join(files[:5]) + (f" (+{len(files) - 5})" if len(files) > 5 else "")
        what = (f"xcodegen generate endret eller lagde filer i hovedmappen {primary}: {shown}" if after_xcodegen
                else f"hovedmappen {primary} er ikke ren: {shown}")
        raise Stop(3, what, state="\n".join(entries[:20]))


def precondition_main(land, repo: Path, gd: Path):
    """Step 1: the main folder holds a clean main; pull --ff-only under land's lock; local main
    must then equal origin/main. Returns (main folder, commit to build)."""
    primary = land.primary_worktree(repo)
    main = land.default_branch(repo)
    if not primary or not main:
        raise Stop(3, "fant ikke hovedmappen eller standardgrenen")
    primary = Path(primary)
    branch = land.out(primary, "symbolic-ref", "--short", "-q", "HEAD")
    if branch != main:
        raise Stop(3, f"hovedmappen {primary} står på {branch or 'frakoblet HEAD'}, ikke {main}")
    _clean_main_folder(land, primary)
    with _land_lock(gd):
        try:
            r = _run(["git", "-C", primary, "pull", "--ff-only", "--no-rebase", "origin", main],
                     timeout=120, env=land.batch_env(primary))
        except subprocess.TimeoutExpired:
            raise Stop(3, "git pull --ff-only brukte over 120 s") from None
        if r.returncode:
            raise Stop(3, "git pull --ff-only feilet", state=(r.stderr.strip() or r.stdout.strip())[-300:])
        # Read under the lock: a land that moves main right after it is released is not a mismatch.
        head = land.out(primary, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
        upstream = land.out(primary, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{main}^{{commit}}")
    if not head or not upstream:
        raise Stop(3, f"kunne ikke lese HEAD eller origin/{main} etter hentingen")
    if head != upstream:
        raise Stop(3, f"lokal {main} er ikke lik origin/{main} (commits som ikke er pushet eller landet)",
                   state=f"{main} {head[:12]}, origin/{main} {upstream[:12]}")
    _clean_main_folder(land, primary)
    return primary, head


def _scheme_from_line(repo, ref):
    parsed = installable_at(repo, ref)
    if parsed is None or parsed == "conflict" or parsed[0] != "macos-app":
        what = "mangler" if parsed is None else ("står to ganger med ulike verdier" if parsed == "conflict"
                                                 else f"er '{parsed[0]}'")
        raise Stop(2, f"Installable:-linjen på {ref} {what}; install gjelder bare macos-app")
    return parsed[1]


def _container(primary: Path) -> list:
    """Workspace before project, as verify-and-land Phase 2; more than one is never guessed."""
    spaces = sorted(primary.glob("*.xcworkspace"))
    if len(spaces) > 1:
        raise Stop(64, f"flere arbeidsområder i {primary}: {', '.join(p.name for p in spaces)}")
    if spaces:
        return ["-workspace", str(spaces[0])]
    projects = sorted(primary.glob("*.xcodeproj"))
    if len(projects) > 1:
        raise Stop(64, f"flere prosjekter og ingen arbeidsområde i {primary}: {', '.join(p.name for p in projects)}")
    return ["-project", str(projects[0])] if projects else []


def _generate_if_needed(land, primary: Path):
    """`xcodegen generate` when project.yml is newer than the project (or there is none)."""
    spec = primary / "project.yml"
    if not spec.is_file():
        return
    pbx = [p / "project.pbxproj" for p in primary.glob("*.xcodeproj")]
    try:
        stale = not pbx or any(not p.is_file() or spec.stat().st_mtime > p.stat().st_mtime for p in pbx)
    except OSError as e:
        raise Stop(64, f"kunne ikke sammenligne project.yml med prosjektet: {e}") from None
    if not stale:
        return
    if not shutil.which("xcodegen"):
        raise Stop(64, "project.yml er nyere enn prosjektet, men xcodegen finnes ikke på PATH")
    try:
        r = _run(["xcodegen", "generate"], cwd=primary, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Stop(64, f"xcodegen generate feilet: {e}") from None
    if r.returncode:
        raise Stop(64, f"xcodegen generate ga kode {r.returncode}", state=_last_line(r.stderr, r.stdout))
    _clean_main_folder(land, primary, after_xcodegen=True)   # generated output that differs from the commit


def _parse_settings(text: str) -> list[dict]:
    sections, cur = [], {}
    for line in text.splitlines():
        if line.startswith("Build settings for "):
            if cur:
                sections.append(cur)
            cur = {}
            continue
        m = _SETTING_RE.match(line)
        if m:
            cur.setdefault(m.group(1), m.group(2).strip())
    if cur:
        sections.append(cur)
    return sections


def _distinct(sections):
    return {(s.get("FULL_PRODUCT_NAME"), s.get("PRODUCT_BUNDLE_IDENTIFIER")) for s in sections}


def _pick_app_section(apps: list[dict], scheme: str) -> list[dict]:
    """A scheme may also build helper apps or login items. The app is the section whose
    TARGET_NAME is the scheme, else the one named <scheme>.app; still several is never guessed."""
    if len(_distinct(apps)) <= 1:
        return apps
    for match in ([s for s in apps if s.get("TARGET_NAME") == scheme],
                  [s for s in apps if s.get("FULL_PRODUCT_NAME") == f"{scheme}.app"]):
        if match and len(_distinct(match)) == 1:
            return match
    names = ", ".join(sorted(str(n) for n, _ in _distinct(apps)))
    raise Stop(64, f"skjemaet '{scheme}' bygger flere apper, og ingen heter som skjemaet: {names}")


def discover_build(repo, scheme, derived=None) -> dict:
    """Step 2: container, scheme and the four settings, read through the Release macOS destination.
    `derived` is the build's -derivedDataPath, so BUILT_PRODUCTS_DIR is where the build puts the app."""
    land = _load_land()
    primary = Path(repo)
    _generate_if_needed(land, primary)
    container = _container(primary)
    argv = ["xcodebuild", *container, "-showBuildSettings", "-configuration", "Release",
            "-destination", "platform=macOS", "-scheme", scheme,
            *(["-derivedDataPath", str(derived)] if derived else [])]
    try:
        r = _run(argv, cwd=primary, timeout=300)
    except OSError as e:
        raise Stop(64, f"kunne ikke kjøre xcodebuild: {e}") from None
    except subprocess.TimeoutExpired:
        raise Stop(70, "xcodebuild -showBuildSettings brukte over 300 s") from None
    if r.returncode:
        raise Stop(64, f"xcodebuild -showBuildSettings for skjemaet '{scheme}' ga kode {r.returncode}",
                   state=_last_line(r.stderr, r.stdout))
    sections = _parse_settings(r.stdout)
    apps = _pick_app_section([s for s in sections if s.get("FULL_PRODUCT_NAME", "").endswith(".app")], scheme)
    settings = apps[0] if apps else (sections[0] if len(sections) == 1 else {})
    missing = [k for k, _ in _SETTINGS if not settings.get(k)]
    if missing:
        raise Stop(64, f"xcodebuild oppga ikke {', '.join(missing)} for skjemaet '{scheme}'")
    info = {key: settings[k] for k, key in _SETTINGS}
    name, exe, bid = info["full_product_name"], info["executable_name"], info["bundle_id"]
    if not name.endswith(".app") or "/" in name or name.startswith("."):
        raise Stop(64, f"FULL_PRODUCT_NAME '{name}' er ikke en app-bunt")
    if "/" in exe or exe in (".", ".."):
        raise Stop(64, f"EXECUTABLE_NAME '{exe}' er ugyldig")
    if not _BUNDLE_ID_RE.fullmatch(bid):
        raise Stop(64, f"PRODUCT_BUNDLE_IDENTIFIER '{bid}' er ugyldig")
    info["container"] = container
    return info


def _processes() -> list[tuple[int, str]]:
    """(pid, comm) from `ps -Axo pid=,comm=`. A ps that fails is a stop, never 'not running'."""
    try:
        r = _run(["ps", "-Axo", "pid=,comm="], timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Stop(70, f"kunne ikke liste prosessene (ps): {e}") from None
    if r.returncode:
        raise Stop(70, f"ps ga kode {r.returncode}; kan ikke vite om appen kjører", state=_last_line(r.stderr))
    procs = []
    for line in r.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            procs.append((int(parts[0]), parts[1]))
    return procs


def _spellings(path) -> set[str]:
    return {str(path), os.path.realpath(str(path))}


def app_instances(executable_name, bundle_id) -> list[tuple[int, str]]:
    """Every running copy of the app, wherever its bundle lies: `comm` ends in
    /Contents/MacOS/<exe> and the bundle three levels up has our bundle id. A bundle that cannot
    be read counts as ours (fails closed); a readable other bundle id is another app."""
    suffix = f"/Contents/MacOS/{executable_name}"
    found = []
    for pid, comm in _processes():
        if not comm.endswith(suffix) or len(comm) == len(suffix):
            continue
        other, problem = _bundle_id(Path(comm).parent.parent.parent)
        if problem or other == bundle_id:
            found.append((pid, comm))
    return found


def quit_app(bundle_id, executable_name, deadline=None) -> bool:
    """Ask the app to quit itself and wait until no copy of it runs anywhere.
    Never kill, never relaunch. True when they are all gone within the deadline."""
    if deadline is None:
        deadline = _env_seconds("GSTACK_QUIT_DEADLINE", 20)
    if not _BUNDLE_ID_RE.fullmatch(bundle_id):
        raise Stop(64, f"ugyldig bundle-ID '{bundle_id}'")
    end = time.monotonic() + deadline
    # `is running` never launches the app; a bare `tell` would start it if it quit in between.
    script = f'if application id "{bundle_id}" is running then tell application id "{bundle_id}" to quit'
    try:
        _run(["osascript", "-e", script], timeout=max(deadline, 1))
    except subprocess.TimeoutExpired:
        pass        # the app may be showing a dialog; the poll below decides
    except OSError as e:
        raise Stop(4, f"kunne ikke be appen avslutte seg selv (osascript): {e}") from None
    while True:
        if not app_instances(executable_name, bundle_id):
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(1)


def migration_signal(repo, stamp_commit, head):
    """(signal, reason) for the span stamp..head. Anything that cannot be measured is a signal."""
    land = _load_land()
    repo = Path(repo)
    if not isinstance(stamp_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", stamp_commit):
        return True, "stempelet har ingen gyldig commit; spennet er ukjent"
    if land.git(repo, "cat-file", "-e", f"{stamp_commit}^{{commit}}").returncode:
        return True, f"stempelets commit {stamp_commit[:12]} finnes ikke lenger; spennet er ukjent"
    r = land.git(repo, "merge-base", "--is-ancestor", stamp_commit, head)
    if r.returncode == 1:
        return True, f"stempelets commit {stamp_commit[:12]} er ikke i historikken til {head[:12]}; spennet er ukjent"
    if r.returncode:
        return True, f"kunne ikke avgjøre spennet: {r.stderr.strip()[-200:]}"
    d = land.git(repo, "diff", "--quiet", stamp_commit, head, "--")
    if d.returncode == 0:
        return False, "ingen endringer siden stempelet"
    if d.returncode != 1:
        return True, f"kunne ikke lese endringene siden stempelet: {d.stderr.strip()[-200:]}"
    env = {k: v for k, v in os.environ.items()
           if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY")}
    try:
        c = _run([sys.executable, CLASSIFY, "--diff", "--diff-base", stamp_commit], cwd=repo, timeout=120, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return True, f"classify-change.py kunne ikke kjøres: {e}"
    if c.returncode:
        return True, f"classify-change.py ga kode {c.returncode}: {_last_line(c.stderr, c.stdout)}"
    try:
        result = json.loads(c.stdout)
        signals = result["signals"]
        degraded = bool(result["target"].get("degraded"))
        labels = {s["label"] for s in signals}
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        return True, f"classify-change.py ga utdata som ikke kunne leses: {e}"
    if degraded:
        return True, "classify-change.py kunne ikke lese innholdet i endringene (degraded)"
    if "migration" in labels:
        ev = next((s.get("evidence", "") for s in signals if s.get("label") == "migration"), "")
        return True, f"endringene siden {stamp_commit[:12]} kan endre data på disk ({ev})"
    return False, "ingen migreringssignal"


def _free_name(folder: Path, name: str) -> Path:
    """`name` in `folder`, or `<stem> 2.app`, `<stem> 3.app` … when it is taken."""
    stem, suffix = (name[:-4], ".app") if name.endswith(".app") else (name, "")
    candidate, n = folder / name, 2
    while os.path.lexists(candidate):
        candidate, n = folder / f"{stem} {n}{suffix}", n + 1
    return candidate


def _old_name(stem: str) -> str:
    """The visible name a previous version gets in the Trash: Finder hides dot-names there too."""
    return f"{stem} {time.strftime('%Y-%m-%d %H.%M.%S')}.app"


def _to_trash(path: Path, visible: str):
    """Move a previous version to the Trash, never delete it: (where, None) | (None, problem).
    It is first renamed to the visible name next to itself. Then Finder, with the path as an
    AppleScript argument (never in the source), so Put Back works; it counts only when the path is
    gone afterwards. Without Finder: ~/.Trash/<visible>, with a free name. When both fail, the
    copy gets its hidden `.<name>.gstack-new-<pid>` name back, so the next run's sweep retries:
    never a visible dated duplicate in the applications folder."""
    original = path = Path(path)
    try:
        named = _free_name(path.parent, visible)
        os.rename(path, named)
        path = named
    except OSError:
        pass                        # trashed under its own name rather than not at all
    silent = ""
    wait = _env_seconds("GSTACK_FINDER_TIMEOUT", FINDER_TIMEOUT)
    try:
        r = _run(["osascript", "-e", "on run argv", "-e",
                  'tell application "Finder" to delete (POSIX file (item 1 of argv))', "-e", "end run",
                  str(path)], timeout=wait)
        if r.returncode == 0 and not os.path.lexists(path):
            return "papirkurven", None
        if "-1712" in r.stderr or "-1743" in r.stderr:      # AppleEvent timed out / not authorised
            silent = FINDER_SILENT
    except subprocess.TimeoutExpired:
        silent = FINDER_SILENT      # macOS's «wants to control Finder» prompt nobody can answer
    except OSError:
        pass
    try:
        trash = Path.home() / ".Trash"
        trash.mkdir(exist_ok=True)
        dest = _free_name(trash, visible)
        shutil.move(str(path), str(dest))
        return f"papirkurven ({dest}){silent}", None
    except (OSError, RuntimeError, shutil.Error) as e:
        failure = e
    if path != original and not os.path.lexists(original):
        try:
            os.rename(path, original)
            path = original
        except OSError:
            pass
    retry = "; neste kjøring prøver igjen" if path == original else ""
    return None, f"kunne ikke legge den i papirkurven ({failure}){silent}; den ligger i {path}{retry}"


def _remove_leftovers(apps: Path, bundle_id: str):
    """Under the install lock every `.<name>.gstack-new-<pid>` with our bundle id is a leftover
    of an interrupted run (a PID can be reused, so it is not checked). Such a leftover may be the
    user's previous version (a run stopped between the swap and the Trash), so it goes to the Trash,
    never to rm. Others are left alone. Returns where each one went."""
    try:
        entries = list(apps.iterdir()) if apps.is_dir() else []
    except OSError as e:
        raise Stop(70, f"kunne ikke lese {apps}: {e}") from None
    moved = []
    for p in entries:
        m = _NEW_COPY_RE.fullmatch(p.name)
        if not m or p.is_symlink() or not p.is_dir():
            continue
        if _bundle_id(p)[0] != bundle_id:
            continue
        where, problem = _to_trash(p, _old_name(m.group(1)))
        if problem:                 # _to_trash has given it its hidden name back
            raise Stop(70, f"en rest etter en avbrutt installering ble liggende: {problem}")
        moved.append(where)
    return moved


def _read_stamp(gd: Path):
    """(stamp, problem): stamp None and problem None means there is no stamp at all."""
    return _read_json(gd / STAMP_FILE)


def ask_questions(args, info, apps: Path, gd: Path, primary: Path, head: str):
    """Step 3, in fail-closed order: 7 (another app; no flag helps, and quitting by bundle id must
    never address it), 4 (running), 5 (migration since the stamp), 6 (unstamped copy).
    Nothing is quit here: the returned plan (None, or (label, executable name)) is carried out
    just before the swap, after the build and the copy are verified and the questions are asked
    again, so a stop on 5 or 6, a failed build or a failed check never leaves the app closed."""
    target = apps / info["full_product_name"]
    bid, exe = info["bundle_id"], info["executable_name"]
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise Stop(7, f"{target} er ikke en vanlig app-mappe; rydd den selv")
    if target.exists():
        other, problem = _bundle_id(target)
        if problem:
            raise Stop(7, f"kan ikke vite hvilken app {target} er: {problem}; rydd den selv")
        if other != bid:
            raise Stop(7, f"{target} er en annen app ({other}, ikke {bid}); rydd den selv")

    # Every running copy with our bundle id must be the one the flag covers, compared as exact text:
    # --quit-running covers the copy in the applications folder, --quit-path that one bundle.
    plan = None
    running = app_instances(exe, bid)
    if running:
        listed = ", ".join(f"{c} (PID {p})" for p, c in running[:3])
        if not (args.quit_running or args.quit_path):
            raise Stop(4, f"{target.name} kjører: {listed}", state=listed)
        covered_bundle = Path(os.path.abspath(args.quit_path)) if args.quit_path else target
        covered = _spellings(covered_bundle / "Contents" / "MacOS" / exe)
        others = [c for _, c in running if c not in covered]
        if others:
            raise Stop(4, f"{target.name} kjører også utenfor {covered_bundle}: {', '.join(others[:3])}",
                       state=listed)
        if args.quit_path:
            qbid, problem = _bundle_id(covered_bundle)
            if problem or qbid != bid:
                raise Stop(64, f"--quit-path {covered_bundle} er ikke {bid}: {problem or qbid}")
        plan = (f"{target.name} i {covered_bundle}", exe)

    stamp, problem = _read_stamp(gd)
    ours = stamp is not None and stamp.get("bundle_id") == bid
    if problem or ours:
        flagged, why = (True, f"stempelet kan ikke leses ({problem}); spennet er ukjent") if problem else \
            migration_signal(primary, stamp.get("commit"), head)
        if flagged and not args.accept_migration:
            raise Stop(5, why)
    covered = False
    if ours and isinstance(stamp.get("app_path"), str) and stamp["app_path"]:
        covered = os.path.realpath(stamp["app_path"]) == os.path.realpath(target)
    if target.exists() and not covered and not args.replace_unstamped:
        raise Stop(6, f"{target} finnes, men uten stempel; forrige versjon er ukjent")
    return plan


def carry_out_quit(bundle_id, plan):
    """The quit the user said yes to (--quit-running / --quit-path). Never kill."""
    if plan and not quit_app(bundle_id, plan[1]):
        raise Stop(4, f"{plan[0]} avsluttet seg ikke selv i tide; den ble ikke drept")


# --- interruption: SIGTERM / SIGINT become Stop(70, "avbrutt …") ------------------------------
# A background install that is killed still stores its result and removes what it created. A
# signal never splits a critical section (the swap and its bookkeeping, the cleanup, the atomic
# writes): it is held there and raised when the section ends. Only the first signal raises.

_SIGNALS = {"critical": 0, "pending": None, "fired": False}


def _interrupted(signum) -> Stop:
    _SIGNALS["fired"] = True
    try:
        name = signal.Signals(signum).name
    except ValueError:
        name = str(signum)
    return Stop(70, f"avbrutt ({name})")


def _on_signal(signum, frame):
    if _SIGNALS["fired"]:
        return                                  # one interruption is enough; let the cleanup finish
    if _SIGNALS["critical"]:
        _SIGNALS["pending"] = signum
        return
    raise _interrupted(signum)


@contextlib.contextmanager
def _critical(raise_pending=True):
    _SIGNALS["critical"] += 1
    try:
        yield
    finally:
        _SIGNALS["critical"] -= 1
    if raise_pending and not _SIGNALS["critical"] and _SIGNALS["pending"] is not None and not _SIGNALS["fired"]:
        signum, _SIGNALS["pending"] = _SIGNALS["pending"], None
        raise _interrupted(signum)


# --- steps 4-7: build, verify before the swap, swap, register and stamp ------------------------

def _require_writable(apps: Path):
    if not apps.is_dir():
        raise Stop(10, f"{apps} finnes ikke")
    if not os.access(apps, os.W_OK | os.X_OK):
        raise Stop(10, f"{apps} er ikke skrivbar for denne brukeren; install bruker aldri sudo")


def _log_tail(log: Path) -> str:
    try:
        return log.read_text(encoding="utf-8", errors="replace")[-1500:]
    except OSError:
        return ""


def build(repo, info, scheme, gd=None) -> Path:
    """Step 4: `xcodebuild … -derivedDataPath <git dir>/gstack-install-build build`, all output in
    <git dir>/gstack-install-build.log. No signing override. Code 8 names the log. Returns the app.
    Package plug-ins and macros are trusted without the Xcode dialog: a fresh derived-data folder has no
    per-checkout trust, so a project with a code-generating plug-in (smithy-swift) would stop at "Validate
    plug-in" on every first build. The build is the user's own `origin/main`, and the projects' own build
    scripts pass the same two flags."""
    gd = Path(gd) if gd else gitdir(repo)
    log = gd / BUILD_LOG
    argv = ["xcodebuild", *info["container"], "-scheme", scheme, "-configuration", "Release",
            "-destination", "platform=macOS", "-derivedDataPath", str(gd / BUILD_DIR),
            "-skipPackagePluginValidation", "-skipMacroValidation", "build"]
    try:
        with open(log, "wb") as f:
            r = subprocess.run(argv, cwd=repo, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                               timeout=BUILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Stop(8, f"bygget brukte over {BUILD_TIMEOUT} s; logg: {log}") from None
    except OSError as e:
        raise Stop(8, f"bygget kunne ikke kjøres ({e}); logg: {log}") from None
    if r.returncode:
        raise Stop(8, f"bygget feilet (xcodebuild ga kode {r.returncode}); logg: {log}", state=_log_tail(log))
    product = Path(info["built_products_dir"]) / info["full_product_name"]
    if product.is_symlink() or not product.is_dir():
        raise Stop(8, f"bygget lagde ikke {product}; logg: {log}")
    return product


def verify_copy(app, bundle_id):
    """Step 5's check, also run on the final path: `codesign --verify --deep --strict`, then the
    bundle id read with plistlib (R8). Raises Stop(9); the caller removes what it created."""
    try:
        r = _run(["codesign", "--verify", "--deep", "--strict", str(app)], timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Stop(9, f"codesign kunne ikke kontrollere {app}: {e}") from None
    if r.returncode:
        raise Stop(9, f"codesign --verify --deep --strict avviste {app}", state=_last_line(r.stderr, r.stdout))
    bid, problem = _bundle_id(app)
    if problem:
        raise Stop(9, problem)
    if bid != bundle_id:
        raise Stop(9, f"{app} har bundle-ID {bid}, ikke {bundle_id}")


def _copy(product: Path, tmp: Path):
    """`ditto <product> <apps>/.<name>.gstack-new-<pid>`."""
    try:
        r = _run(["ditto", str(product), str(tmp)], timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Stop(9, f"ditto kunne ikke kopiere {product}: {e}") from None
    if r.returncode:
        _require_writable(tmp.parent)
        raise Stop(9, f"ditto ga kode {r.returncode} for {tmp}", state=_last_line(r.stderr, r.stdout))
    if tmp.is_symlink() or not tmp.is_dir():
        raise Stop(9, f"ditto lagde ikke {tmp}")


def _renamex(a, b, flags):
    """macOS renamex_np(a, b, flags) through ctypes; errno becomes the matching OSError subclass."""
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renamex_np
    fn.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
    fn.restype = ctypes.c_int
    if fn(os.fsencode(str(a)), os.fsencode(str(b)), flags) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), str(a), None, str(b))


def _rename_dance(a, b):
    """Three renames. NOT atomic: only for the tests on Linux (GSTACK_SWAP=rename)."""
    mid = Path(a).with_name(Path(a).name + ".gstack-swap")
    os.rename(a, mid)
    os.rename(b, a)
    os.rename(mid, b)


def _test_knob() -> bool:
    """GSTACK_SWAP=rename, honoured only outside macOS: on a Mac the real renamex_np always runs."""
    return sys.platform != "darwin" and os.environ.get("GSTACK_SWAP") == "rename"


def _swap(old, new):
    """Exchange two folders in one step: renamex_np(RENAME_SWAP) on macOS. Elsewhere only the test
    knob works (_rename_dance); without it the swap refuses (70)."""
    if sys.platform == "darwin":
        return _renamex(old, new, RENAME_SWAP)
    if _test_knob():
        return _rename_dance(old, new)
    raise Stop(70, "byttet i ett steg (renamex_np) finnes bare på macOS")


def _place(new, target):
    """Move `new` to `target`, never replacing anything there (not even an empty folder, which a
    plain rename would): renamex_np(RENAME_EXCL) on macOS, the test knob's checked rename elsewhere."""
    if sys.platform == "darwin":
        return _renamex(new, target, RENAME_EXCL)
    if _test_knob():
        if os.path.lexists(target):
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(target))
        return os.rename(new, target)
    raise Stop(70, "å flytte appen på plass (renamex_np) finnes bare på macOS")


def _put_in_place(tmp: Path, target: Path, st: dict):
    """Step 6. With an old copy the two are swapped, and `tmp` then holds the previous version;
    without one the copy is moved there without replacing anything. A refusal is code 10."""
    try:
        if os.path.lexists(target):
            _swap(target, tmp)
            st["holds"] = "old"
        else:
            _place(tmp, target)
            st["holds"] = None
        st["swapped"] = True
    except PermissionError as e:
        raise Stop(10, f"{target.parent} tillot ikke byttet ({e}). Er mappen skrivbar? macOS kan også kreve "
                       "«Appadministrasjon» for terminalen (Systeminnstillinger → Personvern og sikkerhet)") from None
    except OSError as e:
        raise Stop(70, f"byttet av {target} feilet: {e}") from None


def register(target: Path):
    """`lsregister -f <app>`. A failure does not undo the install (Launch Services finds the app
    on its own later); the problem is named in the reason. The problem text, or None."""
    exe = os.environ.get("GSTACK_LSREGISTER") or LSREGISTER
    try:
        r = _run([exe, "-f", str(target)], timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"lsregister kunne ikke kjøres: {e}"
    return f"lsregister ga kode {r.returncode}" if r.returncode else None


def _atomic_json(path: Path, data: dict) -> str | None:
    """A temp file in the same folder, fsync, then os.replace. The error text, or None."""
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return None
    except OSError as e:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return str(e)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_stamp(gd: Path, scheme, bundle_id, commit, target: Path):
    """Step 7's stamp, written atomically: scheme, bundle_id, commit, app_path, version, installed_at."""
    version = None
    try:
        with open(target / "Contents" / "Info.plist", "rb") as f:
            plist = plistlib.load(f)
        short, number = plist.get("CFBundleShortVersionString"), plist.get("CFBundleVersion")
        if isinstance(short, str) and short:
            version = short + (f" ({number})" if isinstance(number, str) and number and number != short else "")
    except (OSError, ValueError, AttributeError, plistlib.InvalidFileException):
        pass
    data = {"scheme": scheme, "bundle_id": bundle_id, "commit": commit, "app_path": os.path.abspath(target),
            "version": version, "installed_at": _utc_now()}
    err = _atomic_json(gd / STAMP_FILE, data)
    if err:
        raise Stop(70, f"{target} er installert, men stempelet kunne ikke skrives: {err}")


def _cleanup(tmp: Path, st: dict, stem: str):
    """What this run created and still holds: its own copy is removed, the previous version
    (after a swap) goes to the Trash."""
    if not os.path.lexists(tmp):
        return
    if st["holds"] == "new":
        shutil.rmtree(tmp, ignore_errors=True)        # our pid-named copy, checked absent before ditto
    elif st["holds"] == "old":
        _to_trash(tmp, _old_name(stem))


def _roll_back(tmp: Path, target: Path, st: dict, failed: Stop):
    """R4': the copy at the final path failed its check. Undo the swap so the previous version
    is back at `target` untouched, and leave the rejected copy at `tmp` for _cleanup to remove.
    Always raises Stop(9). If the swap back itself fails, nothing is cleaned up or trashed and the
    reason says where each copy lies."""
    had_old = st["holds"] == "old"
    try:
        if had_old:
            _swap(target, tmp)
        else:
            _place(target, tmp)
    except (OSError, Stop) as err:
        st["holds"] = None                      # never let cleanup touch either copy now
        where = (f"den avviste kopien ligger i {target}, den gamle i {tmp}" if had_old
                 else f"den avviste kopien ligger i {target}")
        raise Stop(9, f"{failed.message} på den endelige stien, og byttet kunne ikke rulles tilbake ({err}); "
                      f"{where}; ingenting er stemplet", failed.state) from None
    st["holds"], st["swapped"] = "new", False
    old = "den gamle kopien er urørt" if had_old else "det fantes ingen gammel kopi"
    raise Stop(9, f"{failed.message} på den endelige stien; byttet er rullet tilbake, {old}; "
                  "ingenting er stemplet", failed.state)


def deliver(args, info, scheme, apps: Path, gd: Path, primary: Path, head: str) -> dict:
    """Steps 4-7. The old copy stays until the new one is verified; the app is asked to quit only
    right before the swap; every failure removes only what this run created."""
    bid, name = info["bundle_id"], info["full_product_name"]
    stem = name[:-len(".app")]
    target = apps / name
    product = build(primary, info, scheme, gd)          # 8: nothing touched, the app keeps running
    tmp = apps / f".{stem}.gstack-new-{os.getpid()}"
    st = {"holds": None, "swapped": False, "stamped": False}
    try:
        if os.path.lexists(tmp):
            raise Stop(70, f"{tmp} finnes allerede og er ikke en rest av denne appen; rydd den selv")
        st["holds"] = "new"
        try:
            _copy(product, tmp)
            verify_copy(tmp, bid)
        except Stop as e:
            if e.code != 9:
                raise
            raise Stop(9, f"{e.message}; den midlertidige kopien er fjernet, den gamle er urørt", e.state) from None
        plan = ask_questions(args, info, apps, gd, primary, head)    # the build took time: ask again
        carry_out_quit(bid, plan)
        _require_writable(apps)
        with _critical():                       # R4': swap and final check are one unit
            # HEAD is read here, inside the section and right before the swap, so no step of ours
            # (and no signal) lies between this check and _put_in_place.
            now = _load_land().out(primary, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
            if now != head:
                raise Stop(11, f"main flyttet seg under bygget ({head[:7]} → {(now or 'ukjent')[:7]}); "
                               "ingenting er byttet eller stemplet", state=f"bygget {head}, HEAD nå {now}")
            _put_in_place(tmp, target, st)
            try:
                verify_copy(target, bid)
            except Stop as e:
                _roll_back(tmp, target, st, e)
        notes = [n for n in (register(target),) if n]
        with _critical():
            write_stamp(gd, scheme, bid, head, target)
            st["stamped"] = True
        old_note = "det fantes ingen gammel kopi"
        if st["holds"] == "old":                # only now, after the check at the final path
            with _critical():
                where, problem = _to_trash(tmp, _old_name(stem))
                st["holds"] = None
            old_note = f"den gamle kopien ligger i {where}" if where else f"den gamle kopien: {problem}"
        return {"status": "installed",
                "reason": "; ".join([f"{name} {head[:7]} er installert i {apps}", old_note, *notes])}
    except BaseException as e:
        with _critical(raise_pending=False):
            _cleanup(tmp, st, stem)
        if isinstance(e, Stop) and e.code == 70 and st["swapped"]:
            e.message += (f"; {target} var allerede byttet og stemplet" if st["stamped"]
                          else f"; {target} var allerede byttet, men er ikke stemplet")
        raise


def _already_current(primary: Path, gd: Path, apps: Path, scheme, head):
    """The stamp when it already proves `head` is installed in `apps` (same predicate as report:
    stamp_is_current), else None. Checked before anything is asked or built."""
    stamp, problem = _read_stamp(gd)
    if problem or not stamp or stamp.get("scheme") != scheme:
        return None
    app = stamp.get("app_path")
    if not isinstance(app, str) or not app or os.path.realpath(os.path.dirname(app)) != os.path.realpath(apps):
        return None
    return stamp if stamp_is_current(primary, stamp, head) else None


def _install_locked(args, repo: Path, gd: Path, ctx: dict) -> dict:
    land = _load_land()
    ref = _line_ref(land, repo)[0]
    if ref is None:
        raise Stop(2, "fant ingen standardgren å lese Installable: fra")
    _scheme_from_line(repo, ref)                       # fast stop before anything is pulled
    primary, head = precondition_main(land, repo, gd)
    ctx["commit"] = head
    scheme = _scheme_from_line(primary, head)          # the line as it stands on the commit to build
    apps = Path(args.applications_dir) if args.applications_dir else Path("/Applications")
    current = _already_current(primary, gd, apps, scheme, head)
    if current:                                        # before the running check: never asks to quit
        # A hidden copy an earlier run could not trash is retried here too (still under the lock).
        moved = _remove_leftovers(apps, current["bundle_id"])
        reason = f"{Path(current['app_path']).name} {head[:7]} er allerede installert"
        if moved:
            reason += f"; {len(moved)} rest(er) etter en avbrutt installering lagt i {', '.join(moved)}"
        return {"status": "current", "reason": reason}
    info = discover_build(primary, scheme, gd / BUILD_DIR)
    _require_writable(apps)                            # 10 before any build time is spent
    _remove_leftovers(apps, info["bundle_id"])
    ask_questions(args, info, apps, gd, primary, head)  # stops before the build; nothing is quit yet
    return deliver(args, info, scheme, apps, gd, primary, head)


def _write_result(gd: Path, outcome: dict) -> str | None:
    """Atomic: a temp file in the same folder, then os.replace. The error text, or None."""
    return _atomic_json(gd / RESULT_FILE, {**outcome, "finished_at": _utc_now()})


def _outcome(code, reason, commit, status=None) -> dict:
    return {"status": status or ("installed" if code == 0 else "stopped"), "code": code,
            "reason": reason, "commit": commit}


def cmd_install(args) -> int:
    _SIGNALS.update(critical=0, pending=None, fired=False)
    previous = {s: signal.signal(s, _on_signal) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        return _cmd_install(args)
    finally:
        for s, handler in previous.items():
            signal.signal(s, handler)


def _cmd_install(args) -> int:
    ctx = {"commit": None}
    state = ""
    outcome = _outcome(70, "avbrutt før resultatet ble målt", None)
    try:
        repo = Path(args.repo)
        if not repo.is_dir() or _load_land().git(repo, "rev-parse", "--git-dir").returncode:
            raise Stop(2, f"{repo} er ikke et git-repo")
        try:
            gd = gitdir(repo)
        except _CountError as e:
            raise Stop(2, str(e)) from None
        with InstallLock(gd):          # a run that does not hold the lock never writes the result
            try:
                done = _install_locked(args, repo, gd, ctx)
                outcome = _outcome(0, done.get("reason", ""), ctx["commit"], done.get("status"))
            except Stop as e:
                outcome, state = _outcome(e.code, e.message, ctx["commit"]), e.state
            except Exception as e:     # unexpected: still a stored stop, with the measured state
                outcome = _outcome(70, f"uventet feil: {type(e).__name__}: {e}", ctx["commit"])
                state = traceback.format_exc()[-1500:]
            finally:
                with _critical(raise_pending=False):
                    err = _write_result(gd, {**outcome, "state": state})
                    _SIGNALS["fired"] = True    # the run is over: a later signal must not change the outcome
                if err:
                    outcome["reason"] += f" (resultatet kunne ikke lagres: {err})"
    except Stop as e:
        outcome, state = _outcome(e.code, e.message, ctx["commit"]), e.state
    except Exception as e:
        outcome = _outcome(70, f"uventet feil: {type(e).__name__}: {e}", ctx["commit"])
        state = traceback.format_exc()[-1500:]
    if state:
        print(state)
    print(json.dumps(outcome, ensure_ascii=False))
    return outcome["code"]


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
    argv = sys.argv[1:] if argv is None else list(argv)
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        if e.code in (0, None):
            return 0
        if argv[:1] == ["install"]:     # install's last stdout line is always the JSON object
            print(json.dumps(_outcome(64, "feil bruk av install (se stderr)", None), ensure_ascii=False))
        return 64
    if not getattr(args, "func", None):
        parser.print_usage(sys.stderr)
        return 64
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
