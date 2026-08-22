"""Guard scripts/check-branch-hygiene.sh — the unlanded-work detector.

Exists because a plugin that ships /ship and finishing-a-development-branch still
had nothing that NOTICED a branch was never landed. Signal discipline is the whole
design: silent on a clean repo and on work in progress, loud only on work that has
actually been left behind.
"""

import subprocess
import pathlib
import pytest

HOOK = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "check-branch-hygiene.sh"


def git(repo, *args, **kw):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, **kw)


def run_hook(repo, idle_days="7"):
    r = subprocess.run(["bash", str(HOOK)], cwd=str(repo), capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(repo),
                            "GSTACK_BRANCH_IDLE_DAYS": idle_days})
    assert r.returncode == 0, f"hook must never fail a session: {r.stderr}"
    return r.stdout


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@t.t")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.txt").write_text("a")
    git(tmp_path, "add", "-A"); git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def test_clean_repo_is_silent(repo):
    """A hook that speaks when there is nothing to say gets ignored when there is."""
    assert run_hook(repo) == ""


def test_non_git_directory_is_silent(tmp_path):
    assert run_hook(tmp_path) == ""


def test_uncommitted_changes_are_reported(repo):
    (repo / "f.txt").write_text("changed")
    assert "uncommitted change" in run_hook(repo)


def test_current_branch_is_never_nagged(repo):
    """Committing on a branch you are standing on is work in progress, not debt."""
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    assert run_hook(repo) == ""


def test_recent_unmerged_branch_is_not_nagged(repo):
    """Below the idle threshold is active work — reporting it would be noise."""
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    git(repo, "checkout", "-q", "main")
    assert run_hook(repo, idle_days="7") == ""


def test_idle_unmerged_branch_is_reported(repo):
    """Same branch, genuinely old — now it is at risk of being forgotten."""
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A")
    old_date = "2020-01-01T00:00:00"
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "wip"], check=True,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(repo),
                        "GIT_AUTHOR_DATE": old_date, "GIT_COMMITTER_DATE": old_date,
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.t"})
    git(repo, "checkout", "-q", "main")
    out = run_hook(repo)
    assert "feature" in out and "not merged" in out


def test_invalid_threshold_falls_back_instead_of_crashing(repo):
    """A hook that aborts on a typo'd env var is worse than one that ignores it."""
    (repo / "f.txt").write_text("changed")
    assert "uncommitted change" in run_hook(repo, idle_days="seven")


def test_disable_switch_silences_everything(repo):
    (repo / "f.txt").write_text("changed")
    assert run_hook(repo, idle_days="0") == ""


# --- blind spots found 2026-08-22 while documenting the hook for end users -------
# Both are "work can disappear" cases that every branch-based check missed: a branch
# fully merged locally but never pushed reported nothing, and a stash is not a branch
# at all. Documenting the tool is how they surfaced — writing down what it does not
# catch is a cheaper audit than re-reading the code.


def with_remote(tmp_path, repo):
    """Give `repo` a real upstream so ahead/behind counts are meaningful."""
    # OUTSIDE the work tree — a bare repo created inside it shows up as an
    # untracked directory and the hook correctly reports a dirty tree, which
    # looks like a hook bug and is a test-harness bug.
    bare = tmp_path.parent / f"{tmp_path.name}-remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "-q", "-u", "origin", "main")
    return bare


def test_pushed_and_clean_is_silent(tmp_path, repo):
    with_remote(tmp_path, repo)
    assert run_hook(repo) == ""


def test_unpushed_commits_are_reported(tmp_path, repo):
    """A commit that exists only on this machine is one disk failure from gone."""
    with_remote(tmp_path, repo)
    (repo / "f.txt").write_text("local only")
    git(repo, "commit", "-qam", "local only")
    out = run_hook(repo)
    assert "only on this machine" in out and "ahead of origin/main" in out


def test_local_only_repo_is_never_nagged_about_pushing(tmp_path, repo):
    """No remote configured means pushing is not a thing this repo can do. Saying so
    every session would be noise — and noise is what makes a hook get ignored."""
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    git(repo, "checkout", "-q", "main")
    assert "only on this machine" not in run_hook(repo)


def test_unpushed_is_not_double_reported_with_stale(tmp_path, repo):
    """A branch never pushed at all is already covered by the stale-unmerged check;
    counting it again here would report one piece of work twice."""
    with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    git(repo, "checkout", "-q", "main")
    assert "only on this machine" not in run_hook(repo)


def test_fresh_stash_is_not_nagged(tmp_path, repo):
    """git-hygiene tells users a stash is for holds of minutes-to-hours — so a fresh
    one is the tool being used correctly, not debt."""
    with_remote(tmp_path, repo)
    (repo / "f.txt").write_text("wip"); git(repo, "stash", "-q")
    assert "stash" not in run_hook(repo)


def test_stale_stash_is_reported(tmp_path, repo):
    """Past the threshold it stopped being a hold and became forgotten work."""
    with_remote(tmp_path, repo)
    (repo / "f.txt").write_text("wip")
    subprocess.run(["git", "-C", str(repo), "stash", "-q"], check=True,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(repo),
                        "GIT_COMMITTER_DATE": "2020-01-01T00:00:00",
                        "GIT_AUTHOR_DATE": "2020-01-01T00:00:00",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.t",
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.t"})
    out = run_hook(repo)
    assert "stash(es)" in out and "meant for hours" in out
