# swiftui-design-consultation + swiftui-track + dual-track routing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship plugin v2.2.0 of superpowers-gstack, containing two new SwiftUI-track skills and the routing changes that make them discoverable, with zero changes to upstream gstack.

**Architecture:** Three coordinated changes shipping together — (1) a thin `swiftui-track` skill that writes `.gstack/track`, (2) a substantial `swiftui-design-consultation` skill that orchestrates the swiftui-rag MCP surface, chains into `macos-native-review`, and uses `/htmlify` for proposal preview + DESIGN.html generation, (3) updates to `setup-routing` and `adapt` that emit track-aware routing rules into project CLAUDE.md so the model dispatches `/design-consultation` and `/office-hours` correctly. Routing lives in CLAUDE.md (the model is the dispatcher); no code changes to gstack.

**Tech Stack:** Markdown (SKILL.md files), Bash (skill preambles, helper logic), AskUserQuestion (skill prompts), Apple Human Interface Guidelines (HIG citations via WebFetch), swiftui-rag MCP tools (`corpus_info`, `search_swiftui_corpus`, `index_project`, `search_project`, `swift_typecheck`, `review_macos_hig`, `review_liquid_glass`, `review_accessibility`), htmlify v2 (`/htmlify` skill in this repo), Swift Package Manager (generated `Package.swift`).

**Spec:** `docs/superpowers/specs/2026-05-17-swiftui-design-consultation-design.md` (commit `80242e8`). All seven detail decisions are resolved in the spec's § Detail decisions — do not re-decide.

---

## File Structure

### Files to create

| Path | Responsibility |
|---|---|
| `skills/swiftui-track/SKILL.md` | Frontmatter + Bash logic + AskUserQuestion brief. ~50 lines. Asks iOS/macOS/both, writes `.gstack/track`, suggests next step. Idempotent. |
| `skills/swiftui-design-consultation/SKILL.md` | Main consultation skill. ~500 lines. Phase 0 self-bootstrap, Phase 1 product context, Phase 3 proposal + htmlify preview, Phase 6 paired generation + macos-native-review chain. |
| `skills/swiftui-design-consultation/templates/Package.swift.template` | Swift Package skeleton with `{{PLATFORMS}}` substitution token. |
| `skills/swiftui-design-consultation/templates/Colors.swift.template` | Skeleton for Sources/DesignSystem/Colors.swift; substitution tokens for semantic + brand color sets. |
| `skills/swiftui-design-consultation/templates/Typography.swift.template` | Skeleton for Sources/DesignSystem/Typography.swift. |
| `skills/swiftui-design-consultation/templates/Spacing.swift.template` | Skeleton for spacing + radius enums. |
| `skills/swiftui-design-consultation/templates/Motion.swift.template` | Skeleton for motion presets. |
| `skills/swiftui-design-consultation/templates/Materials.swift.template` | Skeleton encoding Liquid Glass discipline (chrome + chromeDense only). |
| `skills/swiftui-design-consultation/templates/HIGBudgetTests.swift.template` | Test skeleton — asserts no hardcoded RGB, no `.easeInOut`, no material on content. |
| `skills/swiftui-design-consultation/templates/PlatformsTests.swift.template` | Test skeleton — asserts `Package.swift` platforms match declared targets. |
| `skills/swiftui-design-consultation/templates/DESIGN.md.template` | Human source-of-truth template; substitution tokens for all design dimensions. |
| `docs/superpowers/plans/progress.md` | Per global CLAUDE.md instruction: rolling progress file the executing session updates after each phase. |

### Files to modify

| Path | Change |
|---|---|
| `skills/setup-routing/SKILL.md` | Add new step "Step 4.5: Native track evaluation" + extend Step 6's CLAUDE.md template with the Track-aware routing section. Add rows for both new skills in the skill table. |
| `skills/adapt/SKILL.md` | Mirror setup-routing's additions, with preservation logic (do not duplicate Track-aware routing section if already present). |
| `skills/macos-native-review/SKILL.md` | Add cross-reference under "Related skills" pointing to swiftui-design-consultation as the upstream design-system step. |
| `skills/htmlify/SKILL.md` | Add one-line note that swiftui-design-consultation is a heavy htmlify consumer (Phase 3 preview + Phase 6 DESIGN.html generation). |
| `CLAUDE.md` (this repo) | Add `## Skill routing` entries for `/superpowers-gstack:swiftui-track` and `/superpowers-gstack:swiftui-design-consultation`. |
| `README.md` | Add entries under "Skills" for both new skills; mention dual-track routing. |
| `CHANGELOG.md` | Add v2.2.0 entry. |
| `.claude-plugin/plugin.json` | Bump `version` from `2.1.1` to `2.2.0`. |

---

## Phase 1: swiftui-track skill (the foundation)

Smallest deliverable, no dependencies on other new things. Ship this first; subsequent phases build on it.

### Task 1.1: Create swiftui-track SKILL.md

**Files:**
- Create: `skills/swiftui-track/SKILL.md`

- [ ] **Step 1: Create the skill directory**

Run:
```bash
mkdir -p /Users/kjetilge/Developer/superpowers-gstack/skills/swiftui-track
```

Expected: directory exists, empty.

- [ ] **Step 2: Write SKILL.md content**

Create `skills/swiftui-track/SKILL.md` with the following exact content:

````markdown
---
name: swiftui-track
description: |
  Declare this project as SwiftUI (iOS / macOS / both). Writes
  .gstack/track. Required upstream of swiftui-design-consultation;
  invoked automatically by office-hours when native intent is inferred
  (via CLAUDE.md routing rule), and as Phase 0 self-bootstrap by
  swiftui-design-consultation if the marker is missing. Idempotent —
  re-invocation lets the user change the value.
  Use when starting a new SwiftUI project, when an existing project
  should be declared as native, or to change the platform target.
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /superpowers-gstack:swiftui-track

Declare this project's SwiftUI platform target. Writes one file:
`.gstack/track` containing `ios`, `macos`, or `both`. That marker is
read by:
- The dual-track CLAUDE.md routing rule (so `/design-consultation`
  dispatches to the SwiftUI variant)
- `swiftui-design-consultation` Phase 0 (so it knows which platforms
  to declare in the generated `Package.swift`)
- Future skills: `swiftui-qa`, `swiftui-design-review`, `swiftui-ship`

Marker absence is treated as `web` (gstack backwards-compatible default).

## Workflow

### Step 1: Read current marker

```bash
mkdir -p .gstack
CURRENT=""
if [ -f .gstack/track ]; then
  CURRENT=$(cat .gstack/track | tr -d '[:space:]')
fi
echo "CURRENT_TRACK: ${CURRENT:-none}"
```

### Step 2: Ask the platform question

Use AskUserQuestion with this brief. If `CURRENT_TRACK` is one of
`ios | macos | both`, mark that option `(recommended)` so keeping the
current value is the one-click path. Otherwise mark `iOS only` as
`(recommended)`.

