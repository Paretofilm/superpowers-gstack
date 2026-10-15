"""The view-gate hook must nudge once, stay quiet after a lint, and never break a write."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "view-gate.py"
VIEW = "import SwiftUI\nstruct Pill: View {\n    var body: some View { Text(\"x\") }\n}\n"
MODEL = "struct Item: Codable { var id: Int }\n"


@pytest.fixture(autouse=True)
def isolated_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()


def hook(event: dict, cwd: Path) -> str:
    r = subprocess.run([sys.executable, str(SCRIPT), "nudge"], input=json.dumps(event),
                       capture_output=True, text=True, cwd=cwd)
    assert r.returncode == 0, r.stderr
    return r.stdout


def edit(path: Path, session="s1") -> dict:
    return {"session_id": session, "tool_name": "Edit", "cwd": str(path.parent),
            "tool_input": {"file_path": str(path)}}


def test_view_file_edit_earns_one_reminder(tmp_path):
    f = tmp_path / "Pill.swift"
    f.write_text(VIEW)
    out = json.loads(hook(edit(f), tmp_path))
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "/superpowers-gstack:swiftui-view-gate" in ctx and "View gate:" in ctx
    assert hook(edit(f), tmp_path) == "", "one reminder per unlinted streak"


def test_an_edit_after_a_lint_earns_a_new_reminder(tmp_path):
    f = tmp_path / "Pill.swift"
    f.write_text(VIEW)
    assert hook(edit(f), tmp_path)
    lint = {"session_id": "s1", "tool_name": "mcp__swiftui-rag__review_macos_hig", "tool_input": {}}
    assert hook(lint, tmp_path) == ""
    assert hook(edit(f), tmp_path), "the lint is stale once the view changes again"
    assert hook(edit(f), tmp_path) == ""


def test_non_view_swift_and_other_files_are_silent(tmp_path):
    m = tmp_path / "Item.swift"
    m.write_text(MODEL)
    t = tmp_path / "notes.md"
    t.write_text("struct X: View {}")
    assert hook(edit(m), tmp_path) == ""
    assert hook(edit(t), tmp_path) == ""


def test_views_directory_counts_without_a_view_declaration(tmp_path):
    d = tmp_path / "Views"
    d.mkdir()
    f = d / "Helper.swift"
    f.write_text(MODEL)
    assert hook(edit(f), tmp_path)


def test_view_modifier_alone_is_not_a_view(tmp_path):
    f = tmp_path / "Mod.swift"
    f.write_text("struct Glow: ViewModifier { func body(content: Content) -> some ViewModifier { self } }\n")
    assert hook(edit(f), tmp_path) == ""


def test_sessions_are_independent(tmp_path):
    f = tmp_path / "Pill.swift"
    f.write_text(VIEW)
    assert hook(edit(f, "a"), tmp_path)
    assert hook(edit(f, "b"), tmp_path)


@pytest.mark.parametrize("payload", ["", "not json", "[]", "null", '{"tool_input": 3}'])
def test_garbage_input_never_raises(payload, tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "nudge"], input=payload,
                       capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and r.stdout == ""


def git(cwd: Path, *a: str) -> str:
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=cwd,
                          capture_output=True, text=True, check=True).stdout


def test_files_lists_changed_view_files_only(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "Item.swift").write_text(MODEL)
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "switch", "-q", "-c", "feat")
    (tmp_path / "Pill.swift").write_text(VIEW)
    (tmp_path / "Item.swift").write_text(MODEL + "// edit\n")
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-q", "-m", "feat")
    (tmp_path / "Dirty.swift").write_text(VIEW)   # uncommitted, untracked
    r = subprocess.run([sys.executable, str(SCRIPT), "files", "--base", "main"],
                       capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["Dirty.swift", "Pill.swift"]


def test_files_with_a_bad_ref_is_blocked(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    r = subprocess.run([sys.executable, str(SCRIPT), "files", "--base", "nope"],
                       capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 2 and r.stderr.startswith("BLOCKED")


def test_files_outside_a_repository_is_blocked(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "files", "--base", "main"],
                       capture_output=True, text=True, cwd=tmp_path,
                       env={"PATH": "/usr/bin:/bin", "GIT_CEILING_DIRECTORIES": str(tmp_path.parent)})
    assert r.returncode == 2 and r.stderr.startswith("BLOCKED")


def test_hook_is_registered_and_points_at_the_script():
    hooks = json.loads((REPO / "hooks" / "hooks.json").read_text())["hooks"]["PostToolUse"]
    entry = next(h for h in hooks if "view-gate.py" in h["hooks"][0]["command"])
    assert entry["hooks"][0]["command"] == "${CLAUDE_PLUGIN_ROOT}/scripts/view-gate.py nudge"
    for tool in ("Write", "Edit", "MultiEdit", "mcp__swiftui-rag__review_macos_hig",
                 "mcp__swiftui-rag__review_accessibility", "mcp__swiftui-rag__review_liquid_glass"):
        assert __import__("re").fullmatch(entry["matcher"], tool), tool
    assert not __import__("re").fullmatch(entry["matcher"], "mcp__swiftui-rag__search_swiftui_corpus")
    assert (REPO / "scripts" / "view-gate.py").stat().st_mode & 0o111


def test_files_from_a_subdirectory_still_finds_untracked_views(tmp_path):
    """`git ls-files --others` prints paths relative to the cwd, `git diff --name-only`
    relative to the top; mixing them would silently drop a view."""
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "App" / "Sources").mkdir(parents=True)
    (tmp_path / "App" / "Sources" / "Item.swift").write_text(MODEL)
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-q", "-m", "base")
    (tmp_path / "App" / "Sources" / "New.swift").write_text(VIEW)
    r = subprocess.run([sys.executable, str(SCRIPT), "files", "--base", "main"],
                       capture_output=True, text=True, cwd=tmp_path / "App" / "Sources")
    assert r.returncode == 0 and r.stdout.split() == ["App/Sources/New.swift"], (r.stdout, r.stderr)


def test_files_finds_non_ascii_names_and_generic_views(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "Item.swift").write_text(MODEL)
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-q", "-m", "base")
    (tmp_path / "Kategori-æøå.swift").write_text(VIEW)
    (tmp_path / "Generic.swift").write_text("struct Box<T>: View {\n    var body: Never { fatalError() }\n}\n")
    r = subprocess.run([sys.executable, str(SCRIPT), "files", "--base", "main"],
                       capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert sorted(r.stdout.split("\n")[:-1]) == ["Generic.swift", "Kategori-æøå.swift"]
