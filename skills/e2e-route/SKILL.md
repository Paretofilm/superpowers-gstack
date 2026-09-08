---
name: e2e-route
description: |
  Pure dispatcher: picks the right E2E executor for a Swift test request from
  context (platform × intent × verification kind) and hands off. Routes to the
  scaffold/MCP-sim/QA/design-review skills.
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
  platform's executor. **Run them SEQUENTIALLY.** The scaffolds handle coexistence via
  their shared TARGET_DIR convention: on a multiplatform target each uses a
  platform-suffixed test directory — `<App>iOSUITests/` for /ios-e2e-scaffold,
  `<App>macOSUITests/` for /macos-e2e-scaffold — and each scaffold's "already
  scaffolded" Phase-0 check globs `*UITests/` name-agnostically but EXCLUDES the
  sibling platform's suffixed directory (`*macOSUITests/` ignored by ios,
  `*iOSUITests/` ignored by macos). So whichever runs second is not blocked by the
  first's files, and the two never collide on the same directory or the same
  `xcodegen.yml`/`project.pbxproj` UI-test target. Each decision block's "Next action"
  must name its platform-specific target dir.

### 3. Verification kind (optional refinement)

Functional / accessibility-assertion vs visual. A request about layout, spacing,
colour, dark mode, or "does it look right" → the visual-regression row.

### 4. Executor — host vs VM (committed macOS only)

Read `.gstack/e2e-executor`: `host` or `vm`, and the file's absence means `host`. Only
those two strings are valid — `VM`, a trailing space or an empty file is
`BLOCKED — invalid .gstack/e2e-executor`, never a silent `host`. A malformed pin that
quietly runs on the host is the failure the marker exists to prevent, because the run
still looks fine.

This axis applies **only to committed macOS runs**. Exploratory/MCP-live and
visual-regression always run on the host — a live MCP session and a screenshot diff both
need the user's own screen — so do not read the file for those rows.

You are a **reader** of this pin, never its writer. `/superpowers-gstack:adapt` and
`/superpowers-gstack:setup-routing` ask the question and write the file; this skill
changes no files at all.

**Absent rig and failing rig are different, and get opposite answers.** You only decide
the first; the runner handles the second:

- **Rig absent** (`command -v vm-e2e` finds nothing) while the pin says `vm` → still
  route to the run, and name it: `executor=vm→host-fallback`, with the line
  `executor=vm requested, rig not found on this host — running on host without lease`.
  A committed `vm` pin must not brick the repo on every Mac without the rig.
- **Exception — non-interactive session** with pin `vm` and no rig → **refuse**. The
  fallback above is only safe because a human reads the warning; nobody does here, and an
  unleased host run can collide with another.

  Be honest about what is detectable. `CI` and `GITHUB_ACTIONS` are visible from a Bash
  call and settle it. `--print`, a scheduled run and a subagent dispatch are **not** —
  this skill has no session-kind preamble, and a TTY check answers the wrong question
  because an agent's Bash tool pipes stdout even when a human is watching. So:

  ```bash
  [ -n "${CI:-}${GITHUB_ACTIONS:-}${E2E_NONINTERACTIVE:-}" ] && echo NONINTERACTIVE
  ```

  If you *know* the session is non-interactive from your own context — you were
  dispatched as a subagent, or the invocation is `--print` — set `E2E_NONINTERACTIVE=1`
  before invoking the runner and treat the refusal as in force. When neither the
  environment nor your context says so, treat the session as interactive and let the
  fallback run. Guessing "probably automated" from a pipe would refuse the ordinary case.
- **Rig present but the run fails** → not your call. The runner fails loudly with the
  cause and does not fall back; a rig fault is exactly what you want surfaced, and a host
  run instead would turn a real defect into a silently slower pass.

## Routing table (the oracle)

The macOS committed row has **four** entry points, in priority order. Pick the first that
applies and name it as the next action.

**Entry points 1–3 all require a macOS UI-test target to exist:**

```bash
find . -maxdepth 2 -type d -name '*UITests' ! -name '*iOSUITests' | head -1
```

Two separate reasons, and both matter. The pin is written at onboarding, before any suite
necessarily exists, so a `vm` pin alone must never route a project with no tests at the
rig. And `scripts/run-uitests.sh` is a **shared path**: `/ios-e2e-scaffold` generates one
at the same location, so in a multiplatform project scaffolded for iOS first, an
unguarded entry point 1 would answer a committed *macOS* request by running the *iOS*
suite — and never reach the macOS scaffold. If the only `*UITests` directory is the iOS
one, this check finds nothing and routing falls through to entry point 4, which is
correct: the macOS suite does not exist yet.

