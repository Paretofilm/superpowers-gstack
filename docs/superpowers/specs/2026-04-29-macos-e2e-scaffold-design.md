# `/macos-e2e-scaffold` — Design Spec

**Status:** Approved 2026-04-29
**Plugin version:** 1.9.1 → 1.10.0 (minor bump, new skill)
**Branch:** `feat/macos-e2e-scaffold` (off main)
**Related:** Sibling-stubs `ios-e2e-scaffold`, `swiftui-snapshot-scaffold`, `appkit-e2e-scaffold` (deferred to IDEAS.md)

---

## 1. Overview

A one-shot scaffolding skill for macOS SwiftUI projects that lack XCUITest infrastructure. Invoked from project root, it creates a UI Test target, an accessibility-identifier convention, ranked TIER-1/2/3 test stubs, and a Claude-readable xcresult runner script.

**Genre:** project-level, code-modifying. Mirrors `setup-routing` in shape (one-shot, generates files), mirrors `macos-native-review` in tone (severity-tiered output, Phase 0 self-check). Distinct from `pitfall-verification`/`quality-review`/`macos-native-review` which review artefacts without modifying code.

**The question this skill answers:** *Is this project E2E-tested at the UI level?* — and if not, here's the foundation, the convention, and the first 5–7 test stubs.

---

## 2. Motivation

XCUITest is Apple's official E2E testing framework, free, supported, and the right answer for "click button → assert on screen state" tests. But it has a steep onboarding cliff:

1. UI Test Bundle target setup differs across project types (SPM vs xcodegen vs plain .xcodeproj)
2. Accessibility-identifier conventions are project-specific and rarely documented
3. xcresult parsing requires bespoke tooling for AI-readable test output
4. First-test-stubs require knowing which flows matter (heuristic decision)

A motivated developer can solve each in isolation. Bundling them into a deterministic skill is what makes XCUITest accessible to projects that have skipped it for years.

**Observed need:** SwiftConfig (concurrent project to this plugin) reached production-shape with extensive unit-test coverage but zero UI tests. Native macOS app windows pop up during `xcodebuild test -destination 'platform=macOS'` runs because tests host inside the app process — but no actual E2E assertions exist. The gap is real.

---

## 3. Architecture

**Type:** plugin-internal skill, manually invoked.
**Path:** `skills/macos-e2e-scaffold/SKILL.md`
**Trigger:** `/macos-e2e-scaffold` from a Swift project root. Not auto-invoked anywhere (modifies project files; user must consent per project).

**Execution model:** deterministic Read+Grep+pattern-matching. No LLM judgment in the heuristic. Same model as `pitfall-verification`/`quality-review`/`macos-native-review`. Reproducible across runs.

**Outputs (when run from a fresh project):**

| Artifact | Path | Tier |
|---|---|---|
| UI Test target setup | `<App>UITests/` (project-type-dependent, see §9) | required |
| Smoke test | `<App>UITests/SmokeTest.swift` | TIER-1 #1 |
| Happy-path test | `<App>UITests/HappyPathTests.swift` | TIER-1 #2 |
| Error-recovery test | `<App>UITests/ErrorRecoveryTests.swift` | TIER-1 #3 |
| Modal+menu tests | `<App>UITests/ModalAndMenuTests.swift` | TIER-2 (if pattern present) |
| Multi-window+toolbar | `<App>UITests/MultiWindowAndToolbarTests.swift` | TIER-3 (if pattern present) |
| Identifier convention | `docs/accessibility-identifiers.md` | required |
| xcresult runner | `scripts/run-uitests.sh` | required |
| Source modifications | Top 5 views (with batch confirmation) — `.accessibilityIdentifier(...)` added | required |

---

## 4. Phase 0 Self-Check (refuse-conditions)

Before any other action, the skill runs three checks. Any failure → return early with explanation.

