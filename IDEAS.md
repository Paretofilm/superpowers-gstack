# Backlog — proposed skills

Notes on potential future skills, gathered during real review work. Each entry follows a consistent template:

- **Gap.** What existing skills miss.
- **Scope.** What the skill would do.
- **Method.** How it works (citation grounding, output format, mechanics).
- **Differentiation.** Why it's not duplicating an existing skill.
- **Status.** Deferred / shipped / in progress.

When a skill ships, its entry moves to the "Shipped" section below with the commit reference. Active backlog entries above; shipped record below.

---

## `ios-native-review` ✅ SHIPPED in v2.4.0 (2026-05-18) — originally proposed 2026-04-28

**Gap.** Same gap as the (now-shipped) `macos-native-review` had on the macOS side: existing review skills (`pitfall-verification`, `quality-review`) don't validate iOS UI claims against Apple Human Interface Guidelines for iOS specifically. iOS HIG paths and surfaces differ from macOS — touch-first interaction, navigation paradigm (tab bar / navigation stack vs window-based), modal patterns (sheet detents, full-screen presentation), Dynamic Island, gesture conventions.

**Scope.** Validate an iOS app spec or implementation plan against Apple HIG-iOS, specifically:

- **Touch targets** — 44×44pt minimum, hit-area conventions
- **Navigation paradigm** — tab bar vs navigation stack vs split view; large titles; `.navigationBarTitleDisplayMode`
- **Modal presentation** — sheet detents (`.presentationDetents`), full-screen cover, popover (iPad), `.presentationDragIndicator`
- **Gesture conventions** — swipe-to-go-back, edge gestures, pull-to-refresh framing
- **Status bar / safe area / Dynamic Island** — content respect for system surfaces
- **Keyboard handling** — `.keyboardType`, `.textContentType`, return-key actions, dismissal
- **Haptics** — appropriate haptic feedback for confirmation, selection, error
- **Accessibility** — VoiceOver rotor support, Dynamic Type up to AX5, Reduce Motion
- **App lifecycle** — scene-based architecture, background tasks, state restoration
- **App Store / TestFlight conventions** — privacy nutrition labels framing, review-prompt timing

**Method.** Same as `macos-native-review`: WebFetch against `developer.apple.com/design/human-interface-guidelines/<topic>` (iOS sub-paths), severity-tiered findings (CRITICAL / SIGNIFICANT / POLISH), strict per-finding citations, `PROVISIONAL` fallback. Phase 0 detects iOS signals (`UIKit`, `SwiftUI` with iOS deployment target, `UIViewController`, etc.).

**Differentiation.**
- `quality-review` = "would this feel premium?" (cross-platform)
- `pitfall-verification` = "would this work?" (bug hunt)
- `macos-native-review` = "is this Apple-native on Mac?"
- `ios-native-review` = "is this iOS-native?" (touch-first, navigation paradigm, modal detents)

**Status.** ✅ Shipped in v2.4.0. Mirror of macos-native-review structure with 13 iOS-specific categories (vocabulary, controls/touch targets, navigation, modal presentation, gestures, system surfaces, keyboard, haptics, semantic colors, animation, privileged ops, accessibility, lifecycle). Closes backlog S2 from v1.1-backlog. See `skills/ios-native-review/SKILL.md`.

---

## `windows-native-review` (proposed 2026-04-28, deferred)

**Gap.** Existing review skills don't validate Windows app UI claims against Microsoft Fluent Design / WinUI 3 conventions. Windows-specific surfaces — taskbar, system tray, Win11 corner radius, mica/acrylic materials, command bar conventions — are absent from cross-platform `quality-review`.

**Scope.** Validate a Windows app spec or implementation plan against Microsoft Fluent Design + WinUI 3 conventions, specifically:

