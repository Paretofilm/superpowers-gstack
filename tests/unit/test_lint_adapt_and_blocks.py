"""Lint E8 / E12 / E13 / E14 and the shared block files.

Until 3.1.0 this file pinned twenty sentences of /adapt's prose (E13's guards)
because a reword could silently delete the growth check. The merge is a script
now — scripts/adapt-claude-md.py, tested in test_adapt_script.py — so what is
left to pin is the layering: the skill delegates, the script is the one
generator, the blocks stay single-sourced and placeholder-complete.
"""

import importlib.util
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
BLOCKS = REPO / "skills" / "adapt" / "blocks"


def load(name, rel):
    import sys
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod   # dataclasses resolve string annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


lint = load("lint_skills", "scripts/lint-skills.py")
ADAPT_SKILL = (REPO / "skills" / "adapt" / "SKILL.md").read_text()


# --- E13: the skill delegates; it never merges by hand ---------------------------

def test_the_skill_names_the_script_and_the_lint_passes_on_it():
    assert "scripts/adapt-claude-md.py" in ADAPT_SKILL
    assert lint.check_adapt_delegates(ADAPT_SKILL) == []


def test_dropping_the_script_reference_turns_e13_red():
    mutated = ADAPT_SKILL.replace("scripts/adapt-claude-md.py", "the merge tool")
    assert mutated != ADAPT_SKILL
    assert any("never names" in e for e in lint.check_adapt_delegates(mutated))


@pytest.mark.parametrize("needle,why", lint.ADAPT_HAND_SURGERY)
def test_every_retired_hand_surgery_instruction_turns_e13_red(needle, why):
    """Paste one sentence of the 2.x prose back and the lint must say so — the
    model must never be asked to perform the merge again."""
    assert needle not in ADAPT_SKILL, f"{needle!r} is back in the skill"
    errs = lint.check_adapt_delegates(ADAPT_SKILL + "\n" + needle + " …\n")
    assert any(repr(needle) in e for e in errs), errs


def test_the_unperformable_instruction_stays_denylisted():
    line = "3. **Verify preserved content** — diff the old vs new CLAUDE.md mentally."
    assert any(p.search(line) for p, _ in lint.DENYLIST)
    assert "diff the old vs new CLAUDE.md mentally" not in ADAPT_SKILL


def test_the_skill_keeps_the_three_report_labels_verbatim():
    """The script prints them; the skill relays the report and must not translate
    them, so it has to name them exactly."""
    script = load("adapt_claude_md", "scripts/adapt-claude-md.py")
    for label in (script.REMOVED_LABEL, script.NOTHING_REMOVED, script.DEFERRED_LABEL):
        assert label in ADAPT_SKILL, label


def test_the_skill_asks_before_applying_and_defaults_to_preserving():
    assert "--dry-run" in ADAPT_SKILL
    assert "--rescue" in ADAPT_SKILL
    assert ADAPT_SKILL.index("--dry-run") < ADAPT_SKILL.index("Shall I proceed")
    assert "left** at its old version" in ADAPT_SKILL or "**left** at its old version" in ADAPT_SKILL


def test_header_comment_in_the_script_does_not_nest_a_comment_terminator():
    """HTML comments do not nest: an inner '-->' would close the header early and
    dump the rest of the warning into the rendered file as visible text."""
    script = load("adapt_claude_md", "scripts/adapt-claude-md.py")
    body = script.HEADER_LINE2[4:script.HEADER_LINE2.index("-->")]
    assert "<!--" not in body
    assert script.HEADER_LINE2.endswith("-->") and script.HEADER_LINE2.count("-->") == 1


# --- E8: one generator, single-sourced blocks --------------------------------------

def test_the_script_roster_covers_every_block_and_nothing_else():
    roster = lint.adapt_script_blocks()
    assert roster is not None
    assert set(roster) == set(lint.MARKER_BLOCKS) | {"model-routing-section.md"}
    assert set(lint.PLAIN_BLOCKS) == {"model-routing-section.md", "PLACEHOLDERS.md"}


def test_every_marker_block_parses_as_a_heading():
    for name in lint.MARKER_BLOCKS:
        first = (BLOCKS / name).read_text().split("\n", 1)[0]
        assert lint.heading_text(first), f"{name} first line is not a parseable heading"
        assert re.match(r"^## .*<!-- gstack-[a-z-]+-v\d+ -->$", first), name


