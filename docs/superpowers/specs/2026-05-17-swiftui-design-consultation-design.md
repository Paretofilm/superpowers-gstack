---
title: swiftui-design-consultation + swiftui-track + dual-track routing — design spec
status: READY — all decisions resolved; awaiting final user review before writing-plans
date: 2026-05-17
revised: 2026-05-17 (scope expanded to cover full dual-track routing; all 7 detail decisions resolved with safe defaults)
author: brainstorm session, Oslo
related:
  - skills/macos-native-review/SKILL.md
  - skills/htmlify/SKILL.md
  - skills/setup-routing/SKILL.md
  - skills/adapt/SKILL.md
  - ~/.claude/skills/gstack/design-consultation/SKILL.md (web sibling, gstack)
  - ~/.claude/skills/gstack/office-hours/SKILL.md (entry point, gstack)
upstream_dependency: swiftui-rag-mcp v1.3.1 (8 MCP tools)
ships_together: ["swiftui-design-consultation", "swiftui-track", "setup-routing update", "adapt update", "CLAUDE.md routing rules"]
plugin_version: 2.1.1 → 2.2.0
---

# swiftui-design-consultation + swiftui-track — design spec

> Dual-track routing for superpowers-gstack. Ships two new skills and
> updates two existing ones so that a SwiftUI project idea — starting
> from a `/office-hours` session in an empty folder — routes through
> the SwiftUI design track end to end, while preserving full
> backwards compatibility for web projects.
>
> **`swiftui-design-consultation`:** first native skill in the plugin.
> Targets iOS 26+ / macOS 26 Liquid Glass. Orchestrates the swiftui-rag
> MCP surface and chains into macos-native-review. Produces a `DESIGN.md`
> + a paired Swift Package starter, with a live HTML preview via
> `/htmlify` during proposal review.
>
> **`swiftui-track`:** thin track-declaration skill. Asks one question
> (iOS / macOS / both), writes `.gstack/track`, suggests the next step.
> Idempotent. Invoking it is the declaration.
>
> **Routing updates:** `setup-routing` and `adapt` skills generate
> track-aware routing rules in project CLAUDE.md so that `/office-hours`,
> `/design-consultation`, and other dual-track skills route correctly
> based on the marker.

## Why this skill, why now

The web sibling `/design-consultation` is the gstack workhorse for new web
projects. It produces a `DESIGN.md` (the design source of truth) after a
multi-phase consultation. There is no native equivalent. As soon as we start
shipping SwiftUI projects through this plugin we lose that source-of-truth
discipline — every project re-derives typography, color, motion, and
material choices from scratch, and there is no Apple-conformance gate.

The new swiftui-rag MCP surface (8 tools, post-T0–T12 reinstall, verified
2026-05-17 ~01:30) gives us what we need: `corpus_info` for discoverability,
`search_swiftui_corpus` for canonical-pattern grounding, `index_project` +
`search_project` for existing-project context, `swift_typecheck` for
generated code verification, and `review_macos_hig` + `review_liquid_glass`
+ `review_accessibility` for conformance gating. The smoke-test confirmed
the HIG gap is closed (4/4 violations flagged on the canonical sample).

This skill is the integration that makes the new MCP surface load-bearing
for the plugin.

## Constraints already locked in

Decided through six AskUserQuestions + one scope expansion during the
2026-05-17 brainstorm. Not open for re-decision in this spec:

| Decision | Choice | Why |
|---|---|---|
| **v1 scope** | Lean: Phase 1 + Phase 3 + Phase 6. Skip research, outside voices, AI mockup board. | Ship in one session, defer the unproven SwiftUI-mockup pipeline. |
| **Output artifacts** | DESIGN.md + Swift Package starter (DesignSystem.swift + Package.swift + Tests). | Boil-the-Lake — code is what views import, prose is what humans review. |
| **Platforms** | Three options on the `swiftui-track` skill: iOS / macOS / both. iPadOS-only and all-Apple-stack are manual `Package.swift` edits. | Three covers 95 % of cases; over-granular options inflate the surface for no real gain. |
| **Project mode** | Auto-detect. Existing → `index_project` + `search_project`. Greenfield → propose from scratch. | Uses new MCP capability; single skill, two modes. |
| **Chain with macos-native-review** | Both. HIG budget set in Phase 1, auto-review on artifacts after Phase 6, iterate ≤2 rounds. | Measurable bar; design lands HIG-clean. |
| **Architecture** | Approach C — proposal-first, paired generation from a single internal data model. | Best coherence + lowest cognitive load + prevents DESIGN.md ↔ Swift drift. |
| **Routing architecture** | CLAUDE.md-driven (model is dispatcher) + thin `swiftui-track` skill + self-bootstrap in consultation. | Zero changes to gstack; backwards compat; existing plugin pattern (routing in CLAUDE.md, not code). |
| **`swiftui-track` UX** | Asks one question (iOS / macOS / both), writes marker, suggests next. Idempotent. Re-invocation flow is symmetric (current value marked recommended). | Invoking the skill is the declaration; the only branch point is which platforms. |

