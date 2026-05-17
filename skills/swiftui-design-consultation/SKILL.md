---
name: swiftui-design-consultation
description: |
  Apple-canon design system consultation for SwiftUI projects. Produces
  DESIGN.md (human source of truth) + a Swift Package starter
  (DesignSystem.swift + Package.swift + Tests) wired with semantic
  colors, SF Pro typography, Liquid Glass material discipline, named
  motion presets, and accessibility baseline. Orchestrates the
  swiftui-rag MCP surface for canonical patterns and HIG citations,
  uses /htmlify for Phase 3 proposal preview, chains into
  macos-native-review for HIG conformance gating.
  Use when starting a new SwiftUI project, when an existing SwiftUI
  project lacks a coherent design system, or when refreshing one.
  Phase 0 inlines the platform-question if .gstack/track is missing
  (since v2.3.0 — previously delegated to standalone swiftui-track
  skill, which was removed).
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - WebFetch
  - Skill
  - mcp__swiftui-rag__corpus_info
  - mcp__swiftui-rag__search_swiftui_corpus
  - mcp__swiftui-rag__index_project
  - mcp__swiftui-rag__search_project
  - mcp__swiftui-rag__swift_typecheck
  - mcp__swiftui-rag__review_macos_hig
  - mcp__swiftui-rag__review_liquid_glass
  - mcp__swiftui-rag__review_accessibility
upstream_skills:
  - office-hours-track-aware (typical entry — sets marker before this skill runs)
chains_to:
  - macos-native-review
  - htmlify
---

# /superpowers-gstack:swiftui-design-consultation

Apple-canon design system consultation for SwiftUI projects. Output:
`DESIGN.md` + `DesignSystem/` Swift Package + `DESIGN.html` (via htmlify).

## Phase 0 — Setup

### Step 0.0: Initialize gstack helpers (set $SLUG)

This skill writes per-project state under `~/.gstack/projects/$SLUG/`,
so `$SLUG` (the gstack project identifier derived from the git remote)
must be set before any other Phase reads or writes it.

```bash
# Pull gstack-slug into the current shell. Sets $SLUG = repo-slug
# from `git remote get-url origin` per gstack convention.
#
# CAREFUL: `eval "$(... 2>/dev/null)" || fallback` does NOT work — if
# gstack-slug is missing, command substitution returns empty, `eval ""`
# succeeds (exit 0), and the fallback never runs. Capture output first
# and check non-empty explicitly.
SLUG_OUTPUT=$(~/.claude/skills/gstack/bin/gstack-slug 2>/dev/null)
if [ -n "$SLUG_OUTPUT" ]; then
  eval "$SLUG_OUTPUT"
fi
if [ -z "${SLUG:-}" ]; then
  # Fallback: derive slug from git toplevel basename, or pwd basename
  # if not in a git repo.
  SLUG="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")"
  export SLUG
fi
if [ -z "$SLUG" ] || [ "$SLUG" = "/" ]; then
  echo "FATAL: could not derive SLUG. Aborting." >&2
  exit 1
fi
mkdir -p ~/.gstack/projects/"$SLUG"
echo "SLUG: $SLUG"
```

`$SLUG` is referenced throughout subsequent phases for state-file paths
(`~/.gstack/projects/$SLUG/design-proposal-{ts}.md`,
`~/.gstack/projects/$SLUG/swiftui-consultation-state.json`, etc.).

### Step 0.1: Track self-bootstrap (inline platform-question)

```bash
mkdir -p .gstack
if [ ! -f .gstack/track ] || [ -z "$(cat .gstack/track 2>/dev/null | tr -d '[:space:]')" ]; then
  echo "TRACK_MISSING"
else
  echo "TRACK: $(cat .gstack/track | tr -d '[:space:]')"
fi
```

If output is `TRACK_MISSING`, ask the platform question inline. Since
v2.3.0 there is no separate `swiftui-track` skill — the platform
question lives here (when invoked directly) and in
`/superpowers-gstack:office-hours-track-aware` Phase 3 (when reached
via the standard office-hours flow).

AskUserQuestion brief:

```
D0 — Which platform target does this project ship to?
Project/branch/task: declaring SwiftUI track for direct invocation
ELI10: I need to know iPhone/iPad, Mac, or both — so generated
  Package.swift and design defaults match. The marker is set once
  per project and read by all future swiftui-* skills.
Stakes if we pick wrong: Package.swift declares wrong platforms;
  easy to re-run later. No permanent damage.
Recommendation: iOS only (most common for new projects)
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) iOS only (recommended)
  ✅ Most common case; iPadOS works via iOS target automatically
  ✅ Smallest Package.swift surface
  ❌ No macOS companion — add later by re-running
B) macOS only
  ✅ Menu-bar tools, productivity apps, system utilities
  ✅ Liquid Glass strategy tuned for macOS chrome
  ❌ Narrows reach — no phone/tablet
C) Both iOS + macOS
  ✅ Cross-platform Swift Package; max reach
  ❌ More #if os() surfaces; longer compile times
Net: pick where you'll first ship.
```

Write the chosen value to `.gstack/track`:

```bash
echo "$CHOICE" > .gstack/track
```

After write, re-read:

```bash
TRACK=$(cat .gstack/track | tr -d '[:space:]')
echo "TRACK: $TRACK"
```

`$TRACK` must be one of `ios | macos | both` to continue. If it is
anything else (corrupted marker, user typed invalid value), STOP and
report `BLOCKED — invalid .gstack/track value`.

### Step 0.2: Detect project mode

```bash
MODE="greenfield"
if find . -maxdepth 3 -type f \( -name "*.xcodeproj" -o -name "Package.swift" -o -name "*.swift" \) 2>/dev/null | head -1 | grep -q .; then
  MODE="existing"
fi
echo "MODE: $MODE"
```

### Step 0.3: Verify MCP surface

Call `mcp__swiftui-rag__corpus_info` (no arguments). Verify the
returned JSON has:
- `runtime_version` (string, e.g., "1.3.1")
- `sample_count` (integer, > 0)
- `hig_rules` (array with at least 11 entries)
- `accessibility_rules` (array with at least 3 entries)

If any field is missing or the call fails, STOP and report:
`BLOCKED — swiftui-rag MCP unavailable. Run /sync-gbrain or check pipx install.`

### Step 0.3.1: Verify MCP parameter schemas (defensive)

Tool NAMES are only half the contract. Before any later phase
invokes these tools, verify the actual parameter NAMES match what
the plan assumes. The tool schemas are visible in Claude Code's
tool list (the same list this skill's frontmatter `allowed-tools`
references). Read them and confirm:

| Tool | Expected primary param | If schema differs, use the actual name |
|---|---|---|
| `mcp__swiftui-rag__index_project` | `path` (string) | Look for `repo_path`, `project_path`, `dir`, etc. |
| `mcp__swiftui-rag__search_project` | `query` (string) | Look for `q`, `text`, `pattern` |
| `mcp__swiftui-rag__search_swiftui_corpus` | `question` (string) — verified live | Optional: `platform`, `cluster_tag`, `hyde_doc`, `top_k` |
| `mcp__swiftui-rag__swift_typecheck` | `swift_code` (string), `target_versions` (array of strings) | Verify both names |
| `mcp__swiftui-rag__review_macos_hig` | `swift_code` (string) | Verify name |
| `mcp__swiftui-rag__review_liquid_glass` | `swift_code` (string) | Verify name |
| `mcp__swiftui-rag__review_accessibility` | `swift_code` (string) | Verify name |

If a tool's actual schema differs from the table above, the agent
executing this plan should ADJUST its invocations accordingly — do
not blindly use the names above if the schema disagrees. This is a
runtime-correctness gate; the plan's prose uses the most likely names
but the schema is authoritative.

If any tool is missing from the tool list (e.g., MCP server not
attached), STOP and report `BLOCKED — required MCP tool not available`.

### Step 0.4: Existing-project indexing

If `MODE` is `existing`, call `mcp__swiftui-rag__index_project` with
the repo root path. Cache the returned project ID for Phase 1 lookups.

### Step 0.5: Read existing DESIGN.md if present

```bash
if [ -f DESIGN.md ]; then
  echo "DESIGN_MD_EXISTS"
fi
```

If exists, read it. We may be doing a refresh consultation, in which
case Phase 3 will surface "keep / replace / refine" choices per pillar.