def test_the_skill_references_placeholders_and_carries_no_inline_block():
    assert "PLACEHOLDERS.md" in ADAPT_SKILL
    for line in ADAPT_SKILL.splitlines():
        assert not re.search(r"<!-- gstack-[a-z-]+-v\d+ -->", line), f"inline marker copy: {line}"
        h = lint.heading_text(line)
        if h:
            for name in lint.MARKER_BLOCKS:
                assert h != lint.heading_text((BLOCKS / name).read_text().split("\n", 1)[0]), line


def test_git_hygiene_provenance_example_in_the_script_matches_the_block():
    """The script derives `emitted=` from the file; nothing hardcodes the number.
    Guard that no doc example drifted from what git-hygiene.md carries today."""
    text = (BLOCKS / "git-hygiene.md").read_text()
    marker = re.search(r"<!-- (gstack-git-hygiene-v\d+) -->", text.split("\n", 1)[0]).group(1)
    own = (REPO / "CLAUDE.md").read_text()
    assert f"<!-- {marker} --><!-- emitted={text.count(chr(10))} -->" in own, \
        "the repo's own CLAUDE.md provenance is stale — run scripts/sync-own-claude-md.py"


def test_block_files_never_carry_the_emitted_attribute():
    """`emitted=` is written by the script into a project's CLAUDE.md. In a block
    file it would be a constant that lies the moment the block changes length."""
    for f in sorted(BLOCKS.glob("*.md")):
        assert "emitted=" not in f.read_text().split("\n", 1)[0], f"{f.name} line 1"


# --- E12: placeholders --------------------------------------------------------------

def test_no_block_hardcodes_a_simulator_model():
    for f in sorted(BLOCKS.glob("*.md")):
        assert not re.search(r"name=iPhone \d", f.read_text()), f"{f.name} names a model"


def test_xcode_tools_uses_the_placeholder():
    assert "{{IOS_SIMULATOR}}" in (BLOCKS / "xcode-tools.md").read_text()


def test_every_placeholder_in_a_block_is_documented():
    """E12's invariant, asserted through the lint's own function so the test and
    the rule cannot drift: an undocumented {{TOKEN}} reaches a project's
    CLAUDE.md raw, which PLACEHOLDERS.md's own preamble forbids."""
    documented = lint.documented_placeholders((BLOCKS / "PLACEHOLDERS.md").read_text())
    for f in sorted(BLOCKS.glob("*.md")):
        if f.name == "PLACEHOLDERS.md":
            continue
        for tok in set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", f.read_text())):
            assert tok in documented, f"{f.name}: {{{{{tok}}}}} undocumented"


def test_a_placeholder_heading_with_no_body_is_not_documentation():
    empty = "# Placeholders\n\n## `{{EMPTY_TOKEN}}` (somewhere)\n\n## `{{REAL_TOKEN}}`\n\nRun `echo hi`.\n"
    assert lint.documented_placeholders(empty) == {"REAL_TOKEN"}


def test_the_simulator_fallback_keeps_a_parenthesised_model_name_whole():
    """`iPhone SE (3rd generation)` is the device's exact name. A pattern anchored
    on the first '(' truncates it to `iPhone SE`, which no simulator is called —
    so the placeholder emits the destination error it exists to prevent."""
    import subprocess
    ph = (BLOCKS / "PLACEHOLDERS.md").read_text()
    fallback = re.search(r"^ +(xcrun simctl list devices available \| sed -nE "
                         r"'s/\^ \*\(iPhone \.\*\).*?/p'.*)$", ph, re.M)
    assert fallback, "the {{IOS_SIMULATOR}} fallback command is not in PLACEHOLDERS.md"
    line = "    iPhone SE (3rd generation) (AABBCCDD-1122-3344-5566-778899AABBCC) (Shutdown) \n"
    out = subprocess.run(["bash", "-c", fallback.group(1).replace(
        "xcrun simctl list devices available", "cat")], input=line,
        capture_output=True, text=True).stdout.strip()
    assert out == "iPhone SE (3rd generation)", out


def test_denylist_catches_a_hardcoded_simulator_model():
    line = "`xcodebuild -scheme X -destination 'platform=iOS Simulator,name=iPhone 16' build`"
    assert any(p.search(line) for p, _ in lint.DENYLIST)