| Check | Detect via | Refuse-message |
|---|---|---|
| Swift project | grep for `*.xcodeproj` directory or `Package.swift` in cwd | "Not a Swift project. /macos-e2e-scaffold requires .xcodeproj or Package.swift in project root." |
| SwiftUI macOS app | grep for `WindowGroup`, `Window(`, `Settings {`, `MenuBarExtra(` in `*.swift` under project source root | "No SwiftUI macOS app target detected. Skill is macOS-only — for iOS use /ios-e2e-scaffold (deferred), for AppKit use /appkit-e2e-scaffold (deferred)." |
| Not already scaffolded | check if `<App>UITests/` exists with > 1 `.swift` test file | "UI test target already exists with N test files. Skill won't overwrite — extend manually instead." |

**Phase 0 output format** (always emitted, even on success):

```
## /macos-e2e-scaffold Phase 0
✅ Swift project detected (SwiftConfig.xcodeproj)
✅ SwiftUI macOS app (WindowGroup found in SwiftConfigApp.swift:12)
✅ No existing UI test target

Project type: xcodegen-managed (.xcodegen.yml detected)
Scheme: SwiftConfig
Source root: SwiftConfig/
Total .swift files in source root: 47

Proceeding with audit + scaffold.
```

---

## 5. Scope

### In-scope
- macOS XCUITest target scaffolding (project-type-aware: xcodegen, SPM, plain .xcodeproj)
- Standard SwiftUI controls: `Button`, `Toggle`, `TextField`, `Picker`, `NavigationLink`, `Sheet`, `MenuBarExtra`, `WindowGroup`, `Window`, `ToolbarItem`, `.commands { ... }`
- Accessibility-identifier suggestion + auto-application with batch confirmation
- TIER-1/2/3 test-stub generation (deterministic pattern-match)
- xcresult-to-Claude-readable runner script
- One-shot delivery (no continuous mode)

### Out-of-scope
- iOS / watchOS / visionOS — deferred to sibling skills (IDEAS.md)
- AppKit-only views (`NSWindow`, `NSViewController`, NSAccessibility) — deferred to `appkit-e2e-scaffold`
- Snapshot-testing (`swift-snapshot-testing`) — deferred to `swiftui-snapshot-scaffold`
- New project bootstrap (use `xcodegen` or Xcode template — outside skill responsibility)
- Custom view introspection beyond standard SwiftUI controls
- Performance / load testing (`measure { ... }` blocks)
- Accessibility audit — covered by `macos-native-review` Category 8
- Continuous coverage gate — deferred to potential v2 sibling `swiftui-e2e-coverage`
- Cross-target dependency resolution (skill assumes app target is self-contained)

---

## 6. Heuristic Process

Deterministic, top-down, Read+Grep based. Order matters.

### Step 1: Detect project type
1. If `.xcodegen.yml` or `project.yml` exists → **xcodegen-managed**
2. Else if `Package.swift` exists and contains `.executableTarget(name:` → **SPM-based**
3. Else if `*.xcodeproj` exists → **plain .xcodeproj**

### Step 2: Detect scheme name
- xcodegen: read `name:` field at root of `xcodegen.yml`/`project.yml`
- SPM: read `name:` from `Package.swift`'s `Package(name: ...)`
- plain .xcodeproj: parse `*.xcodeproj/xcshareddata/xcschemes/*.xcscheme` filenames; fallback to directory name

### Step 3: Find source root
- xcodegen: read `targets.<schemename>.sources.path` from yml
- SPM: `Sources/<TargetName>/`
- plain .xcodeproj: parse `project.pbxproj` for `path = ` of main app target's source group; fallback to `<schemename>/`

### Step 4: Walk Scene tree
1. Grep source root for `WindowGroup`, `Window(`, `Settings {`, `MenuBarExtra(`
2. For each Scene: grep its body for `NavigationLink(destination:`, `.sheet(content:`, `.fullScreenCover(content:`
3. Recursively follow destinations to build view-graph (max depth: 5; cycle detection by view-name set)
4. For each view in graph, count interactive controls: `Button`, `Toggle`, `TextField`, `Picker`, `NavigationLink`

