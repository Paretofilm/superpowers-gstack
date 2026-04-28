# Backlog — proposed skills

Notes on potential future skills, gathered during real review work. Each entry explains the GAP (what existing skills miss), the SCOPE (what the skill would do), and the OBSERVED NEED (when it would have been useful).

---

## `macos-native-review` (proposed 2026-04-28)

**Gap.** `quality-review` covers premium-app feel in general terms (silent failures, loading states, empty states, native conventions, animations). It mentions native conventions but does NOT validate specific UI claims against Apple Human Interface Guidelines. `pitfall-verification` checks for bugs. Neither catches "this app smells non-native because the spec uses non-Apple vocabulary, the wrong control type for the surface, or missing macOS-standard keyboard shortcuts."

**Scope.** Validate a macOS app spec or implementation against Apple HIG, specifically:

- **Vocabulary:** does copy use Apple-canonical verbs (`Apply`/`Replace`/`Save`/`Done`/`Cancel`) and noun choices (Apple says "System Settings", not "Tweaks"; "Sidebar", not "Navigation Pane"; "Sheet", not "Modal Dialog")?
- **Control choices:** is the chosen control HIG-correct for the surface? (e.g. `Picker` vs `Segmented Control` vs `TabView`; `Sheet` vs `Popover` vs `Alert`; toolbar buttons vs inline buttons)
- **Keyboard shortcuts:** are macOS-standard shortcuts present? (`⌘W` to dismiss, `⌘.` to cancel, `⌘1`–`⌘9` for tab toggles, `⌘↩` for primary action in sheets, Space for expand/collapse)
- **Semantic colors:** are status indicators using the right Apple semantic colors and not hardcoded? Does dark-mode story exist?
- **Sheet / window behavior:** modal vs non-modal, dismissable, resizable — HIG-compliant?
- **Animation timing:** is `.spring(response: 0.35, dampingFraction: 0.85)` aligned with Apple defaults, or is it just "feels good" guesswork?
- **Privileged ops, files-in-home-dir, sandbox boundaries:** is the design HIG-aligned for sudo / sensitive operations?
- **Accessibility:** are VoiceOver labels, Dynamic Type, and contrast considered?

**Method.** WebFetch against `developer.apple.com/design/human-interface-guidelines/<topic>` for each UI element claim, then mark each spec section ✓ / ⚠️ / ✗ with the HIG quote that supports the verdict. Should ground assertions in citations rather than the model's training data, since HIG evolves.

**Output format.** Same severity-tiered structure as `quality-review` (Critical / Significant / Polish) but every finding cites a specific HIG page URL.

**Observed need.** During Phase E spec work for SwiftConfig (a native macOS SwiftUI app aimed at "premium feel"), all four review lenses already in the project — self-check, pitfall-verification × 3, quality-review, codex-consult × 4 — shipped a SHIP-READY spec that none of them had validated against actual Apple HIG. The user explicitly asked "burde vi ta en review til? i så fall hva slags?" and the gap that emerged was: nothing in our toolbox validates UI vocabulary, control choices, or keyboard conventions against Apple's published guidelines. We did the review manually (WebFetch + spec walk-through) but it should be a first-class skill for any macOS/iOS app project.

**Differentiation from existing skills:**
- `quality-review` = "would this feel premium?" (cross-platform, principle-based)
- `pitfall-verification` = "would this work?" (bug hunt)
- `codex-consult` = adversarial second opinion (independent model)
- `macos-native-review` = "is this Apple-native?" (HIG-citation-grounded, platform-specific)

**Adjacent skills to consider:** `ios-native-review`, `windows-native-review`, `material-design-review` (Android) — same shape, different style guide. Could share infrastructure (severity tiers, citation format) via a parent `platform-native-review` skill.

**When to invoke.** After a spec or implementation plan that touches platform-specific UI surfaces. Same trigger position as `quality-review` — between pitfall-verification and writing-plans.
