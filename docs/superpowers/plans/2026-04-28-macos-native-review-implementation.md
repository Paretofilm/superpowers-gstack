# `macos-native-review` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a new plugin-internal review skill (`/superpowers-gstack:macos-native-review`) that validates PRDs, specs, and implementation plans for macOS apps against Apple Human Interface Guidelines via WebFetch citations. Bump plugin to v1.9.0. Refactor IDEAS.md to move macos entry out and add three sibling stubs (iOS, Windows, Android Material).

**Architecture:** Standalone plugin-internal skill, mirroring `pitfall-verification` and `quality-review` shape. 12 macOS-specific categories, each anchored to a default HIG URL on `developer.apple.com`. Strict per-finding citations with `PROVISIONAL` fallback when the site is unreachable. Auto-triggers via frontmatter description; Phase 0 self-check rejects non-macOS artifacts before category review begins.

**Tech Stack:** Markdown only. No code, no scripts. Validation via `grep` + manual reads. WebFetch for HIG URL verification.

---

## Context for the engineer (assume zero prior context)

**Repo:** `/Users/kjetilge/Developer/superpowers-gstack`. **All paths in this plan are relative to that repo root.** Run `cd /Users/kjetilge/Developer/superpowers-gstack` before starting.

**Approved spec:** `docs/superpowers/specs/2026-04-28-macos-native-review-design.md` (commit `2ccfad7` on `main`). Read it once at start; you should not need to re-read mid-plan since this plan inlines all content.

**Branch:** Work on `feat/macos-native-review` (created in Task 1). Do NOT work on `main`.

**Pre-flight expectations:** Working tree must be clean before Task 1. Only `.DS_Store` (gitignored) is acceptable as untracked. If real uncommitted changes exist, STOP and ask the user — this plan creates discrete commits and shouldn't bury someone else's work-in-progress.

**Genre conventions to mirror** (read these once for tone; the SKILL.md content in Task 3 is already tuned to match):
- `skills/pitfall-verification/SKILL.md` — 109 lines, terse
- `skills/quality-review/SKILL.md` — 235 lines, severity-tiered with output template

**Plugin-internal skill convention:** New plugin skills (this one, `pitfall-verification`, `quality-review`, `context-handoff`) are announced in `README.md` "What's Included" + a `CHANGELOG.md` entry — they are **NOT** added to the routing tables in `setup-routing/SKILL.md` or `adapt/SKILL.md`. Those tables surface upstream Superpowers/GStack skills only. Do not break this convention.

**Version-bump rule:** When `plugin.json` version changes, the version markers in `setup-routing/SKILL.md` and `adapt/SKILL.md` must change to match in the same commit. The SessionStart hook reads these markers; out-of-sync values will misfire on user projects.

---

## Task 1: Pre-flight and create feature branch

**Files:** No file changes; environment setup only.

- [ ] **Step 1: Verify working directory and clean tree**

```bash
cd /Users/kjetilge/Developer/superpowers-gstack
pwd
git status --short
```

Expected: `pwd` returns `/Users/kjetilge/Developer/superpowers-gstack`. `git status --short` returns either nothing or only `?? .DS_Store` / `?? skills/.DS_Store` lines (both gitignored). Anything else: STOP and ask the user.

- [ ] **Step 2: Verify on `main` and up to date with origin**

```bash
git rev-parse --abbrev-ref HEAD
git fetch origin main
git status -sb
```

Expected: branch is `main`. Status line is `## main...origin/main` (no "ahead" or "behind"). If behind, `git pull --ff-only` first. If ahead, STOP — there are unpushed commits to investigate.

- [ ] **Step 3: Verify spec exists and is committed**

```bash
git log --oneline -- docs/superpowers/specs/2026-04-28-macos-native-review-design.md
test -f docs/superpowers/specs/2026-04-28-macos-native-review-design.md && echo "spec present"
```

Expected: `git log` shows commit `2ccfad7` (or a later SHA if the spec was amended). `spec present` is printed.

- [ ] **Step 4: Create and switch to feature branch**

```bash
git checkout -b feat/macos-native-review
git rev-parse --abbrev-ref HEAD
```

Expected: `feat/macos-native-review` printed.

- [ ] **Step 5: Confirm plugin version baseline**

```bash
grep -E '^\s*"version"' .claude-plugin/plugin.json
grep -E 'version \*\*1\.' skills/setup-routing/SKILL.md skills/adapt/SKILL.md
```

Expected:
- `plugin.json`: `"version": "1.8.1",`
- `setup-routing/SKILL.md`: `**Version:** This skill writes version **1.8.1** ...`
- `adapt/SKILL.md`: `**Version check:** This skill is version **1.8.1**. ...`

