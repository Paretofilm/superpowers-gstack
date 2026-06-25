---
name: ios-e2e-scaffold
description: One-shot XCUITest scaffolding for iOS SwiftUI apps. Audits the Scene tree, generates ranked TIER-1/2/3 test stubs, suggests accessibility identifiers with batch confirmation, and emits a Claude-readable xcresult runner script targeting the iOS Simulator. Manual invocation only — modifies project files.
version: 1.0.0
---

# ios-e2e-scaffold

Manual-invocation skill that bootstraps XCUITest infrastructure for iOS SwiftUI projects.
Mirrors `macos-e2e-scaffold`'s deterministic Read+Grep heuristic; differs only where iOS differs.

## Phase 0 — Self-check

Before any other action, run three refuse-conditions. Any failure → return early with explicit message; no files modified.

| Check | Detect via | Refuse-message |
|---|---|---|
| Swift project | `*.xcodeproj` directory or `Package.swift` in cwd | "Not a Swift project. /ios-e2e-scaffold requires .xcodeproj or Package.swift in project root." |
| iOS SwiftUI app | **iOS-discriminating signal** (see below) AND SwiftUI scene (`@main` + `App`/`WindowGroup`/`TabView`/`NavigationStack`) | "No iOS SwiftUI app target detected. Skill is iOS-only — for macOS use /macos-e2e-scaffold, for AppKit use /appkit-e2e-scaffold (deferred)." |
| Not already scaffolded | `<App>UITests/` exists with `find ... -name '*.swift' \| wc -l` > 1 | "UI test target already exists with N test files. Skill won't overwrite — extend manually instead." |

### iOS-discriminating signal — REQUIRED

`WindowGroup` is **cross-platform** (shared with macOS) and does NOT identify iOS on its own. Detect iOS via the FIRST that matches:

1. **SPM:** `Package.swift` contains `.iOS(` in a `platforms:` clause (and the target is an app, not a library).
2. **xcodegen:** `project.yml`/`xcodegen.yml` target has `platform: iOS`.
3. **plain `.xcodeproj`:** `project.pbxproj` contains `SDKROOT = iphoneos` or `SUPPORTED_PLATFORMS = "?iphoneos` for the app target's build config.
4. **Corroborating (necessary-not-sufficient):** `grep -rl 'import UIKit' --include='*.swift'` present AND macOS-only scenes absent (`MenuBarExtra(`, `Settings {`, `Window(`).

**Multiplatform targets** (`.iOS(` AND `.macOS(` in `Package.swift`, or `SUPPORTED_PLATFORMS` lists both `iphoneos` and `macosx`): Phase 0 **passes** (iOS is among the platforms) and emits a note — "Multiplatform target detected; scaffolding iOS-Simulator tests. Run /macos-e2e-scaffold separately for the macOS surface." Treat `iphoneos`/`.iOS(` presence as sufficient; do not refuse just because macOS is also supported.

Always emit Phase 0 result on success:

```
## /ios-e2e-scaffold Phase 0
✅ Swift project detected (<project>.xcodeproj | Package.swift)
✅ iOS SwiftUI app (iOS signal: <SDKROOT=iphoneos | .iOS( | platform: iOS>; scene <Type> in <File.swift>:<line>)
✅ No existing UI test target

Project type: <xcodegen-managed | SPM-based | plain .xcodeproj>
Scheme: <SchemeName>
Source root: <path>
Total .swift files in source root: <N>
[Multiplatform note, if applicable]

Proceeding with audit + scaffold.
```

## What this skill does

1. **Audits** the project: walks the SwiftUI Scene tree, ranks views by interactive-control density, identifies top 5.
2. **Suggests** accessibility identifiers for each control in top 5 views; applies them after user batch-confirmation.
3. **Generates** ranked TIER-1/2/3 test stubs with `XCTFail("not implemented")` placeholders, an identifier-convention doc, and a Claude-readable xcresult runner script targeting the iOS Simulator.

## What this skill is NOT

