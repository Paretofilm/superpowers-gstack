---
name: ios-native-review
description: Use after a PRD, spec, or implementation plan for an iOS app or feature — before implementation begins. Validates the artifact against Apple Human Interface Guidelines (iOS) via WebFetch citations: vocabulary, controls/touch targets, navigation paradigm, modal presentation, gestures, system surfaces, keyboard handling, haptics, semantic colors, animation timing, privileged operations, accessibility, app lifecycle. Complementary to pitfall-verification ("will this work?") and quality-review ("will this feel good?") — this asks "is this iOS-native?".
---

# iOS native review

Use this skill after a PRD, spec, or implementation plan that contains iOS-specific UI surfaces — before implementation begins. It is NOT a bug hunt, NOT a cross-platform polish review. It is a targeted check that *the artifact, if shipped as written, will read as a native iOS app to an experienced iPhone/iPad user* — on the level of Things, Bear, Overcast, Streaks, Carrot Weather, Lookup — and not as an Android-port or web-app wrapper.

Every finding cites a specific Apple Human Interface Guidelines page on `developer.apple.com`. The model fetches HIG pages during review rather than relying on training-data recall, so verdicts are grounded in the current published guidelines.

Invoke with: `/superpowers-gstack:ios-native-review`

## When to invoke

Automatically after completing:

- A PRD, spec, or design document for an iOS or iPadOS app or feature
- An implementation plan that touches iOS UI surfaces
- Output from `writing-specs`, `writing-plans`, `plan-design-review`, `plan-eng-review`, or any planning skill — when iOS signals are present (see Phase 0)

Run **once** before implementation. Re-run after substantial spec/plan revisions affecting UI surfaces.

## Relationship to pitfall-verification and quality-review

This skill is *complementary, not overlapping*, with the two existing review skills. Run all three sequentially on a fresh artifact for an iOS app:

| Skill | Lens | Question |
|-------|------|----------|
| `pitfall-verification` | Correctness | "Will this work?" (bugs, security, contracts, edge cases) |
| `quality-review` | Perceived quality | "Will this feel good?" (silent failures, loading, empty/error states, polish — cross-platform) |
| `ios-native-review` | Apple-native conformance | "Is this iOS-native?" (HIG-citation-grounded, iOS-specific) |

Recommended flow on a fresh artifact for an iOS app:

1. `pitfall-verification` → fix bugs
2. `quality-review` → fix feel
3. `ios-native-review` → fix native-conformance gaps
4. Hand off to `writing-plans` / implementation

