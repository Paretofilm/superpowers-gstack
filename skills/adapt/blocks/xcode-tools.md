## Native Apple development tools (Xcode workflow) <!-- gstack-xcode-tools-v11 -->

Xcode-related operations MUST be performed by the agent — NEVER delegated to the user; the user should never need to open Xcode to verify your work. Prefer MCP tools, falling back to CLI otherwise. Check MCP availability via `ToolSearch` first (deferred tools load on demand); drop to CLI only if the search returns nothing.

### Tool routing for Apple-platform operations

| Operation | Preferred (MCP) | Fallback (CLI, always available with Xcode) |
|---|---|---|
| Type-check Swift code | `mcp__swiftui-rag__swift_typecheck` | `xcrun swift -typecheck <file>.swift` |
| Search SwiftUI corpus / HIG | `mcp__swiftui-rag__search_swiftui_corpus` | (no CLI fallback — use `mcp__apple-docs__search_apple_docs`) |
| HIG conformance review | `mcp__swiftui-rag__review_macos_hig`, `review_accessibility`, `review_liquid_glass` | (no CLI fallback — read HIG via `mcp__apple-docs__get_apple_doc_content` and apply rules manually) |
| Build Xcode project for simulator | `mcp__XcodeBuildMCP__build_sim` | `xcodebuild -scheme <name> -destination 'platform=iOS Simulator,name={{IOS_SIMULATOR}}' build` |
| Build + launch in simulator | `mcp__XcodeBuildMCP__build_run_sim` | `xcodebuild ... build && xcrun simctl launch booted <bundle-id>` |
| Run XCTest / Swift Testing | `mcp__XcodeBuildMCP__test_sim` | `xcodebuild test -scheme <name> -destination 'platform=iOS Simulator,name={{IOS_SIMULATOR}}'` |
| List / boot simulators | `mcp__XcodeBuildMCP__list_sims`, `boot_sim` | `xcrun simctl list devices`, `xcrun simctl boot <udid>` |
| Capture simulator logs | `mcp__XcodeBuildMCP__launch_app_logs_sim` | `xcrun simctl spawn booted log stream --predicate '...'` |
| UI automation in simulator | `mcp__XcodeBuildMCP__ui_tap`, `screenshot`, `snapshot_ui`, `ui_describe_all` | `xcrun simctl io booted screenshot <path>.png` (screenshots only; tap/snapshot are MCP-only) |
| **Build a macOS app** | (XcodeBuildMCP's macOS workflow is off by default) | `xcodebuild -scheme <name> -configuration Debug -destination 'platform=macOS' build` |
| **Resolve the built product path** | — | `xcodebuild -showBuildSettings -scheme <name> -configuration Debug \| grep -E '^ +(BUILT_PRODUCTS_DIR\|FULL_PRODUCT_NAME\|PRODUCT_BUNDLE_IDENTIFIER) '` |
| **Launch the macOS app you just built** | — | quit the running instance, then `open "$BUILT_PRODUCTS_DIR/$FULL_PRODUCT_NAME"` |
| **Prove which bundle is running** | — | `ps -o comm= -p "$(pgrep -n <exec-name>)"` — prints the full executable path |
| Apple platform docs (HIG, APIs) | `mcp__apple-docs__search_apple_docs`, `get_apple_doc_content` | `man` pages for CLI tools; online docs at developer.apple.com |
| WWDC video search / examples | `mcp__apple-docs__search_wwdc_content`, `get_wwdc_code_examples` | (no CLI fallback — fetch via `WebFetch` against developer.apple.com/wwdc) |

Simulator models come and go with Xcode releases. If `xcodebuild` answers "Unable to
find a device matching the provided destination specifier", the destination name is
stale, not the project — run `xcrun simctl list devices available` and use a model
from that list.

### Verifying a macOS app by eye — never against an installed copy

macOS has no simulator, so "run it and look" means launching a real bundle — and the
machine usually holds more than one. Spotlight, the Dock, Launchpad and `open -a
<Name>` all resolve to the copy in `/Applications`, which is whatever was last
released. A `DerivedData` product may be from a different branch. Neither rebuilds
when you switch branches, because nothing ever does.

So a fix can be correct, committed, and completely absent from the app the user
opens — and the natural conclusion is that the fix failed. Verify by **construction,
not inspection**:

1. Build the branch that is checked out.
2. Quit any running instance — otherwise macOS activates the one already up.
3. `open` the **absolute path** under `BUILT_PRODUCTS_DIR`. Never by app name.
4. Confirm with `ps -o comm=` that the running executable is inside that directory.
5. Say which branch and commit is on screen before asking whether the fix is there.

`/superpowers-gstack:verify-and-land` performs exactly this sequence and then lands it
by the project's `Landing mode:` line; reach for it rather than re-deriving the steps.

### SwiftUI view changes — look up, lint, see, then say what you saw

A control can compile, pass every linter and still be unusable: a pop-up button with
`.menuIndicator(.hidden)` and a plain label looks like static text. This applies
whenever you add or change a `View` in the app target, not only in a design-system package.

1. **Look up before writing.** One `mcp__swiftui-rag__search_swiftui_corpus` query for the
   *kind of control* ("pop-up button in a table row"), not for a SwiftUI symbol. Note the one
   thing it decided. If nothing relevant comes back, say so; never cite a source you did not get.
2. **Lint after writing.** `review_macos_hig` (macOS or both; skip it on iOS, where its
   window and menu-bar findings mislead), `review_accessibility`, and `review_liquid_glass`
   when the project targets Liquid Glass, on each changed view file. They are pattern
   checks: "clean" means no known pattern matched, not that the control looks right.
3. **Affordance check.** Every interactive element shows, without hovering, that it is
   interactive: an indicator on pop-ups and pull-downs, an outline or fill on fields, a
   standard shape on buttons. If a cue is hidden on purpose, say why.
4. **See it.** On macOS, render the view with `live-swiftui` (`render`, then `screenshot`; it
   needs a `#Preview`) or launch the built app by absolute path (previous section) and
   screenshot it. On iOS, run it in the simulator and use `mcp__XcodeBuildMCP__screenshot`.
   For a list or table, at least one row per state: normal, empty, longest label.
5. **Report what you saw.** In the final message, say per changed view either *rendered and
   seen* or *built, appearance unverified* and why. "Follows the HIG" and "matches the system
   control" need a source from step 1; without one, word it as a choice. A size or opacity you
   did not look up is a choice, not conformance.

### E2E executor — where committed UI tests run

This project's committed macOS UI tests run on: **{{E2E_EXECUTOR}}**.

The value lives in `.gstack/e2e-executor` (`host` or `vm`; the file's absence means
`host`). It is a committed pin, like `.gstack/track` — a project-level decision, not a
per-developer one — so a teammate cloning the repo gets the same behaviour.

`vm` means committed UI tests are dispatched to a macOS VM rig via `vm-e2e`, which owns
the lease, boot, transfer, resigning and run. The point is isolation: a UI test that
takes over the screen cannot fight the user for focus, two runs cannot collide on one
machine, and an unattended run does not depend on anyone being logged in. Nothing in
this file needs to know how the rig works — only that `vm-e2e` is on `PATH` and speaks
JSON.

**An explicit request from the user overrides the pin.** The pin routes *committed* UI
tests, and it exists so an unattended suite does not grab the keyboard while someone is
working — not to put the user's own machine off limits. When the user asks for a run on
their machine, do it: the app may not be installed in the guest, may not be installable
there, or may need their logins, licences or documents, none of which a fresh guest has.
Say in one line what you are about to drive and roughly how long it will take, so they
can leave the keyboard and mouse alone — that is a heads-up, not a request for
permission, and you do not wait for an answer — then say when you are done. Two caveats
survive, because they are technical rather than policy: a screenshot taken on the host
captures a screen region and can catch the wrong display, and two UI-test runs can never
share one macOS instance.

**Reading the marker.** Only the exact strings `host` and `vm` are valid. Anything else
— `VM`, a trailing space, an empty file, a stray comment — is an invalid pin, not a
silent `host`: refuse with `BLOCKED — invalid .gstack/e2e-executor`, the same shape as
the `.gstack/track` check. A typo that quietly runs on the host is precisely the
failure this marker exists to prevent, because the run still looks fine.

**When the rig is absent vs. when it fails — opposite answers.** Both matter, and
conflating them is the trap:

| Situation | Detect | Response |
|---|---|---|
| Marker is `vm`, `command -v vm-e2e` finds nothing | rig not installed on this machine | **Run on the host**, printing `executor=vm requested, rig not found on this host — running on host without lease`. Never silently. A committed `vm` marker must not brick the repo on every Mac without the rig. |
| Marker is `vm`, rig present, run fails to produce a result | no parseable JSON on stdout, or an `error` field | **Fail loudly, naming the cause.** Do NOT fall back to the host. A rig fault is the thing you want to find out about; running on the host instead turns a real defect into a silently slower run. |
| Non-interactive session (`CI`, `--print`, scheduled), marker `vm`, rig absent | nobody reads a warning | **Fail.** The fallback above depends on a human seeing the line. |

**Reading the result.** Host and VM emit the same JSON shape, so the caller does not
branch on executor:

```json
{"total": 16, "passed": 7, "failed": 0, "skipped": 9, "executed": 7,
 "executor": "vm", "xcresult": "/path/on/host.xcresult"}
```

Always state `skipped` in plain text. "Green and empty" — every test skipped, nothing
run, exit 0 — is the most dangerous result this pipeline can produce, because it reads
as success. `executed` (`total − skipped`) is the number that says whether anything
actually happened; treat `executed == 0` as a failure regardless of exit code. If the
rig omits `executed`, derive it rather than dropping the check.

### Project file management (prefer declarative)

Never hand-edit the auto-generated XML in `.xcodeproj/project.pbxproj`. Default to **XcodeGen** (`brew install xcodegen` — committable `project.yml`, re-runnable `xcodegen generate`); use **Tuist** only when XcodeGen isn't sufficient (multi-target, complex schemes, generated frameworks).

### Capabilities, signing, and provisioning

Three surfaces, three different handlers:

| Surface | What | Who handles it |
|---|---|---|
| `entitlements.properties` under the target in `project.yml` (XcodeGen) | Declares which capabilities (CloudKit, push, app groups, keychain sharing, etc.) the app uses. XcodeGen writes the file at `entitlements.path` from it on every `xcodegen generate` | **Agent** — edit here; that `*.entitlements` file is generated output and is never edited by hand |
| `*.entitlements` file (no XcodeGen, or an `entitlements:` with no `properties:`) | The same declarations, with the file itself as the source | **Agent** — edit declaratively as XML |
| `project.yml` (XcodeGen) or `*.xcodeproj` build settings | `DEVELOPMENT_TEAM`, code signing identity, target capabilities | **Agent** — edit declaratively |
| Apple Developer Portal (developer.apple.com) | Registers container IDs (CloudKit), App IDs, provisioning profiles, push certificates | **User** — Apple ID login + 2FA required; agent cannot access |

**Which one is the source:** `grep -n -A6 'entitlements:' project.yml`, then read that target's whole `entitlements:` mapping (comments can push keys past the shown lines). A `properties:` key in it means the file is generated: a hand edit to `*.entitlements` is overwritten by the next `xcodegen generate`, and the missing capability fails only at run time, not at build time.

**Default signing for macOS apps — never ad-hoc.** When you create a new XcodeGen `project.yml` with a **macOS** app target, it MUST declare, in the macOS target's `settings.base` (project-level only when macOS is the sole platform): `CODE_SIGN_STYLE: Manual`, `DEVELOPMENT_TEAM: {{DEVELOPMENT_TEAM}}`, `CODE_SIGN_IDENTITY: "Developer ID Application"`. Do NOT put `Developer ID Application` in a shared multiplatform `settings.base` — it leaks to the iOS target and breaks it. NEVER emit `CODE_SIGN_IDENTITY: "-"` with `CODE_SIGNING_REQUIRED: NO` — ad-hoc signing changes the app's cdhash on every rebuild, so macOS re-prompts every TCC permission (Desktop/Documents/Downloads) forever. `Developer ID Application` (manual) needs no provisioning profile or portal round-trip while the app uses no restricted entitlement, yet yields a stable designated requirement, so granted TCC permissions survive rebuilds. Automatic `Apple Development` signing works headlessly on macOS when the team's Apple ID is already added in Xcode's Accounts pane and every `xcodebuild` passes `-allowProvisioningUpdates`: Xcode then creates the App ID, certificate and profile itself. Without both — a new app on a Mac where no account is signed in, say — it fails with "No signing certificate found". A project that already builds and tests that way (`CODE_SIGN_STYLE: Automatic` plus the flag in its build and pre-merge commands) is working: leave it as it is. The rule above is for new projects, not a reason to migrate one. A restricted entitlement needs a provisioning profile under either style, Developer ID included (Apple TN3125: only App Sandbox, Hardened Runtime, `application-groups` and `get-task-allow` are unrestricted, so iCloud/CloudKit and push are restricted). Under automatic signing `-allowProvisioningUpdates` creates that profile; under manual signing it only downloads one that already exists in the portal (`man xcodebuild`). **iOS is different:** iOS apps cannot use Developer ID — keep `Apple Development` + a provisioning profile (the ad-hoc/TCC issue doesn't apply to simulator apps). Verify a macOS build: `codesign -dvvv <app> 2>&1 | grep -E "Signature=|TeamIdentifier"` — `Signature=adhoc` or `TeamIdentifier=not set` means it is still broken.

**Capability workflow (e.g. CloudKit):** (1) agent declares the capability + container in the entitlements source — `entitlements.properties` in `project.yml` when XcodeGen generates the file, `*.entitlements` otherwise. iCloud takes separate keys, each its own entry: `com.apple.developer.icloud-services` (the services, e.g. `CloudKit`, `CloudDocuments`), `com.apple.developer.icloud-container-identifiers` (the containers CloudKit uses) and, for iCloud Drive documents, `com.apple.developer.ubiquity-container-identifiers` (the same container named again). A service without its container list builds and then fails at run time; (2) agent ensures `DEVELOPMENT_TEAM` is set in `project.yml`; (3) agent runs `xcodegen generate` + `xcodebuild build`; (4) if signing fails with "container not registered" / "no matching provisioning profile" — do not stop yet: rebuild with `-allowProvisioningUpdates`, adding `-allowProvisioningDeviceRegistration` when the destination is a device not yet registered. For an automatically signed target whose team account is signed in to Xcode, this registers the App ID, adds the capability and creates the profile in seconds; for a manually signed target it only downloads profiles that already exist. Only if the flag also fails, STOP and hand the user the exact portal steps (developer.apple.com/account → Identifiers → App ID → enable the capability → link the container; ~30 sec), then retry the build once after their click — never loop on a failing signing build. Signing in to the portal, or adding an account to Xcode, needs Apple ID + 2FA that no MCP/CLI tool automates; what an account already signed in to Xcode can do, `xcodebuild` can do for you. The declarative entitlements + `project.yml` path is the only one that works for both the agent and git history. For CI/CD with many apps or frequent provisioning, **Fastlane match** + spaceship is the standard automation surface — out of scope for solo workflows; mention it only if the user scales beyond one or two apps.

### Anti-patterns (NEVER do these)

- ❌ "Open Xcode and run the tests" — use `mcp__XcodeBuildMCP__test_sim` (MCP) or `xcodebuild test` (CLI) instead
- ❌ "Build the app in Xcode to verify" — use `mcp__XcodeBuildMCP__build_sim` (MCP) or `xcodebuild build` (CLI) instead
- ❌ "Open the app and check" (macOS) — that opens `/Applications`, not this branch. Build, then `open` the absolute `BUILT_PRODUCTS_DIR` path
- ❌ "This follows the HIG" about a SwiftUI view you never rendered, or with no corpus or HIG page behind it
- ❌ "Take a screenshot of the simulator" — use `mcp__XcodeBuildMCP__screenshot` (MCP) or `xcrun simctl io booted screenshot` (CLI) instead
- ❌ "Click through the Signing & Capabilities pane in Xcode" — declare entitlements in `entitlements.properties` in `project.yml` (XcodeGen), or in `*.entitlements` when nothing generates it, instead
- ❌ Editing a `*.entitlements` file that XcodeGen generates — `xcodegen generate` writes it back; change `entitlements.properties` in `project.yml`
- ❌ "Check what the system color looks like in HIG" — use `mcp__apple-docs__search_apple_docs` or `mcp__swiftui-rag__search_swiftui_corpus` instead

If a verification step requires the Xcode UI, you have not finished the task — verify via MCP or CLI tools, then report results.
