import fcntl, importlib.util, json, os, plistlib, subprocess, sys
from pathlib import Path
import pytest
from work_state_fixtures import make_repo, add_origin, commit_file, stub_bin, stub_env, write_app, _with_settings

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

def test_install_safe_action_starts_with_the_running_interpreter(tmp_path):
    import sys
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: macos-app App\n"); add_origin(repo)
    argv = ws.measure_installable(repo)["safe_actions"][0]
    assert argv[0] == sys.executable and os.path.isabs(argv[0])
    assert argv[1:3] == [os.path.abspath(ws.__file__), "install"]

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
# A run that passes every question now builds and installs (Task 6): `passed` is exit 0.
# Ruling R8: fake apps carry a real Contents/Info.plist (write_app); there is no plutil stub.

def run_install(repo, stubs, apps, *extra, env_extra=None):
    apps.mkdir(parents=True, exist_ok=True)        # the applications folder of the test (never /Applications)
    env = {**os.environ, **stub_env(apps.parent), "PATH": f"{stubs}:{os.environ['PATH']}", **(env_extra or {})}
    p = subprocess.run([sys.executable, str(SCRIPT), "install", "--repo", str(repo),
                        "--applications-dir", str(apps), *extra], capture_output=True, text=True, env=env)
    return p.returncode, json.loads(p.stdout.strip().splitlines()[-1])

def app_repo(tmp_path, line="Installable: macos-app Fake App\n"):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", line); add_origin(repo)
    return repo

def passed(code, out):
    return code == 0 and out["status"] in ("installed", "current")

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
    code, out = run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")
    assert code == 3 and "Extra.swift" in out["reason"]                          # R10: names the files

def test_a_stored_code_3_is_shown_by_report(tmp_path):                            # R10
    repo = app_repo(tmp_path)
    (repo / "Extra.swift").write_text("x\n")
    assert run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")[0] == 3
    (repo / "Extra.swift").unlink()
    ask = json.loads(run_report(repo)[1][-1])["ask"]
    assert any("kode 3" in a and "Extra.swift" in a for a in ask)

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

def test_a_process_with_the_same_exe_name_but_another_bundle_id_is_ignored(tmp_path):   # review fix 1
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    stranger = write_app(tmp_path / "Elsewhere dir" / "Other.app", "com.other.app")
    env = stub_env(tmp_path); Path(env["STUB_PS_FILE"]).write_text(f"1 {stranger}/Contents/MacOS/Fake\n")
    for flags in ([], ["--quit-running"], ["--quit-path", str(stranger)]):
        assert passed(*run_install(repo, stub_bin(tmp_path), apps, *flags))
    assert "osascript" not in Path(env["STUB_LOG"]).read_text()

@pytest.mark.parametrize("flag", ["--quit-running", "--quit-path"])
def test_a_third_running_copy_with_our_bundle_id_stops_both_flags(tmp_path, flag):     # review fix 1
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    stamp_at(repo, apps, _rev(repo, "HEAD"))
    commit_file(repo, "Sources/View.swift", "struct V {}\n"); push(repo)     # Task 6: a current stamp is 0
    branch_app = write_app(tmp_path / "DerivedData dir" / "Fake App.app")
    third = write_app(tmp_path / "Third dir" / "Fake App.app")
    covered = apps / "Fake App.app" if flag == "--quit-running" else branch_app
    env = stub_env(tmp_path)
    Path(env["STUB_PS_FILE"]).write_text(f"1 {covered}/Contents/MacOS/Fake\n2 {third}/Contents/MacOS/Fake\n")
    extra = [flag] if flag == "--quit-running" else [flag, str(branch_app)]
    code, out = run_install(repo, stub_bin(tmp_path), apps, *extra)
    assert code == 4 and str(third) in out["reason"]
    assert "osascript" not in Path(env["STUB_LOG"]).read_text()

