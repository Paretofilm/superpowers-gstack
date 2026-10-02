"""scripts/land-worktree.py — solo landing in one command (spec 2026-09-29).

Preflight tests use a FAKE `wt` (a shell script answering only `config approvals
list`), so they run without worktrunk, in CI too. The landing tests in the second
half need the real `wt` and skip without it. Every path in the fixture contains a
space on purpose: an argument list that survives `my proj` survives everything a
shell string would have mangled.
"""
from __future__ import annotations

import fcntl
import json
import os
import importlib.util
import shlex
import shutil
import signal
import subprocess
import sys
import time
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


# A fake merge that does what a successful `wt merge` does to the refs: the target
# (the last argument) fast-forwards to the worktree's HEAD. No hooks, no rebase.
FF_MERGE = 'for t; do :; done; git -C "$2" update-ref "refs/heads/$t" HEAD; exit 0'


def write_shim(root, approvals, merge="exit 99", approvals_rc=0):
    """Fake wt: answers `config approvals list`; records the argv of `merge` to
    <bin>/merge-argv (one argument per line) and then runs the `merge` shell body."""
    d = root / "bin"
    d.mkdir(exist_ok=True)
    f = d / "wt"
    f.write_text("#!/bin/sh\nif [ \"$3\" = config ] && [ \"$4\" = approvals ]; then\n"
                 "cat <<'EOF'\n" + approvals + f"EOF\nexit {approvals_rc}\nfi\n"
                 "if [ \"$3\" = merge ]; then\n"
                 "printf '%s\\n' \"$@\" > \"$(dirname \"$0\")/merge-argv\"\n"
                 + merge + "\nfi\nexit 99\n")
    f.chmod(0o755)
    return d


def land(lab, *args, shim=APPROVED, wt=None, env=None, merge="exit 99", approvals_rc=0):
    path = "/usr/bin:/bin"
    if shim is not None:
        path = f"{write_shim(lab.root, shim, merge, approvals_rc)}:{path}"
    e = {"HOME": str(lab.root), "PATH": path}
    e.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPT), "--worktree", str(wt or lab.wt),
                           "--ci-wait", "0", *args], capture_output=True, text=True, env=e)


def verdict(p):
    return json.loads(p.stdout.strip().splitlines()[-1])


# --- mode: fails closed -------------------------------------------------------

def project_mode(lab, text):
    """The whole project says `text` (None: no CLAUDE.md at all): committed on main,
    pushed, and the branch rebased onto it, so main and branch agree."""
    if text is None:
        git(lab.primary, "rm", "-q", "CLAUDE.md")
    else:
        (lab.primary / "CLAUDE.md").write_text(text)
        git(lab.primary, "add", "CLAUDE.md")
    git(lab.primary, "commit", "-qm", "chore: mode on main")
    git(lab.primary, "push", "-q", "origin", "main")
    git(lab.wt, "rebase", "-q", "main")


def set_mode(lab, text, scope):
    """`project`: main and branch say it alike. `branch`: only the branch says it (main
    keeps the fixture's `Landing mode: solo`)."""
    if scope == "project":
        project_mode(lab, text)
    else:
        (lab.wt / "CLAUDE.md").write_text(text)
        git(lab.wt, "commit", "-qam", "chore: mode")


# 3.5.1: what the project says (main and branch alike) is read as before → 2. The same
# text on the branch alone, against main's solo, is the branch changing the mode → 14.
SCOPES = [pytest.param("project", 2, id="project"), pytest.param("branch", 14, id="branch-only")]


@pytest.mark.parametrize("text", [
    "# proj\n",                                        # no line at all
    "# proj\n\nLanding mode: pr\n",                    # explicit pr
    "# proj\n\nLanding mode: solo \n",                 # trailing space
    "# proj\n\nSet Landing mode: solo in prose.\n",    # inside a sentence
    "# proj\n\nLanding mode: SOLO\n",                  # wrong case
])
@pytest.mark.parametrize("scope,code", SCOPES)
def test_mode_other_than_exact_solo_fails_closed(lab, text, scope, code):
    set_mode(lab, text, scope)
    p = land(lab, "--preflight-only")
    assert p.returncode == code, p.stderr
    assert verdict(p)["landed"] is False


FENCE = "```"


@pytest.mark.parametrize("text", [
    f"# proj\n\n{FENCE}\nLanding mode: solo\n{FENCE}\n",                   # only an example in a fence
    f"# proj\n\n~~~md\nLanding mode: solo\n~~~\n",                          # tilde fence
    "# proj\n\nLanding mode: solo\n\nLanding mode: pr\n",                   # the real lines disagree
    "# proj\n\nLanding mode: pr\n\nLanding mode: solo\n",
])
@pytest.mark.parametrize("scope,code", SCOPES)
def test_mode_in_a_code_fence_or_conflicting_fails_closed(lab, text, scope, code):
    set_mode(lab, text, scope)
    assert land(lab, "--preflight-only").returncode == code


def test_a_fenced_pr_example_does_not_override_the_real_solo_line(lab):
    (lab.wt / "CLAUDE.md").write_text(f"# proj\n\nExample:\n{FENCE}\nLanding mode: pr\n{FENCE}\n\nLanding mode: solo\n")
    git(lab.wt, "commit", "-qam", "chore: mode")
    p = land(lab, "--preflight-only")
    assert p.returncode == 0, p.stderr


# --- 3.5.1: a branch never sets the policy it is landed under -------------------
# Codex adversarial review 2026-10-02: the mode was read only from the worktree being
# landed, so a branch that switched `pr` to `solo` (or added `solo`) landed on main
# with no pull request. The line is now compared with main's own.

SOLO, PR, NO_LINE = "# proj\n\nLanding mode: solo\n", "# proj\n\nLanding mode: pr\n", "# proj\n"


def nothing_moved(lab, main_before, remote_before):
    assert not (lab.root / "bin" / "merge-argv").exists(), "wt merge never ran"
    assert git(lab.primary, "rev-parse", "main") == main_before, "local main did not move"
    assert git(lab.remote, "rev-parse", "main") == remote_before, "nothing was pushed"


@pytest.mark.parametrize("on_main,on_branch", [
    pytest.param(PR, SOLO, id="pr-to-solo"),
    pytest.param(NO_LINE, SOLO, id="adds-solo"),
    pytest.param(None, SOLO, id="adds-claude-md-with-solo"),
    pytest.param(SOLO, PR, id="solo-to-pr"),
    pytest.param(SOLO, NO_LINE, id="drops-the-line"),
    pytest.param(SOLO, f"# proj\n\n{FENCE}\nLanding mode: solo\n{FENCE}\n", id="fences-the-line"),
    pytest.param(PR, "# proj\n\nLanding mode: pr\n\nLanding mode: solo\n", id="adds-a-second-value"),
])
def test_a_branch_that_introduces_or_changes_the_landing_mode_is_code_14(lab, on_main, on_branch):
    if on_main != SOLO:
        project_mode(lab, on_main)
    (lab.wt / "CLAUDE.md").write_text(on_branch)
    git(lab.wt, "add", "CLAUDE.md")
    git(lab.wt, "commit", "-qm", "chore: the branch sets its own landing mode")
    main_before, remote_before = git(lab.primary, "rev-parse", "main"), git(lab.remote, "rev-parse", "main")
    p = land(lab, merge=FF_MERGE)                  # a real landing attempt, not a preflight
    assert p.returncode == 14, p.stdout + p.stderr
    v = verdict(p)
    assert v["landed"] is False and v["code"] == 14
    assert "main says" in p.stderr and "the branch says" in p.stderr, "both values are named"
    assert "diff" in p.stderr and "CLAUDE.md" in p.stderr, "the change is printed for the user"
    nothing_moved(lab, main_before, remote_before)


