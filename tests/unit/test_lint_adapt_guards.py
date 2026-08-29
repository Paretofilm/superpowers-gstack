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
    assert lint.check_adapt_guards(ADAPT_SKILL) == []


def _splice_region(step, old, new, count=1):
    """Rewrite one `### Step N` region of the skill text, leaving the rest alone.

    Mutating the whole file would hit occurrences in other steps and prove the
    wrong thing — the property under test is per-region.
    """
    region = lint.step_regions(ADAPT_SKILL)[step]
    start = ADAPT_SKILL.index(region)
    mutated_region = region.replace(old, new, count)
    assert mutated_region != region, f"{old!r} not found in {step}"
    return ADAPT_SKILL[:start] + mutated_region + ADAPT_SKILL[start + len(region):]


def test_every_guard_needle_matches_exactly_once_in_its_region():
    """The F1 class, closed structurally rather than three times over.

    `cannot attribute this section to a past emitter` and
    `Nothing project-authored was removed.` each occurred twice by 2.49.0 — the
    second copy added by the branch that introduced the guard — and
    `diff .gstack/CLAUDE.md.pre-adapt CLAUDE.md` had occurred twice since 2.48.0.
    A needle matching twice reports the copy, not the site it names: delete the
    guard and the lint stays green.
    """
    regions = lint.step_regions(ADAPT_SKILL)
    for step, needle, why in lint.ADAPT_GUARDS:
        assert regions[step].count(needle) == 1, (
            f"{needle!r} matches {regions[step].count(needle)} times in {step} — "
            f"it no longer pins {why}")


def test_deleting_one_occurrence_of_any_guard_turns_the_lint_red():
    """Not 'the words are gone from the file' — 'this site is gone'. Excision
    tests remove whole regions; this removes exactly what the needle names, which
    is the mutation a reword or a tidy-up actually performs."""
    for step, needle, why in lint.ADAPT_GUARDS:
        errs = lint.check_adapt_guards(_splice_region(step, needle, ""))
        # the lint formats needles with !r, so compare against the same repr —
        # a needle carrying a newline is not a substring of its own message.
        assert any(repr(needle) in e for e in errs), (
            f"deleting {needle!r} from {step} left E13 green")


def test_a_needle_matching_twice_is_reported_rather_than_passing():
    """The other half: a needle can also stop discriminating because someone
    quotes the guard elsewhere in the same step. Silence there is the failure —
    the check has to say the needle stopped pinning its site."""
    step, needle, why = lint.ADAPT_GUARDS[0]
    errs = lint.check_adapt_guards(_splice_region(step, needle, needle + "\n" + needle))
    assert any("2 times" in e and repr(needle) in e for e in errs), errs


def test_every_guard_needle_lives_in_the_step_that_owns_it():
    """Region anchoring is the whole mechanism — assert it directly, so a needle
    quietly re-pointed at a step it does not belong to shows up here."""
    regions = lint.step_regions(ADAPT_SKILL)
    for step, needle, why in lint.ADAPT_GUARDS:
        assert step in regions, f"{step} region missing"
        assert needle in regions[step], f"{needle!r} not in {step} ({why})"


# --- Mutation tests -------------------------------------------------------
#
# E13 claimed to pin four guards and pinned one. Deleting the whole Growth check
# gate left the lint green (the needle `"**Growth check"` also matched the 17
# cross-references); deleting Step 6's mandatory diff item left the lint green
# AND the unit suite passing, and that is the guard that FEEDS the Removed block;
# deleting the snapshot instruction left it green because the path string
# survived elsewhere. A guard that survives its own deletion is decoration.
#
# Each case excises the guard's region from the file text IN MEMORY — the real
# file is never touched — and asserts the lint's own checker reports it.

GUARD_REGIONS = {
    "growth check gate (cross-references left in place)": (
        "**Growth check — applies to every marker-managed section",
        "**Insert or upgrade the Autonomy",
    ),
    "Step 6 mandatory diff item 3": (
        "3. **Diff against the snapshot and classify every removed line.**",
        "Report to the user:",
    ),
    "Step 5 pre-write snapshot instruction": (
        "**Snapshot before the first write.**",
        "**CLAUDE.md updates:**",
    ),
    "Step 6 Removed report block": (
        "> **Removed (not plugin prose):**",
        "**Never omit the Removed block.**",
    ),
    "case-3 attribution check": (
        "**Attribution check — applies to case 3",
        "**Insert or upgrade the Autonomy",
    ),
}


