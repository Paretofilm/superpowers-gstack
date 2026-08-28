## Native Apple development tools (Xcode workflow) <!-- gstack-xcode-tools-v6 -->

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

`/superpowers-gstack:verify-and-land` performs exactly this sequence and then offers
the landing; reach for it rather than re-deriving the steps.

### Project file management (prefer declarative)

Never hand-edit the auto-generated XML in `.xcodeproj/project.pbxproj`. Default to **XcodeGen** (`brew install xcodegen` — committable `project.yml`, re-runnable `xcodegen generate`); use **Tuist** only when XcodeGen isn't sufficient (multi-target, complex schemes, generated frameworks).

### Capabilities, signing, and provisioning

Three surfaces, three different handlers:

| Surface | What | Who handles it |
|---|---|---|
| `*.entitlements` file | Declares which capabilities (CloudKit, push, app groups, keychain sharing, etc.) the app uses | **Agent** — edit declaratively as XML |
| `project.yml` (XcodeGen) or `*.xcodeproj` build settings | `DEVELOPMENT_TEAM`, code signing identity, target capabilities | **Agent** — edit declaratively |
| Apple Developer Portal (developer.apple.com) | Registers container IDs (CloudKit), App IDs, provisioning profiles, push certificates | **User** — Apple ID login + 2FA required; agent cannot access |

**Default signing for macOS apps — never ad-hoc.** Every new XcodeGen `project.yml` with a **macOS** app target MUST declare, in the macOS target's `settings.base` (project-level only when macOS is the sole platform): `CODE_SIGN_STYLE: Manual`, `DEVELOPMENT_TEAM: {{DEVELOPMENT_TEAM}}`, `CODE_SIGN_IDENTITY: "Developer ID Application"`. Do NOT put `Developer ID Application` in a shared multiplatform `settings.base` — it leaks to the iOS target and breaks it. NEVER emit `CODE_SIGN_IDENTITY: "-"` with `CODE_SIGNING_REQUIRED: NO` — ad-hoc signing changes the app's cdhash on every rebuild, so macOS re-prompts every TCC permission (Desktop/Documents/Downloads) forever. `Developer ID Application` (manual) needs no provisioning profile or portal round-trip, yet yields a stable designated requirement, so granted TCC permissions survive rebuilds; automatic `Apple Development` signing does NOT work headlessly on macOS (portal registration needs Apple ID + 2FA and `xcodebuild` fails with "No signing certificate found"). **iOS is different:** iOS apps cannot use Developer ID — keep `Apple Development` + a provisioning profile (the ad-hoc/TCC issue doesn't apply to simulator apps). Verify a macOS build: `codesign -dvvv <app> 2>&1 | grep -E "Signature=|TeamIdentifier"` — `Signature=adhoc` or `TeamIdentifier=not set` means it is still broken.

**Capability workflow (e.g. CloudKit):** (1) agent declares the capability + container in `*.entitlements` (declarative XML); (2) agent ensures `DEVELOPMENT_TEAM` is set in `project.yml`; (3) agent runs `xcodegen generate` + `xcodebuild build`; (4) if signing fails with "container not registered" / "no matching provisioning profile" — STOP and hand the user the exact portal steps (developer.apple.com/account → Identifiers → App ID → enable the capability → link the container; ~30 sec), then retry the build after their click. The portal requires Apple ID + 2FA that no MCP/CLI tool automates — the declarative entitlements + `project.yml` path is the only one that works for both the agent and git history. For CI/CD with many apps or frequent provisioning, **Fastlane match** + spaceship is the standard automation surface — out of scope for solo workflows; mention it only if the user scales beyond one or two apps.

### Anti-patterns (NEVER do these)

- ❌ "Open Xcode and run the tests" — use `mcp__XcodeBuildMCP__test_sim` (MCP) or `xcodebuild test` (CLI) instead
- ❌ "Build the app in Xcode to verify" — use `mcp__XcodeBuildMCP__build_sim` (MCP) or `xcodebuild build` (CLI) instead
- ❌ "Open the app and check" (macOS) — that opens `/Applications`, not this branch. Build, then `open` the absolute `BUILT_PRODUCTS_DIR` path
- ❌ "Take a screenshot of the simulator" — use `mcp__XcodeBuildMCP__screenshot` (MCP) or `xcrun simctl io booted screenshot` (CLI) instead
- ❌ "Click through the Signing & Capabilities pane in Xcode" — declare entitlements in `*.entitlements` + `project.yml` (XcodeGen) instead
- ❌ "Check what the system color looks like in HIG" — use `mcp__apple-docs__search_apple_docs` or `mcp__swiftui-rag__search_swiftui_corpus` instead

If a verification step requires the Xcode UI, you have not finished the task — verify via MCP or CLI tools, then report results.
