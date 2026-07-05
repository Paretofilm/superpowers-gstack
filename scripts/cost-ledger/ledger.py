#!/usr/bin/env python3
"""Cost-ledger storage and concurrency layer.

Spec §3: storage layout, concurrency (O_APPEND + flock), atomic writes,
and git helpers. All other modules import from here; this module has no
imports from tune / monitor / cli (no circular deps).

Public API the pitfall-verification skill consumes (§10 integration):
    read_overrides()      — before dispatch (point 1)
    append_record(rec)    — after synthesis (point 2)
    run_tune_cycle lives in tune.py (point 3)
"""
from __future__ import annotations

import contextlib
import datetime
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# Ledger directory resolution (env-override for test isolation).
# ---------------------------------------------------------------------------

def _ledger_dir() -> Path:
    """Resolve LEDGER_DIR; always re-reads the env var so tests can override."""
    raw = os.environ.get("COST_LEDGER_DIR", "~/.claude/cost-ledger/")
    return Path(raw).expanduser().resolve()


def _path(name: str) -> Path:
    """Resolve a file path inside LEDGER_DIR, creating the dir if absent."""
    d = _ledger_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / name


# ---------------------------------------------------------------------------
# Exclusive flock lock (serialises writers; read-only callers use timeout=0
# to get a skip-on-contention fallback — spec §3).
# ---------------------------------------------------------------------------

LOCK_TIMEOUT_S = 10  # default; callers may pass shorter for read-only usage


@contextlib.contextmanager
def ledger_lock(timeout: float = LOCK_TIMEOUT_S) -> Iterator[None]:
    """Exclusive flock on .lock; raises TimeoutError when timeout expires.

    Callers that cannot afford to block should catch TimeoutError and skip
    the locked section (spec §3: "a session that cannot acquire the lock
    within a short timeout skips tuning for that review").  The LOCK_EX is
    non-blocking; we poll at 50 ms intervals up to `timeout` seconds.
    """
    lock_path = _path(".lock")
    # Open a fresh fd each time so each context-manager instance owns its own
    # open-file-description — required for flock isolation across threads.
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    raise TimeoutError(
                        f"could not acquire ledger lock within {timeout:.1f}s"
                    )
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Ledger append (O_APPEND — no lock required for single small writes, §3).
# ---------------------------------------------------------------------------

_MAX_APPEND_BYTES = 4096  # POSIX PIPE_BUF floor; exceeded records are rejected