If any is not 1.8.1, STOP — baseline is off, do not proceed.

(No commit in this task — branch creation is enough.)

---

## Task 2: Verify the 12 default HIG URLs via WebFetch

**Why this is its own task:** Apple periodically restructures HIG paths (the iOS 18 / macOS 15 information-architecture pass moved several pages). The skill ships with a category-default URL table; if any URL 404s, the skill is born broken. Verify before committing the SKILL.md.

**Files:** No file changes in this task — the verification result populates the URL slots in Task 3's SKILL.md draft. Update the table below with what you find, then carry the verified URLs forward.

- [ ] **Step 1: WebFetch each candidate URL — fill the table**

Run WebFetch on each URL below. Mark each as `OK` if the page loads with relevant content, or `MOVED → <new-url>` if the page redirects or 404s. If a URL has moved, find the new canonical path on `developer.apple.com/design/human-interface-guidelines/`.

| # | Category | Candidate URL | Result (fill in) |
|---|----------|----------------|------------------|
| 2 | Buttons | https://developer.apple.com/design/human-interface-guidelines/buttons | |
| 3 | Keyboards | https://developer.apple.com/design/human-interface-guidelines/keyboards | |
| 4a | Color | https://developer.apple.com/design/human-interface-guidelines/color | |
| 4b | Dark mode | https://developer.apple.com/design/human-interface-guidelines/dark-mode | |
| 5a | Sheets | https://developer.apple.com/design/human-interface-guidelines/sheets | |
| 5b | Popovers | https://developer.apple.com/design/human-interface-guidelines/popovers | |
| 5c | Alerts | https://developer.apple.com/design/human-interface-guidelines/alerts | |
| 6 | Motion | https://developer.apple.com/design/human-interface-guidelines/motion | |
| 7 | Privacy | https://developer.apple.com/design/human-interface-guidelines/privacy | |
| 8 | Accessibility | https://developer.apple.com/design/human-interface-guidelines/accessibility | |
| 9, 10b, 12 | The menu bar | https://developer.apple.com/design/human-interface-guidelines/the-menu-bar | |
| 10a | Windows | https://developer.apple.com/design/human-interface-guidelines/windows | |
| 11 | The Dock | https://developer.apple.com/design/human-interface-guidelines/the-dock | |

**WebFetch prompt template** (use for each URL):

> Fetch this Apple HIG page. Confirm the page loads (200) and is the canonical URL for the topic, not a redirect. Report: status code, page title, and one short verbatim quote (~10–25 words) representative of the page content. If the page 404s or the content is clearly off-topic, report the canonical URL by checking the HIG sidebar or homepage.

- [ ] **Step 2: Capture per-URL verbatim quotes**

For each `OK` URL, save a short verbatim quote (~10–25 words) from the page. These quotes are NOT pasted into the SKILL.md (the skill fetches its own quotes at review time), but they serve as a smoke test that the URLs return real HIG content. Save the quotes in a temporary scratch list — do not commit them.

- [ ] **Step 3: Resolve any moved URLs**

If any candidate is `MOVED`, update the canonical URL in the table above (in this plan file). The Task 3 SKILL.md template references this table — the engineer executing Task 3 will substitute the verified URLs.

- [ ] **Step 4: Decision gate**

If 0 URLs moved: proceed to Task 3 with the candidate URLs as-is.

If 1–3 URLs moved: proceed to Task 3 with verified URLs substituted into the SKILL.md template at the marked spots.

If 4+ URLs moved: STOP. Apple has done a major HIG restructure; this plan needs review. Surface to the user with the list of moved URLs and proposed canonical replacements before continuing.

