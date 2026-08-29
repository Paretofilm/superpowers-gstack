# /adapt Provenance and Pinning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `/adapt`'s length-heuristic guess about who wrote a section with a fact the plugin records at emit time, and pin the two lint holes worth pinning.

**Architecture:** The growth check currently infers authorship from a line-count ratio, which is a proxy for the thing it actually wants to know: *how much has this section grown since the plugin wrote it?* That number stops being a guess the moment the plugin records what it emitted. Each emitted marker gains an `emitted=<N>` attribute — the block's line count at emit time — so the next upgrade computes provable growth (`current − emitted`) instead of a ratio against a block whose size drifts between releases. Sections emitted before this change carry no attribute and fall back to the existing ratio-and-volume triggers, so nothing regresses. Two lint holes left parked at 2.48.0 get closed; one stays parked with its reason restated.

**Tech Stack:** Markdown instruction files (`skills/adapt/SKILL.md`, `skills/setup-routing/SKILL.md`, `skills/setup-routing/blocks/*.md`), Python 3 lint (`scripts/lint-skills.py`), pytest (`tests/unit/`).

**Spec:** No separate spec. This plan implements three items carried forward from 2.48.0's review, recorded in that release's CHANGELOG and merge commit `9745907`: the deferred F8 ("the 1.5× ratio is the wrong signal"), and two of the three lint holes parked at the review breaker.

---

## Global Constraints

- **Lint green after every task.** `python3 scripts/lint-skills.py` exits 0. Two warnings are expected and are NOT errors: `W2 adapt` and `W2 swiftui-design-consultation`.
- **Unit tests pass after every task.** `pytest tests/unit -q` — **249 passed** when this plan was written; 250 after Task 1. Counts below are measured, not predicted — if yours differs, say so rather than assuming the plan is right.
- **The integration test costs real API credits.** Run it exactly once, in Task 5. Never in a loop.
- **Lint E8 governs block files, not emitted sections.** Line 1 of every marker block must keep matching `^## .*<!-- gstack-[a-z-]+-v\d+ -->$`. **Block files keep the bare marker** — the `emitted=` attribute is added by the generators at write time and appears only in a project's CLAUDE.md. A block file carrying `emitted=` is a bug.
- **E13 needles are contract strings.** Adding prose near one is safe; rewording the needle itself turns the lint red on purpose.
- **Version:** `.claude-plugin/plugin.json` `2.48.0` → `2.49.0`, with a matching `## [2.49.0]` CHANGELOG entry (lint E4 refuses otherwise).
- **Marker version bumps:** none. This changes what generators *write around* a marker, not the markers themselves. No `DENYLIST` range updates.
- **Branch first:** `git switch -c feat/adapt-emitted-provenance` off `main`. Never `git commit --no-verify`; stage by explicit path.

---

## What the evidence already settles

Measured on 2026-08-29 before writing this plan, so no task re-derives it:

- **The attribution check's behaviour change is a no-op on this machine.** Six adapted projects under `~/Developer` (`swiftconfig`, `FagfilmYrkeMontasje`, `live-swiftui`, `sing-replay`, `receipts-collector`, plus three worktree copies), on plugin versions 2.34.1 through 2.47.0. In every one, the count of plugin-managed headings equals the count of markers — **zero markerless sections**. Case 3 cannot fire on any of them, so the 2.48.0 change from REPLACE to PRESERVE reaches none of this user's work.
- **Two sections have a genuine marker-to-sentinel gap.** `autonomy` (marker 2026-05-18, sentinel `The only five reasons to stop and ask` 2026-07-05) and `multi-lens-review` (marker 2026-05-19, sentinel `What counts as ship-worthy` 2026-07-05). The other four gained marker and sentinel the same day.
- **Why that gap is nearly harmless, and where it isn't.** Case 3 fires only when the marker is *absent*, i.e. on content emitted before the marker existed. For a section emitted in that window, the sentinel is absent too, so `/adapt` now preserves it and inserts the block beside it instead of upgrading it. That is the safe failure the attribution check was designed to accept — a stale section costs one `/adapt` run after the user deletes it. It cannot reach this user (no markerless sections anywhere), but the plugin is published, so other users on pre-2.34 adaptations can hit it. Task 1 makes it visible rather than silent.

