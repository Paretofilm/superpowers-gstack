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


def test_header_warns_which_sections_are_plugin_owned():
    assert "are plugin-managed: /adapt replaces each one" in ADAPT_SKILL


def test_header_comment_does_not_nest_a_comment_terminator():
    """HTML comments do not nest: an inner '-->' would close the header early and
    dump the rest of the warning into the rendered file as visible text."""
    start = ADAPT_SKILL.index("<!-- Sections whose heading carries")
    body = ADAPT_SKILL[start + 4 : ADAPT_SKILL.index("-->", start)]
    assert "<!--" not in body


def test_growth_check_exists_and_states_a_threshold():
    assert "**Growth check" in ADAPT_SKILL
    assert "1.5×" in ADAPT_SKILL


def test_growth_check_precedes_every_per_section_rule():
    """Stated once, above the rules it governs — a gate below its cases is a gate
    the reader meets after deciding."""
    gate = ADAPT_SKILL.index("**Growth check")
    first_rule = ADAPT_SKILL.index("**Insert or upgrade the Autonomy")
    assert gate < first_rule


def test_growth_check_has_a_non_interactive_branch():
    """/adapt also runs under --print, in CI, and as a subagent. A hard stop
    there is a hang, not a safeguard."""
    gate = ADAPT_SKILL[ADAPT_SKILL.index("**Growth check"):]
    gate = gate[: gate.index("**Insert or upgrade the Autonomy")]
    assert "Non-interactive runs" in gate


BLOCKS = REPO / "skills" / "setup-routing" / "blocks"


def test_no_block_hardcodes_a_simulator_model():
    import re
    for f in sorted(BLOCKS.glob("*.md")):
        assert not re.search(r"name=iPhone \d", f.read_text()), f"{f.name} names a model"


def test_xcode_tools_uses_the_placeholder():
    assert "{{IOS_SIMULATOR}}" in (BLOCKS / "xcode-tools.md").read_text()


def test_every_placeholder_in_a_block_is_documented():
    """E12's invariant, asserted directly: an undocumented {{TOKEN}} reaches a
    project's CLAUDE.md raw, which PLACEHOLDERS.md's own preamble forbids."""
    import re
    documented = set(re.findall(r"^##\s+`\{\{([A-Z0-9_]+)\}\}`",
                                (BLOCKS / "PLACEHOLDERS.md").read_text(), re.M))
    for f in sorted(BLOCKS.glob("*.md")):
        if f.name == "PLACEHOLDERS.md":
            continue
        for tok in set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", f.read_text())):
            assert tok in documented, f"{f.name}: {{{{{tok}}}}} undocumented"


def test_denylist_catches_a_hardcoded_simulator_model():
    line = "`xcodebuild -scheme X -destination 'platform=iOS Simulator,name=iPhone 16' build`"
    assert any(p.search(line) for p, _ in lint.DENYLIST)