def test_a_branch_that_edits_claude_md_but_keeps_the_mode_lands_as_before(lab):
    (lab.wt / "CLAUDE.md").write_text(f"# proj\n\nNotes.\n\n{FENCE}\nLanding mode: pr\n{FENCE}\n\nLanding mode: solo\n")
    git(lab.wt, "commit", "-qam", "docs: notes, same mode")
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 0, p.stderr
    assert git(lab.remote, "rev-parse", "main") == git(lab.wt, "rev-parse", "HEAD")


def test_main_changing_the_mode_after_the_branch_forked_is_a_rebase_not_14(lab):
    """The branch did not touch the line; main did, later. That is 'rebase needed' (after
    the rebase the branch carries main's line), not a branch setting its own policy."""
    (lab.primary / "CLAUDE.md").write_text(PR)
    git(lab.primary, "commit", "-qam", "chore: the project moves to pull requests")
    git(lab.primary, "push", "-q", "origin", "main")
    main_before, remote_before = git(lab.primary, "rev-parse", "main"), git(lab.remote, "rev-parse", "main")
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 10, p.stderr
    assert "rebase needed" in p.stderr and "landing mode" in p.stderr
    nothing_moved(lab, main_before, remote_before)


def test_a_stale_local_main_cannot_hide_a_mode_change_on_origin(lab):
    """origin/main moved to `pr`; local main still says `solo`. A branch that contains
    origin/main and switches back to `solo` looks unchanged next to the stale local main.
    The landing compares again with the main it would land on (after the fast-forward)."""
    other = lab.root / "other"
    subprocess.run(["git", "clone", "-q", str(lab.remote), str(other)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(other, "config", k, v)
    commit(other, "CLAUDE.md", PR, "chore: the project moves to pull requests")
    git(other, "push", "-q", "origin", "main")
    git(lab.wt, "fetch", "-q", "origin")
    git(lab.wt, "rebase", "-q", "origin/main")
    commit(lab.wt, "CLAUDE.md", SOLO, "chore: and back to solo, on the branch")
    remote_before = git(lab.remote, "rev-parse", "main")
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 14, p.stdout + p.stderr
    assert "local main was fast-forwarded to origin/main" in p.stderr, "the one move is named"
    assert not (lab.root / "bin" / "merge-argv").exists(), "wt merge never ran"
    assert git(lab.remote, "rev-parse", "main") == remote_before, "nothing was pushed"


@pytest.mark.parametrize("sub_claude_md,project,code", [
    pytest.param("# pkg\n\nLanding mode: pr\n", SOLO, 0, id="sub-says-pr-root-solo"),
    pytest.param(None, SOLO, 0, id="no-claude-md-in-sub"),
    pytest.param("# pkg\n\nLanding mode: solo\n", PR, 2, id="sub-says-solo-root-pr"),
])
def test_a_call_from_a_subdirectory_reads_the_worktree_root(lab, sub_claude_md, project, code):
    if project != SOLO:
        project_mode(lab, project)
    sub = lab.wt / "pkg"
    sub.mkdir()
    (sub / ("CLAUDE.md" if sub_claude_md else "keep.md")).write_text(sub_claude_md or "x\n")
    git(lab.wt, "add", "-A")
    git(lab.wt, "commit", "-qm", "feat: a package with its own notes")
    p = land(lab, "--preflight-only", wt=sub)
    assert p.returncode == code, p.stdout + p.stderr


def test_a_subdirectorys_own_gate_file_is_not_the_projects_gate(lab):
    """wt merge reads .config/wt.toml at the worktree root; the check must read the same file."""
    (lab.wt / ".config" / "wt.toml").write_text('[post-start]\nx = "true"\n')   # root: no gate
    sub = lab.wt / "pkg"
    (sub / ".config").mkdir(parents=True)
    (sub / ".config" / "wt.toml").write_text(HOOK_TOML)
    (sub / "CLAUDE.md").write_text(SOLO)
    git(lab.wt, "add", "-A")
    git(lab.wt, "commit", "-qam", "chore: gate only in a subdirectory")
    assert land(lab, "--preflight-only", wt=sub).returncode == 9


def test_a_symlinked_claude_md_is_read_through_the_link_on_main_too(lab):
    """CLAUDE.md -> AGENTS.md is common. The worktree's file is read through the link, so
    main's committed copy must be too, or every such project would stop at 14."""
    (lab.primary / "AGENTS.md").write_text(SOLO)
    (lab.primary / "CLAUDE.md").unlink()
    (lab.primary / "CLAUDE.md").symlink_to("AGENTS.md")
    git(lab.primary, "add", "-A")
    git(lab.primary, "commit", "-qm", "chore: CLAUDE.md is a link")
    git(lab.primary, "push", "-q", "origin", "main")
    git(lab.wt, "rebase", "-q", "main")
    p = land(lab, "--preflight-only")
    assert p.returncode == 0, p.stderr
    commit(lab.wt, "AGENTS.md", PR, "chore: the branch rewrites the link's target")
    p = land(lab, "--preflight-only")
    assert p.returncode == 14
    diff = next(c for c in p.stderr.splitlines() if " diff " in c)
    assert "AGENTS.md" in diff, "the printed diff shows the file that actually changed"


def test_code_14_prints_a_diff_that_survives_a_shell_with_a_hostile_branch_name(lab):
    hostile = lab.root / "hostile wt"
    git(lab.primary, "worktree", "add", "-q", "-b", "feat/$(touch${IFS}pwned);'q", str(hostile))
    commit(hostile, "CLAUDE.md", PR, "chore: the branch switches to pr")
    p = land(lab, "--preflight-only", wt=hostile)
    assert p.returncode == 14, p.stderr
    cmd = next(c for c in p.stderr.splitlines() if " diff " in c).split("   #")[0].strip()
    r = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, cwd=lab.root)
    assert r.returncode == 0, r.stderr
    assert "+Landing mode: pr" in r.stdout and "-Landing mode: solo" in r.stdout
    assert not (lab.root / "pwned").exists() and not (hostile / "pwned").exists()


def test_mode_at_reads_a_commit_and_never_follows_a_link_out_of_the_repository(tmp_path):
    m = load_module()
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(repo, "config", k, v)
    (tmp_path / "outside.md").write_text(SOLO)
    (repo / "docs").mkdir()
    (repo / "docs" / "agents.md").write_text(SOLO)
    (repo / "CLAUDE.md").symlink_to("docs/agents.md")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "in-repo link")
    assert m.mode_at(repo, "HEAD") == "solo"
    for target in ("../outside.md", str(tmp_path / "outside.md")):
        (repo / "CLAUDE.md").unlink()
        (repo / "CLAUDE.md").symlink_to(target)
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", f"link to {target}")
        assert m.mode_at(repo, "HEAD") is None, target
    git(repo, "rm", "-q", "CLAUDE.md")
    git(repo, "commit", "-qm", "no CLAUDE.md")
    assert m.mode_at(repo, "HEAD") is None


