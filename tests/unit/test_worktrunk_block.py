"""skills/adapt/blocks/worktrunk.md — the rules every adapted project gets.

The block must never contain the parsable `Landing mode:` line itself: /adapt replaces
a block wholesale on upgrade, so a line inside it would silently reset a project's
choice of `pr` back to `solo`. land-worktree.py parses that line with an anchored
pattern; prose that merely mentions it, inside a sentence, must not match.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BLOCK = REPO / "skills" / "adapt" / "blocks" / "worktrunk.md"


def test_heading_carries_the_marker_and_the_file_ends_with_newline():
    text = BLOCK.read_text()
    assert re.match(r"^## Worktrees and solo landing <!-- gstack-worktrunk-v4 -->\n", text)
    assert text.endswith("\n")


def test_block_never_holds_the_parsable_mode_line():
    for line in BLOCK.read_text().splitlines():
        assert not re.match(r"^Landing mode: (solo|pr)$", line), f"reset-on-upgrade trap: {line!r}"
        assert not re.match(r"^Local state:", line), f"reset-on-upgrade trap: {line!r}"


def test_files_outside_git_stay_in_the_primary_checkout():
    """3.8.0 (from KvitteriAi, 2026-10-09): a copy splits state that must be one, and
    `data/` in .gitignore does not match a symlink named data, so git add stages it."""
    text = " ".join(BLOCK.read_text().split())
    assert "Files outside git live only in the primary checkout" in text
    assert "git pull --ff-only" in text
    assert "Never copy them into a worktree or link to them from one" in text
    assert "matches only a directory, not a symlink" in text
    assert "`Local state: <paths>` or `Local state: none`" in text


def test_checks_before_landing_run_without_local_state():
    """3.9.0 (benchmark finding, Gemini): a pre-merge check that needs ignored files cannot
    pass in a worktree. CI cannot run it either, so the fix is the check, not a copy."""
    text = " ".join(BLOCK.read_text().split())
    assert "The checks before landing run without these files, exactly as CI does on a fresh clone" in text
    assert "committed stand-ins first" in text
    assert "never copied from the local file" in text
    assert "run it in the primary-checkout session after landing" in text
    assert "tell the user that this check did not gate the landing" in text


def test_block_forbids_the_shortcuts_the_gate_depends_on():
    text = BLOCK.read_text()
    for needle in ("--no-hooks", "--yes", "git stash", "EnterWorktree", "/superpowers-gstack:land"):
        assert needle in text, needle


def test_the_landing_mode_line_belongs_on_the_default_branch():
    """3.5.1: land stops with exit 14 when a branch adds or changes the Landing mode
    line, so the block must say where the answer is committed."""
    text = " ".join(BLOCK.read_text().split())
    assert "commit it on the default branch, not on a feature branch" in text
    assert "exit 14" in text