---

## File Structure

| File | Change | Responsibility after the change |
|---|---|---|
| `skills/setup-routing/SKILL.md` | Emit `emitted=<N>` when writing each marker | New projects record provenance from birth |
| `skills/adapt/SKILL.md` | Emit `emitted=<N>`; tolerate it when scanning; add the authoritative growth trigger; report the preserve-and-insert outcome | The only file that both reads and writes provenance |
| `scripts/lint-skills.py` | Two E13 needles; the Step 6 order rule re-anchored; a threshold-pinning check; a block-file purity check | Release gate |
| `tests/unit/test_lint_adapt_guards.py` | Tests for each of the above | Proves each new rule can fail |
| `tests/fixtures/adapt-growth/CLAUDE.md` | A second fixture section carrying `emitted=` | Exercises the authoritative trigger end to end |
| `tests/integration/test_adapt_growth_gate.sh` | One added assertion | Proves the trigger fires on a real run |
| `.claude-plugin/plugin.json`, `CHANGELOG.md` | 2.49.0 | Release gate |

---

### Task 1: Make the un-upgradable section visible instead of silent

The attribution check accepts one failure to avoid a worse one: a genuinely emitted pre-marker section whose sentinel postdates it gets preserved rather than upgraded. That trade is right. What is wrong is that the user is told two sections now exist without being told *why*, or that the fix is one deletion away.

**Files:**
- Modify: `skills/adapt/SKILL.md` — the **Attribution check** block's "Sentinel absent" bullet
- Modify: `scripts/lint-skills.py` — `ADAPT_GUARDS`
- Test: `tests/unit/test_lint_adapt_guards.py`

**Interfaces:**
- Produces: the contract string `cannot attribute this section to a past emitter`, pinned by E13 and reused by no later task.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_lint_adapt_guards.py`:

```python
def test_preserve_and_insert_tells_the_user_how_to_undo_it():
    """A user who sees two sections and no reason will not know that deleting one
    and re-running /adapt is the whole fix."""
    assert "cannot attribute this section to a past emitter" in ADAPT_SKILL
    assert "delete your copy and re-run" in ADAPT_SKILL
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: FAIL — 1 failed, the rest passing.

- [ ] **Step 3: Rewrite the "Sentinel absent" bullet**

In `skills/adapt/SKILL.md`, replace this bullet of the **Attribution check**:

```markdown
- **Sentinel absent** → you cannot attribute the section to a past emitter. Do NOT
  replace it. Leave it byte-for-byte intact, insert the plugin block as a separate H2
  section immediately below it, and say in the report that both now exist and which
  one is theirs, so they can merge by hand.
```

with:

```markdown
- **Sentinel absent** → you cannot attribute the section to a past emitter. Do NOT
  replace it. Leave it byte-for-byte intact, insert the plugin block as a separate H2
  section immediately below it, and report the outcome in these terms:

  > `<heading>`: I cannot attribute this section to a past emitter — it has no version
  > marker and none of the phrases an older `/adapt` would have written. I left it
  > exactly as it was and put the current plugin version below it, so nothing of yours
  > was touched. If it *is* an old plugin section, delete your copy and re-run
  > `/adapt` and it will upgrade cleanly.

  Two sections sharing a heading is a state the user has to resolve, so tell them
  which one is theirs and what resolves it. A report that only says "both now exist"
  leaves them to work out both.
```

- [ ] **Step 4: Add the E13 needle**

In `scripts/lint-skills.py`, add to `ADAPT_GUARDS`:

```python
    ("Step 5", "cannot attribute this section to a past emitter",
     "the report line that turns a two-sections-now-exist state into an actionable one"),
```

- [ ] **Step 5: Verify both pass**

Run: `python3 scripts/lint-skills.py && pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: lint `0 error(s)`; 250 passed.

- [ ] **Step 6: Commit**

```bash
git add skills/adapt/SKILL.md scripts/lint-skills.py tests/unit/test_lint_adapt_guards.py
git commit -m "fix(adapt): say why a section was not upgraded, and what undoes it