# --- hook presence, wt presence, approvals ------------------------------------

def test_no_pre_merge_hook_is_code_9(lab):
    (lab.wt / ".config" / "wt.toml").write_text('[post-start]\nx = "true"\n')
    git(lab.wt, "commit", "-qam", "chore: no gate")
    assert land(lab, "--preflight-only").returncode == 9


@pytest.mark.parametrize("toml", [
    "[pre-merge]\n",                                  # a table with no commands
    "pre-merge = {}\n",                               # inline, empty
    'pre-merge = ""\n',                               # an empty command
    "pre-merge = []\n",                               # an empty pipeline
    "[[pre-merge]]\n",                                # a pipeline step with no commands
    '[aliases]\npre-merge = "true"\n',                # an alias, not a hook
    '[pre-merge]\ncheck = "   "\n',                   # whitespace only
    '[pre-merge\ncheck = "true"\n',                   # not TOML at all
])
def test_a_pre_merge_hook_that_runs_nothing_is_code_9(lab, toml):
    (lab.wt / ".config" / "wt.toml").write_text(toml)
    git(lab.wt, "commit", "-qam", "chore: hollow gate")
    assert land(lab, "--preflight-only").returncode == 9


@pytest.mark.parametrize("toml", [
    'pre-merge = "make test"\n',
    '[pre-merge]\ntest = "make test"\n',
    '[[pre-merge]]\ninstall = "npm ci"\n\n[[pre-merge]]\ntest = "npm test"\n',
])
def test_every_real_hook_form_counts_as_a_gate(tmp_path, toml):
    m = load_module()
    (tmp_path / ".config").mkdir()
    (tmp_path / ".config" / "wt.toml").write_text(toml)
    assert m.has_pre_merge_hook(tmp_path)


@pytest.mark.parametrize("rc,listing", [
    (1, APPROVED),                                    # wt failed: approval state unknown
    (0, "something wt never printed before\n"),       # unparseable
])
def test_approvals_that_cannot_be_read_fail_closed_as_code_3(lab, rc, listing):
    p = land(lab, "--preflight-only", shim=listing, approvals_rc=rc)
    assert p.returncode == 3, p.stderr


def test_wt_missing_is_code_8(lab):
    assert land(lab, "--preflight-only", shim=None).returncode == 8


def test_wt_missing_says_how_to_install_it_and_offers_no_merge_without_the_gate(lab):
    """3.5.1 (Codex review): the old fallback, git worktree + finishing-a-development-branch,
    merges without the project's approved pre-merge checks. Without wt there is no landing."""
    p = land(lab, "--preflight-only", shim=None)
    assert p.returncode == 8
    assert "brew install worktrunk" in p.stderr
    assert "finishing-a-development-branch" not in p.stderr and "fall back" not in p.stderr.lower()


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
    # feat/x is now behind the updated main: the rebase precheck (fix wave 3) stops it
    assert p.returncode == 10, p.stderr
    assert git(lab.primary, "rev-parse", "HEAD") == before, "the wrong branch must not move"
    assert git(lab.primary, "rev-parse", "main") == git(other, "rev-parse", "HEAD")


# --- no origin: land locally, no push -----------------------------------------

def test_repo_without_origin_passes_preflight(lab):
    git(lab.primary, "remote", "remove", "origin")
    assert land(lab, "--preflight-only").returncode == 0


# --- lock ---------------------------------------------------------------------