### Step 5: Rank views
Sort views by `(reference_count + interactive_control_count)` descending. Top 5 receive identifier suggestions.

### Step 6: Detect TIER mappings
- TIER-1 #1 (Smoke): always (uses Scene-root window-title)
- TIER-1 #2 (Happy-path): pick top-ranked view's primary button (heuristic: `Button` containing async/await call OR action calling a method named `generate*`/`create*`/`save*`/`run*`/`start*`)
- TIER-1 #3 (Error-recovery): pick first view (alphabetical by source-file name, then by line number) containing `.alert(...)`, `errorMessage`, `failure`, or `error: Error`. Tie-breaker is deterministic to ensure reproducibility across runs.
- TIER-2 (Modal): only if `.sheet(isPresented:` or `.fullScreenCover(isPresented:` found in walked tree
- TIER-2 (Menubar): only if `.commands { ... }` or `MenuBarExtra(` found
- TIER-3 (Multi-window): only if `WindowGroup`-count + `Window(`-count > 1
- TIER-3 (Toolbar): only if `ToolbarItem(` count ≥ 2

### Step 7: Generate identifier suggestions
For each control in top 5 views:
- **Skip controls that already have `.accessibilityIdentifier(...)` set** — detected by checking the next 5 lines after the control declaration for `.accessibilityIdentifier(`. Already-identified controls are listed in the report under "Already identified (preserved): N" but not re-suggested.
- **Skip controls inside `#Preview { ... }` blocks or `PreviewProvider` conformances** — these are not part of the runtime app. Detect by tracking brace-depth from `#Preview` or `static var previews` declarations.
- Construct ID as `<ViewName>_<ControlType>_<Purpose>`
- Purpose extracted from button label, action method name, or property name (in priority order)
- snake_case all parts; `_` separator
- Examples: `PlanCardView_Button_GeneratePlan`, `SettingsView_Toggle_EnableTelemetry`, `AIChatView_TextField_PromptInput`

### Step 8: Emit suggestions table for user confirmation
Present batch table:
```
| File:line | Current code | Suggested identifier |
|---|---|---|
| PlanCardView.swift:34 | Button("Generate") { ... } | PlanCardView_Button_GeneratePlan |
| ... | ... | ... |
```
Ask user: "Apply all N suggestions? [a]ll / [c]herry-pick / [s]kip"

If `[c]herry-pick`, follow up with one question per suggestion: "Apply suggestion k of N? [y/n]" — accumulate accepted set, apply only that subset in Step 9. If `[s]kip`, skip Step 9 entirely (test files still generated in Step 10 with placeholder identifier comments showing what to fill in manually).

### Step 9: Apply identifiers (if user confirmed)
Use Edit tool, one identifier per Edit call. On uniqueness conflict (same ID would land on two controls): skip both, flag for manual review in report.

### Step 10: Generate test files
Per TIER, write the test file with `.swift` content following template in §8.

### Step 11: Generate runner script
Write `scripts/run-uitests.sh` that runs `xcodebuild test -only-testing:<App>UITests` and pipes through xcresult parser. See §10 for content.

### Step 12: Generate identifier convention doc
Write `docs/accessibility-identifiers.md` with convention, examples, and rationale.

### Step 13: Emit final report
Per §8.

---

## 7. TIER Rubric

