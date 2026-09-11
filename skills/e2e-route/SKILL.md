---
name: e2e-route
description: Pure dispatcher for Swift E2E tests. Reads platform, intent and executor pin, names the executor and the next action, then hands off.
---

# e2e-route

A pure dispatcher for Swift E2E testing, invoked with `/superpowers-gstack:e2e-route`. It
reads three inputs — platform, intent and executor pin — picks a row in the routing table,
emits one decision block and hands off. It builds, taps, asserts and writes nothing.

## Phase 0 — Self-check

| Check | Detect via | If it fails |
|---|---|---|
| Swift project | `*.xcodeproj` or `Package.swift` in cwd | Refuse: "Not a Swift project — nothing to route." |
| Discoverable scheme | `mcp__XcodeBuildMCP__list_schemes` or `xcodebuild -list` | Ask once which scheme; else refuse "No scheme detected — cannot route." |

## Inputs

### 1. Platform — iOS vs macOS

Read `SUPPORTED_PLATFORMS` / `SDKROOT` via `mcp__XcodeBuildMCP__show_build_settings`; if
MCP is unavailable, `grep -E 'SDKROOT|SUPPORTED_PLATFORMS' *.xcodeproj/project.pbxproj`,
else read `.gstack/track`. Ask only if undetectable.

If the target supports both (`iphoneos` and `macosx` both listed, `.gstack/track` = `both`,
or one scheme per platform) the platform is not determined. Resolve in order: (a) the
request names a platform → use it; (b) else ask once: "This app targets both iOS and
macOS — route to iOS, macOS, or both?"; (c) `both` → emit two decision blocks, iOS then
macOS, run sequentially. The scaffold keeps the suites apart with platform-suffixed
targets (`<App>iOSUITests`, `<App>macOSUITests`); each block's next action names its own.

### 2. Intent — committed vs exploratory vs visual

- **CI forces committed.** `[ -n "${CI:-}${GITHUB_ACTIONS:-}" ] && echo CI` — a CI job
  cannot drive a live simulator session.
- Else infer from the verbs: `utforsk` / `sjekk` / `dogfood` / `trykk gjennom` / `explore`
  / `smoke` → **exploratory**; `må aldri knekke` / `regresjon` / `regression` / `CI` /
  "lock this down" → **committed**; layout, spacing, colour, dark mode, "does it look
  right" → **visual**.
- Ambiguous → ask once: "Exploratory live run, committed regression test, or visual review?"

### 3. Executor pin — host vs vm (committed macOS only)

Read `.gstack/e2e-executor`. `host` and `vm` are the only valid values; absence means
`host`. Anything else (`VM`, a trailing space, an empty file) is
`BLOCKED — invalid .gstack/e2e-executor`, never a silent `host`: a malformed pin that
quietly runs on the host is exactly the failure the marker exists to catch.

Only committed macOS runs read the pin. iOS, exploratory and visual rows always run on
the host — a live session and a screenshot diff both need the user's own screen.

This skill is a **reader** of the pin, never its writer. `/superpowers-gstack:adapt` and
`/superpowers-gstack:setup-routing` ask the question and write the file.

Absent rig and failing rig are different and get opposite answers:

- **Rig absent** (`command -v vm-e2e` finds nothing) with pin `vm` → still route, name it
  `executor=vm→host-fallback` and print
  `executor=vm requested, rig not found on this host — running on host without lease`.
  In a non-interactive session (`CI`, `GITHUB_ACTIONS` or `E2E_NONINTERACTIVE` set, or you
  know you are a subagent / `--print`) refuse instead — nobody reads the warning there.
  When you know that from your own context, set `E2E_NONINTERACTIVE=1` before invoking the
  runner; it cannot detect the session kind itself.
- **Rig present but the run fails** → not your call. `vm-e2e` fails loudly with the cause
  and never falls back; a host run would turn a rig defect into a silently slower pass.

## Routing table

