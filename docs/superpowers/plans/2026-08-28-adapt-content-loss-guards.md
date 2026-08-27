# /adapt Content-Loss Guards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/adapt` incapable of silently destroying project-authored content during a re-adaptation, and stop it emitting a simulator destination that no longer exists.

**Architecture:** Three mechanical guards replace three unperformable instructions. A **pre-write snapshot** (`.gstack/CLAUDE.md.pre-adapt`) gives Step 6 a real "before" side to diff against; a **mandatory Removed block** in the report gives the diff somewhere to land that an empty result cannot hide in; a **growth check** compares each section's length to its block's before replacing, and stops rather than guessing. Each guard is pinned by a lint rule so a future reword cannot quietly drop it. The simulator fix converts a hardcoded model into a `{{IOS_SIMULATOR}}` placeholder resolved at emit time, plus a general lint rule that no undocumented placeholder can reach a project.

**Tech Stack:** Markdown instruction files (`skills/*/SKILL.md`, `skills/setup-routing/blocks/*.md`), Python 3 lint (`scripts/lint-skills.py`), pytest (`tests/unit/`), bash integration tests (`tests/integration/`).

**Spec:** `skills/adapt/IMPROVEMENTS.md`

---

## Global Constraints

Every task's requirements implicitly include these.

- **Lint must be green after every task.** `python3 scripts/lint-skills.py` exits 0. CI runs it on every push (`.github/workflows/lint.yml`). Never leave a red commit behind — add the lint rule and the change it enforces in the *same* commit.
- **Unit tests must pass after every task.** `pytest tests/unit -q`.
- **Block files: first line is the marker heading.** Lint E8 requires every file in `MARKER_BLOCKS` to match `^## .*<!-- gstack-[a-z-]+-v\d+ -->$` on line 1. Nothing may be inserted above it.
- **Blocks are the single source.** Neither `skills/setup-routing/SKILL.md` nor `skills/adapt/SKILL.md` may contain a heading line carrying a `gstack-*-vN` marker, or a markerless re-paste of a block's heading text (lint E8d).
- **Bumping a marker requires a DENYLIST entry** purging the old range, per the release gate in `CLAUDE.md` rule 4.
- **Version:** `.claude-plugin/plugin.json` `2.47.0` → `2.48.0`, with a matching `## [2.48.0]` section in `CHANGELOG.md` (lint E4 refuses otherwise).
- **Generated-CLAUDE.md prose budget** (from Step 5): routing-table row descriptions ≤ 15 words, decision-tree lines ≤ 10 words, no rationale prose in generated sections. This does *not* apply to `SKILL.md` instruction prose, which is read once per `/adapt` run, not once per session.
- **Branch first.** `git switch -c fix/adapt-content-loss-guards` off `main` before Task 1. Never `git commit --no-verify`.
- **Lint E-numbers in use:** E1–E8, E10, E11 (no E9). This plan adds **E12** and **E13**.

---

## Deviations from the spec

The spec was written from a live failure, not from the repo's invariants. Three of its
concrete proposals do not survive contact with the lint; one has an ordering bug. These
are decided here so the implementer does not rediscover them.

### D1. The per-block comment moves to a CLAUDE.md header comment

**Spec §4** asks for a comment at the **top of each file** in `blocks/`. Rejected:

1. **It breaks lint E8.** Line 1 of every marker block must be the `## Heading <!-- gstack-*-vN -->` line. A comment above it fails the lint outright.
2. **It would not reach existing projects without nine marker bumps.** Case 1 of the four-case logic skips a section whose marker already matches. So the comment only lands if every one of the nine markers is bumped — which also means nine DENYLIST entries and a full nine-section re-replace sweep on every adapted project.
3. **Nine copies of one sentence is nine times the context tax** the repo's own Step 5 rule warns about, in the file that is loaded every session.

**Instead:** extend the version header that Step 5 **already rewrites on every run** (`<!-- superpowers-gstack: {version} -->`) into a two-line header carrying the warning. One copy, at the top of the file, current by construction, no marker churn, no lint change. The spec's second placement — the report paragraph — is kept as Task 3, because that is the teachable moment.

*Trade-off accepted:* a user editing the middle of a marked section does not see a warning at the point of editing. The report paragraph covers the moment it actually matters (right after they have seen content removed).

### D2. The real diff moves from the optional review into mandatory Step 6

**Spec §1** replaces "review item 3", which lives in the **optional** review block — the one gated behind *"Would you like me to run a comprehensive review?"*. **Spec §2** feeds the report's Removed block from that diff. But the report is printed *before* the user is asked about the review, so as specified the Removed block would have no input on any run where the user declines.

**Instead:** the diff becomes mandatory Step 6 verify item 3 (which today reads, uselessly, *"Check that no existing content was lost"*). The optional review keeps an item 3 that re-checks the classification with fresh eyes, without the word *mentally*.

### D3. A non-interactive branch is added to the growth gate

**Spec §3** says *"Never proceed past this gate without an answer."* `/adapt` also runs under `--print`, in CI, and as a subagent, where nobody can answer — and a hard stop there is a hang, not a safeguard. A fourth rule takes the **preserving** branch automatically when no one can answer: leave the section at its old version and report it as deferred. A stale section is recoverable; a deleted one is not. This mirrors the non-interactive rule the git-hygiene block already carries.

### D4. `skills/ios-e2e-scaffold/SKILL.md` is pulled into scope

Release-gate rule 4 requires the purged `name=iPhone <N>` pattern to enter the DENYLIST. That lint scans every `<skill>/SKILL.md`, and `ios-e2e-scaffold/SKILL.md:369` carries `name=iPhone 15` — an older instance of the same defect. Either it is fixed or the denylist entry cannot land. It is fixed (Task 5). It is *not* the same severity: that script already falls back to a UDID lookup, so it degrades instead of failing.

`skills/adapt/IMPROVEMENTS.md` needs no handling — the DENYLIST scans only `<skill>/SKILL.md`, `CLAUDE.md`, `README.md`, `model-routing.md`, `blocks/*.md` and `scripts/`. A design note under `skills/adapt/` is not scanned, so it may keep quoting the defect it describes.

---

## File Structure