The attribution check preserves a section it cannot attribute and inserts the
block beside it. Two sections then share a heading, which the user has to
resolve — and the report told them only that both exist.

Measured before writing this: two sections have a real marker-to-sentinel gap
(autonomy, multi-lens-review — markers from mid-May, sentinels from 2026-07-05),
so a pre-marker emitted copy of either is preserved rather than upgraded. That
is the safe failure the check was designed to accept. It should not also be a
silent one."
```

---

### Task 2: Record what the plugin emitted

**Files:**
- Modify: `skills/setup-routing/SKILL.md` — the block-emission instruction
- Modify: `skills/adapt/SKILL.md` — the **Shared block files** paragraph
- Modify: `scripts/lint-skills.py` — a block-file purity check (new **E14**)
- Test: `tests/unit/test_lint_adapt_guards.py`

**Interfaces:**
- Produces: the emitted-marker form `<!-- gstack-<name>-vN emitted=<N> -->`, consumed by Tasks 3 and 4. `<N>` is the block file's line count, counted the way `wc -l` counts it, excluding nothing.
- Lint E-numbers in use: E1–E8, E10–E13. This task adds **E14**.

- [ ] **Step 1: Write the failing test**

```python
def test_both_generators_record_the_emitted_line_count():
    setup = (REPO / "skills" / "setup-routing" / "SKILL.md").read_text()
    for text, who in ((ADAPT_SKILL, "adapt"), (setup, "setup-routing")):
        assert "emitted=<N>" in text, f"{who} does not record provenance"


def test_block_files_never_carry_the_emitted_attribute():
    """`emitted=` is written by a generator into a project's CLAUDE.md. In a block
    file it would be a constant that lies the moment the block changes length."""
    for f in sorted(BLOCKS.glob("*.md")):
        assert "emitted=" not in f.read_text().split("\n", 1)[0], f"{f.name} line 1"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: FAIL on `test_both_generators_record_the_emitted_line_count` (the purity test passes already — that is correct, it is a regression guard, and Step 5 proves it can fail).

- [ ] **Step 3: Instruct both generators to record it**

In **`skills/adapt/SKILL.md`**, append to the **Shared block files** paragraph:

````markdown
**Record what you emitted.** When you write a block into CLAUDE.md, append the block
file's line count to the marker on the heading line, as ` emitted=<N>`:

```
## Git hygiene & commit cadence <!-- gstack-git-hygiene-v9 emitted=162 -->
```

`<N>` is `wc -l` of the block file you just read, before any placeholder substitution
and before any heading-level demote — the count as it ships. This is the only fact that
makes a later upgrade able to tell growth from a block that simply changed size, so do
not estimate it and do not carry a stale value forward from the section you replaced.
Block files themselves never carry `emitted=`; a constant baked into the source would
lie the moment the block changed length.
````

In **`skills/setup-routing/SKILL.md`**, add the same instruction where it emits blocks. Read the file and place it beside the existing block-emission wording; the text above is exact and both generators must carry it identically — lint E8's single-source rule does not cover generator prose, so this is the one place the two are hand-kept in step, and the test above is what keeps them there.

- [ ] **Step 4: Add lint E14**

In `scripts/lint-skills.py`, after the E13 block:

```python
    # E14 block files never carry the emitted= attribute (2.49.0). The count is a
    # fact about one emission, written by a generator into one project's CLAUDE.md.
    # Baked into the block file it becomes a constant that goes stale the next time
    # anyone edits the block — and a stale provenance number is worse than none,
    # because the growth check would trust it.
    if blocks_dir.is_dir():
        for f in sorted(blocks_dir.glob("*.md")):
            if "emitted=" in f.read_text().split("\n", 1)[0]:
                errors.append(
                    f"E14 {BLOCKS_DIR_REL}/{f.name}: line 1 carries `emitted=` — that "
                    f"attribute is written per-emission by the generators, never stored "
                    f"in the source block")
```

Document it in the module docstring's ERRORS list, after E13:

```
  E14 no block file carries the `emitted=` marker attribute. Generators write that
      count into a project's CLAUDE.md at emit time; stored in the source it is a
      constant that goes stale on the next edit, and the growth check would trust it.
```

- [ ] **Step 5: Prove E14 can fail**

Run:

```bash
cp skills/setup-routing/blocks/autonomy.md /tmp/autonomy.bak
sed -i '' '1s/-->/emitted=31 -->/' skills/setup-routing/blocks/autonomy.md
python3 scripts/lint-skills.py 2>&1 | grep -E "E14|error\(s\)"
cp /tmp/autonomy.bak skills/setup-routing/blocks/autonomy.md && rm /tmp/autonomy.bak
python3 scripts/lint-skills.py 2>&1 | tail -1
```

Expected: the mutated run prints an `E14` line, and `3 error(s)` in total — measured, not
predicted. The same `sed` also breaks E8 (its marker regex needs `-->` immediately after the
digits, which ` emitted=31` displaces) and cascades to E11, because `autonomy.md` is in
`sync-own-claude-md.py`'s `UNIVERSAL` list, so this repo's own CLAUDE.md embeds it and goes
stale. E14 firing is what the step proves; the other two are the blast radius of a
deliberately malformed marker. The restored run prints `0 error(s)`. Paste both into your report — a guard nobody has seen fail is a guard nobody has tested.

- [ ] **Step 6: Verify and commit**

Run: `python3 scripts/lint-skills.py && pytest tests/unit -q`
Expected: lint `0 error(s)`; 252 passed.

```bash
git add skills/adapt/SKILL.md skills/setup-routing/SKILL.md scripts/lint-skills.py tests/unit/test_lint_adapt_guards.py
git commit -m "feat(blocks): record the block's line count in the emitted marker

The growth check asks how much a section has grown since the plugin wrote it,
and answers with a ratio against the CURRENT block — a number that moves when
the block moves, for reasons that have nothing to do with the user.

Emitted markers now carry emitted=<N>, the block's line count at the moment it
was written. Next upgrade subtracts. Lint E14 keeps the attribute out of the
source blocks, where it would be a constant that goes stale on the next edit."
```

---

### Task 3: Read provenance when scanning, and keep matching sections that lack it

An emitted marker now has two shapes. Every scan in `/adapt` must match both, or the first `/adapt` after this release stops recognising the sections it just wrote.

**Files:**
- Modify: `skills/adapt/SKILL.md` — the nine `**Insert or upgrade …**` scan lines
- Modify: `scripts/lint-skills.py` — `ADAPT_GUARDS`
- Test: `tests/unit/test_lint_adapt_guards.py`

**Interfaces:**
- Consumes: the emitted-marker form from Task 2.
- Produces: the contract string `optionally followed by ` emitted=<N>``, pinned by E13 and read by Task 4.

- [ ] **Step 1: Write the failing test**