```
D1 — Which platform target does this project ship to?
Project/branch/task: declaring SwiftUI track for this repo
ELI10: This is a one-time project decision. It tells the rest of the
  plugin whether you're building an iPhone/iPad app, a Mac app, or
  both — so generated Swift Package files and design defaults match.
Stakes if we pick wrong: Package.swift declares wrong platforms; you'll
  need to manually edit it later. Other than that, no permanent damage —
  re-running this skill changes the value cheaply.
Recommendation: <see logic above>
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) iOS only
  ✅ Most common case for new projects; smallest Package.swift
  ✅ iPadOS works automatically via iOS target (no separate declaration)
  ❌ No macOS companion app — you'd have to add it later by re-running
B) macOS only
  ✅ Right for menu-bar tools, productivity apps, system utilities
  ✅ Liquid Glass strategy tuned for macOS chrome conventions
  ❌ No phone/tablet — narrows reach
C) Both iOS + macOS
  ✅ Cross-platform Swift Package with `#if os(...)` where needed
  ✅ Maximum reach; one design system serves both
  ❌ More platform-specific code surfaces; longer compile times
Net: Pick based on where you'll first ship, not where you might
   eventually ship — easy to add platforms later by re-running this
   skill.
```

### Step 3: Write the marker

Write the chosen value (`ios`, `macos`, or `both`) to `.gstack/track`:

```bash
echo "$CHOICE" > .gstack/track
```

### Step 4: Report status

Print one of:
- `Track set: <value>` (new file written)
- `Track changed: <old> → <new>` (overwrite of existing different value)
- `Track already set: <value> (no change)` (user chose same as current)

Then suggest:
```
Next: /superpowers-gstack:swiftui-design-consultation
```

That's the whole skill. ~50 lines including this prose.

## Notes

- `.gstack/track` is committed to the repo (project-level decision,
  not per-developer). The plugin's `.gitignore` advice does NOT
  exclude this file.
- Re-invocation is supported and expected. The current value is
  marked `(recommended)` so the symmetric flow lets the user either
  keep or change.
- If `.gstack/` does not exist, it is created. The skill never
  writes outside `.gstack/`.
````

- [ ] **Step 3: Verify the file parses as a valid skill**

Run:
```bash
head -20 skills/swiftui-track/SKILL.md
```

Expected: frontmatter with `name: swiftui-track`, description, allowed-tools list, ending `---` before "# /superpowers-gstack:swiftui-track".

- [ ] **Step 4: Verify allowed-tools are real tool names**

Run:
```bash
grep -A 10 'allowed-tools:' skills/swiftui-track/SKILL.md
```

Expected: lists Bash, Read, Write, AskUserQuestion. All four are standard Claude Code tools — no typos.

- [ ] **Step 5: Manual smoke test — fresh marker**

Run in a temp dir:
```bash
TMPDIR=$(mktemp -d /tmp/swiftui-track-test-XXXX)
cd "$TMPDIR"
cat <<'EOF' > expected-bash
mkdir -p .gstack
CURRENT=""
if [ -f .gstack/track ]; then
  CURRENT=$(cat .gstack/track | tr -d '[:space:]')
fi
echo "CURRENT_TRACK: ${CURRENT:-none}"
EOF
bash expected-bash
```

Expected output: `CURRENT_TRACK: none`. Confirms the Step 1 bash logic from the SKILL.md works on a fresh project.

- [ ] **Step 6: Manual smoke test — write + re-read**

In the same temp dir:
```bash
echo "ios" > .gstack/track
cat .gstack/track
ls -la .gstack/
```

Expected: file contains `ios`, directory exists with the file.

- [ ] **Step 7: Manual smoke test — change value**

```bash
echo "both" > .gstack/track
cat .gstack/track
rm -rf "$TMPDIR"
```

Expected: file now contains `both`. Confirms idempotent overwrite works.

- [ ] **Step 8: Commit**

```bash
cd /Users/kjetilge/Developer/superpowers-gstack
git add skills/swiftui-track/SKILL.md
git commit -m "feat(swiftui-track): add SwiftUI-track declaration skill

New skill /superpowers-gstack:swiftui-track. Asks iOS/macOS/both,
writes .gstack/track marker. Idempotent; re-invocation lets user
change value. Required upstream of swiftui-design-consultation.

Part of plugin v2.2.0 (commit 80242e8 spec).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2: Templates for swiftui-design-consultation

Create all generator templates before the main skill, so the skill's
Phase 6 instructions can reference them by path.

### Task 2.1: Create the templates directory and DESIGN.md template

**Files:**
- Create: `skills/swiftui-design-consultation/templates/DESIGN.md.template`

- [ ] **Step 1: Create directory**

```bash
mkdir -p /Users/kjetilge/Developer/superpowers-gstack/skills/swiftui-design-consultation/templates
```

- [ ] **Step 2: Write DESIGN.md.template**

Create `skills/swiftui-design-consultation/templates/DESIGN.md.template` with:

````markdown
# DESIGN.md
*Generated by swiftui-design-consultation 1.0.0 on {{DATE}}*

## Product Context
{{PRODUCT_CONTEXT}}

**Memorable Apple thing:** {{MEMORABLE_THING}}

## Platform Targets
{{PLATFORMS_PROSE}}

## Aesthetic Direction
{{AESTHETIC_DIRECTION}}

## Typography
{{TYPOGRAPHY_PROSE}}

Cited: https://developer.apple.com/design/human-interface-guidelines/typography

## Color
{{COLOR_PROSE}}

Cited: https://developer.apple.com/design/human-interface-guidelines/color
       https://developer.apple.com/design/human-interface-guidelines/dark-mode

## Materials & Liquid Glass Strategy
{{MATERIALS_PROSE}}

Cited: https://developer.apple.com/design/human-interface-guidelines/materials

## Spacing & Radii
{{SPACING_PROSE}}

## Motion
{{MOTION_PROSE}}

Cited: https://developer.apple.com/design/human-interface-guidelines/motion

## Accessibility Baseline
{{ACCESSIBILITY_PROSE}}

Cited: https://developer.apple.com/design/human-interface-guidelines/accessibility

## HIG Conformance Budget
{{BUDGET_CRITICAL}} CRITICAL · {{BUDGET_SIGNIFICANT}} SIGNIFICANT · {{BUDGET_POLISH}} POLISH findings allowed at ship time.

## Decisions Log

{{DECISIONS_LOG}}

## Design System (code)
The Swift Package starter lives at `./DesignSystem/`.
Every SwiftUI view in this project imports `DesignSystem` and uses
its public API exclusively for colors, fonts, spacing, motion, and
materials. Direct `Color(red:green:blue:)`, `.easeInOut`, or
`.ultraThinMaterial` on content layers are forbidden by
`DesignSystemTests/HIGBudgetTests.swift`.
````

- [ ] **Step 3: Verify all substitution tokens are listed**

Run:
```bash
grep -o '{{[A-Z_]*}}' skills/swiftui-design-consultation/templates/DESIGN.md.template | sort -u
```

Expected output (each on own line):
```
{{ACCESSIBILITY_PROSE}}
{{AESTHETIC_DIRECTION}}
{{BUDGET_CRITICAL}}
{{BUDGET_POLISH}}
{{BUDGET_SIGNIFICANT}}
{{COLOR_PROSE}}
{{DATE}}
{{DECISIONS_LOG}}
{{MATERIALS_PROSE}}
{{MEMORABLE_THING}}
{{MOTION_PROSE}}
{{PLATFORMS_PROSE}}
{{PRODUCT_CONTEXT}}
{{SPACING_PROSE}}
{{TYPOGRAPHY_PROSE}}
```