| File | Change | Responsibility after the change |
|---|---|---|
| `skills/adapt/SKILL.md` | Modify Step 5 (snapshot, header comment, growth check), Step 6 (mandatory diff, report template), xcode-tools case list | The only generator with a "before" state to protect |
| `scripts/lint-skills.py` | Add E12, E13, 3 DENYLIST entries, update 1 | Release gate — pins each guard's contract string |
| `tests/unit/test_lint_adapt_guards.py` | Create | Proves E12/E13 fire on a violation and pass on the repo |
| `skills/setup-routing/blocks/xcode-tools.md` | Modify lines 1, 12, 14, + note under table | Emits a resolvable destination, marker `v6` |
| `skills/setup-routing/blocks/PLACEHOLDERS.md` | Add `{{IOS_SIMULATOR}}` section | Single source for placeholder resolution |
| `skills/ios-e2e-scaffold/SKILL.md` | Modify runner destination block (~line 365–378) | Resolves the simulator by UDID, names no model |
| `tests/fixtures/adapt-growth/CLAUDE.md` | Create | A grown, marker-downgraded section for the regression test |
| `tests/integration/test_adapt_growth_gate.sh` | Create | Asserts the grown content survives a real `/adapt` run |
| `.claude-plugin/plugin.json`, `CHANGELOG.md` | Modify | Release gate |

`skills/setup-routing/SKILL.md` is **not** modified: it generates a new CLAUDE.md, so there is no prior content to lose, and it already instructs placeholder resolution via `blocks/PLACEHOLDERS.md`.

---

### Task 1: The pre-write snapshot and a diff that can be performed

Implements spec §1 (with deviation D2). Everything downstream reads the snapshot this task creates.

**Files:**
- Modify: `skills/adapt/SKILL.md` — Step 5 opening (~line 215), Step 6 verify list (~line 371–374), Step 6 optional-review item 3 (~line 398)
- Modify: `scripts/lint-skills.py` — `DENYLIST` (~line 88), new E13 block after E11
- Test: `tests/unit/test_lint_adapt_guards.py` (create)

**Interfaces:**
- Produces: the snapshot path literal `.gstack/CLAUDE.md.pre-adapt`, consumed by Tasks 2 and 4; the lint constant `ADAPT_GUARDS`, extended by Tasks 2, 3 and 4.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_lint_adapt_guards.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: FAIL — `AttributeError: module 'lint_skills' has no attribute 'ADAPT_GUARDS'`, plus `test_snapshot_path_is_named_in_the_skill` failing on the missing literal.

- [ ] **Step 3: Add the E13 rule and denylist entry to the lint**

In `scripts/lint-skills.py`, add to `DENYLIST` (after the `does not contain ## Mode: auto` entry, ~line 88):

```python
    # 2.48.0: Step 6 used to ask for a diff against a file Step 5 had already
    # overwritten. An unperformable verification is always answered
    # optimistically — the fix is a real snapshot, not better wording.
    (re.compile(r"diff the old vs new CLAUDE\.md mentally"),
     "unperformable verification — diff .gstack/CLAUDE.md.pre-adapt instead (2.48.0)"),
```

Add near the other module-level constants (after `PLAIN_BLOCKS`, ~line 106):

```python
# E13: /adapt's content-loss guards. Each needle is a contract string, not a
# phrasing preference — the snapshot path a user restores from, the report label
# they grep for, the gate heading the per-section rules cross-reference.
ADAPT_GUARDS = [
    (".gstack/CLAUDE.md.pre-adapt",
     "the pre-write snapshot that gives Step 6 a real 'before' side"),
    ("diff .gstack/CLAUDE.md.pre-adapt CLAUDE.md",
     "the diff that replaces the unperformable mental one"),
]
```

Add the check inside the lint's main body, after the E11 block:

```python
    # E13 /adapt content-loss guards (2.48.0). The 2.9.0 -> 2.47.0 re-adaptation
    # of sing-replay was correct on all nine markers and still replaced a
    # 198-line section with a 73-line block, destroying 125 lines of project
    # knowledge, unreported. These guards are the mechanism that makes that
    # visible; they are prose, so nothing but a lint keeps them from being
    # reworded away.
    adapt_skill = SKILLS / "adapt" / "SKILL.md"
    if adapt_skill.is_file():
        adapt_text = adapt_skill.read_text()
        for needle, why in ADAPT_GUARDS:
            if needle not in adapt_text:
                errors.append(f"E13 adapt/SKILL.md missing content-loss guard {needle!r} — {why}")
```

Document it in the module docstring's ERRORS list, after the E11 entry:

```
  E13 /adapt carries its content-loss guards: the pre-write snapshot, the real
      diff, the mandatory Removed report block and the growth check. Each is
      prose that a reword could silently drop; the 2.47.0 field run showed the
      failure is invisible without them (skills/adapt/IMPROVEMENTS.md).
```

- [ ] **Step 4: Run the lint to verify E13 fires**

Run: `python3 scripts/lint-skills.py`
Expected: FAIL with `E13 adapt/SKILL.md missing content-loss guard '.gstack/CLAUDE.md.pre-adapt'` and one for the diff string. This is the lint proving it can see the defect before it is fixed.

- [ ] **Step 5: Add the snapshot to Step 5**

In `skills/adapt/SKILL.md`, immediately after the Step 5 opening line `Apply the changes identified in Step 4. Follow these rules strictly:` and before `**CLAUDE.md updates:**`, insert:

````markdown
**Snapshot before the first write.** Before modifying CLAUDE.md — before any other
rule in this step:

```bash
mkdir -p .gstack && cp CLAUDE.md .gstack/CLAUDE.md.pre-adapt
```

`.gstack/` already holds `track`, so this introduces no new location. This snapshot is
what Step 6 diffs against and what the user restores from if the run goes wrong. Do
NOT substitute `git diff` for it: the project may have uncommitted CLAUDE.md changes,
and CLAUDE.md may not be tracked at all. If CLAUDE.md does not exist yet, skip the
copy — there is no prior content to lose — and say so in the Step 6 report.
````

- [ ] **Step 6: Replace Step 6's mandatory verify item 3 with the real diff**

In `skills/adapt/SKILL.md`, Step 6 currently opens with:

```markdown
After applying changes, verify:
1. Read the updated CLAUDE.md and confirm routing section is correct
2. Confirm `docs/superpowers/` directories exist
3. Check that no existing content was lost
```

Replace item 3 with:

````markdown
3. **Diff against the snapshot and classify every removed line.** Run:

   ```bash
   diff .gstack/CLAUDE.md.pre-adapt CLAUDE.md
   ```

   Read the `<` side. Every removed line is either **(a)** plugin prose replaced by a
   newer version of the same block — expected — or **(b)** project-authored content,
   which is a loss. Put every hunk in one of those two buckets; the (b) list is what
   the report's **Removed** block prints. Do not summarise the diff without reading
   it, and do not answer this item from memory: the file you would be recalling was
   overwritten earlier in Step 5. If the snapshot is missing because CLAUDE.md did
   not exist before this run, say that instead — do not skip the item silently.