- **Vocabulary** — Microsoft-canonical verbs and noun choices
- **Control choices** — `CommandBar` vs `MenuBar`, `Flyout` vs `Dialog`, `NavigationView` vs custom
- **Keyboard shortcuts** — Windows-standard (`Ctrl+W`, `Ctrl+,` for settings, `Alt+F4`, F1 for help)
- **Materials** — Mica vs Acrylic vs SolidBackground; when each applies
- **Win11 corner radius** — 8px on windows, dynamic on controls
- **Taskbar / system tray** — taskbar icon behavior, jump lists, system tray menu conventions
- **Theme** — light/dark/auto with system, accent color respect
- **Accessibility** — Narrator support, high-contrast theme, focus visuals
- **Window management** — snap layouts, multi-window, restore

**Method.** WebFetch against `learn.microsoft.com/en-us/windows/apps/design/...` (Fluent Design and WinUI 3 docs). Same severity tiers and citation discipline as `macos-native-review`. Phase 0 detects Windows signals (`.csproj` with `TargetFramework` net8.0-windows, `Microsoft.UI.Xaml`, `WinUI`, etc.).

**Differentiation.** Same shape as `macos-native-review` but Windows-platform; uses Microsoft docs as the source of truth instead of Apple HIG.

**Status.** Deferred — no observed need. Likely longer wait than `ios-native-review` given current project portfolio's Apple lean.

---

## `material-design-review` (proposed 2026-04-28, deferred)

**Gap.** Existing review skills don't validate Android app UI claims against Material Design 3 (Google's design system). Android-specific surfaces — Material You dynamic color, motion specs, type scale, density — are absent from cross-platform `quality-review`.

**Scope.** Validate an Android app spec or implementation plan against Material Design 3, specifically:

- **Vocabulary** — Material-canonical labels (e.g. "Compose" vs "New", "Send" vs "Submit")
- **Components** — `FloatingActionButton`, `BottomNavigation`, `NavigationDrawer`, `TopAppBar` variants, `BottomSheet`
- **Dynamic color (Material You)** — `colorScheme` adapts to wallpaper; explicit theming for elements that should not adapt
- **Motion specs** — Material easing curves (`emphasized`, `standard`), durations (`short`/`medium`/`long`)
- **Type scale** — display, headline, title, body, label — using Material's named styles
- **Density** — touch target sizes (48dp minimum), padding tokens
- **Accessibility** — TalkBack support, contrast tokens, large-text-mode
- **Edge-to-edge** — gesture insets, system bars handling
- **App bar / scrolling behavior** — collapsing toolbars, tonal elevation on scroll

**Method.** WebFetch against `m3.material.io/...` (Material Design 3 docs). Same severity tiers and citation discipline as `macos-native-review`. Phase 0 detects Android signals (`build.gradle` with Android plugin, `androidx.compose.*` imports, `.kt` Android-tagged files).

**Differentiation.** Same shape as `macos-native-review` but Android-platform; uses Material Design 3 as the source of truth.

**Status.** Deferred — no observed need.

---

## `ios-e2e-scaffold` (proposed 2026-04-29, SHIPPED 2026-06-25 v2.17.0)

**Gap.** XCUITest scaffolding for iOS SwiftUI apps; same shape as the (now-shipped) `macos-e2e-scaffold` but with iOS-specific heuristics — gestures, tab-bar, modals with sheet detents, device-rotation, safe-area, NavigationStack vs WindowGroup at the Scene root.

**Scope.** iOS-only. SwiftUI views. iOS Simulator destination. iOS-specific patterns:

- **Scene root** — `WindowGroup` (iOS) without `MenuBarExtra`/`Settings`
- **Navigation** — `NavigationStack` and `TabView` instead of `WindowGroup`-multi
- **Modals** — `.sheet` with `.presentationDetents`, `.fullScreenCover`, popovers (iPad)
- **Gestures** — swipe-to-go-back, pull-to-refresh, drag gestures
- **Lifecycle** — scene phase transitions, background tasks
- **Device contexts** — orientation, dynamic type, AX5 accessibility tier

Out: macOS, watchOS, AppKit.

**Method.** Mirrors `macos-e2e-scaffold` deterministic Read+Grep heuristic. Detects iOS target via `Package.swift` `.iOS(.v...)` or `.xcodeproj` scheme platform. Different scene-walk patterns (TabView/NavigationStack at root instead of WindowGroup), different runner-script destination (`platform=iOS Simulator,name=iPhone 15`).