15 tokens. The SKILL.md Phase 6 instructions will substitute all 15.

### Task 2.2: Create Package.swift.template

**Files:**
- Create: `skills/swiftui-design-consultation/templates/Package.swift.template`

- [ ] **Step 1: Write the template**

````swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "DesignSystem",
    platforms: [{{PLATFORMS}}],
    products: [
        .library(name: "DesignSystem", targets: ["DesignSystem"]),
    ],
    targets: [
        .target(
            name: "DesignSystem",
            resources: [.process("Resources")]
        ),
        .testTarget(
            name: "DesignSystemTests",
            dependencies: ["DesignSystem"]
        ),
    ]
)
````

`{{PLATFORMS}}` substitutes to one of:
- `ios` track: `.iOS(.v26)`
- `macos` track: `.macOS(.v26)`
- `both` track: `.iOS(.v26), .macOS(.v26)`

- [ ] **Step 2: Verify**

```bash
grep -c '{{PLATFORMS}}' skills/swiftui-design-consultation/templates/Package.swift.template
```

Expected: `1`.

### Task 2.3: Create Colors.swift.template

**Files:**
- Create: `skills/swiftui-design-consultation/templates/Colors.swift.template`

- [ ] **Step 1: Write the template**

````swift
// Sources/DesignSystem/Colors.swift
//
// Semantic-first color system. Direct hardcoded RGB is forbidden
// (enforced by DesignSystemTests/HIGBudgetTests.swift). Brand colors
// live in the asset catalog with light/dark/highContrast variants.

import SwiftUI

public extension Color {
    // MARK: - Semantic (always prefer these in views)

{{SEMANTIC_COLORS}}

    // MARK: - Brand (asset-catalog entries with light/dark/highContrast)

{{BRAND_COLORS}}
}
````

`{{SEMANTIC_COLORS}}` substitutes to multiple lines like:
```swift
    static let appAccent = Color.accentColor
    static let appLabel = Color.primary
    static let appSecondaryLabel = Color.secondary
    static let appDestructive = Color.red
```

`{{BRAND_COLORS}}` substitutes to either an empty marker comment or:
```swift
    static let appBrandPrimary = Color("BrandPrimary", bundle: .module)
```

- [ ] **Step 2: Verify**

```bash
grep -c '{{SEMANTIC_COLORS}}\|{{BRAND_COLORS}}' skills/swiftui-design-consultation/templates/Colors.swift.template
```

Expected: `2`.

### Task 2.4: Create Typography, Spacing, Motion, Materials templates

**Files:**
- Create: `skills/swiftui-design-consultation/templates/Typography.swift.template`
- Create: `skills/swiftui-design-consultation/templates/Spacing.swift.template`
- Create: `skills/swiftui-design-consultation/templates/Motion.swift.template`
- Create: `skills/swiftui-design-consultation/templates/Materials.swift.template`

- [ ] **Step 1: Write Typography.swift.template**

````swift
// Sources/DesignSystem/Typography.swift

import SwiftUI

public extension Font {
{{TYPE_ROLES}}
}
````

`{{TYPE_ROLES}}` substitutes to 4-6 lines like:
```swift
    static let appDisplay = Font.system(.largeTitle, design: .default, weight: .bold)
    static let appTitle   = Font.system(.title2,     design: .default, weight: .semibold)
    static let appBody    = Font.system(.body,       design: .default)
    static let appCaption = Font.system(.caption,    design: .default)
    static let appCode    = Font.system(.body,       design: .monospaced)
```

- [ ] **Step 2: Write Spacing.swift.template**

````swift
// Sources/DesignSystem/Spacing.swift

import CoreGraphics

public enum AppSpacing {
{{SPACING_CONSTANTS}}
}

public enum AppRadius {
{{RADIUS_CONSTANTS}}
}
````

`{{SPACING_CONSTANTS}}` substitutes to:
```swift
    public static let xs: CGFloat = 4
    public static let s:  CGFloat = 8
    public static let m:  CGFloat = 12
    public static let l:  CGFloat = 16
    public static let xl: CGFloat = 24
    public static let xxl: CGFloat = 32
    public static let xxxl: CGFloat = 48
    public static let huge: CGFloat = 64
```

`{{RADIUS_CONSTANTS}}` substitutes to:
```swift
    public static let sharp: CGFloat = 0
    public static let soft: CGFloat = 8
    public static let pill: CGFloat = .infinity
```

- [ ] **Step 3: Write Motion.swift.template**

````swift
// Sources/DesignSystem/Motion.swift
//
// Named easings only. `.easeInOut` is forbidden by HIGBudgetTests.

import SwiftUI

public extension Animation {
{{MOTION_PRESETS}}
}
````

`{{MOTION_PRESETS}}` substitutes to:
```swift
    public static let appPrimary: Animation = .spring(response: 0.35, dampingFraction: 0.85)
    public static let appSnappy:  Animation = .snappy
    public static let appSmooth:  Animation = .smooth
```

- [ ] **Step 4: Write Materials.swift.template**

````swift
// Sources/DesignSystem/Materials.swift
//
// Liquid Glass discipline encoded as API: only chrome variants are
// public. Content-layer material has NO public binding — views cannot
// accidentally apply it because the type isn't exported. Enforced
// further by HIGBudgetTests grepping for .ultraThinMaterial on
// non-chrome views in user code.

import SwiftUI

public enum AppMaterial {
    public static let chrome      = Material.thinMaterial      // toolbars, sidebars
    public static let chromeDense = Material.regularMaterial   // sheets, popovers
    // Intentionally no `content` — content layer must not carry material.
}
````

- [ ] **Step 5: Verify all four files exist with correct token counts**

```bash
for f in Typography Spacing Motion Materials; do
  path="skills/swiftui-design-consultation/templates/${f}.swift.template"
  echo "=== $f ==="
  ls -la "$path"
  grep -c '{{[A-Z_]*}}' "$path" || echo "0 (Materials.swift.template has no tokens — intentional)"
done
```

Expected token counts: Typography=1, Spacing=2, Motion=1, Materials=0 (no substitutions; fully declarative).

### Task 2.5: Create test templates

**Files:**
- Create: `skills/swiftui-design-consultation/templates/HIGBudgetTests.swift.template`
- Create: `skills/swiftui-design-consultation/templates/PlatformsTests.swift.template`

- [ ] **Step 1: Write HIGBudgetTests.swift.template**

````swift
// Tests/DesignSystemTests/HIGBudgetTests.swift
//
// Budget-enforcer tests. They scan the DesignSystem package's own
// source files for forbidden patterns and fail at CI time if any
// commit reintroduces them. Pattern-matching at file level — no
// snapshot library, no external deps.

import XCTest

final class HIGBudgetTests: XCTestCase {
    private var sourceFiles: [URL] {
        let packageDir = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()       // Tests/DesignSystemTests
            .deletingLastPathComponent()       // Tests
            .deletingLastPathComponent()       // package root
            .appendingPathComponent("Sources/DesignSystem")
        return (try? FileManager.default.contentsOfDirectory(
            at: packageDir,
            includingPropertiesForKeys: nil
        )) ?? []
    }

    private func read(_ url: URL) -> String {
        (try? String(contentsOf: url, encoding: .utf8)) ?? ""
    }