````

- [ ] **Step 7: Reword the optional review's item 3**

Further down Step 6, in the numbered list under *"If the user says yes, run the review"*, replace:

```markdown
3. **Verify preserved content** — diff the old vs new CLAUDE.md mentally. Was anything accidentally removed or mangled?
```

with:

```markdown
3. **Re-check the preservation classification** — re-run `diff .gstack/CLAUDE.md.pre-adapt CLAUDE.md` and re-read the `<` side with fresh eyes. The mandatory verify step above already classified each hunk; this pass asks whether any hunk filed under "expected plugin prose" is actually project content wearing plugin-shaped wording.
```

- [ ] **Step 8: Run the lint and the test to verify both pass**

Run: `python3 scripts/lint-skills.py && pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: lint reports `0 error(s)`; pytest reports 5 passed.

- [ ] **Step 9: Commit**

```bash
git add skills/adapt/SKILL.md scripts/lint-skills.py tests/unit/test_lint_adapt_guards.py
git commit -m "fix(adapt): snapshot CLAUDE.md before writing, diff against it after

Step 6 asked the agent to 'diff the old vs new CLAUDE.md mentally'. By the time
it ran, Step 5 had overwritten the file, so the old side existed nowhere the
agent could reach — an unperformable verification, which is always answered
optimistically.

Step 5 now copies CLAUDE.md to .gstack/CLAUDE.md.pre-adapt before its first
write, and Step 6's mandatory verify item diffs against it and classifies every
removed line as plugin prose or project content. Lint E13 pins both strings; the
old wording is denylisted."
```

---

### Task 2: A report block that can reveal a casualty

Implements spec §2, and the report half of spec §4 (per deviation D1).

**Files:**
- Modify: `skills/adapt/SKILL.md` — Step 6 report template (~line 376–382)
- Modify: `scripts/lint-skills.py` — extend `ADAPT_GUARDS`
- Test: `tests/unit/test_lint_adapt_guards.py` (extend)

**Interfaces:**
- Consumes: the (b) list produced by Task 1's mandatory verify item 3.
- Produces: the literal report labels `**Removed (not plugin prose):**` and the sentinel `Nothing project-authored was removed.`, both referenced by Task 4's non-interactive branch and Task 7's assertions.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_lint_adapt_guards.py`:

```python
def test_report_has_a_block_for_what_was_removed():
    """A list of survivors cannot reveal a casualty."""
    assert "**Removed (not plugin prose):**" in ADAPT_SKILL


def test_the_empty_case_has_an_explicit_sentinel():
    """An omitted block reads as 'not checked' — the state it exists to prevent."""
    assert "Nothing project-authored was removed." in ADAPT_SKILL
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: FAIL — 2 failed, 5 passed.

- [ ] **Step 3: Extend `ADAPT_GUARDS`**

In `scripts/lint-skills.py`, add two entries to `ADAPT_GUARDS`:

```python
    ("**Removed (not plugin prose):**",
     "the only report block that can reveal a casualty — survivors lists cannot"),
    ("Nothing project-authored was removed.",
     "the sentinel that makes an empty Removed block mean 'checked', not 'skipped'"),
```

- [ ] **Step 4: Run the lint to verify E13 fires**

Run: `python3 scripts/lint-skills.py`
Expected: FAIL with two new `E13 adapt/SKILL.md missing content-loss guard` lines.

- [ ] **Step 5: Rewrite the Step 6 report template**

Replace the existing template:

```markdown
> **Changes made:**
> - [list each change]
>
> **Preserved:**
> - [existing CLAUDE.md content that was kept]
```

with:

```markdown
> **Changes made:**
> - [list each change]
>
> **Preserved:**
> - [existing CLAUDE.md content that was kept]
>
> **Removed (not plugin prose):**
> - [one line per hunk the verify diff classified as project content: the section
>    it came from, its line count, and where the content went — moved to an
>    unmarked section, or lost]
> - If nothing project-authored was removed, write exactly:
>   `Nothing project-authored was removed.`

**Never omit the Removed block.** An absent block reads as "not checked" — which is
the state the block exists to prevent — so it is the one part of this report that
must appear even when it is empty. A line under **Changes made** such as
`Native Apple development tools: v3 → v5` is true and says nothing about the 125
project-authored lines that upgrade destroyed; only this block can.

When the Removed block is non-empty, add:

> **Where project knowledge belongs.** A heading carrying a `gstack-<name>-vN` marker
> is plugin-owned: `/adapt` replaces the whole section on every upgrade. Pasting
> rescued content back into one guarantees a repeat at the next upgrade. Project
> findings — the measurement you took, the flag that turned out to work, the thing
> that cost you an hour — belong in your own H2 section with no marker. `/adapt`
> never touches those.
```

- [ ] **Step 6: Run the lint and the test to verify both pass**

Run: `python3 scripts/lint-skills.py && pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: lint `0 error(s)`; pytest 7 passed.

- [ ] **Step 7: Commit**

```bash
git add skills/adapt/SKILL.md scripts/lint-skills.py tests/unit/test_lint_adapt_guards.py
git commit -m "fix(adapt): report what was removed, not only what survived

The Step 6 report listed 'Changes made' and 'Preserved'. Neither can show a
casualty: a destroyed section appears under Changes made as one accurate,
uninformative version-bump line, and never on the Preserved list at all.

Adds a mandatory Removed block fed by the verify diff, with an explicit
sentence for the empty case so a missing block cannot pass as a clean one, and
a paragraph — printed only when something was removed — telling the user that
unmarked H2 sections are the place /adapt never touches."
```

---

### Task 3: A header comment that says which sections are volatile

Implements the header half of spec §4, per deviation D1.

**Files:**
- Modify: `skills/adapt/SKILL.md` — first bullet under `**CLAUDE.md updates:**` (~line 217)
- Modify: `scripts/lint-skills.py` — extend `ADAPT_GUARDS`
- Test: `tests/unit/test_lint_adapt_guards.py` (extend)

**Interfaces:**
- Consumes: nothing.
- Produces: a two-line HTML header at the top of every adapted CLAUDE.md.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_lint_adapt_guards.py`:

```python
def test_header_warns_which_sections_are_plugin_owned():
    assert "are plugin-managed: /adapt replaces each one" in ADAPT_SKILL


def test_header_comment_does_not_nest_a_comment_terminator():
    """HTML comments do not nest: an inner '-->' would close the header early and
    dump the rest of the warning into the rendered file as visible text."""
    start = ADAPT_SKILL.index("<!-- Sections whose heading carries")
    body = ADAPT_SKILL[start + 4 : ADAPT_SKILL.index("-->", start)]
    assert "<!--" not in body
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: FAIL — `test_header_warns_...` fails on the missing string; `test_header_comment_...` errors with `ValueError: substring not found`.

