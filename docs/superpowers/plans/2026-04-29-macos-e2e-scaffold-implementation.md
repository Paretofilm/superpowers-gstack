# `/macos-e2e-scaffold` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship plugin v1.10.0 with new skill `/macos-e2e-scaffold` that scaffolds XCUITest infrastructure for macOS SwiftUI projects.

**Architecture:** New SKILL.md following plugin-internal review-skill conventions, version-marker lockstep across plugin.json + setup-routing + adapt, README+CHANGELOG announcement, IDEAS.md sibling-stubs for deferred platforms.

**Tech Stack:** Markdown (SKILL.md), JSON (plugin.json), shell (verification commands).

**Spec reference:** `docs/superpowers/specs/2026-04-29-macos-e2e-scaffold-design.md` (commit 912818d on main)

**Branch:** `feat/macos-e2e-scaffold` off main (Task 1 creates).

**Plan structure:** 11 tasks. Tasks 1, 2, 9, 10 produce no commits (setup/verification/walkthrough/consistency). Tasks 3–8 produce one commit each on `feat/macos-e2e-scaffold`. Task 11 is push + PR.

**SDD note:** This is a markdown-only delivery (no Swift/code execution). Code-quality reviewer subagent in v1.9.0 was skipped for non-code artefacts; mirror that here. Spec-compliance reviewer still runs after each task.

---

## Task 1: Setup feature branch

**Files:**
- Create branch: `feat/macos-e2e-scaffold`

**Pre-conditions:**
- Working tree clean (no uncommitted changes outside the spec commit)
- On main, up to date with origin/main
- Spec commit (912818d) is on main and pushed

- [ ] **Step 1: Verify clean working tree**

Run:
```bash
git status --short
```

Expected: empty output (clean working tree)

If untracked files exist (e.g., `.DS_Store`, scratch files), STOP and ask user before proceeding. Do not auto-stash.

- [ ] **Step 2: Verify on main and synced with origin**

Run:
```bash
git branch --show-current && git log --oneline -1 origin/main..HEAD; echo "---"; git log --oneline -1 HEAD..origin/main
```

Expected:
- Branch: `main`
- No commits ahead of origin (first command output empty after `---`)
- No commits behind origin (second command output empty)

If either has output, STOP and resolve drift first.

- [ ] **Step 3: Create and check out feature branch**

Run:
```bash
git checkout -b feat/macos-e2e-scaffold
git branch --show-current
```

Expected:
- Output: `feat/macos-e2e-scaffold`

**No commit produced by this task.**

---

## Task 2: Validate heuristic patterns

This is a no-commit verification task. The Step 7-Step 8 grep patterns in the SKILL.md must be valid bash regex AND must not match obvious false positives. Mental walkthrough on a synthetic scenario.

- [ ] **Step 1: Validate Scene-detection patterns**

The four Scene-detection patterns from spec §6 Step 4 are:
- `WindowGroup`
- `Window(`
- `Settings {`
- `MenuBarExtra(`

Mental check: do any of these match common false positives?
- `WindowGroup` — could match a comment or string. Acceptable false-positive rate (rare).
- `Window(` — could match `NSWindow(` or `MyWindow(` (custom view). Acceptable; skill operates on SwiftUI surface area, custom Window-named types are SwiftUI by convention.
- `Settings {` — could match an arbitrary type literal. Rare.
- `MenuBarExtra(` — Apple-specific; near-zero false positives.

Verdict: patterns acceptable. Document in SKILL.md that false-positive Scene-detection results in extra heuristic work but no incorrect output.

- [ ] **Step 2: Validate control-detection patterns**

Patterns from spec §6 Step 4:
- `Button` (then `(` or `{`)
- `Toggle` (then `(`)
- `TextField` (then `(`)
- `Picker` (then `(`)
- `NavigationLink` (then `(`)

Mental check: collisions with type names?
- `Button` could match comment text. Use word-boundary: `\bButton\b\s*[({]`
- `Toggle` could match `ToggleStyle` — exclude with negative lookbehind not possible in basic grep; use `\bToggle\b\s*\(`
- `Picker` could match `PickerStyle` — same fix
- `NavigationLink` is unambiguous

Verdict: tighten patterns to require word-boundary + opening paren/brace. Document exact regex in SKILL.md.

- [ ] **Step 3: Validate identifier-conflict-detection logic**

Step 7 next-5-lines check: when checking if a control already has `.accessibilityIdentifier(...)`, scanning the next 5 lines after the control is sufficient because:
- SwiftUI modifiers chain on subsequent lines typical formatting
- 5 lines covers ~99% of realistic formatting (longest chain commonly seen: 3 modifiers per line, formatted vertically)
- Edge case: very long chain (10+ modifiers) might hide identifier — accept risk; collision-detection in Step 9 catches this anyway

Verdict: 5-line window acceptable. Document in SKILL.md as exact behaviour.

- [ ] **Step 4: Validate Preview-exclusion logic**

Patterns to detect Preview blocks:
- `#Preview {` (Swift 5.9+ macro)
- `static var previews:` (PreviewProvider conformance)

Brace-depth tracking: increment on `{`, decrement on `}`, exclude controls when depth-from-Preview-start > 0.

