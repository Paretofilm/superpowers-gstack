# `/adapt` — proposed improvements

Field notes from a real re-adaptation, written so the next agent can act on them
without re-deriving the evidence.

**Source run.** `sing-replay` (Swift 6 / SwiftUI / SwiftData+CloudKit, dual-track
`both`), 2026-08-28. The project had been adapted with plugin **2.9.0** and was
re-adapted to **2.47.0** — 38 versions of drift, which is the case that exposes
these gaps. A first-time adaptation would have hit none of them.

**What happened.** The run was correct on every marker: nine sections landed on
their current versions, no duplicate headings, no unresolved `{{...}}`. It was
also silently destructive: `## Native Apple development tools` had grown from the
block's 73 lines to 198, and the 125-line delta — an entire project's worth of
hard-won knowledge — was replaced without a word. It was only recovered because
the operator happened to take a manual snapshot first.

Entries are ordered by how much damage they prevent, not by effort.

---

## 1. Step 6 asks for a diff that is impossible to perform

**Severity: high. This is the root cause of everything below.**

**Symptom.** `SKILL.md` Step 6, review item 3, instructs:

> **Verify preserved content** — diff the old vs new CLAUDE.md mentally. Was
> anything accidentally removed or mangled?

By the time Step 6 runs, Step 5 has already overwritten `CLAUDE.md`. The "old"
side of that diff does not exist anywhere the agent can reach. The word
*mentally* asks the agent to recall a ~500-line file it read once, several tool
calls ago, and compare it line by line against the new one. That is not a
verification — it is a request to hallucinate a clean bill of health, and it will
usually be granted.

In the source run the agent had to reach for `git diff` and a manually-copied
snapshot to answer the question at all. Neither is mentioned in the skill.

**Fix.** Make Step 5's first action a snapshot, and Step 6's diff a real one.

Add to Step 5, before any write:

```markdown
**Snapshot first.** Before the first modification, copy CLAUDE.md to
`.gstack/CLAUDE.md.pre-adapt` (create `.gstack/` if absent; it is already the
home of `track`). This is what Step 6 diffs against, and what the user restores
from if the run goes wrong. Do NOT rely on git: the project may have uncommitted
CLAUDE.md changes, and the file may not be tracked at all.
```

Then replace Step 6 review item 3 with:

```markdown
3. **Verify preserved content** — run `diff .gstack/CLAUDE.md.pre-adapt CLAUDE.md`
   and read the `<` side. Every removed line is either (a) plugin prose replaced
   by a newer version of the same block, which is expected, or (b) project
   content, which is a loss and must be surfaced. Classify each hunk into one of
   those two buckets and report the (b) list explicitly. Do not summarise the
   diff without reading it.
```

**Cost.** Two lines of instruction, one file write. No new dependency.

---

## 2. The report tells the user what survived, not what died

**Severity: high.**

**Symptom.** Step 6's report template is:

```
**Changes made:**
- [list each change]

**Preserved:**
- [existing CLAUDE.md content that was kept]
```

A list of survivors cannot reveal a casualty. The user reads "Preserved: Project
facts, Verifying your work, …", sees their file is intact, and never learns that
125 lines vanished from a section that is not on either list — because that
section *was* changed, so it is under "Changes made", where it appears as a
single line: `Native Apple development tools: v3 → v5`.

That line is true and completely uninformative about the 125 lines it destroyed.

**Fix.** Add a third, mandatory block to the report — and make it the one that
cannot be omitted when empty, so its absence is meaningful:

```markdown
> **Removed (not plugin prose):**
> - [each hunk from the Step 6 diff classified as project content, with the
>    section it came from and its line count]
> - If nothing project-authored was removed, write exactly:
>   `Nothing project-authored was removed.` Never omit this block — a missing
>   block reads as "not checked", which is the state this whole section exists
>   to prevent.
```

**Cost.** Template change only. Depends on improvement 1 for its input.

---

## 3. A grown marked section is user content — the skill already knows this

**Severity: high. The insight is already in the file; it is just applied to one
case out of nine.**

**Symptom.** Case 3 for `Code reuse discipline` (SKILL.md line ~269) reasons
correctly and explicitly:

> markerless `Code reuse discipline` headings cannot be pre-marker plugin
> content, which means they are *user-authored* sections that happen to share the
> heading. Replacing them would silently destroy the user's hand-written content.

The same failure mode reaches marked sections by a different road. A section that
carries a valid `v3` marker but has grown to 2.7× the block's size is *mostly*
user-authored, whatever its marker says. Case 2 replaces it wholesale anyway,
with no size check and no notice.

Measured in the source run: block 73 lines, project section 198. The delta held
an `-allowProvisioningUpdates` discovery that had replaced a manual
Apple-Developer-Portal step, three lessons about running on a physical iPhone,
and a hard-won note on a tool's current status. None of it was recoverable from
the plugin; all of it was recoverable only from git.

**Fix.** Add a size gate to the shared case-2 logic, stated once:

```markdown
**Growth check (applies to every marker-managed section, case 2 and 3).** Before
replacing, compare the existing section's line count to the block's. If the
existing section is more than ~1.5× the block, it has accumulated project
content that the replacement will destroy. Do not replace silently. Instead:

1. Extract the lines that do not appear in the new block.
2. Offer the user two options: move that content into a new **unmarked** H2
   section (recommended — see improvement 4), or abort this section's upgrade
   and leave it at its old version.
3. Never proceed past this gate without an answer. This is the one place in
   `/adapt` where silent correctness is worse than asking.
```