- [ ] **Step 3: Extend `ADAPT_GUARDS`**

```python
    ("are plugin-managed: /adapt replaces each one",
     "the CLAUDE.md header telling the user which sections are volatile"),
```

- [ ] **Step 4: Run the lint to verify E13 fires**

Run: `python3 scripts/lint-skills.py`
Expected: FAIL with one new `E13` line.

- [ ] **Step 5: Extend the version header in Step 5**

Replace the first bullet under `**CLAUDE.md updates:**`:

```markdown
- Read the plugin version from `.claude-plugin/plugin.json` in the superpowers-gstack plugin directory (check `~/.claude/plugins/cache/*/superpowers-gstack/*/plugin.json`, use the latest). Add or update an HTML comment at the very top of CLAUDE.md: `<!-- superpowers-gstack: {version} -->`
```

with:

````markdown
- Read the plugin version from `.claude-plugin/plugin.json` in the superpowers-gstack plugin directory (check `~/.claude/plugins/cache/*/superpowers-gstack/*/plugin.json`, use the latest). Add or update the **two-line** HTML header at the very top of CLAUDE.md — rewrite both lines every run, so the warning stays current without needing a marker of its own:

  ```
  <!-- superpowers-gstack: {version} -->
  <!-- Sections whose heading carries a gstack-<name>-vN marker are plugin-managed: /adapt replaces each one wholesale on upgrade. Put project-specific findings — the measurement you took, the flag that worked — in your own H2 section with no marker. /adapt never touches those. -->
  ```

  Keep the second line as a single HTML comment with no nested `<!--` inside it: HTML comments do not nest, so an inner opener followed by the first `-->` would end the comment early and render the remainder as visible text.
````

- [ ] **Step 6: Run the lint and the test to verify both pass**

Run: `python3 scripts/lint-skills.py && pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: lint `0 error(s)`; pytest 9 passed.

- [ ] **Step 7: Commit**

```bash
git add skills/adapt/SKILL.md scripts/lint-skills.py tests/unit/test_lint_adapt_guards.py
git commit -m "feat(adapt): say in the file which sections /adapt overwrites

A user whose CLAUDE.md was rewritten learns that marked sections are volatile;
what they do next decides whether it happens again, and the obvious move —
paste the rescued content back where it was — guarantees a repeat.

IMPROVEMENTS.md proposed a comment at the top of each block file. That breaks
lint E8 (line 1 must be the marker heading), only reaches existing projects if
all nine markers are bumped, and puts nine copies of one sentence in the file
loaded every session. The version header is already rewritten on every run, so
the warning goes there instead: one copy, current by construction."
```

---

### Task 4: The growth check

Implements spec §3, with the non-interactive branch from deviation D3. This is the guard that fires *before* the write, so it is the only one that can prevent the loss rather than report it.

**Files:**
- Modify: `skills/adapt/SKILL.md` — insert after the `**Shared block files.**` paragraph (~line 231), before the first `**Insert or upgrade ...**` rule
- Modify: `scripts/lint-skills.py` — extend `ADAPT_GUARDS`
- Test: `tests/unit/test_lint_adapt_guards.py` (extend)

**Interfaces:**
- Consumes: `.gstack/CLAUDE.md.pre-adapt` (Task 1); the Removed report block (Task 2) for its non-interactive branch.
- Produces: the gate heading `**Growth check` referenced by every per-section case-2/case-3 rule.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_lint_adapt_guards.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: FAIL — 3 failed, 9 passed.

- [ ] **Step 3: Extend `ADAPT_GUARDS`**

```python
    ("**Growth check",
     "the size gate that stops a silent replace of a section grown past its block"),
```

- [ ] **Step 4: Run the lint to verify E13 fires**

Run: `python3 scripts/lint-skills.py`
Expected: FAIL with one new `E13` line.

- [ ] **Step 5: Insert the growth check**

In `skills/adapt/SKILL.md`, immediately after the `**Shared block files.**` paragraph and before `**Insert or upgrade the Autonomy and user interruption section.**`, insert:

````markdown
**Growth check — applies to every marker-managed section below, in cases 2 and 3.**
A marker records who *created* a section, not who has written in it since. Before
replacing any section, compare its length against the block's:

```bash
TMP="$(mktemp)"
sed -n '<start>,<end>p' .gstack/CLAUDE.md.pre-adapt > "$TMP"
wc -l "$TMP" <path-to-block>.md
```

You already know `<start>` and `<end>` — finding them is how you perform the REPLACE
at all. If the existing section is more than **1.5×** the block's line count, it has
accumulated project-authored content that the replacement will destroy. Do not
replace it silently:

1. Run `diff "$TMP" <path-to-block>.md` and collect the `<` lines that are not simply
   a reworded version of block prose. That is the content at risk.
2. Ask the user, naming the section and the number of lines at risk, and offer two
   outcomes: **move that content into a new unmarked H2 section** (recommended —
   `/adapt` never touches unmarked sections, so it survives every future upgrade), or
   **leave this section at its old version** and skip its upgrade.
3. Do not proceed past this gate without an answer. This is a category-3 stop under
   the Autonomy rules — genuinely ambiguous, with materially different consequences —
   and the one place in `/adapt` where silent correctness is worse than asking. A
   wrong guess here is unrecoverable for the user; the cost of asking is one question.
4. **Non-interactive runs** (`--print`, CI, a subagent — nobody can answer): take the
   preserving branch without asking. Leave the section at its old version, do not
   replace it, and list it in the report's **Removed (not plugin prose):** block as
   *deferred, not applied*, naming the section. A stale section is recoverable; a
   deleted one is not.

The threshold is a heuristic, not a measurement. A section at 1.1× is usually a user
fixing a typo in plugin prose; the run that motivated this gate was at 2.7× — a
73-line block against a 198-line section, and the 125-line delta held an
`-allowProvisioningUpdates` discovery, three lessons about running on a physical
iPhone, and a note on a tool's current status. None of it was recoverable from the
plugin.
````

- [ ] **Step 6: Cross-reference the gate from the per-section rules**

Nine `**Insert or upgrade ...**` rules follow. In each one, append this sentence to the **case 2** bullet, immediately after `Preserve original heading level.`:

```markdown
Run the **Growth check** above before replacing.
```

Do the same for the **case 3** bullet of every section whose case 3 is a REPLACE — that is all of them except `Code reuse discipline` (whose case 3 already preserves) and `Session Continuity` (whose case 3 replaces only when the handoff.md sniff test passes; add the sentence to that branch).

- [ ] **Step 7: Run the lint and the test to verify both pass**

Run: `python3 scripts/lint-skills.py && pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: lint `0 error(s)`; pytest 12 passed.