def test_every_case_3_replace_names_an_attribution_sentinel():
    """Six reserved headings are ordinary English a project would plausibly write
    for itself; case 3 used to replace them on the heading alone. Each must now
    name a string only a past emitter would have written into that section."""
    reserved = [
        "**Insert or upgrade the Autonomy and user interruption section.**",
        "**Insert or upgrade the Git hygiene & commit cadence section.**",
        "**Insert or upgrade the Multi-lens review section.**",
        "**Insert or upgrade the Keep the plan true to the code section.**",
        "**Insert or upgrade the Native Apple development tools section.**",
        "**Insert or upgrade the Companion skills (discovery) section.**",
    ]
    for anchor in reserved:
        i = ADAPT_SKILL.index(anchor)
        rule = ADAPT_SKILL[i : ADAPT_SKILL.index("The block to insert:", i)]
        case3 = next(l for l in rule.splitlines()
                     if l.startswith("3. **Heading present + marker absent**"))
        assert "**Attribution check** above" in case3, anchor
        assert "Sentinel: the body contains" in case3, anchor


def excise(text, start_marker, end_marker):
    i = text.index(start_marker)
    j = text.index(end_marker, i)
    mutated = text[:i] + text[j:]
    assert len(mutated) < len(text), "excision removed nothing — markers are stale"
    return mutated


def test_deleting_any_guard_turns_the_lint_red():
    for name, (start, end) in GUARD_REGIONS.items():
        errs = lint.check_adapt_guards(excise(ADAPT_SKILL, start, end))
        assert errs, f"deleting the {name} left E13 green"


def test_deleting_the_gate_is_caught_even_though_the_cross_refs_remain():
    """The specific mutation the old needle missed: 17 `Run the **Growth check**
    above` cross-references still say the words after the gate itself is gone."""
    mutated = excise(ADAPT_SKILL, *GUARD_REGIONS["growth check gate (cross-references left in place)"])
    assert "Run the **Growth check** above" in mutated
    assert any("Growth check" in e for e in lint.check_adapt_guards(mutated))


def test_the_mandatory_diff_must_precede_the_optional_review_gate():
    """Moving it below the yes/no leaves it behind a question users usually
    decline — present in the file, absent from most runs."""
    item = "3. **Diff against the snapshot and classify every removed line.**"
    below = "If the user says yes, run the review:"
    moved = ADAPT_SKILL.replace(item, "3. (moved)").replace(below, f"{item}\n\n{below}")
    assert any("appears after" in e for e in lint.check_adapt_guards(moved))


def test_report_has_a_block_for_what_was_removed():
    """A list of survivors cannot reveal a casualty."""
    assert "**Removed (not plugin prose):**" in ADAPT_SKILL


def test_the_empty_case_has_an_explicit_sentinel():
    """An omitted block reads as 'not checked' — the state it exists to prevent."""
    assert "Nothing project-authored was removed." in ADAPT_SKILL


def test_a_deferral_is_not_reported_as_a_removal():
    """The growth check's non-interactive branch used to file a deferred section
    under 'Removed (not plugin prose)', which the report template defines as
    content actually lost. A deferral lost nothing; it needs its own label."""
    assert "**Deferred (grown past its block, not upgraded):**" in ADAPT_SKILL
    gate = ADAPT_SKILL[ADAPT_SKILL.index("**Growth check — applies"):]
    gate = gate[: gate.index("**Attribution check — applies")]
    rule4 = gate[gate.index("4. **Non-interactive runs**"):]
    assert "**Deferred (grown past its block, not upgraded):**" in rule4
    assert "**Removed (not plugin prose):**" not in rule4


def test_the_snapshot_is_rotated_excluded_and_named_to_the_user():
    """A restore point that the next run overwrites, that git commits, and that
    nobody is told about fails in three separate ways."""
    step5 = lint.step_regions(ADAPT_SKILL)["Step 5"]
    assert 'mv .gstack/CLAUDE.md.pre-adapt ".gstack/CLAUDE.md.pre-adapt.$(date' in step5
    assert "info/exclude" in step5
    assert "cp .gstack/CLAUDE.md.pre-adapt CLAUDE.md" in lint.step_regions(ADAPT_SKILL)["Step 6"]


def test_the_growth_gate_has_a_second_trigger_for_small_blocks():
    """A ratio scales with the block: 1.5x of the 162-line git-hygiene block is 81
    losable lines, of the 23-line companion-skills block 11."""
    gate = ADAPT_SKILL[ADAPT_SKILL.index("**Growth check — applies"):]
    gate = gate[: gate.index("**Attribution check — applies")]
    assert "**Ratio (proxy).**" in gate and "**Volume (proxy).**" in gate
    assert "either" in gate


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
    """E12's invariant, asserted through the lint's own function so the test and
    the rule cannot drift: an undocumented {{TOKEN}} reaches a project's
    CLAUDE.md raw, which PLACEHOLDERS.md's own preamble forbids."""
    import re
    documented = lint.documented_placeholders((BLOCKS / "PLACEHOLDERS.md").read_text())
    for f in sorted(BLOCKS.glob("*.md")):
        if f.name == "PLACEHOLDERS.md":
            continue
        for tok in set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", f.read_text())):
            assert tok in documented, f"{f.name}: {{{{{tok}}}}} undocumented"