def test_a_running_branch_build_without_a_flag_is_4(tmp_path):                         # review fix 1
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    branch_app = write_app(tmp_path / "DerivedData dir" / "Fake App.app")
    env = stub_env(tmp_path); Path(env["STUB_PS_FILE"]).write_text(f"1 {branch_app}/Contents/MacOS/Fake\n")
    assert run_install(repo, stub_bin(tmp_path), apps)[0] == 4
    assert run_install(repo, stub_bin(tmp_path), apps, "--quit-running")[0] == 4

def test_quit_path_is_made_absolute(tmp_path):                                          # review minor 6
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    branch_app = write_app(tmp_path / "DerivedData dir" / "Fake App.app")
    env = stub_env(tmp_path); ps_file = Path(env["STUB_PS_FILE"])
    ps_file.write_text(f"1 {branch_app}/Contents/MacOS/Fake\n")
    full = {**os.environ, **env, "PATH": f"{stub_bin(tmp_path)}:{os.environ['PATH']}"}
    p = subprocess.run([sys.executable, str(SCRIPT), "install", "--repo", str(repo), "--applications-dir", str(apps),
                        "--quit-path", "DerivedData dir/Fake App.app"], capture_output=True, text=True, env=full,
                       cwd=str(tmp_path))
    assert passed(p.returncode, json.loads(p.stdout.strip().splitlines()[-1])) and not ps_file.exists()

def test_both_quit_flags_are_a_usage_error_that_still_ends_in_json(tmp_path):          # review minor 6
    repo = app_repo(tmp_path)
    code, out = run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir", "--quit-running", "--quit-path", "/x.app")
    assert code == 64 and out["code"] == 64 and out["status"] == "stopped"