- [ ] **Step 8: Commit**

```bash
git add skills/adapt/SKILL.md scripts/lint-skills.py tests/unit/test_lint_adapt_guards.py
git commit -m "fix(adapt): stop before replacing a section that outgrew its block

Case 3 for Code reuse discipline already reasons that a section /adapt cannot
attribute to a past emitter is user-authored and must not be replaced. The same
failure reaches marked sections by another road: a valid v3 marker on a section
grown to 2.7x the block's size describes a section that is mostly user-authored,
whatever the marker says, and case 2 replaced it wholesale with no size check.

Adds one shared gate above the nine per-section rules: over ~1.5x the block,
extract the delta and ask. Non-interactive runs take the preserving branch
automatically and report the section as deferred rather than hanging on a
question nobody can answer."
```

---

### Task 5: Stop naming a simulator model in the iOS E2E runner

Deviation D4 — required before Task 6's denylist entry can land. Not from the spec, but the same defect one skill over.

**Files:**
- Modify: `skills/ios-e2e-scaffold/SKILL.md:365-378`

**Interfaces:**
- Produces: a runner block containing no `name=iPhone <N>` literal, clearing the way for the DENYLIST pattern in Task 6.

- [ ] **Step 1: Confirm the current occurrence**

Run: `grep -n "name=iPhone" skills/ios-e2e-scaffold/SKILL.md`
Expected: one hit at ~line 369, `DEST='platform=iOS Simulator,name=iPhone 15'`.

- [ ] **Step 2: Replace the destination block**

Replace:

```bash
# Pick a simulator: prefer an EXACT "iPhone 15"; else the first available iPhone by
# UDID (robust to naming — avoids the "iPhone 15" substring matching "iPhone 15 Pro",
# and avoids the digit-only grep missing "iPhone SE"). Targeting by id= is exact.
DEST='platform=iOS Simulator,name=iPhone 15'
if ! xcrun simctl list devices available | grep -q 'iPhone 15 ('; then
  UDID="$(xcrun simctl list devices available | grep 'iPhone' | grep -oiE '[0-9A-F]{8}-([0-9A-F]{4}-){3}[0-9A-F]{12}' | head -1)"
  if [ -n "$UDID" ]; then
    DEST="platform=iOS Simulator,id=${UDID}"
    echo "(iPhone 15 unavailable — using first available iPhone simulator ${UDID})"
  else
    echo "(no iPhone simulator available — xcodebuild will report a destination error)"
  fi
fi
```

with:

```bash
# Pick a simulator by UDID. Never hardcode a model name: Xcode ships a rolling set
# and drops old ones, and a stale name fails as "Unable to find a device matching
# the provided destination specifier" — which reads as a broken project rather than
# a dead device name. Targeting by id= is also exact, so it cannot match "iPhone 15
# Pro" when you meant "iPhone 15", and it does not miss "iPhone SE".
UDID="$(xcrun simctl list devices available | grep 'iPhone' | grep -oiE '[0-9A-F]{8}-([0-9A-F]{4}-){3}[0-9A-F]{12}' | head -1)"
if [ -z "$UDID" ]; then
  echo "No iPhone simulator available. Install a runtime: Xcode > Settings > Components." >&2
  exit 2
fi
DEST="platform=iOS Simulator,id=${UDID}"
echo "(using iPhone simulator ${UDID})"
```

- [ ] **Step 3: Verify no model literal remains**

Run: `grep -n "name=iPhone" skills/ios-e2e-scaffold/SKILL.md; echo "hits: $?"`
Expected: no output, `hits: 1` (grep found nothing).

- [ ] **Step 4: Run the lint**

Run: `python3 scripts/lint-skills.py`
Expected: `0 error(s)` — unchanged; this task removes a future denylist violation rather than fixing a current one.

- [ ] **Step 5: Commit**

```bash
git add skills/ios-e2e-scaffold/SKILL.md
git commit -m "fix(ios-e2e-scaffold): resolve the simulator by UDID, name no model

The emitted runner preferred an exact 'iPhone 15' and fell back to a UDID
lookup, so it degraded rather than failed — but the preferred name is three
Xcode releases stale, and the fallback's message blames a device that has not
shipped in a while. Resolve by UDID unconditionally and exit 2 with an
actionable message when no runtime is installed."
```

---

### Task 6: `{{IOS_SIMULATOR}}` — a destination that exists on this machine

Implements spec §5, plus lint E12 so the next placeholder cannot ship undocumented.

**Files:**
- Modify: `skills/setup-routing/blocks/xcode-tools.md` — line 1 (marker), lines 12 and 14, note after the routing table (~line 24)
- Modify: `skills/setup-routing/blocks/PLACEHOLDERS.md` — new section
- Modify: `skills/adapt/SKILL.md` — xcode-tools case 1 and case 2 (~lines 338–339)
- Modify: `scripts/lint-skills.py` — E12, two DENYLIST changes
- Test: `tests/unit/test_lint_adapt_guards.py` (extend)

**Interfaces:**
- Consumes: the placeholder-resolution contract in `blocks/PLACEHOLDERS.md`, which both generators already reference.
- Produces: `{{IOS_SIMULATOR}}`, marker `gstack-xcode-tools-v6`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_lint_adapt_guards.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_lint_adapt_guards.py -q`
Expected: FAIL — `test_no_block_hardcodes_a_simulator_model` (xcode-tools.md), `test_xcode_tools_uses_the_placeholder`, and `test_denylist_catches_a_hardcoded_simulator_model`.

- [ ] **Step 3: Add E12 to the lint**

In `scripts/lint-skills.py`, add after the E8 block:

```python
    # E12 placeholder completeness (2.48.0). PLACEHOLDERS.md's preamble says no
    # raw {{...}} token may reach a generated CLAUDE.md — but nothing checked
    # that a token a block introduces is documented anywhere a generator would
    # look. An undocumented one is emitted verbatim into a project's CLAUDE.md.
    if blocks_dir.is_dir():
        ph = blocks_dir / "PLACEHOLDERS.md"
        documented = set(re.findall(r"^##\s+`\{\{([A-Z0-9_]+)\}\}`",
                                    ph.read_text(), re.M)) if ph.is_file() else set()
        for f in sorted(blocks_dir.glob("*.md")):
            if f.name == "PLACEHOLDERS.md":
                continue
            for tok in sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", f.read_text()))):
                if tok not in documented:
                    errors.append(
                        f"E12 {BLOCKS_DIR_REL}/{f.name}: placeholder {{{{{tok}}}}} is not "
                        f"documented in {BLOCKS_DIR_REL}/PLACEHOLDERS.md — the generators "
                        f"have no resolution rule, so it reaches the project verbatim")
