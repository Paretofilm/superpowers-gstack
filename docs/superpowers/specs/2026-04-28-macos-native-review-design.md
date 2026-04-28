# Design — `macos-native-review` skill

**Status:** Approved 2026-04-28. Ready for implementation plan.
**Plugin:** superpowers-gstack v1.8.1 → v1.9.0 (this delivery)
**Type:** New plugin-internal skill + IDEAS.md cleanup.

---

## 1. Problem

The `superpowers-gstack` plugin already ships two artifact-review skills:

- `pitfall-verification` — *"will this work?"* (correctness, contracts, edge cases)
- `quality-review` — *"will this feel good?"* (cross-platform perceived-quality polish)

During the SwiftConfig spec review (a native macOS SwiftUI app aimed at premium feel), both skills plus codex-consult and self-check signed off as SHIP-READY — yet none of them had validated the spec's UI claims against Apple's published Human Interface Guidelines. The gap that surfaced: nothing in our toolbox grounds *"is this Apple-native?"* in HIG citations, as opposed to the model's training-data recall of HIG.

This skill closes that gap for macOS specifically. iOS, Windows, and Android variants remain backlog items in IDEAS.md (see §10).

## 2. Non-goals

- Not a bug-hunt (`pitfall-verification` owns that)
- Not a cross-platform polish review (`quality-review` owns that)
- Not a security audit of entitlements / sandbox content (`/cso` owns that)
- Not a live UI design review (`/design-review`, `/plan-design-review` own that)
- Not a developer-experience review (`/plan-devex-review` owns that)
- Not release-engineering: code signing, notarization, Sparkle internals are out of scope
- Not iOS, iPadOS, watchOS, tvOS, visionOS — separate skills, deferred in IDEAS.md
- Not Windows or Android — separate skills, deferred in IDEAS.md

## 3. Architecture decision

**Standalone skill, not a parametrized parent.**

We considered a `platform-native-review` parent that takes a `platform=macos|ios|windows|android` argument with shared severity-tier infrastructure. Rejected because:

- Apple HIG, Microsoft Fluent, and Material Design 3 share only severity-tier scaffolding (~20–30 lines of output template). The per-platform category lists, citation URLs, vocabulary expectations, and surface inventories are very different.
- Skills are triggered by frontmatter `description`. A single broad `platform-native-review` description triggers less precisely than four narrow descriptions.
- We have zero sibling experience. Abstracting across imagined siblings is premature; the cost of refactoring four standalone skills into a parent later is lower than the cost of building the wrong abstraction now.
- The plugin's existing skills (`pitfall-verification`, `quality-review`, `setup-routing`, `adapt`, `context-handoff`) are all narrowly-scoped and concrete. A parametrized meta-skill would be the only outlier.

Future siblings (`ios-native-review`, `windows-native-review`, `material-design-review`) will be standalone files following the same shape.

## 4. Scope — 12 categories

The skill walks 12 macOS-specific surfaces. Each maps to a default HIG URL on `developer.apple.com`. Findings within a category cite either the default URL or a more specific sub-page.

| # | Category | Default HIG URL (subpath of `developer.apple.com/design/human-interface-guidelines/`) |
|---|----------|---------------------------------------------------------------------------------|
| 1 | Vocabulary (Apple-canonical verbs/nouns) | (cross-referenced per-component) |
| 2 | Buttons & control choices (Picker vs Segmented vs TabView; Sheet vs Popover vs Alert) | `buttons` |
| 3 | Keyboard shortcuts (⌘W, ⌘., ⌘1–9, ⌘↩, Space, Esc) | `keyboards` |
| 4 | Semantic colors & dark mode (status indicators, system colors, dark-mode story) | `color`, `dark-mode` |
| 5 | Sheets, popovers, alerts (modal vs non-modal, dismiss, resize) | `sheets`, `popovers`, `alerts` |
| 6 | Animation timing (`.spring`, `.snappy` vs SwiftUI default `.easeInOut`) | `motion` |
| 7 | Privileged operations & permission prompts (sudo, TCC, Authorization Services framing) | `privacy` |
| 8 | Accessibility (VoiceOver labels, Dynamic Type, contrast, full-keyboard-access) | `accessibility` |
| 9 | Menu bar (File/Edit/View/Window/Help conventions, command placement, in-menu shortcuts) | `the-menu-bar` |
| 10 | App lifecycle & window restoration (⌘Q vs ⌘W semantics, "close last window doesn't quit on Mac", state restoration, "Reopen All Windows from Last Session") | `windows`, `the-menu-bar` |
| 11 | Dock icon behavior (click-to-reactivate, dock menu, badge counts) | `the-dock` |
| 12 | App menu (App > About <App>, App > Settings…, App > Quit; "Settings" not "Preferences" since macOS 13) | `the-menu-bar` |