Mental check: nested struct/closure inside view body might confuse depth. Acceptable false-positive rate; worst case is preserving an existing identifier or skipping a real control inside a preview-only sub-view (rare).

Verdict: simple brace-depth tracking suffices. Document exact algorithm in SKILL.md.

**No commit produced by this task.** Findings inform Task 3 SKILL.md content.

---

## Task 3: Write SKILL.md

**Files:**
- Create: `skills/macos-e2e-scaffold/SKILL.md`

**Inlined content for the subagent — write this exact content:**

````markdown
---
name: macos-e2e-scaffold
description: One-shot XCUITest scaffolding for macOS SwiftUI apps. Audits the project, generates ranked TIER-1/2/3 test stubs, suggests accessibility identifiers with batch confirmation, and emits a Claude-readable xcresult runner script. Manual invocation only — modifies project files.
version: 1.10.0
---

# macos-e2e-scaffold

Manual-invocation skill that bootstraps XCUITest infrastructure for macOS SwiftUI projects.

## Phase 0 — Self-check

Before any other action, run three refuse-conditions. Any failure → return early with explicit message; no files modified.

| Check | Detect via | Refuse-message |
|---|---|---|
| Swift project | `*.xcodeproj` directory or `Package.swift` in cwd | "Not a Swift project. /macos-e2e-scaffold requires .xcodeproj or Package.swift in project root." |
| SwiftUI macOS app | grep `WindowGroup\|Window(\|Settings {\|MenuBarExtra(` in `*.swift` under source root | "No SwiftUI macOS app target detected. Skill is macOS-only — for iOS use /ios-e2e-scaffold (deferred), for AppKit use /appkit-e2e-scaffold (deferred)." |
| Not already scaffolded | `<App>UITests/` exists with `find ... -name '*.swift' \| wc -l` > 1 | "UI test target already exists with N test files. Skill won't overwrite — extend manually instead." |

Always emit Phase 0 result on success:

```
## /macos-e2e-scaffold Phase 0
✅ Swift project detected (<project>.xcodeproj | Package.swift)
✅ SwiftUI macOS app (WindowGroup found in <File.swift>:<line>)
✅ No existing UI test target

Project type: <xcodegen-managed | SPM-based | plain .xcodeproj>
Scheme: <SchemeName>
Source root: <path>
Total .swift files in source root: <N>

Proceeding with audit + scaffold.
```

## What this skill does

1. **Audits** the project: walks the SwiftUI Scene tree, ranks views by interactive-control density, identifies top 5.
2. **Suggests** accessibility identifiers for each control in top 5 views; applies them after user batch-confirmation.
3. **Generates** ranked TIER-1/2/3 test stubs with `XCTFail("not implemented")` placeholders, an identifier-convention doc, and a Claude-readable xcresult runner script.

## What this skill is NOT

