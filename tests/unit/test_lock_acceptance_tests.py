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
    assert settings(r)["permissions"]["deny"] == [
        "Edit(/Tests/Acceptance/**)", "Write(/Tests/Acceptance/**)",
        "Edit(/.gstack/acceptance-lock.json)", "Write(/.gstack/acceptance-lock.json)"]
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
    assert git(r, "log", "--format=%s", "-1").strip() == "chore(acceptance): unlock radid tests"


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


@pytest.mark.parametrize("body", ['{"locks": 5}', '{"locks": [1]}', '{"locks": [{"feature": "x"}]}'])
@pytest.mark.parametrize("cmd", ["lock", "verify", "unlock"])
def test_a_malformed_receipt_is_refused_with_two(tmp_path, body, cmd):
    r = repo(tmp_path)
    (r / ".gstack").mkdir()
    (r / ".gstack" / "acceptance-lock.json").write_text(body)
    before = git(r, "rev-parse", "HEAD")
    args = {"lock": ("lock", "--feature", "radid", "--path", "Tests/Acceptance/**"),
            "verify": ("verify",), "unlock": ("unlock", "--feature", "radid")}[cmd]
    p = run(r, *args, expect=2)
    assert "BLOCKED" in p.stderr and "malformed" in p.stderr
    assert git(r, "rev-parse", "HEAD") == before


def test_overlapping_locks_do_not_break_each_other(tmp_path):
    r = repo(tmp_path)
    lock(r, "one")
    (r / "Tests" / "Acceptance" / "test_c.py").write_text("def test_c():\n    pass\n")
    lock(r, "two")
    run(r, "verify")
    run(r, "verify", "--feature", "one")
    (r / "Tests" / "Acceptance" / "test_a.py").write_text("changed\n")
    p = run(r, "verify", expect=1)
    assert p.stdout.splitlines().count("CHANGED one Tests/Acceptance/test_a.py") == 1
    assert p.stdout.splitlines().count("CHANGED two Tests/Acceptance/test_a.py") == 1


def test_dotfiles_are_locked_and_verified(tmp_path):
    r = repo(tmp_path)
    h = r / "Tests" / "Acceptance" / ".hidden_test.py"
    h.write_text("x = 1\n")
    lock(r)
    assert "Tests/Acceptance/.hidden_test.py" in receipt(r)["locks"][0]["files"]
    h.write_text("x = 2\n")
    p = run(r, "verify", expect=1)
    assert "CHANGED radid Tests/Acceptance/.hidden_test.py" in p.stdout


def test_non_ascii_names_are_unquoted_and_stdout_is_pure(tmp_path):
    r = repo(tmp_path)
    f = r / "Tests" / "Acceptance" / "test_ø.py"
    f.write_text("x = 1\n")
    lock(r)
    f.write_text("x = 2\n")
    p = run(r, "verify", expect=1)
    assert p.stdout.splitlines() == ["CHANGED radid Tests/Acceptance/test_ø.py"]
    assert "Restore it" in p.stderr


def test_a_hand_edited_receipt_fails_verify_and_a_clean_one_passes(tmp_path):
    r = repo(tmp_path)
    lock(r)
    run(r, "verify")                                           # clean receipt: ok
    rc = r / ".gstack" / "acceptance-lock.json"
    data = json.loads(rc.read_text())
    data["locks"][0]["files"] = []                             # the cheat: forget the files
    rc.write_text(json.dumps(data, indent=2) + "\n")
    p = run(r, "verify", expect=1)                             # unstaged
    assert "CHANGED receipt .gstack/acceptance-lock.json" in p.stdout.splitlines()
    git(r, "add", "-f", str(rc))
    run(r, "verify", expect=1)                                 # staged
    git(r, "commit", "-q", "-m", "tamper")
    p = run(r, "verify", expect=1)                             # committed by hand: not this script's subject
    assert 'not by this script' in p.stdout and '"tamper"' in p.stdout


def test_an_uncommitted_receipt_fails_verify(tmp_path):
    r = repo(tmp_path)
    lock(r)
    git(r, "reset", "-q", "--hard", "HEAD~1")                  # receipt gone from HEAD...
    head = git(r, "rev-parse", "HEAD").strip()
    (r / ".gstack").mkdir(exist_ok=True)
    (r / ".gstack" / "acceptance-lock.json").write_text(
        json.dumps({"locks": [{"feature": "radid", "commit": head, "files": []}]}))
    p = run(r, "verify", expect=1)
    assert "CHANGED receipt" in p.stdout