## Workflow

### Phase 0 — Setup (now with track self-bootstrap)

1. **Track self-bootstrap.** Read `.gstack/track`. If missing or empty,
   invoke `/superpowers-gstack:swiftui-track` (which asks the
   iOS/macOS/both question and writes the marker). This guarantees the
   marker is set before Phase 1 reads it. If marker exists, continue.
2. Detect project mode by checking for `*.xcodeproj` / `Package.swift` /
   `*.swift` files. If found → existing-project mode. Otherwise →
   greenfield.
3. Verify MCP surface is alive: call `corpus_info` (cheap, ~50 ms cached)
   and confirm `runtime_version`, `sample_count`, and that all 8 tools
   are listed in the rule registry / capability surface.
4. **Existing project only:** call `index_project` on the repo root.
   Cache the indexer's project ID.
5. Read `DESIGN.md` if it already exists — we may be doing a refresh
   rather than a first consultation.

### Phase 1 — Product Context (single combined AskUserQuestion)

One AskUserQuestion brief, **three fields** (platform comes from the
marker, not asked here):

1. **Product confirm/refine** — pre-filled from README/CLAUDE.md if
   available. Confirm name, audience, space.
2. **Memorable Apple thing** — *"What's the one Apple-native quality you
   want this app to be remembered for?"* (e.g., "as fluid as Things",
   "as sharp as Linear-mac", "as quiet as Reeder"). Every later design
   decision must serve this answer.
3. **HIG conformance budget** — recommended default (0 CRITICAL, 0
   SIGNIFICANT, ≤5 POLISH) plus a strict alternative (0/0/0) and a
   relaxed alternative (0/3/10).

The **platform target** (iOS / macOS / both) is read from `.gstack/track`
— set by `swiftui-track` either via direct invocation, via Phase 0
self-bootstrap, or via office-hours intent detection upstream. The
value cascades directly into `Package.swift` `.platforms`.

If **existing project** detected, prepend a paragraph:
*"I indexed your project. Current patterns I found: N Color
extensions, M Font declarations, K material usages, X non-semantic
colors flagged. We can keep, replace, or refine each in Phase 3."*

### Phase 3 — Complete Proposal (with htmlify preview)

This is the consultation's center of gravity. Three sub-steps:

1. **Build internal data model.** Query `search_swiftui_corpus` per
   pillar (typography, color, materials, motion, accessibility) to
   ground each choice in canonical patterns + HIG citations. Fold
   in existing-project signals if applicable.

2. **Render and preview.** Serialize the data model to a structured
   Markdown file at `~/.gstack/projects/$SLUG/design-proposal-{ts}.md`.
   Invoke `/htmlify` on that file → open in Safari. User sees the
   design system as a live visual artifact (typography specimens in
   actual SF Pro / SF Mono / New York; color swatches with light/dark
   toggle; CSS-approximated material samples; 8-pt spacing ruler;
   CSS-spring motion previews; HIG conformance budget panel; decisions
   log with rationale).

3. **Approve / drill / change.** One AskUserQuestion in the chat:
   *Approve / Drill into X / Change Y / Start over*. Drill-down loop
   uses Approach-B-style pillar-scoped questions only for the pillar
   the user named. Each drill re-renders the proposal MD and
   re-htmlifies, so the Safari preview stays current.

### Phase 6 — Write Artifacts

Paired generation. Both `DESIGN.md` and `Sources/DesignSystem/*.swift`
are pure functions of the data model — they cannot drift because
they share a generator.