## Phase 1 — Product Context

Single combined AskUserQuestion brief. Three fields (platform is
already in `.gstack/track`, no need to re-ask).

### Step 1.1: Pre-fill from project context

If `README.md` or `CLAUDE.md` exist, read them and extract: product
name, audience, space/industry. Pre-fill the AskUserQuestion with what
you found, asking the user to confirm or refine.

If `MODE` is `existing` and `search_project` was indexed, call
`mcp__swiftui-rag__search_project` with these queries:
- `"Color extension"` — surface existing semantic-color decisions
- `"Font.system\|Font.custom"` — surface existing typography
- `"\.material\|\.glassEffect"` — surface existing material usage
- `"Color(red:"` — flag non-semantic colors (a quality signal)

Cache the counts: `N Color extensions, M Font declarations, K material
usages, X non-semantic colors flagged`. These appear in the Phase 1
prompt.

### Step 1.2: Ask the combined Phase 1 question

AskUserQuestion brief:

```
D1 — Product context for the SwiftUI design system

Project/branch/task: starting design consultation for this $TRACK project
ELI10: I need three things before I can propose a design system:
  what the product IS, what feeling it should evoke (so every later
  design choice serves one anchor), and how strict the HIG conformance
  bar is. The platform is already set ($TRACK from .gstack/track).
Stakes if we pick wrong: a memorable-thing answer that's too vague
  produces a generic-feeling app; a too-loose budget lets POLISH
  findings accumulate; an unclear audience leads to mis-tuned
  defaults (e.g., productivity-app density vs reader-app whitespace).

Field 1 — Product context confirm/refine
[Pre-filled from README/CLAUDE.md if found. User confirms or rewrites.]

Field 2 — Memorable Apple thing
"What's the one Apple-native quality you want this app to be remembered
for after a user opens it for the first time?" Examples: "as fluid as
Things", "as sharp as Linear-mac", "as quiet as Reeder", "as confident
as Stripe-mac". One sentence.

Field 3 — HIG conformance budget
A) Recommended: 0 CRITICAL · 0 SIGNIFICANT · ≤5 POLISH (recommended)
B) Strict: 0 / 0 / 0 (zero tolerance — for apps that must feel Apple-native on first launch)
C) Relaxed: 0 / 3 / 10 (early prototype; some POLISH and limited SIGNIFICANT acceptable)
```

If `MODE` is `existing`, prepend to the brief:
```
I indexed your project. Current patterns I found: $N Color extensions,
$M Font declarations, $K material usages, $X non-semantic colors
flagged. We can keep, replace, or refine each in Phase 3.
```

### Step 1.3: Store the answer

Cache the user's three answers as JSON in
`~/.gstack/projects/$SLUG/swiftui-consultation-state.json`:

```json
{
  "track": "ios",
  "product_context": "...",
  "memorable_thing": "...",
  "budget": { "critical": 0, "significant": 0, "polish": 5 },
  "mode": "greenfield",
  "existing_patterns": null
}
```

This state survives /clear, so a long consultation can resume.

## Phase 3 — Complete Proposal (with htmlify preview)

Build the internal DesignProposal data model, serialize to a structured
proposal Markdown, /htmlify it for Safari preview, then ask user to
approve / drill / change.

### Step 3.1: Build the data model

Query `mcp__swiftui-rag__search_swiftui_corpus` per pillar to ground
each choice in canonical patterns + HIG citations:

- Typography: query `"typography roles SF Pro semantic font"`
- Color: query `"semantic color asset catalog dark mode adaptive"`
- Materials: query `"Liquid Glass material chrome content layer"`
- Motion: query `"spring animation snappy smooth named easing"`
- Accessibility: query `"VoiceOver Dynamic Type contrast accessibility"`

Each returns 3-5 corpus samples + HIG-page citations. Use these as
grounding for proposing the design.

Build the in-memory DesignProposal object per the spec § "The internal
data model". Tokens map to the templates from Phase 2.

### Step 3.2: Serialize and /htmlify the proposal

Pin a single timestamp so the file written here and the path referenced
when invoking htmlify match exactly (do NOT call `$(date ...)` twice;
the two calls would produce different timestamps when seconds tick):

