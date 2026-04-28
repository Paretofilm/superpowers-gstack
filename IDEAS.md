# Backlog — proposed skills

Notes on potential future skills, gathered during real review work. Each entry follows a consistent template:

- **Gap.** What existing skills miss.
- **Scope.** What the skill would do.
- **Method.** How it works (citation grounding, output format, mechanics).
- **Differentiation.** Why it's not duplicating an existing skill.
- **Status.** Deferred / shipped / in progress.

When a skill ships, its entry moves to the "Shipped" section below with the commit reference. Active backlog entries above; shipped record below.

---

## `ios-native-review` (proposed 2026-04-28, deferred)

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

**Status.** Deferred — no observed need yet. Pick up when a real iOS spec review surfaces the gap.

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

## Shipped

- `macos-native-review` — shipped in v1.9.0 (2026-04-28). See `skills/macos-native-review/SKILL.md`.