1. `./scripts/run-uitests.sh` exists → run it. It reads `.gstack/e2e-executor` itself and
   dispatches to the VM or the host, so this one entry point covers both executors.
2. Else UI-test target exists **and** pin is `vm` **and** `vm-e2e` is on `PATH` → call
   `vm-e2e` directly. This is the path for a suite that predates the scaffold runner.
3. Else UI-test target exists → run it on the host:
   `xcodebuild test -scheme <Scheme> -destination 'platform=macOS' -only-testing:<Target>`.
   Covers a legacy or hand-made suite with a `host` pin and no runner script — without
   this the project matches no entry point at all.
4. Else no UI-test target → `/macos-e2e-scaffold` to create one.

**A project that is already scaffolded routes to entry point 1, 2 or 3 — never to
MCP-live.** Read literally, `/macos-e2e-scaffold`'s refuse-condition 3 ("a UI-test target
already exists") would bounce a regression request to exploratory live testing, which
answers a different question entirely. The scaffold refusing means *the suite is already
there* — run it. Anywhere below that still lists "a UI-test target already exists" as a
reason to fall back to MCP-live is superseded by this rule for committed intent.

**Set `E2E_NONINTERACTIVE=1` when you invoke entry point 1 from a non-interactive
session** (`--print`, a scheduled run, a subagent). The runner refuses the missing-rig
host fallback when it sees that, and it cannot detect the session kind itself: an agent's
Bash tool always pipes stdout, so a TTY check would refuse every interactive run too.
You know the session kind; the script does not.