- **Not a review skill.** Does not analyse spec/plan/PRD artefacts. Use `/pitfall-verification` (will-it-work?), `/quality-review` (will-it-feel-premium?), or `/macos-native-review` (is-it-Apple-native?) for those.
- **Not a code-quality reviewer.** Does not check view-code idioms (use Antoine van der Lee's `swiftui-expert-skill`) or unit-test idioms (use `swift-testing-expert`).
- **Not iOS-aware.** Use `/ios-e2e-scaffold` (deferred — IDEAS.md).
- **Not AppKit-aware.** Use `/appkit-e2e-scaffold` (deferred).
- **Not snapshot-aware.** Use `/swiftui-snapshot-scaffold` (deferred).
- **Not auto-invoked.** Manual `/macos-e2e-scaffold` only — same model as `setup-routing`.

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
- TIER-1 #2 (Happy-path): pick top-ranked view's primary button. Heuristic: `Button` containing `await` OR action calling a method named `generate*`/`create*`/`save*`/`run*`/`start*`
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

File naming:
- `<App>UITests/SmokeTest.swift` (TIER-1 #1)
- `<App>UITests/HappyPathTests.swift` (TIER-1 #2)
- `<App>UITests/ErrorRecoveryTests.swift` (TIER-1 #3)
- `<App>UITests/ModalAndMenuTests.swift` (TIER-2 if any)
- `<App>UITests/MultiWindowAndToolbarTests.swift` (TIER-3 if any)

### Step 11: Generate runner script
Write `scripts/run-uitests.sh` per template in §11 of this skill (substitute `<APP>` with detected scheme name). Make executable: `chmod +x scripts/run-uitests.sh`.

### Step 12: Generate identifier convention doc
Write `docs/accessibility-identifiers.md` with the convention, examples, rationale, and a table listing all applied identifiers with their source-file:line.

### Step 13: Emit final report
Per §8 of this skill.

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
✅ SwiftUI macOS app (<N> Scenes detected)
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
- `scripts/run-uitests.sh` — `xcodebuild test -only-testing:<App>UITests`, parses xcresult to Claude-readable JSON (Xcode 16+ format; falls back to plaintext on older Xcode)

### Convention doc
- `docs/accessibility-identifiers.md` — `<ViewName>_<ControlType>_<Purpose>`, snake_case, examples, full identifier table

### Project-type integration
<branch-specific instructions per §9>

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
  <App>UITests:
    type: bundle.ui-testing
    platform: macOS
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

This is an honest limitation, not a skill failure.

### plain .xcodeproj (no xcodegen)
Skill cannot reliably modify `project.pbxproj` programmatically (one wrong line corrupts the project).

- Generate files in `<App>UITests/` directory
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

## Failure modes

| Mode | Detection | Resolution |
|---|---|---|
| Project doesn't build | `xcodebuild build` fails before scaffold | Skill stops; user fixes build first |
| Identifier uniqueness conflict | Same ID for 2+ controls | Skip both; flag for manual review |
| Existing UI test target | Phase 0 detects `<App>UITests/*.swift` count > 1 | Refuse; suggest manual extension |
| Phase 0 fails | Refuse-condition triggered | Return early; never modify files |
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

`macos-e2e-scaffold` is the only skill in the ecosystem that *creates* test infrastructure rather than *reviewing* artefacts. This warrants the manual-only invocation pattern (no auto-trigger) — skill should run with full user awareness, not as a pipeline step.

## Runner script template

`scripts/run-uitests.sh`:

```bash
#!/usr/bin/env bash
# Auto-generated by /macos-e2e-scaffold v1.10.0
# Runs UI tests and emits Claude-readable JSON summary.
# Requires Xcode 16+ for JSON xcresulttool format; falls back to plaintext on older.

set -e

SCHEME="<APP>"
RESULT_BUNDLE="$(mktemp -d)/uitests.xcresult"

xcodebuild test \
  -scheme "$SCHEME" \
  -destination 'platform=macOS' \
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
````

**Verification commands for Task 3:**

- [ ] **Step 1: Verify file created**

Run:
```bash
test -f skills/macos-e2e-scaffold/SKILL.md && wc -l skills/macos-e2e-scaffold/SKILL.md
```

Expected: file exists; line count 250–400 (sanity check)

- [ ] **Step 2: Verify all 12 sections present in correct order**

Run:
```bash
grep -nE '^## |^---$' skills/macos-e2e-scaffold/SKILL.md | head -25
```

Expected sections in order:
1. Phase 0 — Self-check
2. What this skill does
3. What this skill is NOT
4. Heuristic process
5. TIER rubric
6. Identifier convention
7. Output format
8. Project-type-specific behavior
9. Failure modes
10. Relationship to other skills
11. Runner script template

(Plus frontmatter at top with `name`, `description`, `version: 1.10.0`.)

- [ ] **Step 3: Verify version marker**

Run:
```bash
head -5 skills/macos-e2e-scaffold/SKILL.md | grep -E '^version: 1\.10\.0$'
```

Expected: line found

- [ ] **Step 4: Commit**

```bash
git add skills/macos-e2e-scaffold/SKILL.md
git commit -m "$(cat <<'EOF'
feat(v1.10.0): add /macos-e2e-scaffold skill

XCUITest scaffolding skill for macOS SwiftUI projects. Walks Scene tree
deterministically (Read+Grep, no LLM judgment), ranks views by control
density, generates ranked TIER-1/2/3 test stubs with placeholder
assertions, suggests accessibility identifiers with batch confirmation,
and emits a Claude-readable xcresult runner script.

Manual invocation only — modifies project files. Phase 0 self-check
refuses if project is not Swift/SwiftUI/macOS or already scaffolded.

Three project-type branches: xcodegen-managed (modifies yml), SPM-based
(honest limitation — UI tests require .xcodeproj), plain .xcodeproj
(emits manual Xcode steps; never edits project.pbxproj programmatically).

Spec: docs/superpowers/specs/2026-04-29-macos-e2e-scaffold-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Bump plugin.json version 1.9.1 → 1.10.0

**Files:**
- Modify: `.claude-plugin/plugin.json:4`

- [ ] **Step 1: Read current value**

Run:
```bash
grep -n '"version"' .claude-plugin/plugin.json
```

Expected: `"version": "1.9.1"` on line ~4

- [ ] **Step 2: Edit version**

Use Edit tool to replace `"version": "1.9.1"` with `"version": "1.10.0"` in `.claude-plugin/plugin.json`.

- [ ] **Step 3: Verify**

Run:
```bash
grep '"version"' .claude-plugin/plugin.json
```

Expected: `"version": "1.10.0"`

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "$(cat <<'EOF'
chore(v1.10.0): bump plugin.json version 1.9.1 → 1.10.0

Required for marketplace cache to pick up new /macos-e2e-scaffold skill.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Bump version markers in setup-routing and adapt

**Files:**
- Modify: `skills/setup-routing/SKILL.md` (version marker)
- Modify: `skills/adapt/SKILL.md` (version marker)

These files contain a "Plugin version: X.Y.Z" line that must stay lockstep with `plugin.json` so users running `/setup-routing` or `/adapt` get correctly versioned generation output.

- [ ] **Step 1: Locate version marker in setup-routing**

Run:
```bash
grep -nE '1\.9\.1|version' skills/setup-routing/SKILL.md | head -10
```

Note the line(s) referencing `1.9.1`.

- [ ] **Step 2: Update setup-routing**

Use Edit tool to replace `1.9.1` with `1.10.0` in `skills/setup-routing/SKILL.md`. Use `replace_all: true` if there are multiple occurrences.

- [ ] **Step 3: Verify setup-routing**

Run:
```bash
grep -c '1\.10\.0' skills/setup-routing/SKILL.md
grep -c '1\.9\.1' skills/setup-routing/SKILL.md
```

Expected: count of `1.10.0` ≥ 1; count of `1.9.1` = 0

- [ ] **Step 4: Locate version marker in adapt**

Run:
```bash
grep -nE '1\.9\.1|version' skills/adapt/SKILL.md | head -10
```

- [ ] **Step 5: Update adapt**

Use Edit tool to replace `1.9.1` with `1.10.0` in `skills/adapt/SKILL.md`. Use `replace_all: true` if multiple.

- [ ] **Step 6: Verify adapt**

Run:
```bash
grep -c '1\.10\.0' skills/adapt/SKILL.md
grep -c '1\.9\.1' skills/adapt/SKILL.md
```

Expected: count of `1.10.0` ≥ 1; count of `1.9.1` = 0

- [ ] **Step 7: Commit**

```bash
git add skills/setup-routing/SKILL.md skills/adapt/SKILL.md
git commit -m "$(cat <<'EOF'
chore(v1.10.0): bump setup-routing and adapt version markers

Lockstep with plugin.json — generators emit correct version in their
output for new projects.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Update README "What's Included" — 6 → 7 skills

**Files:**
- Modify: `README.md` (What's Included section)

- [ ] **Step 1: Locate "What's Included" section**

Run:
```bash
grep -nE '^##.*Inkluder|What.s Included|## .*Skill' README.md | head -10
```

Note the section heading and start line.

- [ ] **Step 2: Read the current section to see existing 6-skill listing format**

Use Read tool on README.md around the "What's Included" section. Skills currently listed (in order added):
1. `/setup-routing`
2. `/adapt`
3. `/context-handoff`
4. `/pitfall-verification`
5. `/quality-review`
6. `/macos-native-review`

- [ ] **Step 3: Add `/macos-e2e-scaffold` as 7th bullet**

Use Edit tool. Match the existing bullet format. Insert after the `/macos-native-review` bullet:

```markdown
- **`/macos-e2e-scaffold`** — Scaffolds XCUITest infrastructure for macOS SwiftUI projects. Walks the Scene tree deterministically, generates ranked TIER-1/2/3 test stubs with placeholder assertions, suggests accessibility identifiers with batch confirmation, and emits a Claude-readable xcresult runner script. Manual invocation only — modifies project files. Phase 0 self-check refuses non-Swift, non-SwiftUI, non-macOS, or already-scaffolded projects.
```

- [ ] **Step 4: Verify count**

Run:
```bash
grep -cE '^\- \*\*`/' README.md
```

Expected: 7 (or whatever was the count before, +1)

Cross-check by reading the updated section to confirm proper formatting.

- [ ] **Step 5: Update count if mentioned in surrounding prose**

Search for explicit "six skills" or "6 skills" references that need updating to "seven" / "7":

Run:
```bash
grep -nE 'six skills|6 skills|seks skills' README.md
```

If matches: Edit to "seven skills" / "7 skills" / "syv skills" (preserve language).

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs(v1.10.0): announce /macos-e2e-scaffold in README What's Included

Sixth → seventh skill in the plugin. Scaffolds XCUITest infrastructure
for macOS SwiftUI projects, complementing the three artifact-review
skills (pitfall-verification, quality-review, macos-native-review).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Add CHANGELOG `[1.10.0] - 2026-04-29` entry

**Files:**
- Modify: `CHANGELOG.md` (insert at top after `# Changelog` heading)

- [ ] **Step 1: Read current CHANGELOG top to mirror voice**

Run:
```bash
head -30 CHANGELOG.md
```

Note the voice/structure of `[1.9.1]`, `[1.9.0]`, `[1.8.0]` entries — short paragraph + sub-headings (`### Added`, `### Changed`, etc.).

- [ ] **Step 2: Insert new entry**

Use Edit tool to insert after `# Changelog` line. New entry content:

```markdown
## [1.10.0] - 2026-04-29

### Added
- **`/macos-e2e-scaffold` skill** — One-shot XCUITest scaffolding for macOS SwiftUI projects. Walks the Scene tree deterministically (Read+Grep, no LLM judgment), ranks views by interactive-control density, and generates ranked TIER-1/2/3 test stubs (Smoke + Happy-path + Error-recovery always; Modal/Menubar/Multi-window/Toolbar conditional on pattern detection). Suggests accessibility identifiers with `<ViewName>_<ControlType>_<Purpose>` convention and applies them via batch confirmation (`[a]ll`/`[c]herry-pick`/`[s]kip`). Emits a Claude-readable `scripts/run-uitests.sh` that parses xcresult to JSON (Xcode 16+) with plaintext fallback. Three project-type branches: xcodegen-managed (modifies yml), SPM-based (honest limitation — UI tests require .xcodeproj), plain .xcodeproj (manual Xcode steps; never edits project.pbxproj programmatically). Phase 0 self-check refuses non-Swift, non-SwiftUI, non-macOS, or already-scaffolded projects. Manual invocation only — distinct from artefact-review skills which auto-trigger.

### Changed
- `setup-routing` and `adapt` version markers bumped to 1.10.0.
- IDEAS.md: added three sibling stubs (`ios-e2e-scaffold`, `swiftui-snapshot-scaffold`, `appkit-e2e-scaffold`) using the same Gap/Scope/Method/Differentiation/Status template; added `macos-e2e-scaffold` to "Shipped" section.

### Notes for users
- Skill creates new files (UI test target, identifier-doc, runner script) and modifies existing view files (adds `.accessibilityIdentifier(...)` after batch confirmation). Run only after committing or stashing in-progress work.
- Skill is the first plugin-internal skill that *generates code* rather than *reviewing artefacts*. Mental model: `/setup-routing` for the project itself, `/macos-e2e-scaffold` for the project's UI test infrastructure.
```

- [ ] **Step 3: Verify entry inserted at top**

Run:
```bash
head -25 CHANGELOG.md
```

Expected: `## [1.10.0] - 2026-04-29` is the first version-section after the `# Changelog` heading.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
docs(v1.10.0): add CHANGELOG entry for /macos-e2e-scaffold release

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Update IDEAS.md (sibling stubs + shipped section)

**Files:**
- Modify: `IDEAS.md` (add 3 sibling stubs, add macos-e2e-scaffold to Shipped section)

- [ ] **Step 1: Read current IDEAS.md to understand structure**

Use Read tool on IDEAS.md. Note:
- Whether it has separate "Proposed" and "Shipped" sections
- The Gap/Scope/Method/Differentiation/Status template format
- Which entries currently exist

If IDEAS.md doesn't have a "Shipped" section yet, the Task 8 work also adds it (model on v1.9.0 sibling stubs).

- [ ] **Step 2: Add three new "Proposed" entries**

Use Edit tool to insert these three blocks. Place them in the Proposed section (or create one if absent), in alphabetical order or grouped with related platform skills:

```markdown
### `/ios-e2e-scaffold` (proposed 2026-04-29)

**Gap:** XCUITest scaffolding for iOS SwiftUI apps; same shape as `/macos-e2e-scaffold` but with iOS-specific heuristics (gestures, tab-bar, modals, device-rotation, safe-area).

**Scope:** iOS-only. SwiftUI views. iOS Simulator destination. iOS-specific patterns (TabView, NavigationStack, sheet detents, gesture recognizers). Out: macOS, watchOS, AppKit.

**Method:** Mirrors `/macos-e2e-scaffold` deterministic Read+Grep heuristic. Detects iOS target via `Package.swift` `.iOS(.v...)` or `.xcodeproj` scheme platform. Different scene-walk patterns (TabView at root instead of WindowGroup), different runner-script destination (`platform=iOS Simulator,name=iPhone 15`).

**Differentiation:** Different heuristic targets (iOS top-flows differ from macOS), different runner-script destination, different identifier examples. Not a wrapper — distinct heuristic.

**Status:** Deferred until observed need. v1.10.0 ships `/macos-e2e-scaffold` only; iOS-only projects can still benefit from generic XCUITest knowledge but skill-form awaits demand.

---

### `/swiftui-snapshot-scaffold` (proposed 2026-04-29)

**Gap:** Snapshot-test scaffolding via `swift-snapshot-testing` (Pointfree). Catches visual regressions XCUITest misses (wrong color, wrong margin, cut-off text). Complementary to `/macos-e2e-scaffold` and `/ios-e2e-scaffold`, not a replacement.

**Scope:** Cross-platform (macOS + iOS). Adds `swift-snapshot-testing` Package.swift dependency. Generates baseline snapshots for top 5 views. First run produces baselines; subsequent runs verify.

**Method:** Detect `View`-conforming structs, render with `assertSnapshot(matching:as:.image)` skeletons. Heuristic ranks views by complexity (modifier count, sub-view count). Runner-script equivalent for snapshot diffs.

**Differentiation:** Visual regression rather than interaction. Pairs with any e2e-scaffold skill — together they cover both interaction and rendering.

**Status:** Deferred until snapshot-testing demand surfaces. Currently SwiftConfig and similar projects use unit + XCUITest; snapshot is a third tier rarely adopted from day one.

---

### `/appkit-e2e-scaffold` (proposed 2026-04-29)

**Gap:** XCUITest scaffolding for AppKit-based macOS apps (legacy or Catalyst-bridged).

**Scope:** AppKit-only views (`NSWindow`, `NSViewController`, NSAccessibility). Different identifier convention (NSAccessibility uses `accessibilityIdentifier()` method on `NSView` directly).

**Method:** Grep for `NSWindow`, `NSViewController`, `NSButton`, `NSTextField`. Different scene-walk heuristic (no SwiftUI Scene tree; AppKit uses controller hierarchy).

**Differentiation:** AppKit-only. Won't work for SwiftUI projects (use `/macos-e2e-scaffold`). Useful for legacy apps that haven't migrated to SwiftUI.

**Status:** Deferred until observed need (most modern macOS apps are SwiftUI-first).
```

- [ ] **Step 3: Add `macos-e2e-scaffold` to "Shipped" section**

If IDEAS.md has a Shipped section, append:

```markdown
- `/macos-e2e-scaffold` (shipped 2026-04-29 in v1.10.0) — XCUITest scaffolding for macOS SwiftUI projects. Walks Scene tree, generates ranked TIER-1/2/3 test stubs, suggests accessibility identifiers with batch confirmation, emits Claude-readable runner script. Three project-type branches (xcodegen / SPM / plain .xcodeproj).
```

If no Shipped section exists, create one at the top of the file with this entry plus the three earlier shipped skills:

```markdown
## Shipped

- `/pitfall-verification` (shipped 2026-04-22 in v1.5.0) — Targeted final-check skill for PRDs/specs/plans/code; max two rounds; domain-specific pitfall inference.
- `/quality-review` (shipped 2026-04-28 in v1.8.0) — Perceived-quality gate, 15 categories of "feels cheap" risks, severity-tiered findings.
- `/macos-native-review` (shipped 2026-04-28 in v1.9.0) — HIG-citation-grounded macOS conformance gate, 12 categories with developer.apple.com citations.
- `/macos-e2e-scaffold` (shipped 2026-04-29 in v1.10.0) — XCUITest scaffolding for macOS SwiftUI projects. Walks Scene tree, generates ranked TIER-1/2/3 test stubs, suggests accessibility identifiers with batch confirmation, emits Claude-readable runner script. Three project-type branches (xcodegen / SPM / plain .xcodeproj).
```

(Decision left to subagent based on actual IDEAS.md structure observed in Step 1.)

- [ ] **Step 4: Verify**

Run:
```bash
grep -cE 'ios-e2e-scaffold|swiftui-snapshot-scaffold|appkit-e2e-scaffold' IDEAS.md
grep -c 'macos-e2e-scaffold' IDEAS.md
```

Expected: first ≥ 3; second ≥ 1 (or ≥ 2 if Shipped section exists)

- [ ] **Step 5: Commit**

```bash
git add IDEAS.md
git commit -m "$(cat <<'EOF'
docs(v1.10.0): add three sibling stubs and Shipped entry to IDEAS.md

Stubs: /ios-e2e-scaffold, /swiftui-snapshot-scaffold, /appkit-e2e-scaffold.
Each follows the Gap/Scope/Method/Differentiation/Status template established
in v1.9.0 for native-review siblings.

Adds /macos-e2e-scaffold to Shipped section (creates section if absent).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Smoke test — synthetic SwiftUI macOS spec mental walkthrough

This is a no-commit verification task. Subagent walks through the SKILL.md instructions against a synthetic but realistic SwiftUI macOS project mentally, listing exactly what the skill would produce. Surfaces any category whose instructions don't cover an obvious case.

Synthetic project: `MoodTracker` (3 Scenes, 12 controls, 1 sheet, 1 menubar command, 1 alert).

**Project structure (synthetic):**

```
MoodTracker/
├── MoodTrackerApp.swift          (WindowGroup, MenuBarExtra, Settings)
├── ContentView.swift             (NavigationStack, NavigationLink → MoodEntryView)
├── MoodEntryView.swift           (Button "Save", TextField "Note", Picker "Mood", .alert)
├── SettingsView.swift            (Toggle "Notifications", Toggle "Sync")
└── HistoryView.swift             (NavigationLink-list)
```

**Patterns present:**
- `WindowGroup`: yes (1)
- `MenuBarExtra`: yes (1)
- `Settings { }`: yes (1)
- `.sheet(isPresented:)`: no
- `.commands`: yes (in MenuBarExtra body)
- `.alert(...)`: yes (in MoodEntryView)
- `ToolbarItem`: 0
- Multi-WindowGroup: no (only 1 WindowGroup)

- [ ] **Step 1: Walk Phase 0**

Expected outputs:
- ✅ Swift project (assume `.xcodeproj` and `xcodegen.yml` present → xcodegen-managed)
- ✅ SwiftUI macOS app (3 Scenes detected)
- ✅ No existing UI test target

- [ ] **Step 2: Walk Steps 1–5 (project type, scheme, source root, scene walk, ranking)**

Expected:
- Project type: xcodegen-managed
- Scheme: MoodTracker
- Source root: MoodTracker/
- Scenes walked: WindowGroup → ContentView → MoodEntryView, History; MenuBarExtra → small popover; Settings → SettingsView
- Top 5 views ranked by control density:
  1. MoodEntryView (4 controls: Button, TextField, Picker, NavigationLink-back)
  2. SettingsView (2 Toggles)
  3. ContentView (1 NavigationLink)
  4. HistoryView (n NavigationLinks — depending on synthetic)
  5. MoodTrackerApp.swift Scene-level (no interactive controls itself; rank via NavigationLink references)

- [ ] **Step 3: Walk Step 6 TIER mapping**

Expected:
- TIER-1 #1 Smoke: ✅ generated (always)
- TIER-1 #2 Happy-path: ✅ MoodEntryView's "Save" button (matches `save*` heuristic)
- TIER-1 #3 Error-recovery: ✅ MoodEntryView's `.alert(...)` (alphabetically first matching view)
- TIER-2 Modal: ❌ not generated (no `.sheet(isPresented:)`)
- TIER-2 Menubar: ✅ generated (MenuBarExtra + .commands present)
- TIER-3 Multi-window: ❌ not generated (single WindowGroup)
- TIER-3 Toolbar: ❌ not generated (zero ToolbarItem)

- [ ] **Step 4: Walk Step 7–9 identifier suggestions**

Expected suggestions for top 5 views:
- `MoodEntryView_Button_Save`
- `MoodEntryView_TextField_Note`
- `MoodEntryView_Picker_Mood`
- `SettingsView_Toggle_Notifications`
- `SettingsView_Toggle_Sync`
- `ContentView_NavigationLink_OpenEntry`
- (HistoryView links — variable)

Total ~6–10 identifier suggestions, all unique → no conflicts. User confirms `[a]ll` → all applied via Edit calls.

- [ ] **Step 5: Walk Steps 10–13 (file generation + report)**

Expected files written:
- `MoodTrackerUITests/SmokeTest.swift` (TIER-1 #1)
- `MoodTrackerUITests/HappyPathTests.swift` (TIER-1 #2 — testTIER1_SaveMoodEntry)
- `MoodTrackerUITests/ErrorRecoveryTests.swift` (TIER-1 #3 — testTIER1_MoodEntryAlert)
- `MoodTrackerUITests/ModalAndMenuTests.swift` (TIER-2 menubar only — testTIER2_MoodMenuCommand)
- (no TIER-3 file)
- `docs/accessibility-identifiers.md`
- `scripts/run-uitests.sh`
- xcodegen.yml updated with `MoodTrackerUITests` target block

- [ ] **Step 6: Detect any gap**

Walk through and flag if any of these is true:
- An obvious scenario the skill misses
- A heuristic that produces a clearly wrong stub for the synthetic project
- A category whose instructions don't cover the project's pattern
- Output format doesn't capture a generated artefact correctly

If any gap surfaces: dispatch a fix subagent that addresses the SKILL.md drift, then re-run Task 9 verification.

If no gap: report "Smoke test CLEAN. All categories produce expected output for MoodTracker synthetic spec."

**No commit produced by this task.**

---

## Task 10: Cross-file consistency check

This is a no-commit read-only verification task. Confirms version numbers + cross-references match across all touched files before push.

- [ ] **Step 1: Verify plugin.json version**

Run:
```bash
grep '"version"' .claude-plugin/plugin.json
```

Expected: `"version": "1.10.0"`

- [ ] **Step 2: Verify setup-routing version marker**

Run:
```bash
grep -E '1\.(9\.1|10\.0)' skills/setup-routing/SKILL.md | head -5
```

Expected: matches show `1.10.0`, no `1.9.1` remaining

- [ ] **Step 3: Verify adapt version marker**

Run:
```bash
grep -E '1\.(9\.1|10\.0)' skills/adapt/SKILL.md | head -5
```

Expected: matches show `1.10.0`, no `1.9.1` remaining

- [ ] **Step 4: Verify SKILL.md version marker**

Run:
```bash
grep -E '^version: ' skills/macos-e2e-scaffold/SKILL.md
```

Expected: `version: 1.10.0`

- [ ] **Step 5: Verify CHANGELOG entry**

Run:
```bash
grep '## \[1\.10\.0\]' CHANGELOG.md
```

Expected: 1 match (`## [1.10.0] - 2026-04-29`)

- [ ] **Step 6: Verify README "What's Included" mentions skill**

Run:
```bash
grep -E '/macos-e2e-scaffold' README.md
```

Expected: ≥ 1 match

- [ ] **Step 7: Verify IDEAS.md sibling stubs**

Run:
```bash
grep -E '/ios-e2e-scaffold|/swiftui-snapshot-scaffold|/appkit-e2e-scaffold' IDEAS.md
```

Expected: 3 lines (one per sibling)

- [ ] **Step 8: Verify CHANGELOG voice consistency with prior entries**

Read tool on CHANGELOG.md, check that the new `[1.10.0]` entry follows the same voice/structure as `[1.9.1]`, `[1.9.0]`, `[1.8.0]` (short paragraph leading, `### Added`/`### Changed`/`### Notes for users` sub-headings, no marketing copy).

If voice drift: dispatch a fix subagent.

- [ ] **Step 9: Verify branch is correct + clean**

Run:
```bash
git status --short
git branch --show-current
git log --oneline -7 main..HEAD
```

Expected:
- Working tree clean
- Branch: feat/macos-e2e-scaffold
- 6 commits ahead of main (Tasks 3–8 each one commit)

- [ ] **Step 10: Report**

Either `CLEAN` (proceed to Task 11) or list specific drift items. If drift, dispatch fix subagent before continuing to push.

**No commit produced by this task.**

---

## Task 11: Push branch + open PR

**Pre-conditions:** Tasks 1–10 complete and clean.

- [ ] **Step 1: Push branch to origin**

Run:
```bash
git push -u origin feat/macos-e2e-scaffold
```

Expected: branch pushed; tracking set to origin

- [ ] **Step 2: Open PR**

Run:
```bash
gh pr create --title "feat(v1.10.0): /macos-e2e-scaffold — XCUITest scaffolding skill for SwiftUI macOS apps" --body "$(cat <<'EOF'
## Summary

- Adds `/macos-e2e-scaffold` skill — one-shot XCUITest scaffolding for macOS SwiftUI projects
- Walks the Scene tree deterministically (Read+Grep, no LLM judgment); ranks views by interactive-control density; generates ranked TIER-1/2/3 test stubs (Smoke + Happy-path + Error-recovery always; Modal/Menubar/Multi-window/Toolbar conditional)
- Suggests accessibility identifiers with `<ViewName>_<ControlType>_<Purpose>` convention; applies via batch confirmation (`[a]ll`/`[c]herry-pick`/`[s]kip`)
- Emits Claude-readable `scripts/run-uitests.sh` (Xcode 16+ JSON xcresult format with plaintext fallback)
- Three project-type branches: xcodegen-managed (modifies yml), SPM-based (honest limitation — UI tests require .xcodeproj), plain .xcodeproj (manual Xcode steps; never edits project.pbxproj programmatically)
- Phase 0 self-check refuses non-Swift, non-SwiftUI, non-macOS, or already-scaffolded projects
- Manual invocation only — distinct from artefact-review skills (`pitfall-verification`/`quality-review`/`macos-native-review`)

## Spec & plan

- Spec: `docs/superpowers/specs/2026-04-29-macos-e2e-scaffold-design.md` (commit 912818d on main)
- Plan: `docs/superpowers/plans/2026-04-29-macos-e2e-scaffold-implementation.md`

## Test plan

- [ ] Plugin installs cleanly via `/plugin install superpowers-gstack@paretofilm-plugins`
- [ ] `/plugin list` shows version 1.10.0
- [ ] `/macos-e2e-scaffold` is discoverable in skill list
- [ ] Phase 0 refuse paths trigger correctly (test in non-Swift directory, non-SwiftUI Swift directory, project with existing UI test target)
- [ ] Mental walkthrough on synthetic MoodTracker project produces expected outputs (Task 9 already verified this)
- [ ] CHANGELOG voice matches v1.9.1/v1.9.0/v1.8.0 entries
- [ ] Cross-file version consistency: plugin.json + setup-routing + adapt + SKILL.md all show 1.10.0
- [ ] IDEAS.md has three sibling stubs and Shipped section entry
- [ ] README "What's Included" lists 7 skills

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 3: Report PR URL prominently to user**

Print the PR URL on its own line, prefixed with "**PR opened:**".

User reviews and merges manually. Do NOT auto-merge.

**No commit produced by this task** (push + PR-creation only).

---

## Acceptance criteria (from spec §17)

- [ ] `skills/macos-e2e-scaffold/SKILL.md` exists with all 12 sections per spec §9
- [ ] Plugin version is 1.10.0 across plugin.json, setup-routing/SKILL.md version marker, adapt/SKILL.md version marker
- [ ] README "What's Included" lists 7 skills including `/macos-e2e-scaffold`
- [ ] CHANGELOG has `[1.10.0] - 2026-04-29` entry matching v1.9.x voice
- [ ] IDEAS.md has 3 sibling stubs and `macos-e2e-scaffold` in "Shipped" section
- [ ] Smoke-test mental walkthrough on synthetic MoodTracker spec produces expected output (Phase 0 ✅, ~10 identifiers, 4 stubs across TIER-1 + TIER-2)
- [ ] Cross-file consistency check passes
- [ ] PR `feat/macos-e2e-scaffold` opened against main with title `feat(v1.10.0): /macos-e2e-scaffold — XCUITest scaffolding skill for SwiftUI macOS apps`

---

## Notes to the SDD orchestrator

1. **Tasks 4–8 commit independently on the same branch.** Run sequentially, not parallel — committing on the same branch in parallel causes rebase headaches.

2. **Task 3 SKILL.md is the bulk of the work.** Subagent receives the full inlined draft above and writes it verbatim. The "Step 3 SKILL.md verification" pattern of grep-checking section presence + line count + version-marker is sufficient — no semantic spec-compliance review needed (spec compliance is built into the inlined draft).

3. **For non-code markdown deliveries, the code-quality reviewer subagent step from SDD can be skipped** (mirror v1.9.0 macos-native-review). Spec-compliance reviewer still runs after each task.

4. **Task 9 smoke test is mental walkthrough, not file generation.** The subagent's report should list which expected outputs would be produced for each TIER on the synthetic MoodTracker spec, and flag any category whose instructions don't cover an obvious case. If gaps surface, dispatch a fix subagent before Task 10.

5. **Task 10 cross-file consistency is read-only verification.** If drift surfaces, dispatch a fix subagent that addresses just that drift, then re-run Task 10 verification.

6. **Task 11 (push + PR) must run AFTER Tasks 1–10 are all complete and clean.** Do not push until Task 10 reports CLEAN.

7. **Plugin.json version bump (Task 4) is critical** — without it, marketplace cache won't update. Task 10 verifies this explicitly.

**Out-of-scope reminders for subagents:**
- Do NOT add `macos-e2e-scaffold` to setup-routing/adapt routing tables (those are upstream-only).
- Do NOT add `macos-e2e-scaffold` to user-level CLAUDE.md (user's call, not in this delivery).
- Do NOT implement sibling skills (deferred to IDEAS.md stubs).
- Do NOT bump version beyond 1.10.0.
- Do NOT auto-merge the PR — user reviews and merges manually.

**At the end of execution:** report PR URL prominently. User reviews and merges manually.