`ios-native-review` does *not* replace `quality-review`. The latter has 13 platform-independent categories (silent failures, empty states, multi-tenancy, AI output, sort order, etc.) that are still worth running on iOS projects. Modest overlap on two categories (quality-review's keyboard / animations) is acceptable: that skill checks generic conventions, this skill checks Apple-iOS-specific values.

### Relationship to macos-native-review and swiftui-design-consultation

For **iOS + macOS multi-target projects**: run `ios-native-review` AND `macos-native-review` both. They're complementary, not redundant — most HIG categories overlap in name but diverge in detail (sheets work differently, navigation is fundamentally different, modal presentation rules differ).

`/superpowers-gstack:swiftui-design-consultation` is the upstream design-system step for SwiftUI projects. It produces a DESIGN.md + Swift Package starter; for iOS projects it auto-chains into this skill on the DESIGN.md and `mcp__swiftui-rag__review_macos_hig` (which despite its name contains many platform-agnostic HIG rules) on each generated `.swift` file.

## Sequence

1. **Phase 0 — iOS signal detection** (~30 seconds). Scan the artifact for iOS signals. If none found, return `N/A` and exit. If macOS-only, return `N/A` with sibling-skill note. Otherwise proceed.
2. **Walk the 13 categories.** For each: question → risk surface → verify against HIG page (WebFetch) → cite → report `N/A | HANDLED | NOT HANDLED — proposed fix`.
3. **Produce the verdict** in the output format below.

## Phase 0 — iOS signal detection

Scan the artifact for any of these signals:

- `.swift` files referenced in scope with iOS-flavored types
- Imports: `SwiftUI`, `UIKit`, `Combine` (in Apple context)
- Type references: `UIViewController`, `UINavigationController`, `UITabBarController`, `UIView`, `UIApplication`, `UIScene`, `WindowGroup` (in iOS App context), `TabView`, `NavigationStack`, `NavigationSplitView`
- Explicit text: "iOS app", "iPhone app", "iPad app", "iPadOS", "iOS-native", "UIKit", "SwiftUI for iOS"
- Build target: `.xcodeproj` with iOS deployment target, `Package.swift` with `.iOS(.v…)` platform, Info.plist with `UIApplicationSceneManifest`

Decision:

- **No signals found:** return `N/A — no iOS surfaces detected, skill not applicable` and exit. Do not proceed.
- **Multi-target (iOS + macOS):** proceed. iOS surfaces are relevant. Run macos-native-review in parallel.
- **macOS-only signals:** return `N/A — macOS-only project. Use /superpowers-gstack:macos-native-review instead.`
- **iOS signals present:** proceed.

Phase 0 is the safety net for false positives. Without it, the skill would flag "missing tab bar" for a watchOS app or a Linux CLI tool.

## Category-default HIG URL table

Output this table at the top of every review. Each finding cites either the default URL or a more specific sub-page.

| # | Category | Default HIG URL |
|---|----------|------------------|
| 1 | Vocabulary | (cross-referenced per-component — cites the HIG page of the component containing the offending text) |
| 2 | Controls & touch targets | https://developer.apple.com/design/human-interface-guidelines/buttons |
| 3 | Navigation paradigm (tab bar, navigation stack, split view) | https://developer.apple.com/design/human-interface-guidelines/tab-bars, https://developer.apple.com/design/human-interface-guidelines/navigation-bars |
| 4 | Modal presentation (sheets, full-screen, popovers) | https://developer.apple.com/design/human-interface-guidelines/sheets, https://developer.apple.com/design/human-interface-guidelines/popovers, https://developer.apple.com/design/human-interface-guidelines/alerts |
| 5 | Gestures | https://developer.apple.com/design/human-interface-guidelines/gestures |
| 6 | System surfaces (safe area, Dynamic Island, status bar) | https://developer.apple.com/design/human-interface-guidelines/layout, https://developer.apple.com/design/human-interface-guidelines/live-activities |
| 7 | Keyboard handling | https://developer.apple.com/design/human-interface-guidelines/onscreen-keyboards |
| 8 | Haptics | https://developer.apple.com/design/human-interface-guidelines/playing-haptics |
| 9 | Semantic colors & dark mode | https://developer.apple.com/design/human-interface-guidelines/color, https://developer.apple.com/design/human-interface-guidelines/dark-mode |
| 10 | Animation timing | https://developer.apple.com/design/human-interface-guidelines/motion |
| 11 | Privileged operations & permission prompts | https://developer.apple.com/design/human-interface-guidelines/privacy, https://developer.apple.com/design/human-interface-guidelines/onboarding |
| 12 | Accessibility | https://developer.apple.com/design/human-interface-guidelines/accessibility |
| 13 | App lifecycle & state restoration | https://developer.apple.com/design/human-interface-guidelines/launching, https://developer.apple.com/design/human-interface-guidelines/multitasking |

URLs verified at skill creation (spot-checked /buttons for touch-target guidance — JSON endpoint returned canonical 44×44 pt quote). If a URL 404s during review, see "Fallback when developer.apple.com unreachable" below.

## The 13 categories

For each category: state the question, locate the risk surface in the artifact, verify by WebFetching the HIG page, and report `N/A | HANDLED | NOT HANDLED — proposed fix` with citation.

### 1. Vocabulary

Does copy use Apple-canonical verbs and noun choices for iOS? Apple uses `Done` / `Cancel` / `Save` / `Delete` / `Add`, not custom verbs. iOS says "Tab bar", not "Bottom Navigation"; "Sheet", not "Bottom Sheet" (Material term); "Navigation bar", not "App bar". Toolbar items are placed in the `Toolbar` modifier, not in custom-built bottom bars. Vocabulary mismatches signal "this app is an Android port".

Risk surfaces: every user-facing string in the spec (button labels, tab titles, navigation titles, sheet titles, alert copy, empty-state copy).

Cite: the HIG page of the component containing the offending text.

### 2. Controls & touch targets

Are interactive elements at least 44×44 pt? Are controls HIG-correct for the surface? Specifically: `Button` vs `Menu` vs `Picker`; `Toggle` vs `Switch`; `Stepper` for fine-grained numeric input; `SegmentedControl` for ≤6 mutually-exclusive options. Tap targets smaller than 44×44 pt cause mis-taps; controls mis-mapped to surfaces signal cross-platform thinking.

Risk surfaces: every interactive control, especially icon-only buttons, tab-bar items, list-row actions.

Cite: https://developer.apple.com/design/human-interface-guidelines/buttons. Verbatim 44×44 pt guidance: "a button needs a hit region of at least 44x44 pt … to ensure that people can select it easily".

### 3. Navigation paradigm

Is the right navigation pattern chosen for the app's content? `TabView` for ≤5 top-level peer destinations; `NavigationStack` for hierarchical drill-down; `NavigationSplitView` for iPad/multi-column. Are large titles (`.navigationBarTitleDisplayMode(.large)`) used on root screens, inline on drill-down? Is the back-button label predictable (the previous screen's title, not "Back")? Wrong choices read as Android-style (everything-is-a-stack) or web-style (sidebar-first).