| Tier | Always-generate? | Heuristic trigger | Test file |
|---|---|---|---|
| 1 #1 Smoke | yes | always | `SmokeTest.swift` |
| 1 #2 Happy-path | yes | top-ranked view + primary action | `HappyPathTests.swift` |
| 1 #3 Error-recovery | yes | first `.alert`/error-state view | `ErrorRecoveryTests.swift` |
| 2 Modal | conditional | `.sheet(isPresented:` or `.fullScreenCover(isPresented:` present | `ModalAndMenuTests.swift` |
| 2 Menubar | conditional | `.commands { ... }` or `MenuBarExtra(` present | `ModalAndMenuTests.swift` |
| 3 Multi-window | conditional | Scene-count > 1 | `MultiWindowAndToolbarTests.swift` |
| 3 Toolbar | conditional | `ToolbarItem(`-count ≥ 2 | `MultiWindowAndToolbarTests.swift` |

**TIER-1 is non-negotiable** — even on a project where heuristics return weak matches, three test files appear. Smoke is meaningful (validates app launches). Happy-path and Error-recovery may need user-tuning but provide a starting structure.

**TIER-2 and TIER-3 conditional** — skipped silently if pattern not detected. Report says "TIER-2 sheet/modal: not generated (no `.sheet(isPresented:)` found)".

---

## 8. Output Format

After Phase 0 emission and identifier-application, the final report (single message at end of skill execution):

```markdown
## /macos-e2e-scaffold report — SwiftConfig

### Phase 0
✅ Swift project (xcodegen-managed)
✅ SwiftUI macOS app (4 Scenes detected)
✅ No existing UI test target

### Project context
- Scheme: SwiftConfig
- Source root: SwiftConfig/
- Top 5 views by control density: PlanCardView, AIChatView, SettingsView, MainContentView, PlanListView

### Identifier suggestions (12 total)
✅ Applied (10): PlanCardView_Button_GeneratePlan, AIChatView_TextField_PromptInput, ...
⏭️  Skipped on uniqueness conflict (2): SettingsView_Toggle_Enable (collides with PlanCardView_Toggle_Enable — review manually)

### Test stubs generated (5)
**TIER-1 (3 — must implement)**
- `SmokeTest.swift` :: testTIER1_AppLaunches
- `HappyPathTests.swift` :: testTIER1_GeneratePlan
- `ErrorRecoveryTests.swift` :: testTIER1_PlanGenerationError

**TIER-2 (2 — should implement if applicable)**
- `ModalAndMenuTests.swift` :: testTIER2_SettingsSheet
- `ModalAndMenuTests.swift` :: testTIER2_NewPlanCommand

**TIER-3 (0 — patterns not detected)**
- Multi-window: not generated (single WindowGroup)
- Toolbar: not generated (only 1 ToolbarItem)

### Runner script
- `scripts/run-uitests.sh` — `xcodebuild test -only-testing:SwiftConfigUITests`, parses xcresult to Claude-readable JSON

### Convention doc
- `docs/accessibility-identifiers.md` — `<ViewName>_<ControlType>_<Purpose>`, snake_case, examples

### Project-type integration
xcodegen detected → updated `xcodegen.yml` to add SwiftConfigUITests target. Run `xcodegen generate` before opening Xcode.

### Next steps
1. `xcodegen generate` (re-generate .xcodeproj with new test target)
2. `./scripts/run-uitests.sh` — all 5 TIER stubs will fail with `XCTFail("not implemented")`. That's expected — fill in assertions per stub.
3. Re-invoke /macos-e2e-scaffold if you add new top-level views or controls. Skill detects existing UI test target and refuses overwrite (extend manually).
```

---

## 9. SKILL.md Structure

The implementation plan task that writes `skills/macos-e2e-scaffold/SKILL.md` should follow this exact section order:

1. **Frontmatter** (`name`, `description`)
2. **Phase 0 self-check** — three refuse-conditions, exact messages
3. **What this skill does** — three-bullet summary
4. **What this skill is NOT** — boundaries (no iOS, no AppKit, no snapshot, no continuous mode)
5. **Heuristic process** — 13-step list (§6 above), exact patterns and grep targets
6. **TIER rubric** — table from §7
7. **Identifier convention** — `<ViewName>_<ControlType>_<Purpose>` with examples
8. **Output format** — sample report (§8)
9. **Project-type-specific behavior** — xcodegen, SPM, plain .xcodeproj branches
10. **Failure modes** — uniqueness conflicts, project-doesn't-build, partial scaffolding
11. **Relationship to other skills** — table (§11)
12. **Version marker** — `version: 1.10.0`

