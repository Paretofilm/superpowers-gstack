"""Guard lint E13 — /adapt's content-loss guards are prose, so pin their contract.

A re-adaptation can be correct on every marker and still destroy project content:
before 2.48.0, Step 6 asked for a diff against a file Step 5 had already
overwritten. The strings E13 checks ARE the contract — the snapshot path a user
restores from, the report label they grep for. Rewording one fires the lint; that
is the point, not a nuisance.
"""

import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lint = load("lint_skills", "scripts/lint-skills.py")
ADAPT_SKILL = (REPO / "skills" / "adapt" / "SKILL.md").read_text()


def test_snapshot_path_is_named_in_the_skill():
    assert ".gstack/CLAUDE.md.pre-adapt" in ADAPT_SKILL


def test_snapshot_is_written_before_the_diff_reads_it():
    """Order matters: a diff instruction above the snapshot instruction is the
    original bug wearing a new path."""
    write_at = ADAPT_SKILL.index("cp CLAUDE.md .gstack/CLAUDE.md.pre-adapt")
    diff_at = ADAPT_SKILL.index("diff .gstack/CLAUDE.md.pre-adapt CLAUDE.md")
    assert write_at < diff_at


def test_the_unperformable_instruction_is_gone():
    assert "diff the old vs new CLAUDE.md mentally" not in ADAPT_SKILL


def test_denylist_catches_the_unperformable_instruction():
    line = "3. **Verify preserved content** — diff the old vs new CLAUDE.md mentally."
    assert any(p.search(line) for p, _ in lint.DENYLIST)


def test_every_adapt_guard_is_present():
    for needle, why in lint.ADAPT_GUARDS:
        assert needle in ADAPT_SKILL, f"{needle!r} missing ({why})"


def test_report_has_a_block_for_what_was_removed():
    """A list of survivors cannot reveal a casualty."""
    assert "**Removed (not plugin prose):**" in ADAPT_SKILL


def test_the_empty_case_has_an_explicit_sentinel():
    """An omitted block reads as 'not checked' — the state it exists to prevent."""
    assert "Nothing project-authored was removed." in ADAPT_SKILL