**Cost.** One shared rule plus a per-section cross-reference. The extraction in
step 1 is a plain `comm`/`diff` against the block file — no model judgement
needed to *detect* the loss, only to classify it.

**Note on the threshold.** 1.5× is a starting point, not a measurement. The
source run was 2.7×. A section at 1.1× is probably a user fixing a typo in plugin
prose; at 2×+ it is certainly not.

---

## 4. Nothing tells the user where project knowledge belongs

**Severity: medium, but it is the cheapest fix in this document and the one that
ends the problem permanently.**

**Symptom.** A user whose CLAUDE.md gets rewritten learns that marked sections
are volatile. What they do next decides whether it happens again. The obvious
move — paste the rescued content back where it was — guarantees a repeat at the
next upgrade. Nothing in the skill warns against it.

In the source run the operator caught this and put the recovered 125 lines in a
new unmarked `## Apple-lærdommer fra dette prosjektet` instead. That was a
judgement call made under time pressure, not something the skill suggested.

**Fix.** Two places, one sentence each.

In Step 6's report, after the "Removed" block:

```markdown
> **Where project knowledge belongs.** Sections carrying a `<!-- gstack-*-vN -->`
> marker are plugin-owned and replaced wholesale on every upgrade. Project-
> specific findings — the measurement you took, the flag that turned out to work,
> the thing that cost you an hour — belong in your own H2 section with no marker.
> `/adapt` never touches those.
```

And as a comment at the top of each file in `skills/setup-routing/blocks/`, so it
survives into the generated CLAUDE.md where a future agent will actually read it:

```markdown
<!-- Plugin-managed section. /adapt replaces this entire block on upgrade.
     Do not add project-specific content here; put it in an unmarked H2. -->
```

**Cost.** One template paragraph, one comment line per block file (11 files).

---

## 5. `blocks/xcode-tools.md` hardcodes a simulator model

**Severity: low, but it is wrong on the author's own machine today.**

**Symptom.** Lines 12 and 14 of `skills/setup-routing/blocks/xcode-tools.md`
name `iPhone 16` in the CLI-fallback column:

```
| Build Xcode project for simulator | … | `xcodebuild -scheme <name> -destination 'platform=iOS Simulator,name=iPhone 16' build` |
| Run XCTest / Swift Testing        | … | `xcodebuild test  -scheme <name> -destination 'platform=iOS Simulator,name=iPhone 16'` |
```

Xcode ships a rolling set of simulators and drops old ones. On the source
machine (2026-08-27) no iPhone 16 remained — only the 17 series — and
`xcodebuild` answered:

```
xcodebuild: error: Unable to find a device matching the provided destination specifier
```

which reads as a project misconfiguration, not as a stale device name. The
emitted CLAUDE.md was actively sending agents into that error.

**Fix.** Either resolve it at emit time via a placeholder, or stop naming a model
at all. The placeholder is better — a concrete command an agent can paste beats a
correct abstraction it has to expand.

Add to `blocks/PLACEHOLDERS.md`:

```markdown
## `{{IOS_SIMULATOR}}` (xcode-tools.md — native tracks only)

A simulator name that exists on this machine right now. Resolve with:

    xcrun simctl list devices available | grep -m1 -oE 'iPhone [0-9]+[a-z]*( Pro( Max)?)?'

Prefer a plain numbered model over a Pro/Max variant — it is the most likely to
exist on a collaborator's machine too. If the command returns nothing (no
simulators installed), emit `iPhone 17` and note in the report that no simulator
was found locally.
```

Then substitute in the two table rows, and add one line under the table:

```markdown
Simulator models come and go with Xcode releases. If `xcodebuild` says
"Unable to find a device matching the provided destination specifier", the
destination name is stale, not the project — check `xcrun simctl list devices
available`.
```

**Cost.** One placeholder, one shell command, two substitutions.

---

## How to verify a fix

These are cheap to test without a real 38-version-drift project:

1. **Build a fixture.** Copy any adapted CLAUDE.md, downgrade one marker
   (`v5` → `v3`), and paste 100 lines of obviously-project-specific prose into
   that section.
2. **Run `/adapt`.** With improvements 1–3 in place it must: write
   `.gstack/CLAUDE.md.pre-adapt`, detect the 2×+ growth, stop and ask, and — if
   told to proceed — list the removed project lines under "Removed".
3. **The regression to watch for** is the quiet one: a run that reports
   `Nothing project-authored was removed.` while the diff says otherwise. Assert
   against the diff, not against the report.

## What is already right — do not "fix" these

Worth stating, because two of them look like bugs until you read the reasoning:

- **The four-case marker logic is sound.** Nine sections upgraded cleanly in the
  source run, including the H3-rooted `Session Continuity` demote, which is the
  subtle one.
- **`Session Continuity` case 3's handoff.md sniff test** correctly told an
  emitted section from a user-authored one. Keep it.
- **The heading-level demote rule** and its "Verify after inserting" paragraph
  read as over-explained. They are not — the source run's only H3-rooted section
  hit exactly that path, and the instruction shape it warns about ("modify the
  first line, paste the rest verbatim") is genuinely easy to skip.