| Intent | Platform | Executor |
|---|---|---|
| Committed regression | macOS | `./scripts/run-uitests.sh` → else `vm-e2e` (target exists + pin `vm`) → else `xcodebuild test -only-testing:<Target>` on the host (target exists) → else `/macos-e2e-scaffold`. Honours `.gstack/e2e-executor`. |
| Committed regression | iOS | `/ios-e2e-scaffold` |
| Exploratory / live | macOS | `XcodeBuildMCP` UI-automation (`snapshot_ui` → tap → screenshot) |
| Exploratory / live | iOS | `ios-simulator` MCP (`ui_find_element` / `ui_tap`) or `/ios-qa` |
| Visual regression | iOS | screenshot/vision diff + `/ios-design-review` |
| Visual regression | macOS | screenshot/vision diff + `/design-review` (generic designer's-eye QA — no macOS-specific reviewer exists) |
| Visual exploration (Tier-2 escalation) | iOS/iPadOS | `/superpowers-gstack:ios-visual-explore` — Gemini computer-use drives the app visually. Route here when the accessibility tree is insufficient (visual landmarks, layout regressions XCUITest can't assert, open-ended "find visual issues" missions). Not a first resort; paid Gemini API per run. |

## Fallback

Degrade to the MCP-live row for the platform **only when the chosen scaffold's Phase 0
actually refuses** — i.e. one of the scaffold's three refuse-conditions fires:

1. not a Swift project, or
2. no SwiftUI app for the routed platform detected — no SwiftUI scene (e.g. a
   UIKit-/AppKit-only app) or no platform-discriminating signal (e.g. a pure-iOS app
   routed to /macos-e2e-scaffold, or vice versa).

Emit an explicit note naming the unmet precondition. No false promise; always a way
forward.

**Refuse-condition 3 — "a UI-test target already exists" — is NOT a fallback trigger for
committed intent.** It used to be listed here, and that was the bug: for a committed
regression request the scaffold refusing means *the suite is already there*, so the
answer is to run it (entry point 1, 2 or 3 above), not to switch to exploratory live
testing, which answers a different question. A legacy suite with a `host` pin and no
runner script is exactly the case that would otherwise fall through every branch and end
up in MCP-live having never run the regression it was asked for. It remains a fallback
trigger for **exploratory** intent, where live testing is what was wanted anyway.

**SPM-only is NOT a fallback trigger.** The scaffold skills accept `Package.swift`
projects and proceed — they generate files under `Tests/<TARGET_DIR>/` (`<App>UITests`,
platform-suffixed on multiplatform targets) with a "SwiftPM can't host a UI-test
bundle; add an .xcodeproj" warning. So for SPM-only iOS/macOS apps
the dispatcher still routes to the scaffold skill; it does NOT degrade to MCP-live.

## Output — routing-decision block

Emit **one block per resolved platform** — normally exactly one; **two when the
multiplatform tiebreak resolved to `both`** (one iOS block + one macOS block) — then
stop. Do not build/tap/assert; hand control back after emitting.

```
## /e2e-route decision
Detected: platform=<iOS|macOS>, intent=<committed|exploratory|visual>, source=<scheme|.gstack/track|asked>
executor=<host|vm|vm→host-fallback>
Chosen executor: <skill or MCP sequence>
Why: <one line tying context → routing cell>
Next action: <exact /skill to invoke OR exact MCP call sequence>
```

`executor=` is present on every block. For committed macOS it carries the resolved pin;
for iOS, exploratory and visual rows it is always `host`, because those never read the
axis. `vm→host-fallback` means the pin said `vm` and the rig was not on this machine —
print the fallback line with it, so the reason is visible and not merely implied.

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

## Simulator readiness ladder (MCP-live only)

When the routed executor is **MCP-live** (`ios-simulator` / `XcodeBuildMCP` / raw
`idb`+`simctl`), readiness is not a single boolean. "Booted" exists at three levels that
lag each other unpredictably — sometimes by **minutes** on a cold iOS 26 boot:

| Level | Signal | Reality |
|---|---|---|
| 1 | `xcrun simctl list devices booted` shows `Booted` | CoreSimulator state — earliest, a diagnostic not a gate |
| 2 | `xcrun simctl bootstatus <udid> -b` returns | launchd/system services — neither sufficient nor necessary for automation; a diagnostic not a gate |
| 3 | `describe-all` / `snapshot_ui` returns a non-degenerate tree | SpringBoard rendered, AX bridge live — **the only readiness gate** |

These are **not a clean monotonic ladder.** In the 2026-06-27 incident `bootstatus -b`
(level 2) was *still blocking* after the UI (level 3) was already up. Treat level 3 as the
only readiness gate; levels 1–2 are diagnostics you read, never conditions you wait on.

**Rules — these prevent stranded passive waits:**

1. **Poll the precondition you actually need (level 3), not a proxy.** A device that
   reports `Booted` can still show a black screen with an empty AX tree. Gate the first
   probe on a non-degenerate tree, not on `Booted`.
2. **Never block on `bootstatus -b` as your wakeup signal.** It can block far longer than
   the device takes to become usable — or indefinitely, if its boot-completion condition
   is never met — so it always needs an external timeout. Instead run a bounded
   `run_in_background` until-loop that *exits* the moment the level-3 precondition is true
   (one notification, within seconds):
   ```bash
   # Ready ≠ "Booted". A cold-boot AX tree can contain elements whose frames are
   # all null/0 (degenerate) — so gate on REAL geometry, not just on nodes existing.
   # REPLACE the ready() body with a check against YOUR tool's actual output (an
   # element with a NON-ZERO frame width — a label alone does not prove geometry).
   # Confirm field names once against a real dump. Note: idb roles are bare ("Button",
   # "Application"), NOT AX-prefixed — do not grep for "AXButton". Until you replace it,
   # ready() fails loudly, so the loop can never falsely report success.
   ready() {
     echo "readiness predicate not implemented — replace ready()" >&2
     return 1
   }
   start=$SECONDS
   until ready; do
     if [ $((SECONDS - start)) -gt 120 ]; then
       echo "TIMEOUT: AX tree still degenerate" >&2
       exit 1   # fail loudly — a wrapping background task must NOT notify "ready"
     fi
     sleep 1
   done
   ```
3. **Always pair "I'll be notified when the task finishes" with a fallback wakeup.** The
   harness re-invokes on task *completion*; a hung task strands you forever. Set a
   `ScheduleWakeup` fallback (or a bounded `Monitor` timeout) so a hang can't cost 10
   idle minutes. If your only plan is "I'll be notified automatically," you have no plan
   for the notification not arriving.
4. **Never emit a bare "waiting."** Either you are actively polling (a background
   until-loop that exits) or you hand control back. Idle-waiting on an opaque blocking
   command is the anti-pattern that wasted real time on a Fase-2 iPad spike (2026-06-27).

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
