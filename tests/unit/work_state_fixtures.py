"""Fixtures for tests/unit/test_work_state.py. Every path contains a space on purpose."""
from __future__ import annotations

import subprocess
from pathlib import Path


def run(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f"git {args}: {r.stderr}")
    return r.stdout.strip()


def commit_file(repo, name, text, message=None):
    f = Path(repo) / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    run(repo, "add", "--", name)
    run(repo, "commit", "-q", "-m", message or f"edit {name}")


def make_repo(tmp_path) -> Path:
    repo = Path(tmp_path) / "my proj"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    run(repo, "config", "user.name", "Test")
    run(repo, "config", "user.email", "test@example.com")
    run(repo, "config", "commit.gpgsign", "false")
    commit_file(repo, "CLAUDE.md", "# proj\n", "init")
    return repo


def add_origin(repo) -> Path:
    repo = Path(repo)
    origin = repo.parent / "origin dir"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(origin)], check=True)
    run(repo, "remote", "add", "origin", str(origin))
    run(repo, "fetch", "-q", "origin")
    run(repo, "branch", "--set-upstream-to=origin/main", "main")
    return origin


def stub_bin(tmp_path, **behaviours) -> Path:
    """One executable shell script per keyword in `<tmp_path>/stub bin`; the body is the snippet.
    Every stub appends 'name argv...' to $STUB_LOG when it is set. Names not given are not created."""
    d = Path(tmp_path) / "stub bin"
    d.mkdir(parents=True, exist_ok=True)
    for name, body in behaviours.items():
        f = d / name
        f.write_text(
            "#!/bin/sh\n"
            f'if [ -n "$STUB_LOG" ]; then printf \'%s\\n\' "{name} $*" >> "$STUB_LOG"; fi\n'
            f"{body}\n", encoding="utf-8")
        f.chmod(0o755)
    return d


def stub_env(tmp_path) -> dict:
    """Environment variables the stubs and work-state.py read, all under tmp_path."""
    base = Path(tmp_path)
    out, trash = base / "stub out", base / "stub trash"
    out.mkdir(parents=True, exist_ok=True)
    trash.mkdir(parents=True, exist_ok=True)
    return {
        "STUB_OUT": str(out),
        "STUB_LOG": str(base / "stub.log"),
        "STUB_PS_FILE": str(base / "stub ps.txt"),
        "STUB_TRASH": str(trash),
        "GSTACK_LSREGISTER": str(base / "stub lsregister"),
    }
