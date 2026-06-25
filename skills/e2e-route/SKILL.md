---
name: e2e-route
description: Pure-dispatcher that picks the right E2E executor for a Swift test request from context (platform × intent × verification kind) and hands off — without owning execution. Routes to /macos-e2e-scaffold, /ios-e2e-scaffold, MCP-live simulator automation, or /ios-qa / /ios-design-review. Manual + CLAUDE.md routing.
version: 1.0.0
---

# e2e-route

A **pure dispatcher** for Swift E2E testing. Given a test request it reads context
deterministically, chooses the right E2E executor, and dispatches — it does **not** own
execution. It is the thin routing layer above the scaffold skills and the MCP-live
tools, analogous to how `pitfall-verification` orchestrates lenses without
reimplementing them.

Invoke with: `/superpowers-gstack:e2e-route`

## Phase 0 — Self-check

| Check | Detect via | Refuse-message |
|---|---|---|
| Swift project | `*.xcodeproj` or `Package.swift` in cwd | "Not a Swift project. /e2e-route needs a Swift app to route tests for." |
| Detectable target | a scheme/target is discoverable (see Platform below) | If none: ask the user once which scheme to target; else refuse "No scheme/target detected — cannot route." |

## Routing inputs (read in order)

### 1. Intent — exploratory (MCP-live) vs committed (XCUITest)

- **CI forces committed.** Detect CI by running Bash:
  ```bash
  [ -n "${CI:-}${GITHUB_ACTIONS:-}" ] && echo CI
  ```
  If set, force *committed* — a CI context cannot drive a live MCP simulator session.
- **Else infer from the user's verbs:**
  - `utforsk` / `sjekk` / `dogfood` / `trykk gjennom` / `explore` / `smoke` / "press through the flow" → **MCP-live**
  - `må aldri knekke` / `regresjon` / `regression` / `CI` / "lock this down" → **committed**
- **Ambiguous** (no verb signal, not in CI) → ask the user once:
  "Exploratory live run, or committed regression test?"

### 2. Platform — iOS vs macOS

Detect via `mcp__XcodeBuildMCP__show_build_settings` / `list_schemes` (read
`SDKROOT` / `SUPPORTED_PLATFORMS`); if MCP unavailable, fall back to
`grep -E 'SDKROOT|SUPPORTED_PLATFORMS' *.xcodeproj/project.pbxproj` or read
`.gstack/track`. Ask only if undetectable.

**Multiplatform tiebreak — REQUIRED (the user's premise is "both platforms").** If the
detected target supports BOTH iOS and macOS (`SUPPORTED_PLATFORMS` lists both
`iphoneos` and `macosx`, or `.gstack/track` = `both`, or two schemes one per
platform), the platform is NOT uniquely determined. Resolve in order:

- (a) If the test request names a platform ("test the iPhone flow", "the macOS menu
  bar") → use it.
- (b) Else ask the user once: "This app targets both iOS and macOS — route this test
  to iOS, macOS, or both?"
- (c) `both` → emit **two** decision blocks (one iOS, one macOS), each routing to its
  platform's executor.

### 3. Verification kind (optional refinement)

Functional / accessibility-assertion vs visual. A request about layout, spacing,
colour, dark mode, or "does it look right" → the visual-regression row.

## Routing table (the oracle)

| Intent | Platform | Executor |
|---|---|---|
| Committed regression | macOS | `/macos-e2e-scaffold` + its xcresult runner |
| Committed regression | iOS | `/ios-e2e-scaffold` |
| Exploratory / live | macOS | `XcodeBuildMCP` UI-automation (`snapshot_ui` → tap → screenshot) |
| Exploratory / live | iOS | `ios-simulator` MCP (`ui_find_element` / `ui_tap`) or `/ios-qa` |
| Visual regression | iOS | screenshot/vision diff + `/ios-design-review` |
| Visual regression | macOS | screenshot/vision diff + `/design-review` (generic designer's-eye QA — no macOS-specific reviewer exists) |

## Fallback

Degrade to the MCP-live row for the platform **only when the chosen scaffold's Phase 0
actually refuses** — i.e. one of the scaffold's three refuse-conditions fires:

1. not a Swift project, or
2. no SwiftUI scene detected (e.g. a UIKit-/AppKit-only app), or
3. a UI-test target already exists.

Emit an explicit note naming the unmet precondition. No false promise; always a way
forward.

**SPM-only is NOT a fallback trigger.** The scaffold skills accept `Package.swift`
projects and proceed — they generate files under `Tests/<App>UITests/` with a "SwiftPM
can't host a UI-test bundle; add an .xcodeproj" warning. So for SPM-only iOS/macOS apps
the dispatcher still routes to the scaffold skill; it does NOT degrade to MCP-live.

## Output — routing-decision block

Emit **one block per resolved platform** — normally exactly one; **two when the
multiplatform tiebreak resolved to `both`** (one iOS block + one macOS block) — then
stop. Do not build/tap/assert; hand control back after emitting.

```
## /e2e-route decision
Detected: platform=<iOS|macOS>, intent=<committed|exploratory|visual>, source=<scheme|.gstack/track|asked>
Chosen executor: <skill or MCP sequence>
Why: <one line tying context → routing cell>
Next action: <exact /skill to invoke OR exact MCP call sequence>
```

## What this skill is NOT

- **Not an executor.** It does not build, tap, assert, or run tests itself — it names
  the executor and the exact next action, then hands off.
- **Not a scaffolder.** It does not modify app files or generate test stubs — the
  scaffold skills (`/ios-e2e-scaffold`, `/macos-e2e-scaffold`) do that.
- **Not a QA-report writer.** Use `/ios-qa` / `/qa` for live QA reports.
- **Not auto-hooked.** Manual `/e2e-route` + CLAUDE.md routing only — no
  PostToolUse/UserPromptSubmit hook (avoids hijacking existing `/qa` / `/ios-qa`
  routing).

## Shared foundation

Both executors locate controls via the accessibility tree the same way, using the
`<ViewName>_<ControlType>_<Purpose>` identifier convention (snake_case) **owned by the
scaffold skills** — `e2e-route` points at it but does not own or apply identifiers.
This is why the routing layer stays thin: element-lookup is identical whether the
executor is `ui_find_element("PlanListView_Button_GeneratePlan")` (MCP-live) or
`app.buttons["PlanListView_Button_GeneratePlan"].tap()` (XCUITest).

## Relationship to other skills

| Skill | Layer | Asks |
|---|---|---|
| **`e2e-route`** | **routing** | **Which executor for this test?** |
| `ios-e2e-scaffold` / `macos-e2e-scaffold` | project | Is this E2E-tested? |
| `ios-qa` | live | Does the running app behave? |
| `ios-design-review` | visual | Does it look right on device? |
| `pitfall-verification` | artifact | Will this work? |

`e2e-route` sits above the project-layer scaffold skills and the MCP-live tools. It
decides the *executor*; the executor decides *how*.