---

## 10. Project-Type-Specific Behavior

### xcodegen-managed
- Modify `xcodegen.yml` (or `project.yml`) to add new target:
  ```yaml
  targets:
    SwiftConfigUITests:
      type: bundle.ui-testing
      platform: macOS
      sources:
        - SwiftConfigUITests
      dependencies:
        - target: SwiftConfig
  ```
- Skill writes the diff, not the regenerated .xcodeproj. User runs `xcodegen generate`.
- Report says: "Run `xcodegen generate` before opening Xcode"

### SPM-based
- Note: SwiftPM does NOT support UI Test bundles natively (only `.testTarget` for unit tests). UI Tests require .xcodeproj.
- Skill detects this case and emits a special branch:
  - Generate test files in `Tests/<App>UITests/` directory
  - Print warning: "SPM doesn't support UI Test bundles. Generated files exist but require .xcodeproj. Recommend: switch to xcodegen-managed project, or add .xcodeproj manually with `xcodebuild -create-xcframework` workflow."
  - Refuse to attempt project-modification
- This is an *honest limitation*, not a skill failure. Document it explicitly.

### plain .xcodeproj (no xcodegen)
- Skill cannot reliably modify project.pbxproj programmatically (one wrong line corrupts the project).
- Generate files in `<App>UITests/` directory.
- Emit step-by-step manual instructions:
  ```
  1. Open <App>.xcodeproj in Xcode
  2. File > New > Target > macOS > UI Testing Bundle
  3. Name: <App>UITests
  4. Drag generated .swift files into target
  5. Set Host Application: <App>
  6. Build target once to verify
  ```
- Report says: "Generated files exist; manual Xcode steps required for target setup."

---

## 11. Runner Script (`scripts/run-uitests.sh`)

Generated content (template — substitute `<APP>` with detected scheme name):

```bash
#!/usr/bin/env bash
# Auto-generated by /macos-e2e-scaffold v1.10.0
# Runs UI tests and emits Claude-readable JSON summary.

set -e

SCHEME="<APP>"
RESULT_BUNDLE="$(mktemp -d)/uitests.xcresult"

xcodebuild test \
  -scheme "$SCHEME" \
  -destination 'platform=macOS' \
  -only-testing:"${SCHEME}UITests" \
  -resultBundlePath "$RESULT_BUNDLE" \
  -quiet 2>&1 | tail -50

# Parse xcresult to JSON summary
xcrun xcresulttool get test-results summary \
  --path "$RESULT_BUNDLE" \
  --format json \
  | jq '{total: .totalTestCount, passed: .passedTests, failed: .failedTests, results: [.testFailures[] | {test: .testIdentifier, file: .sourceCodeContext.location.filePath, line: .sourceCodeContext.location.lineNumber, message: .failureText}]}'
```

Output is JSON Claude can parse to identify failing tests and source-line references — significantly better than tail-grep on raw xcodebuild output.

---

## 12. Failure Modes