def test_no_quit_is_sent_when_nothing_runs(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    env = stub_env(tmp_path)
    assert passed(*run_install(repo, stub_bin(tmp_path), apps, "--quit-running"))
    assert "osascript" not in Path(env["STUB_LOG"]).read_text()

def test_a_failing_ps_is_never_read_as_not_running(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    code, out = run_install(repo, stub_bin(tmp_path, ps="exit 1"), apps)
    assert code == 70 and "ps" in out["reason"]

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
    assert len(list(Path(stub_env(tmp_path)["STUB_TRASH"]).iterdir())) == 1      # to the Trash, never rm

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
    code, out = run_install(repo, stubs, tmp_path / "Applications dir")
    assert code == 3 and "xcodegen" in out["reason"] and "project.pbxproj" in out["reason"]

def test_helper_apps_in_the_settings_do_not_make_it_ambiguous(tmp_path):        # review fix 2
    repo = app_repo(tmp_path)
    dirs = "printf '    BUILT_PRODUCTS_DIR = %s\\n' \"$STUB_OUT\"\n"
    body = ("echo 'Build settings for action build and target Helper:'\n"
            f"echo '    TARGET_NAME = Helper'\n{dirs}echo '    FULL_PRODUCT_NAME = Helper.app'\n"
            "echo '    PRODUCT_BUNDLE_IDENTIFIER = com.example.helper'\necho '    EXECUTABLE_NAME = Helper'\n"
            "echo 'Build settings for action build and target Fake App:'\n"
            f"echo '    TARGET_NAME = Fake App'\n{dirs}echo '    FULL_PRODUCT_NAME = Fake App.app'\n"
            "echo '    PRODUCT_BUNDLE_IDENTIFIER = com.example.fake'\necho '    EXECUTABLE_NAME = Fake'\n")
    ambiguous = body.replace("TARGET_NAME = Fake App", "TARGET_NAME = Main").replace("= Fake App.app", "= Main.app")
    assert run_install(repo, stub_bin(tmp_path, xcodebuild=_with_settings(settings=ambiguous)),
                       tmp_path / "Applications dir")[0] == 64
    # after an install the stamp is current and discovery never runs, so the ambiguous case goes first
    assert passed(*run_install(repo, stub_bin(tmp_path, xcodebuild=_with_settings(settings=body)),
                               tmp_path / "Applications dir"))

def test_a_workspace_is_preferred_to_a_project(tmp_path):
    repo = app_repo(tmp_path); env = stub_env(tmp_path)
    commit_file(repo, "Fake.xcodeproj/project.pbxproj", "x\n")
    commit_file(repo, "Fake.xcworkspace/contents.xcworkspacedata", "x\n"); push(repo)
    run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")
    log = Path(env["STUB_LOG"]).read_text()
    assert f"-workspace {repo}/Fake.xcworkspace" in log and "-project" not in log


# ---- Task 6: install — build, verify before the swap, atomic swap, register, stamp ----
# Adapted from the brief: old copies are write_app bundles (R8; an empty folder is 7), build behaviour
# is changed through _with_settings (a bare "exit 65" would fail -showBuildSettings with 64), and the
# lsregister stub takes its last argument (the argv is `lsregister -f <app>`).

def _trash(tmp_path):
    return Path(stub_env(tmp_path)["STUB_TRASH"])

def _log(tmp_path):
    f = Path(stub_env(tmp_path)["STUB_LOG"])
    return f.read_text() if f.exists() else ""

def test_a_successful_install_swaps_stamps_and_a_second_run_is_current(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    code, out = run_install(repo, stub_bin(tmp_path), apps)
    assert code == 0 and out["status"] == "installed"
    stamp = json.loads((ws.gitdir(repo) / "gstack-installed-app.json").read_text())
    assert stamp["commit"] == _rev(repo, "origin/main") == out["commit"]
    assert set(stamp) == {"scheme", "bundle_id", "commit", "app_path", "version", "installed_at"}
    assert stamp["app_path"] == str(apps / "Fake App.app") and stamp["bundle_id"] == "com.example.fake"
    assert (apps / "Fake App.app").is_dir()
    assert (apps / "Fake App.app" / "built.txt").read_text().strip() == stamp["commit"]
    assert not [p for p in apps.iterdir() if ".gstack-new-" in p.name]
    stored = json.loads((ws.gitdir(repo) / "gstack-install-result.json").read_text())
    assert stored["code"] == 0 and stored["status"] == "installed"
    code, out = run_install(repo, stub_bin(tmp_path), apps)
    assert code == 0 and out["status"] == "current"
    assert ws.measure_installable(repo)["status"] == "ok"

def test_the_build_uses_release_macos_the_install_build_folder_and_no_signing_override(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"
    assert run_install(repo, stub_bin(tmp_path), apps)[0] == 0
    gd = ws.gitdir(repo)
    build = [l for l in _log(tmp_path).splitlines() if l.startswith("xcodebuild") and "-showBuildSettings" not in l]
    assert len(build) == 1 and build[0].endswith(" build")
    assert f"-derivedDataPath {gd}/gstack-install-build" in build[0]
    assert "-configuration Release -destination platform=macOS" in build[0] and "CODE_SIGN" not in build[0]
    assert (gd / "gstack-install-build.log").is_file()
    assert "lsregister -f " + str(apps / "Fake App.app") in _log(tmp_path)

def test_code_8_leaves_the_old_copy_untouched_and_names_the_log(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    marker = apps / "Fake App.app" / "old.txt"; marker.write_text("old")
    code, out = run_install(repo, stub_bin(tmp_path, xcodebuild=_with_settings("echo boom; exit 65")), apps,
                            "--replace-unstamped")
    assert code == 8 and "gstack-install-build.log" in out["reason"] and marker.read_text() == "old"
    assert "boom" in (ws.gitdir(repo) / "gstack-install-build.log").read_text()
    assert not [p for p in apps.iterdir() if ".gstack-new-" in p.name]

def test_a_failed_build_leaves_the_running_app_running(tmp_path):                    # carry-over (b)
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    ps_file = Path(stub_env(tmp_path)["STUB_PS_FILE"])
    ps_file.write_text(f"123 {apps}/Fake App.app/Contents/MacOS/Fake\n")
    code, _ = run_install(repo, stub_bin(tmp_path, xcodebuild=_with_settings("exit 65")), apps,
                          "--quit-running", "--replace-unstamped")
    assert code == 8 and ps_file.exists() and "osascript" not in _log(tmp_path)

def test_the_app_is_asked_to_quit_only_after_the_copy_is_verified(tmp_path):        # carry-over (b)
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    ps_file = Path(stub_env(tmp_path)["STUB_PS_FILE"])
    ps_file.write_text(f"123 {apps}/Fake App.app/Contents/MacOS/Fake\n")
    code, _ = run_install(repo, stub_bin(tmp_path), apps, "--quit-running", "--replace-unstamped")
    log = _log(tmp_path)
    assert code == 0 and not ps_file.exists()
    build = log.index("xcodebuild -")                                           # the first, -showBuildSettings
    build = log.index("xcodebuild", build + 1)
    assert build < log.index("ditto") < log.index("codesign") < log.index("to quit") < log.index("lsregister")

def test_code_9_removes_the_temporary_copy_and_keeps_the_old_one(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    (apps / "Fake App.app" / "old.txt").write_text("old")
    stubs = stub_bin(tmp_path, ditto='cp -R "$1" "$2" && touch "$2/bad-signature"')   # the copy fails verification
    code, _ = run_install(repo, stubs, apps, "--replace-unstamped")
    assert code == 9 and (apps / "Fake App.app" / "old.txt").read_text() == "old"
    assert not [p for p in apps.iterdir() if ".gstack-new-" in p.name]
    assert json.loads((ws.gitdir(repo) / "gstack-install-result.json").read_text())["code"] == 9
    assert not (ws.gitdir(repo) / "gstack-installed-app.json").exists()

def test_code_9_when_the_copy_has_another_bundle_id(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"
    other = _with_settings().replace("<string>com.example.fake</string>", "<string>com.example.other</string>")
    code, out = run_install(repo, stub_bin(tmp_path, xcodebuild=other), apps)
    assert code == 9 and "com.example.other" in out["reason"]
    assert not (apps / "Fake App.app").exists() and not list(apps.iterdir())

def test_code_10_when_the_applications_dir_is_not_writable_and_no_sudo_is_attempted(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir(); apps.chmod(0o555)
    try:
        code, _ = run_install(repo, stub_bin(tmp_path), apps)
    finally:
        apps.chmod(0o755)
    log = _log(tmp_path)
    assert code == 10 and "sudo" not in log
    assert not [l for l in log.splitlines() if l.startswith("xcodebuild") and "-showBuildSettings" not in l]  # no build

def test_code_11_when_main_moves_during_the_build_nothing_is_swapped_or_stamped(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    marker = apps / "Fake App.app" / "old.txt"; marker.write_text("old")
    mover = f'git -C "{repo}" commit -q --allow-empty -m moved && git -C "{repo}" push -q origin main'
    ps_file = Path(stub_env(tmp_path)["STUB_PS_FILE"])
    ps_file.write_text(f"123 {apps}/Fake App.app/Contents/MacOS/Fake\n")
    code, _ = run_install(repo, stub_bin(tmp_path, xcodebuild=_with_settings(mover)), apps,
                          "--replace-unstamped", "--quit-running")
    assert code == 11 and marker.read_text() == "old" and not (apps / "Fake App.app" / "built.txt").exists()
    assert not (ws.gitdir(repo) / "gstack-installed-app.json").exists()
    assert [p.name for p in apps.iterdir()] == ["Fake App.app"] and not list(_trash(tmp_path).iterdir())
    assert "to quit" in _log(tmp_path)              # review minor 3: HEAD is re-checked after the quit, right before the swap

def test_install_replaces_with_a_swap_and_the_old_copy_ends_in_the_trash(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    (apps / "Fake App.app" / "old.txt").write_text("old")
    code, out = run_install(repo, stub_bin(tmp_path), apps, "--replace-unstamped")
    assert code == 0 and (apps / "Fake App.app" / "built.txt").is_file() and not (apps / "Fake App.app" / "old.txt").exists()
    trashed = list(_trash(tmp_path).rglob("old.txt"))                     # the old copy went to the trash, not to rm
    assert trashed and not trashed[0].parent.name.startswith(".")        # a visible name in the Trash
    assert "papirkurven" in out["reason"]
    assert [p.name for p in apps.iterdir()] == ["Fake App.app"]

def test_the_trash_falls_back_to_the_home_trash_with_a_timestamp(tmp_path):        # carry-over (d)
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    (apps / "Fake App.app" / "old.txt").write_text("old")
    stubs = stub_bin(tmp_path, osascript='case "$*" in *Finder*) exit 1 ;; esac')
    code, out = run_install(repo, stubs, apps, "--replace-unstamped")
    home_trash = Path(stub_env(tmp_path)["HOME"]) / ".Trash"
    found = list(home_trash.rglob("old.txt"))
    assert code == 0 and found and found[0].parent.name.startswith("Fake App ")
    assert 'tell application "Finder" to delete (POSIX file (item 1 of argv))' in _log(tmp_path)
    assert str(home_trash) in out["reason"] and [p.name for p in apps.iterdir()] == ["Fake App.app"]

def test_a_name_with_spaces_and_non_ascii_survives(tmp_path):                  # Review Focus 5
    repo = app_repo(tmp_path, "Installable: macos-app Fake App æøå\n"); apps = tmp_path / "Applications dir ø"; apps.mkdir()
    stubs = stub_bin(tmp_path, xcodebuild=_with_settings(None, product="Fake App æøå.app"))
    code, out = run_install(repo, stubs, apps)
    assert code == 0 and (apps / "Fake App æøå.app").is_dir()
    stamp = json.loads((ws.gitdir(repo) / "gstack-installed-app.json").read_text(encoding="utf-8"))
    assert stamp["scheme"] == "Fake App æøå" and stamp["app_path"] == str(apps / "Fake App æøå.app")
    assert run_install(repo, stubs, apps)[1]["status"] == "current"

# R4': passes the check of the temporary copy, fails the check at the final path.
_FINAL_CHECK_FAILS = 'for last; do :; done; case "$last" in *.gstack-new-*) exit 0;; esac; exit 1'

def test_a_failed_final_check_without_an_old_copy_rolls_back_and_stamps_nothing(tmp_path):   # R4'
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    code, out = run_install(repo, stub_bin(tmp_path, codesign=_FINAL_CHECK_FAILS), apps)
    assert code == 9 and "rullet tilbake" in out["reason"]
    assert not (ws.gitdir(repo) / "gstack-installed-app.json").exists()
    assert not list(apps.iterdir()) and not list(_trash(tmp_path).iterdir())
    assert "lsregister" not in _log(tmp_path)

def test_a_failed_final_check_swaps_the_old_copy_back_untouched(tmp_path):         # R4'
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    (apps / "Fake App.app" / "old.txt").write_text("old")
    code, out = run_install(repo, stub_bin(tmp_path, codesign=_FINAL_CHECK_FAILS), apps, "--replace-unstamped")
    assert code == 9 and "rullet tilbake" in out["reason"] and "urørt" in out["reason"]
    assert (apps / "Fake App.app" / "old.txt").read_text() == "old"
    assert not (apps / "Fake App.app" / "built.txt").exists()
    assert [p.name for p in apps.iterdir()] == ["Fake App.app"]                  # no leftover
    assert not list(_trash(tmp_path).iterdir())                                 # nothing trashed
    assert not (ws.gitdir(repo) / "gstack-installed-app.json").exists()

def _broken_trash(tmp_path):
    """Finder fails and ~/.Trash is read-only: the previous version cannot go anywhere."""
    home_trash = Path(stub_env(tmp_path)["HOME"]) / ".Trash"
    home_trash.mkdir(exist_ok=True); home_trash.chmod(0o555)
    return home_trash, stub_bin(tmp_path, osascript='case "$*" in *Finder*) exit 1 ;; esac')

def test_an_old_copy_that_cannot_be_trashed_stays_hidden_for_the_next_run(tmp_path):   # review IMPORTANT 2
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    (apps / "Fake App.app" / "old.txt").write_text("old")
    home_trash, stubs = _broken_trash(tmp_path)
    try:
        code, out = run_install(repo, stubs, apps, "--replace-unstamped")
    finally:
        home_trash.chmod(0o755)
    assert code == 0 and "neste kjøring" in out["reason"]
    assert [p.name for p in apps.iterdir() if not p.name.startswith(".")] == ["Fake App.app"]
    hidden = [p for p in apps.iterdir() if p.name.startswith(".")]
    assert len(hidden) == 1 and ".gstack-new-" in hidden[0].name and (hidden[0] / "old.txt").is_file()

def test_a_leftover_that_cannot_be_trashed_is_renamed_back_to_hidden(tmp_path):    # review IMPORTANT 2
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"
    leftover = write_app(apps / ".Fake App.gstack-new-999")
    home_trash, stubs = _broken_trash(tmp_path)
    try:
        code, out = run_install(repo, stubs, apps)
    finally:
        home_trash.chmod(0o755)
    assert code == 70 and str(leftover) in out["reason"]
    assert leftover.is_dir() and [p.name for p in apps.iterdir()] == [".Fake App.gstack-new-999"]

def test_placing_without_an_old_copy_never_replaces_an_empty_folder(tmp_path, monkeypatch):   # review minor 2
    monkeypatch.setenv("GSTACK_SWAP", "rename")                    # honoured only outside macOS
    new, target = tmp_path / "new dir", tmp_path / "Fake App.app"; new.mkdir(); (new / "n.txt").write_text("n")
    target.mkdir()
    with pytest.raises(OSError):
        ws._place(new, target)
    assert (new / "n.txt").is_file() and not list(target.iterdir())
    target.rmdir()
    ws._place(new, target)
    assert (target / "n.txt").is_file() and not new.exists()

def test_the_test_swap_knob_is_ignored_on_macos(monkeypatch):                      # review minor 1
    monkeypatch.setenv("GSTACK_SWAP", "rename")
    monkeypatch.setattr(ws.sys, "platform", "darwin")
    calls = []
    monkeypatch.setattr(ws, "_renamex", lambda a, b, flags: calls.append(flags))
    ws._swap("a", "b"); ws._place("c", "d")
    assert calls == [ws.RENAME_SWAP, ws.RENAME_EXCL]

def test_current_comes_before_the_running_check(tmp_path):                          # carry-over (c)
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"
    assert run_install(repo, stub_bin(tmp_path), apps)[0] == 0
    ps_file = Path(stub_env(tmp_path)["STUB_PS_FILE"])
    ps_file.write_text(f"123 {apps}/Fake App.app/Contents/MacOS/Fake\n")
    Path(stub_env(tmp_path)["STUB_LOG"]).unlink()
    code, out = run_install(repo, stub_bin(tmp_path), apps)
    assert code == 0 and out["status"] == "current" and ps_file.exists()
    assert not [l for l in _log(tmp_path).splitlines() if l.split(" ")[0] in ("osascript", "ps", "xcodebuild")]

def test_a_new_commit_after_an_install_is_installed_over_the_stamped_copy(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"
    assert run_install(repo, stub_bin(tmp_path), apps)[0] == 0
    commit_file(repo, "Sources/View.swift", "struct V {}\n"); push(repo)
    code, out = run_install(repo, stub_bin(tmp_path), apps)
    assert code == 0 and out["status"] == "installed" and out["commit"] == _rev(repo, "HEAD")
    assert (apps / "Fake App.app" / "built.txt").read_text().strip() == _rev(repo, "HEAD")
    assert len(list(_trash(tmp_path).iterdir())) == 1

def _stored(repo):
    return json.loads((ws.gitdir(repo) / "gstack-install-result.json").read_text())

def test_sigterm_during_the_build_stores_avbrutt_with_the_commit_and_ends_in_json(tmp_path):   # carry-over (a)
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    (apps / "Fake App.app" / "old.txt").write_text("old")
    stubs = stub_bin(tmp_path, xcodebuild=_with_settings('kill -TERM "$PPID"; sleep 5; exit 0'))
    code, out = run_install(repo, stubs, apps, "--replace-unstamped")
    assert code == 70 and "avbrutt" in out["reason"] and out["commit"] == _rev(repo, "HEAD")
    assert _stored(repo)["code"] == 70 and _stored(repo)["commit"] == out["commit"]
    assert (apps / "Fake App.app" / "old.txt").read_text() == "old"
    assert [p.name for p in apps.iterdir()] == ["Fake App.app"]

def test_sigterm_during_the_copy_removes_the_temporary_copy(tmp_path):              # carry-over (a)
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; write_app(apps / "Fake App.app")
    (apps / "Fake App.app" / "old.txt").write_text("old")
    stubs = stub_bin(tmp_path, ditto='cp -R "$1" "$2"; kill -TERM "$PPID"; sleep 5')
    code, out = run_install(repo, stubs, apps, "--replace-unstamped")
    assert code == 70 and "avbrutt" in out["reason"] and _stored(repo)["code"] == 70
    assert [p.name for p in apps.iterdir()] == ["Fake App.app"]
    assert (apps / "Fake App.app" / "old.txt").read_text() == "old"
    assert not list(_trash(tmp_path).iterdir())                                  # our own copy: removed, not trashed

def test_sigint_is_stored_as_avbrutt_too(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"
    stubs = stub_bin(tmp_path, xcodebuild=_with_settings('kill -INT "$PPID"; sleep 5; exit 0'))
    code, out = run_install(repo, stubs, apps)
    assert code == 70 and "avbrutt" in out["reason"] and _stored(repo)["code"] == 70

def test_the_swap_without_the_test_knob_refuses_outside_macos(tmp_path, monkeypatch):
    monkeypatch.delenv("GSTACK_SWAP", raising=False)
    monkeypatch.setattr(ws.sys, "platform", "linux")
    a, b = tmp_path / "a dir", tmp_path / "b dir"; a.mkdir(); b.mkdir()
    with pytest.raises(ws.Stop) as e:
        ws._swap(a, b)
    assert e.value.code == 70 and a.is_dir() and b.is_dir()

def test_the_rename_dance_swaps_two_folders(tmp_path, monkeypatch):
    monkeypatch.setenv("GSTACK_SWAP", "rename")
    a, b = tmp_path / "a dir", tmp_path / "b dir"; a.mkdir(); b.mkdir()
    (a / "a.txt").write_text("a"); (b / "b.txt").write_text("b")
    ws._swap(a, b)
    assert (a / "b.txt").is_file() and (b / "a.txt").is_file() and sorted(p.name for p in tmp_path.iterdir()) == ["a dir", "b dir"]

@pytest.mark.skipif(sys.platform != "darwin", reason="renamex_np exists only on macOS")
def test_renamex_np_swaps_two_folders_atomically_on_macos(tmp_path, monkeypatch):
    monkeypatch.delenv("GSTACK_SWAP", raising=False)
    a, b = tmp_path / "a dir æ", tmp_path / "b dir"; a.mkdir(); b.mkdir()
    (a / "a.txt").write_text("a"); (b / "b.txt").write_text("b")
    ws._swap(a, b)
    assert (a / "b.txt").is_file() and (b / "a.txt").is_file()
