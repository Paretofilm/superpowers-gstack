---
name: macos-e2e-scaffold
description: |
  One-shot XCUITest scaffolding for macOS SwiftUI apps: audits the project,
  generates ranked TIER-1/2/3 stubs, suggests accessibility identifiers, emits an
  xcresult runner. Manual only — modifies project files.
---

# macos-e2e-scaffold

Manual-invocation skill that bootstraps XCUITest infrastructure for macOS SwiftUI projects.

## Phase 0 — Self-check

Before any other action, run three refuse-conditions. Any failure → return early with explicit message; no files modified.

| Check | Detect via | Refuse-message |
|---|---|---|
| Swift project | `*.xcodeproj` directory or `Package.swift` in cwd | "Not a Swift project. /macos-e2e-scaffold requires .xcodeproj or Package.swift in project root." |
| SwiftUI macOS app | **macOS-discriminating signal** (see below) AND SwiftUI scene (grep `WindowGroup\|Window(\|Settings {\|MenuBarExtra(` in `*.swift` under source root) | "No SwiftUI macOS app target detected. Skill is macOS-only — for iOS use /ios-e2e-scaffold, for AppKit use /appkit-e2e-scaffold (deferred)." |
| Not already scaffolded | **any** directory matching `*UITests/` at cwd — EXCLUDING the iOS sibling's `*iOSUITests/` (which must not block macOS scaffolding on multiplatform projects) — contains > 1 `*.swift` (`find . -maxdepth 2 -type d -name '*UITests' ! -name '*iOSUITests'` then count) — do NOT assume the `<App>`-prefixed name, since the scheme is not detected until Step 2 | "UI test target already exists (`<found-dir>/`, N test files). Skill won't overwrite — extend manually instead." |

### macOS-discriminating signal — REQUIRED

`WindowGroup` is **cross-platform** (shared with iOS) and does NOT identify macOS on its own. Detect macOS via the FIRST that matches:

1. **SPM:** `Package.swift` contains `.macOS(` in a `platforms:` clause (and the target is an app, not a library).
2. **xcodegen:** `project.yml`/`xcodegen.yml` target has `platform: macOS`.
3. **plain `.xcodeproj`:** `project.pbxproj` contains `SDKROOT = macosx` or `SUPPORTED_PLATFORMS` includes `macosx` for the app target's build config.
4. **Corroborating (necessary-not-sufficient):** a macOS-only scene type present (`MenuBarExtra(`, `Settings {`, `Window(`) AND iOS-only signals absent (`SDKROOT = iphoneos`, `platform: iOS`, `import UIKit`, `.fullScreenCover(`).

A project with ONLY iOS signals must be refused with the row's refuse-message pointing to `/ios-e2e-scaffold` — do NOT scaffold macOS tests from a bare `WindowGroup`.

**Multiplatform targets** (`.iOS(` AND `.macOS(` in `Package.swift`, or `SUPPORTED_PLATFORMS` lists both `iphoneos` and `macosx`): Phase 0 **passes** (macOS is among the platforms) and emits a note — "Multiplatform target detected; scaffolding macOS tests. Run /ios-e2e-scaffold separately for the iOS surface." Treat `macosx`/`.macOS(` presence as sufficient; do not refuse just because iOS is also supported.

### TARGET_DIR convention