```

Document it in the module docstring's ERRORS list, before the E13 entry:

```
  E12 every `{{TOKEN}}` used in a shared block has a resolution rule in
      blocks/PLACEHOLDERS.md. Without one the generators emit it verbatim into
      the project's CLAUDE.md — the exact outcome that file's preamble forbids.
```

- [ ] **Step 4: Update the DENYLIST**

Replace the stale-marker entry:

```python
    (re.compile(r"gstack-xcode-tools-v[0-4]\b"), "stale xcode-tools marker (current: v5+, 2.45.0)"),
```

with:

```python
    (re.compile(r"gstack-xcode-tools-v[0-5]\b"), "stale xcode-tools marker (current: v6+, 2.48.0)"),
    # v5 hardcoded `name=iPhone 16`; Xcode had already dropped it on the author's
    # own machine, and the resulting "Unable to find a device matching the
    # provided destination specifier" reads as a broken project, not a dead name.
    (re.compile(r"name=iPhone \d"),
     "hardcoded simulator model — use {{IOS_SIMULATOR}} or resolve by UDID (2.48.0)"),
```

- [ ] **Step 5: Run the lint to verify both new rules fire**

Run: `python3 scripts/lint-skills.py`
Expected: FAIL with `E7 skills/setup-routing/blocks/xcode-tools.md:12` and `:14` (denylisted `name=iPhone 16`). E12 does not fire yet — the placeholder does not exist.

- [ ] **Step 6: Document the placeholder**

Append to `skills/setup-routing/blocks/PLACEHOLDERS.md`:

````markdown
## `{{IOS_SIMULATOR}}` (xcode-tools.md — native tracks only)

A simulator model that exists on this machine right now. Resolve with:

    xcrun simctl list devices available | grep -m1 -oE 'iPhone [0-9]+[a-z]*( Pro( Max)?)?'

Prefer a plain numbered model over a Pro/Max variant — it is the one most likely
to exist on a collaborator's machine too. If the command returns nothing (no
simulator runtimes installed), emit `iPhone 17` and say in the adapt report that
no simulator was found locally, so the destination is a guess until a runtime is
installed.

Never hardcode a constant here. Xcode ships a rolling set of simulators and drops
old ones: on the machine that motivated this placeholder (2026-08-27) no iPhone 16
remained, and the emitted command failed as `xcodebuild: error: Unable to find a
device matching the provided destination specifier` — which reads as a project
misconfiguration rather than a stale device name.
````

- [ ] **Step 7: Substitute in `xcode-tools.md` and bump its marker**

Line 1 — bump the marker:

```markdown
## Native Apple development tools (Xcode workflow) <!-- gstack-xcode-tools-v6 -->
```

Line 12 — replace `name=iPhone 16` with `name={{IOS_SIMULATOR}}`:

```markdown
| Build Xcode project for simulator | `mcp__XcodeBuildMCP__build_sim` | `xcodebuild -scheme <name> -destination 'platform=iOS Simulator,name={{IOS_SIMULATOR}}' build` |
```

Line 14 — same substitution:

```markdown
| Run XCTest / Swift Testing | `mcp__XcodeBuildMCP__test_sim` | `xcodebuild test -scheme <name> -destination 'platform=iOS Simulator,name={{IOS_SIMULATOR}}'` |
```

Immediately after the routing table (after the `WWDC video search / examples` row, before `### Verifying a macOS app by eye`), insert:

```markdown
Simulator models come and go with Xcode releases. If `xcodebuild` answers "Unable to
find a device matching the provided destination specifier", the destination name is
stale, not the project — run `xcrun simctl list devices available` and use a model
from that list.
```

- [ ] **Step 8: Update `/adapt`'s xcode-tools case list**

In `skills/adapt/SKILL.md`, change case 1 from ``matches `v5``` to ``matches `v6```, and extend case 2's parenthetical:

```markdown
1. **Heading present + marker matches `v6`** → skip (idempotent).
2. **Heading present + marker `v1`–`v5`** (v1 assumed XcodeBuildMCP universally; v2 added CLI fallback but missed capabilities; v3 hardcoded one team's `DEVELOPMENT_TEAM`; v4 was simulator-only and had no macOS build/launch path at all; v5 hardcoded an `iPhone 16` destination that Xcode no longer ships) → REPLACE through next heading of equal-or-shallower level.
```

Leave the rest of case 2 unchanged, including the Growth check sentence added in Task 4.

- [ ] **Step 9: Run the lint and the tests to verify all pass**