1. Write `DESIGN.md` to the project root.
2. Generate the Swift Package:
   - `DesignSystem/Package.swift` (platforms from Phase 1)
   - `DesignSystem/Sources/DesignSystem/{Colors,Typography,Spacing,Motion,Materials}.swift`
   - `DesignSystem/Sources/DesignSystem/Resources/Assets.xcassets` (brand colors light/dark/highContrast)
   - `DesignSystem/Tests/DesignSystemTests/{HIGBudgetTests,PlatformsTests}.swift`
3. Call `swift_typecheck` on the generated Swift against the declared
   platforms. If it fails to typecheck on macOS 26 SDK — fix and retry.
4. Run `/htmlify DESIGN.md` → write `DESIGN.html` next to DESIGN.md.
5. **Chain to macos-native-review** on `DESIGN.md`.
6. **Chain to `review_macos_hig`** on each generated `.swift` file.
7. Aggregate findings against Phase 1 budget.
   - Within budget → commit, present summary, done.
   - Over budget → surface findings + proposed fixes, regenerate from
     updated data model, re-check. Hard cap: 2 iterations. If still
     over budget after 2 → present honestly and ask whether to ship
     anyway, override budget, or refine manually.

## The internal data model

DESIGN.md and DesignSystem.swift are both pure functions of this object.
Phase 6 does not ask "what should I write?" — it serializes.

```
DesignProposal {
  product:   { name, audience, space, memorableThing }
  platforms: [iOS26, macOS26, ...]               // Package.swift + #if os() guards

  budget: { critical: 0, significant: 0, polish: 5 }

  aesthetic:  { direction, rationale }
  typography: {
    primary:   { family: "SF Pro", weights, sizes-by-role }
    monospace: { family: "SF Mono" or alternative }
    rounded:   { family: "SF Pro Rounded" | nil }
    serif:     { family: "New York" | nil }
    rationale
  }
  color: {
    semantic: {
      accent:          "Color.accentColor",
      label:           "Color.primary",
      secondaryLabel:  "Color.secondary",
      systemBackground, secondarySystemBackground, tertiarySystemBackground,
      destructive: ".red", success: ".green", warning: ".yellow", info: ".blue"
    }
    brand: [ ColorAsset(name, lightHex, darkHex, highContrastHex) ]
    rationale
  }
  materials: {
    chromeMaterial:      ".thinMaterial"        // toolbars, sidebars
    chromeMaterialDense: ".regularMaterial"     // sheets, popovers
    contentMaterial:     nil                    // NEVER on content layer
    glassEffectScopes:   [ "toolbar", "sheetBackground", "popoverBackground" ]
    rationale
  }
  spacing: { base: 8, scale: [4, 8, 12, 16, 24, 32, 48, 64] }
  radii:   { sharp: 0, soft: 8, pill: .infinity }
  motion: {
    primary: ".spring(response: 0.35, dampingFraction: 0.85)"
    snappy:  ".snappy"
    smooth:  ".smooth"
    rationale: "no generic .easeInOut anywhere"
  }
  accessibility: {
    dynamicTypeBaseline: ".body",
    contrastTarget: "WCAG AA + Apple Increase Contrast verified",
    voiceOverContract: "every non-text Button has .accessibilityLabel"
  }
}
```

## DESIGN.md template (the human source of truth)

```markdown
# DESIGN.md
*Generated by swiftui-design-consultation 1.0.0 on YYYY-MM-DD*

## Product Context
[product, audience, space, memorable Apple thing]

## Platform Targets
[iOS 26 / macOS 26 / dual / etc] — and what API differences this implies.

## Aesthetic Direction
[one paragraph + HIG citation grounding]

## Typography
[SF Pro / SF Pro Rounded / SF Mono / New York roles + sizes]
Cited: https://developer.apple.com/design/human-interface-guidelines/typography

## Color
[semantic-first principles + asset-catalog brand additions]
Cited: https://developer.apple.com/design/human-interface-guidelines/color
       https://developer.apple.com/design/human-interface-guidelines/dark-mode

## Materials & Liquid Glass Strategy
[where glass goes, where it doesn't, why]
Cited: https://developer.apple.com/design/human-interface-guidelines/materials

## Spacing & Radii
[8-pt base scale + radius vocabulary]

## Motion
[named easings + when each fires; NO .easeInOut]
Cited: https://developer.apple.com/design/human-interface-guidelines/motion

## Accessibility Baseline
[Dynamic Type, contrast, VoiceOver contract]
Cited: https://developer.apple.com/design/human-interface-guidelines/accessibility

## HIG Conformance Budget
0 CRITICAL · 0 SIGNIFICANT · ≤5 POLISH findings allowed at ship time.

## Decisions Log
[every choice + why + which alternative was rejected]

## Design System (code)
The Swift Package starter lives at ./DesignSystem/.
Every SwiftUI view in this project imports DesignSystem and uses its
public API exclusively for colors, fonts, spacing, motion, and materials.
```