**Differentiation.** Different heuristic targets (iOS top-flows differ from macOS), different runner-script destination, different identifier examples. Not a wrapper around macos-e2e-scaffold — distinct heuristic with iOS-specific TIER mappings.

**Status.** Shipped 2026-06-25 (v2.17.0). See `skills/ios-e2e-scaffold/SKILL.md`. Phase 0 hardened beyond the original proposal: `WindowGroup` is cross-platform, so iOS detection requires an iOS-discriminating signal (`SDKROOT = iphoneos` / `.iOS(` / `platform: iOS`), not `WindowGroup` alone. Multiplatform targets pass with a note. Runner picks `iPhone 15` else falls back to first available iOS Simulator.

---

## `e2e-route` (proposed + SHIPPED 2026-06-25 v2.17.0)

**Gap.** No routing layer above the E2E executors. `macos-e2e-scaffold`, `ios-e2e-scaffold`, and the MCP-live simulator tools each cover one (platform × intent) cell, but nothing decides *which* executor a given test request needs.

**Scope.** Pure dispatcher — reads context (platform via SUPPORTED_PLATFORMS/.gstack/track × intent via CI-env/verbs × verification kind) and routes to the right executor, then hands off. Owns no execution: no build/tap/assert, no file modification, no test-stub generation. Manual `/e2e-route` + CLAUDE.md routing; not auto-hooked.

**Method.** Routing table keyed on (intent × platform). Committed→scaffold skills; exploratory→MCP-live; visual→`/ios-design-review`. Multiplatform tiebreak asks iOS/macOS/both (both → two decision blocks). Fallback to MCP-live only on a real scaffold Phase 0 refusal (not on SPM-only, which the scaffolds accept).

**Status.** Shipped 2026-06-25 (v2.17.0). See `skills/e2e-route/SKILL.md`. The router *above* the deferred/shipped scaffold skills — `swiftui-snapshot-scaffold` and `appkit-e2e-scaffold` remain deferred and would slot into the routing table when built.

---

## `swiftui-snapshot-scaffold` (proposed 2026-04-29, deferred)

**Gap.** Snapshot-test scaffolding via `swift-snapshot-testing` (Pointfree). Catches visual regressions XCUITest misses — wrong color, wrong margin, cut-off text, dark-mode rendering bugs. Complementary to `macos-e2e-scaffold` and `ios-e2e-scaffold`, not a replacement.

**Scope.** Cross-platform (macOS + iOS). Adds `swift-snapshot-testing` Package.swift dependency. Generates baseline snapshots for top 5 views (heuristic same as e2e-scaffold but ranked by render-complexity rather than interaction-density). First run produces baselines; subsequent runs verify diffs.