Risk surfaces: top-level navigation structure; per-screen title configuration; back-navigation labeling.

Cite: https://developer.apple.com/design/human-interface-guidelines/tab-bars, https://developer.apple.com/design/human-interface-guidelines/navigation-bars

### 4. Modal presentation (sheets, full-screen, popovers)

For each modal surface: is it the right presentation style? `.sheet` for self-contained modal tasks (auto-detents on iOS 16+); `.fullScreenCover` for immersive flows (onboarding, camera, video player); `.popover` ONLY on iPad (regular size class) — it becomes a sheet on iPhone automatically. Are sheet detents specified (`.presentationDetents([.medium, .large])`) where mid-size makes sense? Is `.presentationDragIndicator(.visible)` set for user-discoverable dismissal? Is `.interactiveDismissDisabled()` used when the user has unsaved input?

Risk surfaces: every modal surface; every "show this view" interaction in the spec.

Cite: /sheets, /popovers, /alerts.

### 5. Gestures

Are platform-standard gestures preserved? Specifically: swipe-from-left-edge for navigation back (don't disable unless absolutely necessary); pull-to-refresh on lists (`.refreshable {}`); swipe-actions on list rows (`.swipeActions {}`); long-press for context menu (`.contextMenu {}`). Are custom gestures clearly differentiated from system gestures (no edge-conflicts)? Are gesture hints visible (drag indicators, swipe affordances) for non-obvious interactions?

Risk surfaces: every list, scroll view, and modal — anywhere gesture conflicts can occur; any spec describing a custom gesture.

Cite: https://developer.apple.com/design/human-interface-guidelines/gestures

### 6. System surfaces (safe area, Dynamic Island, status bar)

Does the layout respect `safeAreaInsets` (no content under notch, home indicator, status bar)? Is content extended into the safe area only deliberately (`ignoresSafeArea` is opt-in, not default)? For apps with background activities (timers, audio, navigation): is Live Activity / Dynamic Island integration considered or explicitly out-of-scope? Is the status bar style appropriate (`.dark` content over light background, `.light` over dark)?

Risk surfaces: every full-screen view; every navigation-bar-less view; every long-running background task.

Cite: https://developer.apple.com/design/human-interface-guidelines/layout for safe areas; https://developer.apple.com/design/human-interface-guidelines/live-activities for Dynamic Island.

### 7. Keyboard handling

Are `.keyboardType` and `.textContentType` set correctly on each `TextField`? Common pairings: `.emailAddress` + `.emailAddress`; `.numberPad` + appropriate `textContentType`; `.URL` + `.URL`. Is the return-key action specified (`.submitLabel(.send | .next | .done)`)? Does keyboard dismiss on tap-outside (or is there an explicit "Done" button on a numpad)? Does the form scroll to keep the focused field visible above the keyboard?

Risk surfaces: every text input; every form; every multi-field flow.

Cite: https://developer.apple.com/design/human-interface-guidelines/onscreen-keyboards

### 8. Haptics

Are haptics used for confirmation (`.notificationOccurred(.success | .warning | .error)`), selection (`.selectionChanged`), and impact (`.impactOccurred(.light | .medium | .heavy)`)? Or are they absent (making the app feel "silent" / unresponsive on iPhone), or overused (haptic on every tap is fatiguing)? Haptics should accompany state changes that the user benefits from feeling, not every UI event.

Risk surfaces: form submission outcomes; toggle / switch state changes; segmented-control selection; sheet present/dismiss; destructive actions.

Cite: https://developer.apple.com/design/human-interface-guidelines/playing-haptics

### 9. Semantic colors & dark mode

Are status indicators using Apple semantic colors (`Color.accentColor`, `.red`, `.green`, `Color(.systemBlue)`, `Color(.label)`, `Color(.secondaryLabel)`) that adapt to appearance, or are they hardcoded hex? Are background colors using `Color(.systemBackground)` / `.systemGroupedBackground` / `.secondarySystemBackground` for grouping hierarchy? Does the spec address dark mode explicitly, or assume light-mode-only?

Risk surfaces: every color reference in the spec; every status indicator; the dark-mode story (or its absence).

Cite: https://developer.apple.com/design/human-interface-guidelines/color and /dark-mode.

### 10. Animation timing

Does the spec rely on SwiftUI default animations (`.easeInOut` — generic and reads as "default"), or specify named easing aligned with Apple's defaults (`.spring(response: 0.35, dampingFraction: 0.85)`, `.snappy`, `.smooth`, `.bouncy`)? Are transitions appropriate (`.move(edge:)` for slide-in, `.scale.combined(with: .opacity)` for emphasis, `.identity` for no transition)? Premium iOS apps have signature motion. Generic `.easeInOut` reads as "AI-generated" or "rushed".

Risk surfaces: every sheet present/dismiss, list reorder, tab switch, state change that is visible.

Cite: https://developer.apple.com/design/human-interface-guidelines/motion

### 11. Privileged operations & permission prompts

If the app requires sensitive permissions (Location, Camera, Microphone, Photo Library, Notifications, Contacts, Tracking via ATT): is the flow framed as deliberate design — explanation screen + consent + clear "why we need this" — or as the raw system prompt fired immediately on launch? Is the request *delayed* until the user reaches a feature that needs it (just-in-time)? Is the `NSXxxxUsageDescription` Info.plist string a real sentence ("Used to attach photos to your notes"), not a token ("photo access")? For App Tracking Transparency: is the pre-prompt explanation present (Apple requires it for any non-zero opt-in rate)?

Risk surfaces: every permission request; the launch flow; the Info.plist usage strings; the onboarding flow.

Cite: https://developer.apple.com/design/human-interface-guidelines/privacy and /onboarding.

### 12. Accessibility

Are VoiceOver labels defined for non-text controls (icon-only buttons especially)? Is Dynamic Type supported up to AX5 sizes (`Text(...).font(.body)` over fixed `.system(size: 16)`)? Are color contrasts meeting WCAG AA (4.5:1 for normal text, 3:1 for large)? Is Reduce Motion respected (`UIAccessibility.isReduceMotionEnabled` → fade instead of slide)? Is `.accessibilityLabel`, `.accessibilityHint`, `.accessibilityValue` used appropriately on custom controls? Does the spec mention VoiceOver rotor navigation for complex screens?

Risk surfaces: every interactive control, every icon-only button, every motion-heavy transition, every color-coded status indicator.

Cite: https://developer.apple.com/design/human-interface-guidelines/accessibility

### 13. App lifecycle & state restoration

Does the spec address scene-based lifecycle (multi-window on iPadOS)? Is state preserved across backgrounding (returning users land where they left off, not on the launch screen)? Are long-running operations handled correctly (`BGAppRefreshTask`, `BGProcessingTask` for background refresh; `URLSession` background config for downloads)? Is the launch screen designed to match the first-content screen (not a splash with logo, which Apple discourages)?

Risk surfaces: launch flow; backgrounding/foregrounding behavior; multi-window support claims; background-task usage.

Cite: https://developer.apple.com/design/human-interface-guidelines/launching, https://developer.apple.com/design/human-interface-guidelines/multitasking

## How to run the check

For each category:

1. **State the question** — one sentence.
2. **Locate the risk surface** — which spec section, which file, which user flow?
3. **WebFetch the cited HIG page** — read the relevant guidance, capture a short verbatim quote (~10–25 words) that supports or contradicts the spec's choice.
4. **Verify against the spec** — does the spec align with the HIG quote? Or does it deviate without rationale?
5. **Compare to peer iOS apps** — when in doubt: "how does Things handle this?", "how does Bear handle this?", "how does Overcast handle this?", "how does Lookup handle this?". Cite the comparison.
6. **Report**: `N/A` (with reason) / `HANDLED` (point to where) / `NOT HANDLED — proposed fix` (concrete, file/section-anchored, with citation).

Concrete findings only. Never vague advice like "follow HIG more closely". Every NOT HANDLED finding must include:

- A proposed fix that names a file, function, or spec section
- A citation: HIG URL + verbatim quote

### Citation discipline

**Every finding cites a HIG URL.** No exceptions. Use the category-default URL or a more specific sub-page. Where the model is uncertain, WebFetch first, cite the exact quote, then form the finding.

### Fallback when developer.apple.com unreachable

If WebFetch fails for any HIG URL during review, the skill degrades visibly:

- Each uncited finding is tagged `(uncited — developer.apple.com unreachable)`.
- The verdict downgrades from `SHIP-READY` / `NEEDS PATCH` / `NEEDS POLISH` to `PROVISIONAL — re-run when network available`.

Never fall back silently to training-data recall pretending the citation was verified.

**Robust-citation note:** Apple's HIG site is a JS-rendered SPA. WebFetch on the HTML URL often returns minimal content (only the page title). As a fallback, Apple exposes a structured-content JSON API at `https://developer.apple.com/tutorials/data/design/human-interface-guidelines/<slug>.json` that returns the page's content in machine-readable form. If WebFetch on the HTML URL returns sparse content, retry against the JSON endpoint before tagging the finding as `(uncited)`. Verified at skill creation: the JSON endpoint for `/buttons` returns the canonical 44×44 pt touch-target quote.

## Output format

```
iOS native review (HIG-citation-grounded) —

CATEGORY-DEFAULT URLs:
- [reproduce the 13-row table from above]

CRITICAL (will feel un-iOS on first launch):
- C<N>. <one-line finding> — <risk surface, file:line or spec section>
  → <concrete fix anchored to a file/section>
  Cited: <HIG URL> "<short verbatim quote>"
- ...

SIGNIFICANT (works, but reads as cross-platform port within first week):
- S<N>. <finding> → <fix>
  Cited: <HIG URL> "<quote>"
- ...

POLISH (gap to Apple-tier — Things, Bear, Overcast, Carrot Weather):
- P<N>. <finding> → <fix>
  Cited: <category-default URL> (or specific override)
- ...

Peer comparison: <which iOS-tier app was used as the bar — Things, Bear, Overcast, Streaks, Carrot Weather, Lookup — and how this artifact stacks up>

Verdict: SHIP-READY | NEEDS PATCH | NEEDS POLISH | PROVISIONAL
```

If `SHIP-READY`: hand off to implementation.
If `NEEDS PATCH`: fix CRITICAL findings, re-run.
If `NEEDS POLISH`: surface to user with explicit fix-now-or-defer choice (track deferred polish as debt note).
If `PROVISIONAL`: communicate citation status; user decides whether to ship anyway or block on verification.

## Severity rubric

- **CRITICAL** — first launch reads as "wrong platform". Examples:
  - Bottom-navigation bar custom-built instead of `TabView`
  - Sheet without dismiss mechanism on iPhone (no drag indicator, no Cancel, no swipe-down)
  - Permission prompt fires on launch with no rationale
  - Tap targets visibly smaller than 44×44 pt on primary controls
  - Hardcoded colors that fail completely in dark mode
  - Content rendered under notch / Dynamic Island / home indicator
  - Disabled swipe-back gesture on a hierarchical navigation flow

- **SIGNIFICANT** — works, but an experienced iPhone user reads the app as a port within the first week. Examples:
  - "Bottom Sheet" terminology (Material) instead of "Sheet"
  - No haptics on confirmation / destructive actions
  - Generic SwiftUI-default `.easeInOut` on sheet present/dismiss
  - Missing `.textContentType` on email/password fields (no autofill)
  - No pull-to-refresh on a list that obviously needs it
  - Permission `NSUsageDescription` strings are tokens, not sentences

- **POLISH** — the gap between "works as an iOS app" and "feels like Things, Bear, Carrot Weather":
  - No haptic differentiation between selection vs confirmation
  - Animation timing close to but not exactly Apple's defaults
  - Launch screen has a logo splash instead of matching first-content layout
  - No `.presentationDragIndicator` on dismissible sheets where it would aid discoverability
  - Missing Dynamic Island integration on a clearly-applicable background task

Be honest about severity. POLISH must not be escalated to CRITICAL to force fix.

## What this skill is NOT

- Not a bug hunt — that's `pitfall-verification`
- Not a cross-platform polish review — that's `quality-review`
- Not a security audit (entitlements, sandbox content) — that's `/cso`
- Not a design review of an existing UI — that's `/design-review` (live) or `/plan-design-review` (plan)
- Not a developer-experience review — that's `/plan-devex-review`
- Not release engineering (code signing, App Store submission, TestFlight pipelines) — separate domain
- Not macOS, iPadOS-as-desktop, watchOS, tvOS, visionOS — separate skills (macos-native-review exists; others deferred in IDEAS.md)
- Not Windows or Android — separate skills (deferred in IDEAS.md)
- Not a code-level SwiftUI review — that's `swiftui-expert-skill` by Antoine van der Lee (separate plugin, install via `/plugin install swiftui-expert@swiftui-expert-skill` after adding marketplace `AvdLee/SwiftUI-Agent-Skill`). It reviews SwiftUI implementation at the code layer (state management, view composition, performance, deprecated-API migration, Liquid Glass, Instruments tracing). `ios-native-review` reviews the spec/plan *before* code exists. Complementary at different lifecycle stages: run `ios-native-review` on the spec, then `swiftui-expert-skill` on the implementation.

It is the *Apple-native conformance gate* between "spec written" and "implementation begins" for iOS projects. Catch the un-iOS decisions before they ship.

## Example finding (tone & precision)

```
C1. Bottom navigation custom-built instead of TabView. Spec §2.4 ("App
navigation") describes a "bottom navigation bar with 4 main sections"
implemented as a custom HStack pinned to the bottom safe area. iOS apps
use TabView for ≤5 top-level peer destinations — it handles tab-bar
sizing, dark mode adaptation, large-content viewer for AX users, and
Dynamic Type scaling automatically. A custom HStack will fail on all
four counts, and read as Material-Design-on-iOS to first launch.

Risk surface: spec §2.4; whatever view-file declares the bottom bar
(likely `RootView.swift` or `MainTabView.swift`).

Fix: change spec §2.4 to specify SwiftUI `TabView` with one `Tab(...)`
per top-level destination. Drop the custom bottom HStack. Use
`.toolbar(.visible, for: .tabBar)` only where explicit visibility
control is needed.

Cited: https://developer.apple.com/design/human-interface-guidelines/tab-bars
"A tab bar lets people navigate among different sections of an app …
people expect to find tab bars near the bottom of the screen."
```

That is the bar: spec section reference, code-file pointer, concrete fix, and a verbatim HIG quote with URL.
