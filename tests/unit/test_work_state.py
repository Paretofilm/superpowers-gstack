import fcntl, importlib.util, json, os, plistlib, subprocess, sys
from pathlib import Path
import pytest
from work_state_fixtures import make_repo, add_origin, commit_file, stub_bin, stub_env, write_app

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


# ---- Task 4: report ----

def run_report(repo, *extra):
    p = subprocess.run([sys.executable, str(SCRIPT), "report", "--repo", str(repo), *extra],
                       capture_output=True, text=True)
    return p.returncode, p.stdout.strip().splitlines()

def test_a_clean_pushed_repo_with_no_line_reports_undefined_and_exit_0_or_1_by_rule(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    code, lines = run_report(repo)
    last = json.loads(lines[-1])
    assert code == 0          # R9: undefined does not nag; the JSON status carries the truth
    assert last["installable"]["status"] == "undefined"
    assert "installerbar: ikke definert, kjør /adapt" in last["line"]
    assert lines[0].startswith("Tilstand:")

def test_installable_line_only_inside_a_fence_is_undefined(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "```\nInstallable: plugin\n```\n"); add_origin(repo)
    assert json.loads(run_report(repo)[1][-1])["installable"]["status"] == "undefined"

def test_installable_line_only_on_a_branch_is_undefined(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "-c", "feat/x"], check=True)
    commit_file(repo, "CLAUDE.md", "Installable: none\n")
    assert json.loads(run_report(repo)[1][-1])["installable"]["status"] == "undefined"

def test_an_unexpected_exception_still_ends_with_a_json_object(tmp_path, monkeypatch, capsys):
    repo = make_repo(tmp_path); add_origin(repo)
    def boom(parts): raise RuntimeError("kaboom")
    monkeypatch.setattr(ws, "build_line", boom)
    assert ws.main(["report", "--repo", str(repo)]) == 1
    last = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert "kaboom" in last["error"] and "line" in last

def test_remote_without_origin_main_is_never_ok_for_a_plugin(tmp_path, monkeypatch):
    repo = _plugin_repo(tmp_path)
    run_git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    run_git("update-ref", "-d", "refs/remotes/origin/main")
    monkeypatch.setenv("PATH", f"{stub_bin(tmp_path, claude='exit 0')}:{os.environ['PATH']}")
    r = ws.measure_installable(repo)
    assert r["status"] == "open" and "main er ikke pushet" in r["detail"]

def test_a_corrupt_plugin_registry_is_not_reported_as_not_installed(tmp_path, monkeypatch):
    repo = _plugin_repo(tmp_path)
    reg = tmp_path / "home" / ".claude" / "plugins"; reg.mkdir(parents=True)
    (reg / "installed_plugins.json").write_text("{broken")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PATH", f"{stub_bin(tmp_path, claude='exit 0')}:{os.environ['PATH']}")
    d = ws.measure_installable(repo)["detail"]
    assert "kunne ikke leses" in d and "ikke installert" not in d