## DesignSystem.swift sketch (the code source of truth)

```swift
// Sources/DesignSystem/Colors.swift
import SwiftUI
public extension Color {
    static let appAccent = Color.accentColor
    static let appLabel = Color.primary
    static let appSecondaryLabel = Color.secondary
    static let appDestructive = Color.red
    static let appBrandPrimary = Color("BrandPrimary", bundle: .module)
}

// Sources/DesignSystem/Typography.swift
public extension Font {
    static let appDisplay = Font.system(.largeTitle, design: .default, weight: .bold)
    static let appTitle   = Font.system(.title2,     design: .default, weight: .semibold)
    static let appBody    = Font.system(.body,       design: .default)
    static let appCaption = Font.system(.caption,    design: .default)
    static let appCode    = Font.system(.body,       design: .monospaced)
}

// Sources/DesignSystem/Spacing.swift
public enum AppSpacing { public static let xs = 4.0; public static let s = 8.0; /* ... */ }
public enum AppRadius  { public static let soft = 8.0; public static let pill = CGFloat.infinity }

// Sources/DesignSystem/Motion.swift
public extension Animation {
    static let appPrimary: Animation = .spring(response: 0.35, dampingFraction: 0.85)
    static let appSnappy:  Animation = .snappy
    static let appSmooth:  Animation = .smooth
}

// Sources/DesignSystem/Materials.swift  (Liquid Glass discipline encoded)
public enum AppMaterial {
    public static let chrome      = Material.thinMaterial
    public static let chromeDense = Material.regularMaterial
    // No `content` — content layer must not carry material.
}
```

## Swift Package layout

```
DesignSystem/
├── Package.swift                     # declares .iOS(.v26) / .macOS(.v26) per Phase 1
├── Sources/
│   └── DesignSystem/
│       ├── Colors.swift
│       ├── Typography.swift
│       ├── Spacing.swift
│       ├── Motion.swift
│       ├── Materials.swift
│       └── Resources/
│           └── Assets.xcassets       # brand colors: light / dark / highContrast
└── Tests/
    └── DesignSystemTests/
        ├── HIGBudgetTests.swift      # no hardcoded RGB, no .easeInOut, no material on content
        └── PlatformsTests.swift      # Package.swift platforms == declared targets
```

The tests are budget-enforcers, not feature tests. They fail at CI time
if a later commit reintroduces `Color(red:green:blue:)` or `.easeInOut`.
The budget is enforced beyond the consultation — it follows the code.

## /htmlify integration

`/htmlify` is the rich-rendering skill already in this plugin (v2.1.1).
Two integration points make swiftui-design-consultation visual without
adding a SwiftUI-mockup pipeline.

### Point 1 — Phase 3 proposal preview

After Phase 3 builds the data model, serialize a structured proposal
Markdown and invoke `/htmlify` on it. The HTML opens in Safari and
shows:

- **Typography specimens** rendered with actual system fonts (SF Pro
  Display, SF Pro Text, SF Mono, SF Pro Rounded, New York) at the
  roles' real sizes and weights
- **Color swatches** for both semantic palette and brand additions,
  with a light/dark mode toggle (CSS `prefers-color-scheme` + manual
  switch)
- **Material samples** approximated via CSS `backdrop-filter` —
  `.thinMaterial` vs `.regularMaterial` vs explicit "no material on
  content" demo
- **Spacing ruler** — 8-pt scale shown to actual pixel ratios
- **Motion previews** — CSS spring approximations of
  `.spring(response: 0.35, dampingFraction: 0.85)`, `.snappy`,
  `.smooth`
- **HIG conformance budget** panel
- **Decisions log** with rationale and HIG citations as live links

