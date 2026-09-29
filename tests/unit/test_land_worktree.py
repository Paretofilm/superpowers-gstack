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
import importlib.util
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


def load_module():
    spec = importlib.util.spec_from_file_location("land_worktree", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


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
    path = "/usr/bin:/bin"
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


# --- final-review fixes -------------------------------------------------------

def test_sh_tolerates_non_utf8_output():
    m = load_module()
    r = m.sh("printf", "a\\377b")
    assert r.returncode == 0 and r.stdout.startswith("a") and r.stdout.endswith("b")


def test_unexpected_exception_prints_json_verdict_and_exits_70(monkeypatch, capsys, tmp_path):
    m = load_module()

    def boom(a):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(m, "land", boom)
    rc = m.main(["--worktree", str(tmp_path)])
    cap = capsys.readouterr()
    assert rc == 70
    v = json.loads(cap.out.strip().splitlines()[-1])
    assert v["landed"] is False and v["code"] == 70 and "kaboom" in v["message"]
    assert "Traceback" in cap.err and "kaboom" in cap.err


def test_unexpected_exception_releases_the_lock(lab, monkeypatch, capsys):
    m = load_module()

    def boom(*a, **k):
        raise RuntimeError("inside the lock")
    monkeypatch.setattr(m, "_land_locked", boom)
    assert m.main(["--worktree", str(lab.wt)]) == 70
    assert not lock_dir(lab).exists()


def test_missing_main_branch_is_code_64_naming_the_flag(lab):
    p = land(lab, "--main-branch", "nosuch", "--preflight-only")
    assert p.returncode == 64, p.stderr
    assert "--main-branch" in p.stderr


def test_recovery_hint_names_a_runnable_command():
    m = load_module()
    assert m.pull_hint(Path("/tmp/my proj"), "main") == "git -C '/tmp/my proj' pull --rebase origin main"
    without = m.pull_hint(None, "main")
    assert "checked out" in without and "git -C" not in without


def test_untracked_directory_overlap_is_code_5(lab):
    (lab.wt / "newdir").mkdir()
    commit(lab.wt, "newdir/a.py", "x\n", "feat: adds newdir/a.py")
    (lab.primary / "newdir").mkdir()
    (lab.primary / "newdir" / "a.py").write_text("mine\n")
    p = land(lab, "--preflight-only")
    assert p.returncode == 5, p.stderr
    assert "newdir/a.py" in p.stderr


def dead_pid():
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    return dead.pid


def test_stale_lock_rename_lost_race_is_code_12(lab, monkeypatch):
    m = load_module()
    d = lock_dir(lab)
    d.mkdir()
    (d / "pid").write_text(str(dead_pid()))

    def lost(*a, **k):
        raise FileNotFoundError("another process won the rename")
    monkeypatch.setattr(m.os, "rename", lost)
    with pytest.raises(m.Stop) as e:
        with m.Lock(d.parent):
            pass
    assert e.value.code == 12


def test_lock_exit_leaves_a_lock_now_owned_by_someone_else(lab):
    m = load_module()
    d = lock_dir(lab)
    with m.Lock(d.parent):
        (d / "pid").write_text(str(os.getpid() + 1))
    assert d.exists(), "a lock whose pid file is not ours is never removed"
    shutil.rmtree(d)


def test_stale_lock_is_renamed_before_removal(lab, monkeypatch):
    m = load_module()
    d = lock_dir(lab)
    d.mkdir()
    (d / "pid").write_text(str(dead_pid()))
    calls, real = [], m.os.rename

    def spy(a, b):
        calls.append((str(a), str(b)))
        real(a, b)
    monkeypatch.setattr(m.os, "rename", spy)
    with m.Lock(d.parent):
        pass
    assert calls and calls[0][1].endswith(f".stale-{os.getpid()}")
    assert not Path(calls[0][1]).exists()


# --- usage --------------------------------------------------------------------

def test_landing_from_main_is_code_64(lab):
    assert land(lab, "--preflight-only", wt=lab.primary).returncode == 64


def test_bad_argument_is_code_64_not_2(lab):
    assert land(lab, "--no-such-flag").returncode == 64


# ===== landing against the real wt (skipped without worktrunk, e.g. in CI) =====

needs_wt = pytest.mark.skipif(shutil.which("wt") is None,
                              reason="wt (worktrunk) not installed — expected in CI")


def real_land(lab, *args):
    """Isolated HOME/XDG so approvals never touch the developer's own config."""
    e = {"HOME": str(lab.root), "XDG_CONFIG_HOME": str(lab.root / "xdg"),
         "PATH": os.environ["PATH"]}
    return subprocess.run([sys.executable, str(SCRIPT), "--worktree", str(lab.wt), "--ci-wait", "0", *args],
                          capture_output=True, text=True, env=e)


def approve(lab):
    e = {"HOME": str(lab.root), "XDG_CONFIG_HOME": str(lab.root / "xdg"), "PATH": os.environ["PATH"]}
    r = subprocess.run(["wt", "-C", str(lab.wt), "config", "approvals", "add", "--yes"],
                       capture_output=True, text=True, env=e, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr


def set_hook(lab, command):
    (lab.wt / ".config" / "wt.toml").write_text(f"[pre-merge]\ncheck = '{command}'\n")
    git(lab.wt, "commit", "-qam", "chore: hook")


def remote_log(lab):
    return git(lab.remote, "log", "--format=%s", "main")


@needs_wt
def test_lands_pushes_and_leaves_the_worktree_for_the_caller(lab):
    git(lab.wt, "push", "-q", "-u", "origin", "feat/x")          # a pushed branch must be deleted
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 0, p.stderr
    v = verdict(p)
    assert v["landed"] is True and "feat: x" in remote_log(lab)
    assert git(lab.primary, "rev-parse", "main") == git(lab.remote, "rev-parse", "main")
    assert lab.wt.exists(), "the script never removes the worktree"
    assert git(lab.remote, "branch", "--list", "feat/x") == "", "the remote branch is deleted"
    assert any("remove feat/x" in r for r in v["remaining"])


@needs_wt
def test_unapproved_hooks_are_code_3_before_anything_moves(lab):
    p = real_land(lab)                                            # no approve(lab)
    assert p.returncode == 3, p.stderr
    assert "feat: x" not in remote_log(lab)


@needs_wt
def test_red_hook_is_code_6_and_main_does_not_move(lab):
    set_hook(lab, "false")
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 6, p.stderr
    assert "feat: x" not in remote_log(lab)
    assert git(lab.primary, "rev-parse", "main") == git(lab.remote, "rev-parse", "main")
    assert lab.wt.exists()


@needs_wt
def test_rebase_conflict_is_code_10_with_the_rebase_left_open(lab):
    commit(lab.wt, "shared.md", "feature side\n", "feat: shared")
    commit(lab.primary, "shared.md", "main side\n", "chore: main moves the same line")
    git(lab.primary, "push", "-q", "origin", "main")
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 10, p.stderr
    assert (Path(git(lab.wt, "rev-parse", "--path-format=absolute", "--git-dir")) / "rebase-merge").exists()


@needs_wt
def test_origin_moving_during_the_checks_is_code_7_and_nothing_is_pushed(lab):
    other = lab.root / "other"
    subprocess.run(["git", "clone", "-q", str(lab.remote), str(other)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(other, "config", k, v)
    set_hook(lab, f"cd \"{other}\" && echo x >> z.md && git add -A && git commit -qm race && git push -q origin main")
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 7, p.stderr
    assert f"git -C '{lab.primary}' pull --rebase origin main" in p.stderr
    assert "feat: x" not in remote_log(lab) and "race" in remote_log(lab)
    assert "feat: x" in git(lab.primary, "log", "--format=%s", "main"), "local main holds the work"
    assert lab.wt.exists(), "worktree and branch stand as the recovery point"


@needs_wt
def test_repo_without_origin_lands_locally_with_a_warning(lab):
    git(lab.primary, "remote", "remove", "origin")
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 0, p.stderr
    assert "feat: x" in git(lab.primary, "log", "--format=%s", "main")
    assert any("no origin" in w for w in verdict(p)["warnings"])


@needs_wt
def test_unclassified_wt_merge_failure_is_code_70_and_nothing_is_pushed(lab):
    # A git hook that refuses the fast-forward of main: wt merge fails in a way no
    # _classify rule names (not approvals, hook, rebase or overlap).
    hook = lab.primary / ".git" / "hooks" / "reference-transaction"
    hook.write_text('#!/bin/sh\n[ "$1" = prepared ] && grep -q " refs/heads/main$" && exit 1\nexit 0\n')
    hook.chmod(0o755)
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 70, p.stdout + p.stderr
    assert verdict(p)["code"] == 70
    assert "feat: x" not in remote_log(lab)
    assert lab.wt.exists()


@needs_wt
def test_non_fatal_failures_after_the_push_exit_0_and_are_listed(lab):
    git(lab.wt, "push", "-q", "-u", "origin", "feat/x")
    approve(lab)
    # no gh on PATH: only wt and git (through /usr/bin) are reachable
    bin_dir = lab.root / "nogh-bin"
    bin_dir.mkdir()
    (bin_dir / "wt").symlink_to(shutil.which("wt", path=os.environ["PATH"]))
    e = {"HOME": str(lab.root), "XDG_CONFIG_HOME": str(lab.root / "xdg"), "PATH": f"{bin_dir}:/usr/bin:/bin"}
    assert shutil.which("gh", path=e["PATH"]) is None
    p = subprocess.run([sys.executable, str(SCRIPT), "--worktree", str(lab.wt), "--ci-wait", "0"],
                       capture_output=True, text=True, env=e)
    assert p.returncode == 0, p.stderr
    assert "feat: x" in remote_log(lab), "the push happened"
    v = verdict(p)
    assert any("gh is not installed" in w for w in v["warnings"])
    assert "warning: gh is not installed" in p.stdout, "the human-readable remaining/warning section lists it"
    assert any("remove feat/x" in r for r in v["remaining"])
