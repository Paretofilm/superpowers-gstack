---
name: macos-native-review
description: Use after a PRD, spec, or implementation plan for a macOS app or feature — before implementation begins. Validates the artifact against Apple Human Interface Guidelines via WebFetch citations: vocabulary, control choices, keyboard shortcuts, semantic colors, sheets/popovers/alerts, animations, privileged operations, accessibility, menu bar, app lifecycle, dock behavior, App menu. Complementary to pitfall-verification ("will this work?") and quality-review ("will this feel good?") — this asks "is this Apple-native?".
---

# macOS native review

Use this skill after a PRD, spec, or implementation plan that contains macOS-specific UI surfaces — before implementation begins. It is NOT a bug hunt, NOT a cross-platform polish review. It is a targeted check that *the artifact, if shipped as written, will read as a native Mac app to an experienced Mac user* — on the level of Things, Raycast, Linear-mac, Stripe-mac, CleanMyMac — and not as an iOS port.

Every finding cites a specific Apple Human Interface Guidelines page on `developer.apple.com`. The model fetches HIG pages during review rather than relying on training-data recall, so verdicts are grounded in the current published guidelines.

Invoke with: `/superpowers-gstack:macos-native-review`

## When to invoke

Automatically after completing:

- A PRD, spec, or design document for a macOS app or feature
- An implementation plan that touches macOS UI surfaces
- Output from `writing-specs`, `writing-plans`, `plan-design-review`, `plan-eng-review`, or any planning skill — when macOS signals are present (see Phase 0)

Run **once** before implementation. Re-run after substantial spec/plan revisions affecting UI surfaces.

## Relationship to pitfall-verification and quality-review

This skill is *complementary, not overlapping*, with the two existing review skills. Run all three sequentially on a fresh artifact for a macOS app:

| Skill | Lens | Question |
|-------|------|----------|
| `pitfall-verification` | Correctness | "Will this work?" (bugs, security, contracts, edge cases) |
| `quality-review` | Perceived quality | "Will this feel good?" (silent failures, loading, empty/error states, polish — cross-platform) |
| `macos-native-review` | Apple-native conformance | "Is this Apple-native?" (HIG-citation-grounded, macOS-specific) |

Recommended flow on a fresh artifact for a macOS app:

1. `pitfall-verification` → fix bugs
2. `quality-review` → fix feel
3. `macos-native-review` → fix native-conformance gaps
4. Hand off to `writing-plans` / implementation

