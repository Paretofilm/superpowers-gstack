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