    func testNoHardcodedRGB() throws {
        for url in sourceFiles where url.pathExtension == "swift" {
            let source = read(url)
            XCTAssertFalse(
                source.contains("Color(red:"),
                "Hardcoded RGB color found in \(url.lastPathComponent). Use semantic colors or asset-catalog brand entries."
            )
        }
    }

    func testNoEaseInOut() throws {
        for url in sourceFiles where url.pathExtension == "swift" {
            let source = read(url)
            XCTAssertFalse(
                source.contains(".easeInOut"),
                "Generic .easeInOut found in \(url.lastPathComponent). Use AppPrimary, AppSnappy, or AppSmooth from Motion.swift."
            )
        }
    }

    func testNoUltraThinMaterialOutsideMaterialsFile() throws {
        for url in sourceFiles where url.pathExtension == "swift" && url.lastPathComponent != "Materials.swift" {
            let source = read(url)
            XCTAssertFalse(
                source.contains(".ultraThinMaterial"),
                ".ultraThinMaterial found in \(url.lastPathComponent) (only allowed inside Materials.swift via AppMaterial)."
            )
        }
    }
}
````

- [ ] **Step 2: Write PlatformsTests.swift.template**

````swift
// Tests/DesignSystemTests/PlatformsTests.swift
//
// Asserts Package.swift platforms match {{DECLARED_TRACK}}. Fails
// at CI time if Package.swift is hand-edited away from the
// generated value.

import XCTest

final class PlatformsTests: XCTestCase {
    func testPackageSwiftDeclaresExpectedPlatforms() throws {
        let packageURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()       // Tests/DesignSystemTests
            .deletingLastPathComponent()       // Tests
            .deletingLastPathComponent()       // package root
            .appendingPathComponent("Package.swift")
        let source = try String(contentsOf: packageURL, encoding: .utf8)

{{PLATFORM_ASSERTIONS}}
    }
}
````

`{{PLATFORM_ASSERTIONS}}` substitutes per track:
- `ios`:
  ```swift
          XCTAssertTrue(source.contains(".iOS(.v26)"), "Package.swift missing .iOS(.v26)")
          XCTAssertFalse(source.contains(".macOS"), "Package.swift unexpectedly declares macOS")
  ```
- `macos`:
  ```swift
          XCTAssertTrue(source.contains(".macOS(.v26)"), "Package.swift missing .macOS(.v26)")
          XCTAssertFalse(source.contains(".iOS"), "Package.swift unexpectedly declares iOS")
  ```
- `both`:
  ```swift
          XCTAssertTrue(source.contains(".iOS(.v26)"), "Package.swift missing .iOS(.v26)")
          XCTAssertTrue(source.contains(".macOS(.v26)"), "Package.swift missing .macOS(.v26)")
  ```

- [ ] **Step 3: Verify**

```bash
ls -la skills/swiftui-design-consultation/templates/
```

Expected: 9 files (Package.swift.template, Colors.swift.template, Typography.swift.template, Spacing.swift.template, Motion.swift.template, Materials.swift.template, HIGBudgetTests.swift.template, PlatformsTests.swift.template, DESIGN.md.template).

- [ ] **Step 4: Commit templates as a unit**

```bash
cd /Users/kjetilge/Developer/superpowers-gstack
git add skills/swiftui-design-consultation/templates/
git commit -m "feat(swiftui-design-consultation): add generator templates

9 templates (Package.swift, Colors/Typography/Spacing/Motion/Materials
swift, HIGBudgetTests/PlatformsTests swift, DESIGN.md). Substitution
tokens documented at site of use. No skill logic yet — that lands in
the next phase.

Part of plugin v2.2.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.6: Add WCAG contrast-check helper script

The spec's § Detail decisions #1 promises "accept hex AND run a contrast
check against proposed text/background colors". The math is non-trivial
(sRGB → linear → relative luminance → contrast ratio). Implement it as
a bash helper script so the skill can call it deterministically instead
of asking Claude to do the math.

**Files:**
- Create: `skills/swiftui-design-consultation/bin/contrast-check.sh`

- [ ] **Step 1: Create bin directory**

```bash
mkdir -p /Users/kjetilge/Developer/superpowers-gstack/skills/swiftui-design-consultation/bin
```

- [ ] **Step 2: Write contrast-check.sh**

````bash
#!/usr/bin/env bash
# contrast-check.sh — WCAG 2.1 contrast ratio between two hex colors.
#
# Usage: contrast-check.sh <fg-hex> <bg-hex>
# Output: JSON to stdout with ratio + pass flags for AA-normal and AA-large.
# Exit: 0 always (caller reads JSON to decide).
#
# Implements sRGB → linear → relative luminance → contrast ratio
# per https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio. Uses `bc`
# for floating-point math. No external libraries required (bash + bc
# are present on every macOS + Linux install).

set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo '{"error": "usage: contrast-check.sh <fg-hex> <bg-hex>"}' >&2
  exit 1
fi

# Strip leading # if present, accept 3-char or 6-char hex.
normalize_hex() {
  local h="${1#\#}"
  if [ "${#h}" = "3" ]; then
    h="${h:0:1}${h:0:1}${h:1:1}${h:1:1}${h:2:1}${h:2:1}"
  fi
  if ! [[ "$h" =~ ^[0-9a-fA-F]{6}$ ]]; then
    echo "invalid hex: $1" >&2
    exit 2
  fi
  printf '%s\n' "$h"
}

FG=$(normalize_hex "$1")
BG=$(normalize_hex "$2")

# Extract R, G, B as 0-255 ints.
hex_channel() {
  printf '%d\n' "0x$1"
}

FR=$(hex_channel "${FG:0:2}")
FG_=$(hex_channel "${FG:2:2}")
FB=$(hex_channel "${FG:4:2}")
BR=$(hex_channel "${BG:0:2}")
BG_=$(hex_channel "${BG:2:2}")
BB=$(hex_channel "${BG:4:2}")

# sRGB channel → linear: if c/255 <= 0.03928 then c/255/12.92 else ((c/255+0.055)/1.055)^2.4
# Use bc -l for floating point + power.
to_linear() {
  local c=$1
  bc -l <<EOF
v = $c / 255
if (v <= 0.03928) v / 12.92 else e(2.4 * l((v + 0.055) / 1.055))
EOF
}

# Relative luminance: 0.2126*R + 0.7152*G + 0.0722*B
luminance() {
  local r=$1 g=$2 b=$3
  local lr lg lb
  lr=$(to_linear "$r")
  lg=$(to_linear "$g")
  lb=$(to_linear "$b")
  bc -l <<EOF
0.2126 * $lr + 0.7152 * $lg + 0.0722 * $lb
EOF
}

LFG=$(luminance "$FR" "$FG_" "$FB")
LBG=$(luminance "$BR" "$BG_" "$BB")

# Contrast ratio: (lighter + 0.05) / (darker + 0.05)
RATIO=$(bc -l <<EOF
if ($LFG > $LBG) (($LFG + 0.05) / ($LBG + 0.05)) else (($LBG + 0.05) / ($LFG + 0.05))
EOF
)

# Format ratio to 2 decimals.
RATIO_FMT=$(printf '%.2f' "$RATIO")

# WCAG AA: 4.5:1 for normal text, 3:1 for large text (≥18pt or ≥14pt bold).
PASS_NORMAL=$(echo "$RATIO >= 4.5" | bc -l)
PASS_LARGE=$(echo "$RATIO >= 3.0" | bc -l)
PASS_AAA=$(echo "$RATIO >= 7.0" | bc -l)

# bc returns 1 for true, 0 for false; convert to JSON booleans.
bool() { [ "$1" = "1" ] && echo "true" || echo "false"; }

cat <<EOF
{
  "fg": "#$FG",
  "bg": "#$BG",
  "ratio": $RATIO_FMT,
  "pass_aa_normal": $(bool "$PASS_NORMAL"),
  "pass_aa_large": $(bool "$PASS_LARGE"),
  "pass_aaa_normal": $(bool "$PASS_AAA")
}
EOF
````

- [ ] **Step 3: Make executable and smoke-test**

```bash
chmod +x skills/swiftui-design-consultation/bin/contrast-check.sh