def test_a_placeholder_heading_with_no_body_is_not_documentation():
    """The empty case E12 used to accept: a heading names the token and gives the
    generator nothing to resolve it with, which emits it verbatim exactly as if
    the entry did not exist."""
    empty = "# Placeholders\n\n## `{{EMPTY_TOKEN}}` (somewhere)\n\n## `{{REAL_TOKEN}}`\n\nRun `echo hi`.\n"
    assert lint.documented_placeholders(empty) == {"REAL_TOKEN"}


def test_the_simulator_fallback_keeps_a_parenthesised_model_name_whole():
    """`iPhone SE (3rd generation)` is the device's exact name. A pattern anchored
    on the first '(' truncates it to `iPhone SE`, which no simulator is called —
    so the placeholder emits the destination error it exists to prevent."""
    import re as _re
    import subprocess
    ph = (BLOCKS / "PLACEHOLDERS.md").read_text()
    fallback = _re.search(r"^ +(xcrun simctl list devices available \| sed -nE "
                          r"'s/\^ \*\(iPhone \.\*\).*?/p'.*)$", ph, _re.M)
    assert fallback, "the {{IOS_SIMULATOR}} fallback command is not in PLACEHOLDERS.md"
    line = "    iPhone SE (3rd generation) (AABBCCDD-1122-3344-5566-778899AABBCC) (Shutdown) \n"
    out = subprocess.run(["bash", "-c", fallback.group(1).replace(
        "xcrun simctl list devices available", "cat")], input=line,
        capture_output=True, text=True).stdout.strip()
    assert out == "iPhone SE (3rd generation)", out


def test_denylist_catches_a_hardcoded_simulator_model():
    line = "`xcodebuild -scheme X -destination 'platform=iOS Simulator,name=iPhone 16' build`"
    assert any(p.search(line) for p, _ in lint.DENYLIST)


def test_preserve_and_insert_tells_the_user_how_to_undo_it():
    """A user who sees two sections and no reason will not know that deleting one
    and re-running /adapt is the whole fix."""
    assert "cannot attribute this section to a past emitter" in ADAPT_SKILL
    assert "delete your copy and re-run" in ADAPT_SKILL


def test_both_generators_record_the_emitted_line_count():
    """Provenance rides in a SECOND comment beside the marker, never inside it.
    Inside, `<!-- gstack-autonomy-v2 -->` stops being a substring of what was
    written, and every reader that only knows the bare form — an older plugin
    cache, lint E8 — reads the section as markerless."""
    setup = (REPO / "skills" / "setup-routing" / "SKILL.md").read_text()
    for text, who in ((ADAPT_SKILL, "adapt"), (setup, "setup-routing")):
        assert "`<N>` is `wc -l` of the block file you just read" in text, (
            f"{who} does not say how to count `<N>`")
        assert "<!-- gstack-git-hygiene-v9 --><!-- emitted=162 -->" in text, (
            f"{who} does not show provenance as a second comment beside the marker")


def test_neither_generator_writes_provenance_inside_the_marker():
    """The shape this release rejected. `<!-- gstack-x-vN emitted=N -->` is not a
    superstring of `<!-- gstack-x-vN -->`, so a 2.48.0 cache takes the marker for
    absent and either replaces the section or duplicates it."""
    import re
    setup = (REPO / "skills" / "setup-routing" / "SKILL.md").read_text()
    bad = re.compile(r"<!-- gstack-[a-z-]+-v[\dN]+ +emitted=")
    for text, who in ((ADAPT_SKILL, "adapt"), (setup, "setup-routing")):
        assert not bad.search(text), f"{who} writes the attribute inside the marker"


def test_block_files_never_carry_the_emitted_attribute():
    """`emitted=` is written by a generator into a project's CLAUDE.md. In a block
    file it would be a constant that lies the moment the block changes length."""
    for f in sorted(BLOCKS.glob("*.md")):
        assert "emitted=" not in f.read_text().split("\n", 1)[0], f"{f.name} line 1"


def _growth_gate():
    gate = ADAPT_SKILL[ADAPT_SKILL.index("**Growth check"):]
    return gate[: gate.index("**Insert or upgrade the Autonomy")]


