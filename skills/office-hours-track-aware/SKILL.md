---
name: office-hours-track-aware
description: |
  Track-aware wrapper around gstack's /office-hours skill. Runs the
  upstream office-hours session (six forcing questions / builder mode),
  detects native vs web intent from the resulting design doc, asks the
  platform question (iOS / macOS / both) if native, writes .gstack/track,
  renders DESIGN.html via htmlify and OPENS it in Safari BEFORE the
  approval gate, then asks "Approve / Revise / Restart" — fixing the
  upstream "approve-then-read" UX bug. On approval for native projects,
  suggests /superpowers-gstack:swiftui-design-consultation as next step.
  Replaces standalone swiftui-track skill (removed in v2.3.0).
  Use when starting a new product idea, brainstorming, or whenever
  upstream /office-hours would have fired. Set up via CLAUDE.md routing
  to intercept bare /office-hours invocations.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - AskUserQuestion
  - Skill
chains_to:
  - office-hours (gstack — upstream)
  - htmlify
  - swiftui-design-consultation
replaces:
  - swiftui-track (v2.2.0)
---

# /superpowers-gstack:office-hours-track-aware

Track-aware wrapper around gstack's /office-hours. The "right" flow:

1. Run upstream office-hours to completion (it writes design.md)
2. Read design.md, infer track from content
3. Ask platform question if native (one-time per project)
4. Write `.gstack/track`
5. Render + auto-open DESIGN.html in Safari **before approval**
6. Ask approval question (Approve / Revise / Restart) **after** user has read
7. On approval + native: suggest swiftui-design-consultation

## Phase 0 — Setup

### Step 0.0: Initialize $SLUG via gstack-slug

Same pattern as swiftui-design-consultation (defensive fallback):

```bash
SLUG_OUTPUT=$(~/.claude/skills/gstack/bin/gstack-slug 2>/dev/null)
if [ -n "$SLUG_OUTPUT" ]; then
  eval "$SLUG_OUTPUT"
fi
if [ -z "${SLUG:-}" ]; then
  SLUG="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")"
  export SLUG
fi
if [ -z "$SLUG" ] || [ "$SLUG" = "/" ]; then
  echo "FATAL: could not derive SLUG. Aborting." >&2
  exit 1
fi
mkdir -p ~/.gstack/projects/"$SLUG"
echo "SLUG: $SLUG"
```

### Step 0.1: Read existing track marker if present

```bash
mkdir -p .gstack
EXISTING_TRACK=""
if [ -f .gstack/track ]; then
  EXISTING_TRACK=$(cat .gstack/track | tr -d '[:space:]')
fi
echo "EXISTING_TRACK: ${EXISTING_TRACK:-none}"
```

If `EXISTING_TRACK` is already set, skip the platform-question in Phase 3.

## Phase 1 — Run upstream office-hours

Invoke gstack's office-hours via the Skill tool, letting it complete its
normal flow (product context, six forcing questions or builder mode,
write design doc).

```
Skill(skill="office-hours", args="")
```

Note: gstack's office-hours writes the design doc somewhere. Per recent
global CLAUDE.md update (commit f8e6acb and later), the default is
`docs/` under the project root. Older sessions may still write to
`~/super-me/brain/ideas/seeds/` if their CLAUDE.md snapshot is stale.

After the wrapped call completes, locate the just-written design doc:

```bash
# Most recently modified design-doc-like .md file from the last 5 min
RECENT_MD=$(find . docs ~/super-me/brain/ideas/seeds 2>/dev/null \
  -type f -name '*.md' -mmin -5 \
  ! -path '*/node_modules/*' ! -path '*/.git/*' \
  -exec ls -t {} + 2>/dev/null | head -1)
echo "DESIGN_DOC: $RECENT_MD"
```

If `$RECENT_MD` is under `~/super-me/`, **move it to `docs/` under the
repo root** (consistent with current global CLAUDE.md policy):

```bash
if [[ "$RECENT_MD" == "$HOME/super-me/"* ]]; then
  mkdir -p docs
  BASENAME=$(basename "$RECENT_MD")
  TARGET="docs/$BASENAME"
  # Collision-safe: if target exists, append a unique suffix so we
  # never silently overwrite an earlier design doc.
  if [ -e "$TARGET" ]; then
    TS=$(date +%Y%m%d-%H%M%S)
    TARGET="docs/${BASENAME%.md}-$TS.md"
    echo "Note: docs/$BASENAME already existed; saving new doc as $TARGET"
  fi
  mv "$RECENT_MD" "$TARGET"
  # If there's a paired HTML companion, move that too (with same collision check)
  HTML_PEER="${RECENT_MD%.md}.html"
  if [ -f "$HTML_PEER" ]; then
    HTML_TARGET="docs/$(basename "$HTML_PEER")"
    if [ -e "$HTML_TARGET" ]; then
      HTML_TARGET="docs/$(basename "${HTML_PEER%.html}")-$(date +%Y%m%d-%H%M%S).html"
    fi
    mv "$HTML_PEER" "$HTML_TARGET"
  fi
  RECENT_MD="$TARGET"
  echo "Moved design doc to repo-local: $TARGET"
fi
```