def test_the_receipt_rules_are_kept_while_another_lock_remains(tmp_path):
    r = repo(tmp_path)
    lock(r, "one")
    (r / "Tests" / "Acceptance" / "test_c.py").write_text("def test_c():\n    pass\n")
    lock(r, "two")
    run(r, "unlock", "--feature", "one")
    deny = settings(r)["permissions"]["deny"]
    assert "Edit(/.gstack/acceptance-lock.json)" in deny and "Write(/.gstack/acceptance-lock.json)" in deny
    run(r, "unlock", "--feature", "two")
    assert "permissions" not in settings(r)


def test_a_failing_second_commit_names_the_recovery(tmp_path):
    r = repo(tmp_path)
    hook = r / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\ngit diff --cached --name-only | grep -q acceptance-lock && "
                    "{ echo 'hook says no' >&2; exit 1; }\nexit 0\n")
    hook.chmod(0o755)
    p = lock_expect(r, 2)
    test_commit = git(r, "rev-parse", "--short=12", "HEAD").strip()
    assert "BLOCKED — the test commit " + test_commit in p.stderr
    assert "hook says no" in p.stderr
    assert "git add -f" in p.stderr and "git reset --soft HEAD~1" in p.stderr


# --- final review wave 2: hardening ------------------------------------------------

def tamper_receipt(r: Path, mutate) -> None:
    rc = r / ".gstack" / "acceptance-lock.json"
    data = json.loads(rc.read_text())
    mutate(data["locks"][0])
    rc.write_text(json.dumps(data, indent=2) + "\n")


def test_an_option_shaped_commit_is_refused_and_writes_nothing(tmp_path):
    r = repo(tmp_path)
    lock(r)
    out = tmp_path / "x"
    tamper_receipt(r, lambda lk: lk.update(commit=f"--output={out}"))
    p = run(r, "verify", expect=2)
    assert "malformed" in p.stderr and not out.exists()


def test_a_non_hex_commit_is_refused(tmp_path):
    r = repo(tmp_path)
    lock(r)
    tamper_receipt(r, lambda lk: lk.update(commit="main"))
    p = run(r, "verify", expect=2)
    assert "malformed" in p.stderr


def test_an_unknown_commit_has_its_own_message(tmp_path):
    r = repo(tmp_path)
    lock(r)
    tamper_receipt(r, lambda lk: lk.update(commit="b" * 40))
    p = run(r, "verify", expect=2)
    assert f"lock commit {'b' * 12} for radid is not in this repository (squash-merged or rewritten?)" in p.stderr
    assert "ask the user whether to unlock/re-lock" in p.stderr


def test_repointing_the_receipt_at_head_after_editing_a_test_fails_verify(tmp_path):
    r = repo(tmp_path)
    lock(r)
    (r / "Tests" / "Acceptance" / "test_a.py").write_text("def test_a():\n    pass\n")
    git(r, "commit", "-q", "-am", "weaken")
    head = git(r, "rev-parse", "HEAD").strip()
    tamper_receipt(r, lambda lk: lk.update(commit=head))
    git(r, "commit", "-q", "-am", "chore(acceptance): not really")   # a faked subject passes this check...
    git(r, "commit", "-q", "--amend", "-m", "re-point")                # ...but an honest-looking hand commit does not
    p = run(r, "verify", expect=1)
    assert "not by this script" in p.stdout


def test_lock_unlock_lock_again_verifies(tmp_path):
    r = repo(tmp_path)
    lock(r)
    run(r, "unlock", "--feature", "radid")
    lock(r)
    run(r, "verify")


def test_a_new_file_under_a_locked_glob_fails_verify(tmp_path):
    r = repo(tmp_path)
    lock(r)
    (r / "Tests" / "Acceptance" / "conftest.py").write_text("collect_ignore_glob = ['*']\n")
    p = run(r, "verify", expect=1)
    assert "CHANGED radid Tests/Acceptance/conftest.py (new file under a locked path)" in p.stdout


