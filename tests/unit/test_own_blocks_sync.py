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
    """The whole point: what this repo follows is what /adapt emits elsewhere.

    Everything below the heading line is the block verbatim. The heading itself
    is the block's heading as a GENERATOR writes it — with the provenance comment
    appended — which is the same standard, not an exception to it.
    """
    region = sync.render()
    for name in sync.UNIVERSAL:
        raw = (sync.BLOCKS / name).read_text()
        head, _, body = raw.rstrip("\n").partition("\n")
        assert body in region, f"{name} content not emitted verbatim"
        # `head` itself IS a prefix of the emitted heading — that is the design.
        # What must not appear is the heading as a whole LINE, i.e. bare.
        assert f"{head}\n" not in region, (
            f"{name} heading emitted bare — a generator writes provenance beside "
            f"the marker, and this repo is supposed to eat its own cooking")


def test_every_emitted_heading_carries_its_block_s_line_count():
    """`emitted=<N>` is `wc -l` of the block file. Here that definition is
    executable rather than prose, which is the one place it can be checked at all:
    the generators are agents following an instruction, this is a script."""
    import re
    region = sync.render()
    for name in sync.UNIVERSAL:
        raw = (sync.BLOCKS / name).read_text()
        head = raw.split("\n", 1)[0]
        want = f"{head}<!-- emitted={raw.count(chr(10))} -->"
        assert want in region, f"{name}: expected heading {want!r}"
    # and never the shape that stops an older reader matching the marker
    assert not re.search(r"<!-- gstack-[a-z-]+-v\d+ +emitted=", region)


def test_provenance_leaves_the_bare_marker_matchable():
    """The reason for a second comment rather than an attribute inside the first:
    a reader that greps the bare marker — an older plugin cache, lint E8 — must
    still find it byte-for-byte in what we wrote."""
    import re
    region = sync.render()
    for name in sync.UNIVERSAL:
        head = (sync.BLOCKS / name).read_text().split("\n", 1)[0]
        m = re.search(r"<!-- gstack-[a-z-]+-v\d+ -->", head)
        assert m, f"{name}: block heading carries no bare marker to begin with"
        assert m.group(0) in region, (
            f"{name}: bare marker {m.group(0)!r} no longer present in what we wrote")


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