## Phase 2 — Intent inference

Read `$RECENT_MD`. Scan content for native vs web signals.

**Native signals** (case-insensitive, word-boundary):
- `SwiftUI`, `UIKit`, `AppKit`, `Swift`
- `iOS`, `iPadOS`, `macOS`, `watchOS`, `tvOS`, `visionOS`
- `Xcode`, `App Store`, `TestFlight`
- `native Apple`, `Mac app`, `iPhone app`, `iPad app`, `Apple Silicon`

**Web signals**:
- `Next.js`, `React`, `Vue`, `Svelte`, `Angular`
- `Node.js`, `Express`, `Fastify`, `Django`, `Rails`, `Flask`
- `web app`, `webapp`, `dashboard`, `landing page`, `marketing site`
- `npm`, `yarn`, `pnpm`, `Vercel`, `Netlify`

**Inference rule:**

```
native_count = count of native-signal matches
web_count = count of web-signal matches

if native_count > 0 AND web_count == 0:
    track = "native"
if web_count > 0 AND native_count == 0:
    track = "web"
if native_count > 0 AND web_count > 0:
    track = "ambiguous"  # mixed signals — ask user
if both == 0:
    track = "unknown"  # default to web silently
```

## Phase 3 — Platform question (only if native or ambiguous)

If `$EXISTING_TRACK` is already set: skip this step entirely.

If track is `native`: ask the platform question.

If track is `ambiguous`: prepend a paragraph explaining the mixed signals
were found and confirming this is a native project before asking platform.

If track is `web` or `unknown`: skip — no marker is written (matches
gstack default behavior).

AskUserQuestion brief:

```
D1 — Which platform target does this project ship to?
Project/branch/task: declaring SwiftUI track based on inferred native intent
ELI10: I detected native Apple-platform signals in the office-hours
  output. This is a one-time project decision telling the rest of the
  plugin whether you're building for iPhone/iPad, Mac, or both — so
  generated Swift Package files and design defaults match.
Stakes if we pick wrong: Package.swift declares wrong platforms; easy
  to re-run later to change. No permanent damage.
Recommendation: iOS only (most common case for new projects)
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) iOS only (recommended)
  ✅ Most common case; smallest Package.swift
  ✅ iPadOS works automatically via iOS target
  ❌ No macOS companion — add later by re-running
B) macOS only
  ✅ Right for menu-bar tools, productivity apps, system utilities
  ✅ Liquid Glass strategy tuned for macOS chrome
  ❌ No phone/tablet — narrows reach
C) Both iOS + macOS
  ✅ Cross-platform Swift Package; max reach
  ✅ One design system serves both
  ❌ More #if os() surfaces; longer compile times
Net: pick where you'll first ship, not where you might eventually ship.
```

Write the chosen value (`ios`, `macos`, or `both`) to `.gstack/track`:

```bash
echo "$CHOICE" > .gstack/track
```

Report:
- `Track set: <value>` (new)
- `Track changed: <old> → <new>` (overwrite)
- `Track already set: <value> (no change)` (no-op)

## Phase 4 — htmlify + auto-open BEFORE approval

This is the UX fix vs upstream office-hours. The design doc is opened in
Safari so the user can READ it before deciding.

**Decide rendering tier:**

- v1 (basic): default, always works
- v2 (rich, with plan): if the design doc has structure that benefits
  (e.g., "Approaches Considered" → comparison-matrix; architecture
  section with nodes/arrows → flowchart-svg), build a plan JSON.

Quick heuristics for v2 plan generation:

```
if design_doc contains heading matching "Approach(es)" or "Options Considered":
    add comparison-matrix section
if design_doc contains heading matching "Architecture" with ASCII boxes:
    add flowchart-svg section
if design_doc contains memorable single-sentence quote:
    add pullquote
if design_doc has "Note:" / "Warning:" / "Insight:" callouts:
    add callout-box
ALWAYS add a feedback_panel — even minimal (just custom_questions: comment)
```

If at least 2 v2 treatments apply, write a plan JSON to
`/tmp/office-hours-plan-$TS.json` and invoke v2 rendering. Otherwise, v1.

**Invoke htmlify via Skill tool with `--open`:**

```
Skill(skill="superpowers-gstack:htmlify",
      args="<absolute path to design doc> [--plan /tmp/office-hours-plan-$TS.json] --open")
```

The `--open` flag closes existing Safari windows and opens the just-
rendered HTML alone. User now reads in a distraction-free reader view.

**Tell the user explicitly:**

```
Design-doc'en er åpnet i Safari. Les gjennom, og kom tilbake hit
når du er klar med en avgjørelse.
```