Set once in Phase 0 and used everywhere below (Step 10 file naming, the xcodegen/Xcode UI-test target name, and the runner's `-only-testing:` argument):

- Single-platform macOS target → `TARGET_DIR = <App>UITests`
- Multiplatform target → `TARGET_DIR = <App>macOSUITests` — so the macOS and iOS UI-test targets coexist. `/ios-e2e-scaffold` uses `<App>iOSUITests` in the same situation, and each scaffold's "already scaffolded" glob ignores the sibling's suffixed directory; without the suffix the two would collide on the same directory and the same `xcodegen.yml`/`project.pbxproj` UI-test target.

Always emit Phase 0 result on success:

```
## /macos-e2e-scaffold Phase 0
✅ Swift project detected (<project>.xcodeproj | Package.swift)
✅ SwiftUI macOS app (macOS signal: <SDKROOT=macosx | .macOS( | platform: macOS | macOS-only scene>; scene <Type> in <File.swift>:<line>)
✅ No existing UI test target

Project type: <xcodegen-managed | SPM-based | plain .xcodeproj>
Scheme: <SchemeName>
Source root: <path>
Total .swift files in source root: <N>
[Multiplatform note, if applicable — TARGET_DIR = <App>macOSUITests]

Proceeding with audit + scaffold.
```

## What this skill does

1. **Audits** the project: walks the SwiftUI Scene tree, ranks views by interactive-control density, identifies top 5.
2. **Suggests** accessibility identifiers for each control in top 5 views; applies them after user batch-confirmation.
3. **Generates** ranked TIER-1/2/3 test stubs with `XCTFail("not implemented")` placeholders, an identifier-convention doc, and a Claude-readable xcresult runner script.

## What this skill is NOT

- **Not a review skill.** Does not analyse spec/plan/PRD artefacts. Use `/pitfall-verification` (will-it-work?), `/quality-review` (will-it-feel-premium?), or `/macos-native-review` (is-it-Apple-native?) for those.
- **Not a code-quality reviewer.** Does not check view-code idioms (use Antoine van der Lee's `swiftui-expert-skill`) or unit-test idioms (use `swift-testing-expert`).
- **Not iOS-aware.** Use `/ios-e2e-scaffold`.
- **Not AppKit-aware.** Use `/appkit-e2e-scaffold` (deferred).
- **Not snapshot-aware.** Use `/swiftui-snapshot-scaffold` (deferred).
- **Not auto-invoked.** Manual `/macos-e2e-scaffold` only — same model as `setup-routing`. Normally reached via `/e2e-route`.

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
1. Grep source root: `grep -rn -E 'WindowGroup|Window\(|Settings \{|MenuBarExtra\(' --include='*.swift'`
2. For each Scene file, grep its body for `NavigationLink(destination:`, `.sheet(content:`, `.fullScreenCover(content:`
3. Recursively follow destinations to build view-graph (max depth: 5; cycle detection via view-name set)
4. For each view in graph, count interactive controls using word-boundary patterns:
   - `\bButton\b\s*[({]`
   - `\bToggle\b\s*\(`
   - `\bTextField\b\s*\(`
   - `\bPicker\b\s*\(`
   - `\bNavigationLink\b\s*\(`

### Step 5: Rank views
Sort views by `(reference_count + interactive_control_count)` descending. Tie-breaker: alphabetical by source-file name, then by line number. Top 5 receive identifier suggestions.

### Step 6: Detect TIER mappings
- TIER-1 #1 (Smoke): always (uses Scene-root window-title)
- TIER-1 #2 (Happy-path): pick top-ranked view's primary button. Heuristic: `Button` containing `await` OR action calling a method named `generate*`/`create*`/`save*`/`run*`/`start*`. **Fallback** if no Button matches: pick the first Button in the top-ranked view (by line number); mark the generated stub with comment `// HEURISTIC: generic fallback — no save/create/await action matched. Verify this is the right primary action.` so user knows to double-check.
- TIER-1 #3 (Error-recovery): pick first view (alphabetical by source-file name, then by line number — deterministic) containing `.alert(...)`, `errorMessage`, `failure`, or `error: Error`
- TIER-2 (Modal): only if `.sheet(isPresented:` or `.fullScreenCover(isPresented:` found in walked tree
- TIER-2 (Menubar): only if `.commands { ... }` or `MenuBarExtra(` found
- TIER-3 (Multi-window): only if `WindowGroup`-count + `Window(`-count > 1
- TIER-3 (Toolbar): only if `ToolbarItem(` count ≥ 2

### Step 7: Generate identifier suggestions
For each control in top 5 views:
- **Skip controls that already have `.accessibilityIdentifier(...)` set** — check next 5 lines after the control declaration. Already-identified controls listed in report under "Already identified (preserved)" but not re-suggested.
- **Skip controls inside `#Preview { ... }` blocks or `PreviewProvider` (`static var previews:`) conformances** — track brace-depth from `#Preview` or `static var previews` declarations; exclude when depth > 0.
- Construct ID as `<ViewName>_<ControlType>_<Purpose>`
- Purpose extracted from button label, action method name, or property name (in priority order)
- snake_case all parts; `_` separator
- Examples: `PlanCardView_Button_GeneratePlan`, `SettingsView_Toggle_EnableTelemetry`, `AIChatView_TextField_PromptInput`

### Step 8: Emit suggestions table for user confirmation
Present batch table in markdown:
```
| File:line | Current code | Suggested identifier |
|---|---|---|
| PlanCardView.swift:34 | Button("Generate") { ... } | PlanCardView_Button_GeneratePlan |
| ... | ... | ... |
```
Ask: "Apply all N suggestions? [a]ll / [c]herry-pick / [s]kip"

If `[c]herry-pick`: follow up with one question per suggestion: "Apply suggestion k of N? [y/n]". Accumulate accepted set; apply only that subset in Step 9.

If `[s]kip`: skip Step 9 entirely; test files in Step 10 still generated, with placeholder identifier comments showing what user must fill in manually.

### Step 9: Apply identifiers
Use Edit tool, one identifier per Edit call. On uniqueness conflict (same ID would land on two distinct controls): skip both; flag for manual review in report.

### Step 10: Generate test files
Per TIER, write one `.swift` file with `XCTFail("not implemented — fyll inn assertion")` placeholder + TODO-comment pointing to source-file:line + suggested assertions in comments.

File naming (all paths use the Phase 0 `TARGET_DIR` — `<App>UITests` single-platform, `<App>macOSUITests` multiplatform):
- `<TARGET_DIR>/SmokeTest.swift` (TIER-1 #1)
- `<TARGET_DIR>/HappyPathTests.swift` (TIER-1 #2)
- `<TARGET_DIR>/ErrorRecoveryTests.swift` (TIER-1 #3)
- `<TARGET_DIR>/ModalAndMenuTests.swift` (TIER-2 if any)
- `<TARGET_DIR>/MultiWindowAndToolbarTests.swift` (TIER-3 if any)

### Step 11: Generate runner script
Write `scripts/run-uitests.sh` per template in §Runner-script-template (substitute `<APP>` with detected scheme name and `<TARGET_DIR>` with the Phase 0 TARGET_DIR). Make executable: `chmod +x scripts/run-uitests.sh`.

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
| 2 Modal | conditional | `.sheet(isPresented:` or `.fullScreenCover(isPresented:` present | `ModalAndMenuTests.swift` |
| 2 Menubar | conditional | `.commands { ... }` or `MenuBarExtra(` present | `ModalAndMenuTests.swift` |
| 3 Multi-window | conditional | Scene-count > 1 | `MultiWindowAndToolbarTests.swift` |
| 3 Toolbar | conditional | `ToolbarItem(`-count ≥ 2 | `MultiWindowAndToolbarTests.swift` |

**TIER-1 is non-negotiable.** Even on a project where heuristics return weak matches, three test files appear. Smoke validates app launches. Happy-path and Error-recovery may need user-tuning but provide a starting structure.

**TIER-2 and TIER-3 conditional.** Skipped silently if pattern not detected. Report says e.g. "TIER-2 sheet/modal: not generated (no `.sheet(isPresented:)` found)".

## Identifier convention

Format: `<ViewName>_<ControlType>_<Purpose>`

- snake_case all parts
- `_` separator (consistent grep-by-view: `PlanCardView_` matches all PlanCardView-controls)
- Stable across label-text changes (refactor-safe)

Examples:
- `PlanCardView_Button_GeneratePlan`
- `SettingsView_Toggle_EnableTelemetry`
- `AIChatView_TextField_PromptInput`
- `ToolbarView_NavigationLink_OpenSettings`

Convention doc: `docs/accessibility-identifiers.md` (auto-generated by skill, includes table of all applied identifiers + rationale).

## Output format

After Phase 0 emission and identifier-application, the final report (single message at end of skill execution):

```markdown
## /macos-e2e-scaffold report — <ProjectName>

### Phase 0
✅ Swift project (<project-type>)
✅ SwiftUI macOS app (<N> Scenes detected, macOS signal: <signal>)
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
- `ModalAndMenuTests.swift` :: testTIER2_<...> (if pattern detected)

**TIER-3 (<n> — patterns not detected | generated)**
- Multi-window: <generated | not generated (single WindowGroup)>
- Toolbar: <generated | not generated (only N ToolbarItem)>

### Runner script
- `scripts/run-uitests.sh` — `xcodebuild test -only-testing:<TARGET_DIR>`, parses xcresult to Claude-readable JSON (Xcode 16+ format; falls back to plaintext on older Xcode)

### Convention doc
- `docs/accessibility-identifiers.md` — `<ViewName>_<ControlType>_<Purpose>`, snake_case, examples, full identifier table

### Project-type integration
<branch-specific instructions per Project-type-specific-behavior section>

### Next steps
1. <project-type-specific build step>
2. `./scripts/run-uitests.sh` — all <S> TIER stubs will fail with `XCTFail("not implemented")`. That's expected — fill in assertions per stub.
3. Re-invoke /macos-e2e-scaffold if you add new top-level views or controls. Skill detects existing UI test target and refuses overwrite (extend manually).
```

## Project-type-specific behavior

### xcodegen-managed
Modify `xcodegen.yml` (or `project.yml`) to add new target:

```yaml
targets:
  <TARGET_DIR>:
    type: bundle.ui-testing
    platform: macOS
    sources:
      - <TARGET_DIR>
    dependencies:
      - target: <App>
```

Skill writes the diff. User runs `xcodegen generate` to regenerate `.xcodeproj`. Report says: "Run `xcodegen generate` before opening Xcode."

### SPM-based
SwiftPM does NOT support UI Test bundles natively (only `.testTarget` for unit tests). UI Tests require `.xcodeproj`.

Skill detects this case:
- Generate test files in `Tests/<TARGET_DIR>/` directory
- Print warning: "SPM doesn't support UI Test bundles. Generated files exist but require .xcodeproj. Recommend: switch to xcodegen-managed project, or add .xcodeproj manually."
- Refuse to attempt project-modification

This is an honest limitation, not a skill failure. (Note: SPM-only is still a valid input — the skill proceeds and generates files; it does not refuse in Phase 0.)

**Runner for SPM-only:** do NOT emit the normal Step 11 runner — without an `.xcodeproj` there is no scheme, so `xcodebuild test -scheme "$SCHEME"` fails at scheme resolution, not at test execution. Instead write a stub `scripts/run-uitests.sh` that is honest about the precondition:

```bash
#!/usr/bin/env bash
# Auto-generated by /macos-e2e-scaffold (SPM-only project).
echo "SPM-only project: no .xcodeproj → no scheme for 'xcodebuild test'." >&2
echo "Convert to an xcodegen-managed project or add an .xcodeproj, then re-run /macos-e2e-scaffold." >&2
exit 1
```

So a CI consumer that follows `/e2e-route`'s "Next action: ./scripts/run-uitests.sh" fails fast with a clear reason instead of an opaque scheme-resolution error.

### plain .xcodeproj (no xcodegen)
Skill cannot reliably modify `project.pbxproj` programmatically (one wrong line corrupts the project).

- Generate files in `<TARGET_DIR>/` directory
- Emit step-by-step manual instructions:
  ```
  1. Open <App>.xcodeproj in Xcode
  2. File > New > Target > macOS > UI Testing Bundle
  3. Name: <TARGET_DIR>  ← MUST equal the Phase 0 TARGET_DIR EXACTLY. The generated
     scripts/run-uitests.sh hardcodes `-only-testing:"${UITEST_TARGET}"` with this
     name baked in; a different Xcode-suggested name makes the runner report
     "no tests / target not found".
  4. Drag generated .swift files into target
  5. Set Host Application: <App>
  6. Build target once to verify
  ```
- Report says: "Generated files exist; manual Xcode steps required for target setup. Name the UI-test target exactly `<TARGET_DIR>` to match the runner."

## Failure modes

| Mode | Detection | Resolution |
|---|---|---|
| Project doesn't build | `xcodebuild build` fails before scaffold | Skill stops; user fixes build first |
| Identifier uniqueness conflict | Same ID for 2+ controls | Skip both; flag for manual review |
| Existing UI test target | Phase 0 globs `*UITests/` (any dir, excluding `*iOSUITests/`) `*.swift` count > 1 — name-agnostic, before scheme detection | Refuse; suggest manual extension |
| Phase 0 fails | Refuse-condition triggered | Return early; never modify files |
| Platform ambiguous (WindowGroup only) | No macOS-discriminating signal found | Refuse "No SwiftUI macOS app target detected" — do NOT assume macOS from WindowGroup |
| Multiplatform target | `.iOS(` AND `.macOS(`, or both platforms in SUPPORTED_PLATFORMS | Pass; scaffold macOS tests into `<App>macOSUITests/`; note iOS surface needs /ios-e2e-scaffold |
| User declines identifier-application | `[s]kip` answer | Skip Step 9; generate test files with placeholder comments |
| Cherry-pick rejected per-suggestion | User says `[n]` | Apply only confirmed subset |
| xcodegen not in PATH | `xcodegen` not found | Emit instruction: `brew install xcodegen` |
| Empty SwiftUI app | Step 4 yields zero interactive controls | Generate Smoke test only; report "No interactive controls found — only Smoke test generated. Add controls and re-invoke." |
| Existing `.accessibilityIdentifier(...)` | Step 7 next-5-lines check | Preserve; report under "Already identified (preserved)" |
| Controls in `#Preview { ... }` / `PreviewProvider` | Step 7 brace-depth tracking | Exclude from suggestions and density count |
| xcresulttool API mismatch | `xcrun xcresulttool` exits non-zero | Runner falls back to `tail -50` of plaintext xcodebuild output; header notes Xcode 16+ requirement |
| xcodegen.yml unknown structure | Cannot find `targets:`/`name:` keys | Switch to plain .xcodeproj branch; do NOT modify yml; flag ambiguity in report |

**Skill never silently corrupts project files.** All modifications confirmed; uniqueness conflicts skip; .xcodeproj is never directly edited.

## Relationship to other skills

| Skill | Layer | Asks |
|---|---|---|
| `pitfall-verification` | artifact | Will this work? |
| `quality-review` | artifact | Will this feel premium? |
| `macos-native-review` | artifact | Is this Apple-native? |
| **`macos-e2e-scaffold`** | **project** | **Is this E2E-tested?** |
| `swiftui-expert-skill` (Antoine) | code | Is the view code idiomatic? |
| `swift-testing-expert` (Antoine) | code | Is unit-test code idiomatic? |
| `swift-concurrency-expert` (Antoine) | code | Is async/await usage correct? |
| `core-data-expert` (Antoine) | code | Is the persistence layer well-designed? |

`macos-e2e-scaffold` is one of the two scaffold skills (with `/ios-e2e-scaffold`) that *create* test infrastructure rather than *reviewing* artefacts. This warrants the manual-only invocation pattern (no auto-trigger) — skill should run with full user awareness, not as a pipeline step.

## Runner script template

`scripts/run-uitests.sh`:

```bash
#!/usr/bin/env bash
# Auto-generated by /macos-e2e-scaffold v1.10.0
# Runs UI tests and emits Claude-readable JSON summary.
# Requires Xcode 16+ for JSON xcresulttool format; falls back to plaintext on older.

set -uo pipefail

SCHEME="<APP>"
UITEST_TARGET="<TARGET_DIR>"   # <App>UITests, or <App>macOSUITests on multiplatform
RESULT_BUNDLE="$(mktemp -d)/uitests.xcresult"

# Run the tests. Capture xcodebuild's OWN exit status via PIPESTATUS — piping into
# `tail` would otherwise mask a non-zero status (tail returns 0), making a failing
# committed-regression run look green in CI.
xcodebuild test \
  -scheme "$SCHEME" \
  -destination 'platform=macOS' \
  -only-testing:"${UITEST_TARGET}" \
  -resultBundlePath "$RESULT_BUNDLE" \
  -quiet 2>&1 | tail -50
TEST_STATUS=${PIPESTATUS[0]}

# Parse xcresult to JSON summary (Xcode 16+); fall back to plaintext on older Xcode.
xcrun xcresulttool get test-results summary --path "$RESULT_BUNDLE" --format json 2>/dev/null \
  | jq '{total: .totalTestCount, passed: .passedTests, failed: .failedTests, results: [((.testFailures // [])[]) | {test: .testIdentifier, file: .sourceCodeContext.location.filePath, line: .sourceCodeContext.location.lineNumber, message: .failureText}]}' 2>/dev/null \
  || { echo "(Xcode 16+ JSON format unavailable — falling back to plaintext)"; \
       xcrun xcresulttool get --path "$RESULT_BUNDLE" 2>/dev/null | tail -100 || true; }
# NOTE: `.testFailures` is null/absent on an all-green run; `(.testFailures // [])`
# guards `null | .[]` so passing runs still emit clean JSON instead of falling back.

# Exit with the REAL test status so CI / committed-regression runs fail when tests fail.
exit "$TEST_STATUS"
```