| Intent | Platform | Executor |
|---|---|---|
| Committed regression | macOS | Entry points 1–4 below, in order. Honours `.gstack/e2e-executor`. |
| Committed regression | iOS | `./scripts/run-uitests.sh` if it targets the iOS suite, else `/superpowers-gstack:e2e-scaffold` (target `<App>iOSUITests`) |
| Exploratory / live | macOS | XcodeBuildMCP UI automation: `snapshot_ui` → tap → `screenshot` |
| Exploratory / live | iOS | `ios-simulator` MCP (`ui_find_element` / `ui_tap`) or `/ios-qa` |
| Visual exploration | iOS / macOS | XcodeBuildMCP `screenshot` / `snapshot_ui`, driven by the session model |
| Visual regression | iOS | screenshot diff + `/ios-design-review` |
| Visual regression | macOS | screenshot diff + `/design-review` (no macOS-specific reviewer exists) |

**Committed macOS entry points.** Entries 1–3 require a macOS UI-test target —
`find . -maxdepth 2 -type d -name '*UITests' ! -name '*iOSUITests' | head -1` — because the
pin is written at onboarding, before any suite exists, and a `vm` pin alone must never send
a test-less project to the rig. If the only suite is the iOS one, this falls through to 4.

1. `./scripts/run-uitests.sh` exists **and reads the pin** — check with
   `grep -qE '\.gstack/e2e-executor' scripts/run-uitests.sh` → run it. The scaffold's
   template reads the pin itself and dispatches to the VM or the host, so this one entry
   point covers both. A runner without that line is a LEGACY runner written before the
   pin existed: it would run `executor=vm` on the host and say nothing. With pin `host`
   run it anyway; with pin `vm` do not run it — say
   `LEGACY runner (pre-pin) — re-run /superpowers-gstack:e2e-scaffold to regenerate
   scripts/run-uitests.sh`, then fall through to entry point 2. The grep is a heuristic
   over text, not proof (a comment naming the path would pass it); it separates the two
   shapes that actually exist.
2. Else target exists, pin is `vm` and `vm-e2e` is on `PATH` → call `vm-e2e` directly.
3. Else target exists → run on the host:
   `xcodebuild test -scheme <Scheme> -destination 'platform=macOS' -only-testing:<Target>`.
4. Else → `/superpowers-gstack:e2e-scaffold` (target `<App>macOSUITests`).

A project that already has a suite routes to 1–3, never to exploratory. The scaffold
refusing because "a UI-test target already exists" means the suite is there — run it.

## Fallback

Degrade to the exploratory row only when the scaffold's own Phase 0 refuses: not a Swift
project, or no SwiftUI app for the routed platform (UIKit/AppKit-only, or a pure-iOS app
routed to macOS). Name the unmet precondition. SPM-only is **not** a fallback trigger —
the scaffold accepts `Package.swift` and writes under `Tests/<Target>/` with a warning.

**Waiting.** If the executor needs a simulator, gate on a non-degenerate `snapshot_ui` /
`describe-all` tree, not on `simctl` reporting `Booted`. Wait with the Monitor tool or a
bounded poll, never an open-ended "waiting".

## Output — decision block

One block per resolved platform, then stop. Do not build, tap or assert; hand control back.

```
## /e2e-route decision
Detected: platform=<iOS|macOS>, intent=<committed|exploratory|visual>, source=<scheme|.gstack/track|asked>
executor=<host|vm|vm→host-fallback>
Chosen executor: <skill or MCP sequence>
Why: <one line tying context → routing cell>
Next action: <exact /skill to invoke OR exact MCP call sequence>
```

`executor=` is on every block: the resolved pin for committed macOS, `host` for every
other row; `vm→host-fallback` prints its fallback line alongside it.

## What this skill is not

Not an executor, not a scaffolder, not a QA-report writer (`/ios-qa`, `/qa`), and not
auto-hooked — manual invocation and CLAUDE.md routing only, so it never hijacks `/qa`.
Both executors find controls via the same `<ViewName>_<ControlType>_<Purpose>`
accessibility-identifier convention, owned by `/superpowers-gstack:e2e-scaffold` — lookup
is identical for `ui_find_element(...)` and `app.buttons[...]`, which keeps routing thin.
