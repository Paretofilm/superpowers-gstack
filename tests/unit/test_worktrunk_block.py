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
    assert re.match(r"^## Worktrees and solo landing <!-- gstack-worktrunk-v2 -->\n", text)
    assert text.endswith("\n")


def test_block_never_holds_the_parsable_mode_line():
    for line in BLOCK.read_text().splitlines():
        assert not re.match(r"^Landing mode: (solo|pr)$", line), f"reset-on-upgrade trap: {line!r}"


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