def lock_file(lab):
    return Path(git(lab.wt, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "gstack-land.lock"


def lock_is_free(path) -> bool:
    """True when nobody holds the kernel lock (we take it and give it straight back)."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    finally:
        os.close(fd)   # closing the only fd drops the lock too
    return True


def hold_lock(path):
    """Another process holds the lock until it is killed."""
    p = subprocess.Popen([sys.executable, "-c",
                          "import fcntl,os,sys,time\n"
                          f"fd=os.open({str(path)!r}, os.O_RDWR|os.O_CREAT, 0o644)\n"
                          "fcntl.flock(fd, fcntl.LOCK_EX)\nprint('held', flush=True)\ntime.sleep(60)\n"],
                         stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "held"
    return p


def test_lock_held_by_a_live_process_is_code_12_naming_the_file(lab):
    holder = hold_lock(lock_file(lab))
    try:
        p = land(lab, "--preflight-only")
        assert p.returncode == 12, p.stderr
        assert str(lock_file(lab)) in p.stderr
    finally:
        holder.kill()
        holder.wait()


def test_lock_is_released_after_a_normal_run(lab):
    assert land(lab, "--preflight-only").returncode == 0
    assert lock_is_free(lock_file(lab))


def test_lock_is_released_after_a_stop(lab):
    assert land(lab, "--preflight-only", shim=UNAPPROVED).returncode == 3
    assert lock_is_free(lock_file(lab))


def test_lock_of_a_dead_holder_is_free_without_any_stale_detection(lab):
    holder = hold_lock(lock_file(lab))
    holder.kill()
    holder.wait()
    assert land(lab, "--preflight-only").returncode == 0


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
    assert lock_is_free(lock_file(lab))


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


def test_second_lock_in_the_same_repo_is_code_12(lab):
    m = load_module()
    common = lock_file(lab).parent
    with m.Lock(common):
        with pytest.raises(m.Stop) as e:
            with m.Lock(common):
                pass
    assert e.value.code == 12
    assert lock_is_free(lock_file(lab))


SLOW_MERGE = 'echo "$$" > "$(dirname "$0")/merge-pid"; exec sleep 20'


def start_slow_landing(lab, merge=SLOW_MERGE, pidfile=None, ci_wait="0"):
    """A landing that blocks in a slow step; returns once that step's process has
    written its pid to `pidfile` (default: the fake wt merge's)."""
    shim = write_shim(lab.root, APPROVED, merge)
    pidfile = pidfile or shim / "merge-pid"
    e = {"HOME": str(lab.root), "PATH": f"{shim}:/usr/bin:/bin"}
    p = subprocess.Popen([sys.executable, str(SCRIPT), "--worktree", str(lab.wt), "--ci-wait", ci_wait],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=e)
    deadline = time.time() + 20
    while not (pidfile.exists() and pidfile.read_text().strip()):
        assert time.time() < deadline and p.poll() is None, p.communicate()
        time.sleep(0.05)
    return p, int(pidfile.read_text())


def test_orphaned_wt_merge_keeps_the_lock_when_the_script_is_killed(lab):
    p, child = start_slow_landing(lab)
    try:
        p.kill()
        p.wait()
        assert not lock_is_free(lock_file(lab)), "the merge still runs: a second landing must not start"
    finally:
        os.kill(child, signal.SIGKILL)
    deadline = time.time() + 5
    while not lock_is_free(lock_file(lab)):
        assert time.time() < deadline, "lock never freed after the orphan died"
        time.sleep(0.05)


def test_sigterm_is_a_clean_stop_with_a_verdict_and_a_free_lock(lab):
    p, child = start_slow_landing(lab)
    try:
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=15)
    finally:
        try:
            os.kill(child, signal.SIGKILL)
        except ProcessLookupError:
            pass
    assert p.returncode == 70, err
    v = json.loads(out.strip().splitlines()[-1])
    assert v["landed"] is False and v["code"] == 70 and "interrupted" in v["message"]
    assert "git status" in err
    assert lock_is_free(lock_file(lab))
    assert "feat: x" not in remote_log(lab)
    assert "main was not moved" in err and "no rebase is open" in err, "the state is measured"


# --- fix wave 2: the gate, the exact tip, what is printed --------------------

def merge_argv(lab):
    return (lab.root / "bin" / "merge-argv").read_text().splitlines()


def test_wt_merge_is_forced_to_verify_and_named_the_target(lab):
    """A1/A3/A4: hooks forced on over any config, explicit target, never auto-commit."""
    land(lab, "--main-branch", "main")
    argv = merge_argv(lab)
    assert argv[-1] == "main", "the validated main is passed as TARGET"
    assert "--no-commit" in argv and "--no-squash" in argv and "--no-remove" in argv
    pairs = list(zip(argv, argv[1:]))
    assert ("--config-set", "merge.verify=true") in pairs
    assert "--no-hooks" not in argv and "--yes" not in argv and "-y" not in argv


def test_worktrunk_merge_env_overrides_are_scrubbed(lab):
    shim = write_shim(lab.root, APPROVED, 'env > "$(dirname "$0")/merge-env"; exit 99')
    e = {"HOME": str(lab.root), "PATH": f"{shim}:/usr/bin:/bin", "WORKTRUNK_MERGE__VERIFY": "false"}
    subprocess.run([sys.executable, str(SCRIPT), "--worktree", str(lab.wt), "--ci-wait", "0"],
                   capture_output=True, text=True, env=e)
    env = (shim / "merge-env").read_text()
    assert "WORKTRUNK_MERGE__VERIFY" not in env
    # the project's hooks run under wt merge: our git transport settings stay out of them
    assert "BatchMode" not in env


def test_lands_with_a_fake_merge_and_pushes_the_exact_tip(lab):
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 0, p.stderr
    tip = git(lab.wt, "rev-parse", "HEAD")
    assert verdict(p)["sha"] == tip
    assert git(lab.remote, "rev-parse", "main") == tip


def test_main_with_an_extra_commit_after_the_merge_is_not_pushed(lab):
    """B1: main must be exactly the tip that passed the gate."""
    extra = ('git -C "$2" update-ref refs/heads/main '
             '"$(git -C "$2" commit-tree -p HEAD -m extra "HEAD^{tree}")"; exit 0')
    before = git(lab.remote, "rev-parse", "main")
    p = land(lab, merge=extra)
    assert p.returncode == 70, p.stderr
    assert git(lab.remote, "rev-parse", "main") == before, "nothing was pushed"
    assert "extra" not in remote_log(lab)


def test_nothing_to_land_is_code_64(lab):
    empty = lab.root / "my proj.empty"
    git(lab.primary, "worktree", "add", "-q", "-b", "feat/empty", str(empty))
    p = land(lab, "--preflight-only", wt=empty)
    assert p.returncode == 64, p.stderr
    assert "nothing to land" in p.stderr


def test_failed_merge_reports_that_main_moved_when_it_did(lab):
    """D3: the state after a failing wt merge is measured, not assumed."""
    moved = 'git -C "$2" update-ref refs/heads/main HEAD; echo "boom from wt"; exit 1'
    p = land(lab, merge=moved)
    assert p.returncode == 70, p.stderr
    assert "main moved" in p.stderr and "boom from wt" in p.stderr
    assert "main was not moved" not in p.stderr


def test_failed_merge_reports_that_main_did_not_move(lab):
    p = land(lab, merge='echo "pre-merge command failed: check"; exit 1')
    assert p.returncode == 6, p.stderr
    assert "main was not moved" in p.stderr
    assert "pre-merge command failed: check" in p.stderr, "the output tail is shown for code 6 too"


def test_extra_commit_on_the_remote_branch_is_not_deleted(lab):
    """B4: the remote branch is removed only when everything on it landed."""
    git(lab.wt, "push", "-q", "-u", "origin", "feat/x")
    other = lab.root / "other"
    subprocess.run(["git", "clone", "-q", "-b", "feat/x", str(lab.remote), str(other)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(other, "config", k, v)
    commit(other, "late.md", "l\n", "feat: pushed from elsewhere")
    git(other, "push", "-q", "origin", "feat/x")
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 0, p.stderr
    assert git(lab.remote, "branch", "--list", "feat/x") != "", "unlanded remote work survives"
    v = verdict(p)
    assert any("origin/feat/x" in w for w in v["warnings"])


def test_fully_landed_remote_branch_is_deleted(lab):
    git(lab.wt, "push", "-q", "-u", "origin", "feat/x")
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 0, p.stderr
    assert git(lab.remote, "branch", "--list", "feat/x") == ""


def test_remote_branch_is_matched_by_full_ref_not_by_tail(lab):
    """`ls-remote --heads origin x` also matches refs/heads/other/x."""
    git(lab.wt, "push", "-q", "origin", "HEAD:refs/heads/team/feat/x")
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 0, p.stderr
    assert git(lab.remote, "branch", "--list", "team/feat/x") != ""
    assert not any("feat/x" in w for w in verdict(p)["warnings"]), "no delete was even attempted"


def test_push_error_after_the_update_landed_is_treated_as_pushed(lab, monkeypatch, capsys):
    """B3: a non-zero push exit is re-checked against origin before it is called a failure."""
    m = load_module()
    shim = write_shim(lab.root, APPROVED, FF_MERGE)
    monkeypatch.setenv("PATH", f"{shim}:/usr/bin:/bin")
    monkeypatch.setenv("HOME", str(lab.root))
    real = m.git

    def flaky(repo, *args):
        r = real(repo, *args)
        if args[:1] == ("push",) and "--delete" not in args:
            return subprocess.CompletedProcess(r.args, 1, r.stdout, "connection reset after the update")
        return r
    monkeypatch.setattr(m, "git", flaky)
    assert m.main(["--worktree", str(lab.wt), "--ci-wait", "0"]) == 0
    assert git(lab.remote, "rev-parse", "main") == git(lab.wt, "rev-parse", "HEAD")


def test_rejected_push_is_code_7_not_confirmed(lab):
    hook = lab.remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho no >&2\nexit 1\n")
    hook.chmod(0o755)
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 7, p.stderr
    assert "not confirmed pushed" in p.stderr
    assert "nothing was pushed" not in p.stderr
    assert "UNCHECKED" in p.stderr and "hook pre-merge" in p.stderr


def test_failed_git_diff_is_unknown_not_no_overlap(lab):
    m = load_module()
    with pytest.raises(m.Stop) as e:
        m.changed(lab.wt, "refs/heads/nosuch...refs/heads/main")
    assert e.value.code == 70
    with pytest.raises(m.Stop):
        m.dirty_files(lab.root / "not-a-repo")


def test_git_never_prompts_and_ssh_is_batch_mode(lab, monkeypatch):
    m = load_module()
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
    monkeypatch.delenv("GIT_SSH", raising=False)
    env = m.batch_env(lab.wt)
    assert env["GIT_TERMINAL_PROMPT"] == "0" and "BatchMode=yes" in env["GIT_SSH_COMMAND"]
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -i mykey")
    assert m.batch_env(lab.wt)["GIT_SSH_COMMAND"] == "ssh -i mykey", "the user's transport is kept"
    monkeypatch.delenv("GIT_SSH_COMMAND")
    git(lab.wt, "config", "core.sshCommand", "ssh -i other")
    assert "GIT_SSH_COMMAND" not in m.batch_env(lab.wt), "core.sshCommand is not overridden"


def test_primary_is_the_main_worktree_even_with_a_separate_git_dir(tmp_path):
    m = load_module()
    repo, gd = tmp_path / "repo", tmp_path / "store" / "gd"
    gd.parent.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--separate-git-dir", str(gd), str(repo)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(repo, "config", k, v)
    commit(repo, "a", "a\n", "init")
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "feat", str(wt))
    # git 2.54 itself names the git dir as the main worktree here; never hand that to wt
    assert m.primary_worktree(wt) is None
    assert m.primary_worktree(wt) != (tmp_path / "store").resolve(), "the old <common>/.. answer"
    git(repo, "config", "core.worktree", str(repo))            # what a submodule's git dir carries
    assert m.primary_worktree(wt) == repo.resolve()


def test_primary_is_the_main_worktree_in_an_ordinary_repo(lab):
    assert load_module().primary_worktree(lab.wt) == lab.primary.resolve()


HOSTILE_BRANCH = "feat/$(touch${IFS}pwned);'q"


def test_printed_commands_round_trip_through_a_shell(tmp_path):
    """E1: a branch with shell metacharacters and a path with an apostrophe."""
    root = tmp_path / "it's here"
    root.mkdir()
    remote, primary = root / "remote.git", root / "my proj"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(primary)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(primary, "config", k, v)
    (primary / ".config").mkdir()
    (primary / ".config" / "wt.toml").write_text(HOOK_TOML)
    (primary / "CLAUDE.md").write_text("# proj\n\nLanding mode: solo\n")
    git(primary, "add", "-A")
    git(primary, "commit", "-qm", "init")
    git(primary, "remote", "add", "origin", str(remote))
    git(primary, "push", "-q", "-u", "origin", "main")
    wt = root / "wt's tree"
    git(primary, "worktree", "add", "-q", "-b", HOSTILE_BRANCH, str(wt))
    commit(wt, "f.md", "f\n", "feat: f")
    lab = SimpleNamespace(root=root, remote=remote, primary=primary, wt=wt)
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 0, p.stderr
    assert not (wt / "pwned").exists() and not Path("pwned").exists()
    remove = next(r for r in verdict(p)["remaining"] if " remove " in r)
    assert shlex.split(remove) == ["wt", "-C", str(primary), "remove", HOSTILE_BRANCH]

    m = load_module()
    for stop in (m._classify(subprocess.CompletedProcess([], 1, "pre-merge command failed", ""), wt, "main", False, False),
                 m._classify(subprocess.CompletedProcess([], 1, "CONFLICT", ""), wt, "main", False, True),
                 m._classify(subprocess.CompletedProcess([], 1, "needs approval", ""), wt, "main", False, False)):
        for c in stop.commands:
            argv = shlex.split(c.split("   #")[0])
            assert str(wt) in argv, c
    cmds = m.push_stop_commands(wt, primary, "main")
    assert shlex.split(cmds[1].split("   #")[0])[:3] == ["git", "-C", str(primary)]
    assert any(shlex.split(c.split("   #")[0])[:4] == ["wt", "-C", str(primary), "hook"] for c in cmds)
    held = m.Stop  # the lock message names a quoted file
    common = Path(git(wt, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    with m.Lock(common):
        with pytest.raises(held) as e:
            with m.Lock(common):
                pass
    assert shlex.split(e.value.commands[0].split("   #")[0])[-1] == str(common / "gstack-land.lock")


# --- fix wave 3 ------------------------------------------------------------------

def test_python_without_tomllib_stops_with_a_json_verdict(lab, monkeypatch, capsys):
    m = load_module()
    monkeypatch.setattr(m, "tomllib", None)
    assert m.main(["--worktree", str(lab.wt), "--preflight-only"]) == 70
    cap = capsys.readouterr()
    v = json.loads(cap.out.strip().splitlines()[-1])
    assert v["code"] == 70 and "Python >= 3.11" in v["message"]


OLD_PY = "/usr/bin/python3"


@pytest.mark.skipif(not Path(OLD_PY).exists() or subprocess.run(
    [OLD_PY, "-c", "import sys; sys.exit(sys.version_info >= (3, 11))"]).returncode != 0,
    reason="no python older than 3.11 at /usr/bin/python3")
def test_an_old_system_python_gets_a_verdict_not_a_traceback(lab):
    shim = write_shim(lab.root, APPROVED)
    p = subprocess.run([OLD_PY, str(SCRIPT), "--worktree", str(lab.wt), "--preflight-only"],
                       capture_output=True, text=True,
                       env={"HOME": str(lab.root), "PATH": f"{shim}:/usr/bin:/bin"})
    assert p.returncode == 70, p.stderr
    assert "Python >= 3.11" in verdict(p)["message"]


def kill_quietly(pid):
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def interrupt(p, child):
    try:
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
    finally:
        kill_quietly(child)
    return out, err, json.loads(out.strip().splitlines()[-1])


def test_interrupt_after_the_merge_moved_main_says_so_and_how_to_finish(lab):
    moved = ('git -C "$2" update-ref refs/heads/main HEAD; '
             'echo "$$" > "$(dirname "$0")/merge-pid"; exec sleep 20')
    tip = git(lab.wt, "rev-parse", "HEAD")
    p, child = start_slow_landing(lab, merge=moved)
    out, err, v = interrupt(p, child)
    assert p.returncode == 70 and v["landed"] is False, err
    assert "main moved" in err and "not confirmed pushed" in err
    assert git(lab.remote, "rev-parse", "main") != tip
    assert "push origin" in err, "the way to finish is printed"
    assert f"push origin {tip}:" in err, "and it pushes the gated sha, nothing else"
    assert "exit 4" in err, "and that a plain re-run would stop on the unpushed main"


def test_interrupt_with_main_not_at_the_gated_sha_prints_no_push(lab):
    """Wave 4 minor 1: a push is offered only for the sha that passed the gate."""
    odd = ('git -C "$2" update-ref refs/heads/main '
           '"$(git -C "$2" commit-tree -p HEAD -m odd "HEAD^{tree}")"; '
           'echo "$$" > "$(dirname "$0")/merge-pid"; exec sleep 20')
    p, child = start_slow_landing(lab, merge=odd)
    out, err, v = interrupt(p, child)
    assert p.returncode == 70 and v["landed"] is False, err
    assert "main moved" in err
    assert "push origin" not in err


def test_an_error_while_measuring_an_interrupt_still_gives_a_verdict(lab, monkeypatch, capsys):
    """Wave 4 minor 2: the measurement itself must not escape the verdict guarantee."""
    m = load_module()

    def interrupted(a):
        m.PROGRESS.update(wt=lab.wt, branch="feat/x", main="main", before="0" * 40)
        raise KeyboardInterrupt
    monkeypatch.setattr(m, "land", interrupted)
    monkeypatch.setattr(m, "out", lambda *a, **k: None)          # every git read fails
    assert m.main(["--worktree", str(lab.wt)]) == 70
    v = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert v["code"] == 70 and v["landed"] is False and "interrupted" in v["message"]


def test_an_exception_while_measuring_an_interrupt_still_gives_a_verdict(lab, monkeypatch, capsys):
    m = load_module()

    def interrupted(a):
        m.PROGRESS.update(wt=lab.wt, branch="feat/x", main="main")
        raise KeyboardInterrupt

    def boom(*a):
        raise RuntimeError("measurement broke")
    monkeypatch.setattr(m, "land", interrupted)
    monkeypatch.setattr(m, "rebase_open", boom)
    assert m.main(["--worktree", str(lab.wt)]) == 70
    cap = capsys.readouterr()
    v = json.loads(cap.out.strip().splitlines()[-1])
    assert v["code"] == 70 and "interrupted" in v["message"] and "measurement broke" in cap.err


def test_a_leftover_rebase_head_is_not_an_open_rebase(lab):
    """Wave 4 minor 5: only rebase-merge/rebase-apply mean a rebase is open."""
    f = Path(git(lab.wt, "rev-parse", "--path-format=absolute", "--git-path", "REBASE_HEAD"))
    f.write_text(git(lab.wt, "rev-parse", "HEAD") + "\n")
    p = land(lab, "--preflight-only")
    assert p.returncode == 0, p.stderr


def test_ff_of_main_never_autostashes(lab):
    """Codex P2: merge.autostash=true would stash (and unstage) the main worktree's work."""
    git(lab.primary, "config", "merge.autostash", "true")
    other = lab.root / "other"
    subprocess.run(["git", "clone", "-q", str(lab.remote), str(other)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(other, "config", k, v)
    commit(other, "z.md", "z\n", "chore: someone else pushed")
    git(other, "push", "-q", "origin", "main")
    (lab.primary / "shared.md").write_text("staged, unrelated\n")
    git(lab.primary, "add", "shared.md")
    p = land(lab, "--preflight-only")
    # main really fast-forwarded (else the test is vacuous); feat/x is then behind it: 10
    assert p.returncode == 10, p.stderr
    assert git(lab.primary, "rev-parse", "main") == git(other, "rev-parse", "HEAD")
    assert git(lab.primary, "stash", "list") == "", "no stash entry, ever"
    assert "shared.md" in git(lab.primary, "diff", "--cached", "--name-only"), "still staged"


def test_unreadable_branch_after_the_merge_is_named_as_such(lab):
    """Wave 5 minor b: no 'got a new commit (?)' when the branch simply cannot be read."""
    gone = ('for t; do :; done; git -C "$2" update-ref "refs/heads/$t" HEAD; '
            'git -C "$2" update-ref -d refs/heads/feat/x; exit 0')
    p = land(lab, merge=gone)
    assert p.returncode == 70, p.stderr
    assert "could not read the branch after the merge" in p.stderr
    assert "got a new commit" not in p.stderr
    assert "feat: x" not in remote_log(lab)


def solo_repo(root, branch):
    """A primary on `branch` (no remote, so no origin/HEAD) and a feature worktree."""
    primary = root / "repo"
    subprocess.run(["git", "init", "-q", "-b", branch, str(primary)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(primary, "config", k, v)
    (primary / ".config").mkdir()
    (primary / ".config" / "wt.toml").write_text(HOOK_TOML)
    (primary / "CLAUDE.md").write_text("# proj\n\nLanding mode: solo\n")
    git(primary, "add", "-A")
    git(primary, "commit", "-qm", "init")
    wt = root / "repo.feat"
    git(primary, "worktree", "add", "-q", "-b", "feat/y", str(wt))
    commit(wt, "y.md", "y\n", "feat: y")
    return SimpleNamespace(root=root, primary=primary, wt=wt)


@pytest.mark.parametrize("branch,code", [("master", 0), ("main", 0), ("trunk", 64)])
def test_default_branch_falls_back_to_main_then_master(tmp_path, branch, code):
    """Codex P2 (wave 5): origin/HEAD → main → master → a usage error naming --main-branch."""
    r = solo_repo(tmp_path, branch)
    p = land(r, "--preflight-only")
    assert p.returncode == code, p.stderr
    if code == 0:
        assert verdict(p)["main"] == branch
    else:
        assert "--main-branch" in p.stderr


@pytest.mark.parametrize("remote_branches", [
    pytest.param(("main",), id="origin-main-only"),
    pytest.param(("main", "master"), id="origin-main-and-a-stale-master"),
])
def test_default_branch_agrees_with_verify_and_land_when_origin_head_is_missing(tmp_path, remote_branches):
    """3.5.1: with no origin/HEAD (a repo only ever pushed, never fetched), verify-and-land's
    DEFAULT_REF tries origin/main first. land tried local main, then local master — so with
    origin/main and only a local master it picked master, and with a stale origin/master
    beside origin/main it landed and pushed there. Now both name main; master is no target."""
    r = solo_repo(tmp_path, "master")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    git(r.primary, "remote", "add", "origin", str(remote))
    for name in remote_branches:
        git(r.primary, "push", "-q", "origin", f"master:{name}")
    assert git(r.primary, "symbolic-ref", "-q", "refs/remotes/origin/HEAD", check=False) == ""
    before = {n: git(remote, "rev-parse", n) for n in remote_branches}
    p = land(r, merge=FF_MERGE)
    assert p.returncode == 64, p.stdout + p.stderr
    assert "'main' does not exist here" in p.stderr and "--main-branch" in p.stderr
    assert {n: git(remote, "rev-parse", n) for n in remote_branches} == before, "nothing was pushed"


# --- the skill's exit-code table matches the script ---------------------------

LAND_SKILL = REPO / "skills" / "land" / "SKILL.md"


def exit_rows() -> dict[int, str]:
    rows = {}
    for line in LAND_SKILL.read_text().splitlines():
        if line.startswith("| ") and line.split("|")[1].strip().isdigit():
            rows[int(line.split("|")[1])] = " ".join(line.split())
    return rows


def test_exit_codes_are_distinct_and_each_has_a_row_in_the_skill():
    m = load_module()
    codes = [m.MODE, m.UNAPPROVED, m.MAIN_AHEAD, m.OVERLAP, m.HOOK_RED, m.PUSH, m.NO_WT, m.NO_HOOK,
             m.REBASE, m.FETCH, m.LOCKED, m.DIRTY, m.POLICY, m.USAGE, m.UNKNOWN]
    assert len(set(codes)) == len(codes), "two stops share a code"
    assert not {0, 1} & set(codes), "0 is landed; 1 is what an uncaught Python error exits with"
    assert set(exit_rows()) == {0, *codes}


def test_skill_exit_14_shows_the_change_and_leaves_the_choice_to_the_user():
    row = exit_rows()[14]
    assert "git diff" in row and "CLAUDE.md" in row
    assert "never through `land`" in row, "the policy change reaches main on its own"
    assert "/ship" in row, "a project whose main says pr takes the change through a pull request"
    assert "restore" in row, "or the branch is put right"


def test_skill_exit_8_stops_for_the_install_and_merges_nothing_without_the_gate():
    row = exit_rows()[8]
    assert "brew install worktrunk" in row
    assert "Fall back" not in row and "without the gate" in row.replace("pre-merge ", "")


def test_skill_exit_2_records_a_missing_line_on_main_not_on_the_branch():
    row = exit_rows()[2]
    assert "on `main`" in row and "not on the branch" in row, "a line the branch adds stops at 14"


def test_interrupt_during_the_push_is_not_called_landed(lab):
    pid = lab.root / "push-pid"
    hook = lab.remote / "hooks" / "pre-receive"
    hook.write_text(f'#!/bin/sh\necho "$$" > "{pid}"\nexec sleep 20\n')
    hook.chmod(0o755)
    p, child = start_slow_landing(lab, merge=FF_MERGE, pidfile=pid)
    out, err, v = interrupt(p, child)
    assert p.returncode == 70 and v["landed"] is False, err
    assert "main moved" in err and "not confirmed pushed" in err


def test_interrupt_after_a_confirmed_push_is_a_landing_with_a_warning(lab):
    pid = lab.root / "gh-pid"
    (lab.root / "bin").mkdir(exist_ok=True)
    gh = lab.root / "bin" / "gh"
    gh.write_text(f'#!/bin/sh\necho "$$" > "{pid}"\nexec sleep 20\n')
    gh.chmod(0o755)
    p, child = start_slow_landing(lab, merge=FF_MERGE, pidfile=pid, ci_wait="30")
    out, err, v = interrupt(p, child)
    assert p.returncode == 0, err
    assert v["landed"] is True and v["sha"] == git(lab.wt, "rev-parse", "HEAD")
    assert any("interrupted" in w for w in v["warnings"])
    assert git(lab.remote, "rev-parse", "main") == v["sha"]


def test_all_worktrunk_env_is_kept_away_from_wt(lab):
    shim = write_shim(lab.root, APPROVED, 'env > "$(dirname "$0")/merge-env"; exit 99')
    e = {"HOME": str(lab.root), "PATH": f"{shim}:/usr/bin:/bin",
         "WORKTRUNK_PROJECT_CONFIG_PATH": str(lab.root / "elsewhere.toml"), "WORKTRUNK_ANYTHING": "x"}
    subprocess.run([sys.executable, str(SCRIPT), "--worktree", str(lab.wt), "--ci-wait", "0"],
                   capture_output=True, text=True, env=e)
    assert "WORKTRUNK_" not in (shim / "merge-env").read_text()


def test_wt_merge_never_rebases_inside_the_gated_step(lab):
    land(lab)
    argv = merge_argv(lab)
    assert "--no-rebase" in argv and "merge.rebase=true" not in argv


def test_branch_behind_main_is_code_10_before_anything_moves(lab):
    commit(lab.primary, "later.md", "l\n", "chore: main moves on")
    git(lab.primary, "push", "-q", "origin", "main")
    main_before, branch_before = git(lab.primary, "rev-parse", "main"), git(lab.wt, "rev-parse", "HEAD")
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 10, p.stderr
    assert "rebase needed" in p.stderr
    assert shlex.split(next(c for c in p.stderr.splitlines() if "step rebase" in c).strip()) == \
        ["wt", "-C", str(lab.wt), "step", "rebase", "main"]
    assert not (lab.root / "bin" / "merge-argv").exists(), "wt merge never ran"
    assert git(lab.primary, "rev-parse", "main") == main_before
    assert git(lab.wt, "rev-parse", "HEAD") == branch_before


def test_open_rebase_in_the_worktree_is_code_10_with_the_state_visible(lab):
    commit(lab.wt, "shared.md", "feature side\n", "feat: shared")
    commit(lab.primary, "shared.md", "main side\n", "chore: main moves the same line")
    git(lab.primary, "push", "-q", "origin", "main")
    git(lab.wt, "rebase", "main", check=False)                  # conflicts: the rebase stays open
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 10, p.stderr
    assert "a rebase is open" in p.stderr and "rebase --abort" in p.stderr


def test_remote_branch_whose_extra_content_is_only_in_a_merge_commit_is_kept(lab):
    """git cherry skips merge commits: a merge carrying a unique file must not read as landed."""
    git(lab.wt, "push", "-q", "-u", "origin", "feat/x")
    other = lab.root / "other"
    subprocess.run(["git", "clone", "-q", "-b", "feat/x", str(lab.remote), str(other)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(other, "config", k, v)
    (other / "unique.md").write_text("only here\n")
    git(other, "add", "unique.md")
    tree = git(other, "write-tree")
    base = git(other, "rev-parse", "origin/main")
    evil = git(other, "commit-tree", tree, "-p", "HEAD", "-p", base, "-m", "merge carrying unique.md")
    git(other, "push", "-q", "origin", f"{evil}:refs/heads/feat/x")
    p = land(lab, merge=FF_MERGE)
    assert p.returncode == 0, p.stderr
    assert git(lab.remote, "rev-parse", "refs/heads/feat/x") == evil, "the merge commit survives"
    assert any("origin/feat/x" in w for w in verdict(p)["warnings"])


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
@pytest.mark.parametrize("how", ["user-config", "project-scoped-user-config", "env"])
def test_merge_verify_false_cannot_switch_the_gate_off(lab, how):
    """A1: worktrunk's `merge.verify = false` skips hooks without --no-hooks (measured on
    0.79.0). The landing forces it back on, so a red hook still stops it."""
    set_hook(lab, "false")
    approve(lab)
    cfg = lab.root / "xdg" / "worktrunk" / "config.toml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    extra = {}
    if how == "user-config":
        cfg.write_text("[merge]\nverify = false\n")
    elif how == "project-scoped-user-config":
        e = {"HOME": str(lab.root), "XDG_CONFIG_HOME": str(lab.root / "xdg"), "PATH": os.environ["PATH"]}
        show = subprocess.run(["wt", "-C", str(lab.wt), "config", "show"], capture_output=True, text=True, env=e).stdout
        ident = next(l.split("Identifier:", 1)[1].strip() for l in show.splitlines() if "Identifier:" in l)
        cfg.write_text(f'[projects."{ident}".merge]\nverify = false\n')
    else:
        extra = {"WORKTRUNK_MERGE__VERIFY": "false"}
    e = {"HOME": str(lab.root), "XDG_CONFIG_HOME": str(lab.root / "xdg"), "PATH": os.environ["PATH"], **extra}
    p = subprocess.run([sys.executable, str(SCRIPT), "--worktree", str(lab.wt), "--ci-wait", "0"],
                       capture_output=True, text=True, env=e)
    assert p.returncode == 6, p.stdout + p.stderr
    assert "feat: x" not in remote_log(lab)
    assert "feat: x" not in git(lab.primary, "log", "--format=%s", "main")


@needs_wt
def test_main_branch_other_than_wts_default_is_the_merge_target(lab):
    """A3: --main-branch trunk lands on trunk; wt's own default (main) does not move."""
    git(lab.primary, "branch", "trunk", "main")
    git(lab.primary, "push", "-q", "origin", "trunk")
    approve(lab)
    before = git(lab.primary, "rev-parse", "main")
    p = real_land(lab, "--main-branch", "trunk")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "feat: x" in git(lab.remote, "log", "--format=%s", "trunk")
    assert git(lab.primary, "rev-parse", "main") == before
    assert "feat: x" not in remote_log(lab)


@needs_wt
def test_rebase_conflict_is_code_10_with_the_rebase_left_open(lab):
    commit(lab.wt, "shared.md", "feature side\n", "feat: shared")
    commit(lab.primary, "shared.md", "main side\n", "chore: main moves the same line")
    git(lab.primary, "push", "-q", "origin", "main")
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 10 and "rebase needed" in p.stderr, p.stderr    # the precheck: nothing moved yet
    # the printed guidance: wt step rebase — it conflicts and leaves the rebase open
    e = {"HOME": str(lab.root), "XDG_CONFIG_HOME": str(lab.root / "xdg"), "PATH": os.environ["PATH"]}
    r = subprocess.run(["wt", "-C", str(lab.wt), "step", "rebase", "main"], capture_output=True, text=True,
                       env=e, stdin=subprocess.DEVNULL)
    assert r.returncode != 0
    assert (Path(git(lab.wt, "rev-parse", "--path-format=absolute", "--git-dir")) / "rebase-merge").exists()
    p = real_land(lab)
    assert p.returncode == 10 and "a rebase is open" in p.stderr, p.stderr
    assert "feat: shared" not in remote_log(lab)


@needs_wt
def test_branch_behind_main_lands_after_the_printed_rebase(lab):
    """P1-b: the gate runs on the rebased tree, so the rebase happens before wt merge."""
    commit(lab.primary, "later.md", "l\n", "chore: main moves on")
    git(lab.primary, "push", "-q", "origin", "main")
    approve(lab)
    assert real_land(lab).returncode == 10
    e = {"HOME": str(lab.root), "XDG_CONFIG_HOME": str(lab.root / "xdg"), "PATH": os.environ["PATH"]}
    r = subprocess.run(["wt", "-C", str(lab.wt), "step", "rebase", "main"], capture_output=True, text=True,
                       env=e, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    p = real_land(lab)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "feat: x" in remote_log(lab) and "chore: main moves on" in remote_log(lab)


@needs_wt
def test_a_commit_made_on_the_branch_during_the_gate_is_never_pushed(lab):
    """Codex P1 (wave 4): the tip is captured before wt merge; a commit that appears on
    the branch while the hooks run was never checked."""
    set_hook(lab, 'git commit --allow-empty -qm sneaked-in-during-the-gate')
    approve(lab)
    gated = git(lab.wt, "rev-parse", "HEAD")
    p = real_land(lab)
    assert p.returncode == 70, p.stdout + p.stderr
    sneaked = git(lab.wt, "rev-parse", "refs/heads/feat/x")
    assert sneaked != gated
    assert sneaked[:9] in p.stderr, "the new commit is named"
    assert "sneaked-in-during-the-gate" not in remote_log(lab) and "feat: x" not in remote_log(lab)


@needs_wt
def test_a_hook_that_changes_a_tracked_file_is_not_pushed(lab):
    """Codex P1 (wave 5): an auto-formatter in the gate tested a tree that differs from
    the commit — the worktree must be clean after wt merge."""
    set_hook(lab, "echo formatted >> shared.md")
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 70, p.stdout + p.stderr
    assert "shared.md" in p.stderr and "diff" in p.stderr
    assert "feat: x" not in remote_log(lab)


@needs_wt
def test_worktrunk_project_config_path_cannot_swap_the_checked_gate(lab):
    """P1-a: WORKTRUNK_PROJECT_CONFIG_PATH pointed wt at another file than the one checked."""
    set_hook(lab, "false")
    alt = lab.root / "alt.toml"
    alt.write_text('[pre-merge]\ncheck = "true"\n')
    e = {"HOME": str(lab.root), "XDG_CONFIG_HOME": str(lab.root / "xdg"), "PATH": os.environ["PATH"]}
    for extra in ({}, {"WORKTRUNK_PROJECT_CONFIG_PATH": str(alt)}):   # approve both files' commands
        r = subprocess.run(["wt", "-C", str(lab.wt), "config", "approvals", "add", "--yes"],
                           capture_output=True, text=True, env={**e, **extra}, stdin=subprocess.DEVNULL)
        assert r.returncode == 0, r.stderr
    p = subprocess.run([sys.executable, str(SCRIPT), "--worktree", str(lab.wt), "--ci-wait", "0"],
                       capture_output=True, text=True, env={**e, "WORKTRUNK_PROJECT_CONFIG_PATH": str(alt)})
    assert p.returncode == 6, p.stdout + p.stderr
    assert "feat: x" not in remote_log(lab)


@needs_wt
def test_interrupt_during_a_real_hook_says_main_was_not_moved(lab):
    pid = lab.root / "hook-pid"
    set_hook(lab, f'echo $$ > "{pid}"; exec sleep 30')
    approve(lab)
    e = {"HOME": str(lab.root), "XDG_CONFIG_HOME": str(lab.root / "xdg"), "PATH": os.environ["PATH"]}
    p = subprocess.Popen([sys.executable, str(SCRIPT), "--worktree", str(lab.wt), "--ci-wait", "0"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=e)
    deadline = time.time() + 30
    while not (pid.exists() and pid.read_text().strip()):
        assert time.time() < deadline and p.poll() is None, p.communicate()
        time.sleep(0.05)
    out, err, v = interrupt(p, int(pid.read_text()))
    assert p.returncode == 70 and v["landed"] is False, err
    assert "main was not moved" in err
    assert "feat: x" not in git(lab.primary, "log", "--format=%s", "main")


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
    assert f"wt -C '{lab.primary}' hook pre-merge" in p.stderr, "B2: the gate runs on the rebased result"
    assert "UNCHECKED" in p.stderr
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


def _origin_moves_on(lab):
    other = lab.root / "other"
    subprocess.run(["git", "clone", "-q", str(lab.remote), str(other)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(other, "config", k, v)
    commit(other, "z.md", "z\n", "chore: someone else pushed")
    git(other, "push", "-q", "origin", "main")
    return git(other, "rev-parse", "HEAD")


def test_code_10_says_main_was_fast_forwarded_when_it_was(lab):
    new_main = _origin_moves_on(lab)
    branch_before = git(lab.wt, "rev-parse", "HEAD")
    p = land(lab)
    assert p.returncode == 10, p.stderr
    assert "local main was fast-forwarded to origin/main" in p.stderr
    assert "nothing moved" not in p.stderr
    assert git(lab.primary, "rev-parse", "main") == new_main
    assert git(lab.wt, "rev-parse", "HEAD") == branch_before


def test_code_10_says_nothing_moved_when_origin_was_not_ahead(lab):
    commit(lab.primary, "later.md", "l\n", "chore: main moves on")
    git(lab.primary, "push", "-q", "origin", "main")
    p = land(lab)
    assert p.returncode == 10, p.stderr
    assert "nothing moved" in p.stderr
    assert "fast-forwarded" not in p.stderr


def test_nothing_to_land_says_main_was_fast_forwarded_when_it_was(lab):
    empty = lab.root / "my proj.empty"
    git(lab.primary, "worktree", "add", "-q", "-b", "feat/empty", str(empty))
    _origin_moves_on(lab)
    p = land(lab, "--preflight-only", wt=empty)
    # the branch is behind the new main, so 0 commits ahead -> nothing to land
    assert p.returncode == 64, p.stderr
    assert "local main was fast-forwarded to origin/main" in p.stderr
