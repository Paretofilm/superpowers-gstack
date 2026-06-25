# e2e-route + ios-e2e-scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship two skills — `ios-e2e-scaffold` (XCUITest scaffolding for iOS SwiftUI apps, mirroring `macos-e2e-scaffold`) and `e2e-route` (a pure-dispatcher that routes a test request to the right E2E executor) — plus the routing/version wiring.

**Architecture:** `ios-e2e-scaffold` is a standalone deterministic Read+Grep heuristic skill that mirrors the shape of `skills/macos-e2e-scaffold/SKILL.md` but swaps in iOS-specific Scene-walk patterns, TIER mappings, and an iOS-Simulator runner destination. `e2e-route` sits above both scaffold skills and the MCP-live tools as a thin routing layer (no execution of its own), analogous to how `pitfall-verification` orchestrates lenses. Build the scaffold first (zero deps), then the dispatcher on top.

**Tech Stack:** Markdown SKILL.md files (Claude Code plugin skills). No runtime code. "Tests" are structural grep assertions + dry-run scenario walks against the documented routing/refuse oracle.

## Global Constraints

- Plugin name: `superpowers-gstack`. Current version `2.16.0` (in `.claude-plugin/plugin.json`). Bump to `2.17.0` (two new skills = minor).
- Skills live in `skills/<name>/SKILL.md` with YAML frontmatter `name:` + `description:` + `version:` (per existing skills).
- `ios-e2e-scaffold` is **manual-invocation only** — same model as `macos-e2e-scaffold` / `setup-routing`. No auto-trigger hook.
- `e2e-route` is **manual + CLAUDE.md routing** — no PostToolUse/UserPromptSubmit hook.
- Identifier convention is `<ViewName>_<ControlType>_<Purpose>` (snake_case) — match `macos-e2e-scaffold` exactly. The shipped macOS skill is the source of truth and the dispatcher must point at one consistent convention. (Design doc reconciled 2026-06-25 to this form.)
- Bump plugin version whenever pushing plugin changes (or cache won't update).
- Dual-track repo: skills must not assume web default. These are native-track skills — fine.

---

## File Structure

- `skills/ios-e2e-scaffold/SKILL.md` — Phase 1. New scaffold skill (mirror of macOS).
- `skills/e2e-route/SKILL.md` — Phase 2. New dispatcher skill.
- `IDEAS.md` — Phase 2. Mark `ios-e2e-scaffold` shipped; add `e2e-route`; keep snapshot/appkit deferred.
- `CLAUDE.md` — Phase 2. Add routing lines for both skills.
- `.claude-plugin/plugin.json` — Phase 2. Version bump `2.16.0` → `2.17.0`.
- `CHANGELOG.md` — Phase 2. New entry.
- `skills/setup-routing/SKILL.md`, `skills/adapt/SKILL.md` — Phase 2. Sync skill-evaluation tables IF they enumerate the e2e skills.
- `skills/macos-e2e-scaffold/SKILL.md` — Phase 2. One-line update: change "for iOS use /ios-e2e-scaffold (deferred)" → "(shipped)".

---

## Phase 1 — Task 1: `ios-e2e-scaffold` skill

**Files:**
- Create: `skills/ios-e2e-scaffold/SKILL.md`
- Reference (read-only template): `skills/macos-e2e-scaffold/SKILL.md`

**Interfaces:**
- Produces: a skill named `ios-e2e-scaffold` invoked as `/superpowers-gstack:ios-e2e-scaffold`. `e2e-route` (Phase 2) dispatches to it for the (committed-regression × iOS) cell. The dispatcher relies on these exact section names existing: `## Phase 0 — Self-check` (refuse-conditions) and the iOS-Simulator runner destination string `platform=iOS Simulator,name=iPhone 15`.

- [ ] **Step 1: Create the skill file, mirroring the macOS skill section-for-section**

Author `skills/ios-e2e-scaffold/SKILL.md`. Copy the *shape* of `macos-e2e-scaffold` (frontmatter, Phase 0, What-it-does, What-it-is-NOT, Heuristic process Steps 1–13, TIER rubric, Identifier convention, Output format, Project-type-specific behavior, Failure modes, Relationship-to-other-skills, Runner-script template). Apply these iOS-specific substitutions:

Frontmatter:
```yaml
---
name: ios-e2e-scaffold
description: One-shot XCUITest scaffolding for iOS SwiftUI apps. Audits the Scene tree, generates ranked TIER-1/2/3 test stubs, suggests accessibility identifiers with batch confirmation, and emits a Claude-readable xcresult runner script targeting the iOS Simulator. Manual invocation only — modifies project files.
version: 1.0.0
---
```

Phase 0 refuse-matrix (iOS variant):

| Check | Detect via | Refuse-message |
|---|---|---|
| Swift project | `*.xcodeproj` or `Package.swift` in cwd | "Not a Swift project. /ios-e2e-scaffold requires .xcodeproj or Package.swift in project root." |
| iOS SwiftUI app | **iOS-discriminating** signal (see below) AND SwiftUI scene (`@main` + `App`/`WindowGroup`/`TabView`/`NavigationStack`) | "No iOS SwiftUI app target detected. Skill is iOS-only — for macOS use /macos-e2e-scaffold, for AppKit use /appkit-e2e-scaffold (deferred)." |
| Not already scaffolded | `<App>UITests/` with `*.swift` count > 1 | "UI test target already exists with N test files. Skill won't overwrite — extend manually instead." |

> **iOS-discriminating signal — REQUIRED, because `WindowGroup` is cross-platform (shared with macOS) and does NOT identify iOS on its own.** Detect iOS via the FIRST that matches:
> 1. SPM: `Package.swift` contains `.iOS(` in a `platforms:` clause (and the target is an app, not a library).
> 2. xcodegen: `project.yml`/`xcodegen.yml` target has `platform: iOS`.
> 3. plain `.xcodeproj`: `project.pbxproj` contains `SDKROOT = iphoneos` or `SUPPORTED_PLATFORMS = "?iphoneos` for the app target's build config.
> 4. Corroborating (necessary-not-sufficient): `grep -rl 'import UIKit' --include='*.swift'` and absence of macOS-only scenes (`MenuBarExtra(`, `Settings {`, `Window(`).
>
> If a target builds for BOTH iOS and macOS (multiplatform: `.iOS(` AND `.macOS(` in Package.swift, or `SUPPORTED_PLATFORMS` lists both): Phase 0 **passes** (iOS is among the platforms) but emits a note — "Multiplatform target detected; scaffolding iOS-Simulator tests. Run /macos-e2e-scaffold separately for the macOS surface." Use `iphoneos`/`.iOS(` presence as sufficient; do not refuse just because macOS is also supported.

Step 4 (Scene-walk) iOS root patterns — grep:
```
grep -rn -E 'WindowGroup|TabView\s*[({]|NavigationStack|NavigationSplitView' --include='*.swift'
```
And per-view destination patterns add iOS-specific: `.sheet(isPresented:`, `.sheet(item:`, `.fullScreenCover(isPresented:`, `.fullScreenCover(item:`, `.popover(`, `NavigationLink(`, `.navigationDestination(`.

Step 4 interactive-control patterns — keep the macOS five (`Button`, `Toggle`, `TextField`, `Picker`, `NavigationLink`) and ADD iOS-common: `\bStepper\b\s*\(`, `\bSlider\b\s*\(`, `\bDatePicker\b\s*\(`, `\bMenu\b\s*[({]`.

Step 6 TIER mappings (iOS variant):
- TIER-1 #1 Smoke: always (app launches, root scene appears).
- TIER-1 #2 Happy-path: top-ranked view's primary action (same `await`/`generate*`/`create*`/`save*`/`run*`/`start*` heuristic + generic-fallback comment).
- TIER-1 #3 Error-recovery: first view (alphabetical+line tiebreak) with `.alert(`, `errorMessage`, `failure`, or `error: Error`.
- TIER-2 Modal: if `.sheet(isPresented:`/`.sheet(item:`/`.fullScreenCover(`/`.popover(` found → `ModalAndSheetTests.swift`.
- TIER-2 Tab-navigation: if `TabView` found → `TabNavigationTests.swift` (assert tab switch changes selected content).
- TIER-3 Push-navigation: if `NavigationStack` + (`NavigationLink(`-count ≥ 2 OR `.navigationDestination(` present) → `PushNavigationTests.swift` (list → detail push/pop).
- TIER-3 Gestures/rotation: if `.swipeActions(`, `.refreshable`, OR `.onRotate`/orientation usage found → `GestureAndRotationTests.swift`.

(Drop the macOS-only Menubar / Multi-window / Toolbar tiers — replace with the iOS tiers above.)

Step 11 (Runner script) — iOS destination. Template body identical to macOS EXCEPT:
```bash
DEST='platform=iOS Simulator,name=iPhone 15'
xcodebuild test \
  -scheme "$SCHEME" \
  -destination "$DEST" \
  -only-testing:"${SCHEME}UITests" \
  -resultBundlePath "$RESULT_BUNDLE" \
  -quiet 2>&1 | tail -50
```
Add a comment: boots the simulator on demand; if the named device is missing, fall back to the first available iOS Simulator via `xcrun simctl list devices available`.

Project-type-specific behavior: keep the three branches (xcodegen-managed / SPM-based / plain .xcodeproj) but set `platform: iOS` in the xcodegen target snippet and the Xcode manual-steps say "iOS > UI Testing Bundle".

"What this skill is NOT" — flip the cross-references: "Not macOS-aware. Use /macos-e2e-scaffold." Keep AppKit/snapshot deferred lines.

- [ ] **Step 2: Structural verification (the test)**

Run these greps; each MUST return a hit (this is the oracle for "the skill is complete"):
```bash
F=skills/ios-e2e-scaffold/SKILL.md
grep -q '^name: ios-e2e-scaffold' "$F" && echo "ok:name"
grep -q '^version: 1.0.0' "$F" && echo "ok:version"
grep -q '## Phase 0 — Self-check' "$F" && echo "ok:phase0"
grep -q 'platform=iOS Simulator' "$F" && echo "ok:ios-destination"
grep -q 'TabView' "$F" && grep -q 'NavigationStack' "$F" && echo "ok:ios-scene-patterns"
grep -q '/macos-e2e-scaffold' "$F" && echo "ok:macos-crossref"
grep -qi 'manual' "$F" && echo "ok:manual-only"
! grep -qF "destination 'platform=macOS'" "$F" && echo "ok:no-macos-runner"
```
Expected: eight `ok:` lines. Any missing → fix the corresponding section before continuing. (The last check confirms no macOS *runner destination* leaked in — it deliberately does NOT grep `MenuBarExtra`, which the iOS skill legitimately names in its platform-exclusion guidance.)

- [ ] **Step 3: Dry-run scenario walk**

In prose (no app needed), trace the heuristic against a hypothetical iOS app with `TabView` root + one `.sheet`. Confirm: Phase 0 passes (iOS SwiftUI detected), Smoke+Happy+Error TIER-1 always emit, TIER-2 Modal + TIER-2 Tab-navigation emit, TIER-3 push/gesture conditionals evaluate correctly. Record the trace as a fenced block at the end of this step's notes (not in the skill file).

- [ ] **Step 4: Commit**
```bash
git add skills/ios-e2e-scaffold/SKILL.md
git commit -m "feat(ios-e2e-scaffold): XCUITest scaffolding for iOS SwiftUI apps"
```

---

## Phase 2 — Task 2: `e2e-route` dispatcher skill

**Files:**
- Create: `skills/e2e-route/SKILL.md`

**Interfaces:**
- Consumes: `/ios-e2e-scaffold` (Task 1), `/macos-e2e-scaffold` (existing), `/ios-qa` (existing), `/ios-design-review` (existing), and the MCP-live tools (`XcodeBuildMCP`, `ios-simulator`).
- Produces: a skill `e2e-route` invoked as `/superpowers-gstack:e2e-route`. CLAUDE.md routing (Task 3) points natural test-intents at it.

- [ ] **Step 1: Create `skills/e2e-route/SKILL.md`**

Frontmatter:
```yaml
---
name: e2e-route
description: Pure-dispatcher that picks the right E2E executor for a Swift test request from context (platform × intent × verification kind) and hands off — without owning execution. Routes to /macos-e2e-scaffold, /ios-e2e-scaffold, MCP-live simulator automation, or /ios-qa / /ios-design-review. Manual + CLAUDE.md routing.
version: 1.0.0
---
```

Body sections (author each in full):

1. `# e2e-route` + one-paragraph statement of "pure dispatcher, does not own execution".

2. `## Phase 0 — Self-check`:
   - Not a Swift project (`*.xcodeproj`/`Package.swift` absent) → refuse: "Not a Swift project. /e2e-route needs a Swift app to route tests for."
   - No detectable scheme/target → ask once, else refuse.

3. `## Routing inputs (read in order)`:
   - **Intent** — detect CI by running Bash `[ -n "${CI:-}${GITHUB_ACTIONS:-}" ] && echo CI`; if set, force *committed* (a CI context cannot drive a live MCP simulator session). Else infer from the user's verbs: `utforsk`/`sjekk`/`dogfood`/`trykk gjennom`/`explore`/`smoke` → MCP-live; `må aldri knekke`/`regresjon`/`CI`/`regression` → committed. **Ambiguous (no verb signal, not in CI) → ask the user once: "Exploratory live run or committed regression test?"**
   - **Platform** — detect via `XcodeBuildMCP` `show_build_settings`/`list_schemes` (read `SDKROOT`/`SUPPORTED_PLATFORMS`) or `.gstack/track`; iOS vs macOS. Detection mechanism (state it explicitly in the skill): run `mcp__XcodeBuildMCP__show_build_settings` and read `SUPPORTED_PLATFORMS`; if MCP unavailable, `grep -E 'SDKROOT|SUPPORTED_PLATFORMS' *.xcodeproj/project.pbxproj` or read `.gstack/track`. Ask only if undetectable.
   - **Multiplatform tiebreak (REQUIRED — the user's premise is "both platforms"):** if the detected target supports BOTH iOS and macOS (`SUPPORTED_PLATFORMS` lists both, or `.gstack/track` = `both`, or two schemes one per platform), the platform is NOT uniquely determined. Resolve in this order: (a) if the test request names a platform ("test the iPhone flow", "macOS menu bar") → use it; (b) else ask the user once: "This app targets both iOS and macOS — route this test to iOS, macOS, or both?"; (c) "both" → emit two decision blocks (one per platform), each routing to its platform's executor.
   - **Verification kind** (optional) — functional/AX-assertion vs visual.

4. `## Routing table` (the oracle — reproduce verbatim):

| Intent | Platform | Executor |
|---|---|---|
| Committed regression | macOS | `/macos-e2e-scaffold` + its xcresult runner |
| Committed regression | iOS | `/ios-e2e-scaffold` |
| Exploratory / live | macOS | `XcodeBuildMCP` UI-automation (`snapshot_ui` → tap → screenshot) |
| Exploratory / live | iOS | `ios-simulator` MCP (`ui_find_element`/`ui_tap`) or `/ios-qa` |
| Visual regression | both | screenshot/vision diff + `/ios-design-review` |

5. `## Fallback`: if a committed-regression route's scaffold Phase 0 refuses (e.g. iOS app not SwiftUI, or SPM-only with no .xcodeproj), degrade to the MCP-live row for that platform and emit an explicit note naming the unmet precondition. No false promise.

6. `## Output — routing-decision block`: the skill emits exactly one block and then stops:
```
## /e2e-route decision
Detected: platform=<iOS|macOS>, intent=<committed|exploratory|visual>, source=<scheme|.gstack/track|asked>
Chosen executor: <skill or MCP sequence>
Why: <one line tying context → cell>
Next action: <exact /skill to invoke OR exact MCP call sequence>
```

7. `## What this skill is NOT`: not an executor (no build/tap/assert), does not modify app files (scaffold skills do), not a QA-report writer, not auto-hooked.

8. `## Shared foundation`: points at the `<ViewName>_<ControlType>_<Purpose>` identifier convention owned by the scaffold skills — both executors locate elements via the accessibility tree the same way; the dispatcher does not own or apply identifiers.

9. `## Relationship to other skills`: a table mirroring the macOS skill's, placing `e2e-route` at the "routing" layer above `macos-e2e-scaffold`/`ios-e2e-scaffold` (project layer).

- [ ] **Step 2: Structural verification (the test)**
```bash
F=skills/e2e-route/SKILL.md
grep -q '^name: e2e-route' "$F" && echo "ok:name"
grep -q '/ios-e2e-scaffold' "$F" && grep -q '/macos-e2e-scaffold' "$F" && echo "ok:scaffold-targets"
grep -q 'ios-simulator' "$F" && grep -q 'XcodeBuildMCP' "$F" && echo "ok:mcp-live"
grep -q 'Fallback' "$F" && echo "ok:fallback"
grep -qi 'not an executor\|does not own execution\|pure.dispatcher' "$F" && echo "ok:boundary"
grep -q 'GITHUB_ACTIONS\|CI' "$F" && echo "ok:ci-forces-committed"
```
Expected: six `ok:` lines.

- [ ] **Step 3: Dry-run the routing oracle — all 5 cells**

Trace each row of the routing table with a concrete context and confirm the decision block names the documented executor. Also trace the fallback: iOS + committed + (SPM-only project) → degrades to `ios-simulator` MCP with an explicit note. Record the 6 traces as a fenced block in this step's notes.

- [ ] **Step 4: Commit**
```bash
git add skills/e2e-route/SKILL.md
git commit -m "feat(e2e-route): pure-dispatcher for Swift E2E test routing"
```

---

## Phase 2 — Task 3: Wiring (routing, IDEAS, version, changelog, sync)

**Files:**
- Modify: `CLAUDE.md`, `IDEAS.md`, `.claude-plugin/plugin.json`, `CHANGELOG.md`, `skills/macos-e2e-scaffold/SKILL.md`
- Conditionally modify: `skills/setup-routing/SKILL.md`, `skills/adapt/SKILL.md`

**Interfaces:**
- Consumes: skill names `ios-e2e-scaffold`, `e2e-route` (Tasks 1–2).

- [ ] **Step 1: Add CLAUDE.md routing lines**

In the "## Skill routing" list of `CLAUDE.md`, after the `macos-e2e-scaffold`-adjacent entries, add:
```markdown
- E2E test a Swift app, "test the app", "trykk gjennom flyten", "e2e", press buttons and verify → invoke /superpowers-gstack:e2e-route. Pure dispatcher: reads platform (scheme/.gstack/track) × intent (CI/verbs; asks once if ambiguous) and routes to /macos-e2e-scaffold, /ios-e2e-scaffold, MCP-live simulator automation, or /ios-design-review. Does not execute itself.
- Scaffold committed XCUITest for an iOS SwiftUI app → invoke /superpowers-gstack:ios-e2e-scaffold (manual only; mirrors /macos-e2e-scaffold with iOS heuristics). Normally reached via /e2e-route.
```

- [ ] **Step 2: Update IDEAS.md**

Edit the `ios-e2e-scaffold` entry status line `**Status.** Deferred until observed need...` → `**Status.** Shipped 2026-06-25 (v2.17.0). See skills/ios-e2e-scaffold/SKILL.md.` Add a new short entry for `e2e-route` describing it as the router above the scaffold skills (shipped 2026-06-25). Leave `swiftui-snapshot-scaffold` and `appkit-e2e-scaffold` as deferred.

- [ ] **Step 3: Bump plugin version**

In `.claude-plugin/plugin.json`: `"version": "2.16.0"` → `"version": "2.17.0"`.

- [ ] **Step 4: Update macos-e2e-scaffold cross-reference**

In `skills/macos-e2e-scaffold/SKILL.md`, change `for iOS use /ios-e2e-scaffold (deferred)` → `for iOS use /ios-e2e-scaffold` and the "Not iOS-aware. Use `/ios-e2e-scaffold` (deferred — IDEAS.md)." → "Not iOS-aware. Use `/ios-e2e-scaffold`."

- [ ] **Step 5: Sync setup-routing / adapt skill tables (conditional)**
```bash
grep -n 'macos-e2e-scaffold' skills/setup-routing/SKILL.md skills/adapt/SKILL.md
```
If either enumerates `macos-e2e-scaffold` in a skill-evaluation table, add parallel rows for `ios-e2e-scaffold` and `e2e-route`. If neither mentions it, skip (record "no e2e skills enumerated — skip" in notes).

- [ ] **Step 6: Add CHANGELOG entry**

Prepend a `## v2.17.0` section to `CHANGELOG.md` (match existing format) summarizing: new `ios-e2e-scaffold` skill, new `e2e-route` dispatcher, routing + IDEAS updates.

- [ ] **Step 7: Verify + commit**
```bash
python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))" && echo "ok:json-valid"
grep -q '2.17.0' .claude-plugin/plugin.json && echo "ok:version"
grep -q 'e2e-route' CLAUDE.md && grep -q 'ios-e2e-scaffold' CLAUDE.md && echo "ok:routing"
grep -q 'v2.17.0' CHANGELOG.md && echo "ok:changelog"
git add -A && git commit -m "feat(v2.17.0): wire e2e-route + ios-e2e-scaffold into routing, IDEAS, changelog"
```
Expected: four `ok:` lines, then commit.

---

## Self-Review (run after plan written)

1. **Spec coverage:** ios-e2e-scaffold (Task 1) ✓, e2e-route (Task 2) ✓, CLAUDE.md routing ✓, IDEAS.md ✓, plugin.json ✓, CHANGELOG ✓, setup-routing/adapt sync ✓, visual-regression row included in routing table ✓.
2. **Placeholder scan:** no TBD/TODO; iOS substitutions specified concretely.
3. **Type consistency:** identifier convention resolved to `<ViewName>_<ControlType>_<Purpose>` (Global Constraints) and used consistently in both skills; section names the dispatcher depends on (`## Phase 0 — Self-check`, `platform=iOS Simulator,name=iPhone 15`) are exactly the strings Task 1 produces.