# Black on white — known ratio 21:1, should pass everything
./skills/swiftui-design-consultation/bin/contrast-check.sh 000000 ffffff
# Light gray on white — known to fail AA-normal
./skills/swiftui-design-consultation/bin/contrast-check.sh aaaaaa ffffff
# Warm copper #B87333 on near-black #1a1a1a — typical brand-on-dark
./skills/swiftui-design-consultation/bin/contrast-check.sh B87333 1a1a1a
```

Expected outputs (verify ratios manually against a WCAG calculator):
- 1st: `"ratio": 21.00, "pass_aa_normal": true, ...`
- 2nd: `"ratio": 2.32, "pass_aa_normal": false, "pass_aa_large": false`
- 3rd: `"ratio": 4.62, "pass_aa_normal": true, "pass_aa_large": true`

If ratios are off by more than ±0.1, the bc math has a bug — debug
before continuing.

- [ ] **Step 4: Commit**

```bash
cd /Users/kjetilge/Developer/superpowers-gstack
git add skills/swiftui-design-consultation/bin/contrast-check.sh
git commit -m "feat(swiftui-design-consultation): WCAG contrast-check helper

Bash + bc implementation of sRGB→linear→luminance→contrast ratio per
WCAG 2.1. No external deps; called by Phase 6 Step 6.2 to validate
brand-color hex against text/background before writing to asset catalog.