`macos-native-review` does *not* replace `quality-review`. The latter has 13 platform-independent categories (silent failures, empty states, multi-tenancy, AI output, sort order, etc.) that are still worth running on macOS projects. Modest overlap on two categories (quality-review's keyboard / animations) is acceptable: that skill checks generic conventions, this skill checks Apple-specific values.

## Sequence

1. **Phase 0 — macOS signal detection** (~30 seconds). Scan the artifact for macOS signals. If none found, return `N/A` and exit. If iOS-only, return `N/A` with deferred-skill note. Otherwise proceed.
2. **Walk the 12 categories.** For each: question → risk surface → verify against HIG page (WebFetch) → cite → report `N/A | HANDLED | NOT HANDLED — proposed fix`.
3. **Produce the verdict** in the output format below.

## Phase 0 — macOS signal detection

Scan the artifact for any of these signals:

- `.swift` files referenced in scope
- Imports: `SwiftUI`, `AppKit`, `Cocoa`, `Combine` (in Apple context)
- Type references: `NSWindow`, `NSView`, `NSApplication`, `NSDocument`, `WindowGroup`, `MenuBarExtra`, `Settings` scene
- Explicit text: "macOS app", "Mac app", "macOS-native", "AppKit", "SwiftUI for Mac"
- Build target: `.xcodeproj` with macOS deployment target, `Package.swift` with `.macOS(.v…)` platform

Decision:

- **No signals found:** return `N/A — no macOS surfaces detected, skill not applicable` and exit. Do not proceed.
- **Multi-target (iOS + macOS):** proceed. macOS surfaces are relevant.
- **iOS-only signals:** return `N/A — iOS-only project. The ios-native-review skill is in the backlog (IDEAS.md). Run /quality-review for cross-platform polish in the meantime.`
- **macOS signals present:** proceed.

Phase 0 is the safety net for false positives. Without it, the skill would flag "missing ⌘ shortcuts" for a Linux CLI tool.

## Category-default HIG URL table

Output this table at the top of every review. Each finding cites either the default URL or a more specific sub-page.

| # | Category | Default HIG URL |
|---|----------|------------------|
| 1 | Vocabulary | (cross-referenced per-component — cites the HIG page of the component containing the offending text) |
| 2 | Buttons & control choices | https://developer.apple.com/design/human-interface-guidelines/buttons |
| 3 | Keyboard shortcuts | https://developer.apple.com/design/human-interface-guidelines/keyboards |
| 4 | Semantic colors & dark mode | https://developer.apple.com/design/human-interface-guidelines/color, https://developer.apple.com/design/human-interface-guidelines/dark-mode |
| 5 | Sheets, popovers, alerts | https://developer.apple.com/design/human-interface-guidelines/sheets, https://developer.apple.com/design/human-interface-guidelines/popovers, https://developer.apple.com/design/human-interface-guidelines/alerts |
| 6 | Animation timing | https://developer.apple.com/design/human-interface-guidelines/motion |
| 7 | Privileged operations & permission prompts | https://developer.apple.com/design/human-interface-guidelines/privacy |
| 8 | Accessibility | https://developer.apple.com/design/human-interface-guidelines/accessibility |
| 9 | Menu bar | https://developer.apple.com/design/human-interface-guidelines/the-menu-bar |
| 10 | App lifecycle & window restoration | https://developer.apple.com/design/human-interface-guidelines/windows, https://developer.apple.com/design/human-interface-guidelines/the-menu-bar |
| 11 | Dock icon behavior (Apple HIG has no standalone Dock page; default URL covers Dock contextual menus only — see citation note in §11 below) | https://developer.apple.com/design/human-interface-guidelines/dock-menus |
| 12 | App menu (App > About / Settings… / Quit) | https://developer.apple.com/design/human-interface-guidelines/the-menu-bar |

URLs verified at skill creation. If a URL 404s during review, see "Fallback when developer.apple.com unreachable" below.

## The 12 categories

For each category: state the question, locate the risk surface in the artifact, verify by WebFetching the HIG page, and report `N/A | HANDLED | NOT HANDLED — proposed fix` with citation.

### 1. Vocabulary

Does copy use Apple-canonical verbs and noun choices? In macOS 13+, "Settings" replaced "Preferences" as the App-menu label. Apple uses `Apply` / `Replace` / `Save` / `Done` / `Cancel`, not custom verbs. Apple says "Sidebar", not "Navigation Pane"; "Sheet", not "Modal Dialog". Vocabulary mismatches signal "this app doesn't know the platform".

Risk surfaces: every user-facing string in the spec (button labels, menu items, dialog titles, error messages, empty-state copy).

Cite: the HIG page of the component containing the offending text.

### 2. Buttons & control choices

Is the chosen control HIG-correct for the surface? Specifically: `Picker` vs `SegmentedControl` vs `TabView`; `Sheet` vs `Popover` vs `Alert`; toolbar buttons vs inline buttons; `Toggle` vs checkbox-styled button. A Picker used where a Segmented Control belongs reads as iOS-port instantly.

Risk surfaces: every interactive control introduced by the spec.

Cite: https://developer.apple.com/design/human-interface-guidelines/buttons (or sub-pages for specific control types).

### 3. Keyboard shortcuts

Are macOS-standard shortcuts present and correctly assigned?

- ⌘W — close window (not quit)
- ⌘Q — quit application
- ⌘. — cancel current operation
- ⌘1–9 — switch tabs / sidebar items
- ⌘↩ — primary action in sheet
- Space — quick-look / preview / expand-collapse
- Esc — dismiss sheet / cancel

Missing shortcuts = experienced Mac users hit phantom keys and feel the app is broken.

Risk surfaces: every modal, sheet, list, navigation control in the spec.

Cite: https://developer.apple.com/design/human-interface-guidelines/keyboards

### 4. Semantic colors & dark mode

Are status indicators using Apple semantic colors (`Color.accentColor`, `.red`, `.green`, `Color(NSColor.systemBlue)`) that adapt to appearance, or are they hardcoded hex? Does the spec address dark mode explicitly, or assume light-mode-only?

Risk surfaces: every color reference in the spec; every status indicator; the dark-mode story (or its absence).

Cite: https://developer.apple.com/design/human-interface-guidelines/color and /dark-mode.

### 5. Sheets, popovers, alerts

For each modal surface in the spec: is it the right type? Sheets are for window-scoped modal flows; popovers for transient inline content tied to a UI element; alerts for critical decisions. Is the dismiss mechanism HIG-compliant (sheet: dedicated Cancel + primary buttons; popover: click-outside; alert: Cancel + destructive action)? Is resize-ability appropriate?

Risk surfaces: every modal or transient surface.

Cite: /sheets, /popovers, /alerts.

### 6. Animation timing

Does the spec rely on SwiftUI default animations (`.easeInOut` — generic and reads as "default"), or specify named easing aligned with Apple's defaults (`.spring(response: 0.35, dampingFraction: 0.85)`, `.snappy`, `.smooth`)? Premium Mac apps have signature motion. Generic `.easeInOut` reads as "AI-generated".

Risk surfaces: every sheet present/dismiss, list reorder, state change that is visible.

Cite: https://developer.apple.com/design/human-interface-guidelines/motion

### 7. Privileged operations & permission prompts

If the app requires sudo, admin auth, or system permissions (Full Disk Access, Accessibility, Screen Recording, Automation): is the flow framed as deliberate design — explanation sheet + consent + clear "why we need this" — or as a toast that pops up and disappears? "Just a toast" reads as cheap. Apple's HIG mandates explanation before the system prompt fires.

Risk surfaces: every TCC permission, `osascript` with admin privileges, `Authorization Services` call, sudo flow.

Cite: https://developer.apple.com/design/human-interface-guidelines/privacy

### 8. Accessibility

Are VoiceOver labels defined for non-text controls? Is Dynamic Type support implied (no fixed font sizes that break at large accessibility text sizes)? Is contrast adequate? Is full-keyboard-access mentioned for non-trivial flows?

Risk surfaces: every interactive control, every text-density spec, every keyboard-flow.

Cite: https://developer.apple.com/design/human-interface-guidelines/accessibility

### 9. Menu bar

Does the spec define a menu bar? At minimum macOS apps need: App menu (auto), File, Edit, View (if applicable), Window, Help. Are commands placed in HIG-conventional menus (e.g., Find in Edit, not in View)? Are in-menu shortcuts annotated? Missing menu bar = experienced Mac user looks for the keyboard equivalent and finds nothing.

Risk surfaces: any spec describing a Mac app's command surface; any feature that should be reachable via the menu bar.

Cite: https://developer.apple.com/design/human-interface-guidelines/the-menu-bar

### 10. App lifecycle & window restoration

Is `⌘Q` vs `⌘W` semantics correct (Q quits app, W closes window only)? Does the spec address "close last window doesn't quit on Mac" (unlike iOS, the app stays running)? Is state restoration on relaunch defined ("Reopen All Windows from Last Session")? Is multi-window support indicated where relevant?

Risk surfaces: app launch flow; quit/close flow; window-management behavior in spec.

Cite: /windows, /the-menu-bar.

### 11. Dock icon behavior

Does click-on-dock-icon (when app is hidden / in background) reactivate the main window? Is a dock menu defined for relevant commands? Are badge counts used (and HIG-conformant) where appropriate? For menu-bar-only utilities (e.g. `MenuBarExtra`-only apps with no primary window), does the spec explicitly declare `LSUIElement` (Info.plist) — or the SwiftUI equivalent — to suppress the dock icon? An "agent app" that still shows a dock icon reads as un-finished.

Risk surfaces: dock-icon UX; background/foreground transitions; dock contextual menu; menu-bar-only apps that should be `LSUIElement` agents but don't say so.

Cite — citation strategy for this category:
- For findings about Dock **right-click contextual menus** specifically: cite https://developer.apple.com/design/human-interface-guidelines/dock-menus.
- For findings about general Dock UX (click-to-reactivate, badge counts, background/foreground transitions): Apple HIG does not have a single canonical page. Cite https://developer.apple.com/design/human-interface-guidelines/the-menu-bar (macOS-chrome guidance) or the relevant per-component page (e.g. notifications for badge counts).
- If the citation is partial-match, note that explicitly in the finding (e.g. `Cited (partial — covers contextual menu only): <url>`).

This is the only category in the skill where the default URL is a partial match. All other categories have a single canonical HIG page.

### 12. App menu (App > About / Settings… / Quit)

Does the spec include a proper App menu? It should have: About <App>, Settings… (not "Preferences" since macOS 13), Hide / Hide Others / Show All, Quit <App>. Is the About panel content specified (version, build, copyright, credits)?

Risk surfaces: App menu structure; About panel content.

Cite: https://developer.apple.com/design/human-interface-guidelines/the-menu-bar

## How to run the check

For each category:

1. **State the question** — one sentence.
2. **Locate the risk surface** — which spec section, which file, which user flow?
3. **WebFetch the cited HIG page** — read the relevant guidance, capture a short verbatim quote (~10–25 words) that supports or contradicts the spec's choice.
4. **Verify against the spec** — does the spec align with the HIG quote? Or does it deviate without rationale?
5. **Compare to peer Mac apps** — when in doubt: "how does Things handle this?", "how does Raycast handle this?", "how does Stripe-mac handle this?". Cite the comparison.
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

**Robust-citation note:** Apple's HIG site is a JS-rendered SPA. WebFetch sometimes returns minimal HTML. As a fallback, Apple exposes a structured-content JSON API at `https://developer.apple.com/tutorials/data/design/human-interface-guidelines/<slug>.json` that returns the page's content in machine-readable form. If WebFetch returns sparse content, retry against the JSON endpoint before tagging the finding as `(uncited)`.

## Output format

```
macOS native review (HIG-citation-grounded) —

CATEGORY-DEFAULT URLs:
- [reproduce the 12-row table from above]

CRITICAL (will feel un-Mac on first launch):
- C<N>. <one-line finding> — <risk surface, file:line or spec section>
  → <concrete fix anchored to a file/section>
  Cited: <HIG URL> "<short verbatim quote>"
- ...

SIGNIFICANT (works, but reads as iOS-port within first week):
- S<N>. <finding> → <fix>
  Cited: <HIG URL> "<quote>"
- ...

POLISH (gap to Apple-tier — Things, Raycast, Linear-mac):
- P<N>. <finding> → <fix>
  Cited: <category-default URL> (or specific override)
- ...

Peer comparison: <which Mac-tier app was used as the bar — Things, Raycast, Linear-mac, Stripe-mac, CleanMyMac — and how this artifact stacks up>

Verdict: SHIP-READY | NEEDS PATCH | NEEDS POLISH | PROVISIONAL
```

If `SHIP-READY`: hand off to implementation.
If `NEEDS PATCH`: fix CRITICAL findings, re-run.
If `NEEDS POLISH`: surface to user with explicit fix-now-or-defer choice (track deferred polish as debt note).
If `PROVISIONAL`: communicate citation status; user decides whether to ship anyway or block on verification.

## Severity rubric

- **CRITICAL** — first launch reads as "wrong platform". Examples:
  - `⌘Q` only closes active window instead of quitting the app
  - "Settings" labeled "Preferences" or located outside the App menu
  - No menu bar at all
  - Modal sheet without a dismiss mechanism
  - Hardcoded colors that fail completely in dark mode

- **SIGNIFICANT** — works, but an experienced Mac user reads the app as an iOS port within the first week. Examples:
  - Hardcoded colors that don't adapt to dark mode
  - Generic SwiftUI-default `.easeInOut` on sheet present/dismiss
  - Missing `⌘1–9` for tab switching
  - `Picker` used where `Segmented Control` belongs
  - Sudo prompt framed as toast instead of sheet with rationale

- **POLISH** — the gap between "works as a Mac app" and "feels like Things, Raycast, Linear":
  - No hover-state on toolbar buttons
  - Animation timing close to but not exactly Apple's defaults
  - About panel without copyright string or version-build label
  - Missing menu-item shortcut hint where it could exist

Be honest about severity. POLISH must not be escalated to CRITICAL to force fix.

## What this skill is NOT

- Not a bug hunt — that's `pitfall-verification`
- Not a cross-platform polish review — that's `quality-review`
- Not a security audit (entitlements, sandbox content) — that's `/cso`
- Not a design review of an existing UI — that's `/design-review` (live) or `/plan-design-review` (plan)
- Not a developer-experience review — that's `/plan-devex-review`
- Not release engineering (code signing, notarization, Sparkle internals) — separate domain
- Not iOS, iPadOS, watchOS, tvOS, visionOS — separate skills (deferred in IDEAS.md)
- Not Windows or Android — separate skills (deferred in IDEAS.md)
- Not a code-level SwiftUI review — that's `swiftui-expert-skill` by Antoine van der Lee (separate plugin, install via `/plugin install swiftui-expert@swiftui-expert-skill` after adding marketplace `AvdLee/SwiftUI-Agent-Skill`). It reviews SwiftUI implementation at the code layer (state management, view composition, performance, deprecated-API migration, Liquid Glass, Instruments tracing). `macos-native-review` reviews the spec/plan *before* code exists. Complementary at different lifecycle stages: run `macos-native-review` on the spec, then `swiftui-expert-skill` on the implementation.

It is the *Apple-native conformance gate* between "spec written" and "implementation begins" for macOS projects. Catch the un-Mac decisions before they ship.

## Example finding (tone & precision)

```
C1. App menu uses "Preferences" instead of "Settings". Spec §3.2 ("App
menu structure") lists "Preferences…" as the App-menu item. Apple changed
this label to "Settings…" in macOS 13 (Ventura, 2022); it is now canonical
across the macOS ecosystem. Apps still using "Preferences…" read as
un-updated.

Risk surface: spec §3.2; whatever code generates the menu (likely
`AppMenu.swift` or a SwiftUI `Settings` scene declaration).

Fix: change spec §3.2 to "Settings…". When implementing, use SwiftUI's
`Settings { }` scene which auto-labels the menu correctly on macOS 13+.

Cited: https://developer.apple.com/design/human-interface-guidelines/the-menu-bar
"In macOS 13 and later, the system uses the term Settings... to refer
to what was formerly called preferences."
```

That is the bar: spec section reference, code-file pointer, concrete fix, and a verbatim HIG quote with URL.
