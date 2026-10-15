import importlib.util, json, os, subprocess, sys
from pathlib import Path
import pytest
from work_state_fixtures import make_repo, add_origin, commit_file

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "work-state.py"

def load():
    spec = importlib.util.spec_from_file_location("work_state", SCRIPT)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

ws = load()

@pytest.mark.parametrize("text,want", [
    ("Installable: plugin\n", ("plugin", None)),
    ("Installable: macos-app Sing Replay\n", ("macos-app", "Sing Replay")),
    ("Installable: command ./check.sh --quick\n", ("command", "./check.sh --quick")),
    ("Installable: none\n", ("none", None)),
    ("no line here\n", None),
    ("Installable: macos-app\n", None),             # scheme missing -> invalid -> absent
    ("Installable: command\n", None),
    ("Installable: teleport\n", None),
    ("```\nInstallable: plugin\n```\n", None),       # inside a fence
    ("Installable: plugin\nInstallable: none\n", "conflict"),
    ("Installable: plugin\nInstallable: plugin\n", ("plugin", None)),
])
def test_parse_installable(text, want):
    assert ws.parse_installable(text) == want

def test_the_line_is_read_from_origin_main_not_from_a_branch(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "-c", "feat/x"], check=True)
    commit_file(repo, "CLAUDE.md", "Installable: plugin\n")
    assert ws.installable_at(repo, "origin/main") is None    # the branch cannot change it

def test_the_line_is_read_when_origin_main_has_it(tmp_path):
    repo = make_repo(tmp_path)
    commit_file(repo, "CLAUDE.md", "Installable: macos-app Sing Replay\n")
    add_origin(repo)
    assert ws.installable_at(repo, "origin/main") == ("macos-app", "Sing Replay")

def test_usage_errors_are_64():
    assert ws.main([]) == 64
    assert ws.main(["frobnicate"]) == 64


def test_committed_is_open_for_a_dirty_tree_and_names_the_files(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "scratch.txt").write_text("x")
    r = ws.measure_committed(repo)
    assert r["status"] == "open" and r["items"] == ["scratch.txt"]

def test_committed_ok_for_a_clean_tree(tmp_path):
    r = ws.measure_committed(make_repo(tmp_path))
    assert r["status"] == "ok" and r["items"] == []

def test_committed_looks_at_the_main_folder_too(tmp_path):
    repo = make_repo(tmp_path); wt = tmp_path / "other wt"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "feat/y", str(wt)], check=True)
    (repo / "dirty.txt").write_text("x")
    assert ws.measure_committed(wt)["status"] == "open"      # dirty in the primary, seen from the worktree

def test_pushed_ok_when_branch_and_main_match_origin(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    assert ws.measure_pushed(repo)["status"] == "ok"

def test_pushed_open_for_unpushed_commit_with_upstream_offers_git_push(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "-c", "feat/z"], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "-u", "origin", "feat/z"], check=True)
    commit_file(repo, "a.txt", "a")
    r = ws.measure_pushed(repo)
    assert r["status"] == "open"
    assert ["git", "-C", str(repo), "push"] in r["safe_actions"]

def test_pushed_never_offers_a_force_push(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "-c", "feat/z"], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "-u", "origin", "feat/z"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "--amend", "-m", "rewritten", "--allow-empty"], check=True)
    r = ws.measure_pushed(repo)
    assert r["safe_actions"] == [] and any("force" in a for a in r["ask"])

def test_pushed_without_origin_is_a_dash_not_a_tick(tmp_path):
    repo = make_repo(tmp_path)
    r = ws.measure_pushed(repo)
    assert r["status"] == "undefined" and "ingen fjern-repo" in r["detail"]

def test_pushed_with_unreachable_origin_is_unknown_with_the_reason(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", str(tmp_path / "gone")], check=True)
    r = ws.measure_pushed(repo)
    assert r["status"] == "unknown" and r["detail"]