The user reads visually, then returns to chat to approve/drill/change.
On a drill, the proposal MD is rewritten and re-htmlified — the
Safari preview stays current.

### Point 2 — Phase 6 dual artifact

After writing `DESIGN.md`, invoke `/htmlify DESIGN.md` and save the
output as `DESIGN.html` next to it. The project then has:

- **`DESIGN.md`** — the source. Edited, code-reviewed, committed.
- **`DESIGN.html`** — the visual version for stakeholders. Can be
  opened from Finder, shared by file, or hosted.

When `DESIGN.md` is later edited (manual tweak or v1.1 re-consultation),
re-htmlify automatically (or via a save hook).

### Why this unlocks Phase 5 equivalent

The web sibling's Phase 5 (AI mockups + comparison board) generates
actual UI screenshots and runs them through a feedback loop. For
SwiftUI v1 we explicitly skipped this because the SwiftUI-mockup
pipeline is unproven. The /htmlify preview gives us ~75 % of the same
value without that uncertainty: the user sees the design system as a
coherent visual artifact, not individual screen mockups, but enough to
say "yes, this is the direction" or "no, the fonts are too cold."

Aligned with the user's global preference: "HTML is state-of-the-art
for AI agent output … MD beholdes for kunnskapsfilene."

## Dual-track routing (new — scope-expanded)

The four pieces below let a SwiftUI idea travel from "empty folder +
`/office-hours`" through `swiftui-track` and `swiftui-design-consultation`
without any changes to upstream gstack code.

### 1. Track marker

| Property | Value |
|---|---|
| **Path** | `.gstack/track` (project-relative; one file per project) |
| **Format** | Single line: `ios`, `macos`, or `both` |
| **Absence semantics** | Treated as `web` (backwards-compatible default for gstack-only projects) |
| **Encoding** | UTF-8, trailing newline ignored on read |
| **Set by** | `swiftui-track` skill (always); office-hours intent inference (when CLAUDE.md routing fires); self-bootstrap in `swiftui-design-consultation` (fallback) |
| **Read by** | CLAUDE.md routing rules (via the model); `swiftui-design-consultation` Phase 1 (to pick `Package.swift` platforms); future `swiftui-qa`, `swiftui-design-review`, `swiftui-ship` skills |
| **Survives** | `/clear`, `/compact`, context-handoff, Conductor workspace switches (it's a file on disk, not session state) |
| **Gitignored?** | **No** — committed to the repo so the track is project-level, not per-developer. Add `.gstack/` to `.gitignore` only if it later starts holding per-developer artifacts. |

### 2. `swiftui-track` skill

**Purpose:** declare this project as SwiftUI (and which Apple platforms
it targets). Idempotent. Re-invocation lets the user change the value.

**Location:** `skills/swiftui-track/SKILL.md`

**Frontmatter (sketch):**

```yaml
---
name: swiftui-track
description: |
  Declare this project as SwiftUI (iOS / macOS / both). Writes
  .gstack/track. Required upstream of swiftui-design-consultation;
  invoked automatically by office-hours when native intent is inferred,
  and as Phase 0 self-bootstrap by swiftui-design-consultation if
  the marker is missing. Idempotent — re-invocation lets the user
  change the value.
allowed-tools: [Bash, Read, Write, AskUserQuestion]
---
```

**Workflow:**

1. Read current `.gstack/track` if present.
2. AskUserQuestion: "Which platform target does this project ship to?"
   - A) iOS only (recommended default if no current value)
   - B) macOS only
   - C) Both iOS + macOS
   - If a current value exists, mark it `(recommended)` instead so
     keeping it is the one-click path.
3. Write the answer (`ios` / `macos` / `both`) to `.gstack/track`.
4. Print one of:
   - `Track set: <value>` (new)
   - `Track changed: <old> → <new>` (overwrite)
   - `Track already set: <value> (no change)` (kept the recommended)
5. Suggest: `Next: /superpowers-gstack:swiftui-design-consultation`

**Total skill body: ~30 lines including AskUserQuestion brief.**

### 3. CLAUDE.md routing rules (generated by setup-routing + adapt)

Both `setup-routing` (new projects) and `adapt` (existing projects)
get a new section to append/preserve in the project's `CLAUDE.md`:

```markdown
## Track-aware routing (dual-track)

This project follows superpowers-gstack's dual-track convention.
Track is declared in `.gstack/track` (`ios` | `macos` | `both`).
Missing marker = `web` (gstack default).

### When user starts a new product idea (/office-hours, brainstorming, etc.)

After product context is clear, check `.gstack/track`:
- If missing AND the description signals native (SwiftUI, iOS, iPadOS,
  macOS app, App Store, native Apple), invoke
  `/superpowers-gstack:swiftui-track` to declare the platform target,
  then continue.
- If missing AND the description signals web (Next.js, React, web app,
  dashboard, landing page, marketing site), do nothing — web is the
  default.
- If genuinely ambiguous, ask the user once before continuing.

### When user invokes /design-consultation (no namespace)

Read `.gstack/track`:
- `ios` / `macos` / `both` → invoke
  `/superpowers-gstack:swiftui-design-consultation`
- Absent or `web` → invoke `/design-consultation` (gstack)
- The user can always bypass by typing the namespaced version directly.

### When user invokes other dual-track skills (/design-review, /qa, /ship)

Web and SwiftUI variants will be added incrementally per the native
skill roadmap (`swiftui-qa`, `swiftui-design-review`, `swiftui-ship`).
The same `.gstack/track` lookup applies once those land.
```

`setup-routing` writes this for new projects. `adapt` preserves existing
CLAUDE.md content and appends this section if absent.

### 4. End-to-end walkthrough (the case the user asked about)

**User in empty folder:** "I have an idea for a SwiftUI app that does X."

```
1. User types: /office-hours
2. office-hours runs as today (gstack skill — no code changes).
3. During product-context phase, the model sees "SwiftUI" in the
   user's description.
4. The model reads CLAUDE.md track-aware routing rule (above) and
   matches the native-signal pattern.
5. Model invokes /superpowers-gstack:swiftui-track.
6. swiftui-track asks: iOS / macOS / both?
7. User picks (e.g., "iOS only"). Marker written: .gstack/track = "ios"
8. office-hours continues to completion, saves its design doc.
9. office-hours' completion line now points to next step:
   "Next: /superpowers-gstack:swiftui-design-consultation"
10. User runs it. Phase 0 reads the marker (no re-ask). Phase 1 asks
    product + memorable Apple thing + HIG budget. Phase 3 proposes,
    /htmlify-previews. Phase 6 writes DESIGN.md + Swift Package (iOS-only
    Package.swift derived from the marker), reviews against budget,
    commits.
```

**Result:** dual-track works end-to-end, no changes to gstack, no
duplicated code, marker survives across sessions and workspaces.

### Failure modes and mitigations

| Failure | What happens | Mitigation |
|---|---|---|
| Model forgets the CLAUDE.md routing rule and skips swiftui-track | office-hours saves design doc, user runs swiftui-design-consultation directly | Phase 0 self-bootstrap invokes swiftui-track — gap is caught |
| User invokes swiftui-design-consultation directly without office-hours | Same as above | Phase 0 self-bootstrap handles it |
| User invokes /design-consultation (no namespace) in a project with marker `ios` | Model reads CLAUDE.md rule, dispatches to swiftui-design-consultation | Rule is explicit; one round-trip cost only if model misses |
| Marker says `web` but user is now building SwiftUI | swiftui-design-consultation Phase 0 sees existing marker, doesn't overwrite | User runs `swiftui-track` explicitly to change |
| Project is genuinely both web and SwiftUI (rare) | Marker = `both` will be wrong for `.platforms` | Edge case — user edits Package.swift manually after; CLAUDE.md rule asks once for dual-target projects |

## MCP tool orchestration map

| Tool | Phase | Purpose |
|---|---|---|
| `corpus_info` | Phase 0 | Capability check; cache rule registry for citation lookup |
| `index_project` | Phase 0 (existing only) | Ingest current Swift sources |
| `search_project` | Phase 1 (existing only) | Surface current Color/Font/material patterns |
| `search_swiftui_corpus` | Phase 3 | Ground each pillar in canonical patterns + HIG cites |
| `swift_typecheck` | Phase 6 | Verify generated Swift against declared platforms |
| `review_macos_hig` | Phase 6 chain | Conformance gate on generated `.swift` |
| `review_liquid_glass` | Phase 6 chain (optional, narrower) | LG-only ship gate |
| `review_accessibility` | Phase 6 chain | A11y rule sweep on generated code |

