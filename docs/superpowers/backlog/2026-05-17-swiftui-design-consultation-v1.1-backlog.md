---
title: swiftui-design-consultation v1.1 backlog — deferred findings from codex adversarial review
date: 2026-05-17
parent_spec: docs/superpowers/specs/2026-05-17-swiftui-design-consultation-design.md
parent_plan: docs/superpowers/plans/2026-05-17-swiftui-design-consultation-implementation.md
source: codex challenge review (session 019e35be-2f64-78b2-a8ad-51815222ff78)
status: BACKLOG — v1.1 candidates
---

# swiftui-design-consultation v1.1 backlog

After codex adversarial review on 2026-05-17, six CRITICAL findings
were patched inline (commits TBD — see plan v2 update). The 7
SIGNIFICANT and 3 MINOR findings were accepted as v1.1 backlog so
v2.2.0 can ship without scope creep. Document here so they're not
lost.

## SIGNIFICANT findings (v1.1 priority)

### S1. Model-as-dispatcher routing under-tested

**What codex flagged.** Spec lines 651-663 acknowledge native projects
can mis-dispatch to web. Plan smoke tests at lines 1854-1856 and
1894-1896 "verify by inspection" that the routing rules exist — but
don't test actual dispatch behavior in a real session.

**v1.1 fix.** Add a real end-to-end smoke test that:
1. Sets up a fresh repo with `.gstack/track = native`
2. Invokes `/design-consultation` in a non-interactive Claude Code
   session (`claude --print` mode)
3. Asserts the dispatched skill is `swiftui-design-consultation`,
   not the gstack web variant
4. Repeats with marker absent → asserts dispatch to web

**Why deferred.** Requires test harness infrastructure not yet in
this plugin. Real-session test cost ~1 minute per case. Worth
building for v1.1.

### S2. ✅ FIXED in v2.4.0 — macos-native-review chain gives iOS-only projects zero DESIGN.md native review

**Status: FIXED in v2.4.0.** Shipped `/superpowers-gstack:ios-native-review` as sibling skill — 13 iOS-specific categories mirroring macos-native-review structure. Phase 0 detects iOS vs macOS signals; multi-target projects run both. `macos-native-review` Phase 0 updated to point at the new sibling skill for iOS-only artifacts (instead of IDEAS.md). `setup-routing` + `adapt` evaluation tables also gained the missing macos-native-review row alongside the new ios-native-review row.

Original codex finding preserved below for history.

---



**What codex flagged.** For `track = ios`, the plan explicitly skips
macos-native-review (lines 1429-1433) because the skill's Phase 0
returns N/A for iOS-only artifacts (SKILL.md lines 61-64). The spec's
broad "auto-review on artifacts" claim (line 73) is technically wrong
for iOS-only consultations — only `review_macos_hig` on the `.swift`
files runs, not the DESIGN.md review.

**v1.1 fix.** Build `ios-native-review` as a sibling skill. The
backlog file `IDEAS.md` already mentions it. Spec scope and chain
behavior would then match for both tracks.

**Why deferred.** Building ios-native-review is a separate spec+plan
cycle (~3-4 hours). The current iOS-only behavior is honest — the
generated Swift files DO get `review_macos_hig` applied (which
contains many platform-agnostic rules), so the HIG budget is still
partially enforced for iOS-only projects, just not via the DESIGN.md
review path.

### S3. "Pure functions of same data model" is not actually enforced

**What codex flagged.** The data model in spec lines 170-222 is prose.
Phase 6 generators read an approved proposal Markdown file (plan lines
1243-1250) and substitute tokens from it (lines 1291-1293). No
structured object, no schema, no shared generator. Drift between
DESIGN.md and DesignSystem.swift is possible — the "they can't drift"
guarantee is aspirational, not enforced.

**v1.1 fix.** Define the data model as a real schema:
- Option A: YAML schema at
  `skills/swiftui-design-consultation/schema/proposal.schema.yaml`
- Option B: JSON Schema (more tooling-friendly)
- Generator reads schema, validates the proposal MD parses against it,
  then produces both DESIGN.md and DesignSystem.swift from the parsed
  object

**Why deferred.** Substantial implementation work (~4-6 hours). For
v1.0, the workflow is "Claude reads proposal, substitutes consistently"
— relying on Claude's ability to keep two outputs in sync from one
in-context input. Works for single-session generations; the drift risk
appears mostly on Phase 6 iteration loops or refresh consultations.

### S4. HIG iteration loop has no convergence guard

**What codex flagged.** Plan lines 1454-1462: 2-iteration cap, no
comparison against Phase 3 accepted proposal, no severity monotonicity.
Iteration 2 can leave user with WORSE artifact than they accepted
(e.g., fixing CRITICAL introduces SIGNIFICANT that wasn't there
before).

**v1.1 fix.** Add convergence check between iterations:
- Compare findings at iteration N vs iteration N-1
- Require severity monotonicity: no NEW CRITICAL allowed; SIGNIFICANT
  count must not increase; POLISH count can drift
- If monotonicity violated, ROLLBACK to iteration N-1 and ask user

**Why deferred.** Requires structured findings comparison (parsing
review output into a typed structure). Tied to S3 (formal data
model). Best built together.

### S5. ✅ FIXED in v2.2.0 — Contrast helper: printf locale break JSON

**What codex flagged.** Plan line 812: `printf '%.2f' "$RATIO"` emits
comma decimals under some `LC_NUMERIC` locales (e.g., German, French,
Norwegian — `LC_NUMERIC=nb_NO`). `"ratio": 4,62` is invalid JSON.