**Method.** Detect `View`-conforming structs, render with `assertSnapshot(matching:as:.image)` skeletons. Heuristic ranks views by complexity (modifier count, sub-view count, conditional-rendering branches). Generates per-state snapshot stubs (default state, loading state, error state, empty state — based on view's @State properties).

**Differentiation.** Visual regression rather than interaction. Pairs with any e2e-scaffold skill — together they cover both interaction (XCUITest) and rendering (snapshot).

**Status.** Deferred until snapshot-testing demand surfaces. Currently most projects use unit + XCUITest; snapshot is a third tier rarely adopted from day one.

---

## `appkit-e2e-scaffold` (proposed 2026-04-29, deferred)

**Gap.** XCUITest scaffolding for AppKit-based macOS apps (legacy, mature, or Catalyst-bridged). Different identifier conventions — NSAccessibility uses `accessibilityIdentifier()` method on `NSView` directly, not the SwiftUI `.accessibilityIdentifier(...)` modifier.

**Scope.** AppKit-only views (`NSWindow`, `NSViewController`, `NSButton`, `NSTextField`, `NSTableView`). Different scene-walk heuristic (no SwiftUI Scene tree; AppKit uses controller hierarchy via `NSWindowController` and `NSViewController` segues/storyboards).

**Method.** Grep for `NSWindow`, `NSViewController`, `NSButton(`, `NSTextField(`, `NSTableView`. Walk controller hierarchy from `NSStoryboard` references. Different identifier convention applied via Swift code rather than modifier-chain.

**Differentiation.** AppKit-only. Won't work for SwiftUI projects (use `macos-e2e-scaffold`). Useful for legacy apps that haven't migrated to SwiftUI, or hybrid SwiftUI-on-AppKit projects where critical surfaces are still AppKit.

**Status.** Deferred until observed need (most modern macOS apps are SwiftUI-first).

---

## Partial-artifact verification — når er `pitfall-verification` for tidlig? (proposed 2026-05-21, open question)

**Gap.** `pitfall-verification` er kalibrert for *komplette artefakter* — ferdige specs, planer eller kode. Skill-en har et "maks to runder"-budsjett. Men under lange brainstorming/design-sesjoner produseres sub-artefakter inkrementelt (f.eks. én arkitektur-seksjon av fem). Å kjøre den fulle skill-en på partial output gir enten (a) false positives om "manglende seksjoner" som bare ikke er skrevet ennå, eller (b) bruker opp runde-budsjettet tidlig så den endelige komplette-artefakt-runden har mindre headroom.

**Observed need.** Surfaced 2026-05-21 midt i brainstorm av "Live SwiftUI v0"-design. Etter at seksjon 1 av 5 (arkitektur + moduler) var presentert spurte brukeren om en pitfall-review passet. Fem ekte flagg fantes i den seksjonen (NSXPCConnection-mekanikk, concurrency-koherens mellom stateless API og "last render wins", SwiftSyntax-versjonsbinding, NSHostingView/dlclose-livssyklus, ToolService XPC-bridge-overhead) — alle verdt å fange før vi bygget fire seksjoner til oppe på dem. Men formell skill-invokasjon føltes feilkalibrert. Løsningen i sesjonen ble en uformell inline-sanity-check og senere bruk av den formelle skill-en på ferdig spec.

**Scope.** En av tre løsninger:
- (a) En lettere søsken-skill `partial-design-sanity-check` med eksplisitt "jeg ser kun arkitektur-seksjonen, ikke flagg manglende detalj"-framing.
- (b) En utvidelse av `pitfall-verification` med en `partial: true`-flag og tilpassede prompts som beskjeder hva som er bevisst utelatt.
- (c) Eksplisitt veiledning i `pitfall-verification` SKILL.md om *når man ikke skal bruke den* — push partial-artefakt-reviews til inline self-review i stedet.

**Åpne underspørsmål.**
- Er det verdt en separat skill, eller bare en flag/modus på den eksisterende?
- Skal partial reviews konsumere budsjett fra hovedskill-ens "to runder", eller ha sitt eget?
- Hvordan interagerer dette med brainstorming → writing-specs-handoffs — skal pitfall alltid kjøre mellom handoffs, selv når hver artefakt er intermediær?
- Hvis vi legger til en `partial`-modus: hvordan deklarerer vi hvilke seksjoner som er bevisst fraværende (så modellen vet å ikke flagge dem)?

**Differentiation.** Ikke et nytt domene — samme risiko-taksonomi som `pitfall-verification` (sikkerhet, idempotens, kontrakter, edge cases). Forskjellen er *artefakt-komplettheit-signalering*: si til reviewer-en "dette er strukturelt ufullstendig by design, evaluer det som er der".

**Status.** Open question. Ikke blokkerende for shipped skills. Trenger beslutning før neste gang det surfacer — sannsynligvis allerede ved seksjon 2-5 av `live-swiftui`-designet.

---

## Shipped

- `macos-native-review` — shipped in v1.9.0 (2026-04-28). See `skills/macos-native-review/SKILL.md`.
- `macos-e2e-scaffold` — shipped in v1.10.0 (2026-04-29). See `skills/macos-e2e-scaffold/SKILL.md`.
- `ios-native-review` — shipped in v2.4.0 (2026-05-18). Mirror of macos-native-review with 13 iOS-specific categories. See `skills/ios-native-review/SKILL.md`. (Body entry above retained for proposal-vs-shipped record.)
