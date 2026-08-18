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