`macos-native-review` (separate skill, not MCP) also fires in Phase 6
against the `DESIGN.md` artifact.

## Skill registration

Two new skills + two updated skills, all shipped together.

### New skills

| Item | Change |
|---|---|
| `skills/swiftui-design-consultation/SKILL.md` | NEW. Main consultation skill (this spec's centerpiece). |
| `skills/swiftui-track/SKILL.md` | NEW. ~30-line track-declaration skill. |

### Updated skills

| Item | Change |
|---|---|
| `skills/setup-routing/SKILL.md` | Generate the "Track-aware routing (dual-track)" CLAUDE.md section for new projects. Add row for swiftui-design-consultation in the skill table. |
| `skills/adapt/SKILL.md` | Same as setup-routing for existing projects: preserve existing CLAUDE.md content, append the new routing section if absent, never overwrite or duplicate. Add row for swiftui-design-consultation. |

### Plugin-level changes

| Item | Change |
|---|---|
| `.claude-plugin/plugin.json` version | bump `2.1.1` → `2.2.0` (minor — adds two skills + routing capability) |
| `README.md` | add entries under "Skills" for both new skills; mention dual-track routing |
| `CLAUDE.md` (this repo) | add `## Skill routing` row entries for both new skills under "Key routing rules" |
| `skills/macos-native-review/SKILL.md` | add cross-reference under "Related skills" pointing to swiftui-design-consultation as the upstream design-system step |
| `skills/htmlify/SKILL.md` | add note that swiftui-design-consultation is a heavy htmlify consumer (Phase 3 preview + Phase 6 DESIGN.html generation) |

### Invocation surfaces

- `/superpowers-gstack:swiftui-track` — direct user invocation, or auto via office-hours intent inference, or auto via swiftui-design-consultation Phase 0 self-bootstrap
- `/superpowers-gstack:swiftui-design-consultation` — direct user invocation, or auto via `/design-consultation` dispatch when marker present
- `/design-consultation` (no namespace) — gstack skill; dispatches to swiftui variant via CLAUDE.md rule when marker present

### Ship checklist (for the implementation plan to generate)

- [ ] Write `skills/swiftui-track/SKILL.md`
- [ ] Write `skills/swiftui-design-consultation/SKILL.md`
- [ ] Update `skills/setup-routing/SKILL.md` (new CLAUDE.md section + skill table row)
- [ ] Update `skills/adapt/SKILL.md` (same, with preservation logic)
- [ ] Update `skills/macos-native-review/SKILL.md` (cross-ref)
- [ ] Update `skills/htmlify/SKILL.md` (consumer note)
- [ ] Update repo `CLAUDE.md` (routing table rows)
- [ ] Update repo `README.md` (new skill entries)
- [ ] Bump `.claude-plugin/plugin.json` to `2.2.0`
- [ ] Test path: empty folder → `/office-hours` "SwiftUI idea" → ends with marker set + design doc + suggested next step
- [ ] Test path: marker present → `/design-consultation` dispatches to swiftui variant
- [ ] Test path: backwards compat — existing web project without marker → `/design-consultation` still routes to gstack web skill
- [ ] Test path: swiftui-design-consultation invoked directly in empty folder → Phase 0 self-bootstrap kicks in

## Out of scope for v1 (explicitly deferred)

- AI mockup generation pipeline for SwiftUI (Phase 5 web-equivalent)
- Persistent per-project taste profile (Phase 1.5 web-equivalent)
- Outside design voices (Codex + Claude subagent consultation)
- Competitive research browsing (Phase 2 web-equivalent)
- iPadOS-only, watchOS-only, tvOS-only, visionOS-only specialization
  (handled through the "all-Apple-26" platform option but not
  optimized per non-iOS/macOS platform)
- Three remaining native skills queued behind this:
  `macos-e2e-scaffold --run`, `swiftui-qa`, `swiftui-design-review`,
  `swiftui-ship`

## Detail decisions (resolved 2026-05-17)

Resolved via "go with defaults" pass. Each decision has the chosen
default and a one-line rationale.

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | **Brand-color sourcing** | Accept hex AND run a contrast check against proposed text/background colors; surface adjustments inline. | Boil-the-lake; catches accessibility bugs at design time; near-zero marginal cost. |
| 2 | **`#if os(...)` guard generation** | Minimal — guards only where the Apple SDK would fail to compile cross-platform (e.g., AppKit-only types on iOS). | Flat module risks silent bugs; aggressive guards are over-engineering. Minimal = compile-correct without noise. |
| 3 | **Snapshot test library** | Hand-rolled inline assertions — no `swift-snapshot-testing` dependency. | `HIGBudgetTests` are pattern-matching against generated `.swift` source (grep-equivalent). Zero deps keeps the package consumable everywhere. |
| 4 | **DESIGN.html versioning** | Consultation-only — re-render `DESIGN.html` only when `swiftui-design-consultation` runs. | Save-hook adds file watcher and complicates the skill; manual lets HTML rot. Consultation-only is the simple middle ground. User can `htmlify DESIGN.md` manually if needed. |
| 5 | **`.gstack/track` git status** | Committed to repo (project-level). Tracked by git, not gitignored. | Track is a project decision, not a per-developer preference. Committing means new collaborators inherit the correct routing immediately. |
| 6 | **Swift Package location** | `<repo>/DesignSystem/` (sibling directory at repo root). | Simplest; works for both greenfield and existing projects without workspace structure. User can `mv` to `Packages/DesignSystem/` if their project has Xcode workspace conventions. |
| 7 | **office-hours next-step suggestion** | Print `Next: /superpowers-gstack:swiftui-design-consultation` explicitly when the marker is `ios`/`macos`/`both` and the office-hours flow completes. | Discoverability beats minimalism. The CLAUDE.md routing rule already runs; surfacing the suggestion in the output costs nothing. |

These defaults are not open for re-decision in this spec. If
implementation reveals a problem (e.g., contrast-check library
choice), the implementation plan handles it.

## Status (READY)

| Section | Status |
|---|---|
| Group 1: workflow shape | ✅ approved 2026-05-17 |
| Group 2: artifacts | ✅ approved 2026-05-17 (with /htmlify-integration folded in) |
| Group 3: orchestration, registration, routing | ✅ approved 2026-05-17 (CLAUDE.md-driven dispatcher + swiftui-track + self-bootstrap; 3-option platform marker; full ship-checklist defined) |
| 7 detail decisions | ✅ resolved 2026-05-17 (safe defaults applied; see § Detail decisions) |

**Spec is READY.** Next step after final user review of this HTML:
commit this file to git, then invoke `writing-plans` to produce the
implementation plan that ships
`swiftui-design-consultation` + `swiftui-track` + routing updates as
plugin v2.2.0.

## Known limitations (in-scope, accepted by design)

- **Model-as-dispatcher reliability for `/design-consultation`.** The
  CLAUDE.md track-aware routing rule depends on Claude (the model)
  reading the rule when the user invokes `/design-consultation`
  without a namespace. After /compact, long sessions, or in fresh
  subagents, CLAUDE.md may not be in context — the model could
  mistakenly dispatch to the wrong variant. swiftui-design-consultation's
  Phase 0 self-bootstrap catches mis-dispatch *to it*, but the web
  `/design-consultation` (gstack skill) has no equivalent self-check —
  if mis-dispatched to web for a native project, it just runs as web.
  This is acceptable by design (the architecture chose CLAUDE.md
  routing over a code-level wrapper to avoid touching gstack). Users
  who see the wrong dispatch can type the namespaced version
  (`/superpowers-gstack:swiftui-design-consultation`) to bypass.

- **Concurrent skill invocations.** If two Claude Code sessions both
  run swiftui-design-consultation in the same project, both write to
  `DESIGN.md`, `DesignSystem/`, and `.gstack/track` (last-writer-wins).
  Project-state artifacts under `~/.gstack/projects/$SLUG/` are
  timestamp-distinguished so they don't collide. Acceptable for v1.

## Known issues to log separately

- **htmlify feedback panel copy-to-clipboard does not work via file://.**
  Reported during this brainstorm session — `navigator.clipboard.writeText`
  is restricted by Safari on `file://` origins. The fallback path
  ("Clipboard unavailable — text is selected, press Cmd/Ctrl-C") works
  when the user clicks the "Copy feedback as prompt" button, but not
  when selecting text manually. Confirmed via inspection of
  `skills/htmlify/src/render/components/feedback-panel.ts` lines
  123-139. Separate fix, not in this spec's scope.