def test_overlapping_locks_and_files_outside_every_glob_are_fine(tmp_path):
    r = repo(tmp_path)
    lock(r, "one")
    (r / "Tests" / "Acceptance" / "test_c.py").write_text("def test_c():\n    pass\n")
    lock(r, "two")
    (r / "src.py").write_text("x = 1\n")
    (r / "Tests" / "Acceptance" / "__pycache__").mkdir()
    (r / "Tests" / "Acceptance" / "__pycache__" / "a.pyc").write_text("x")
    run(r, "verify")


def test_a_symlinked_test_is_refused(tmp_path):
    r = repo(tmp_path)
    (r / "real.py").write_text("def test_r():\n    pass\n")
    (r / "Tests" / "Acceptance" / "test_link.py").symlink_to(r / "real.py")
    p = run(r, "lock", "--feature", "radid", "--path", "Tests/Acceptance/**", expect=2)
    assert "is a symlink; lock the real file" in p.stderr


def test_an_ignored_untracked_settings_file_is_not_committed(tmp_path):
    r = repo(tmp_path)
    (r / ".gitignore").write_text(".claude/\n")
    git(r, "add", ".gitignore")
    git(r, "commit", "-q", "-m", "ignore")
    p = lock(r)
    assert ".claude/settings.json is git-ignored, so the deny rules are local only and not committed" in p.stdout
    assert "Edit(/Tests/Acceptance/**)" in settings(r)["permissions"]["deny"]      # on disk
    assert git(r, "ls-files", ".claude/settings.json").strip() == ""
    assert git(r, "ls-files", ".gstack/acceptance-lock.json").strip() != ""        # the receipt is forced in
    run(r, "verify")


def test_a_tracked_or_unignored_settings_file_is_added_without_force(tmp_path):
    r = repo(tmp_path)
    p = lock(r)
    assert "git-ignored" not in p.stdout
    assert git(r, "ls-files", ".claude/settings.json").strip() != ""
    (tmp_path / "t").mkdir()
    r2 = repo(tmp_path / "t")
    (r2 / ".claude").mkdir()
    (r2 / ".claude" / "settings.json").write_text("{}\n")
    (r2 / ".gitignore").write_text(".claude/\n")
    git(r2, "add", "-f", ".claude/settings.json", ".gitignore")
    git(r2, "commit", "-q", "-m", "tracked")
    p = lock(r2)
    assert "git-ignored" not in p.stdout
    assert "Edit(/Tests/Acceptance/**)" in git(r2, "show", "HEAD:.claude/settings.json")


def test_an_assume_unchanged_flag_on_a_locked_file_fails_verify(tmp_path):
    r = repo(tmp_path)
    lock(r)
    git(r, "update-index", "--assume-unchanged", "Tests/Acceptance/test_a.py")
    p = run(r, "verify", expect=1)
    assert "CHANGED radid Tests/Acceptance/test_a.py (assume-unchanged/skip-worktree flag)" in p.stdout
    git(r, "update-index", "--no-assume-unchanged", "Tests/Acceptance/test_a.py")
    git(r, "update-index", "--skip-worktree", "Tests/Acceptance/test_a.py")
    run(r, "verify", expect=1)


# --- final review wave 3 ------------------------------------------------------------

def rebased_feature(tmp_path, weaken: bool = False):
    r = repo(tmp_path)
    git(r, "checkout", "-q", "-b", "feat")
    lock(r)
    lock_commit = receipt(r)["locks"][0]["commit"]
    git(r, "checkout", "-q", "main")
    (r / "other.txt").write_text("main moved\n")
    git(r, "add", "other.txt")
    git(r, "commit", "-q", "-m", "main moves")
    git(r, "checkout", "-q", "feat")
    git(r, "rebase", "-q", "main")
    assert subprocess.run(["git", "merge-base", "--is-ancestor", lock_commit, "HEAD"], cwd=r).returncode != 0
    if weaken:
        (r / "Tests" / "Acceptance" / "test_a.py").write_text("def test_a():\n    pass\n")
        git(r, "commit", "-q", "-am", "weaken")
    return r, lock_commit


