## Native Apple development tools (Xcode workflow) <!-- gstack-xcode-tools-v4 -->

Xcode-related operations MUST be performed by the agent — NEVER delegated to the user. The user should never need to open Xcode to verify your work. Prefer MCP tools when available; fall back to CLI when not.

### Tool routing for Apple-platform operations

For each operation, **prefer the MCP tool when available**, falling back to CLI otherwise. Check MCP availability via `ToolSearch` first (these are deferred tools loaded on demand); only drop to CLI if the search returns nothing.

| Operation | Preferred (MCP) | Fallback (CLI, always available with Xcode) |
|---|---|---|
| Type-check Swift code | `mcp__swiftui-rag__swift_typecheck` | `xcrun swift -typecheck <file>.swift` |
| Search SwiftUI corpus / HIG | `mcp__swiftui-rag__search_swiftui_corpus` | (no CLI fallback — use `mcp__apple-docs__search_apple_docs`) |
| HIG conformance review | `mcp__swiftui-rag__review_macos_hig`, `review_accessibility`, `review_liquid_glass` | (no CLI fallback — read HIG via `mcp__apple-docs__get_apple_doc_content` and apply rules manually) |
| Build Xcode project for simulator | `mcp__XcodeBuildMCP__build_sim` | `xcodebuild -scheme <name> -destination 'platform=iOS Simulator,name=iPhone 16' build` |
| Build + launch in simulator | `mcp__XcodeBuildMCP__build_run_sim` | `xcodebuild ... build && xcrun simctl launch booted <bundle-id>` |
| Run XCTest / Swift Testing | `mcp__XcodeBuildMCP__test_sim` | `xcodebuild test -scheme <name> -destination 'platform=iOS Simulator,name=iPhone 16'` |
| List / boot simulators | `mcp__XcodeBuildMCP__list_sims`, `boot_sim` | `xcrun simctl list devices`, `xcrun simctl boot <udid>` |
| Capture simulator logs | `mcp__XcodeBuildMCP__launch_app_logs_sim` | `xcrun simctl spawn booted log stream --predicate '...'` |
| UI automation in simulator | `mcp__XcodeBuildMCP__ui_tap`, `screenshot`, `snapshot_ui`, `ui_describe_all` | `xcrun simctl io booted screenshot <path>.png` (screenshots only; tap/snapshot are MCP-only) |
| Apple platform docs (HIG, APIs) | `mcp__apple-docs__search_apple_docs`, `get_apple_doc_content` | `man` pages for CLI tools; online docs at developer.apple.com |
| WWDC video search / examples | `mcp__apple-docs__search_wwdc_content`, `get_wwdc_code_examples` | (no CLI fallback — fetch via `WebFetch` against developer.apple.com/wwdc) |

### Project file management (prefer declarative)

Avoid hand-editing the auto-generated XML in `.xcodeproj/project.pbxproj`. Two declarative alternatives:

- **XcodeGen** (`brew install xcodegen`) — generate `.xcodeproj` from a committable `project.yml`. Re-runnable via `xcodegen generate`. Strongly recommended for solo / small-team SwiftUI projects.
- **Tuist** — more powerful declarative project manager; heavier dependency. Use if XcodeGen isn't sufficient (multi-target, complex schemes, generated frameworks).

For new SwiftUI projects under this plugin, default to XcodeGen unless the project explicitly requires Tuist.

### Capabilities, signing, and provisioning

Three surfaces, three different handlers:

| Surface | What | Who handles it |
|---|---|---|
| `*.entitlements` file | Declares which capabilities (CloudKit, push, app groups, keychain sharing, etc.) the app uses | **Agent** — edit declaratively as XML |
| `project.yml` (XcodeGen) or `*.xcodeproj` build settings | `DEVELOPMENT_TEAM`, code signing identity, target capabilities | **Agent** — edit declaratively |
| Apple Developer Portal (developer.apple.com) | Registers container IDs (CloudKit), App IDs, provisioning profiles, push certificates | **User** — Apple ID login + 2FA required; agent cannot access |

