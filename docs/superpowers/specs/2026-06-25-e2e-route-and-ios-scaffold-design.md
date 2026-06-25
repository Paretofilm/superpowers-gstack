# Design: `e2e-route` dispatcher + `ios-e2e-scaffold`

Date: 2026-06-25
Status: approved (brainstorming → plan)
Branch: `feat/e2e-route-and-ios-scaffold`

## Problem

The user develops both iOS and macOS Swift apps and wants automated E2E testing
where an agent can "press buttons and observe expected results." Accessibility-tree
driven interaction (the user's intuition) is exactly how both Apple's XCUITest and
the MCP simulator-automation tools locate and actuate controls.

Today the repo has partial support:

- **MCP-live path** (agent presses buttons live in a session) — exists for **both**
  platforms via `XcodeBuildMCP` (`snapshot_ui`/tap/screenshot) and the `ios-simulator`
  MCP (`ui_find_element`/`ui_tap`/`ui_describe_all`), plus `/ios-qa`.
- **Committed-XCUITest path** (deterministic regression tests in the repo / CI) —
  exists only for **macOS** via `/macos-e2e-scaffold`. The iOS equivalent
  (`ios-e2e-scaffold`) was specced in IDEAS.md but deferred.

Two gaps:

1. No **routing layer** that decides, per test, which executor is right given the
   context (platform × intent × verification kind).
2. The iOS committed-regression path has **no scaffold target**.

This design closes both by shipping two skills together.

## Scope

Two skills in one deliverable:

1. **`ios-e2e-scaffold`** — mirrors `macos-e2e-scaffold` with iOS-specific heuristics.
   Closes the iOS committed-regression gap so the dispatcher never has to degrade.
2. **`e2e-route`** — a pure-dispatcher skill that reads context, picks the right
   executor, and hands off. The thin routing layer above the scaffold skills and the
   MCP-live tools — analogous to how `pitfall-verification` orchestrates lenses
   without reimplementing them.

Out of scope: `swiftui-snapshot-scaffold` and `appkit-e2e-scaffold` remain deferred
(IDEAS.md). `e2e-route`'s visual-regression row routes to the *existing*
screenshot/vision + `/ios-design-review` path, not to a new snapshot skill.

## Build order

`ios-e2e-scaffold` first (zero dependencies — standalone scaffold), then `e2e-route`
on top (dispatches to two now-existing scaffold targets). Natural two-phase plan.

---

## Skill 1: `ios-e2e-scaffold`

Manual-invocation skill that bootstraps XCUITest infrastructure for **iOS** SwiftUI
projects. Mirrors `macos-e2e-scaffold`'s deterministic Read+Grep heuristic; differs
only where iOS differs.

### Phase 0 — self-check (refuse-conditions)

| Check | Detect via | Refuse-message |
|---|---|---|
| Swift project | `*.xcodeproj` or `Package.swift` in cwd | "Not a Swift project. /ios-e2e-scaffold requires .xcodeproj or Package.swift in project root." |
| iOS SwiftUI app | iOS target (`Package.swift` `.iOS(.v…)` or `.xcodeproj` scheme platform = iOS) **and** SwiftUI scene (`WindowGroup`/`@main App`) | "No iOS SwiftUI app target detected. Skill is iOS-only — for macOS use /macos-e2e-scaffold, for AppKit use /appkit-e2e-scaffold (deferred)." |
| Not already scaffolded | `<App>UITests/` exists with >1 `*.swift` | "UI test target already exists with N test files. Skill won't overwrite — extend manually instead." |

Emit a Phase 0 result block on success (scheme, source root, swift-file count, project type).

### What it does

1. **Audits** the SwiftUI Scene tree — walks from `@main App`, ranks views by
   interactive-control density, identifies top 5 flows.
2. **Suggests** accessibility identifiers (`domene.skjerm.handling`) for each control
   in the top 5; applies after **batch confirmation**.
3. **Generates** ranked TIER-1/2/3 XCUITest stubs with `XCTFail("not implemented")`
   placeholders, an identifier-convention doc, and a Claude-readable xcresult runner
   script.

### iOS-specific differences from the macOS skill

- **Scene-walk root patterns:** `TabView` / `NavigationStack` / `NavigationSplitView`
  at root (not `WindowGroup` / `MenuBarExtra` / `Settings`).
- **Interaction surfaces unique to iOS:** tab-bar items, sheet detents
  (`.presentationDetents`), full-screen covers, swipe-actions, pull-to-refresh,
  device rotation, safe-area insets.
- **Runner-script destination:** `platform=iOS Simulator,name=iPhone 15` (vs macOS
  destination). Boots the simulator if needed.
- **TIER mappings:** iOS top-flows (onboarding, tab navigation, modal present/dismiss,
  list→detail push) differ from macOS top-flows (window/menu/toolbar).

Not a wrapper around `macos-e2e-scaffold` — a distinct heuristic that shares the
macОS skill's *shape* but has iOS-specific targets.

### What it is NOT

Not a review skill, not a code-quality reviewer, not macOS-aware, not snapshot-aware,
not auto-invoked (manual `/ios-e2e-scaffold` only).

---

## Skill 2: `e2e-route`

A **pure dispatcher**. Given a test request it reads context deterministically,
chooses the right E2E executor, and dispatches — it does **not** own execution.

### Triggering

Manual `/e2e-route` always works, **plus** a CLAUDE.md routing line that intercepts
natural intents ("test the app", "e2e", "trykk gjennom flyten") and dispatches.
Not auto-hooked (no PostToolUse/UserPromptSubmit hook — avoids hijacking existing
`/qa` / `/ios-qa` routing).

### Routing inputs (read in order)

1. **Intent** — CI env (`CI` / `GITHUB_ACTIONS`) forces *committed*. Else inferred
   from verbs (`utforsk`/`sjekk`/`dogfood`/`trykk gjennom` → MCP-live;
   `må aldri knekke`/`regresjon`/`CI` → committed). Ask the user **once** only when
   the signals are genuinely ambiguous.
2. **Platform** — `show_build_settings` / `list_schemes` or `.gstack/track`. Ask only
   if undetectable.
3. **Verification kind** (optional refinement) — functional/AX-assertion vs visual.

### Routing table (doubles as the test oracle)

| Intent | Platform | Executor |
|---|---|---|
| Committed regression | macOS | `/macos-e2e-scaffold` + its xcresult runner |
| Committed regression | iOS | `/ios-e2e-scaffold` |
| Exploratory / live | macOS | `XcodeBuildMCP` UI-automation (`snapshot_ui` → tap → screenshot) |
| Exploratory / live | iOS | `ios-simulator` MCP (`ui_find_element`/`ui_tap`) / `/ios-qa` |
| Visual regression | both | screenshot/vision diff + `/ios-design-review` |

**Fallback:** if a committed-regression route's scaffold Phase 0 refuses (e.g. iOS app
that is not SwiftUI), `e2e-route` degrades to the MCP-live row for that platform and
emits an explicit note naming the unmet precondition. No false promise; always a way
forward.

