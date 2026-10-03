"""scripts/lock-acceptance-tests.py — the acceptance tests the user approved stay as approved.

The vibe workflow has one checkpoint: the user reads the acceptance tests once. After
that the tests are the contract, and an agent that edits one to turn red into green
has broken it silently. `lock` commits the tests and denies Edit/Write on them;
`verify` is the real gate (a deny rule does not stop `sed` through Bash).
These tests run the script against temporary git repositories.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "lock-acceptance-tests.py"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def repo(tmp_path: Path) -> Path:
    r = tmp_path / "app"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "T")
    git(r, "config", "commit.gpgsign", "false")
    (r / "README.md").write_text("app\n")
    git(r, "add", "README.md")
    git(r, "commit", "-q", "-m", "init")
    acc = r / "Tests" / "Acceptance"
    acc.mkdir(parents=True)
    (acc / "test_a.py").write_text("def test_a():\n    assert 1 == 1\n")
    (acc / "test_b.py").write_text("def test_b():\n    assert 2 == 2\n")
    return r


def run(r: Path, *args: str, expect: int = 0, cwd: Path | None = None):
    p = subprocess.run([sys.executable, str(SCRIPT), *args, "--project-dir", str(cwd or r)],
                       capture_output=True, text=True)
    assert p.returncode == expect, f"exit {p.returncode} (wanted {expect})\n{p.stdout}\n{p.stderr}"
    assert "Traceback" not in p.stderr
    return p


def receipt(r: Path) -> dict:
    return json.loads((r / ".gstack" / "acceptance-lock.json").read_text())


def settings(r: Path) -> dict:
    return json.loads((r / ".claude" / "settings.json").read_text())


def lock(r: Path, feature: str = "radid", *globs: str):
    return run(r, "lock", "--feature", feature, *[x for g in (globs or ("Tests/Acceptance/**",)) for x in ("--path", g)])


def test_lock_commits_the_tests_then_the_rules_and_the_receipt(tmp_path):
    r = repo(tmp_path)
    lock(r)
    log = git(r, "log", "--format=%s", "-3").splitlines()
    assert log[0] == "chore(acceptance): deny edits to radid tests"
    assert log[1] == "test(acceptance): lock radid"
    test_commit = git(r, "rev-parse", "HEAD~1").strip()
    lk = receipt(r)["locks"][0]
    assert lk["commit"] == test_commit
    assert lk["files"] == ["Tests/Acceptance/test_a.py", "Tests/Acceptance/test_b.py"]
    assert settings(r)["permissions"]["deny"] == ["Edit(/Tests/Acceptance/**)", "Write(/Tests/Acceptance/**)"]
    assert git(r, "status", "--porcelain") == ""


def test_verify_is_zero_when_untouched_and_one_for_any_change(tmp_path):
    r = repo(tmp_path)
    lock(r)
    run(r, "verify")
    f = r / "Tests" / "Acceptance" / "test_a.py"
    f.write_text("def test_a():\n    assert True\n")          # not committed
    p = run(r, "verify", expect=1)
    assert "CHANGED radid Tests/Acceptance/test_a.py" in p.stdout
    git(r, "add", str(f))                                      # staged
    run(r, "verify", expect=1)
    git(r, "commit", "-q", "-m", "weaken")                     # committed
    run(r, "verify", expect=1)


def test_verify_sees_a_deleted_test(tmp_path):
    r = repo(tmp_path)
    lock(r)
    (r / "Tests" / "Acceptance" / "test_b.py").unlink()
    p = run(r, "verify", expect=1)
    assert "test_b.py" in p.stdout


def test_verify_without_a_receipt_is_two(tmp_path):
    r = repo(tmp_path)
    p = run(r, "verify", expect=2)
    assert "no acceptance lock" in p.stderr


def test_verify_from_a_subdirectory_finds_the_top_level(tmp_path):
    r = repo(tmp_path)
    lock(r)
    (r / "Tests" / "Acceptance" / "test_a.py").write_text("changed\n")
    run(r, "verify", expect=1, cwd=r / "Tests")


def test_existing_settings_are_kept(tmp_path):
    r = repo(tmp_path)
    (r / ".claude").mkdir()
    (r / ".claude" / "settings.json").write_text(json.dumps(
        {"model": "opusplan", "permissions": {"allow": ["Bash(ls:*)"], "deny": ["Read(/.env)"]}}))
    lock(r)
    s = settings(r)
    assert s["model"] == "opusplan" and s["permissions"]["allow"] == ["Bash(ls:*)"]
    assert s["permissions"]["deny"][0] == "Read(/.env)"


def test_invalid_settings_json_refuses_before_any_commit(tmp_path):
    r = repo(tmp_path)
    (r / ".claude").mkdir()
    (r / ".claude" / "settings.json").write_text("{ not json")
    before = git(r, "rev-parse", "HEAD")
    p = lock_expect(r, 2)
    assert "BLOCKED" in p.stderr and "settings.json" in p.stderr
    assert git(r, "rev-parse", "HEAD") == before
    assert not (r / ".gstack" / "acceptance-lock.json").exists()


def lock_expect(r: Path, code: int, *extra: str):
    return run(r, "lock", "--feature", "radid", "--path", "Tests/Acceptance/**", *extra, expect=code)


@pytest.mark.parametrize("glob", ["NoSuchDir/**", "/Tests/**", "../elsewhere/**"])
def test_a_bad_glob_refuses(tmp_path, glob):
    r = repo(tmp_path)
    p = run(r, "lock", "--feature", "radid", "--path", glob, expect=2)
    assert "BLOCKED" in p.stderr


def test_a_feature_cannot_be_locked_twice(tmp_path):
    r = repo(tmp_path)
    lock(r)
    p = lock_expect(r, 2)
    assert "already locked" in p.stderr


def test_unrelated_staged_work_is_not_committed(tmp_path):
    r = repo(tmp_path)
    (r / "notes.txt").write_text("mine\n")
    git(r, "add", "notes.txt")
    lock(r)
    assert "notes.txt" not in git(r, "log", "--name-only", "--format=", "-2")
    assert git(r, "diff", "--cached", "--name-only").strip() == "notes.txt"


def test_unlock_removes_only_its_own_rules(tmp_path):
    r = repo(tmp_path)
    (r / ".claude").mkdir()
    (r / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"deny": ["Read(/.env)"]}}))
    lock(r)
    run(r, "unlock", "--feature", "radid")
    assert settings(r)["permissions"]["deny"] == ["Read(/.env)"]
    assert receipt(r)["locks"] == []
    assert git(r, "log", "--format=%s", "-1").strip() == "chore(acceptance): unlock radid tests (user request)"


def test_two_locks_sharing_a_glob_keep_the_rule_until_both_are_unlocked(tmp_path):
    r = repo(tmp_path)
    lock(r, "one")
    (r / "Tests" / "Acceptance" / "test_c.py").write_text("def test_c():\n    pass\n")
    lock(r, "two")
    run(r, "unlock", "--feature", "one")
    assert "Edit(/Tests/Acceptance/**)" in settings(r)["permissions"]["deny"]
    run(r, "unlock", "--feature", "two")
    assert "permissions" not in settings(r)


def test_unlock_of_an_unknown_feature_is_two(tmp_path):
    r = repo(tmp_path)
    lock(r)
    p = run(r, "unlock", "--feature", "nope", expect=2)
    assert "nope" in p.stderr


def test_a_single_star_glob_also_matches_files(tmp_path):
    r = repo(tmp_path)
    lock(r, "radid", "Tests/Acceptance/*.py")
    assert receipt(r)["locks"][0]["files"] == ["Tests/Acceptance/test_a.py", "Tests/Acceptance/test_b.py"]