def test_unreadable_info_plist_is_unknown_and_a_different_bundle_id_is_stale(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: macos-app App\n"); add_origin(repo)
    head = _rev(repo, "origin/main")
    stamp_file = ws.gitdir(repo) / "gstack-installed-app.json"
    app = _app(tmp_path, "other.id")
    stamp_file.write_text(json.dumps(_stamp(app, head)))
    assert ws.measure_installable(repo)["status"] == "stale"
    (app / "Contents" / "Info.plist").write_text("not a plist")
    r = ws.measure_installable(repo)
    assert r["status"] == "unknown" and r["safe_actions"] == []
    (app / "Contents" / "Info.plist").unlink()
    assert ws.measure_installable(repo)["status"] == "unknown"

def test_all_green_is_exit_0_and_a_tick_per_part(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "# p\nInstallable: none\n"); add_origin(repo)
    code, lines = run_report(repo)
    assert code == 0
    assert "committet ✓" in lines[0] and "pushet ✓" in lines[0] and "mapper ryddet ✓" in lines[0]

def test_never_a_tick_when_something_is_left(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: none\n"); add_origin(repo)
    (repo / "x.txt").write_text("x")
    code, lines = run_report(repo)
    assert code == 1 and "committet ✓" not in lines[0] and "committet ✗" in lines[0]

def test_conflicting_installable_lines_read_as_undefined(tmp_path):             # Review Focus 2
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: plugin\nInstallable: none\n"); add_origin(repo)
    assert json.loads(run_report(repo)[1][-1])["installable"]["status"] == "undefined"

def test_not_a_git_repo_is_exit_2(tmp_path):
    (tmp_path / "plain").mkdir()
    assert run_report(tmp_path / "plain")[0] == 2

def test_bad_usage_is_exit_64(tmp_path):
    assert run_report(tmp_path, "--bogus")[0] == 64

def test_a_stored_stop_code_is_shown_under_ask_until_a_run_succeeds(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: macos-app App\n"); add_origin(repo)
    (ws.gitdir(repo) / "gstack-install-result.json").write_text(json.dumps({"code": 4, "reason": "App is running", "commit": "abc"}))
    ask = json.loads(run_report(repo)[1][-1])["ask"]
    assert any("App is running" in a for a in ask)

def test_a_corrupt_result_file_is_an_ask_not_a_crash(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: macos-app App\n"); add_origin(repo)
    (ws.gitdir(repo) / "gstack-install-result.json").write_text("{not json")
    code, lines = run_report(repo)
    assert code == 1 and json.loads(lines[-1])["ask"]

def test_json_only_prints_just_the_object(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: none\n"); add_origin(repo)
    code, lines = run_report(repo, "--json-only")
    assert len(lines) == 1 and json.loads(lines[0])["line"].startswith("Tilstand:")

def test_plugin_kind_reads_installed_version_when_the_registry_exists(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    commit_file(repo, "CLAUDE.md", "Installable: plugin\n")
    commit_file(repo, ".claude-plugin/plugin.json", '{"name": "demo", "version": "3.15.0"}\n')
    commit_file(repo, "CHANGELOG.md", "# Changelog\n\n## [3.15.0] - 2026-10-20\n")
    add_origin(repo)
    reg = tmp_path / "home" / ".claude" / "plugins"; reg.mkdir(parents=True)
    (reg / "installed_plugins.json").write_text(json.dumps({"plugins": {"demo@m": [{"version": "3.14.0"}]}}))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PATH", f"{stub_bin(tmp_path, claude='exit 0')}:{os.environ['PATH']}")
    assert "3.15.0 på main, du har 3.14.0" in ws.measure_installable(repo)["detail"]

def _plugin_repo(tmp_path, changelog="# Changelog\n\n## [3.15.0] - 2026-10-20\n"):
    repo = make_repo(tmp_path)
    commit_file(repo, "CLAUDE.md", "Installable: plugin\n")
    commit_file(repo, ".claude-plugin/plugin.json", '{"name": "demo", "version": "3.15.0"}\n')
    commit_file(repo, "CHANGELOG.md", changelog)
    add_origin(repo)
    return repo

def test_plugin_validation_failure_is_open(tmp_path, monkeypatch):
    repo = _plugin_repo(tmp_path)
    monkeypatch.setenv("PATH", f"{stub_bin(tmp_path, claude='echo bad manifest; exit 1')}:{os.environ['PATH']}")
    r = ws.measure_installable(repo)
    assert r["status"] == "open" and "bad manifest" in r["detail"]

def test_plugin_without_a_changelog_entry_is_open(tmp_path, monkeypatch):
    repo = _plugin_repo(tmp_path, "# Changelog\n")
    monkeypatch.setenv("PATH", f"{stub_bin(tmp_path, claude='exit 0')}:{os.environ['PATH']}")
    assert ws.measure_installable(repo)["status"] == "open"

def test_plugin_without_claude_on_path_is_unknown(tmp_path, monkeypatch):
    repo = _plugin_repo(tmp_path)
    monkeypatch.setenv("PATH", str(stub_bin(tmp_path, git='exec /usr/bin/git "$@"')))
    r = ws.measure_installable(repo)
    assert r["status"] == "unknown" and "claude ikke funnet" in r["detail"]

def test_command_kind_exit_code_decides(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: command exit 0\n"); add_origin(repo)
    assert ws.measure_installable(repo)["status"] == "ok"
    commit_file(repo, "CLAUDE.md", "Installable: command echo nope; exit 3\n")
    subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", "main"], check=True)
    r = ws.measure_installable(repo)
    assert r["status"] == "open" and "nope" in r["detail"]

def _app(tmp_path, bundle_id="com.example.app"):
    app = tmp_path / "Apps dir" / "My App.app"
    (app / "Contents").mkdir(parents=True, exist_ok=True)
    with open(app / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump({"CFBundleIdentifier": bundle_id}, f, fmt=plistlib.FMT_BINARY)
    return app

def _stamp(app, commit):
    return {"scheme": "App", "bundle_id": "com.example.app", "commit": commit,
            "app_path": str(app), "version": "1", "installed_at": "2026-10-15T10:00:00Z"}

def _rev(repo, rev):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", rev], capture_output=True, text=True).stdout.strip()

def test_stamp_is_current_checks_commit_path_and_bundle_id(tmp_path):
    repo = make_repo(tmp_path); head = _rev(repo, "HEAD")
    app = _app(tmp_path)
    assert ws.stamp_is_current(repo, _stamp(app, head), head)
    assert not ws.stamp_is_current(repo, _stamp(app, "0" * 40), head)
    assert not ws.stamp_is_current(repo, _stamp(tmp_path / "gone.app", head), head)
    assert not ws.stamp_is_current(repo, {**_stamp(app, head), "bundle_id": "other.id"}, head)
    assert not ws.stamp_is_current(repo, {"commit": head}, head)

def test_macos_app_ok_stale_and_corrupt_stamp(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: macos-app App\n"); add_origin(repo)
    head = _rev(repo, "origin/main")
    stamp_file = ws.gitdir(repo) / "gstack-installed-app.json"
    r = ws.measure_installable(repo)
    assert r["status"] == "stale" and r["safe_actions"][0][-2:] == ["--repo", str(repo)]
    stamp_file.write_text(json.dumps(_stamp(_app(tmp_path), head)))
    assert ws.measure_installable(repo)["status"] == "ok"
    stamp_file.write_text(json.dumps(_stamp(_app(tmp_path), "0" * 40)))
    assert ws.measure_installable(repo)["status"] == "stale"
    stamp_file.write_text("{broken")
    assert ws.measure_installable(repo)["status"] == "unknown"

def test_stub_helpers_make_a_logging_stub_dir(tmp_path):
    d = stub_bin(tmp_path, tool="echo hi")
    env = {**os.environ, **stub_env(tmp_path)}
    assert subprocess.run([str(d / "tool"), "a", "b"], env=env, capture_output=True, text=True).stdout == "hi\n"
    assert "tool a b" in Path(env["STUB_LOG"]).read_text()
    assert not (d / "other").exists()


# ---- Task 5: install — preconditions, discovery, the four questions, the lock ----
# Until Task 6 builds and swaps, a run that passes every question stops at 70 "not implemented".
# Ruling R8: fake apps carry a real Contents/Info.plist (write_app); there is no plutil stub.

PASSED = 70

def run_install(repo, stubs, apps, *extra, env_extra=None):
    env = {**os.environ, **stub_env(apps.parent), "PATH": f"{stubs}:{os.environ['PATH']}", **(env_extra or {})}
    p = subprocess.run([sys.executable, str(SCRIPT), "install", "--repo", str(repo),
                        "--applications-dir", str(apps), *extra], capture_output=True, text=True, env=env)
    return p.returncode, json.loads(p.stdout.strip().splitlines()[-1])

def app_repo(tmp_path, line="Installable: macos-app Fake App\n"):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", line); add_origin(repo)
    return repo

def passed(code, out):
    return code == PASSED and out["reason"] == "not implemented"

def stamp_at(repo, apps, commit):
    (ws.gitdir(repo) / "gstack-installed-app.json").write_text(json.dumps(
        {"scheme": "Fake App", "bundle_id": "com.example.fake", "commit": commit, "app_path": str(apps / "Fake App.app"),
         "version": "1", "installed_at": "2026-10-01T00:00:00Z"}))

def push(repo):
    subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", "main"], check=True)

def test_code_2_when_the_line_is_not_macos_app(tmp_path):
    repo = app_repo(tmp_path, "Installable: plugin\n")
    assert run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")[0] == 2

def test_code_3_when_the_main_folder_is_on_another_branch(tmp_path):
    repo = app_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "-c", "feat/q"], check=True)
    assert run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")[0] == 3

def test_code_3_when_the_main_folder_is_dirty_but_ignored_files_are_fine(tmp_path):
    repo = app_repo(tmp_path); commit_file(repo, ".gitignore", "local.cfg\n")
    push(repo)                                     # adapted: local main must equal origin/main
    (repo / "local.cfg").write_text("x")
    (repo / "tracked.txt").write_text("y"); subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    assert run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")[0] == 3
    subprocess.run(["git", "-C", str(repo), "reset", "-q", "tracked.txt"], check=True); (repo / "tracked.txt").unlink()
    assert passed(*run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir"))   # brief: != 3

def test_code_3_for_untracked_files_that_are_not_ignored(tmp_path):
    repo = app_repo(tmp_path)
    (repo / "Extra.swift").write_text("// would be compiled into the build\n")
    assert run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")[0] == 3

def test_code_3_when_local_main_has_commits_origin_lacks(tmp_path):
    repo = app_repo(tmp_path); commit_file(repo, "notes.txt", "unpushed\n")
    code, out = run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")
    assert code == 3 and "pushet" in out["reason"]

def test_the_pull_brings_main_up_to_origin(tmp_path):
    repo = app_repo(tmp_path); origin = tmp_path / "origin dir"
    other = tmp_path / "other clone"
    subprocess.run(["git", "clone", "-q", str(origin), str(other)], check=True)
    subprocess.run(["git", "-C", str(other), "-c", "user.name=T", "-c", "user.email=t@e", "-c", "commit.gpgsign=false", "commit", "-q",
                    "--allow-empty", "-m", "landed elsewhere"], check=True)
    subprocess.run(["git", "-C", str(other), "push", "-q", "origin", "main"], check=True)
    code, out = run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")
    assert passed(code, out)
    assert out["commit"] == _rev(other, "HEAD") == _rev(repo, "HEAD")

def test_code_4_when_the_app_runs_and_only_an_exact_path_match_counts(tmp_path):   # Review Focus 5
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    app = apps / "Fake App.app"
    exe = f"{app}/Contents/MacOS/Fake"
    stubs = stub_bin(tmp_path, ps=f'echo "123 {exe}"')
    assert run_install(repo, stubs, apps)[0] == 4
    stubs = stub_bin(tmp_path, ps=f'echo "123 {exe}-helper"')       # prefix is not a match
    assert passed(*run_install(repo, stubs, apps))

def test_quit_running_asks_the_app_to_quit_and_never_kills(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    env = stub_env(tmp_path); ps_file = Path(env["STUB_PS_FILE"])
    ps_file.write_text(f"123 {apps}/Fake App.app/Contents/MacOS/Fake\n")
    code, out = run_install(repo, stub_bin(tmp_path), apps, "--quit-running", "--replace-unstamped")
    log = Path(env["STUB_LOG"]).read_text()
    assert passed(code, out) and "to quit" in log and "kill" not in log and not ps_file.exists()
    assert 'tell application id "com.example.fake" to quit' in log

def test_the_app_is_not_quit_when_a_later_question_stops(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    env = stub_env(tmp_path); ps_file = Path(env["STUB_PS_FILE"])
    ps_file.write_text(f"123 {apps}/Fake App.app/Contents/MacOS/Fake\n")
    code, _ = run_install(repo, stub_bin(tmp_path), apps, "--quit-running")      # unstamped copy: 6
    assert code == 6 and ps_file.exists() and "osascript" not in Path(env["STUB_LOG"]).read_text()

def test_code_4_again_when_the_app_will_not_quit_within_the_deadline(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    env = stub_env(tmp_path); Path(env["STUB_PS_FILE"]).write_text(f"123 {apps}/Fake App.app/Contents/MacOS/Fake\n")
    stubs = stub_bin(tmp_path, osascript="exit 0")                 # asks, but never quits
    code, _ = run_install(repo, stubs, apps, "--quit-running", env_extra={"GSTACK_QUIT_DEADLINE": "1"})
    assert code == 4 and "kill" not in Path(env["STUB_LOG"]).read_text()

def test_quit_path_only_accepts_instances_inside_that_bundle(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    branch_app = tmp_path / "DerivedData dir" / "Fake App.app"
    env = stub_env(tmp_path)
    Path(env["STUB_PS_FILE"]).write_text(f"1 {branch_app}/Contents/MacOS/Fake\n2 {apps}/Fake App.app/Contents/MacOS/Fake\n")
    code, _ = run_install(repo, stub_bin(tmp_path), apps, "--quit-path", str(branch_app))
    assert code == 4                                               # the /Applications copy also runs
    assert "to quit" not in Path(env["STUB_LOG"]).read_text()

def test_quit_path_quits_the_branch_build_when_it_is_the_only_instance(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    branch_app = write_app(tmp_path / "DerivedData dir" / "Fake App.app")
    env = stub_env(tmp_path); ps_file = Path(env["STUB_PS_FILE"])
    ps_file.write_text(f"1 {branch_app}/Contents/MacOS/Fake\n")
    code, out = run_install(repo, stub_bin(tmp_path), apps, "--quit-path", str(branch_app))
    assert passed(code, out) and not ps_file.exists() and "to quit" in Path(env["STUB_LOG"]).read_text()

def test_quit_path_with_another_bundle_id_is_refused(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    branch_app = write_app(tmp_path / "DerivedData dir" / "Fake App.app", "com.other.app")
    env = stub_env(tmp_path); Path(env["STUB_PS_FILE"]).write_text(f"1 {branch_app}/Contents/MacOS/Fake\n")
    code, _ = run_install(repo, stub_bin(tmp_path), apps, "--quit-path", str(branch_app))
    assert code == 64 and "to quit" not in Path(env["STUB_LOG"]).read_text()

def test_no_quit_is_sent_when_nothing_runs(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    env = stub_env(tmp_path)
    assert passed(*run_install(repo, stub_bin(tmp_path), apps, "--quit-running"))
    assert "osascript" not in Path(env["STUB_LOG"]).read_text()

def test_a_failing_ps_is_never_read_as_not_running(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    code, out = run_install(repo, stub_bin(tmp_path, ps="exit 1"), apps)
    assert code == 70 and out["reason"] != "not implemented"

def test_code_5_when_the_span_since_the_stamp_has_a_migration_signal(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    stamp_at(repo, apps, _rev(repo, "HEAD"))
    write_app(apps / "Fake App.app")
    commit_file(repo, "Sources/Migrations/0002_add_column.sql", "ALTER TABLE t ADD COLUMN c INT;\n")
    push(repo)
    assert run_install(repo, stub_bin(tmp_path), apps)[0] == 5
    assert passed(*run_install(repo, stub_bin(tmp_path), apps, "--accept-migration"))

def test_a_span_without_a_migration_signal_passes(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    stamp_at(repo, apps, _rev(repo, "HEAD")); write_app(apps / "Fake App.app")
    commit_file(repo, "Sources/View.swift", "struct V {}\n"); push(repo)
    assert passed(*run_install(repo, stub_bin(tmp_path), apps))

def test_code_5_when_the_stamped_commit_no_longer_exists_in_history(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir(); write_app(apps / "Fake App.app")
    stamp_at(repo, apps, "0" * 40)
    assert run_install(repo, stub_bin(tmp_path), apps)[0] == 5

def test_code_5_when_the_stamp_is_corrupt(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir(); write_app(apps / "Fake App.app")
    (ws.gitdir(repo) / "gstack-installed-app.json").write_text("{broken")
    assert run_install(repo, stub_bin(tmp_path), apps)[0] == 5

def test_a_classifier_that_cannot_run_counts_as_a_migration_signal(tmp_path, monkeypatch):
    repo = app_repo(tmp_path); base = _rev(repo, "HEAD")
    commit_file(repo, "Sources/View.swift", "struct V {}\n")
    monkeypatch.setattr(ws, "CLASSIFY", tmp_path / "missing classify.py")
    signal, reason = ws.migration_signal(repo, base, _rev(repo, "HEAD"))
    assert signal and reason

def test_code_6_for_an_unstamped_copy_and_replace_unstamped_clears_it(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    assert run_install(repo, stub_bin(tmp_path), apps)[0] == 6
    assert passed(*run_install(repo, stub_bin(tmp_path), apps, "--replace-unstamped"))

def test_code_7_for_a_copy_with_another_bundle_id_and_no_flag_helps(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"
    write_app(apps / "Fake App.app", "com.other.app")
    for flags in ([], ["--replace-unstamped"], ["--accept-migration"], ["--quit-running"]):
        assert run_install(repo, stub_bin(tmp_path), apps, *flags)[0] == 7

def test_code_7_when_the_copy_cannot_be_identified(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; (apps / "Fake App.app").mkdir(parents=True)
    assert run_install(repo, stub_bin(tmp_path), apps, "--replace-unstamped")[0] == 7

def test_code_12_when_another_install_holds_the_lock(tmp_path):
    repo = app_repo(tmp_path)
    fd = os.open(ws.gitdir(repo) / "gstack-install.lock", os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        assert run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")[0] == 12
    finally:
        os.close(fd)
    assert not (ws.gitdir(repo) / "gstack-install-result.json").exists()   # only the holder writes it

def test_code_12_when_land_holds_its_lock_past_the_wait(tmp_path):
    repo = app_repo(tmp_path)
    fd = os.open(ws.gitdir(repo) / "gstack-land.lock", os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        code, _ = run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir",
                              env_extra={"GSTACK_LAND_LOCK_WAIT": "1"})
    finally:
        os.close(fd)
    assert code == 12
    assert json.loads((ws.gitdir(repo) / "gstack-install-result.json").read_text())["code"] == 12

def test_stale_temporary_copies_for_the_same_bundle_id_are_removed_under_the_lock(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    mine = write_app(apps / ".Fake App.gstack-new-999")
    other = write_app(apps / ".Other.gstack-new-998", "com.other.app")
    assert passed(*run_install(repo, stub_bin(tmp_path), apps))
    assert not mine.exists() and other.exists()

def test_every_stop_is_stored_atomically_with_code_reason_and_commit(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    code, out = run_install(repo, stub_bin(tmp_path), apps)
    stored = json.loads((ws.gitdir(repo) / "gstack-install-result.json").read_text())
    assert code == 6 and set(out) == {"status", "code", "reason", "commit"}
    assert {k: stored[k] for k in out} == out and out["commit"] == _rev(repo, "HEAD")
    assert not [p for p in ws.gitdir(repo).iterdir() if p.name.endswith(".tmp")]

def test_a_missing_build_setting_is_64(tmp_path):
    repo = app_repo(tmp_path)
    stubs = stub_bin(tmp_path, xcodebuild="printf '    BUILT_PRODUCTS_DIR = /x\\n    FULL_PRODUCT_NAME = Fake App.app\\n'")
    code, out = run_install(repo, stubs, tmp_path / "Applications dir")
    assert code == 64 and "PRODUCT_BUNDLE_IDENTIFIER" in out["reason"]

def test_failing_build_settings_are_64_and_use_release_and_macos(tmp_path):
    repo = app_repo(tmp_path); env = stub_env(tmp_path)
    assert run_install(repo, stub_bin(tmp_path, xcodebuild="exit 65"), tmp_path / "Applications dir")[0] == 64
    log = Path(env["STUB_LOG"]).read_text()
    assert "-showBuildSettings -configuration Release -destination platform=macOS -scheme Fake App" in log

def test_xcodegen_runs_when_project_yml_is_newer_than_the_project(tmp_path):
    repo = app_repo(tmp_path); env = stub_env(tmp_path)
    commit_file(repo, "project.yml", "name: Fake\n"); push(repo)
    assert passed(*run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir"))
    log = Path(env["STUB_LOG"]).read_text()
    assert log.index("xcodegen generate") < log.index("xcodebuild")

def test_a_generated_project_that_changes_tracked_files_is_3(tmp_path):
    repo = app_repo(tmp_path)
    commit_file(repo, "project.yml", "name: Fake\n"); commit_file(repo, "Fake.xcodeproj/project.pbxproj", "old\n")
    push(repo); os.utime(repo / "project.yml", (2_000_000_000, 2_000_000_000))
    stubs = stub_bin(tmp_path, xcodegen='echo new > Fake.xcodeproj/project.pbxproj')
    assert run_install(repo, stubs, tmp_path / "Applications dir")[0] == 3

def test_a_workspace_is_preferred_to_a_project(tmp_path):
    repo = app_repo(tmp_path); env = stub_env(tmp_path)
    commit_file(repo, "Fake.xcodeproj/project.pbxproj", "x\n")
    commit_file(repo, "Fake.xcworkspace/contents.xcworkspacedata", "x\n"); push(repo)
    run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")
    log = Path(env["STUB_LOG"]).read_text()
    assert f"-workspace {repo}/Fake.xcworkspace" in log and "-project" not in log