def append_record(record: dict) -> None:
    """Atomic O_APPEND write of one JSON line to ledger.jsonl.

    No lock required: a single write() below PIPE_BUF (4096 B) is atomic on
    POSIX local filesystems (§3).  Records exceeding this limit are rejected
    loudly so the atomicity assumption is never silently violated.
    """
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
    encoded = line.encode("utf-8")
    if len(encoded) > _MAX_APPEND_BYTES:
        raise ValueError(
            f"::error::ledger record too large for atomic append "
            f"({len(encoded)} B > {_MAX_APPEND_BYTES}); split or trim fields"
        )
    path = _path("ledger.jsonl")
    fd = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o666)
    try:
        os.write(fd, encoded)
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Readers (safe to call outside the lock — miss-reads fall through to safe
# defaults; corrupt files log a warning and return the empty fallback).
# ---------------------------------------------------------------------------

def read_history() -> list[dict]:
    """Parse ledger.jsonl; missing or empty file returns []."""
    path = _path("ledger.jsonl")
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    records: list[dict] = []
    for i, raw in enumerate(text.splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            records.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            print(
                f"::warning::ledger.jsonl line {i} skipped (bad JSON: {exc})",
                file=sys.stderr,
                flush=True,
            )
    return records


def read_quarantine() -> list[dict]:
    """Parse quarantine.json; missing file returns []."""
    path = _path("quarantine.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as exc:
        print(
            f"::warning::quarantine.json corrupt ({exc}); treating as empty",
            file=sys.stderr,
            flush=True,
        )
        return []


def read_overrides() -> dict:
    """Parse overrides.json; missing file returns the safe empty override set.

    Routing calls this on the hot dispatch path (§10 point 1).  A missing or
    corrupt file falls through to baseline (no adjustments) — the safe direction.
    """
    path = _path("overrides.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": 1, "generated_ts": "", "overrides": []}
    except json.JSONDecodeError as exc:
        print(
            f"::warning::overrides.json corrupt ({exc}); falling back to empty",
            file=sys.stderr,
            flush=True,
        )
        return {"version": 1, "generated_ts": "", "overrides": []}


def read_state() -> dict:
    """Parse state.json (pause flag etc.); missing returns default (unpaused)."""
    path = _path("state.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"paused": False}
    except json.JSONDecodeError as exc:
        print(
            f"::warning::state.json corrupt ({exc}); treating as default",
            file=sys.stderr,
            flush=True,
        )
        return {"paused": False}


def read_baseline() -> dict:
    """Parse baseline.json; missing returns empty baseline (no adjustments)."""
    path = _path("baseline.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": 1, "generated_ts": "", "overrides": []}
    except json.JSONDecodeError as exc:
        print(
            f"::warning::baseline.json corrupt ({exc}); returning empty baseline",
            file=sys.stderr,
            flush=True,
        )
        return {"version": 1, "generated_ts": "", "overrides": []}


# ---------------------------------------------------------------------------
# Atomic write (write-to-temp + os.replace, §3).
# ---------------------------------------------------------------------------

def atomic_write(path: "str | Path", data: "dict | list") -> None:
    """Serialise data as indented JSON and swap atomically via os.replace().

    Spec §3: unlocked readers always see either the whole old file or the
    whole new file, never a partial write.  The temp file is created in the
    SAME directory so the rename stays on one filesystem (POSIX atomicity).
    On failure, the temp file is cleaned up and the original is left intact.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        os.write(fd, payload.encode("utf-8"))
        os.close(fd)
        fd = -1
        os.replace(tmp, path)  # POSIX-atomic on same filesystem
    except Exception:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Timestamp helper.
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Git helpers (fail loud on any error, §3 / check-new-models.py style).
# ---------------------------------------------------------------------------

def _git(*args: str, check: bool = True) -> str:
    """Run a git command in LEDGER_DIR; raise RuntimeError (with ::error::) on failure."""
    ld = str(_ledger_dir())
    result = subprocess.run(
        ["git", "-C", ld, *args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"::error::git {' '.join(args)} failed "
            f"(exit {result.returncode}):\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _git_silent(*args: str) -> str:
    """Run git, swallowing non-zero exit (for idempotent init-like calls)."""
    return _git(*args, check=False)


def ensure_repo() -> None:
    """git init in LEDGER_DIR (idempotent); set minimal config for commits."""
    ld = _ledger_dir()
    ld.mkdir(parents=True, exist_ok=True)
    if not (ld / ".git").exists():
        _git("init")
        _git("config", "user.email", "cost-ledger@local")
        _git("config", "user.name", "cost-ledger")


def commit(paths: "list[str | Path]", message: str) -> str:
    """Stage paths and create a commit in LEDGER_DIR; return new HEAD SHA.

    Raises RuntimeError (fail loud) if git add or commit fail.  Use this for
    adjustment commits so every tuning step is auditable (§3 / §6 step 3).
    """
    ensure_repo()
    ld = _ledger_dir()
    rel: list[str] = []
    for p in paths:
        p = Path(p)
        if p.is_absolute():
            try:
                p = p.relative_to(ld)
            except ValueError:
                pass  # path outside LEDGER_DIR — pass as-is; git -C will handle it
        rel.append(str(p))
    _git("add", "--", *rel)
    # Distinguish a true no-op (nothing staged — e.g. a reset already at baseline)
    # from a real git failure. `git diff --cached --quiet` exits 0 when nothing is
    # staged, 1 when there are staged changes, other on error. A no-op returns ""
    # (no commit); a genuine add/commit/diff failure still raises RuntimeError so
    # callers cannot report success on an unaudited routing change (codex P2).
    staged = subprocess.run(["git", "-C", str(ld), "diff", "--cached", "--quiet"])
    if staged.returncode == 0:
        return ""  # nothing to commit; not a commit, not an error
    if staged.returncode != 1:
        raise RuntimeError(
            f"::error::git diff --cached failed (exit {staged.returncode})"
        )
    _git("commit", "-m", message)
    return _git("rev-parse", "HEAD")


def revert(sha: str) -> str:
    """git revert --no-edit <sha> in LEDGER_DIR; return new HEAD SHA.

    Fails loud on conflicts (caller must ensure no interleaved commits touch
    the same files, which the flock serialisation provides for overrides.json).
    """
    ensure_repo()
    try:
        _git("revert", "--no-edit", sha)
    except RuntimeError as exc:
        # Abort any partial revert state before re-raising.
        _git_silent("revert", "--abort")
        raise RuntimeError(
            f"::error::git revert {sha} failed "
            f"(possible conflict with a later commit): {exc}"
        ) from exc
    return _git("rev-parse", "HEAD")


def git_log(domain: str | None = None, n: int = 20) -> list[str]:
    """Return the last n one-line log entries, optionally grep'd by domain."""
    args = ["log", "--oneline", f"-{n}"]
    if domain:
        args += [f"--grep={domain}"]
    return _git_silent(*args).splitlines()