**Explicitly out of scope:**
- Code signing, notarization, Gatekeeper details (release engineering)
- Sparkle auto-update internals (build/distribution; only the user-facing prompt-framing of an update would surface in §7)
- AppleScript, Services menu (niche extensibility, rarely decisive for "feels native")
- Contents of `entitlements.plist` (security review domain)

URLs are illustrative starting points. Implementation plan must verify each via WebFetch and adjust if Apple has restructured paths.

## 5. Citation discipline

**Strict: every finding cites a HIG URL.**

The skill's output begins with a 12-row "Category-Default URLs" table. Each finding cites either the default for its category or a more specific sub-page. Where possible, findings include a short verbatim quote from the HIG page to ground the assertion.

**Why strict:** discipline scales — "always cite" is easier to hold consistently than tier-based exceptions. The cost of a citation per finding is one URL string. The value is that the model cannot drift into "general SwiftUI knowledge" without it being visible. WebFetching the URL during review is the verification mechanism.

**Fallback when `developer.apple.com` is unreachable:** the skill runs but degrades visibly:
- Each uncited finding is tagged `(uncited — developer.apple.com unreachable)`.
- Verdict downgrades from `SHIP-READY` / `NEEDS PATCH` / `NEEDS POLISH` to `PROVISIONAL — re-run when network available`.
- The skill never falls back silently to training-data citations pretending they were verified.

## 6. Invocation order and triggers

### 6.1 Order

Sequential after the two existing review skills:

```
pitfall-verification    →  "will this work?"        (bugs, contracts, edge cases)
quality-review          →  "will this feel good?"   (cross-platform polish)
macos-native-review     →  "is this Apple-native?"  (HIG-citation-grounded)
writing-plans           →  implementation
```

The three lenses are distinct. Modest overlap with `quality-review` on two categories (its §10 "Keyboard / native conventions" and §11 "Animations") is acceptable: `quality-review` checks generic surfaces (Esc-to-dismiss, focus ring, named easing exists at all), while `macos-native-review` checks Apple-specific values (⌘., ⌘1–9, exact `.spring(response: 0.35, dampingFraction: 0.85)` vs custom). Different lenses, same surface.

`macos-native-review` does *not* replace `quality-review`. The latter has 13 platform-independent categories (silent failures, empty states, multi-tenancy, AI output, sort order, etc.) that are still worth running on macOS projects.

### 6.2 Trigger — auto, with Phase 0 self-check

Frontmatter `description` makes the skill auto-trigger after any PRD/spec/plan that contains macOS signals. The skill's own first action is a Phase 0 self-check:

1. Scan the artifact for macOS signals:
   - `.swift` files in scope
   - Imports: `SwiftUI`, `AppKit`, `Cocoa`, `Combine` in Apple context
   - Type references: `NSWindow`, `NSView`, `NSApplication`, `NSDocument`, `WindowGroup`, `MenuBarExtra`, `Settings`-scene
   - Explicit text: "macOS app", "Mac app", "macOS-native", "AppKit", "SwiftUI for Mac"
   - Build target: `.xcodeproj` with macOS deployment target, `Package.swift` with `.macOS(.v…)` platform
2. If **no signals found:** return `N/A — no macOS surfaces detected, skill not applicable` and exit. Do not proceed to category review.
3. If **multi-target (iOS + macOS):** proceed with review. macOS surfaces are relevant.
4. If **iOS-only signals:** return `N/A — iOS-only project. The ios-native-review skill is in the backlog (IDEAS.md). Run /quality-review for cross-platform polish in the meantime.`

Phase 0 is the safety net for false positives. Without it, the skill would flag "missing ⌘ shortcuts" for a Linux CLI tool.

## 7. Output format

```
macOS native review (HIG-citation-grounded) —

CATEGORY-DEFAULT URLs:
- [12-row table from §4]

CRITICAL (will feel un-Mac on first launch):
- C<N>. <one-line finding> — <risk surface, file:line or spec section>
  → <concrete fix anchored to a file/section>
  Cited: <HIG URL> "<short verbatim quote, ~10–25 words>"
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

Verdict: SHIP-READY | NEEDS PATCH (CRITICAL findings) | NEEDS POLISH (SIGNIFICANT findings) | PROVISIONAL (citations unverified — re-run when developer.apple.com reachable)
```

If `SHIP-READY`: hand off to implementation.
If `NEEDS PATCH`: fix CRITICAL findings, re-run.
If `NEEDS POLISH`: surface to user with explicit fix-now-or-defer choice (track deferred polish as debt note).
If `PROVISIONAL`: communicate citation status; user decides whether to ship anyway or block on verification.

## 8. Severity rubric

- **CRITICAL** — first launch of the app reads as "wrong platform". Examples:
  - `Cmd-Q` only closes active window instead of quitting the app
  - "Settings" labeled "Preferences" or located outside the App menu
  - No menu bar at all
  - Modal sheet without a dismiss mechanism
  - Hardcoded colors that fail completely in dark mode

