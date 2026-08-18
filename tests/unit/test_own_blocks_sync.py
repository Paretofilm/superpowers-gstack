"""Guard scripts/sync-own-claude-md.py + lint E11 — this repo eating its own dog food.

check-plugin-version.sh exempts this repo from the /adapt nag, correctly: its
CLAUDE.md is the SOURCE of the routing and carries no generated marker. But the
exemption was wholesale, so every block shipped to user projects never applied to
the repo producing them — measured 2026-08-18, that repo had six stranded branches
while shipping a git-hygiene block telling everyone else to land theirs.

Generated-and-enforced, not hand-synced: hand-sync with a "keep in sync" comment is
the exact mechanism that let Session Continuity drift for four releases.
"""

import importlib.util
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sync = load("sync_own", "scripts/sync-own-claude-md.py")


def test_region_in_repo_is_current():
    """The committed CLAUDE.md must already be in sync — this is what E11 enforces."""
    text = (REPO / "CLAUDE.md").read_text()
    assert sync.splice(text, sync.render()) == text, (
        "CLAUDE.md own-blocks region is stale — run scripts/sync-own-claude-md.py"
    )


def test_every_universal_block_exists():
    for name in sync.UNIVERSAL:
        assert (sync.BLOCKS / name).is_file(), f"{name} listed as universal but missing"


def test_conditional_and_placeholder_blocks_are_excluded():
    """Emitting these into the plugin's own repo would be wrong, not merely noisy:
    three are native-track conditional, and model-routing carries an unresolved
    {{DOMAIN_SENSITIVITY}} placeholder."""
    for name in ("track-routing.md", "xcode-tools.md", "companion-skills.md",
                 "model-routing-section.md", "PLACEHOLDERS.md"):
        assert name not in sync.UNIVERSAL, f"{name} must not be emitted into this repo"


def test_rendered_region_is_byte_identical_to_the_blocks():
    """The whole point: what this repo follows is what /adapt emits elsewhere."""
    region = sync.render()
    for name in sync.UNIVERSAL:
        body = (sync.BLOCKS / name).read_text().rstrip("\n")
        assert body in region, f"{name} content not emitted verbatim"


def test_splice_is_idempotent():
    text = (REPO / "CLAUDE.md").read_text()
    once = sync.splice(text, sync.render())
    assert sync.splice(once, sync.render()) == once


def test_check_mode_does_not_write(tmp_path, monkeypatch):
    """--check is used by CI; it must never mutate the file it is inspecting."""
    before = (REPO / "CLAUDE.md").read_bytes()
    monkeypatch.setattr(sync.sys, "argv", ["sync", "--check"])
    assert sync.main() == 0
    assert (REPO / "CLAUDE.md").read_bytes() == before