```bash
TS=$(date +%Y%m%d-%H%M%S)
PROPOSAL_PATH=~/.gstack/projects/"$SLUG"/design-proposal-"$TS".md
```

Then write the proposal MD to `$PROPOSAL_PATH`:
```
~/.gstack/projects/$SLUG/design-proposal-$TS.md
```

Structure the file as rich Markdown with:
- H1: "Design Proposal: $PRODUCT_NAME"
- H2 sections per pillar (Aesthetic, Typography, Color, Materials, Spacing, Motion, Accessibility)
- For each pillar: rationale + HIG citation links + table of choices
- Final H2: "HIG Conformance Budget" + "Decisions Log"

Build a /htmlify v2 plan JSON at `/tmp/design-proposal-plan.json` with:
- `flowchart-svg` for the Materials section (shows where glass goes / doesn't)
- `comparison-matrix` for Typography (display vs title vs body vs caption vs code)
- `stats-bar` for the HIG Budget panel
- Color swatches as a custom inline HTML block (via `section-card` body)
- `feedback_panel` with premises drawn from the actual proposal and `Approve / Drill into X / Change Y / Start over` radio

Invoke htmlify via the **Skill tool** (NOT a direct bin path — the
htmlify skill's base directory differs per install location: dev repo
vs marketplace cache vs vendored). Use the Skill invocation pattern
that Claude Code resolves automatically:

```
Skill(skill="superpowers-gstack:htmlify",
      args="~/.gstack/projects/$SLUG/design-proposal-$TS.md --plan /tmp/design-proposal-plan.json --open")
```

If the Skill-tool dispatch is unavailable (rare; only in spawned
sessions without the htmlify plugin), fall back to locating htmlify's
bin from the plugin cache:

```bash
HTMLIFY_BIN=""
for VERSION_DIR in ~/.claude/plugins/cache/paretofilm-plugins/superpowers-gstack/*/; do
  CANDIDATE="${VERSION_DIR}skills/htmlify/bin/htmlify"
  [ -x "$CANDIDATE" ] && HTMLIFY_BIN="$CANDIDATE"
done
# Or repo dev path:
[ -z "$HTMLIFY_BIN" ] && [ -x "$(git rev-parse --show-toplevel 2>/dev/null)/skills/htmlify/bin/htmlify" ] \
  && HTMLIFY_BIN="$(git rev-parse --show-toplevel)/skills/htmlify/bin/htmlify"
[ -z "$HTMLIFY_BIN" ] && { echo "htmlify not found"; exit 1; }

"$HTMLIFY_BIN" ~/.gstack/projects/$SLUG/design-proposal-$TS.md \
  --plan /tmp/design-proposal-plan.json --open
```

Prefer the Skill tool path; fall back to bin only if needed.

### Step 3.3: Ask user approve/drill/change

AskUserQuestion brief:

```
D2 — Does the proposed design system look right?

Project/branch/task: SwiftUI design consultation, Phase 3 proposal review
ELI10: I opened a visual preview in Safari (typography specimens, color
  swatches with light/dark toggle, material samples, motion previews,
  HIG budget panel, decisions log). Tell me which path: approve and
  ship, drill into a specific pillar to tighten it, change something
  specific, or restart the proposal from scratch.

A) Approve — write DESIGN.md + Swift Package now (recommended if the preview feels right)
B) Drill into [pillar] — tighten one pillar without committing the others
C) Change [pillar] — different direction for one pillar
D) Start over — rebuild the whole proposal with different constraints
```

If `A`: proceed to Phase 6.
If `B` or `C`: AskUserQuestion which pillar, then re-query that
pillar's corpus, rewrite that section of the proposal MD, re-htmlify,
loop back to D2.
If `D`: go back to Phase 1 to refine constraints.

### Step 3.4: Cache approved proposal

When user picks `A`, copy the proposal MD to:
```
~/.gstack/projects/$SLUG/swiftui-consultation-state.proposal.md
```

This is the source the Phase 6 generators read.

## Phase 6 — Write Artifacts (with macos-native-review chain)

Paired generation. DESIGN.md and DesignSystem/* are both written from
the approved proposal. Then run conformance review against the HIG
budget; iterate up to 2 times if over budget.

### Step 6.1: Generate DESIGN.md from template (with overwrite-safety)

**Before writing**, check if `<repo>/DESIGN.md` already exists:

```bash
if [ -f DESIGN.md ]; then
  BACKUP="DESIGN.md.backup-$(date +%Y%m%d-%H%M%S)"
  cp DESIGN.md "$BACKUP"
  echo "Existing DESIGN.md backed up to $BACKUP"
fi
```

This is the refresh-mode safety net: any prior DESIGN.md is preserved
under a timestamp suffix before overwrite. Same pattern for the Swift
Package in Step 6.2.

Then read `skills/swiftui-design-consultation/templates/DESIGN.md.template`.
Substitute all 15 tokens (`{{DATE}}`, `{{PRODUCT_CONTEXT}}`, etc.)
from the approved proposal. Write to `<repo>/DESIGN.md`.

### Step 6.2: Generate Swift Package (with overwrite-safety)

**Before writing**, back up any existing DesignSystem/ directory
(refresh-mode safety net, companion to Step 6.1's DESIGN.md backup):

```bash
if [ -d DesignSystem ]; then
  BACKUP_DIR="DesignSystem.backup-$(date +%Y%m%d-%H%M%S)"
  mv DesignSystem "$BACKUP_DIR"
  echo "Existing DesignSystem/ moved to $BACKUP_DIR"
fi
```

Then create the directory layout:

```bash
mkdir -p DesignSystem/Sources/DesignSystem/Resources
mkdir -p DesignSystem/Tests/DesignSystemTests
```

For each template in `skills/swiftui-design-consultation/templates/`:
- Read it
- Substitute tokens per `$TRACK` and the proposal data model
- Write to the corresponding path under `DesignSystem/`

Mapping:
- `Package.swift.template` → `DesignSystem/Package.swift`
  - Substitute `{{PLATFORMS}}` per `$TRACK`:
    - `ios` → `.iOS(.v26)`
    - `macos` → `.macOS(.v26)`
    - `both` → `.iOS(.v26), .macOS(.v26)`
- `Colors.swift.template` → `DesignSystem/Sources/DesignSystem/Colors.swift`
- `Typography.swift.template` → `DesignSystem/Sources/DesignSystem/Typography.swift`
- `Spacing.swift.template` → `DesignSystem/Sources/DesignSystem/Spacing.swift`
- `Motion.swift.template` → `DesignSystem/Sources/DesignSystem/Motion.swift`
- `Materials.swift.template` → `DesignSystem/Sources/DesignSystem/Materials.swift`
- `HIGBudgetTests.swift.template` → `DesignSystem/Tests/DesignSystemTests/HIGBudgetTests.swift`
- `PlatformsTests.swift.template` → `DesignSystem/Tests/DesignSystemTests/PlatformsTests.swift`

For brand colors with hex values, also create asset-catalog entries
under `DesignSystem/Sources/DesignSystem/Resources/Assets.xcassets/`.
Each brand color entry uses Xcode's color-set format with light, dark,
and high-contrast variants.

**WCAG contrast check (via Phase 2 helper):** for each brand hex
provided, call `skills/swiftui-design-consultation/bin/contrast-check.sh`
once against the proposed light-mode background and once against the
proposed dark-mode background. Parse the returned JSON:

```bash
# Example call from inside the skill — handle exit code explicitly
# so a missing `bc` or invalid hex doesn't silently pass the check.
CONTRAST_BIN="./skills/swiftui-design-consultation/bin/contrast-check.sh"

if RESULT_LIGHT=$("$CONTRAST_BIN" "$BRAND_HEX" "$BG_LIGHT_HEX" 2>&1); then
  PASS_LIGHT=$(echo "$RESULT_LIGHT" | grep -o '"pass_aa_normal": [a-z]*' | awk '{print $2}')
else
  PASS_LIGHT="error"
  echo "WARN: contrast-check failed for $BRAND_HEX vs $BG_LIGHT_HEX (exit $?). Skipping; surfacing to user." >&2
fi

if RESULT_DARK=$("$CONTRAST_BIN" "$BRAND_HEX" "$BG_DARK_HEX" 2>&1); then
  PASS_DARK=$(echo "$RESULT_DARK" | grep -o '"pass_aa_normal": [a-z]*' | awk '{print $2}')
else
  PASS_DARK="error"
  echo "WARN: contrast-check failed for $BRAND_HEX vs $BG_DARK_HEX (exit $?). Skipping; surfacing to user." >&2
fi
```

If either result is `error` (helper script failed — likely `bc` missing
or invalid hex), surface the warning to the user and ask explicitly
whether to accept the brand color without verified contrast. Do NOT
treat empty/missing PASS as a pass.

If either `PASS_LIGHT` or `PASS_DARK` is `false`, surface to the user:
- The actual ratio (from `RESULT_LIGHT.ratio` / `RESULT_DARK.ratio`)
- A flag: "Brand color $BRAND_HEX fails WCAG AA against $WHICH background"
- AskUserQuestion: keep this hex (override), or pick a different one?

The skill does NOT auto-adjust the hex (the spec said L*-rotation in
OKLCH but that requires a full color-space library — out of scope for
v1's bash helper). Manual adjustment by the user is the v1 fallback;
auto-suggestion can be added in v1.1.

### Step 6.3: Type-check generated Swift

Call `mcp__swiftui-rag__swift_typecheck` with the generated Swift code.
Target versions per `$TRACK`:
- `ios`: `["iOS-26.0"]`
- `macos`: `["macOS-26.0"]`
- `both`: `["iOS-26.0", "macOS-26.0"]`

If typecheck fails: fix the offending file (likely a missing `#if os()`
guard for platform-specific API) and retry. Hard cap: 3 typecheck
attempts. If still failing, STOP and report the diagnostic.

### Step 6.4: Generate DESIGN.html via Skill tool (auto-copy to repo root)

Invoke htmlify via the **Skill tool** (same pattern as Step 3.2; do
NOT use a hardcoded bin path):

```
Skill(skill="superpowers-gstack:htmlify", args="<repo>/DESIGN.md")
```

No --plan needed — v1 rendering is fine for the human-readable spec;
no feedback panel needed for the final DESIGN.html.

htmlify writes to `<repo>/.superpowers-html/DESIGN.html` by default,
but `.superpowers-html/` is typically gitignored. The spec promises
`DESIGN.html` lives next to `DESIGN.md` at repo root and ships
committed. After htmlify completes, copy the file:

```bash
mkdir -p .superpowers-html  # ensure htmlify output dir exists
if [ -f .superpowers-html/DESIGN.html ]; then
  cp .superpowers-html/DESIGN.html DESIGN.html
  echo "Copied DESIGN.html to repo root for commit"
else
  echo "WARN: htmlify did not produce expected output at .superpowers-html/DESIGN.html" >&2
  # Don't fail the skill — DESIGN.md is the source of truth; HTML is auxiliary.
fi
```

The repo-root `DESIGN.html` is what Step 6.8 commits. The
`.superpowers-html/DESIGN.html` is the htmlify-managed copy (refreshed
on every re-htmlify; remains gitignored). Both exist intentionally;
they have different lifecycles.

### Step 6.5: Chain to macos-native-review (on DESIGN.md)

macos-native-review reads the artifact from context, not from a path
argument. Two steps:

1. **Read DESIGN.md into context** via the Read tool:
   ```
   Read(file_path="<absolute path>/DESIGN.md")
   ```

2. **Invoke macos-native-review** via the Skill tool. The just-loaded
   DESIGN.md content is now in the model's context, so the skill's
   Phase 0 (macOS signal detection) and the 12-category review can
   read it directly:
   ```
   Skill(skill="superpowers-gstack:macos-native-review",
         args="Review the DESIGN.md just loaded into context. It is the design system spec for a SwiftUI project on track=$TRACK; budget is $BUDGET_CRITICAL/$BUDGET_SIGNIFICANT/$BUDGET_POLISH.")
   ```

Capture the skill's verdict and findings list by severity (CRITICAL,
SIGNIFICANT, POLISH). These feed into the budget check at Step 6.7.

If the project's `$TRACK` is `ios` only, macos-native-review's Phase 0
will return `N/A — iOS-only project`. In that case, skip its findings
in the aggregation (only the three review-* tool findings from Step
6.6 count toward the budget). This is expected behavior —
macos-native-review is macOS-specific by design.

### Step 6.6: Chain to review-* tools (on each .swift file)

The three review-* tools are **complementary, not overlapping**.
Each has its own ruleset; running all three is the only way to get
complete coverage:

| Tool | What it lints | Rules |
|------|---------------|-------|
| `mcp__swiftui-rag__review_macos_hig` | Full macOS HIG ruleset | C1, C2, S1–S9 (11 rules) |
| `mcp__swiftui-rag__review_accessibility` | Accessibility-only subset | A1, A2, A3 (3 rules) |
| `mcp__swiftui-rag__review_liquid_glass` | Liquid Glass-only subset of HIG | C1, S7, S8 (subset) |

For each `.swift` file under `DesignSystem/Sources/DesignSystem/`,
**invoke all three tools in parallel** (they are independent and
read-only). Each call passes the same `swift_code` argument.

Aggregate findings across all three tools by severity, **deduplicating
by `(rule_id, line)`** — `review_liquid_glass` returns a subset of
HIG findings, so the same `S7-material-on-content` finding can appear
in both its output and `review_macos_hig`'s. Count it once.

**Known limitation (as of swiftui-rag v1.4.0 / corpus v1.3.3):** the
`C1-glass-on-content` rule does not always fire when the `.glassEffect`
modifier is separated from its shape primitive by other method calls.
Pattern that DOES fire: `Circle().glassEffect()`. Pattern that has been
observed NOT to fire: `Circle().fill(...).frame(...).glassEffect()`.
If your generated code uses shape-then-modifier-then-glassEffect chains
on content layers, manually verify against Materials HIG. Track
upstream fix at `swiftui-rag-pipeline` issue tracker.

### Step 6.7: Budget check + iteration

Aggregate findings from **all three review-* tools** combined
(`review_macos_hig` + `review_accessibility` + `review_liquid_glass`),
deduplicated by `(rule_id, line)`, plus macos-native-review verdict:
- CRITICAL count
- SIGNIFICANT count
- POLISH count

Compare against the Phase 1 budget. If within budget:
- Commit the artifacts (one commit, message format below)
- Print summary: "✅ DESIGN.md + DesignSystem/ + DESIGN.html committed. 0 CRITICAL · 0 SIGNIFICANT · 3 POLISH (within budget of 0/0/5)."
- Done.

If over budget:
- List findings ranked by severity with file:line + proposed fix
- Update the data model to absorb the proposed fixes
- Regenerate all artifacts (Step 6.1 onwards)
- Re-run reviews
- Hard cap: 2 iterations. If still over budget after iteration 2, STOP
  and AskUserQuestion: "Findings exceed budget after 2 iterations.
  Choose: (A) ship anyway, (B) override budget to actual numbers,
  (C) refine manually now."

### Step 6.8: Commit (including .gstack/track marker)

The spec requires `.gstack/track` committed to the repo (project-level
decision, not per-developer). If the project's `.gitignore` already
excludes `.gstack/`, we need to force-add the marker AND record an
exception in `.gitignore` so future runs don't silently drop it.

```bash
# Ensure .gstack/track is committable
if git check-ignore -q .gstack/track 2>/dev/null; then
  # Project ignores .gstack/ — add an exception for the marker
  if ! grep -q '^!\.gstack/track$' .gitignore 2>/dev/null; then
    echo '!.gstack/track' >> .gitignore
    echo "Added exception for .gstack/track to .gitignore"
  fi
  git add .gitignore
  git add -f .gstack/track  # force-add since ignore rule still matches dir-walk
else
  git add .gstack/track
fi

git add DESIGN.md DESIGN.html DesignSystem/
git commit -m "feat: scaffold design system via swiftui-design-consultation

Generated by /superpowers-gstack:swiftui-design-consultation.

- DESIGN.md: design source of truth (HIG-cited)
- DesignSystem/: Swift Package with semantic colors, SF Pro typography,
  Liquid Glass material discipline, named motion presets, accessibility
  baseline
- DesignSystemTests: HIGBudgetTests + PlatformsTests enforce the
  conformance budget at CI time

Track: $TRACK
HIG findings: $CRITICAL CRITICAL · $SIGNIFICANT SIGNIFICANT · $POLISH POLISH (within budget)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```