- **SIGNIFICANT** — works, but an experienced Mac user reads the app as an iOS port within the first week. Examples:
  - Hardcoded colors that don't respond to dark mode
  - Generic SwiftUI-default `.easeInOut` on sheet present/dismiss
  - Missing ⌘1–9 for tab switching
  - `Picker` used where `Segmented Control` belongs
  - Sudo prompt framed as toast instead of sheet with rationale

- **POLISH** — the gap between "works as a Mac app" and "feels like Things, Raycast, Linear". Examples:
  - No hover-state on toolbar buttons
  - Animation timing close to but not exactly Apple's defaults
  - About panel without copyright string or version-build label
  - Missing menu-item shortcut hint where it could exist

Be honest about severity. POLISH must not be escalated to CRITICAL to force fix.

## 9. Skill format

Standard plugin-internal skill, mirroring `pitfall-verification` and `quality-review`:

- File: `skills/macos-native-review/SKILL.md`
- Frontmatter: `name: macos-native-review`, `description: <auto-trigger description, see below>`
- Sections (in order):
  1. Title + invocation command (`/superpowers-gstack:macos-native-review`)
  2. When to invoke (auto-trigger conditions)
  3. Relationship to `pitfall-verification` and `quality-review` (comparison table)
  4. Sequence (Phase 0 → Categories → Verdict)
  5. Phase 0 — macOS signal detection
  6. Category-default URL table
  7. The 12 categories (each: question → risk surface → verify against HIG → report)
  8. How to run the check (citation discipline, fallback behavior)
  9. Output format
  10. Severity rubric
  11. What this skill is NOT
  12. Example finding (tone & precision)

Frontmatter `description` (draft, refine in implementation):

> Use after a PRD, spec, or implementation plan for a macOS app or feature — before implementation begins. Validates the artifact against Apple Human Interface Guidelines via WebFetch citations: vocabulary, control choices, keyboard shortcuts, semantic colors, sheets/popovers/alerts, animations, privileged operations, accessibility, menu bar, app lifecycle, dock behavior, App menu. Complementary to pitfall-verification ("will this work?") and quality-review ("will this feel good?"); this asks "is this Apple-native?".

## 10. Sibling-skill backlog (IDEAS.md cleanup)

When this skill ships:

1. **Remove** the existing `macos-native-review` entry from IDEAS.md (replaced by the shipped skill; reference commit SHA in changelog).
2. **Add three new entries** with a consistent template — Gap / Scope / Method / Differentiation / Status: deferred (no observed need yet):
   - `ios-native-review` — touch-first, navigation paradigm, modal patterns, sheet detents, Dynamic Island. Mirrors macOS structure but with iOS-specific HIG paths.
   - `windows-native-review` — Microsoft Fluent Design, WinUI 3 conventions, taskbar/system tray, Win11 corner radius, mica/acrylic materials. Citations against `learn.microsoft.com/en-us/windows/apps/design/`.
   - `material-design-review` — Material Design 3 (Android), dynamic color, motion specs, type scale, density. Citations against `m3.material.io`.

3. The three deferred entries follow the same shape, so when one of them is picked up, the brainstorming sequence is short — the template gives the reviewer a head start.

## 11. Delivery scope

This delivery includes:

- New skill: `skills/macos-native-review/SKILL.md`
- Plugin version bump: `1.8.1 → 1.9.0` (`plugin.json`)
- README "What's Included" updated: five → six skills
- CHANGELOG entry for `[1.9.0]`
- Version markers in `setup-routing/SKILL.md` and `adapt/SKILL.md` bumped to `1.9.0`
- IDEAS.md refactor: macOS entry removed, three sibling entries added with consistent template

Out of delivery scope (deferred):
- Implementing the three sibling skills
- Expanding `quality-review` or `pitfall-verification` to cross-reference `macos-native-review`
- Adding `macos-native-review` to user-level CLAUDE.md verification process (user's call)

## 12. Risks & open questions

- **HIG URL drift.** Apple periodically restructures HIG paths (e.g., the iOS 18 / macOS 15 information-architecture pass moved several pages). The implementation plan must verify each of the 12 default URLs via WebFetch before shipping. If a path 404s, surface and resolve before commit.
- **Multi-target false negatives.** A `Package.swift` listing both `.iOS` and `.macOS` will trigger Phase 0 correctly, but a "shared business logic, separate UI targets" repo where the artifact under review only mentions iOS UI will skip macOS review even when the macOS target exists. Acceptable for v1 — caller can always invoke manually.
- **Citation rate-limit / outage during real reviews.** PROVISIONAL fallback handles this, but if it triggers frequently, users may stop trusting the verdict. Monitor anecdotally during first 5–10 real-world runs; revisit if PROVISIONAL becomes the modal verdict.
- **Overlap erosion.** If we later add `ios-native-review` and the two skills share too much output template, that's a signal to extract the parent skill at *that* point — not now.

---

**Approved by user 2026-04-28 in brainstorming session. Ready for `superpowers:writing-plans`.**
