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


def test_pushed_unborn_head_is_unknown_not_ok(tmp_path):
    repo = tmp_path / "my proj"; repo.mkdir()
    origin = tmp_path / "origin dir"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(origin)], check=True)
    r = ws.measure_pushed(repo)
    assert r["status"] == "unknown" and "kunne ikke telle" in r["detail"]

def test_pushed_on_main_ahead_is_ask_only_and_listed_once(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    commit_file(repo, "a.txt", "a")
    r = ws.measure_pushed(repo)
    assert r["status"] == "open" and r["safe_actions"] == []
    assert len(r["ask"]) == 1 and len(r["items"]) == 1


# --- measure_tidy: mapper ryddet ---------------------------------------------------------
# `wt -C <main> remove <branch>` names the branch, not the folder, so a removal is
# recognised by the branch (or by the folder in the no-`wt` fallback).

def make_landed_branch(repo, name="feat/done"):
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    git("switch", "-q", "-c", name); commit_file(repo, f"{name.replace('/', '_')}.txt", "x")
    git("switch", "-q", "main"); git("merge", "-q", "--ff-only", name); git("push", "-q", "origin", "main")

def removes(r, wt, branch):
    return any(str(wt) in " ".join(a) or branch in a for a in r["safe_actions"])

def test_a_landed_branch_with_a_commit_is_deleted_with_dash_d(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo); make_landed_branch(repo)
    r = ws.measure_tidy(repo)
    assert ["git", "-C", str(repo), "branch", "-d", "feat/done"] in r["safe_actions"]

def test_a_branch_made_seconds_ago_from_main_is_not_proven_landed(tmp_path):    # Review Focus 3
    repo = make_repo(tmp_path); add_origin(repo)
    subprocess.run(["git", "-C", str(repo), "branch", "feat/fresh"], check=True)
    r = ws.measure_tidy(repo)
    assert not any("feat/fresh" in " ".join(a) for a in r["safe_actions"])
    assert any("feat/fresh" in a for a in r["ask"])

def test_a_squash_merged_branch_is_asked_about_never_deleted(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    g("switch", "-q", "-c", "feat/sq"); commit_file(repo, "s.txt", "s"); g("switch", "-q", "main")
    g("merge", "-q", "--squash", "feat/sq"); g("commit", "-q", "-m", "squash"); g("push", "-q", "origin", "main")
    r = ws.measure_tidy(repo)
    assert not any("-D" in a for a in r["safe_actions"])
    assert any("feat/sq" in a for a in r["ask"])

def test_a_clean_landed_worktree_is_removed_but_not_the_one_the_session_stands_in(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo); wt = tmp_path / "wt done"
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    g("worktree", "add", "-q", "-b", "feat/w", str(wt)); commit_file(wt, "w.txt", "w")
    g("merge", "-q", "--ff-only", "feat/w"); g("push", "-q", "origin", "main")
    assert removes(ws.measure_tidy(repo), wt, "feat/w")
    assert not removes(ws.measure_tidy(wt), wt, "feat/w")   # standing in it

def test_ignored_non_cache_files_keep_a_worktree_in_ask(tmp_path):              # Review Focus 4
    repo = make_repo(tmp_path); add_origin(repo); wt = tmp_path / "wt env"
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    commit_file(repo, ".gitignore", ".env\n"); g("push", "-q", "origin", "main")
    g("worktree", "add", "-q", "-b", "feat/e", str(wt)); commit_file(wt, "e.txt", "e")
    g("merge", "-q", "--ff-only", "feat/e"); g("push", "-q", "origin", "main")
    (wt / ".env").write_text("SECRET=1")
    r = ws.measure_tidy(repo)
    assert not removes(r, wt, "feat/e") and any(str(wt) in a for a in r["ask"])

def test_only_cache_content_counts_as_clean(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo); wt = tmp_path / "wt cache"
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    commit_file(repo, ".gitignore", "node_modules/\n"); g("push", "-q", "origin", "main")
    g("worktree", "add", "-q", "-b", "feat/c", str(wt)); commit_file(wt, "c.txt", "c")
    g("merge", "-q", "--ff-only", "feat/c"); g("push", "-q", "origin", "main")
    (wt / "node_modules").mkdir(); (wt / "node_modules" / "x.js").write_text("1")
    assert removes(ws.measure_tidy(repo), wt, "feat/c")

def test_a_leftover_sibling_folder_with_other_content_is_asked_about(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    left = tmp_path / "my proj.old"; left.mkdir(); (left / "notes.md").write_text("keep me")
    r = ws.measure_tidy(repo)
    assert any(str(left) in a for a in r["ask"]) and not any(str(left) in " ".join(a) for a in r["safe_actions"])

def test_a_cache_only_sibling_goes_to_the_trash_never_rm(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    left = tmp_path / "my proj.cache"; (left / "node_modules").mkdir(parents=True); (left / "node_modules" / "a.js").write_text("1")
    acts = ws.measure_tidy(repo)["safe_actions"]
    assert [a for a in acts if str(left) in " ".join(a)] == [["osascript", "-e", "on run argv", "-e",
                     'tell application "Finder" to delete (POSIX file (item 1 of argv))', "-e", "end run", str(left)]]

def test_a_worktree_in_use_is_asked_about(tmp_path, monkeypatch):
    repo = make_repo(tmp_path); add_origin(repo); wt = tmp_path / "wt busy"
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    g("worktree", "add", "-q", "-b", "feat/b", str(wt)); commit_file(wt, "b.txt", "b")
    g("merge", "-q", "--ff-only", "feat/b"); g("push", "-q", "origin", "main")
    monkeypatch.setattr(ws, "_cwds", lambda: [str(wt / "sub")])
    r = ws.measure_tidy(repo)
    assert not removes(r, wt, "feat/b") and any(str(wt) in a and "i bruk" in a for a in r["ask"])

def test_a_failed_git_measurement_is_unknown_not_clean(tmp_path):
    r = ws.measure_tidy(tmp_path / "not a repo")
    assert r["status"] == "unknown" and r["safe_actions"] == [] and r["ask"] == []

def test_nothing_left_is_ok_and_leftovers_are_open(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    assert ws.measure_tidy(repo)["status"] == "ok"
    subprocess.run(["git", "-C", str(repo), "branch", "feat/fresh"], check=True)
    assert ws.measure_tidy(repo)["status"] == "open"

def test_in_use_matches_whole_path_components_only(monkeypatch):
    monkeypatch.setattr(ws, "_cwds", lambda: ["/a/bc/sub"])
    assert ws.in_use(Path("/a/b")) is False and ws.in_use(Path("/a/bc")) is True


# --- review round 1: fixes ---------------------------------------------------------------

def landed_worktree(tmp_path, name="wt x", branch="feat/x"):
    repo = make_repo(tmp_path); add_origin(repo); wt = tmp_path / name
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    g("worktree", "add", "-q", "-b", branch, str(wt)); commit_file(wt, "x.txt", "x")
    g("merge", "-q", "--ff-only", branch); g("push", "-q", "origin", "main")
    return repo, wt, g

def test_untracked_work_is_seen_even_when_status_hides_untracked_files(tmp_path):
    repo, wt, g = landed_worktree(tmp_path)
    g("config", "status.showUntrackedFiles", "no")
    (wt / "precious.txt").write_text("work")
    r = ws.measure_tidy(repo)
    assert not removes(r, wt, "feat/x") and any(str(wt) in a for a in r["ask"])

def test_the_trash_action_passes_the_path_as_an_argument(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    left = tmp_path / 'my proj.q"uote'; (left / "node_modules").mkdir(parents=True); (left / "node_modules" / "a.js").write_text("1")
    acts = [a for a in ws.measure_tidy(repo)["safe_actions"] if str(left) in " ".join(a)]
    assert acts == [["osascript", "-e", "on run argv", "-e",
                     'tell application "Finder" to delete (POSIX file (item 1 of argv))', "-e", "end run", str(left)]]

def test_an_unreadable_sibling_is_not_taken_for_cache_only(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    left = tmp_path / "my proj.locked"; sub = left / "secret"; sub.mkdir(parents=True); (sub / "f.txt").write_text("1")
    sub.chmod(0)
    try:
        r = ws.measure_tidy(repo)
    finally:
        sub.chmod(0o755)
    assert not any(str(left) in " ".join(a) for a in r["safe_actions"])
    assert r["status"] in ("unknown", "open")

def test_lsof_with_no_output_is_a_failed_measurement(monkeypatch):
    monkeypatch.setattr(ws.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", ""))
    with pytest.raises(Exception):
        ws.in_use(Path("/a/b"))

def test_a_prunable_worktree_is_asked_about_and_does_not_make_the_measure_unknown(tmp_path):
    import shutil
    repo, wt, g = landed_worktree(tmp_path)
    shutil.rmtree(wt)
    r = ws.measure_tidy(repo)
    assert r["status"] == "open" and any(f"git -C {repo} worktree prune" in a for a in r["ask"])
    assert not removes(r, wt, "feat/x")

def test_a_locked_worktree_is_never_removed(tmp_path):
    repo, wt, g = landed_worktree(tmp_path)
    g("worktree", "lock", str(wt))
    r = ws.measure_tidy(repo)
    assert not removes(r, wt, "feat/x") and any(str(wt) in a and "låst" in a for a in r["ask"])

def test_a_symlinked_sibling_goes_to_ask(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    target = tmp_path / "elsewhere"; (target / "node_modules").mkdir(parents=True)
    link = tmp_path / "my proj.link"; link.symlink_to(target)
    r = ws.measure_tidy(repo)
    assert not any(str(link) in " ".join(a) for a in r["safe_actions"]) and any(str(link) in a for a in r["ask"])

def test_without_wt_the_fallback_is_worktree_remove_then_branch_d(tmp_path, monkeypatch):
    repo, wt, g = landed_worktree(tmp_path)
    monkeypatch.setattr(ws.shutil, "which", lambda name: None)
    acts = ws.measure_tidy(repo)["safe_actions"]
    assert acts == [["git", "-C", str(repo), "worktree", "remove", str(wt)],
                    ["git", "-C", str(repo), "branch", "-d", "feat/x"]]

def test_the_session_worktree_with_a_landed_branch_is_listed_in_ask_not_removed(tmp_path):
    repo, wt, g = landed_worktree(tmp_path)
    r = ws.measure_tidy(wt)
    assert not removes(r, wt, "feat/x") and any("ExitWorktree" in a and "feat/x" in a for a in r["ask"])