### Output and boundaries

Emits one **routing-decision block**: chosen executor, the detected context that drove
the choice, and the exact next action (skill to invoke or MCP sequence). Then hands
control back. It does **not** build/tap/assert itself, does **not** modify app files
(the scaffold skills do that), and is **not** a QA-report writer.

Shared foundation it points at (but does not own): the `domene.skjerm.handling`
accessibility-identifier convention — both executors locate elements the same way.

### Phase 0 — self-check

- Not a Swift project → refuse.
- No detectable scheme/target → ask once, else refuse.

---

## Testing

Both skills are markdown routing/heuristic skills, so "testing" = dry-run scenarios:

- **`e2e-route`:** the routing table above is the truth table. It is embedded in the
  skill as an explicit oracle — every (intent × platform) combination has one expected
  executor, verifiable by reading the decision block the skill emits for a given
  context.
- **`ios-e2e-scaffold`:** the Phase 0 refuse-matrix and the TIER-mapping are the
  oracle — verify against a real iOS SwiftUI fixture that detection and ranking pick
  the documented targets.

## Deliverable files

- `skills/ios-e2e-scaffold/SKILL.md`
- `skills/e2e-route/SKILL.md`
- `CLAUDE.md` — new routing lines for both skills
- `IDEAS.md` — mark `ios-e2e-scaffold` shipped; add `e2e-route` as the router above the
  scaffold skills; note `swiftui-snapshot-scaffold` / `appkit-e2e-scaffold` still deferred
- `.claude-plugin/plugin.json` — version bump
- `CHANGELOG.md` — entry
- (skill discovery tables in `skills/setup-routing/SKILL.md` and `skills/adapt/SKILL.md`
  if they enumerate skills — keep in sync)