- **Not a review skill.** Does not analyse spec/plan/PRD artefacts. Use `/pitfall-verification` (will-it-work?), `/quality-review` (will-it-feel-premium?), or `/ios-native-review` (is-it-iOS-native?) for those.
- **Not a code-quality reviewer.** Does not check view-code idioms (use Antoine van der Lee's `swiftui-expert-skill`) or unit-test idioms (use `swift-testing-expert`).
- **Not macOS-aware.** Use `/macos-e2e-scaffold`.
- **Not AppKit/UIKit-aware.** SwiftUI only. For AppKit use `/appkit-e2e-scaffold` (deferred).
- **Not snapshot-aware.** Use `/swiftui-snapshot-scaffold` (deferred).
- **Not auto-invoked.** Manual `/ios-e2e-scaffold` only — same model as `setup-routing`. Normally reached via `/e2e-route`.

## Heuristic process (deterministic, Read+Grep based)

### Step 1: Detect project type
1. If `xcodegen.yml` or `project.yml` exists → **xcodegen-managed**
2. Else if `Package.swift` contains `.executableTarget(name:` → **SPM-based**
3. Else if `*.xcodeproj` exists → **plain .xcodeproj**

### Step 2: Detect scheme name
- xcodegen: read `name:` field at root of `xcodegen.yml`/`project.yml`
- SPM: read `name:` from `Package(name: ...)`
- plain .xcodeproj: parse `*.xcodeproj/xcshareddata/xcschemes/*.xcscheme` filenames; fallback to project directory name

### Step 3: Find source root
- xcodegen: read `targets.<schemename>.sources.path` from yml
- SPM: `Sources/<TargetName>/`
- plain .xcodeproj: parse `project.pbxproj` for main app target's source group `path = `; fallback to `<schemename>/`

### Step 4: Walk Scene tree
1. Grep source root for iOS root patterns:
   ```
   grep -rn -E 'WindowGroup|TabView\s*[({]|NavigationStack|NavigationSplitView' --include='*.swift'
   ```
2. For each Scene file, grep its body for iOS destination patterns: `NavigationLink(destination:`, `NavigationLink(`, `.navigationDestination(`, `.sheet(isPresented:`, `.sheet(item:`, `.fullScreenCover(isPresented:`, `.fullScreenCover(item:`, `.popover(`
3. Recursively follow destinations to build view-graph (max depth: 5; cycle detection via view-name set)
4. For each view in graph, count interactive controls using word-boundary patterns:
   - `\bButton\b\s*[({]`
   - `\bToggle\b\s*\(`
   - `\bTextField\b\s*\(`
   - `\bPicker\b\s*\(`
   - `\bNavigationLink\b\s*\(`
   - `\bStepper\b\s*\(`
   - `\bSlider\b\s*\(`
   - `\bDatePicker\b\s*\(`
   - `\bMenu\b\s*[({]`

### Step 5: Rank views
Sort views by `(reference_count + interactive_control_count)` descending. Tie-breaker: alphabetical by source-file name, then by line number. Top 5 receive identifier suggestions.

### Step 6: Detect TIER mappings
- TIER-1 #1 (Smoke): always (app launches, root scene appears).
- TIER-1 #2 (Happy-path): pick top-ranked view's primary button. Heuristic: `Button` containing `await` OR action calling a method named `generate*`/`create*`/`save*`/`run*`/`start*`. **Fallback** if no Button matches: pick the first Button in the top-ranked view (by line number); mark the generated stub with comment `// HEURISTIC: generic fallback — no save/create/await action matched. Verify this is the right primary action.`
- TIER-1 #3 (Error-recovery): pick first view (alphabetical by source-file name, then by line number — deterministic) containing `.alert(`, `errorMessage`, `failure`, or `error: Error`
- TIER-2 (Modal): only if `.sheet(isPresented:`, `.sheet(item:`, `.fullScreenCover(`, or `.popover(` found in walked tree → `ModalAndSheetTests.swift`
- TIER-2 (Tab-navigation): only if `TabView` found → `TabNavigationTests.swift` (assert tab switch changes selected content)
- TIER-3 (Push-navigation): only if `NavigationStack` present AND (`NavigationLink(`-count ≥ 2 OR `.navigationDestination(` present) → `PushNavigationTests.swift` (list → detail push/pop)
- TIER-3 (Gestures/rotation): only if `.swipeActions(`, `.refreshable`, or orientation usage (`.onRotate`, `UIDevice.*orientation`, `@Environment(\.verticalSizeClass)`) found → `GestureAndRotationTests.swift`

### Step 7: Generate identifier suggestions
For each control in top 5 views:
- **Skip controls that already have `.accessibilityIdentifier(...)` set** — check next 5 lines after the control declaration. Already-identified controls listed in report under "Already identified (preserved)" but not re-suggested.
- **Skip controls inside `#Preview { ... }` blocks or `PreviewProvider` (`static var previews:`) conformances** — track brace-depth from `#Preview` or `static var previews` declarations; exclude when depth > 0.
- Construct ID as `<ViewName>_<ControlType>_<Purpose>`
- Purpose extracted from button label, action method name, or property name (in priority order)
- snake_case all parts; `_` separator
- Examples: `PlanListView_Button_GeneratePlan`, `SettingsView_Toggle_EnableTelemetry`, `ChatView_TextField_PromptInput`

### Step 8: Emit suggestions table for user confirmation
Present batch table in markdown:
```
| File:line | Current code | Suggested identifier |
|---|---|---|
| PlanListView.swift:34 | Button("Generate") { ... } | PlanListView_Button_GeneratePlan |
| ... | ... | ... |
```
Ask: "Apply all N suggestions? [a]ll / [c]herry-pick / [s]kip"

If `[c]herry-pick`: follow up with one question per suggestion: "Apply suggestion k of N? [y/n]". Accumulate accepted set; apply only that subset in Step 9.

If `[s]kip`: skip Step 9 entirely; test files in Step 10 still generated, with placeholder identifier comments showing what user must fill in manually.

### Step 9: Apply identifiers
Use Edit tool, one identifier per Edit call. On uniqueness conflict (same ID would land on two distinct controls): skip both; flag for manual review in report.

### Step 10: Generate test files
Per TIER, write one `.swift` file with `XCTFail("not implemented — fyll inn assertion")` placeholder + TODO-comment pointing to source-file:line + suggested assertions in comments.

File naming:
- `<App>UITests/SmokeTest.swift` (TIER-1 #1)
- `<App>UITests/HappyPathTests.swift` (TIER-1 #2)
- `<App>UITests/ErrorRecoveryTests.swift` (TIER-1 #3)
- `<App>UITests/ModalAndSheetTests.swift` (TIER-2 modal, if any)
- `<App>UITests/TabNavigationTests.swift` (TIER-2 tab, if any)
- `<App>UITests/PushNavigationTests.swift` (TIER-3 push, if any)
- `<App>UITests/GestureAndRotationTests.swift` (TIER-3 gesture/rotation, if any)

### Step 11: Generate runner script
Write `scripts/run-uitests.sh` per template in §Runner-script-template (substitute `<APP>` with detected scheme name). Make executable: `chmod +x scripts/run-uitests.sh`.

### Step 12: Generate identifier convention doc
Write `docs/accessibility-identifiers.md` with the convention, examples, rationale, and a table listing all applied identifiers with their source-file:line.

### Step 13: Emit final report
Per Output-format section below.

## TIER rubric

| Tier | Always-generate? | Heuristic trigger | Test file |
|---|---|---|---|
| 1 #1 Smoke | yes | always | `SmokeTest.swift` |
| 1 #2 Happy-path | yes | top-ranked view + primary action | `HappyPathTests.swift` |
| 1 #3 Error-recovery | yes | first `.alert`/error-state view (alphabetical+line tiebreak) | `ErrorRecoveryTests.swift` |
| 2 Modal | conditional | `.sheet(isPresented:`/`.sheet(item:`/`.fullScreenCover(`/`.popover(` present | `ModalAndSheetTests.swift` |
| 2 Tab-navigation | conditional | `TabView` present | `TabNavigationTests.swift` |
| 3 Push-navigation | conditional | `NavigationStack` + (`NavigationLink(`-count ≥ 2 or `.navigationDestination(`) | `PushNavigationTests.swift` |
| 3 Gestures/rotation | conditional | `.swipeActions(`/`.refreshable`/orientation usage present | `GestureAndRotationTests.swift` |

**TIER-1 is non-negotiable.** Even on a project where heuristics return weak matches, three test files appear. Smoke validates app launches. Happy-path and Error-recovery may need user-tuning but provide a starting structure.

**TIER-2 and TIER-3 conditional.** Skipped silently if pattern not detected. Report says e.g. "TIER-2 tab-navigation: not generated (no `TabView` found)".

## Identifier convention

Format: `<ViewName>_<ControlType>_<Purpose>`

- snake_case all parts
- `_` separator (consistent grep-by-view: `PlanListView_` matches all PlanListView-controls)
- Stable across label-text changes (refactor-safe)

Examples:
- `PlanListView_Button_GeneratePlan`
- `SettingsView_Toggle_EnableTelemetry`
- `ChatView_TextField_PromptInput`
- `DetailView_NavigationLink_OpenSettings`

Identical to the `macos-e2e-scaffold` convention, so `/e2e-route` can point at one consistent convention for both platforms.

Convention doc: `docs/accessibility-identifiers.md` (auto-generated by skill, includes table of all applied identifiers + rationale).

## Output format

After Phase 0 emission and identifier-application, the final report (single message at end of skill execution):

```markdown
## /ios-e2e-scaffold report — <ProjectName>

### Phase 0
✅ Swift project (<project-type>)
✅ iOS SwiftUI app (<N> Scenes detected, iOS signal: <signal>)
✅ No existing UI test target

### Project context
- Scheme: <SchemeName>
- Source root: <path>
- Top 5 views by control density: <View1>, <View2>, <View3>, <View4>, <View5>

### Identifier suggestions (<N> total)
✅ Applied (<N>): <Id1>, <Id2>, ...
⏭️  Skipped on uniqueness conflict (<M>): <Id-X> (collides with <Id-Y> — review manually)
ℹ️  Already identified (preserved <K>): <Id-existing-1>, ...
🚫 Excluded from Preview blocks (<L>)

### Test stubs generated (<S>)
**TIER-1 (3 — must implement)**
- `SmokeTest.swift` :: testTIER1_AppLaunches
- `HappyPathTests.swift` :: testTIER1_<HappyPathName>
- `ErrorRecoveryTests.swift` :: testTIER1_<ErrorPathName>

**TIER-2 (<n> — should implement if applicable)**
- `ModalAndSheetTests.swift` :: testTIER2_<...> (if `.sheet`/`.fullScreenCover`/`.popover` detected)
- `TabNavigationTests.swift` :: testTIER2_<...> (if `TabView` detected)

**TIER-3 (<n> — patterns not detected | generated)**
- Push-navigation: <generated | not generated (no NavigationStack / <2 NavigationLink)>
- Gestures/rotation: <generated | not generated (no swipe/refresh/orientation usage)>

### Runner script
- `scripts/run-uitests.sh` — `xcodebuild test -only-testing:<App>UITests` against `platform=iOS Simulator`, parses xcresult to Claude-readable JSON (Xcode 16+ format; falls back to plaintext on older Xcode)

### Convention doc
- `docs/accessibility-identifiers.md` — `<ViewName>_<ControlType>_<Purpose>`, snake_case, examples, full identifier table

### Project-type integration
<branch-specific instructions per Project-type-specific-behavior section>

### Next steps
1. <project-type-specific build step>
2. `./scripts/run-uitests.sh` — all <S> TIER stubs will fail with `XCTFail("not implemented")`. That's expected — fill in assertions per stub.
3. Re-invoke /ios-e2e-scaffold if you add new top-level views or controls. Skill detects existing UI test target and refuses overwrite (extend manually).
```

## Project-type-specific behavior

### xcodegen-managed
Modify `xcodegen.yml` (or `project.yml`) to add new target:

```yaml
targets:
  <App>UITests:
    type: bundle.ui-testing
    platform: iOS
    sources:
      - <App>UITests
    dependencies:
      - target: <App>
```

Skill writes the diff. User runs `xcodegen generate` to regenerate `.xcodeproj`. Report says: "Run `xcodegen generate` before opening Xcode."

### SPM-based
SwiftPM does NOT support UI Test bundles natively (only `.testTarget` for unit tests). UI Tests require `.xcodeproj`.

Skill detects this case:
- Generate test files in `Tests/<App>UITests/` directory
- Print warning: "SPM doesn't support UI Test bundles. Generated files exist but require .xcodeproj. Recommend: switch to xcodegen-managed project, or add .xcodeproj manually."
- Refuse to attempt project-modification

This is an honest limitation, not a skill failure. (Note: SPM-only is still a valid input — the skill proceeds and generates files; it does not refuse in Phase 0.)

### plain .xcodeproj (no xcodegen)
Skill cannot reliably modify `project.pbxproj` programmatically (one wrong line corrupts the project).

- Generate files in `<App>UITests/` directory
- Emit step-by-step manual instructions:
  ```
  1. Open <App>.xcodeproj in Xcode
  2. File > New > Target > iOS > UI Testing Bundle
  3. Name: <App>UITests
  4. Drag generated .swift files into target
  5. Set Target to be Tested: <App>
  6. Build target once to verify
  ```
- Report says: "Generated files exist; manual Xcode steps required for target setup."

## Failure modes

| Mode | Detection | Resolution |
|---|---|---|
| Project doesn't build | `xcodebuild build` fails before scaffold | Skill stops; user fixes build first |
| Identifier uniqueness conflict | Same ID for 2+ controls | Skip both; flag for manual review |
| Existing UI test target | Phase 0 detects `<App>UITests/*.swift` count > 1 | Refuse; suggest manual extension |
| Phase 0 fails | Refuse-condition triggered | Return early; never modify files |
| Platform ambiguous (WindowGroup only) | No iOS-discriminating signal found | Refuse "No iOS SwiftUI app target detected" — do NOT assume iOS from WindowGroup |
| Multiplatform target | `.iOS(` AND `.macOS(`, or both platforms in SUPPORTED_PLATFORMS | Pass; scaffold iOS tests; note macOS surface needs /macos-e2e-scaffold |
| User declines identifier-application | `[s]kip` answer | Skip Step 9; generate test files with placeholder comments |
| Cherry-pick rejected per-suggestion | User says `[n]` | Apply only confirmed subset |
| xcodegen not in PATH | `xcodegen` not found | Emit instruction: `brew install xcodegen` |
| Named simulator missing | `iPhone 15` not in `simctl list` | Runner falls back to first available iOS Simulator (see runner template) |
| Empty SwiftUI app | Step 4 yields zero interactive controls | Generate Smoke test only; report "No interactive controls found — only Smoke test generated. Add controls and re-invoke." |
| Existing `.accessibilityIdentifier(...)` | Step 7 next-5-lines check | Preserve; report under "Already identified (preserved)" |
| Controls in `#Preview { ... }` / `PreviewProvider` | Step 7 brace-depth tracking | Exclude from suggestions and density count |
| xcresulttool API mismatch | `xcrun xcresulttool` exits non-zero | Runner falls back to `tail -50` of plaintext xcodebuild output; header notes Xcode 16+ requirement |
| xcodegen.yml unknown structure | Cannot find `targets:`/`name:` keys | Switch to plain .xcodeproj branch; do NOT modify yml; flag ambiguity in report |

**Skill never silently corrupts project files.** All modifications confirmed; uniqueness conflicts skip; .xcodeproj is never directly edited.

## Relationship to other skills

| Skill | Layer | Asks |
|---|---|---|
| `e2e-route` | routing | Which executor for this test? |
| `pitfall-verification` | artifact | Will this work? |
| `quality-review` | artifact | Will this feel premium? |
| `ios-native-review` | artifact | Is this iOS-native? |
| **`ios-e2e-scaffold`** | **project** | **Is this E2E-tested?** |
| `macos-e2e-scaffold` | project | (macOS counterpart) |
| `swiftui-expert-skill` (Antoine) | code | Is the view code idiomatic? |
| `swift-testing-expert` (Antoine) | code | Is unit-test code idiomatic? |

`ios-e2e-scaffold` *creates* test infrastructure rather than *reviewing* artefacts. This warrants the manual-only invocation pattern (no auto-trigger) — skill should run with full user awareness, not as a pipeline step. It is normally reached via `/e2e-route`.

## Runner script template

`scripts/run-uitests.sh`:

```bash
#!/usr/bin/env bash
# Auto-generated by /ios-e2e-scaffold v1.0.0
# Runs iOS UI tests and emits Claude-readable JSON summary.
# Requires Xcode 16+ for JSON xcresulttool format; falls back to plaintext on older.

set -e

SCHEME="<APP>"
RESULT_BUNDLE="$(mktemp -d)/uitests.xcresult"

# Pick a simulator: prefer iPhone 15; else first available iOS Simulator.
DEST='platform=iOS Simulator,name=iPhone 15'
if ! xcrun simctl list devices available | grep -q 'iPhone 15'; then
  FALLBACK="$(xcrun simctl list devices available | grep -oE 'iPhone [0-9][^(]*' | head -1 | sed 's/ *$//')"
  if [ -n "$FALLBACK" ]; then
    DEST="platform=iOS Simulator,name=${FALLBACK}"
    echo "(iPhone 15 unavailable — using ${FALLBACK})"
  fi
fi

xcodebuild test \
  -scheme "$SCHEME" \
  -destination "$DEST" \
  -only-testing:"${SCHEME}UITests" \
  -resultBundlePath "$RESULT_BUNDLE" \
  -quiet 2>&1 | tail -50

# Parse xcresult to JSON summary (Xcode 16+)
if xcrun xcresulttool get test-results summary --path "$RESULT_BUNDLE" --format json 2>/dev/null \
   | jq '{total: .totalTestCount, passed: .passedTests, failed: .failedTests, results: [.testFailures[] | {test: .testIdentifier, file: .sourceCodeContext.location.filePath, line: .sourceCodeContext.location.lineNumber, message: .failureText}]}' 2>/dev/null; then
  exit 0
fi

# Fallback for older Xcode: plain xcresulttool dump
echo "(Xcode 16+ JSON format unavailable — falling back to plaintext)"
xcrun xcresulttool get --path "$RESULT_BUNDLE" 2>/dev/null | tail -100 || true
```