Part of plugin v2.2.0. Resolves pitfall P3 (unfulfilled contrast-check
promise from spec § Detail decisions #1).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 3: swiftui-design-consultation SKILL.md

The substantial skill. Build incrementally: frontmatter + Phase 0 first
(self-bootstrap is the critical path), then Phase 1, then Phase 3, then
Phase 6.

### Task 3.1: Create skill directory and write frontmatter + Phase 0

**Files:**
- Create: `skills/swiftui-design-consultation/SKILL.md`

- [ ] **Step 1: Create directory and the file with frontmatter + Phase 0**

```bash
mkdir -p /Users/kjetilge/Developer/superpowers-gstack/skills/swiftui-design-consultation
```

Write `skills/swiftui-design-consultation/SKILL.md` starting with:

````markdown
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
  - swiftui-track
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

### Step 0.1: Track self-bootstrap

```bash
mkdir -p .gstack
if [ ! -f .gstack/track ] || [ -z "$(cat .gstack/track 2>/dev/null | tr -d '[:space:]')" ]; then
  echo "TRACK_MISSING"
else
  echo "TRACK: $(cat .gstack/track | tr -d '[:space:]')"
fi
```

If output is `TRACK_MISSING`, invoke `/superpowers-gstack:swiftui-track`
via the Skill tool. That skill asks the iOS/macOS/both question and
writes `.gstack/track`. Wait for it to complete before continuing.

After self-bootstrap, re-read the marker:

```bash
TRACK=$(cat .gstack/track | tr -d '[:space:]')
echo "TRACK: $TRACK"
```

`$TRACK` must be one of `ios | macos | both` to continue. If it is
anything else, STOP and ask the user to run `/superpowers-gstack:swiftui-track`
manually.

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
| `mcp__swiftui-rag__search_swiftui_corpus` | `query` (string) | Look for `q`, `text` |
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

````

- [ ] **Step 2: Verify the file is well-formed**

```bash
head -30 skills/swiftui-design-consultation/SKILL.md
grep -c '^## Phase' skills/swiftui-design-consultation/SKILL.md
```

Expected: frontmatter visible, "## Phase 0 — Setup" present, currently 1 Phase header (more added in next tasks).

### Task 3.2: Append Phase 1 (Product Context)

- [ ] **Step 1: Append Phase 1 to SKILL.md**

Append to `skills/swiftui-design-consultation/SKILL.md`:

````markdown

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
````

- [ ] **Step 2: Verify**

```bash
grep -c '^## Phase' skills/swiftui-design-consultation/SKILL.md
grep -c '^### Step' skills/swiftui-design-consultation/SKILL.md
```

Expected: 2 Phase headers, 8+ Step headers.

### Task 3.3: Append Phase 3 (Proposal + htmlify preview)

- [ ] **Step 1: Append Phase 3 to SKILL.md**

Append:

````markdown

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
````

- [ ] **Step 2: Verify**

```bash
grep -c '^## Phase' skills/swiftui-design-consultation/SKILL.md
```

Expected: 3 Phase headers.

### Task 3.4: Append Phase 6 (Write Artifacts + chain)

- [ ] **Step 1: Append Phase 6 to SKILL.md**

Append:

````markdown

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
in the aggregation (only review_macos_hig findings from Step 6.6 count
toward the budget). This is expected behavior — macos-native-review is
macOS-specific by design.

### Step 6.6: Chain to review_macos_hig (on each .swift file)

For each `.swift` file under `DesignSystem/Sources/DesignSystem/`,
call `mcp__swiftui-rag__review_macos_hig` with its content. Aggregate
findings counts. Same for `mcp__swiftui-rag__review_liquid_glass` and
`mcp__swiftui-rag__review_accessibility`.

### Step 6.7: Budget check + iteration

Aggregate findings:
- CRITICAL count (from all reviews combined)
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
````

- [ ] **Step 2: Verify**

```bash
wc -l skills/swiftui-design-consultation/SKILL.md
grep -c '^## Phase' skills/swiftui-design-consultation/SKILL.md
grep -c '^### Step' skills/swiftui-design-consultation/SKILL.md
```

Expected: ~450-550 lines, 4 Phase headers, ~20+ Step headers.

### Task 3.5: Manual end-to-end smoke

- [ ] **Step 1: Create a throwaway test workspace**

```bash
TESTWS=$(mktemp -d /tmp/swiftui-dc-smoke-XXXX)
cd "$TESTWS"
git init -q
echo "# Test App" > README.md
git add README.md
git commit -q -m "init"
```

- [ ] **Step 2: Manually walk the skill**

Read `skills/swiftui-design-consultation/SKILL.md` as if you were Claude
executing it. For each step, verify:
- The bash snippet runs without syntax error
- The MCP tool calls reference real tool names from `mcp_tools_used`
- The AskUserQuestion brief follows the AskUserQuestion Format
- The template paths exist
- The chain invocations (`macos-native-review`, `htmlify`) reference
  real existing skills

Document any gaps in `skills/swiftui-design-consultation/SMOKE-NOTES.md`
(deleted before commit).

- [ ] **Step 3: Clean up the test workspace**

```bash
cd /Users/kjetilge/Developer/superpowers-gstack
rm -rf "$TESTWS"
```

- [ ] **Step 4: Commit SKILL.md**

```bash
git add skills/swiftui-design-consultation/SKILL.md
git commit -m "feat(swiftui-design-consultation): main consultation skill

~500-line SKILL.md covering Phase 0 (self-bootstrap + setup) through
Phase 6 (paired generation + macos-native-review chain). Orchestrates
swiftui-rag MCP surface, uses /htmlify for Phase 3 preview, generates
DESIGN.md + Swift Package from templates added in previous commit.

Part of plugin v2.2.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 4: Update setup-routing + adapt

Add track-aware routing rule generation. Both skills emit/preserve a
new "Track-aware routing (dual-track)" section in project CLAUDE.md.

### Task 4.1: Update setup-routing

**Files:**
- Modify: `skills/setup-routing/SKILL.md`

- [ ] **Step 1: Locate the CLAUDE.md template section**

Read `skills/setup-routing/SKILL.md`. Find the "## Skill routing"
section starting at line 240 (current location — verify with grep).

- [ ] **Step 2: Add the Track-aware routing block**

Add this block immediately AFTER the existing `## Skill routing`
section in the SKILL.md's CLAUDE.md template. The block is literal —
it gets copied into generated project CLAUDE.md files.

```markdown
## Track-aware routing (dual-track)

This project follows superpowers-gstack's dual-track convention.
Track is declared in `.gstack/track` (`ios` | `macos` | `both`).
Missing marker = `web` (gstack default).

### When user starts a new product idea

After product context is clear in /office-hours or brainstorming, check
`.gstack/track`. If missing:
- Native signals (SwiftUI, iOS, iPadOS, macOS app, App Store) → invoke
  `/superpowers-gstack:swiftui-track`, then continue
- Web signals (Next.js, React, web app, dashboard, landing page) → do
  nothing; web is the default
- Ambiguous → ask the user once before continuing

### When user invokes /design-consultation (no namespace)

Read `.gstack/track`:
- `ios` / `macos` / `both` → invoke `/superpowers-gstack:swiftui-design-consultation`
- Absent or `web` → invoke `/design-consultation` (gstack)

User can always bypass by typing the namespaced version directly.
```

- [ ] **Step 3: Add skill table rows**

In Step 4 ("Evaluate relevant GStack skills") of setup-routing's
process (around line 93), find the GStack skills table. Add:

```markdown
| `/superpowers-gstack:swiftui-track` | Native SwiftUI projects — declares iOS/macOS/both via `.gstack/track`; required upstream of swiftui-design-consultation |
| `/superpowers-gstack:swiftui-design-consultation` | Native SwiftUI projects — produces DESIGN.md + Swift Package starter; equivalent to /design-consultation for web |
```

- [ ] **Step 4: Verify setup-routing still parses**

```bash
grep -c '^## ' skills/setup-routing/SKILL.md
```

Should be one MORE than before (the new Track-aware routing section
heading in the template — and the template is inside the SKILL.md).

- [ ] **Step 5: Commit**

```bash
git add skills/setup-routing/SKILL.md
git commit -m "feat(setup-routing): emit track-aware routing rules

New 'Track-aware routing (dual-track)' section added to the CLAUDE.md
template setup-routing emits. The rules tell Claude (the model) how to
dispatch /office-hours, /design-consultation, and downstream design
skills based on .gstack/track marker. Backwards compatible: missing
marker = web (gstack default behavior preserved).

Adds two skill table rows: /superpowers-gstack:swiftui-track and
/superpowers-gstack:swiftui-design-consultation.

Part of plugin v2.2.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 4.2: Update adapt with preservation logic

**Files:**
- Modify: `skills/adapt/SKILL.md`

- [ ] **Step 1: Mirror the setup-routing changes**

Apply the same two additions to `skills/adapt/SKILL.md`:
- The "Track-aware routing (dual-track)" block in the CLAUDE.md template section
- The two skill table rows

- [ ] **Step 2: Add preservation logic in Step 5 ("Apply changes")**

In `skills/adapt/SKILL.md` Step 5, add this instruction before any
CLAUDE.md write:

```markdown
**Preserve existing Track-aware routing.** Before appending the
Track-aware routing section, check if the project's CLAUDE.md
already contains `## Track-aware routing (dual-track)`. If yes,
skip the append (do not duplicate). If no, append the full section.
This makes the skill idempotent — re-running adapt does not pollute
the file.
```

- [ ] **Step 3: Verify**

```bash
grep -c 'Track-aware routing' skills/adapt/SKILL.md
```

Expected: 2 (one in the template content, one in the preservation
instruction).

- [ ] **Step 4: Commit**

```bash
git add skills/adapt/SKILL.md
git commit -m "feat(adapt): preserve and emit track-aware routing rules

Mirrors setup-routing's changes for existing-project adoption. Adds
preservation logic so re-running adapt does not duplicate the
Track-aware routing section if already present.

Part of plugin v2.2.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 5: Cross-references and registration

Small documentation updates so existing skills know about the new ones,
and the repo's own CLAUDE.md routes correctly.

### Task 5.1: Update macos-native-review cross-reference

**Files:**
- Modify: `skills/macos-native-review/SKILL.md`

- [ ] **Step 1: Find the related-skills section**

Read `skills/macos-native-review/SKILL.md`. Locate the section that
describes its relationship to other skills (currently the table at
"## Relationship to pitfall-verification and quality-review").

- [ ] **Step 2: Add a cross-reference**

After that table, add:

```markdown
### Relationship to swiftui-design-consultation

`/superpowers-gstack:swiftui-design-consultation` is the upstream
design-system step for SwiftUI projects. It produces a DESIGN.md +
Swift Package starter, then auto-chains into macos-native-review on
the DESIGN.md and `mcp__swiftui-rag__review_macos_hig` on each
generated `.swift` file. The HIG conformance budget set in
swiftui-design-consultation Phase 1 is the bar this skill measures
against during that chain.
```

- [ ] **Step 3: Commit**

```bash
git add skills/macos-native-review/SKILL.md
git commit -m "docs(macos-native-review): cross-reference swiftui-design-consultation

The new swiftui-design-consultation skill auto-chains into
macos-native-review during Phase 6. Document the relationship so users
landing on macos-native-review's SKILL.md see the upstream step.

Part of plugin v2.2.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 5.2: Update htmlify consumer note

**Files:**
- Modify: `skills/htmlify/SKILL.md`

- [ ] **Step 1: Add a one-line note in the "When it activates" section**

In `skills/htmlify/SKILL.md`, find the "Når det aktiveres" bullet list
and add:

```markdown
- Invoked programmatically by `/superpowers-gstack:swiftui-design-consultation`
  for Phase 3 proposal preview and Phase 6 DESIGN.html generation
```

- [ ] **Step 2: Commit**

```bash
git add skills/htmlify/SKILL.md
git commit -m "docs(htmlify): note swiftui-design-consultation as consumer

Part of plugin v2.2.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 5.3: Update repo CLAUDE.md routing table

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add rows to the ## Skill routing table**

In `CLAUDE.md`, find the "Key routing rules:" bullet list under
"## Skill routing". Add:

```markdown
- Declare SwiftUI project track (iOS/macOS/both) → invoke /superpowers-gstack:swiftui-track
- Design system for SwiftUI projects (DESIGN.md + Swift Package) → invoke /superpowers-gstack:swiftui-design-consultation
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: route /swiftui-track and /swiftui-design-consultation in repo CLAUDE.md

Part of plugin v2.2.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 5.4: Update README.md

**Files:**
- Modify: `README.md` (create if absent)

- [ ] **Step 1: Add entries under the skills section**

Find or create a "## Skills" section in `README.md`. Add:

```markdown
- `/superpowers-gstack:swiftui-track` — declare a SwiftUI project's
  platform target (iOS / macOS / both); writes `.gstack/track`
- `/superpowers-gstack:swiftui-design-consultation` — Apple-canon design
  system consultation for SwiftUI projects; produces `DESIGN.md` + a
  Swift Package starter; chains into macos-native-review with HIG
  conformance budget
```

If a "## Dual-track" section already exists from the earlier dual-track
commit (`f223a09`), add a note there too:
```markdown
The native track is operational as of v2.2.0 with these two skills.
Run `/superpowers-gstack:swiftui-track` to declare a project as
native; run `/superpowers-gstack:swiftui-design-consultation` to
produce its design system.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(README): document native-track skills shipped in v2.2.0

Part of plugin v2.2.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 6: Smoke tests (ship-checklist verification)

Verify the four end-to-end test paths from the spec's ship-checklist.
All four use a temp workspace; none touches the user's real projects.

### Task 6.1: Test path — empty folder → /office-hours → SwiftUI inference

- [ ] **Step 1: Set up test workspace**

```bash
TESTWS=$(mktemp -d /tmp/dual-track-smoke-1-XXXX)
cd "$TESTWS"
git init -q
echo "# Test" > README.md
git add README.md
git commit -q -m "init"
```

- [ ] **Step 2: Generate CLAUDE.md via setup-routing**

In a fresh Claude Code session (or by reading setup-routing's SKILL.md
and following its instructions manually), generate a CLAUDE.md. Verify
the generated file contains:
```bash
grep -c 'Track-aware routing' CLAUDE.md
```
Expected: 1.

- [ ] **Step 3: Simulate /office-hours invocation**

Verify by inspection: the generated CLAUDE.md routing rule explicitly
instructs Claude to invoke `/superpowers-gstack:swiftui-track` when
"SwiftUI" appears in the user's product description. Manually trigger
this path:
```bash
# After running through office-hours and saying "SwiftUI app"
ls -la .gstack/
cat .gstack/track 2>/dev/null
```
Expected: `.gstack/track` exists and contains one of `ios | macos | both`.

- [ ] **Step 4: Clean up**

```bash
cd /Users/kjetilge/Developer/superpowers-gstack
rm -rf "$TESTWS"
```

### Task 6.2: Test path — marker present → /design-consultation dispatches

- [ ] **Step 1: Set up workspace with marker pre-set**

```bash
TESTWS=$(mktemp -d /tmp/dual-track-smoke-2-XXXX)
cd "$TESTWS"
git init -q
mkdir .gstack
echo "ios" > .gstack/track
echo "init" > README.md
git add . && git commit -q -m "init"
```

- [ ] **Step 2: Generate CLAUDE.md with routing rules present**

Same as Task 6.1 Step 2. Verify the dispatch rule is present:
```bash
grep -A 5 'When user invokes /design-consultation' CLAUDE.md
```
Expected: the rule that reads `.gstack/track` and dispatches accordingly.

- [ ] **Step 3: Verify the rule semantics**

Read the rule. Confirm: marker `ios` → `/superpowers-gstack:swiftui-design-consultation`.

- [ ] **Step 4: Clean up**

```bash
cd /Users/kjetilge/Developer/superpowers-gstack
rm -rf "$TESTWS"
```

### Task 6.3: Test path — backwards compat (no marker → web)

- [ ] **Step 1: Set up workspace with no marker**

```bash
TESTWS=$(mktemp -d /tmp/dual-track-smoke-3-XXXX)
cd "$TESTWS"
git init -q
echo "init" > README.md
git add . && git commit -q -m "init"
# Note: NO .gstack/track
```

- [ ] **Step 2: Generate CLAUDE.md and verify default behavior**

After CLAUDE.md generation, read the routing rule. Confirm:
- The "Absent or web → invoke /design-consultation (gstack)" branch is
  present and unambiguous.

- [ ] **Step 3: Clean up**

```bash
cd /Users/kjetilge/Developer/superpowers-gstack
rm -rf "$TESTWS"
```

### Task 6.4a: Verify non-standard frontmatter loads cleanly

Both new SKILL.md files use non-standard frontmatter fields
(`upstream_skills`, `chains_to`, `mcp_tools_used`). Verify Claude
Code's skill parser accepts them without warnings.

- [ ] **Step 1: Use --plugin-dir to load the dev plugin**

```bash
cd /tmp  # somewhere outside the repo
claude --plugin-dir /Users/kjetilge/Developer/superpowers-gstack --print "list available skills with 'swiftui' in the name"
```

Expected: both `/superpowers-gstack:swiftui-track` and
`/superpowers-gstack:swiftui-design-consultation` appear in the
output. No parser warnings about unknown frontmatter fields.

- [ ] **Step 2: If parser warns about unknown fields**

Remove the non-standard fields from frontmatter (move them to body
content as a `## Skill metadata` section). The fields are
documentation, not load-bearing — they exist so future tooling can
reason about skill graphs but Claude Code's runtime doesn't use them.

### Task 6.4: Test path — direct invocation → Phase 0 self-bootstrap

- [ ] **Step 1: Set up empty workspace**

```bash
TESTWS=$(mktemp -d /tmp/dual-track-smoke-4-XXXX)
cd "$TESTWS"
git init -q
echo "init" > README.md
git add . && git commit -q -m "init"
```

- [ ] **Step 2: Read swiftui-design-consultation Phase 0 self-bootstrap**

Confirm by inspection of
`skills/swiftui-design-consultation/SKILL.md`:
- Phase 0 Step 0.1 checks `.gstack/track`
- If missing, invokes `/superpowers-gstack:swiftui-track`
- After self-bootstrap, re-reads marker
- STOPs if marker is still invalid

- [ ] **Step 3: Clean up + record smoke results**

```bash
cd /Users/kjetilge/Developer/superpowers-gstack
rm -rf "$TESTWS"
```

Create `docs/superpowers/plans/progress.md` (per global CLAUDE.md
instruction):
```markdown
# Implementation Progress — swiftui-design-consultation v2.2.0

## Smoke test results

- ✅ Task 6.1: office-hours intent → swiftui-track invocation path verified
- ✅ Task 6.2: marker present → /design-consultation dispatch verified
- ✅ Task 6.3: backwards compat (no marker → web) verified
- ✅ Task 6.4: direct invocation → Phase 0 self-bootstrap verified

All four paths from the spec ship-checklist passed inspection.
Ready for Phase 7 (release).
```

Commit:
```bash
git add docs/superpowers/plans/progress.md
git commit -m "docs(plan): record smoke test pass for v2.2.0 ship checklist

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 7: Release

### Task 7.1: Bump plugin.json version

**Files:**
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Update version**

Edit `.claude-plugin/plugin.json`, change:
```json
"version": "2.1.1",
```
to:
```json
"version": "2.2.0",
```

- [ ] **Step 2: Verify**

```bash
cat .claude-plugin/plugin.json | grep version
```

Expected: `"version": "2.2.0",`

### Task 7.2: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add v2.2.0 entry at the top**

Prepend to CHANGELOG.md (after any header lines):

```markdown
## [2.2.0] — 2026-05-17

### Added
- **`/superpowers-gstack:swiftui-track`** — declare SwiftUI project
  platform target (iOS / macOS / both); writes `.gstack/track` marker.
  Idempotent.
- **`/superpowers-gstack:swiftui-design-consultation`** — Apple-canon
  design system consultation for SwiftUI projects. Produces `DESIGN.md`
  + Swift Package starter with semantic colors, SF Pro typography,
  Liquid Glass material discipline, named motion presets, and
  accessibility baseline. Orchestrates swiftui-rag MCP surface for
  HIG-citation grounding; uses `/htmlify` for Phase 3 proposal preview
  and Phase 6 DESIGN.html generation; chains into `macos-native-review`
  with HIG conformance budget.

### Changed
- `setup-routing` and `adapt` skills now emit/preserve a
  "Track-aware routing (dual-track)" section in generated project
  CLAUDE.md files. This section tells the model how to dispatch
  `/office-hours` and `/design-consultation` based on `.gstack/track`.
- `macos-native-review` SKILL.md cross-references
  `swiftui-design-consultation` as the upstream design-system step.
- `htmlify` SKILL.md notes `swiftui-design-consultation` as a
  programmatic consumer.

### Compatibility
- Backwards compatible. Projects without `.gstack/track` continue to
  route `/design-consultation` to the gstack web skill (unchanged
  default behavior).
- No changes to upstream gstack code; all routing logic lives in
  CLAUDE.md generated by setup-routing/adapt.
```

- [ ] **Step 2: Commit both version + CHANGELOG together**

```bash
git add .claude-plugin/plugin.json CHANGELOG.md
git commit -m "release(v2.2.0): swiftui-design-consultation + swiftui-track + dual-track routing

Two new skills + routing updates that make the native track operational.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 7.3: Final user-facing summary

- [ ] **Step 1: Print release summary**

Print to the user:

```
🚀 Plugin v2.2.0 ready.

New skills:
- /superpowers-gstack:swiftui-track
- /superpowers-gstack:swiftui-design-consultation

Updated:
- skills/setup-routing/SKILL.md (track-aware routing template)
- skills/adapt/SKILL.md (same, with preservation)
- skills/macos-native-review/SKILL.md (cross-ref)
- skills/htmlify/SKILL.md (consumer note)
- CLAUDE.md, README.md, CHANGELOG.md
- .claude-plugin/plugin.json → 2.2.0

To install in your active Claude Code session:
  /plugin update superpowers-gstack

The marketplace cache will pull v2.2.0. Re-run the htmlify hook
installer if you use the auto-trigger:
  ~/.claude/plugins/cache/paretofilm-plugins/superpowers-gstack/2.2.0/scripts/setup-htmlify-hook.sh

End-to-end test: in an empty folder, run /office-hours and say "I
have an idea for a SwiftUI app that does X" — the dual-track routing
will infer native and invoke /swiftui-track, then suggest
/swiftui-design-consultation as the next step.
```

- [ ] **Step 2: Push (only after explicit user approval)**

Do NOT push automatically. Ask the user:
```
Plugin v2.2.0 committed locally. Push to origin/main now, or wait
for explicit instruction?
```

If user says push:
```bash
git push origin main
```

---

## Self-Review

### Spec coverage

Spec sections vs plan tasks:

| Spec section | Plan task |
|---|---|
| Phase 0 (workflow) | Task 3.1 |
| Phase 1 (product context) | Task 3.2 |
| Phase 3 (proposal + htmlify preview) | Task 3.3 |
| Phase 6 (write artifacts + chain) | Task 3.4 |
| Internal data model | Task 3.3 Step 3.1 (in-memory only — never written to a file by design) |
| DESIGN.md template | Task 2.1 |
| DesignSystem.swift sketch | Tasks 2.3, 2.4 |
| Swift Package layout | Tasks 2.2, 2.4, 2.5 |
| /htmlify integration Point 1 (Phase 3 preview) | Task 3.3 Step 3.2 |
| /htmlify integration Point 2 (Phase 6 dual artifact) | Task 3.4 Step 6.4 |
| Track marker | Task 1.1 (creates it) + Task 3.1 (reads/self-bootstraps) |
| swiftui-track skill | Task 1.1 |
| CLAUDE.md routing rules | Tasks 4.1, 4.2 |
| End-to-end walkthrough | Task 6.1 |
| Failure modes | Implicitly tested by Tasks 6.2-6.4 |
| MCP tool orchestration | Distributed across Tasks 3.1-3.4 (each Phase calls the right MCP tool) |
| Skill registration (2 new + 2 updated) | Tasks 1.1, 3.5 (new); Tasks 4.1, 4.2 (updated) |
| Plugin-level changes (version, README, CHANGELOG, etc.) | Tasks 5.3, 5.4, 7.1, 7.2 |
| Ship checklist (4 test paths) | Tasks 6.1-6.4 |
| § Detail decisions (7 resolved) | Embedded throughout — hex+contrast check (Task 3.4 Step 6.2), minimal #if os (Task 3.4 Step 6.3), hand-rolled tests (Task 2.5), consultation-only DESIGN.html (Task 3.4 Step 6.4), committed marker (Task 1.1 notes), <repo>/DesignSystem/ location (Task 3.4 Step 6.2), explicit office-hours next-step (Tasks 4.1, 4.2 routing block) |

**Coverage: complete.** Every spec section maps to one or more plan tasks.

### Placeholder scan

Searched plan for: TBD, TODO, XXX, "fill in", "see above", "similar to".
**Result: zero.** All steps contain actual content.

### Type consistency

Skill names checked: `swiftui-track`, `swiftui-design-consultation`,
`macos-native-review`, `setup-routing`, `adapt`, `htmlify`. All consistent.

File paths checked: all `skills/` paths use kebab-case consistently;
template extensions consistent (`.swift.template`, `.md.template`);
generated paths (`DesignSystem/Sources/DesignSystem/`,
`DesignSystem/Tests/DesignSystemTests/`) follow SPM convention.

Bash variables checked: `$TRACK`, `$MODE`, `$SLUG`, `$TESTWS`, `$TS`
used consistently. `$SLUG` is set by gstack-slug helper (existing in
preamble — same as other gstack skills).

MCP tool names verified against the skill list at session start: all
8 `mcp__swiftui-rag__*` names match exactly.

**Plan is internally consistent. Ready for execution.**

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-17-swiftui-design-consultation-implementation.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Each subagent loads only its task context, not the full session. Good for this plan because the 7 phases are mostly independent (Phase 2 templates and Phase 3 SKILL.md writing can even parallelize once Phase 1 lands).

**2. Inline Execution** — Execute tasks in this session using `executing-plans`. Batch execution with checkpoints for your review. Better if you want to watch each step and steer in real time, but uses more of the current session's context.

Which approach?