```python
import re


def test_every_scan_rule_tolerates_the_provenance_attribute():
    """Nine rules scan for a marker. After 2.49.0 an emitted marker may carry
    `emitted=`; a rule that matches only the bare form stops recognising the very
    sections this release writes."""
    scans = re.findall(r"its version marker `<!-- gstack-[a-z-]+-vN[^`]*`", ADAPT_SKILL)
    assert len(scans) >= 8, f"expected the scan rules, found {len(scans)}"
    for s in scans:
        assert "emitted" in s, f"scan rule does not tolerate provenance: {s}"


def test_the_tolerance_is_stated_once_in_prose_too():
    assert "optionally followed by ` emitted=<N>`" in ADAPT_SKILL
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: FAIL — 2 failed.

- [ ] **Step 3: State the tolerance once**

In `skills/adapt/SKILL.md`, immediately after the **Record what you emitted** paragraph from Task 2, add:

```markdown
**Reading a marker.** An emitted marker is `<!-- gstack-<name>-vN -->`, optionally
followed by ` emitted=<N>` before the closing `-->`. Every scan below must match both
forms: sections written before 2.49.0 have no attribute, and a scan that accepts only
the bare form would fail to recognise the sections this very release writes — turning
every one of them into a case 4 "heading absent" and appending a duplicate block.
Match the marker by its `gstack-<name>-v<digits>` prefix, never by the whole comment.
```

- [ ] **Step 4: Update the nine scan lines**

Each of the nine rules contains a phrase of this shape:

```
and its version marker `<!-- gstack-autonomy-vN -->`
```

Change each to:

```
and its version marker `<!-- gstack-autonomy-vN -->` (optionally followed by ` emitted=<N>`)
```

Substitute the correct marker name per section: `gstack-autonomy-vN`, `gstack-git-hygiene-vN`, `gstack-multi-lens-review-vN`, `gstack-code-reuse-vN`, `gstack-plan-fidelity-vN`, `gstack-session-continuity-vN`, `gstack-routing-vN`, `gstack-xcode-tools-vN`, `gstack-companion-skills-vN`. Read each rule in the live file — their wording is not uniform, and `Track-aware routing`'s is a multi-line indented list.

- [ ] **Step 5: Add the E13 needle**

```python
    ("Step 5", "optionally followed by ` emitted=<N>`",
     "the rule that stops a post-2.49.0 marker being read as no marker at all"),
```

- [ ] **Step 6: Verify and commit**

Run: `python3 scripts/lint-skills.py && pytest tests/unit -q`
Expected: lint `0 error(s)`; 254 passed.

```bash
git add skills/adapt/SKILL.md scripts/lint-skills.py tests/unit/test_lint_adapt_guards.py
git commit -m "fix(adapt): match a marker by its prefix, not the whole comment

Nine scan rules matched the bare marker exactly. With provenance appended, each
would have read a section this release just wrote as having no marker at all,
fired case 4, and appended a duplicate block below the original."
```

---

### Task 4: Make provenance the primary growth signal

**Files:**
- Modify: `skills/adapt/SKILL.md` — the **Growth check** block
- Modify: `scripts/lint-skills.py` — `ADAPT_GUARDS`, plus the threshold-pinning check
- Test: `tests/unit/test_lint_adapt_guards.py`

**Interfaces:**
- Consumes: `emitted=<N>` (Task 2), read via the tolerant scan (Task 3).
- Produces: the contract string `**Provenance (authoritative).**`.

- [ ] **Step 1: Write the failing test**

```python
def test_growth_check_prefers_provenance_over_the_ratio():
    gate = ADAPT_SKILL[ADAPT_SKILL.index("**Growth check"):]
    gate = gate[: gate.index("**Insert or upgrade the Autonomy")]
    assert "**Provenance (authoritative).**" in gate
    assert "emitted=" in gate
    # the ratio must still be reachable for sections written before 2.49.0
    assert "1.5×" in gate and "no `emitted=`" in gate


def test_the_gate_thresholds_are_pinned():
    """A parked 2.48.0 finding: the test asserted only that the Ratio and Volume
    labels existed, so 1.5x could become 15x and stay green. Tuning these is fine —
    updating this test is how you record that you meant to."""
    gate = ADAPT_SKILL[ADAPT_SKILL.index("**Growth check"):]
    gate = gate[: gate.index("**Insert or upgrade the Autonomy")]
    assert "1.5×" in gate
    assert "~20" in gate
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: FAIL on `test_growth_check_prefers_provenance_over_the_ratio` (the threshold test passes today — that is correct; it is the parked hole being closed, and it fails the moment someone edits a number without editing it).

- [ ] **Step 3: Add the authoritative trigger**

In `skills/adapt/SKILL.md`, inside the **Growth check**, insert this immediately before the existing Ratio trigger:

````markdown
**Provenance (authoritative).** If the section's marker carries ` emitted=<N>`, the
plugin wrote exactly `<N>` lines there. Count the section now; anything above `<N>` was
added by someone else. Fire the gate when the section exceeds `<N>` by more than **~20**
lines:

```bash
awk 'NR>=<start> && NR<=<end>' CLAUDE.md | wc -l     # what is there now
```

This is not a heuristic and it does not care what the block's current size is, so use it
whenever it is available and ignore the two triggers below. A block that grew or shrank
between releases moves the ratio; it cannot move `<N>`.

**When there is no `emitted=`** — every section written before 2.49.0 — fall back to the
two triggers below. They are proxies, and they are why provenance exists.
````

Then retitle the two existing triggers so the precedence is legible: `**Ratio (fallback).**` and `**Volume (fallback).**`. Leave their thresholds and their honest note about what a length heuristic cannot establish exactly as they are.

- [ ] **Step 4: Add the E13 needle**

```python
    ("Step 5", "**Provenance (authoritative).**",
     "the trigger that reads what the plugin actually wrote, not a ratio against a moving block"),
```

- [ ] **Step 5: Verify and commit**

Run: `python3 scripts/lint-skills.py && pytest tests/unit -q`
Expected: lint `0 error(s)`; 256 passed.

```bash
git add skills/adapt/SKILL.md scripts/lint-skills.py tests/unit/test_lint_adapt_guards.py
git commit -m "feat(adapt): decide growth from what was emitted, not from a ratio

git-hygiene.md is 162 lines, so 81 lines of user content could hide under a
1.5x gate; companion-skills.md is 23, so 11. Same threshold, seven times the
exposure — because the ratio measures the block, not the user.

Where emitted=<N> is present the gate now subtracts and asks one question:
is there more here than the plugin put here? The ratio and volume triggers
stay for sections written before this release, retitled as the fallbacks
they now are. Also pins both thresholds, closing a hole parked at 2.48.0:
the test asserted the labels existed, so 1.5x could have become 15x and
stayed green."
```

---

### Task 5: Prove it on a real run

**Files:**
- Modify: `tests/fixtures/adapt-growth/CLAUDE.md`
- Modify: `tests/integration/test_adapt_growth_gate.sh`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Add a provenance-bearing section to the fixture**

The fixture's existing `Native Apple development tools` section stays exactly as it is — it is the no-provenance path, and it must keep passing.

Add a **second** grown section that carries provenance. Its heading:

```markdown
## Git hygiene & commit cadence <!-- gstack-git-hygiene-v9 emitted=162 -->
```

Give it ~200 lines of realistic, unmistakably project-authored git conventions for this
fictional Swift app — branch naming, what the team does about force-pushes, a
release-tagging convention, why they never rebase a shared branch. Include five lines
`PROV-SENTINEL-001` … `005`, spread through it, each stating a specific project fact.
Do not copy text from `skills/setup-routing/blocks/git-hygiene.md`: content matching the
block is content the diff correctly reads as plugin prose, which blunts the test.

Note the shape of this case: the marker is `v9`, the **current** version, so cases 2 and
3 do not fire and only the provenance trigger can catch it. `emitted=162` against ~200
present lines is ~38 over, comfortably past ~20. Against the ratio it is 200/162 = 1.23×
— **below** the 1.5× fallback. That is the point: this section is invisible to the old
signal and visible to the new one.

- [ ] **Step 2: Add the assertion**

In `tests/integration/test_adapt_growth_gate.sh`, after the existing assertions:

```bash
# 5. The provenance trigger fired: a section at 1.23x the block — invisible to the
#    ratio fallback — was caught because emitted=162 says the plugin wrote 162 lines
#    and ~200 are there now.
MISSING_PROV=0
for n in 001 002 003 004 005; do
  grep -q "PROV-SENTINEL-$n" "$WORK/CLAUDE.md" || { echo "  lost PROV-SENTINEL-$n"; MISSING_PROV=1; }
done
[ "$MISSING_PROV" -eq 0 ]; assert "provenance-marked section survives at 1.23x, below the ratio fallback" $?
```

- [ ] **Step 3: Run the integration test — once**

Run: `bash tests/integration/test_adapt_growth_gate.sh`
Expected: exit 0, five assertions passing.

If assertion 5 fails while the others pass, the provenance trigger did not fire. Report
it and stop — **do not** grow the fixture to push it past the ratio fallback, which
would hide exactly the case the task exists to prove.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/adapt-growth/CLAUDE.md tests/integration/test_adapt_growth_gate.sh
git commit -m "test(adapt): prove the provenance trigger catches what the ratio cannot

The new fixture section is 1.23x its block — under the 1.5x fallback, so the
old signal is blind to it — and 38 lines above its emitted=162. One section
per path in one run: the old one keeps the fallback honest, the new one
proves provenance does something the fallback could not."
```

---

### Task 6: Re-anchor the Step 6 order rule

The second of the two lint holes worth closing. E13's Step 6 ordering rule anchors on the text of a user-facing question; rewording that question makes the rule inert, after which the mandatory diff could be moved below the optional gate and stay green.

**Files:**
- Modify: `scripts/lint-skills.py`
- Test: `tests/unit/test_lint_adapt_guards.py`

- [ ] **Step 1: Write the failing test**

```python
def test_step6_order_rule_does_not_depend_on_a_question_s_wording():
    lint_src = (REPO / "scripts" / "lint-skills.py").read_text()
    assert "Would you like me to run a comprehensive review" not in lint_src, (
        "the order rule anchors on prose a copy-edit would break"
    )
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: FAIL — 1 failed.

- [ ] **Step 3: Re-anchor on the structural marker**

Read the Step 6 order rule in `scripts/lint-skills.py`. Replace the
`"Would you like me to run a comprehensive review"` anchor with `"**STOP HERE.**"`,
which is the structural boundary between the mandatory part of Step 6 and the optional
review — it is an instruction to the agent, not copy shown to a user, so an editor
polishing the question no longer silently disarms the rule.

Verify the marker is unique within Step 6 before relying on it:

```bash
awk '/^### Step 6/,/^### Step 7/' skills/adapt/SKILL.md | grep -c '\*\*STOP HERE\.\*\*'
```

Expected: `1`. If it is not 1, pick the nearest unique structural anchor and say in your report which and why.

- [ ] **Step 4: Prove the rule still catches the reordering it exists to catch**

Move Step 6's mandatory diff item below the `**STOP HERE.**` line in a temp copy, run the lint, confirm it goes red, restore. Paste both outputs into your report.

- [ ] **Step 5: Verify and commit**

Run: `python3 scripts/lint-skills.py && pytest tests/unit -q`
Expected: lint `0 error(s)`; 257 passed.

```bash
git add scripts/lint-skills.py tests/unit/test_lint_adapt_guards.py
git commit -m "fix(lint): anchor the Step 6 order rule to structure, not to a question

The rule keyed on the wording of a question shown to the user. A copy-edit
would have made it inert, and the mandatory diff could then have moved below
the optional gate while the lint stayed green. Parked at 2.48.0; the fix is
to anchor on **STOP HERE.**, which is addressed to the agent."
```

---

### Task 7: Release

- [ ] **Step 1: Bump the version**

`.claude-plugin/plugin.json`: `2.48.0` → `2.49.0`.

- [ ] **Step 2: Confirm E4 fires**

Run: `python3 scripts/lint-skills.py`
Expected: FAIL with `E4 CHANGELOG.md: no entry for plugin.json version 2.49.0`.

- [ ] **Step 3: Write the CHANGELOG entry**

Insert under `# Changelog`:

```markdown
## [2.49.0] - 2026-08-29

2.48.0 gave `/adapt` guards against destroying a project's own notes, and left one
question answered by a guess: has this section grown since the plugin wrote it? It
answered with a ratio against the block's *current* size, which moves for reasons that
have nothing to do with the user. `git-hygiene.md` is 162 lines, so 81 lines of hand-
written content could sit under a 1.5× gate; `companion-skills.md` is 23, so 11. Same
threshold, seven times the exposure.

### Changed — provenance replaces the guess
- **Emitted markers now record what was emitted:** `<!-- gstack-git-hygiene-v9 emitted=162 -->`.
  The growth check subtracts instead of dividing, and fires when a section is more than
  ~20 lines above what the plugin actually wrote. It no longer cares what the block
  weighs today.
- **The ratio and volume triggers remain**, retitled as the fallbacks they now are, for
  every section written before this release. Both thresholds are pinned by a test —
  tuning them is fine, and updating that test is how you record that you meant to.
- **All nine scan rules match a marker by its prefix**, so a section this release writes
  is not read by the next run as having no marker at all.
- **Lint E14** keeps `emitted=` out of the source blocks, where it would be a constant
  that goes stale on the next edit — and a stale provenance number is worse than none,
  because the gate would trust it.

### Fixed
- **A section `/adapt` cannot attribute is no longer silently un-upgraded.** It says
  which section, why, that nothing of theirs was touched, and that deleting their copy
  and re-running upgrades it cleanly. Two sections sharing a heading is a state the user
  has to resolve; they were being told only that it existed.
- **The Step 6 ordering rule anchors on structure rather than on a question's wording**
  — a copy-edit would have disarmed it, after which the mandatory diff could have moved
  below the optional gate with the lint still green. Parked at 2.48.0, closed here.
```

- [ ] **Step 4: Run the full gate**

Run: `python3 scripts/lint-skills.py && pytest tests/unit -q`
Expected: lint `0 error(s)` with the two known `W2` warnings; 257 passed. Do **not** re-run the integration test — Task 5 ran it.

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/plugin.json CHANGELOG.md
git commit -m "chore: release 2.49.0 — provenance-based growth detection"
```

- [ ] **Step 6: Multi-lens verification**

Ship-worthy and high-stakes: this changes the emitted CLAUDE.md format, which every
adapted project reads. Invoke `/superpowers-gstack:pitfall-verification`; it chains
Codex and the third house itself. Do not invoke either by hand.

Put these in front of the lenses, because they are where this change can go wrong:

- **The format change is one-way.** A 2.49.0 section read by a 2.48.0 `/adapt` — an
  older plugin cache — sees an unrecognised marker. What does it do? If the answer is
  "case 4, append a duplicate", say so plainly in the CHANGELOG rather than discovering
  it in someone's repo.
- **`<N>` is written by a model counting lines.** What happens when it is wrong by a
  little, and what happens when it is wrong by a lot? The gate trusts it absolutely.
- **Ask for the mutation treatment** on the three new needles and E14 — the 2.48.0
  review found two Critical defects that way and none by reading.

- [ ] **Step 7: Land**

Push, then land with `/ship` or `/superpowers:finishing-a-development-branch`. Merging
publishes 2.49.0 to the marketplace, so confirm that with the user before merging to
`main`.

---

## Self-Review

**1. Coverage.** F8's proper fix: Tasks 2–5. Parked hole "thresholds unpinned": Task 4 Step 1. Parked hole "Step 6 order rule anchors on a question": Task 6. Parked hole P3 (Track-aware routing has no sentinel): **deliberately not addressed** — ruled at 2.48.0 that its heading is plugin-coined, so the risk the attribution check exists for does not apply, and 2.48.0 now states that in the skill rather than assuming it. The open risk named after the 2.48.0 merge (the attribution check's effect on legacy projects): measured before this plan and found to be a no-op on all six of this machine's adapted projects; Task 1 addresses the residual for other plugin users by making the outcome legible rather than by changing behaviour.

**2. Placeholder scan.** No TBDs. `<N>`, `<start>`, `<end>`, `<heading>` and `<name>` are placeholders in the *emitted instruction*, filled by the agent at run time — not gaps in this plan.

**3. Type consistency.** The attribute is spelled ` emitted=<N>` with one leading space in Tasks 2, 3, 4 and 5, and in the fixture's literal `emitted=162`. `**Provenance (authoritative).**`, `**Ratio (fallback).**` and `**Volume (fallback).**` appear identically in Task 4's prose, its test and the CHANGELOG. E-numbers: E14 is claimed once, in Task 2.

**4. Ordering.** Task 2 must precede 3 and 4 (they read what it writes). Task 3 must precede 5 (an intolerant scan would make the fixture's provenance section unreadable). Task 6 is independent. Task 7 is last.

**5. What this plan does not fix.** The gate still trusts a number a model wrote. Provenance narrows the question from "is this section suspiciously long?" to "is there more here than we put here?", which is answerable — but the answer is only as good as the count. A generator that miscounts by 30 lines silently disarms the gate for that section, and nothing here detects it. The honest next step, if that ever bites, is a content hash rather than a line count; it is strictly better and strictly more work, and there is no evidence yet that it is needed.
