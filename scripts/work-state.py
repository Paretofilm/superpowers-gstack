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
import glob
import importlib.util
import io
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
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


def proven_landed(repo, branch) -> bool:
    """Both conditions of the spec; an empty or expired reflog, or any git failure, proves nothing."""
    try:
        return _landed_state(_load_land(), Path(repo), branch)
    except _CountError:
        return False


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


def in_use(path) -> bool:
    """Does a process have its working directory in `path`? Whole path components only."""
    cands = {str(path), str(Path(path).resolve())}
    prefixes = tuple(c.rstrip(os.sep) + os.sep for c in cands)
    return any((c.rstrip(os.sep) + os.sep).startswith(prefixes) for c in _cwds())


def _status_entries(land, path):
    # Explicit flags: status.showUntrackedFiles=no must not hide untracked work (as land.dirty_files).
    r = land.git(path, "status", "--porcelain", "-z", "--ignored", "--untracked-files=all", "--ignore-submodules=none")
    if r.returncode:
        raise _CountError(f"git status failed in {path}: {r.stderr.strip()[-200:]}")
    return [e for e in r.stdout.split("\0") if e]


def is_clean(path) -> bool:
    """Empty `git status --porcelain --ignored`, or only ignored cache content. False on failure."""
    try:
        return _is_clean(_load_land(), Path(path))
    except _CountError:
        return False


def _is_clean(land, path) -> bool:
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
        if in_use(path):
            ask.append(f"{path} i bruk")
        elif not branch:
            ask.append(f"{path} har ingen gren (frakoblet HEAD)")
        elif not _landed_state(land, repo, branch):
            ask.append(f"{path}: grenen {branch} er ikke bevist landet")
        elif not _is_clean(land, path):
            ask.append(f"{path}: har uncommittede eller ignorerte filer som ikke er hurtigbuffer")
        elif have_wt:
            safe.append(["wt", "-C", str(primary), "remove", branch])
        else:
            safe.append(["git", "-C", str(primary), "worktree", "remove", str(path)])
            safe.append(["git", "-C", str(primary), "branch", "-d", branch])
    r = land.git(repo, "for-each-ref", "--format=%(refname:lstrip=2)", "refs/heads")
    if r.returncode:
        raise _CountError(f"kunne ikke liste grener: {r.stderr.strip()[-200:]}")
    for name in r.stdout.split():
        if name in checked_out or name == main:
            continue
        if _landed_state(land, repo, name):
            safe.append(["git", "-C", str(primary), "branch", "-d", name])
        else:
            ask.append(f"{name} er ikke bevist landet")
    if primary.parent.is_dir():
        for d in sorted(primary.parent.glob(glob.escape(primary.name) + ".*")):
            if not d.is_dir() or d.resolve() in known:
                continue
            if d.is_symlink():
                ask.append(f"{d}: er en symbolsk lenke; den flyttes ikke til papirkurven")
            elif in_use(d):
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
            return _installable_app(repo, head, ref)
        if kind == "plugin":
            return _installable_plugin(land, repo, ref, has_origin)
        return _installable_command(land, repo, arg)
    except (_CountError, land.Stop, OSError, subprocess.SubprocessError) as e:
        return _inst("undefined", "unknown", f"kunne ikke måle: {e}")


def _installable_app(repo, head, ref):
    gd = gitdir(repo)
    safe = [["python3", os.path.abspath(__file__), "install", "--repo", str(repo)]]
    ask = []
    result, rerr = _read_json(gd / RESULT_FILE)
    if rerr:
        ask.append(rerr)
    elif result and isinstance(result.get("code"), int) and result["code"] >= 4:
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