## Phase 5 — Approval gate (the fixed UX)

After the user has had time to read, present a clean approval question.
NOTE: there is no "godkjenn AND open" variant because the HTML is
already open. The user reads first, decides second.

AskUserQuestion brief:

```
D2 — Hvordan er design-doc'en?
Project/branch/task: post-office-hours approval gate
ELI10: HTML-en er åpen i Safari. Du har lest gjennom. Tre ting kan
  skje nå: enten er du fornøyd og vi går videre, eller noe trenger
  en revisjon, eller hele premisset var feil og vi må starte om.
Stakes if we pick wrong: Approve med feil i = den feilen bærer
  videre til implementation; Revise = kort iterasjon; Start om =
  taper opp til en time, men det er riktig hvis premisset er galt.
Recommendation: Approve hvis HTML-en føltes riktig fra start til slutt.
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Godkjenn — design-doc'en stemmer (recommended)
  ✅ Markerer som APPROVED, frigjør neste-steg-forslag
  ✅ Ingen flere endringer; vi går rett videre i flyten
  ❌ Eventuelle feil må fikses i implementasjonsfasen, ikke gratis
B) Reviser — noe må endres
  ✅ Korrigerer på rett sted (spec-nivå) før implementation
  ✅ MD + HTML re-rendres med endringene
  ❌ Tar 5-15 min ekstra; bryter momentumet
C) Start om — feil premiss
  ✅ Rett vei hvis spørsmålene office-hours stilte ikke traff
  ❌ Taper opp til en time arbeid; bare gjør dette ved fundamental retning-feil
Net: Approve med mindre du så noe konkret i HTML-en som ikke stemte.
```

If `B` (Revise): ask what to change, edit MD, re-htmlify with same plan,
re-open, loop back to D2.

If `C` (Start om): delete the design doc (with backup), invoke this
skill again from the top (re-runs office-hours).

If `A` (Approve): mark APPROVED, proceed to Phase 6.

## Phase 6 — Mark APPROVED + suggest next step

Update the design doc's YAML frontmatter `status` from `DRAFT` to
`APPROVED`:

```bash
sed -i.bak 's/^status: DRAFT$/status: APPROVED/' "$RECENT_MD"
rm -f "${RECENT_MD}.bak"
```

Re-htmlify so DESIGN.html reflects the new status:

```
Skill(skill="superpowers-gstack:htmlify", args="$RECENT_MD")
```

(No `--open` — Safari already has the previous version; no need to
re-open.)

Print summary + next-step suggestion:

```
✅ Design-doc godkjent: <path>
   Track: $TRACK (or "web/unknown — no marker written")

Neste steg:
- Native (ios/macos/both): /superpowers-gstack:swiftui-design-consultation
- Web: /design-consultation (gstack)
- Other: implement directly per the design doc
```

If track is `native` (any value): the suggestion is explicit; the user
just needs to type it.

## Notes

- **Replaces the obsolete `swiftui-track` skill.** v2.2.0 had a
  standalone swiftui-track for declaring the marker; v2.3.0 folds that
  logic into Phase 3 here (when native intent is inferred) AND into
  `swiftui-design-consultation` Phase 0 (as inline self-bootstrap, in
  case someone invokes swiftui-design-consultation directly without
  going through office-hours).
- **Fixes upstream gstack office-hours approve-then-read UX.** Upstream
  asks "Approve / Approve and open HTML / Revise / Start over" — the
  two approve-variants conflate approval with reading. We open the HTML
  before asking, then ask "Approve / Revise / Restart" cleanly.
- **CLAUDE.md routing intercept.** Setup-routing emits a rule: "When
  user invokes /office-hours, prefer /superpowers-gstack:office-hours-track-aware".
  Same model-as-dispatcher tradeoff as /design-consultation.
- **Idempotent re-runs.** Re-invoking this skill on a project with an
  existing `.gstack/track` marker keeps it (skips Phase 3); re-invokes
  office-hours fresh (writes a new design doc — user controls scope).
  Design-doc moves are collision-safe: if `docs/<name>.md` already
  exists, the new doc gets a timestamp suffix instead of overwriting.
- **Known limitation: track drift.** If `.gstack/track` is already
  `ios` but the new brainstorm is clearly about a macOS-only menu-bar
  tool, the wrapper silently keeps the existing track (Phase 3 is
  skipped). Re-declaring is a manual step — delete `.gstack/track` and
  re-run the wrapper, or edit the file directly. Acceptable for v1
  because mixed-track-within-one-project is rare; revisit if real
  users hit this.
- **No recursion via Skill tool.** Phase 1's `Skill(skill="office-hours")`
  resolves by exact skill name to gstack's upstream office-hours,
  bypassing the CLAUDE.md routing rule (which is a model-level
  instruction for user-typed `/office-hours`, not a kernel redirect).
- **Backwards compatible for web projects.** No marker is written for
  web intent; gstack default behavior preserved.