def test_verify_survives_a_rebase_with_a_warning(tmp_path):
    r, lock_commit = rebased_feature(tmp_path)
    p = run(r, "verify")
    assert f"warning: lock commit {lock_commit[:12]} for radid is not in this branch's history" in p.stderr
    assert "ask the user to re-lock" in p.stderr


def test_verify_after_a_rebase_still_catches_a_weakened_test(tmp_path):
    r, _ = rebased_feature(tmp_path, weaken=True)
    p = run(r, "verify", expect=1)
    assert "CHANGED radid Tests/Acceptance/test_a.py" in p.stdout
    assert "git checkout <lock commit> -- <file>" in p.stderr


def test_each_failure_class_has_its_own_advice(tmp_path):
    r = repo(tmp_path)
    lock(r)
    f = r / "Tests" / "Acceptance" / "test_a.py"
    (r / "Tests" / "Acceptance" / "conftest.py").write_text("x = 1\n")
    git(r, "update-index", "--assume-unchanged", "Tests/Acceptance/test_a.py")
    tamper_receipt(r, lambda lk: lk.update(locked_at="x"))
    p = run(r, "verify", expect=1)
    assert "restore the receipt as the script wrote it" in p.stderr
    assert "remove the file, or ask the user to unlock and re-lock" in p.stderr
    assert "A locked file or the receipt carries an assume-unchanged/skip-worktree flag" in p.stderr
    assert "git update-index --no-assume-unchanged --no-skip-worktree" in p.stderr
    f.write_text("changed\n")
    git(r, "update-index", "--no-assume-unchanged", "Tests/Acceptance/test_a.py")
    assert "Restore it" in run(r, "verify", expect=1).stderr


def test_a_receipt_hidden_by_assume_unchanged_is_still_detected(tmp_path):
    r = repo(tmp_path)
    lock(r)
    git(r, "update-index", "--assume-unchanged", ".gstack/acceptance-lock.json")
    tamper_receipt(r, lambda lk: lk.update(files=[], paths=[]))
    (r / "Tests" / "Acceptance" / "test_a.py").write_text("def test_a():\n    pass\n")
    p = run(r, "verify", expect=1)
    assert "CHANGED receipt .gstack/acceptance-lock.json" in p.stdout


def test_a_staged_modification_is_caught_after_the_working_copy_is_restored(tmp_path):
    r = repo(tmp_path)
    lock(r)
    f = r / "Tests" / "Acceptance" / "test_a.py"
    original = f.read_text()
    f.write_text("def test_a():\n    pass\n")
    git(r, "add", str(f))
    f.write_text(original)
    p = run(r, "verify", expect=1)
    assert "CHANGED radid Tests/Acceptance/test_a.py" in p.stdout


def test_a_committed_modification_is_caught_after_the_working_copy_is_restored(tmp_path):
    r = repo(tmp_path)
    lock(r)
    f = r / "Tests" / "Acceptance" / "test_a.py"
    original = f.read_text()
    f.write_text("def test_a():\n    pass\n")
    git(r, "commit", "-q", "-am", "weaken")
    f.write_text(original)
    p = run(r, "verify", expect=1)
    assert "CHANGED radid Tests/Acceptance/test_a.py" in p.stdout


def test_an_ignored_new_file_is_flagged_but_caches_are_not(tmp_path):
    r = repo(tmp_path)
    lock(r)
    (r / ".git" / "info" / "exclude").write_text("conftest.py\n")
    (r / "Tests" / "Acceptance" / "conftest.py").write_text("collect_ignore_glob = ['*']\n")
    (r / "Tests" / "Acceptance" / "__pycache__").mkdir()
    (r / "Tests" / "Acceptance" / "__pycache__" / "x.pyc").write_text("x")
    (r / "Tests" / "Acceptance" / ".pytest_cache").mkdir()
    (r / "Tests" / "Acceptance" / ".pytest_cache" / "v").write_text("x")
    (r / "Tests" / "Acceptance" / ".DS_Store").write_text("x")
    (r / "Tests" / "Acceptance" / "stray.pyc").write_text("x")
    p = run(r, "verify", expect=1)
    assert sorted(p.stdout.splitlines()) == [
        "CHANGED radid Tests/Acceptance/conftest.py (new file under a locked path)",
        "CHANGED radid Tests/Acceptance/stray.pyc (new file under a locked path)"]