| Mode | Detection | Resolution |
|---|---|---|
| Project doesn't build | xcodebuild build fails before scaffold | Skill stops at Step 0 with build error. User fixes first. |
| Identifier uniqueness conflict | Same ID would apply to 2+ controls | Skip both, flag both in report for manual disambiguation |
| Existing UI test target with > 1 file | Phase 0 detects `<App>UITests/*.swift` count > 1 | Refuse with explanation; suggest manual extension |
| Phase 0 fails | Refuse-condition triggered | Return early, never modify files |
| User declines identifier-application | Batch prompt → user answers `[s]kip` | Skip Step 9; still generate test files (with placeholder identifiers user must fill in) |
| Cherry-pick rejected by user | Apply only confirmed subset | Apply confirmed; report skipped with reason |
| xcodegen not in PATH | `xcodegen` command not found | Emit instruction to install: `brew install xcodegen` |
| Empty SwiftUI app (Scene present but zero interactive controls in any walked view) | Step 4 view-graph yields zero `Button`/`Toggle`/`TextField`/`Picker` | Generate Smoke test only (TIER-1 #1). Skip TIER-1 #2/#3 with report-line "No interactive controls found — only Smoke test generated. Add controls and re-invoke." |
| Existing `.accessibilityIdentifier(...)` on control | Step 7 next-5-lines check | Preserve existing identifier; do not suggest replacement; list in report under "Already identified (preserved)" |
| Controls inside `#Preview { ... }` or `PreviewProvider` | Step 7 brace-depth tracking | Exclude from suggestion set; not counted in interactive-control density |
| xcresulttool API version mismatch | Runner script `xcrun xcresulttool` exits non-zero | Runner emits warning + falls back to plain `tail -50` of `xcodebuild test` output. Note in `scripts/run-uitests.sh` header that the JSON-format command requires Xcode 16+; older Xcode falls back to plaintext. |
| xcodegen.yml unknown structure | Skill cannot find `targets:` or `name:` keys | Skill switches to plain .xcodeproj branch (manual instructions); does NOT modify yml. Report flags ambiguity. |

**Skill never silently corrupts project files.** All modifications are confirmed; uniqueness conflicts skip rather than overwrite; .xcodeproj is never directly edited.

---

## 13. Relationship to Other Skills

| Skill | Layer | Asks |
|---|---|---|
| `pitfall-verification` | artifact | Will this work? |
| `quality-review` | artifact | Will this feel premium? |
| `macos-native-review` | artifact | Is this Apple-native? |
| **`macos-e2e-scaffold`** | **project** | **Is this E2E-tested?** |
| `swiftui-expert-skill` (Antoine) | code | Is the view code idiomatic SwiftUI? |
| `swift-testing-expert` (Antoine) | code | Is unit-test code idiomatic? |
| `swift-concurrency-expert` (Antoine) | code | Is async/await usage correct? |
| `core-data-expert` (Antoine) | code | Is the persistence layer well-designed? |

**Key distinction:** `macos-e2e-scaffold` is the only skill in the ecosystem that *creates* code rather than *reviews* it. This warrants the manual-only invocation pattern (no auto-trigger) — skill should run with full user awareness, not as a pipeline step.

**Cross-references in SKILL.md:** "What this skill is NOT" section should mention:
- Not Apple-native review (use `/macos-native-review`)
- Not view-code review (use `swiftui-expert-skill`)
- Not unit-test scaffolding (use `swift-testing-expert`)
- Not AppKit-aware (use `/appkit-e2e-scaffold` — deferred)
- Not iOS-aware (use `/ios-e2e-scaffold` — deferred)
- Not snapshot-aware (use `/swiftui-snapshot-scaffold` — deferred)

---

## 14. Versioning & Delivery Cadence

| Step | Action |
|---|---|
| 1 | Write spec (this document) ✅ |
| 2 | Self-check + pitfall-verification on spec |
| 3 | User reviews spec |
| 4 | `writing-plans` → implementation plan to `docs/superpowers/plans/2026-04-29-macos-e2e-scaffold-implementation.md` |
| 5 | Self-check + pitfall-verification on plan |
| 6 | `subagent-driven-development` executes plan task-by-task |
| 7 | PR `feat/macos-e2e-scaffold` → main |

### Plugin file changes (delivery scope)

| File | Change |
|---|---|
| `skills/macos-e2e-scaffold/SKILL.md` | NEW (~400 lines per §9 structure) |
| `.claude-plugin/plugin.json` | version 1.9.1 → 1.10.0 |
| `skills/setup-routing/SKILL.md` | version marker bump 1.9.1 → 1.10.0 |
| `skills/adapt/SKILL.md` | version marker bump 1.9.1 → 1.10.0 |
| `README.md` | "What's Included": 6 → 7 skills, add `/macos-e2e-scaffold` bullet |
| `CHANGELOG.md` | new `[1.10.0] - 2026-04-29` entry |
| `IDEAS.md` | Add 3 sibling stubs: `ios-e2e-scaffold`, `swiftui-snapshot-scaffold`, `appkit-e2e-scaffold` (Gap/Scope/Method/Differentiation/Status template); add `macos-e2e-scaffold` to "Shipped" section |
| PR | Title: `feat(v1.10.0): /macos-e2e-scaffold — XCUITest scaffolding skill for SwiftUI macOS apps` |

### Out-of-delivery
- No changes to user-level CLAUDE.md (user's call)
- No changes to setup-routing/adapt routing tables (those are upstream-only — plugin-internal skills are announced in README + CHANGELOG only, mirror `pitfall-verification`/`quality-review`/`macos-native-review` pattern)
- No sibling skill implementation (deferred via IDEAS.md stubs)
- No expansion of existing skills to cross-reference this one (already covered in §13 relationship table within new SKILL.md)

---

## 15. Sibling Skills (IDEAS.md stubs)

Three stubs to add in IDEAS.md, following the same Gap/Scope/Method/Differentiation/Status template as v1.9.0 sibling stubs:

### `/ios-e2e-scaffold` (proposed)
- **Gap:** XCUITest scaffolding for iOS SwiftUI apps; same shape as macos-e2e-scaffold but with iOS-specific heuristics (gestures, tab-bar, modals, device-rotation, safe-area).
- **Scope:** iOS-only. SwiftUI views. iOS Simulator destination. iOS-specific patterns (TabView, NavigationStack, sheet detents, gesture recognizers).
- **Method:** Mirrors macos-e2e-scaffold deterministic heuristic. Detects iOS target via `Package.swift` `.iOS(.v...)` or .xcodeproj scheme platform.
- **Differentiation:** Different heuristic targets (iOS top-flows differ from macOS), different runner-script destination, different identifier examples.
- **Status:** Deferred until observed need.

### `/swiftui-snapshot-scaffold` (proposed)
- **Gap:** Snapshot-test scaffolding via `swift-snapshot-testing` (Pointfree). Catches visual regressions XCUITest misses.
- **Scope:** Cross-platform (macOS + iOS). Adds `swift-snapshot-testing` Package.swift dependency. Generates baseline snapshots for top 5 views.
- **Method:** Detect `View`-conforming structs, render with `assertSnapshot(matching:as:)` skeletons. First run produces baselines; subsequent runs verify.
- **Differentiation:** Visual regression rather than interaction. Complementary to all e2e-scaffold skills, not a replacement.
- **Status:** Deferred until snapshot-testing demand surfaces.

### `/appkit-e2e-scaffold` (proposed)
- **Gap:** XCUITest scaffolding for AppKit-based macOS apps (legacy or Catalyst-bridged).
- **Scope:** AppKit-only views (`NSWindow`, `NSViewController`, NSAccessibility). Different identifier convention (NSAccessibility uses `accessibilityIdentifier()` method on `NSView`).
- **Method:** Grep for `NSWindow`, `NSViewController`, `NSButton`, `NSTextField`. Different scene-walk heuristic.
- **Differentiation:** AppKit-only. Won't work for SwiftUI. Useful for legacy apps.
- **Status:** Deferred until observed need (most modern macOS apps are SwiftUI-first).

---

## 16. Open Questions Resolved During Brainstorming

For audit purposes, recording decisions made interactively:

1. **Architecture:** B (audit + scaffold) chosen over A (scaffold-only) and C (full coverage-gate). C deferred to potential v2.
2. **Test tier:** XCUITest-only chosen over `XCUITest + snapshot` combined. Snapshot deferred to sibling.
3. **Platform:** macOS-only chosen over `macOS + iOS`. iOS deferred to sibling.
4. **Heuristic aggressivity:** Moderate (TIER-1/2/3, 5-7 stubs) chosen over Conservative (3 stubs) and Aggressive (exhaustive).
5. **Auto-applying identifiers:** YES with batch confirmation. User can [a]ll / [c]herry-pick / [s]kip.
6. **TIER-3 generation:** Conditional on pattern presence (not "always emit empty skeleton").
7. **Naming convention:** `/macos-e2e-scaffold` (platform-prefixed, mirror `macos-native-review`) over `/swiftui-e2e-scaffold` (framework-prefixed).

---

## 17. Acceptance Criteria

The implementation is complete when:

- [ ] `skills/macos-e2e-scaffold/SKILL.md` exists with all 12 sections per §9
- [ ] Plugin version is 1.10.0 across plugin.json, setup-routing/SKILL.md version marker, adapt/SKILL.md version marker
- [ ] README "What's Included" lists 7 skills including `/macos-e2e-scaffold`
- [ ] CHANGELOG has `[1.10.0] - 2026-04-29` entry matching v1.9.x voice
- [ ] IDEAS.md has 3 sibling stubs and `macos-e2e-scaffold` in "Shipped" section
- [ ] Smoke-test mental walkthrough: a synthetic SwiftUI macOS spec (3 Scenes, 12 controls, 1 sheet, 1 menubar) produces expected output (Phase 0 ✅, 12 identifiers, 5 stubs across TIER-1 + TIER-2)
- [ ] Cross-file consistency check passes (version numbers match across plugin.json + setup-routing + adapt + CHANGELOG + README)
- [ ] PR `feat/macos-e2e-scaffold` opened against main with title `feat(v1.10.0): /macos-e2e-scaffold — XCUITest scaffolding skill for SwiftUI macOS apps`

---

## 18. Notes for Implementation Plan

The plan written from this spec must be self-contained — subagents executing tasks should not need to re-read this spec mid-execution. That means:

- **SKILL.md content task** must include the full SKILL.md draft inline, not "write a SKILL.md following spec §9 structure"
- **Heuristic patterns task** must include exact grep regexes and pattern-match strings
- **Output template task** must include the exact sample report from §8
- **Project-type-branches task** must include all three branches (xcodegen, SPM, plain .xcodeproj) with concrete YAML/instructions
- **Runner script task** must include the exact bash content from §11
- **IDEAS.md task** must include the three sibling stub bodies inline

Same self-containment discipline as the v1.9.0 macos-native-review plan.

**Pitfall-verification ran on this spec** during brainstorming. Pitfalls verified:
- Identifier collision risk in Step 7 — mitigated by skip-and-flag in Step 9 ✅
- xcodegen-not-installed edge case — handled in §10 + §12 ✅
- SPM-doesn't-support-UI-Tests honest limitation — documented in §10 ✅
- No silent project.pbxproj edits — documented in §10 + §12 ✅
- Phase 0 refuse-conditions unambiguous — verified by §4 message-text ✅
- TIER-3 conditional skip is silent, not noisy — verified by §8 sample ✅
- Heuristic non-determinism — fixed via tie-breakers (alphabetical+line) in §6 Step 5/6 ✅
- Empty SwiftUI app edge case — Smoke-only fallback in §12 ✅
- Existing `.accessibilityIdentifier(...)` on controls — preservation rule in §6 Step 7 + §12 ✅
- SwiftUI Previews exclusion — brace-depth tracking in §6 Step 7 + §12 ✅
- xcresulttool API version compat — Xcode 16+ JSON format with plaintext fallback documented in §11 + §12 ✅
- xcodegen.yml schema variation — graceful degradation to .xcodeproj branch in §12 ✅