# --- 3.0.0: the denylist retires the pre-3.0.0 markers and the removed surfaces ---

@pytest.mark.parametrize("line,hit,why", [
    ("## Multi-lens review <!-- gstack-multi-lens-review-v6 -->", True, "v6 multi-lens"),
    ("## Session Continuity <!-- gstack-session-continuity-v3 -->", True, "v3 session-continuity"),
    ("## Code reuse <!-- gstack-code-reuse-v2 -->", True, "v2 code-reuse"),
    ("## Track routing <!-- gstack-routing-v2 -->", True, "v2 routing"),
    ("## Companion skills <!-- gstack-companion-skills-v2 -->", True, "v2 companion-skills"),
    ("## Git hygiene <!-- gstack-git-hygiene-v9 -->", True, "v9 git-hygiene"),
    ("## Autonomy <!-- gstack-autonomy-v2 -->", True, "the retired autonomy block, any version"),
    ("run python3 scripts/cost-ledger/cli.py status", True, "cost-ledger"),
    ("dispatch /ios-visual-explore for exploratory runs", True, "ios-visual-explore"),
    ("see scripts/computer_use/loop.py", True, "computer_use"),
    ("if the frontmatter says `mode: auto`, treat it as continuous", True, "legacy handoff mode"),
    ("route architecture to glm-5.2 at $1/$3 per Mtok", True, "hardcoded model id / price"),
    ("then auto-chains `/codex review` on the diff", True, "chained codex review"),
    ("close every window in Safari, then open the file", True, "htmlify Safari flow"),
    ("bash scripts/setup-htmlify-hook.sh", True, "htmlify PostToolUse hook"),
    # what a 3.x generator actually writes must stay clean
    ("## Multi-lens review <!-- gstack-multi-lens-review-v7 -->", False, "current multi-lens"),
    ("## Session Continuity <!-- gstack-session-continuity-v4 -->", False, "current session-continuity"),
    ("## Code reuse <!-- gstack-code-reuse-v3 -->", False, "current code-reuse"),
    ("## Track routing <!-- gstack-routing-v3 -->", False, "current routing"),
    ("## Companion skills <!-- gstack-companion-skills-v3 -->", False, "current companion-skills"),
    ("## Git hygiene <!-- gstack-git-hygiene-v10 --><!-- emitted=101 -->", False,
     "v10 must not be caught by a v[0-9] class — the \\b is load-bearing"),
    ("mode: continuous", False, "the only handoff mode still read"),
    ("run gstack `/review` before landing", False, "the 3.0.0 wording for the Codex pass"),
    # the two sites that must name the retired skill in order to remove it
    ('REMOVED_SKILLS = ("ios-visual-explore",)', False, "the script's removal roster"),
    ("drops `ios-visual-explore` rows itself.", False, "the skill's one-line mention"),
])
def test_denylist_retires_the_pre_3_0_0_markers_and_removed_surfaces(line, hit, why):
    assert any(p.search(line) for p, _ in lint.DENYLIST) is hit, why


def test_autonomy_block_is_gone_from_every_roster():
    assert "autonomy.md" not in lint.MARKER_BLOCKS
    assert not (BLOCKS / "autonomy.md").exists()
    sync_src = (REPO / "scripts" / "sync-own-claude-md.py").read_text()
    assert '"autonomy.md"' not in sync_src
    script = load("adapt_claude_md2", "scripts/adapt-claude-md.py")
    assert "autonomy.md" not in {b.file for b in script.BLOCKS}


def test_the_roster_is_inside_the_lint_scan():
    """The weekly auto-update writes into roster.md; the file an LLM edits is the
    one that must be scanned for retired names and stale patterns."""
    src = (REPO / "scripts" / "lint-skills.py").read_text()
    assert '"roster.md"' in src
    for name in ("check_refs", "check_upstream_skills"):
        assert name in src
    assert lint.roster_path().is_file()


def test_every_block_file_ends_with_a_newline():
    """`emitted=` is the newline count; a block without a trailing newline would
    be one line short of its own length forever."""
    for f in sorted(BLOCKS.glob("*.md")):
        assert f.read_bytes().endswith(b"\n"), f.name
