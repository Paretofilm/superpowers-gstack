"""scripts/land-worktree.py — solo landing in one command (spec 2026-09-29).

Preflight tests use a FAKE `wt` (a shell script answering only `config approvals
list`), so they run without worktrunk, in CI too. The landing tests in the second
half need the real `wt` and skip without it. Every path in the fixture contains a
space on purpose: an argument list that survives `my proj` survives everything a
shell string would have mangled.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "land-worktree.py"

APPROVED = "APPROVED\n↳ (none)\n\nUNAPPROVED\n↳ (none)\n"
UNAPPROVED = "APPROVED\n↳ (none)\n\nUNAPPROVED\n❯ pre-merge check:\n  true\n"
HOOK_TOML = '[pre-merge]\ncheck = "true"\n'


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and r.returncode:
        raise AssertionError(f"git {args}: {r.stderr}")
    return r.stdout.strip()


def commit(repo, name, text, msg):
    (Path(repo) / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-qm", msg)


@pytest.fixture
def lab(tmp_path):
    remote = tmp_path / "remote.git"
    primary = tmp_path / "my proj"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(primary)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(primary, "config", k, v)
    (primary / ".config").mkdir()
    (primary / ".config" / "wt.toml").write_text(HOOK_TOML)
    (primary / "CLAUDE.md").write_text("# proj\n\nLanding mode: solo\n")
    (primary / "shared.md").write_text("base\n")
    git(primary, "add", "-A")
    git(primary, "commit", "-qm", "init")
    git(primary, "remote", "add", "origin", str(remote))
    git(primary, "push", "-q", "-u", "origin", "main")
    wt = tmp_path / "my proj.feat-x"
    git(primary, "worktree", "add", "-q", "-b", "feat/x", str(wt))
    commit(wt, "feature.md", "f\n", "feat: x")
    return SimpleNamespace(root=tmp_path, remote=remote, primary=primary, wt=wt)


def write_shim(root, approvals):
    d = root / "bin"
    d.mkdir(exist_ok=True)
    f = d / "wt"
    f.write_text("#!/bin/sh\nif [ \"$3\" = config ] && [ \"$4\" = approvals ]; then\n"
                 "cat <<'EOF'\n" + approvals + "EOF\nexit 0\nfi\nexit 99\n")
    f.chmod(0o755)
    return d


def land(lab, *args, shim=APPROVED, wt=None, env=None):
    path = "/usr/bin:/bin:/usr/local/bin"
    if shim is not None:
        path = f"{write_shim(lab.root, shim)}:{path}"
    e = {"HOME": str(lab.root), "PATH": path}
    e.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPT), "--worktree", str(wt or lab.wt),
                           "--ci-wait", "0", *args], capture_output=True, text=True, env=e)


def verdict(p):
    return json.loads(p.stdout.strip().splitlines()[-1])


# --- mode: fails closed -------------------------------------------------------

@pytest.mark.parametrize("text", [
    "# proj\n",                                        # no line at all
    "# proj\n\nLanding mode: pr\n",                    # explicit pr
    "# proj\n\nLanding mode: solo \n",                 # trailing space
    "# proj\n\nSet Landing mode: solo in prose.\n",    # inside a sentence
    "# proj\n\nLanding mode: SOLO\n",                  # wrong case
])
def test_mode_other_than_exact_solo_fails_closed(lab, text):
    (lab.wt / "CLAUDE.md").write_text(text)
    git(lab.wt, "commit", "-qam", "chore: mode")
    p = land(lab, "--preflight-only")
    assert p.returncode == 2, p.stderr
    assert verdict(p)["landed"] is False


# --- hook presence, wt presence, approvals ------------------------------------

def test_no_pre_merge_hook_is_code_9(lab):
    (lab.wt / ".config" / "wt.toml").write_text('[post-start]\nx = "true"\n')
    git(lab.wt, "commit", "-qam", "chore: no gate")
    assert land(lab, "--preflight-only").returncode == 9


def test_wt_missing_is_code_8(lab):
    assert land(lab, "--preflight-only", shim=None).returncode == 8


def test_unapproved_hooks_is_code_3_and_names_the_command(lab):
    p = land(lab, "--preflight-only", shim=UNAPPROVED)
    assert p.returncode == 3
    assert "approvals add" in p.stderr and "--yes" not in p.stderr


# --- fetch, dirty worktree, main ahead ----------------------------------------

def test_fetch_failure_is_code_11(lab):
    git(lab.primary, "remote", "set-url", "origin", str(lab.root / "nowhere.git"))
    assert land(lab, "--preflight-only").returncode == 11


def test_dirty_worktree_is_code_13(lab):
    (lab.wt / "untracked.md").write_text("x\n")
    p = land(lab, "--preflight-only")
    assert p.returncode == 13 and "untracked.md" not in p.stdout   # message, not a crash


def test_local_main_ahead_of_origin_is_code_4(lab):
    commit(lab.primary, "local.md", "l\n", "chore: unpushed on main")
    p = land(lab, "--preflight-only")
    assert p.returncode == 4
    assert "unpushed on main" in p.stderr, "the commits that would ride along must be listed"


# --- overlap with the worktree that holds main --------------------------------

def test_dirty_file_the_branch_changes_is_code_5(lab):
    commit(lab.wt, "shared.md", "feature\n", "feat: touches shared")
    (lab.primary / "shared.md").write_text("dirt\n")
    p = land(lab, "--preflight-only")
    assert p.returncode == 5 and "shared.md" in p.stderr


def test_dirty_other_file_does_not_block(lab):
    (lab.primary / "unrelated.md").write_text("dirt\n")
    assert land(lab, "--preflight-only").returncode == 0


# --- primary on another branch: main is updated without a checkout ------------

def test_primary_on_other_branch_main_updated_without_touching_it(lab):
    git(lab.primary, "switch", "-q", "-c", "wip/other")
    other = lab.root / "other"
    subprocess.run(["git", "clone", "-q", str(lab.remote), str(other)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(other, "config", k, v)
    commit(other, "z.md", "z\n", "chore: someone else pushed")
    git(other, "push", "-q", "origin", "main")
    before = git(lab.primary, "rev-parse", "HEAD")
    p = land(lab, "--preflight-only")
    assert p.returncode == 0, p.stderr
    assert git(lab.primary, "rev-parse", "HEAD") == before, "the wrong branch must not move"
    assert git(lab.primary, "rev-parse", "main") == git(other, "rev-parse", "HEAD")


# --- no origin: land locally, no push -----------------------------------------

def test_repo_without_origin_passes_preflight(lab):
    git(lab.primary, "remote", "remove", "origin")
    assert land(lab, "--preflight-only").returncode == 0


# --- lock ---------------------------------------------------------------------

def lock_dir(lab):
    return Path(git(lab.wt, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "gstack-land.lock"


def test_live_lock_is_code_12_and_left_alone(lab):
    d = lock_dir(lab)
    d.mkdir()
    (d / "pid").write_text(str(os.getpid()))
    assert land(lab, "--preflight-only").returncode == 12
    assert d.exists(), "someone else's lock is never removed"


def test_stale_lock_is_cleared_and_released(lab):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    d = lock_dir(lab)
    d.mkdir()
    (d / "pid").write_text(str(dead.pid))
    assert land(lab, "--preflight-only").returncode == 0
    assert not d.exists(), "the lock must be released on exit"


# --- usage --------------------------------------------------------------------

def test_landing_from_main_is_code_64(lab):
    assert land(lab, "--preflight-only", wt=lab.primary).returncode == 64


def test_bad_argument_is_code_64_not_2(lab):
    assert land(lab, "--no-such-flag").returncode == 64