**Status: FIXED in v2.2.0 release.** Caught at implementation time
when the controller's `nb_NO.UTF-8` locale exposed it as a real bug
during Task 2.6 dispatch (not theoretical). The fix — `export LC_ALL=C`
at the top of `contrast-check.sh` after `set -euo pipefail` — was
folded into the v2.2.0 ship rather than deferred. Smoke-tested:
ratio 21.00 / 2.32 / 4.59 / 21.00 all emitted with dot decimals on
`nb_NO.UTF-8`. See commit `887f86b`.

### S6. ✅ FIXED in v2.3.2 — `adapt` preservation prevents updating stale routing rules

**Status: FIXED in v2.3.2.** Version marker (`<!-- gstack-routing-v1 -->`) added to the routing-section heading in both `setup-routing` template and `adapt` insertion block. `adapt` now scans for the marker and handles four cases (skip if matches, replace if older version, replace if no marker on legacy projects, append if heading absent) — preserves H2/H3 level symmetry across both skills.

Original codex finding preserved below for history.

---

**What codex flagged.** Plan lines 1651-1654: `adapt` skill skips
appending if `## Track-aware routing (dual-track)` section exists.
Prevents duplicates but ALSO prevents updating old or malformed
versions of the rule.

**v1.1 fix.** Add version marker to the routing section:
```markdown
## Track-aware routing (dual-track) <!-- gstack-routing-v1 -->
```

`adapt` checks for marker:
- Marker present + version matches → skip (idempotent)
- Marker present + version differs → REPLACE the section (upgrade
  path)
- Marker absent → APPEND

**Why deferred.** Routing rule semantics may evolve. Building the
versioning scheme is small but needs to land before any rule change
v1.1+, not in v2.2.0.

### S7. office-hours "next step" claim not implemented — **FIXED in v2.3.0**

**Status: addressed.** v2.3.0 ships
`/superpowers-gstack:office-hours-track-aware` (option A from below)
which wraps upstream office-hours, runs the brainstorm, then handles
track inference + next-step suggestion deterministically. The
swiftui-track skill (v2.2.0 only) is removed; its job is now folded
into the wrapper.

Original codex finding preserved below for history.

---


**What codex flagged.** Spec lines 514-515 and 628 say office-hours
completion now points the user toward swiftui-design-consultation
based on the track marker. The plan changes only `setup-routing` and
`adapt` (CLAUDE.md generation), NOT upstream office-hours. The
CLAUDE.md routing rule tells Claude how to interpret the marker, but
nothing actually inserts a "Next: /superpowers-gstack:swiftui-design-consultation"
line into office-hours' final message.

**v1.1 fix.** Two options:
- A: Wrap office-hours in a new skill `superpowers-gstack:office-hours-track-aware`
  that delegates to gstack's office-hours, then appends the next-step
  suggestion. Invasive but deterministic.
- B: Add a CLAUDE.md instruction: "After /office-hours completes,
  read `.gstack/track`; if present, print 'Next: /superpowers-gstack:swiftui-design-consultation'".
  Less invasive but model-as-dispatcher again.

**Why deferred.** Spec promise should be honored. Probably option B
for v1.1, kept lightweight.

## MINOR findings (acceptable, fix when convenient)

### M1. contrast-check.sh "Exit: 0 always" comment is inconsistent

Comment at plan line 738 says exit is always 0; actual code at lines
747-760 exits nonzero on usage error or invalid hex. Just update the
comment to match reality: `Exit: 0 on success, nonzero on usage/hex
error.` One-line docstring fix; not worth a release on its own.

### M2. Commit steps not idempotent

Every plan task has fixed `git commit -m ...` blocks. Re-running after
partial failure creates duplicate-topic commits or fails with "no
changes staged". Acceptable: the executing agent (or human) handles
this by reading current git state before committing. Real fix would
require dynamic commit-message generation based on staged diff — out
of scope.

### M3. "Phase 2/3 parallelize" handoff overstated

Plan's intro says Phase 2 (templates) and Phase 3 (SKILL.md) can
parallelize after Phase 1 lands. True for DOCUMENTATION authoring;
false for actual skill EXECUTION (Phase 3 references templates by
path). Update the parallelism note to clarify: "Phase 2 and Phase 3
SKILL.md WRITING can parallelize; Phase 3 EXECUTION requires Phase 2
templates to exist."

## Triage summary for v1.1 release planning

| Finding | Priority | Effort | Bundle |
|---|---|---|---|
| S5 (locale JSON bug) | URGENT | 5 min | **Patch v1.0.1 (hotfix)** |
| M1 (doc fix) | LOW | 2 min | Bundle with S5 patch |
| S2 (ios-native-review) | HIGH | 3-4 hours | v1.1 |
| S3 + S4 (schema + convergence) | HIGH | 4-6 hours | v1.1 (together) |
| S6 (versioned routing) | MEDIUM | 1 hour | v1.1 |
| S7 (office-hours next-step) | MEDIUM | 1-2 hours | v1.1 |
| S1 (real dispatch tests) | MEDIUM | 2-3 hours | v1.1 |
| M2 + M3 (cleanup) | LOW | 30 min total | v1.1 |

**Recommended v1.1 scope:** S2 + S3 + S4 + S6 + S7 + S1 + M2 + M3.
Total ~12-18 hours. Ship S5 + M1 as v1.0.1 hotfix immediately after
v2.2.0 lands.