(No commit in this task — verification result is captured in this plan file's table for Task 3 to reference.)

---

## Task 3: Write `skills/macos-native-review/SKILL.md`

**Files:**
- Create: `skills/macos-native-review/SKILL.md`

The full content draft is below. Substitute the verified URLs from Task 2 into the category-default URL table. Otherwise, copy verbatim.

- [ ] **Step 1: Create the directory**

```bash
mkdir -p skills/macos-native-review
ls -la skills/macos-native-review/
```

Expected: empty directory exists.

- [ ] **Step 2: Write `skills/macos-native-review/SKILL.md` with the following content**

```markdown
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
| 11 | Dock icon behavior | https://developer.apple.com/design/human-interface-guidelines/the-dock |
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

Does click-on-dock-icon (when app is hidden / in background) reactivate the main window? Is a dock menu defined for relevant commands? Are badge counts used (and HIG-conformant) where appropriate?

Risk surfaces: dock-icon UX; background/foreground transitions.

Cite: https://developer.apple.com/design/human-interface-guidelines/the-dock

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
```

- [ ] **Step 3: Verify file written**

```bash
wc -l skills/macos-native-review/SKILL.md
head -5 skills/macos-native-review/SKILL.md
```

Expected: line count between 250–320 (allow ±15% from the ~285-line draft). First 5 lines are the frontmatter block (`---`, `name:`, `description:`, `---`, blank). Frontmatter `name` is exactly `macos-native-review`. Frontmatter `description` starts with `Use after a PRD, spec, or implementation plan for a macOS app or feature`.

- [ ] **Step 4: Substitute Task 2's verified URLs (if any moved)**

If Task 2 found any moved URLs, edit `skills/macos-native-review/SKILL.md` to replace each candidate URL with the canonical one. Use Edit tool, not sed. Verify substitution:

```bash
grep -c "developer.apple.com/design/human-interface-guidelines" skills/macos-native-review/SKILL.md
```

Expected: at least 18 hits (12 in the table + 6+ inline in the categories).

- [ ] **Step 5: Commit**

```bash
git add skills/macos-native-review/SKILL.md
git commit -m "$(cat <<'EOF'
feat: add /macos-native-review skill (HIG-citation-grounded)

Validates PRDs, specs, and implementation plans for macOS apps against
Apple Human Interface Guidelines via WebFetch citations. 12 categories
covering vocabulary, controls, shortcuts, semantic colors, sheets,
animation, privileged ops, accessibility, menu bar, app lifecycle,
dock, and App menu.

Severity-tiered (CRITICAL/SIGNIFICANT/POLISH) with strict per-finding
citations. PROVISIONAL fallback when developer.apple.com unreachable.
Phase 0 self-check rejects non-macOS artifacts before category review.

Per spec docs/superpowers/specs/2026-04-28-macos-native-review-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds with the message above.

---

## Task 4: Bump plugin version to 1.9.0 across plugin.json + setup-routing + adapt

**Files:**
- Modify: `.claude-plugin/plugin.json` (line containing `"version": "1.8.1"`)
- Modify: `skills/setup-routing/SKILL.md` (line containing `**Version:** This skill writes version **1.8.1**`)
- Modify: `skills/adapt/SKILL.md` (line containing `**Version check:** This skill is version **1.8.1**`)

The three files MUST stay in lockstep: a SessionStart hook reads the version markers, and divergence causes false "needs adapt" warnings on user projects.

- [ ] **Step 1: Bump `.claude-plugin/plugin.json`**

Use Edit tool. Replace the line:

```
  "version": "1.8.1",
```

with:

```
  "version": "1.9.0",
```

- [ ] **Step 2: Bump `skills/setup-routing/SKILL.md`**

Use Edit tool. Replace:

```
**Version:** This skill writes version **1.8.1** into the CLAUDE.md version marker.
```

with:

```
**Version:** This skill writes version **1.9.0** into the CLAUDE.md version marker.
```

- [ ] **Step 3: Bump `skills/adapt/SKILL.md`**

Use Edit tool. Replace:

```
**Version check:** This skill is version **1.8.1**. If the project's CLAUDE.md contains a version marker (`<!-- superpowers-gstack: X.Y.Z -->`) with an older version, inform the user that routing and session rules will be updated to the current version as part of this adaptation.
```

with:

```
**Version check:** This skill is version **1.9.0**. If the project's CLAUDE.md contains a version marker (`<!-- superpowers-gstack: X.Y.Z -->`) with an older version, inform the user that routing and session rules will be updated to the current version as part of this adaptation.
```

- [ ] **Step 4: Verify all three files match**

```bash
grep '"version"' .claude-plugin/plugin.json
grep 'version \*\*1\.' skills/setup-routing/SKILL.md skills/adapt/SKILL.md
grep -rn '"version": "1\.8\.1"' .claude-plugin/ 2>/dev/null
grep -rn 'version \*\*1\.8\.1\*\*' skills/ 2>/dev/null
```

Expected:
- `plugin.json`: `"version": "1.9.0",`
- `setup-routing/SKILL.md` and `adapt/SKILL.md`: both show `**1.9.0**`
- Last two `grep -rn` (looking for stale 1.8.1 references): no matches.

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/plugin.json skills/setup-routing/SKILL.md skills/adapt/SKILL.md
git commit -m "$(cat <<'EOF'
chore(v1.9.0): bump plugin version and skill version markers

plugin.json 1.8.1 → 1.9.0 (minor — new /macos-native-review skill).
setup-routing and adapt version markers move in lockstep so the
SessionStart hook detects v1.9.0-needed adaptations correctly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Update `README.md` "What's Included" section

**Files:**
- Modify: `README.md` (the "What's Included" section, currently lists five plugin skills)

- [ ] **Step 1: Locate the section**

```bash
grep -n "Claude Code Plugin\* with five skills" README.md
```

Expected: returns the line number (around line 32) of `- **Claude Code Plugin** with five skills:`.

- [ ] **Step 2: Edit the section**

Use Edit tool. Replace this block:

```
- **Claude Code Plugin** with five skills:
  - `/setup-routing` — Generates a tailored CLAUDE.md for new projects
  - `/adapt` — Adds routing to existing projects without losing your CLAUDE.md content
  - `/context-handoff` — Writes a human-readable handoff to `docs/superpowers/handoff.md` before `/clear` or `/compact`. Auto-resumes on next session start. Different from gstack's `/context-save` — this lives in the repo and works cross-machine.
  - `/pitfall-verification` — Final-check skill run after any PRD, spec, plan, or code artifact. Targeted check that typical pitfalls for that artifact type and domain (security, idempotency, contracts, edge cases, LLM output) actually do not apply. Two rounds max.
  - `/quality-review` — Perceived-quality gate run after a PRD, spec, or implementation plan, before implementation begins. Hunts pitfalls that make a product feel cheap or broken even when it technically works (silent failures, missing loading/empty states, error recovery, state drift, animations, AI output, sudo flows). Complementary to `/pitfall-verification`: that one asks "will this work?", this one asks "will this feel good?".
```

with:

```
- **Claude Code Plugin** with six skills:
  - `/setup-routing` — Generates a tailored CLAUDE.md for new projects
  - `/adapt` — Adds routing to existing projects without losing your CLAUDE.md content
  - `/context-handoff` — Writes a human-readable handoff to `docs/superpowers/handoff.md` before `/clear` or `/compact`. Auto-resumes on next session start. Different from gstack's `/context-save` — this lives in the repo and works cross-machine.
  - `/pitfall-verification` — Final-check skill run after any PRD, spec, plan, or code artifact. Targeted check that typical pitfalls for that artifact type and domain (security, idempotency, contracts, edge cases, LLM output) actually do not apply. Two rounds max.
  - `/quality-review` — Perceived-quality gate run after a PRD, spec, or implementation plan, before implementation begins. Hunts pitfalls that make a product feel cheap or broken even when it technically works (silent failures, missing loading/empty states, error recovery, state drift, animations, AI output, sudo flows). Complementary to `/pitfall-verification`: that one asks "will this work?", this one asks "will this feel good?".
  - `/macos-native-review` — Apple-native conformance gate for macOS PRDs, specs, and plans. 12 HIG-citation-grounded categories: vocabulary, control choices, keyboard shortcuts, semantic colors, sheets/popovers/alerts, animation timing, privileged operations, accessibility, menu bar, app lifecycle, dock behavior, App menu. Every finding cites a `developer.apple.com` HIG page via WebFetch. Phase 0 self-check rejects non-macOS artifacts. Complementary to `/pitfall-verification` ("will this work?") and `/quality-review` ("will this feel good?") — this asks "is this Apple-native?".
```

- [ ] **Step 3: Verify edit**

```bash
grep -A1 "Claude Code Plugin\* with" README.md | head -3
grep -c "^  - \`/" README.md
```

Expected:
- First grep shows `- **Claude Code Plugin** with six skills:`
- Second grep returns at least 6 (one per bullet — and any other backtick-prefixed lines further down should not collide, but verify there aren't more bullets than expected).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs(readme): announce /macos-native-review in What's Included

Six skills now (was five). Bullet describes the 12-category HIG-cited
review and its place between pitfall-verification and quality-review.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Add `[1.9.0]` entry to `CHANGELOG.md`

**Files:**
- Modify: `CHANGELOG.md` (insert new section above the `[1.8.1]` entry)

- [ ] **Step 1: Verify the current top of the file**

```bash
head -20 CHANGELOG.md
```

Expected: line 1 is `# Changelog`, line 3 is `## [1.8.1] - 2026-04-28`.

- [ ] **Step 2: Insert the new entry**

Use Edit tool. Replace:

```
# Changelog

## [1.8.1] - 2026-04-28
```

with:

```
# Changelog

## [1.9.0] - 2026-04-28

### Added
- **`/macos-native-review` skill** — Apple-native conformance gate for macOS PRDs, specs, and implementation plans. Walks 12 HIG-grounded categories (vocabulary, control choices, keyboard shortcuts, semantic colors, sheets/popovers/alerts, animation timing, privileged operations, accessibility, menu bar, app lifecycle, dock icon behavior, App menu) and cites `developer.apple.com/design/human-interface-guidelines/...` for every finding via WebFetch. Phase 0 self-check rejects non-macOS artifacts (returns `N/A` for iOS-only or non-Apple projects). `PROVISIONAL` fallback when the HIG site is unreachable — never silently substitutes training-data recall for verified citations. Sequential after `/pitfall-verification` and `/quality-review`: that pair asks *"will this work?"* and *"will this feel good?"*; this asks *"is this Apple-native?"*. Sibling skills (`ios-native-review`, `windows-native-review`, `material-design-review`) deferred as IDEAS.md backlog entries with consistent template.

### Changed
- `setup-routing` and `adapt` version markers bumped to 1.9.0.
- IDEAS.md: removed the `macos-native-review` proposal entry (skill shipped); added three sibling stubs (`ios-native-review`, `windows-native-review`, `material-design-review`) using the same Gap/Scope/Method/Differentiation/Status template.

## [1.8.1] - 2026-04-28
```

- [ ] **Step 3: Verify**

```bash
head -15 CHANGELOG.md
grep -c "^## \[" CHANGELOG.md
```

Expected:
- First few lines show the new `[1.9.0]` entry above `[1.8.1]`.
- Total `## [` headings increased by 1 from baseline (run `git show main:CHANGELOG.md | grep -c '^## \['` to confirm baseline).

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
docs(changelog): add [1.9.0] entry for /macos-native-review

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Refactor `IDEAS.md` — remove macOS entry, add three sibling stubs

**Files:**
- Modify: `IDEAS.md` (replace the `macos-native-review` entry with a "Shipped" reference, then add three deferred sibling entries)

- [ ] **Step 1: Read the current file**

```bash
cat IDEAS.md
```

Expected: file currently contains a header, intro, and the full `macos-native-review (proposed 2026-04-28)` entry (~50 lines).

- [ ] **Step 2: Rewrite the file**

Use Write tool to replace the entire content with:

```markdown
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
```

- [ ] **Step 3: Verify the file**

```bash
wc -l IDEAS.md
grep -c "^## " IDEAS.md
grep -c "^- \*\*" IDEAS.md
```

Expected:
- ~110–130 lines total
- `## ` headings: 4 (the three deferred entries + "Shipped")
- `**Gap.**` / `**Scope.**` etc. lines: at least 12 (4 per deferred entry × 3 entries, plus the intro list).

- [ ] **Step 4: Commit**

```bash
git add IDEAS.md
git commit -m "$(cat <<'EOF'
docs(ideas): refactor backlog — macos shipped, three siblings deferred

Removes the macos-native-review proposal entry (skill is now shipped
in v1.9.0; added a "Shipped" pointer at the bottom of the file).

Adds three new deferred entries with consistent Gap/Scope/Method/
Differentiation/Status template:
- ios-native-review (touch, nav paradigm, sheet detents, Dynamic Island)
- windows-native-review (Fluent Design, WinUI 3, taskbar, mica)
- material-design-review (Material 3, dynamic color, motion, density)

The template gives whoever picks up the next sibling a head start.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Smoke test — run the skill mentally on a synthetic 1-page macOS spec

**Why:** The skill is purely instructions; there's no unit test that can validate it works. The cheapest end-to-end check is to walk a synthetic spec containing intentional flaws through the skill in your head, verify each flaw produces the right finding with citation, and confirm the verdict matches expectations.

**Files:** No file changes; this task produces only a transient walkthrough document that you keep in scratch and do NOT commit.

- [ ] **Step 1: Compose a synthetic spec with intentional flaws**

Treat this as the artifact under review:

```
SPEC: Tweaks — macOS menu bar utility for adjusting system settings

§1. Overview
Tweaks is a SwiftUI menu bar app for macOS 13+. Users open the app from the
menu bar (MenuBarExtra) and adjust system tweaks via a single Preferences
window.

§2. UI surfaces
- Menu bar icon: gear icon, click to open popover with quick settings
- Preferences window (⌘W to quit, ⌘P to open Preferences): tabs for
  Display, Sound, Keyboard, Mouse
- "Apply Tweaks" button uses #007AFF blue; status indicator turns
  red on error
- Modal sheet appears when Tweak requires admin auth; sheet has
  no Cancel button — only "Continue"
- Animations use SwiftUI default (.easeInOut, 0.3s) for sheet
  present/dismiss
- About panel: just shows app name and version

§3. Permissions
When the app needs admin rights, a toast appears at the top of the
window saying "We need admin access" and the system password prompt
fires.
```

- [ ] **Step 2: Walk the 12 categories mentally; document expected findings**

In a scratch doc (not committed), list what the skill SHOULD find. Compare to your expected list of intentional flaws:

| # | Category | Expected finding | Severity |
|---|----------|------------------|----------|
| 1 | Vocabulary | "Preferences" used instead of "Settings…" (macOS 13+) | CRITICAL |
| 1 | Vocabulary | App name "Tweaks" — flag as non-Apple-canonical for system-settings domain (Apple says "System Settings") | POLISH |
| 2 | Buttons | (no obvious flaw — flag as N/A for spec-level review) | N/A |
| 3 | Keyboards | `⌘W` is bound to Quit instead of Close Window | CRITICAL |
| 3 | Keyboards | `⌘P` for Preferences is non-standard; canonical is `⌘,` for Settings | SIGNIFICANT |
| 4 | Colors | Hardcoded `#007AFF` instead of `Color.accentColor` (won't respect user accent) | SIGNIFICANT |
| 4 | Dark mode | No dark-mode story specified | SIGNIFICANT |
| 5 | Sheets | Modal sheet has no Cancel button — HIG mandates dismiss mechanism | CRITICAL |
| 6 | Animation | Generic `.easeInOut` — no signature motion | SIGNIFICANT |
| 7 | Privileged ops | Permission framed as toast instead of explanation sheet with rationale | SIGNIFICANT |
| 8 | Accessibility | No VoiceOver labels for menu bar icon, no Dynamic Type story | SIGNIFICANT |
| 9 | Menu bar | Spec doesn't define a menu bar (File/Edit/View/Window/Help) — only the MenuBarExtra | SIGNIFICANT (likely intentional for a menu-bar-only app, but spec should call this out) |
| 10 | App lifecycle | "⌘W to quit" is wrong; spec needs to address proper Q/W semantics | (subsumed by category 3 finding) |
| 11 | Dock | No mention of dock-icon behavior (and a MenuBarExtra-only app may not have a dock icon — spec should specify `LSUIElement`) | POLISH |
| 12 | App menu | About panel missing copyright, build number, credits | POLISH |

Expected verdict: **NEEDS PATCH** (3 CRITICAL findings).

- [ ] **Step 3: Validate the skill instructions cover each expected finding**

Open `skills/macos-native-review/SKILL.md` and confirm:
- The 12 categories include the question that surfaces each expected finding (e.g. "is `⌘P` the canonical shortcut?" is covered by category 3 — keyboards — which lists ⌘, as the canonical Settings shortcut implicitly via "macOS-standard shortcuts").
- The output format example matches the structure your scratch list uses.
- The severity rubric examples (`Cmd-Q` only closes window, `Picker` instead of Segmented Control, missing dark-mode story) match the kinds of findings the synthetic spec produces.

If any expected finding has no obvious category to land in, the skill's instructions are missing a question. Edit `skills/macos-native-review/SKILL.md` to extend the relevant category. Re-commit if changes were needed.

- [ ] **Step 4: Confirm Phase 0 self-check passes the synthetic spec**

The synthetic spec mentions "SwiftUI", "menu bar app for macOS 13+", "MenuBarExtra", "Preferences window". Phase 0 should match on `SwiftUI` import context, `MenuBarExtra` type reference, and explicit "macOS" text. Verdict: proceed to category review.

If Phase 0 instructions don't cover these signals, edit `skills/macos-native-review/SKILL.md` Phase 0 section.

- [ ] **Step 5: No commit needed**

This task is a walkthrough; no artifact is committed. If Step 3 or 4 surfaced edits to `SKILL.md`, those edits should already be committed (under their own commit, "fix: address smoke-test gap in <category>") before proceeding to Task 9.

---

## Task 9: Cross-file consistency verification

**Why:** With 7 files touched across 6 commits (skill, version markers ×3, README, CHANGELOG, IDEAS), drift is the dominant risk. This task is a focused read of all modified files end-to-end.

**Files:** No new file changes (unless drift is found, in which case fix inline + commit).

- [ ] **Step 1: Confirm version numbers match across all version-bearing files**

```bash
echo "--- plugin.json ---"
grep '"version"' .claude-plugin/plugin.json
echo "--- setup-routing ---"
grep 'version \*\*' skills/setup-routing/SKILL.md
echo "--- adapt ---"
grep 'version \*\*' skills/adapt/SKILL.md
echo "--- CHANGELOG top entry ---"
head -3 CHANGELOG.md
echo "--- IDEAS.md shipped reference ---"
grep -A1 "^## Shipped" IDEAS.md | tail -1
```

Expected: every line shows `1.9.0` (and CHANGELOG header is `## [1.9.0] - 2026-04-28`).

If any file shows a different version: STOP, edit the offender, commit a fix.

- [ ] **Step 2: Confirm CHANGELOG voice matches prior entries**

```bash
sed -n '/## \[1.9.0\]/,/## \[1.8.1\]/p' CHANGELOG.md
```

Expected: voice and structure match `[1.8.0]` (a multi-paragraph "Added" bullet for the new skill, plus a short "Changed" section). Compare against the `[1.8.0]` entry below in the file.

If the voice is jarringly different (e.g. terse "Bumped X" vs multi-paragraph context-rich), revise the `[1.9.0]` entry.

- [ ] **Step 3: Confirm README "What's Included" lists six skills in the right order**

```bash
grep -A8 "Claude Code Plugin\* with" README.md | head -10
```

Expected: header says "six skills"; the bullet order is `setup-routing`, `adapt`, `context-handoff`, `pitfall-verification`, `quality-review`, `macos-native-review`. Each bullet is one-paragraph, prose style, mirroring the others.

- [ ] **Step 4: Confirm IDEAS.md has no leftover stale references**

```bash
grep -i "macos-native-review (proposed" IDEAS.md
grep -c "deferred" IDEAS.md
grep -c "## " IDEAS.md
```

Expected:
- First grep returns no matches (the proposal entry was removed; only the "Shipped" pointer remains).
- "deferred" count: at least 3 (one per sibling entry).
- `## ` heading count: 4 (`ios-native-review`, `windows-native-review`, `material-design-review`, `Shipped`).

- [ ] **Step 5: Confirm the new SKILL.md is well-formed**

```bash
head -3 skills/macos-native-review/SKILL.md
grep -c "^### " skills/macos-native-review/SKILL.md
grep -c "developer.apple.com" skills/macos-native-review/SKILL.md
```

Expected:
- First 3 lines are `---`, `name: macos-native-review`, `description: ...`.
- `### ` heading count: 12 (one per category), give or take ±1 if the categories include sub-headings under "How to run the check" — open the file to confirm.
- `developer.apple.com` count: at least 18 (12 in the table + several inline category citations).

- [ ] **Step 6: Confirm git log is clean and tells the right story**

```bash
git log --oneline main..HEAD
```

Expected (one commit per task that creates artifacts):
1. `feat: add /macos-native-review skill (HIG-citation-grounded)`
2. `chore(v1.9.0): bump plugin version and skill version markers`
3. `docs(readme): announce /macos-native-review in What's Included`
4. `docs(changelog): add [1.9.0] entry for /macos-native-review`
5. `docs(ideas): refactor backlog — macos shipped, three siblings deferred`

(Plus any "fix: smoke-test gap" commit from Task 8 if smoke test surfaced gaps.)

If the order is wrong, the messages are wrong, or commits are missing: STOP, address before Task 10.

- [ ] **Step 7: No commit unless drift was found**

This task is a verification round. Any fixes are committed under their own targeted commit (e.g. `fix: align README skill order`).

---

## Task 10: Push branch and open PR

**Files:** No file changes; remote-only operations.

- [ ] **Step 1: Push the branch**

```bash
git push -u origin feat/macos-native-review
```

Expected: push succeeds; output includes `* [new branch]      feat/macos-native-review -> feat/macos-native-review`.

- [ ] **Step 2: Open the PR**

```bash
gh pr create \
  --base main \
  --head feat/macos-native-review \
  --title "feat(v1.9.0): /macos-native-review — HIG-citation-grounded skill for macOS specs" \
  --body "$(cat <<'EOF'
## Summary

Adds a new plugin-internal review skill, `/superpowers-gstack:macos-native-review`, that validates PRDs, specs, and implementation plans for macOS apps against Apple Human Interface Guidelines via WebFetch citations. 12 macOS-specific categories, severity-tiered findings, strict per-finding HIG URL citations, `PROVISIONAL` fallback when developer.apple.com is unreachable.

Sequential after `pitfall-verification` and `quality-review` for macOS artifacts:

| Skill | Lens | Question |
|-------|------|----------|
| `pitfall-verification` | Correctness | "Will this work?" |
| `quality-review` | Perceived quality | "Will this feel good?" |
| `macos-native-review` | Apple-native conformance | "Is this Apple-native?" |

Phase 0 self-check rejects non-macOS artifacts before category review (returns `N/A` for iOS-only or non-Apple projects).

Sibling skills (`ios-native-review`, `windows-native-review`, `material-design-review`) deferred as IDEAS.md backlog entries with a consistent template, shipped via this PR's IDEAS.md refactor.

## Provenance

- Brainstorming: in-session 2026-04-28 (5 question/answer rounds, A-A-B-A-B)
- Approved spec: `docs/superpowers/specs/2026-04-28-macos-native-review-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-28-macos-native-review-implementation.md`

## Test plan

- [ ] Skill file is well-formed (frontmatter, 12 categories, 12-row default-URL table, output template, severity rubric, "What this skill is NOT")
- [ ] All 12 default HIG URLs return 200 via WebFetch (verified during Task 2)
- [ ] Plugin version markers match across `plugin.json`, `setup-routing/SKILL.md`, `adapt/SKILL.md` (1.9.0)
- [ ] README "What's Included" lists six skills, `macos-native-review` bullet matches the others' tone
- [ ] CHANGELOG `[1.9.0]` entry voice matches prior entries
- [ ] IDEAS.md: macOS proposal entry removed, three sibling stubs present, "Shipped" pointer at the bottom
- [ ] Smoke test: synthetic 1-page spec walked through skill mentally, expected findings produce the right severity verdict (Task 8)
- [ ] Skill is discoverable in Claude Code skill list after `gh pr merge` and `/plugin update superpowers-gstack`

## Out of scope (deferred)

- iOS / Windows / Android sibling skills — backlog
- Adding `/macos-native-review` to user-level CLAUDE.md verification process — user's call
- Cross-references in `quality-review` / `pitfall-verification` to point at the new skill — separate change if value emerges in real use
EOF
)"
```

Expected: PR URL is printed.

- [ ] **Step 3: Confirm PR is open and not in CONFLICTING state**

```bash
PR_NUM=$(gh pr view --json number -q .number)
echo "PR: $PR_NUM"
gh pr view "$PR_NUM" --json mergeable,mergeStateStatus,statusCheckRollup
```

Expected: `mergeable: MERGEABLE` (after a few seconds for GitHub to compute). `mergeStateStatus: CLEAN` or `BEHIND` (depends on whether anything new landed on `main`).

If `CONFLICTING`: there's a conflict to resolve. Likely a CHANGELOG line. Pull `main` into the branch with `git pull origin main --no-rebase` (or rebase, depending on team policy), resolve, push.

- [ ] **Step 4: Surface the PR URL to the user**

Print the URL prominently. The user reviews and merges manually — do NOT auto-merge.

---

## Post-plan

After this plan completes:

1. **Run pitfall-verification on the plan itself.** Per user-level CLAUDE.md ("Pitfall verification: invoker `superpowers-gstack:pitfall-verification` ... Kjør automatisk etter `writing-specs`, `writing-plans`, `executing-plans`..."), the plan should be checked once before execution starts.
2. **User reviews the PR**, merges (squash or merge-commit per their preference), and the v1.9.0 plugin update propagates via marketplace cache invalidation (the version bump in Task 4 is what triggers it).

---

## Self-review notes (for the plan author)

**Spec coverage check (against `docs/superpowers/specs/2026-04-28-macos-native-review-design.md`):**

- §3 architecture (standalone, not parametrized) → Task 3 produces a single SKILL.md, no parent file ✓
- §4 12 categories → Task 3 SKILL.md has 12 numbered category sections ✓
- §5 strict citation discipline + PROVISIONAL fallback → Task 3 SKILL.md "Citation discipline" + "Fallback when developer.apple.com unreachable" sub-sections ✓
- §6.1 sequential after quality-review → Task 3 SKILL.md "Relationship" table + "Recommended flow" ✓
- §6.2 Phase 0 self-check → Task 3 SKILL.md "Phase 0" section ✓
- §7 output format → Task 3 SKILL.md "Output format" section ✓
- §8 severity rubric → Task 3 SKILL.md "Severity rubric" section ✓
- §9 skill format (12 sections in order) → Task 3 SKILL.md follows the order ✓
- §10 IDEAS.md cleanup (remove macOS, add 3 sibling stubs) → Task 7 ✓
- §11 delivery scope (skill + version bump + README + CHANGELOG + version markers + IDEAS.md) → Tasks 3–7 ✓
- §12 risks: HIG URL drift → Task 2 verifies URLs; multi-target false negative → Task 3 Phase 0 explicitly addresses; PROVISIONAL fallback → Task 3 ✓

**Placeholder scan:** No `TBD`, no `TODO`, no `add appropriate X`. Each task has full content inline. Task 2 has a fill-in table for verification results, which is intentional — the verification produces data that adjusts Task 3's URL substitutions.

**Type / name consistency:** Skill name `macos-native-review` used identically in: filename (`skills/macos-native-review/SKILL.md`), frontmatter `name`, invocation command (`/superpowers-gstack:macos-native-review`), README bullet, CHANGELOG entry, IDEAS.md "Shipped" pointer, PR title and body. Spot-checked.

**Cross-task references:** Task 3 refers to URLs verified in Task 2. Task 9 cross-checks Tasks 3–7 outputs. Task 10 references the SKILL.md from Task 3 and the spec/plan paths. No dangling references.