def test_growth_check_reads_provenance_alongside_the_two_proxies():
    """Provenance may only ADD a reason to stop. The first cut made it exclusive —
    "use it whenever it is available and ignore the two triggers below" — which
    means one wrong `<N>` silences all three at once, and `<N>` is a number a past
    run wrote with nothing verifying it. A trigger that fires when it should not
    costs one question; one that stays quiet costs the user their writing."""
    gate = _growth_gate()
    assert "**Provenance (measured, not inferred).**" in gate
    assert "emitted=" in gate
    assert "it adds a\nreason to stop; it never removes one" in gate
    assert "ignore the two triggers below" not in gate, "exclusive precedence is back"
    # the proxies must still be reachable for sections written before 2.49.0
    assert "1.5×" in gate and "no `emitted=`" in gate


def test_an_implausible_emitted_count_is_distrusted():
    """`emitted=212` on a 200-line section must not be able to silence the gate."""
    gate = _growth_gate()
    assert "**Distrust an implausible `<N>`.**" in gate
    assert "at or below `<N>`" in gate


def test_the_gate_thresholds_are_pinned():
    """Each number pinned AT ITS OWN SITE, in the sentence that uses it.

    The first cut of this test sliced the whole gate and asserted `"1.5×" in gate`
    and `"~20" in gate`. The slice held `1.5×` three times and `~20` twice, so
    Ratio's 1.5 could become 15, Volume's ~20 could become ~30, and Provenance's
    ~20 could become ~50, each with this test green — verified by making all three
    edits. A threshold is pinned when changing IT fails, not when some other
    sentence still quotes the old number. Tuning any of them is fine; updating the
    matching line here is how you record that you meant to.
    """
    gate = _growth_gate()

    def between(start, end):
        i = gate.index(start)
        return gate[i : gate.index(end, i)]

    prov = between("- **Provenance (measured, not inferred).**", "- **Ratio (proxy).**")
    assert "now more than **~20** lines longer than `<N>`" in prov
    assert "more than ~20 lines ABOVE the block" in prov, "the distrust band"

    ratio = between("- **Ratio (proxy).**", "- **Volume (proxy).**")
    assert "more than **1.5×** the block's line count" in ratio

    volume = between("- **Volume (proxy).**", "A section with no `emitted=`")
    assert "more than ~20 of the section's lines" in volume


def test_session_continuity_explains_a_preserve_the_same_way():
    """Task 1 gave the shared Attribution check a report that says why a section was
    not upgraded and what undoes it. Session Continuity reaches the same state by its
    own route, and a user cannot tell which branch produced their two sections."""
    rule = ADAPT_SKILL[ADAPT_SKILL.index("**Insert or upgrade the Session Continuity"):]
    rule = rule[: rule.index("blocks/session-continuity.md")]
    assert "merge by hand" not in rule, "still carries the pre-Task-1 phrasing"
    assert "delete your copy and re-run" in rule


def test_step6_order_rule_does_not_depend_on_a_question_s_wording():
    lint_src = (REPO / "scripts" / "lint-skills.py").read_text()
    assert "Would you like me to run a comprehensive review" not in lint_src, (
        "the order rule anchors on prose a copy-edit would break"
    )


def test_step6_order_check_fails_closed_when_its_anchor_is_gone():
    """The check used to read `if first in region and second in region:` — when
    an edit made either anchor disappear, the comparison was skipped rather than
    flagged, so the guard's own removal read exactly like the guard passing. A
    missing anchor must now be its own error, not silence."""
    start = ADAPT_SKILL.index("### Step 6")
    end = ADAPT_SKILL.index("### Step 7", start)
    region = ADAPT_SKILL[start:end]
    marker = "**STOP HERE.**"
    assert region.count(marker) == 1
    mutated_region = region.replace(marker, "**STOP.**")
    assert mutated_region != region, "rename did not change the text"
    mutated = ADAPT_SKILL[:start] + mutated_region + ADAPT_SKILL[end:]

    errs = lint.check_adapt_guards(mutated)
    assert any("ordering anchor" in e and repr(marker) in e for e in errs), errs


def test_ordering_rule_naming_a_missing_step_is_not_silent():
    """The `continue` on a missing region used to be justified by a comment
    claiming the step was already reported upstream. It was not: that upstream
    loop only scans the steps ADAPT_GUARDS names, so a step that appears solely
    in ADAPT_GUARD_ORDER was skipped with no error at all. Simulated here by
    knocking out the `### Step 6` heading an existing ordering entry depends on
    — from the checker's point of view that step now "appears solely in
    ADAPT_GUARD_ORDER", since ADAPT_GUARDS's own missing-heading loop reports it
    too, but under a different message than the one this test pins."""
    heading = "### Step 6: Verify and report"
    assert ADAPT_SKILL.count(heading) == 1
    mutated = ADAPT_SKILL.replace(heading, "### Step Six: Verify and report")
    assert mutated != ADAPT_SKILL, "rename did not change the text"

    errs = lint.check_adapt_guards(mutated)
    assert any("ordering rule names 'Step 6'" in e for e in errs), errs