**Default signing for macOS apps — never ad-hoc.** Every new XcodeGen `project.yml` with a **macOS** app target MUST declare stable signing for that target — put it in the **macOS target's** `settings.base` (or project-level `settings.base` only when macOS is the sole platform, e.g. a single-target app): `CODE_SIGN_STYLE: Manual`, `DEVELOPMENT_TEAM: {{DEVELOPMENT_TEAM}}`, `CODE_SIGN_IDENTITY: "Developer ID Application"`. In a multiplatform project do NOT put `Developer ID Application` in the shared project-level `settings.base` — it would leak to the iOS target and break it. NEVER emit `CODE_SIGN_IDENTITY: "-"` with `CODE_SIGNING_REQUIRED: NO` — that ad-hoc-signs the app, so its cdhash changes on every rebuild and macOS re-prompts for every TCC permission (Desktop / Documents / Downloads access) forever. `Developer ID Application` (manual) needs no provisioning profile and no Developer Portal round-trip, yet yields a stable *designated requirement* (Team ID + bundle ID), so a granted TCC permission survives rebuilds. Automatic signing with `Apple Development` does NOT work headlessly for macOS — it tries to register the Mac in the portal (Apple ID + 2FA, user territory) and `xcodebuild` fails with "No signing certificate found". **iOS is different:** iOS apps cannot use Developer ID — keep `Apple Development` + a provisioning profile there, and the ad-hoc/TCC issue does not apply (iOS-Simulator apps don't hit macOS folder-access prompts). Verify a macOS build is not ad-hoc: `codesign -dvvv <app> 2>&1 | grep -E "Signature=|TeamIdentifier"` — `Signature=adhoc` or `TeamIdentifier=not set` means it is still broken.

**CloudKit example workflow:**

1. **Agent edits entitlements** to declare CloudKit + container:
   ```xml
   <key>com.apple.developer.icloud-services</key>
   <array><string>CloudKit</string></array>
   <key>com.apple.developer.icloud-container-identifiers</key>
   <array><string>iCloud.com.example.appname</string></array>
   ```
2. **Agent ensures `DEVELOPMENT_TEAM` is set** (e.g. via `project.yml`):
   ```yaml
   settings:
     base:
       DEVELOPMENT_TEAM: {{DEVELOPMENT_TEAM}}
   ```
3. **Agent regenerates and builds:**
   ```bash
   xcodegen generate
   xcodebuild build -scheme <name> -destination 'platform=iOS Simulator,name=iPhone 16'
   ```
4. **If signing fails** with "container not registered" / "no matching provisioning profile":
   - STOP. Surface to user with exact portal steps, e.g.:
     > "Container `iCloud.com.example.appname` is not registered in Apple Developer Portal. Go to https://developer.apple.com/account → Identifiers → click your App ID (com.example.appname) → enable the iCloud capability → link the container `iCloud.com.example.appname`. ~30 seconds. Ping me when done and I'll retry the build."
5. **User does the portal-click** (~30 sec).
6. **Agent retries `xcodebuild build`** — succeeds.

**Why this split:** Apple Developer Portal requires Apple ID + 2FA, which no MCP/CLI tool automates stably. Xcode's Capabilities pane is just a frontend to the same portal — clicking there doesn't help an agent that has no portal session either. The declarative path (entitlements + project.yml) is the only path that works for BOTH the agent AND for git history (YAML is committable; portal state is implicit).

For CI/CD with many apps or frequent provisioning operations, **Fastlane match** + spaceship is the standard automation surface. Out of scope for solo vibe-coder workflows; mention it only if the user scales beyond one or two apps.

### Anti-patterns (NEVER do these)

- ❌ "Open Xcode and run the tests" — use `mcp__XcodeBuildMCP__test_sim` (MCP) or `xcodebuild test` (CLI) instead
- ❌ "Build the app in Xcode to verify" — use `mcp__XcodeBuildMCP__build_sim` (MCP) or `xcodebuild build` (CLI) instead
- ❌ "Take a screenshot of the simulator" — use `mcp__XcodeBuildMCP__screenshot` (MCP) or `xcrun simctl io booted screenshot` (CLI) instead
- ❌ "Click through the Signing & Capabilities pane in Xcode" — declare entitlements in `*.entitlements` + `project.yml` (XcodeGen) instead
- ❌ "Check what the system color looks like in HIG" — use `mcp__apple-docs__search_apple_docs` or `mcp__swiftui-rag__search_swiftui_corpus` instead

If a verification step requires Xcode the UI, you have not finished the task — use MCP or CLI tools to verify, then report results.