Run: `python3 scripts/lint-skills.py && pytest tests/unit -q`
Expected: lint `0 error(s)`; the whole unit suite passes, including `test_own_blocks_sync.py` (xcode-tools.md is not in `UNIVERSAL`, so this repo's own CLAUDE.md region is unaffected and needs no re-sync).

- [ ] **Step 10: Commit**

```bash
git add skills/setup-routing/blocks/xcode-tools.md skills/setup-routing/blocks/PLACEHOLDERS.md skills/adapt/SKILL.md scripts/lint-skills.py tests/unit/test_lint_adapt_guards.py
git commit -m "fix(blocks): resolve the simulator destination instead of hardcoding it

xcode-tools v5 emitted 'platform=iOS Simulator,name=iPhone 16' into every
native project's CLAUDE.md. Xcode had already dropped that model on the author's
machine, so the emitted command failed with 'Unable to find a device matching
the provided destination specifier' — a message that reads as a broken project
and sends the agent debugging the wrong thing.

Becomes {{IOS_SIMULATOR}}, resolved at emit time from xcrun simctl. Marker v6 so
adapted projects pick it up. New lint E12 refuses any block placeholder that
PLACEHOLDERS.md does not document, and the hardcoded form is denylisted."
```

---

### Task 7: The regression the report cannot catch

Implements the spec's *"How to verify a fix"*. The failure mode this targets is the quiet one: a run that reports `Nothing project-authored was removed.` while the diff says otherwise. Asserting against the report would accept that run; this asserts against the file.

**Files:**
- Create: `tests/fixtures/adapt-growth/CLAUDE.md`
- Create: `tests/integration/test_adapt_growth_gate.sh`

**Interfaces:**
- Consumes: the growth check (Task 4) and its non-interactive branch — `claude --print` cannot answer a question, so rule 4 is the path under test.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Create the fixture**

Create `tests/fixtures/adapt-growth/CLAUDE.md` — an adapted CLAUDE.md whose xcode-tools section carries an old marker and has grown well past the block:

```markdown
<!-- superpowers-gstack: 2.9.0 -->

# Fixture Project

A native iOS app. This file stands in for a project adapted long ago and never
re-adapted since.

## Native Apple development tools (Xcode workflow) <!-- gstack-xcode-tools-v3 -->

Xcode-related operations MUST be performed by the agent — never delegated to the user.

### Project-specific findings (the content under test)

SENTINEL-LINE-001: `-allowProvisioningUpdates` removed the manual Apple Developer
Portal registration step; without it every fresh clone stalls on provisioning.
SENTINEL-LINE-002: running on a physical iPhone requires the device unlocked AND
trusted, and the first run after a reboot always fails once before succeeding.
SENTINEL-LINE-003: the on-device console drops the first ~200 ms of log output, so
a launch-time crash needs `OSLog` with a persisted store, not `print`.
SENTINEL-LINE-004: `xcodebuild -showBuildSettings` is slow enough (~8 s) that the
runner should cache it per-branch rather than call it per-test.
SENTINEL-LINE-005: this project pins the deployment target one minor below the
current SDK on purpose — raising it breaks the TestFlight cohort on 26.0.

## Project conventions

Swift 6 strict concurrency. SwiftData + CloudKit. No third-party dependencies.
```

- [ ] **Step 2: Write the failing test**

Create `tests/integration/test_adapt_growth_gate.sh`:

```bash
#!/usr/bin/env bash
#
# tests/integration/test_adapt_growth_gate.sh
#
# Verifies that /adapt's growth check (2.48.0) refuses to silently replace a
# marker-managed section that has grown past its block.
#
# The regression this guards is the QUIET one: a run that reports
# "Nothing project-authored was removed." while the diff says otherwise. So the
# assertions read the FILE, never the report.
#
# --print is non-interactive, so the gate's rule 4 (preserving branch) is the
# path under test: the section must be left at its old version, not replaced.
#
# Cost: ~1-2 minutes and a few cents. Requires ANTHROPIC_API_KEY or an active
# Claude Code session.
#
# Usage: bash tests/integration/test_adapt_growth_gate.sh
# Exit codes: 0 = pass, 1 = assertion failed, 2 = setup error.

set -uo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
FIXTURE="$PLUGIN_DIR/tests/fixtures/adapt-growth/CLAUDE.md"
FAILURES=()

if ! command -v claude >/dev/null 2>&1; then
  echo "SETUP ERROR: claude CLI not found in PATH." >&2
  exit 2
fi
if [ ! -f "$FIXTURE" ]; then
  echo "SETUP ERROR: fixture missing at $FIXTURE" >&2
  exit 2
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp "$FIXTURE" "$WORK/CLAUDE.md"
mkdir -p "$WORK/.gstack" && echo "ios" > "$WORK/.gstack/track"
git -C "$WORK" init -q && git -C "$WORK" add -A
git -C "$WORK" -c user.email=t@t -c user.name=t commit -qm "fixture"

echo "Running /adapt against $WORK ..."
( cd "$WORK" && claude --print --plugin-dir "$PLUGIN_DIR" \
    "/superpowers-gstack:adapt" ) > "$WORK/run.log" 2>&1
echo "(exit $?; log at $WORK/run.log)"

assert() {  # $1 = description, $2 = 0/1 condition result
  if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; FAILURES+=("$1"); fi
}

# 1. The snapshot exists — Task 1's guard actually ran.
[ -f "$WORK/.gstack/CLAUDE.md.pre-adapt" ]; assert "snapshot written to .gstack/CLAUDE.md.pre-adapt" $?

# 2. Every sentinel line survives. This is the assertion that matters: it reads
#    the file, so a run that CLAIMS nothing was removed still fails here.
MISSING=0
for n in 001 002 003 004 005; do
  grep -q "SENTINEL-LINE-$n" "$WORK/CLAUDE.md" || { echo "  lost SENTINEL-LINE-$n"; MISSING=1; }
done
[ "$MISSING" -eq 0 ]; assert "all 5 project-authored sentinel lines survive" $?

# 3. The grown section was NOT silently upgraded to v6 — non-interactive runs
#    take the preserving branch.
! grep -q "gstack-xcode-tools-v6" "$WORK/CLAUDE.md"; assert "grown section left at its old marker, not replaced" $?

# 4. The report names the deferral rather than passing over it in silence.
grep -qi "Removed (not plugin prose)" "$WORK/run.log"; assert "report contains the Removed block" $?

echo ""
if [ ${#FAILURES[@]} -eq 0 ]; then
  echo "test_adapt_growth_gate: PASS"
  exit 0
fi
printf 'test_adapt_growth_gate: %d assertion(s) failed\n' "${#FAILURES[@]}"
printf '  - %s\n' "${FAILURES[@]}"
exit 1
```

- [ ] **Step 3: Make it executable and run it**

Run: `chmod +x tests/integration/test_adapt_growth_gate.sh && bash tests/integration/test_adapt_growth_gate.sh`
Expected: PASS on all four assertions. If assertion 2 fails, the growth check is not firing — return to Task 4 rather than weakening the assertion.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/adapt-growth/CLAUDE.md tests/integration/test_adapt_growth_gate.sh
git commit -m "test(adapt): assert grown content survives a real re-adaptation

The regression to watch for is the quiet one — a run that reports 'Nothing
project-authored was removed.' while the diff says otherwise. So this asserts
against the file, never the report: five sentinel lines in a v3-marked section
grown well past its block must still be there afterwards.

--print cannot answer the gate's question, which makes it the right harness for
the non-interactive preserving branch."
```

---

### Task 8: Release

**Files:**
- Modify: `.claude-plugin/plugin.json`, `CHANGELOG.md`

- [ ] **Step 1: Bump the version**

In `.claude-plugin/plugin.json`, change `"version": "2.47.0"` to `"version": "2.48.0"`.

- [ ] **Step 2: Run the lint to verify E4 fires**

Run: `python3 scripts/lint-skills.py`
Expected: FAIL with `E4 CHANGELOG.md: no entry for plugin.json version 2.48.0`.

- [ ] **Step 3: Add the CHANGELOG entry**

Insert directly under `# Changelog`:

```markdown
## [2.48.0] - 2026-08-28

`/adapt` could complete a re-adaptation correctly on every marker and still destroy a
project's accumulated knowledge without saying so. A 2.9.0 → 2.47.0 run on a real
project replaced a 198-line section with its 73-line block; the 125-line delta was
recovered only because the operator happened to snapshot the file first. Field notes:
`skills/adapt/IMPROVEMENTS.md`.

### Fixed — the verification that could not be performed
- **Step 6 asked for a diff against a file Step 5 had already overwritten**, "mentally".
  An unperformable verification is always answered optimistically. Step 5 now snapshots
  CLAUDE.md to `.gstack/CLAUDE.md.pre-adapt` before its first write, and Step 6 diffs
  against it and classifies every removed line as plugin prose or project content.
- **The report listed survivors, which cannot reveal a casualty.** A destroyed section
  appeared under "Changes made" as one accurate, uninformative version-bump line. A
  mandatory **Removed (not plugin prose)** block now carries the diff's verdict, with an
  explicit sentence for the empty case so a missing block cannot pass as a clean one.
- **A marked section grown past its block is mostly user-authored, whatever the marker
  says.** A growth check above the nine per-section rules stops at ~1.5× and asks;
  non-interactive runs take the preserving branch and report the section as deferred.

### Fixed — an emitted command that could not work
- **`xcode-tools` hardcoded `name=iPhone 16`.** Xcode drops old simulators; the failure
  reads as a broken project, not a stale device name. Now `{{IOS_SIMULATOR}}`, resolved
  from `xcrun simctl` at emit time (marker `v6`). `ios-e2e-scaffold`'s runner resolves
  by UDID and names no model.

### Added — guards so this cannot regress quietly
- **Lint E12:** every `{{TOKEN}}` in a shared block must have a resolution rule in
  `blocks/PLACEHOLDERS.md`, or the generators emit it verbatim into a project.
- **Lint E13:** `/adapt` must carry all four content-loss guards. They are prose, so
  nothing but a lint keeps a reword from dropping them.
- **`tests/integration/test_adapt_growth_gate.sh`:** asserts against the file, not the
  report — the regression to catch is a run that claims nothing was removed while the
  diff disagrees.

### Told the user where knowledge belongs
- Adapted CLAUDE.md files now carry a second header line naming marked sections as
  plugin-managed and unmarked H2 sections as the place `/adapt` never touches. The
  report repeats it, but only when something was actually removed.
```

- [ ] **Step 4: Run the full gate**

Run: `python3 scripts/lint-skills.py && pytest tests/unit -q && bash tests/integration/test_adapt_growth_gate.sh`
Expected: lint `0 error(s)` (W2 on `swiftui-design-consultation` is pre-existing); unit suite green; integration test PASS.

- [ ] **Step 5: Check README and routing coverage**

Run: `grep -n "adapt" README.md | head`
Expected: `/superpowers-gstack:adapt` is already listed and no skill was added or renamed, so no README change is needed. If the grep shows a stale description of what `/adapt` preserves, update that line in this commit.

- [ ] **Step 6: Commit**

```bash
git add .claude-plugin/plugin.json CHANGELOG.md
git commit -m "chore: release 2.48.0 — /adapt content-loss guards"
```

- [ ] **Step 7: Multi-lens verification**

This is ship-worthy (version bump, CHANGELOG, `fix` commits changing runtime behaviour) and touches a **contract** — the emitted CLAUDE.md format and two new lint rules other work will be gated on. That is the high-stakes tier.

Invoke `/superpowers-gstack:pitfall-verification`. It auto-chains `/codex review` (Stage 2) and `/superpowers-gstack:third-lens-review` (Stage 3), ending in adversarial synthesis. Do not invoke Codex or the third house by hand.

Specific things to put in front of the lenses:
- **The 1.5× threshold is a guess, not a measurement.** One datapoint (2.7×). Ask whether a line-count ratio is even the right signal, or whether a diff-similarity measure would misfire less.
- **Deviation D1** — is one header comment genuinely better than nine in-section ones, or does locality win?
- **Deviation D3** — is "preserve silently" right for non-interactive runs, or should `/adapt` refuse to run at all against a grown section when nobody can answer?
- **The Growth check's `<start>`/`<end>`** rely on the agent having located section boundaries. Is that reliable enough to build a gate on, or does the gate need its own boundary-finding instruction?

- [ ] **Step 8: Push and land**

```bash
git push -u origin fix/adapt-content-loss-guards
```

Then land it — `/ship`, or `/superpowers:finishing-a-development-branch`. Do not leave the branch unmerged.

---

## Self-Review

**1. Spec coverage**

| Spec item | Task | Notes |
|---|---|---|
| §1 Step 6 asks for an impossible diff | Task 1 | Diff moved to mandatory Step 6 per D2 |
| §2 Report tells what survived, not what died | Task 2 | |
| §3 A grown marked section is user content | Task 4 | Non-interactive branch added per D3 |
| §4 Nothing tells the user where knowledge belongs | Tasks 2 + 3 | Header instead of per-block comments per D1 |
| §5 `xcode-tools.md` hardcodes a simulator model | Task 6 | Plus D4 fallout in Task 5 |
| "How to verify a fix" (3 items) | Task 7 | Fixture, run, assert-against-diff-not-report |
| "What is already right — do not fix" | — | No task touches the four-case logic, the `handoff.md` sniff test, or the demote rule. Task 4 only *appends* a sentence to existing case bullets. |

**2. Placeholder scan** — No TBDs. Every code step carries the literal content. The two `<start>`/`<end>` and `<path-to-block>` tokens inside the Growth check are deliberate: they are placeholders in the *emitted instruction*, filled by the agent at run time, not gaps in this plan. Task 8 Step 7 raises whether that is reliable enough.

**3. Type consistency** — The four `ADAPT_GUARDS` needles are introduced in Tasks 1–4 and asserted in one place (`test_every_adapt_guard_is_present`); each task's own test asserts its needle directly, so a typo between the lint constant and the SKILL.md text fails twice, not zero times. `.gstack/CLAUDE.md.pre-adapt` is spelled identically in Task 1 (write), Task 1 (diff), Task 4 (`sed` source) and Task 7 (assertion 1). The marker `gstack-xcode-tools-v6` appears in Task 6 Steps 4 (denylist range `v[0-5]`), 7 (block line 1), 8 (adapt case 1) and Task 7 assertion 3.

**4. Ordering** — Task 5 must precede Task 6: the `name=iPhone \d` denylist entry would otherwise fail on `ios-e2e-scaffold/SKILL.md`. Tasks 1–4 are strictly ordered (each extends the previous task's report/snapshot). Task 7 requires Tasks 1 and 4. Task 8 is last.
