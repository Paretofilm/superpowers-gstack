# Changelog

## [2.6.0] - 2026-05-18

### Added
- **`tests/` directory with integration-test infrastructure.** First test: `tests/integration/test_track_aware_dispatch.sh` verifies track-aware routing dispatches `/design-consultation` correctly. Two cases (track=ios → swiftui variant; no marker → gstack default), each shells out to `claude --print` in a temp-dir fixture with a minimal CLAUDE.md containing the routing block. Cost ~1 min and a few cents per case; safety net via `--max-budget-usd 1.00`.
- **`tests/run.sh`** — entry point with `--integration` / `--unit` flags. Discovers and runs `tests/integration/test_*.sh` files.
- **`tests/README.md`** — documents prerequisites (Claude Code CLI, `ANTHROPIC_API_KEY`), cost model, what's tested vs deferred, and why integration over unit for this skill set (dispatch logic lives in LLM-interpreted CLAUDE.md text; can't unit-test that without mocking the dispatcher under test).

### Changed
- **`README.md`** gains a **Testing** section linking to `tests/README.md`.

### Why
Closes backlog item **S1** from `docs/superpowers/backlog/2026-05-17-swiftui-design-consultation-v1.1-backlog.md`. v1.0 of swiftui-design-consultation's smoke tests "verified by inspection" that routing rules existed in the generated CLAUDE.md — but never tested actual dispatch behavior. Codex flagged this as the highest-impact gap because mis-dispatch on a native project means the user gets the wrong skill (gstack web design-consultation instead of `swiftui-design-consultation`) and may not notice until DESIGN.md is wrong.

The new test runs against the real Claude Code dispatcher with the real plugin loaded — there is no mocking. Live verification against `Paretofilm/superpowers-gstack@7eadf4f` shows both cases pass: the LLM correctly identifies `superpowers-gstack:swiftui-design-consultation` for track=ios, and explicitly notes "not the SwiftUI namespaced variant" when defaulting to gstack for missing-marker.

### Backwards compatibility
**Fully additive.** No skill behavior changes. The new `tests/` directory and `tests/README.md` exist for contributors; runtime behavior unaffected. No new dependencies (bash only; uses `claude` CLI which is a prerequisite for using the plugin anyway).

### Notes for users
- **Run before submitting PRs that touch routing rules:** `bash tests/run.sh --integration` catches dispatch regressions that "verify by inspection" misses.
- **CI integration deferred.** Running integration tests in GitHub Actions requires `ANTHROPIC_API_KEY` as a repo secret and willingness to spend on every PR. Open question — left as a separate backlog item.
- **Adding tests:** drop another `tests/integration/test_*.sh` script following the same pattern (mktemp fixture → claude --print → grep output). The runner picks them up automatically.

## [2.5.0] - 2026-05-18

### Added
- **`skills/swiftui-design-consultation/schema/proposal.schema.yaml`** — formal data model for design proposals (JSON Schema vocabulary in YAML form). 11 top-level fields (`schema_version`, `metadata`, `track`, `typography`, `color`, `materials`, `motion`, `spacing`, `accessibility`, `platforms`, `budget`, `decisions_log`) capture every token Phase 6 generators consume. `version: 1` documented as the current schema version; mismatch between proposal `schema_version` and schema `version` is a hard STOP error with explicit upgrade guidance.
- **`skills/swiftui-design-consultation/schema/proposal.example.yaml`** — fully populated canonical example (Lighthouse macOS menu-bar utility). Shows every required and recommended field; new proposals SHOULD start from this template and only modify fields where the actual design differs.
- **New Phase 6 Step 6.0 (schema validation)** — read cached proposal YAML, validate against schema (LLM-side: walk every `required` field, confirm type matches), then confirm `schema_version` + `track` align with project state. STOPs surface schema gaps explicitly; never silently substitute empty strings.
- **Severity monotonicity guard between HIG iterations (Step 6.7)** — after each iteration N, compare findings against N-1. No NEW CRITICAL allowed; SIGNIFICANT count must not increase; POLISH may drift. Rollback proposal YAML to N-1 state if monotonicity violated, then AskUserQuestion (accept N anyway / accept N-1 / refine manually). Prevents the failure mode where a fix trades one CRITICAL for another, or fixes a SIGNIFICANT by introducing two new ones.

### Changed
- **Phase 3 Step 3.1 (build data model)** — now references the schema explicitly and produces a structured YAML proposal alongside the in-memory object. "Build the in-memory DesignProposal" → "Build the DesignProposal as a structured YAML document matching proposal.schema.yaml".
- **Phase 3 Step 3.2 (serialize + htmlify)** — writes BOTH `design-proposal-$TS.md` (human-readable, for htmlify preview) AND `design-proposal-$TS.yaml` (structured, for Phase 6). Same pinned timestamp; same data, different presentation.
- **Phase 3 Step 3.4 (cache approved proposal)** — caches both files under canonical names (`swiftui-consultation-state.proposal.yaml` + `.md`). The YAML is authoritative; the MD is its presentation; they must stay consistent.
- **Phase 6 Step 6.1 (generate DESIGN.md)** — token substitution sources from the parsed proposal YAML object loaded in Step 6.0, NOT from prose. New explicit token-to-YAML-field mapping table (15 tokens × YAML paths).
- **Phase 6 Step 6.2 (generate Swift Package)** — same change: tokens map to parsed YAML paths. New mapping table covers all 9 Swift-template tokens. Both 6.1 and 6.2 read the same parsed object, so prose-vs-code drift is structurally impossible.
- **Phase 6 Step 6.7 iteration loop** — proposal YAML is the only thing that gets edited during iteration; DESIGN.md and DesignSystem/* are always regenerated from it. In-memory backup of the YAML before each iteration enables mechanical rollback for the monotonicity guard.

### Why
Closes backlog items **S3** (formal data model) and **S4** (HIG iteration convergence guard) from `docs/superpowers/backlog/2026-05-17-swiftui-design-consultation-v1.1-backlog.md`. v1.0 of swiftui-design-consultation produced DESIGN.md and DesignSystem/* by substituting tokens into templates from a *prose* proposal MD — the "pure functions of the same data model" guarantee was aspirational, not enforced. Drift was possible whenever the LLM mis-substituted tokens, and the iteration loop could leave the user with a strictly worse artifact than they originally approved (no comparison against iteration N-1, no severity monotonicity).

v2.5.0 makes the data model real (structured YAML + schema) and adds the rollback guard. Both changes are LLM-side (no new dependencies, no validator binary, no build step). The schema is human-readable YAML; the validation is the skill reading the schema and confirming the proposal matches; the monotonicity check is finding-comparison the skill performs between iterations.

### Backwards compatibility
**Breaking for in-flight Phase 3 work**, additive for new consultations. Projects mid-consultation when v2.5.0 lands need to re-run Phase 3 to produce a structured proposal YAML — the cached prose-only `swiftui-consultation-state.proposal.md` is not sufficient for Phase 6 anymore. For new projects: zero migration. For freshly-shipped DESIGN.md/DesignSystem from v1.x consultations: no change (the artifacts are already on disk; the schema only matters when re-running the skill).

### Notes for users
- **Re-running consultation after v2.5.0:** start fresh from Phase 0 to produce the YAML proposal. The skill detects missing YAML in Step 6.0 and surfaces it explicitly.
- **Schema evolution:** when adding/removing/renaming proposal fields in the future, bump `version` in `proposal.schema.yaml` and document the upgrade path in the CHANGELOG. The schema-version mismatch check in Step 6.0 will catch proposals on the old format.
- **Monotonicity guard tuning:** if you find legitimate cases where iteration 2 *should* introduce a new SIGNIFICANT (e.g. a deliberate trade-off the user accepts), the AskUserQuestion offers option (A) to override. The guard never silently blocks — only surfaces the discrepancy.

## [2.4.0] - 2026-05-18

### Added
- **`/superpowers-gstack:ios-native-review`** — pre-implementation HIG-citation-grounded review skill for iOS/iPadOS app specs, mirroring the established `macos-native-review` pattern. 13 iOS-specific categories: vocabulary, controls & touch targets (44×44 pt), navigation paradigm (TabView / NavigationStack / NavigationSplitView), modal presentation (sheets + detents, full-screen, popovers), gestures, system surfaces (safe area, Dynamic Island, status bar), keyboard handling (keyboardType / textContentType / submitLabel), haptics, semantic colors & dark mode, animation timing, privileged operations & permission prompts (ATT, location, notifications), accessibility (VoiceOver, Dynamic Type up to AX5, Reduce Motion), app lifecycle & state restoration.
- **Phase 0 iOS signal detection** mirrors macos-native-review's structure: scans for `.swift` files, `UIKit`/`SwiftUI` imports, iOS-flavored types (`UIViewController`, `TabView`, `NavigationStack`, etc.), `iOS app` text mentions, iOS deployment targets. Multi-target projects (iOS + macOS) proceed; macOS-only signals return N/A with sibling-skill note pointing at `/superpowers-gstack:macos-native-review`.
- **Robust-citation strategy reused.** Same JSON fallback as macos-native-review (`developer.apple.com/tutorials/data/design/human-interface-guidelines/<slug>.json`) for cases where the JS-rendered HTML returns only a page title. Verified at skill creation against `/buttons` (canonical 44×44 pt touch-target quote returned).

### Changed
- **`setup-routing` evaluation table** now includes both `macos-native-review` and `ios-native-review` rows. Closes a pre-existing oversight (macos-native-review was missing from the table though it shipped in v1.9.0). Generated CLAUDE.md routing now offers both review skills with platform-aware descriptions.
- **`adapt` evaluation table** mirrors the addition for projects being adapted into the workflow.
- **`setup-routing/model-routing.md`** adds `ios-native-review` row with same model recommendation as macos-native-review (`sonnet` everywhere, `sonnet (req. web)` for Pi local-only since WebFetch against developer.apple.com is required).
- **`macos-native-review` Phase 0** updated: iOS-only signals now point at the newly-shipped `/superpowers-gstack:ios-native-review` instead of "the skill is in the backlog (IDEAS.md)".
- **`IDEAS.md`** marks ios-native-review entry as ✅ SHIPPED in v2.4.0.

### Why
Closes backlog item S2 from `docs/superpowers/backlog/2026-05-17-swiftui-design-consultation-v1.1-backlog.md`. v2.3.0/v2.3.1 shipped dual-track support but iOS-only projects had no DESIGN.md HIG-review path — only the platform-agnostic rules from `macos-native-review`'s SwiftUI-rag chain fired. v2.4.0 closes that gap symmetrically; iOS + macOS multi-target projects now have parallel review surfaces. The deferral note from IDEAS.md was accurate ("Pick up when a real iOS spec review surfaces the gap") — the gap surfaced as part of dual-track stress-testing.

### Backwards compatibility
**Fully additive.** No existing skill behavior changes. The only edit to `macos-native-review` is the Phase 0 fallback text for iOS-only projects (cosmetic, points at the new skill instead of IDEAS.md). Multi-target projects (iOS + macOS) should run both review skills in parallel — neither replaces the other.

### Notes for users
- **Run on iOS specs the same way as macOS:** `/superpowers-gstack:ios-native-review` after `pitfall-verification` + `quality-review`, before implementation.
- **Re-run `/superpowers-gstack:adapt`** on existing iOS projects to surface the new skill in routing recommendations (uses the v2.3.2 routing-version-marker, so it's a single-call upgrade).
- **macos-native-review unchanged in scope.** Phase 0 just points at the sibling skill now instead of the backlog note.

## [2.3.2] - 2026-05-18

### Changed
- **`adapt` Track-aware routing section now uses a version marker (`<!-- gstack-routing-v1 -->`).** Previously, `adapt` skipped the routing section entirely if a section with the matching H2 already existed — which made the skill idempotent but ALSO prevented updating stale or malformed versions across projects already adapted.
- **New four-case logic in `adapt`:** heading + matching marker → skip (idempotent); heading + different-version marker → REPLACE through next H2 (upgrade path); heading + no marker (legacy v2.3.0/v2.3.1 projects) → REPLACE (one-time silent upgrade adds the marker); heading absent → APPEND.
- **`setup-routing` template** emits the version marker on the H3 heading from this version forward, so all newly-generated CLAUDE.md files are already on `v1` and pick up future updates automatically.

### Why
Closes backlog item S6 from `docs/superpowers/backlog/2026-05-17-swiftui-design-consultation-v1.1-backlog.md`. v2.3.0 introduced track-aware routing; v2.3.1 will not be the last time the rules evolve. Without a version marker, every rule change would require either (a) manual editing across N adapted projects, or (b) breaking idempotency. The marker pattern is forward-clean: the next semantic change (`v2`) auto-upgrades existing projects without disturbing surrounding CLAUDE.md content.

### Backwards compatibility
**Fully backwards compatible — no duplicate sections.** Projects adapted on v2.3.0/v2.3.1 have a heading without a marker. The four-case logic treats those as case 3 (REPLACE, byte-identical content + new marker), not as APPEND. The APPEND path only fires when no heading exists at all. Re-running `adapt` on existing projects performs a one-time silent upgrade; surrounding CLAUDE.md content outside the routing section is never touched.

**H2 vs H3 handled symmetrically.** Pre-existing inconsistency: `setup-routing` emits the section as **H3** (subsection of `## Skill routing`); `adapt` historically appended it as top-level **H2**. The new marker-detection scans for either level (`^#{2,3} Track-aware routing \(dual-track\)`) and preserves the original level during upgrade. This avoids accidentally promoting H3 → H2 (which would break the nested structure in setup-routing-generated CLAUDE.md files).

### Notes for users
- **Re-run `/superpowers-gstack:adapt`** on existing dual-track projects to add the version marker. The routing rules themselves are unchanged in this version — only the marker is added. After this, future rule changes (v2+) will upgrade silently.
- The marker is an HTML comment, so it does not render in Markdown previews. Bump the version (`v1` → `v2`) only when the section's semantics change, not for cosmetic edits.

## [2.3.1] - 2026-05-17

### Changed
- `swiftui-design-consultation` Step 6.6 now explicitly invokes **all
  three** swiftui-rag review tools in parallel
  (`review_macos_hig` + `review_accessibility` + `review_liquid_glass`)
  with a deduplication rule on `(rule_id, line)`. Previously the trio
  was mentioned but described loosely ("Same for ..."), which led the
  consumer to under-invoke and miss accessibility-only findings.
- Step 6.7 budget aggregation now explicitly counts findings from all
  three tools, deduplicated.
- Schema table now lists `question` (not `query`) as the
  `search_swiftui_corpus` primary parameter — verified against live
  swiftui-rag v1.4.0 / corpus v1.3.3 MCP responses.

### Documented
- **Known limitation** in Step 6.6: `C1-glass-on-content` does not
  always fire when `.glassEffect` is separated from its shape primitive
  by chained modifiers. Pattern that fires: `Circle().glassEffect()`.
  Pattern that does NOT fire: `Circle().fill(...).frame(...).glassEffect()`.
  Verified by live stress-test in this session. Track upstream fix at
  `swiftui-rag-pipeline` issue tracker.

### Why
- Stress-test on swiftui-rag v1.4.0 revealed the three review tools are
  complementary, not overlapping — each owns its own ruleset
  (`review_accessibility` is the only one that fires A1/A3, etc).
  Running only `review_macos_hig` misses all accessibility findings.

## [2.3.0] - 2026-05-17

### Added
- **`/superpowers-gstack:office-hours-track-aware`** — wrapper around
  upstream `/office-hours` that fixes three UX bugs observed in live
  v2.2.0 usage:
  1. Approval gate ran BEFORE htmlify rendered — user had to approve
     a design they hadn't seen rendered. Now htmlify runs first
     (auto-opens in Safari) and the approval gate comes after.
  2. Plain v1 HTML was rendered instead of the rich v2 plan-driven
     layout. Wrapper now inspects design-doc content for visual
     opportunities (Approaches Considered, architecture diagrams,
     pullquotes, metrics, callouts) and generates a v2 plan JSON
     before invoking `/htmlify --plan ... --open`.
  3. Track inference happened too late (or not at all). Wrapper now
     classifies the brainstormed idea as native vs web and asks the
     iOS/macOS/both platform question inline only when needed.
- Wrapper also relocates design docs from gstack's default location
  (`~/super-me/brain/ideas/seeds/...` etc.) into the project's
  `docs/superpowers/specs/` directory so they live alongside other
  project artifacts.

### Changed
- `swiftui-design-consultation` Step 0.1 now asks the platform question
  inline (AskUserQuestion D0 with iOS / macOS / both options) when
  `.gstack/track` is missing — previously delegated to the standalone
  `swiftui-track` skill. One fewer hop, same result.
- `setup-routing` and `adapt` skill tables: replaced
  `/superpowers-gstack:swiftui-track` row with
  `/superpowers-gstack:office-hours-track-aware`. Updated track-aware
  routing block in generated CLAUDE.md to intercept `/office-hours`
  (not `swiftui-track`) for dual-track projects.
- Repo `CLAUDE.md` skill routing: `office-hours` routes through the
  wrapper; dropped the swiftui-track row.
- `README.md` Skills section: replaced swiftui-track entry with
  office-hours-track-aware entry.

### Removed
- **`/superpowers-gstack:swiftui-track`** (v2.2.0 only) — the
  standalone marker-writing skill is gone. Its job is now folded into
  the wrapper (early-stage inference at brainstorm time) and into
  `swiftui-design-consultation` Step 0.1 (late-stage inline question
  if user jumps straight into design without brainstorming).

### Compatibility
- Backwards compatible. Projects with existing `.gstack/track` markers
  continue working unchanged. Projects without the wrapper installed
  fall back to plain `/office-hours` (gstack), as before.
- No upstream gstack or superpowers code touched.

### Review pipeline
- Inline pitfall-verification on v2.3.0 changes (single round)
- Real-world live-fire test: caught all three UX bugs from sing-replay
  session observation; wrapper design verified against that flow

## [2.2.0] - 2026-05-17

### Added
- **`/superpowers-gstack:swiftui-track`** — declare SwiftUI project
  platform target (iOS / macOS / both); writes `.gstack/track` marker.
  Idempotent.
- **`/superpowers-gstack:swiftui-design-consultation`** — Apple-canon
  design system consultation for SwiftUI projects. Produces `DESIGN.md`
  + Swift Package starter with semantic colors, SF Pro typography,
  Liquid Glass material discipline, named motion presets, and
  accessibility baseline. Orchestrates swiftui-rag MCP surface for
  HIG-citation grounding; uses `/htmlify` for Phase 3 proposal preview
  and Phase 6 DESIGN.html generation; chains into `macos-native-review`
  with HIG conformance budget.
- **`skills/swiftui-design-consultation/bin/contrast-check.sh`** — bash
  helper script implementing WCAG 2.1 contrast-ratio math (sRGB →
  linear → relative luminance → contrast). Called by Phase 6 to
  validate brand colors against text/background. Locale-safe via
  `LC_ALL=C` (decimal separator forced to dot regardless of user locale).

### Changed
- `setup-routing` and `adapt` skills now emit/preserve a
  "Track-aware routing (dual-track)" section in generated project
  CLAUDE.md files. This section tells the model how to dispatch
  `/office-hours` and `/design-consultation` based on `.gstack/track`.
- `macos-native-review` SKILL.md cross-references
  `swiftui-design-consultation` as the upstream design-system step.
- `htmlify` SKILL.md notes `swiftui-design-consultation` as a
  programmatic consumer.
- Repo `CLAUDE.md` skill routing table adds entries for both new
  skills.
- `README.md` "Skills" section adds entries for both new skills.

### Compatibility
- Backwards compatible. Projects without `.gstack/track` continue to
  route `/design-consultation` to the gstack web skill (unchanged
  default behavior).
- No changes to upstream gstack code; all routing logic lives in
  CLAUDE.md generated by setup-routing/adapt.

### Review pipeline
- Spec: `docs/superpowers/specs/2026-05-17-swiftui-design-consultation-design.md` (commit `80242e8`)
- Plan: `docs/superpowers/plans/2026-05-17-swiftui-design-consultation-implementation.md` (commit `4d9b75e`, patched by `96b82bd` + `aa32513` + `9fcffb8`)
- Pitfall verification: 2 rounds, 10 issues found, all patched
- Codex adversarial: 6 CRITICAL patched, 7 SIGNIFICANT + 3 MINOR deferred to `docs/superpowers/backlog/2026-05-17-swiftui-design-consultation-v1.1-backlog.md` (S5 fixed inline)
- Smoke tests: 5 of 5 paths verified (4 by inspection + 1 live `claude --plugin-dir` skill-load check)

## [2.1.1] - 2026-05-16

### Changed
- **`context-handoff` template adds `type: handoff` as first YAML field.** Aligns with htmlify v2.0+ classifier, which treats `type:` as the primary type-discriminator. v1.12.0 handoffs (without `type:`) still work via htmlify's filename-based legacy fallback, but new handoffs written by this skill are now first-class instead of legacy.
- **CLAUDE.md "Session continuity" updated** to detect three handoff formats: `type: handoff` (current, v2.1.1+), YAML-without-`type:` (v1.12.0 → v2.1.0), and prose-only (pre-1.12.0). All read the same YAML fields when present.
- **`context-handoff` SKILL documents htmlify hook side effect.** If the `/htmlify` PostToolUse hook is installed, writing handoff.md auto-renders it as HTML and opens it in Safari. Background, non-blocking — but visible. SKILL.md now warns to mention this once if it surprises the user.

### Why
"Forward-clean" patch. v1.12.0 introduced the YAML handoff schema but predated htmlify's `type:` discriminator. As long as this skill keeps producing handoffs without `type:`, htmlify's legacy-fallback path must stay actively maintained. One-line template change moves new handoffs to the first-class path; the fallback freezes into "pre-existing files only" instead of "needed for current tooling".

### Backwards compatibility
**No breaking changes.** Pre-2.1.1 handoff.md files (with or without YAML) keep working — htmlify's classifier still recognizes them, and CLAUDE.md "Session continuity" still parses them. The change only affects what *new* writes look like.

### Notes for users
- **No action required.** Next time `/superpowers-gstack:context-handoff` runs, the written handoff.md will include `type: handoff` automatically.
- If the Safari auto-open is undesired, disable the htmlify PostToolUse hook by removing the relevant block from `~/.claude/settings.json` (the `scripts/setup-htmlify-hook.sh` installer is opt-in to begin with).

## [2.1.0] - 2026-05-16

### Changed
- **Liquid Glass design system.** Hele `companion.css` skrevet om til en 2026-software-aestethic: gradient-mesh canvas, glass-overflater med edge-highlights (`backdrop-filter: blur(28px) saturate(160%)` + `mask-composite` for kantgradient), "knashe" accent-palette (cyan/magenta/violet/amber/emerald/terracotta), SF Pro + Charter typografi-paring, monospace tabular-numerics. Lys og mørk mode med forskjellige aksent-intensiteter (varme i lys, neon i mørk).
- **Dual-theme + toggle.** Ny pill-knapp i øvre høyre hjørne bytter mellom light/dark/system. Valget persistert i localStorage; OS-preferanse er default. Bootstrap-script kjører før paint så ingen flash-of-wrong-theme.
- **Flowchart-layout med kontekst-bevisste regler:**
  - ≤4-noders lineær chain → LR stacked (full bredde øverst, notes under)
  - =5-noders lineær chain → TB single column, eksakt 50/50 med notes-kolonne
  - ≥6-noders lineær chain → TB split i to sub-kolonner med 90°-cornered connector mellom, eksakt 2/3 (diagram) + 1/3 (notes)
  - Trær / DAG → TB regular side-by-side
  - Eksplisitt `orientation` i plan respekteres alltid
- **Connector-kurve for split-chains:** L+C+L+C+L-mønster (rett ned → 90° bend → rett opp midt mellom kolonnene → 90° bend → rett ned), ikke én sammenhengende S-Bezier. Cubic-Bezier-kontrollpunkter plassert utenfor endepunktene så tangentene er strikt vertikale ved exit/entry.
- **`notes`-felt på `FlowchartData`** — optional markdown rendres som side-kolonne (TB) eller stacked-rad (LR). Lar plan-LLM-en putte budsjett, legend, kontekst som ellers ville gått tapt når en seksjon erstattes av et diagram-treatment.
- **Større flowchart-nodes** (165×50 TB / 165×72 LR), større font (15.5px i bokser, 13px på edges), generøs ranksep (55 TB / 70 LR) — labels får luft.
- **Notes-kolonne stretches** til full kortets indre-høyde (`align-items: stretch` på flex), så border-left ikke avsluttes der tekst slutter.
- **Safari som distraksjonsfri viewer:** `--open` bruker `osascript` til å lukke alle eksisterende Safari-vinduer før den åpner companion-HTML-en. Default-nettleseren røres ikke.

### Fixed
- Dashboard-test bruker nå mer presis assertion (sjekker escaped form, ikke fravær av `<script>` overhodet) siden shell-en legitimat embedder theme-bootstrap-script.

## [2.0.0] - 2026-05-16

### Added
- **`/htmlify` v2 — plan-driven rich rendering.** HTML-companions er ikke lenger "penere MD med strukturerte cards" — de er informative plansjer med 9 visuelle komponenter. Nytt `--plan <plan.json>` flagg laster en rendering plan generert av Claude Code i samme sesjon (Max-plan compute — **ingen Anthropic API-kall**). Plan'en definerer per-seksjon treatment (overstyrer default cards) og global feedback-panel.
- **9 nye komponenter:** `comparison-matrix` (side-ved-side A/B/C med Recommended-highlight), `flowchart-svg` (dagre-layout inline SVG, kobler-fri), `pullquote` (editorial highlight), `callout-box` (info/warn/insight/danger varianter), `stats-bar` (metrics + trend), `two-column` (compare/contrast), `expandable` (pure-CSS `<details>` toggle), `diff-card` (før/etter kode), `feedback-panel` (interaktiv).
- **Interaktiv feedback-panel.** Pure-CSS reveals + en `<script>`-tag som gjør én ting: gather → JSON → clipboard. Premise-sjekkbokser, approach-radioer, custom-spørsmål, og obligatorisk fritekst-kommentar. "Copy feedback as prompt"-knapp → bruker limer inn i neste sesjon. Fallback til `<pre>` med tekst-seleksjon hvis Clipboard API ikke er tilgjengelig. **Ingen server.**
- **Plan-skjema med graceful degradation.** `PlanSchema` (zod, `.passthrough()`) validerer struktur. Hvis plan-fil mangler/feil-formatert: stderr-advarsel + fall tilbake til v1-template-rendering. Manglende H2 i MD = plan-seksjon rendres som ny seksjon.
- **Shared `renderPlannedSections` helper** i `helpers/planWiring.ts`. Tre renderere (designDoc, handoff, plan) bruker samme logikk: kanonisk seksjons-liste først (overstyrt av plan hvis matchende heading), så plan-introduserte seksjoner, så pullquotes interleaved.
- **64 nye tester** (138 totalt opp fra 74) — per-komponent (HTML-escape, edge cases, missing data), plan-wiring (case-tolerant matching, pullquote placement, default fallback), feedback-panel (clipboard script, fallback, escaped labels).

### Why
v1 løste "vibe-codere leser ikke MD" ved å gi penere MD-presentasjon. Men brukeren påpekte at v1 fortsatt er prosa: "veldig mye av poenget med å vise vibe coderen html i stedet for md er fordi med html blir det mulig å lage pene informative plansjer/grafiske fremstillinger." v2 leverer det: når plan'en sier "Approaches Considered = comparison-matrix" får brukeren et lesbart 3-koloners visuelt rasterkort i stedet for en bullet-liste; "Architecture = flowchart-svg" gir et statisk SVG-diagram. Den separate **Phase 1 planning-modellen** (LLM-en lager planen i Claude Code-sesjonen, ikke i CLI'en) holder kostnad nede (Max-plan compute = inkludert) og innholdsforståelse oppe (planen er på model-side, ikke deterministic regex-baserte heuristikker).

### Changed
- **`--open` bruker Safari som dedikert leser.** Tidligere åpnet `--open` HTML-en i brukerens default-nettleser (via `open <url>`). Nå brukes Safari spesifikt — alle eksisterende Safari-vinduer lukkes først, og HTML-en åpnes som eneste vindu. Bakgrunn: brukeren bruker normalt ikke Safari, så Safari blir en distraksjonsfri visning som ikke forstyrres av andre tabs/sesjoner. Default-nettleseren røres ikke. Implementert via `osascript`; fallback til `open` hvis AppleScript feiler.

### Backwards compatibility
**Ingen breaking changes for eksisterende brukere.** Uten `--plan` er output identisk med v1.13.x. Hookken kjører som før (uten plan-generering). `--open` skifter nettleser (Safari) men semantikk er den samme — HTML vises. Major version-bump skyldes scope og dybde av nye features, ikke trukne kontrakter.

### Notes for users
- **Bruke v2 manuelt:** I Claude Code, be om "lag en rik HTML av X.md". Claude leser MD-en, identifiserer visuelle muligheter, skriver `plan.json` til en temp-fil, og kjører `htmlify --plan plan.json`.
- **Auto-trigger via hook** bruker fortsatt v1 (uten --plan). v2-rendering er opt-in inntil videre — vi kan eventuelt utvide hooken når plan-generering blir billigere/raskere.
- **Plan-skjema og treatment-katalogen** er dokumentert i `skills/htmlify/SKILL.md` under "Enhanced rendering (v2 — plan-driven layout)".
- **First-run deps oppdatert:** `cd "$SKILL_DIR" && bun install` (dagre lagt til som ny dependency for flowchart-layout).
- **Eksisterende plugin-installasjoner:** etter upgrade, kjør `bun install` i cache-katalogen for å hente `dagre`. Wrapperen rapporterer exit 5 + nøyaktig kommando hvis ikke gjort.

### Engineering process
Brainstormet via `/office-hours`. Phase A (PlanSchema + CLI flag + plumbing) → Phase B (9 komponenter med tester) → Phase C (feedback-panel + clipboard) → Phase D (docs). Hver fase bisectable-committet. Critical constraint underveis: bruker er på Max-plan → ingen API-kall — plan-generering må skje in-session, ikke i CLI'en.

## [1.13.2] - 2026-05-16

### Added
- **`/htmlify` lagt til i model-routing-tabellen** med Haiku-anbefaling (Claude Code), `qwen3.6-mlx-8bit` (Pi local-only) og Haiku (Pi hybrid). Begrunnelse: CLI'en selv er deterministic — orchestrator-Claude trenger bare å invoke bash-kommandoen, ingen reasoning om innholdet. Klassisk Haiku-territorium, samsvar med `/verification-before-completion`, `/using-git-worktrees`, `/macos-e2e-scaffold`, `/context-handoff`.
- **`/htmlify` lagt til i `setup-routing` og `adapt` evaluation tables** så generert CLAUDE.md inkluderer skill'en for nye prosjekter. Anbefales for alle prosjekter — verdien er proporsjonal med hvor mange MD-artefakter prosjektet produserer.

### Notes for users
- **Re-kjør `/superpowers-gstack:adapt`** på eksisterende prosjekter for å få htmlify-rad lagt til i CLAUDE.md.
- Ingen breaking changes. Funksjonalitet samme som v1.13.1; dette er kun routing-metadata + skill-katalog-oppdatering.

## [1.13.1] - 2026-05-16

### Added
- **Self-locating `bin/htmlify` wrapper.** Nytt skript `skills/htmlify/bin/htmlify` resolverer skill-katalogen fra sin egen path og kan kjøres fra hvilken som helst cwd uten å vite den faktiske installasjons-stien. Sjekker at `bun` og `node_modules/` finnes, printer presis feilmelding (exit 5) hvis ikke.

### Fixed
- **SKILL.md ga feile install-paths.** v1.13.0-instruksjonene refererte til repo-relative stier (`skills/htmlify/...`, `./scripts/setup-htmlify-hook.sh`) som ikke fungerer når plugin'et er installert via marketplace (faktisk path er `~/.claude/plugins/cache/paretofilm-plugins/superpowers-gstack/<version>/...`). Oppdatert til å bruke `$SKILL_DIR/bin/htmlify`-mønsteret som Claude Code resolver automatisk via "Base directory for this skill"-header. CHANGELOG-notater for v1.13.0 hadde samme feil.
- **First-run-setup steg klargjort.** En `bun install` per install-lokasjon er nødvendig — det gjelder både utviklingsrepo og plugin-cache. Wrapperen forteller deg den eksakte kommandoen.

### Notes for users
- **Eksisterende v1.13.0-installasjoner:** Etter oppdatering til v1.13.1, kjør én gang:
  ```bash
  cd ~/.claude/plugins/cache/paretofilm-plugins/superpowers-gstack/1.13.1/skills/htmlify && bun install
  ```
- **Hook-installer-stien er nå tydeligere** i SKILL.md. Hook'en self-lokaliserer fortsatt — installasjon fra cache-stien fungerer.

## [1.13.0] - 2026-05-16

### Added
- **`/htmlify` skill — HTML companions for MD artefacter.** Generates visually elegant, pedagogical HTML next to MD-artefakter fra skills som `/office-hours`, `/autoplan`, `/plan-eng-review`, `/context-handoff` osv. Stilles ut for vibe-codere som ikke orker å lese verbose MD-output. Auto-opens i nettleser via `--open` flag (macOS). Per-katalog aggregert dashboard via `htmlify dashboard <dir>` viser alle companions sortert by mtime med drilldown-lenker. Tre frontmatter-typer støttes: `design-doc`, `handoff`, `plan` (med backward-compat for legacy handoff.md filer uten `type:`-felt). Generic fallback for MD-er uten kjent frontmatter — får banner + full marked-rendret body. Implementert som Bun + TypeScript, kjørt via `bun run skills/htmlify/src/cli.ts <args>`. Output legges i `<dir>/.superpowers-html/<name>.html` (sibling-katalog, auto-gitignored).
- **PostToolUse-hook for auto-trigger.** Et nytt hook-skript (`scripts/htmlify-posttooluse.sh`) fyrer automatisk når Claude Code skriver/redigerer en MD-fil som matcher artefakt-mønstre (`*-design-*.md`, `handoff.md`, `*-plan-*.md`, alt under `.gstack/projects/`). Loop-prevention på `.superpowers-html/*.html` skrives. Installeres én gang via `./scripts/setup-htmlify-hook.sh`.

### Why
Et tilbakevendende mønster: skills produserer verbose MD-output (design-docs, plans, retro-rapporter) som blir liggende ulest. Stockholm-syndrome med MD-format som vinner mot AI-skifte til HTML for menneske-konsum (Thariq Shihipar / Anthropic, mai 2026). Brukerens egen `~/.claude/CLAUDE.md` mandater allerede HTML+MD parallelt for kreative/strategiske artefakter — denne featuren implementerer det mønsteret INNE I plugin'et selv. Companion-HTML er pedagogisk scaffold som viser PROSESSEN (premisser challenged, alternativer vurdert, beslutninger), POSISJONEN (workflow-state), og STATEN (DRAFT/APPROVED/SHIPPED, tasks-progress). YAML-frontmatter er kontrakten (rir på v1.12.0-mønsteret); zod-skjemaer med `.passthrough()` håndterer schema-evolusjon tolerant.

### Notes for users
- **Aktiver auto-trigger:** Kjør `./scripts/setup-htmlify-hook.sh` én gang. Hook'en legges til `~/.claude/settings.json` som PostToolUse-hook. Restart Claude Code etter installasjon.
- **Manuell bruk:** `bun run skills/htmlify/src/cli.ts <path-to-md>` produserer HTML, `--open` åpner i nettleser, `htmlify dashboard <dir>` genererer aggregat-side. Se `skills/htmlify/SKILL.md` for full referanse.
- **First-run deps:** `cd skills/htmlify && bun install` (committed lockfile garanterer reproduserbare bygg). Hook'en feiler silently hvis deps ikke er installert — ingen auto-bootstrap som muterer brukerens checkout.
- **Visual design enforcement:** Stilark `skills/htmlify/styles/companion.css` følger brukerens design-system (Charter/Georgia typografi, varm copper-aksent, hairline borders, asymmetrisk grid). Hardkodet palette — ingen lilla gradient.
- **74 unit-tester følger med** (`cd skills/htmlify && bun test`) — full path coverage på schemas, helpers, renderers, dashboard, output, hook-filter.
- **Cross-platform `--open` kommer i V1.5** (Linux `xdg-open`, WSL `wslview`). V1 er macOS-only by design.
- **`/adapt`-retrofit-integrasjon** (scanning av eksisterende MDer i et prosjekt) er deferred til V1.5.

### Engineering process
Designet via `/office-hours` (builder mode), reviewet via `/plan-eng-review` med 3 reviewer-iterasjoner og uavhengig Codex kald-lesning. Codex utfordret V1-abstraksjonen som førte til scope-expansion: hook og dashboard ble flyttet fra V1.1/V2 inn i V1. Også 7 hardening-fixes anvendt (handoff schema disambiguation, body sanitization via DOMPurify, URL-encoding via `pathToFileURL`, exit-code taxonomy, Levenshtein typo-detection på `type:`-felt). Design-doc + test-plan lever i `~/.gstack/projects/Paretofilm-superpowers-gstack/`.

## [1.12.0] - 2026-05-15

### Changed
- **`context-handoff` schema upgrade — YAML frontmatter + prose hybrid.** `docs/superpowers/handoff.md` now starts with a YAML block carrying machine-parseable fields: `session_end`, `branch`, `commit_at_handoff`, `mode`, `active_task`, `status`, `completed`, `remaining`, `files_in_flight`, `env` (venv/dev_server/test_cmd), and `next_step`. Prose sections below remain for human context (decisions, files modified, plan progress, blockers).
- **Stable task-ID convention** — `<feature-slug>-<n>` (e.g. `auth-rewrite-3`). IDs never renumber; the slug makes them grep-able across handoff history, plan files, and commit messages.
- **`next_step` discipline** — must be one sentence with a concrete verb and (where possible) `file:line` anchor. Vague resumption text ("continue work on auth") is no longer acceptable.
- **`CLAUDE.md` "Session continuity" section** updated to read structured YAML fields. Quotes `next_step` verbatim, names the `active_task`, and surfaces `env` so commands work immediately on resume. Falls back to prose parsing for pre-1.12.0 handoffs.
- **Auto-mode marker migrated to YAML.** New writes use `mode: auto` in YAML; the legacy `## Mode: auto` Markdown marker is still recognized on read for backwards compatibility.

### Why
Phase 1 → Phase 2 handoff was the weakest link in the workflow: prose-only handoffs forced re-parsing on every session start, and "next step" was often too vague to act on without re-reading the whole file. Structured fields let the SessionStart hook restore env automatically, and stable task IDs make it possible to grep across sessions for what happened to a given piece of work. Considered full integration with `acai.sh` (ACIDs) but rejected as too heavy and too immature (v0.0.8) for the actual problem — this is the lighter, reversible alternative.

### Notes for users
- **Existing handoff.md files keep working** — pre-1.12.0 prose-only format is read as-is, then converted to YAML+prose on next write.
- **No action required** unless you've customized the handoff schema yourself. Re-run `/superpowers-gstack:adapt` is NOT needed — `context-handoff` is a self-contained skill.
- Test plan: use on the next project for one week. Iterate on the schema (add/remove YAML fields) or revert based on actual friction.

## [1.11.2] - 2026-05-13

### Changed
- **VERSIONS.md sync** — bumped GStack v1.26.2.0 → v1.34.1.0. Eight upstream point releases scanned; no skills renamed or removed.
- **Three new gstack skills added to `setup-routing` and `adapt` evaluation tables** (upstream additions between v1.26.3.0 and v1.34.1.0):
  - `/sync-gbrain` — keeps gbrain current with the repo's code and refreshes CLAUDE.md search guidance (added next to `/setup-gbrain`).
  - `/scrape` — pulls data from a web page; prototypes a flow via `$B` primitives and returns JSON (added next to `/browse`).
  - `/skillify` — codifies the most recent successful `/scrape` flow into a permanent browser-skill so subsequent calls run in ~200ms.
- `adapt` skill version marker bumped to 1.11.2. `adapt` will now inform users on `1.11.1` or earlier that the three new skill rows are part of the adaptation.

### Notes for users
- **Re-run `/superpowers-gstack:adapt` to pick up the three new skills** if you have an existing CLAUDE.md generated by this plugin. The skill detects the older version marker and adds the new rows without touching the rest of the file.
- Other gstack changes between v1.26.3.0 and v1.34.1.0 are internal (browse-server embedder API, update-check semver guard, signal-handler cleanup, `gbrain code-def/refs/callers/callees`, Conductor worktree leak fix, plan-skill MCP `AskUserQuestion` fallback). None affect this plugin's routing or skill list.

## [1.11.1] - 2026-05-13

### Changed
- **VERSIONS.md sync** — bumped GStack v1.15.0.0 (dde5510) → v1.26.2.0 (30fe6bb) and Claude Code 2.1.119 → 2.1.126. Per auto-update PR #14's own analysis: no new skills added, removed, or renamed upstream. Routing tables and Model Routing recommendations remain accurate. Upstream changes are internal fixes (e.g. `/plan-eng-review` STOP gates, `/office-hours` Phase 4, `AskUserQuestion` MCP fallback, `/ship` PR-title prefix, cross-platform hardening, gbrain manifests, browser-skills runtime, tunnel allowlist expansion).

### Notes for users
- No functional changes in this plugin. v1.11.1 closes auto-update PR #14 / issue #15 which collided with the manually-shipped v1.11.0 model routing release (same pattern as v1.8.1 / PR #9 collision documented in earlier CHANGELOG). The salvageable VERSIONS.md update from PR #14 is incorporated here.

## [1.11.0] - 2026-05-12

### Added
- **Per-skill model routing recommendations** — `setup-routing` and `adapt` now emit a `### Model Routing` subsection inside `## Skill routing` in the generated CLAUDE.md. The table maps each relevant skill (and key per-phase steps within multi-phase skills like `/superpowers:test-driven-development`, `/superpowers:subagent-driven-development`, `/superpowers:systematic-debugging`, `/qa`, `/ship`) to its recommended model per harness.
- **Multi-harness columns** — routing recommendations are column-wise: **Claude Code** (`opus`/`sonnet`/`haiku`), **Pi (local-only)** (concrete Qwen3.6 model IDs from `~/.pi/agent/models.json`), and **Pi (hybrid)** (local default + cloud fallback for heavy reasoning). Orchestrator-Claude identifies its own runtime and picks the matching column. No hook required for the routing itself.
- **Swift-implementation specialization** — Swift/SwiftUI implementation phases route to `qwen3.6-27b-optiQ-SFT` (Stage 12.4 SFT adapter on Qwen3.6-27B-OptiQ-4bit, served via `mlx-sft` provider) when running in Pi. Other implementation phases route to the daily-driver `qwen3.6-mlx-8bit`.
- **Canonical routing table** — `skills/setup-routing/model-routing.md` holds the full table referenced by both `setup-routing` and `adapt`. Includes phase-level sub-tables for the five multi-phase skills, model identifier documentation (Anthropic + Pi), and explicit caveats.
- **`setup-routing` Step 2 question 10** — new always-asked question: which harness(es) will run this project (Claude Code / Pi local-only / Pi hybrid). Determines which columns appear in the generated CLAUDE.md.
- **`setup-routing` Step 5.5** — new step: present model routing recommendations to the user for confirmation before generating CLAUDE.md. Mirrors the existing skill-selection-confirmation pattern in Step 5.
- **`adapt` Step 2 follow-up** — mirrors the harness question. Step 4 gap-detection now includes `### Model Routing` presence check. Step 5 inserts/updates the section without touching other CLAUDE.md content.

### Changed
- `setup-routing` and `adapt` version markers bumped to 1.11.0.
- Generated CLAUDE.md target size: 60-100 lines → 80-130 lines (Model Routing adds ~15-30 lines depending on how many skills and harnesses are selected). The ~150-line compliance budget still applies.

### Notes for users
- **⚠️ Marketplace users:** v1.11.0 adds a new `### Model Routing` subsection to generated CLAUDE.md by default. The **Pi columns reference local-model identifiers specific to the plugin author's setup** (Qwen3.6 variants in `~/.pi/agent/models.json`) — most users won't have those models installed. **To opt out**, answer "None — skip model routing entirely" when prompted for harness in `/setup-routing` (Step 2 Q10) or `/adapt` (Step 2 follow-up). Existing CLAUDE.md files are untouched until you re-run one of those skills.
- **Advisory, not enforced.** Orchestrator-Claude may ignore the recommendations — this v0.1 ships as guidance only. Hook-based enforcement (and online-vs-offline auto-detection for the Pi hybrid column) is deferred to v1.12.0.
- **Empirical validation pending.** The Pi columns lean on the user's `project_vibe_coding_config.md` memory entry (Tier 1/2/3 benchmark from 2026-05-02/03 Quern test). The Anthropic columns are sensible defaults based on each skill's dominant cognitive demand, not benchmarked across this exact skill set.
- **Existing projects:** re-run `/superpowers-gstack:adapt` to pick up Model Routing. The skill detects the older version marker and adds the section without touching other content.
- **Pi model availability:** routing references concrete model IDs (e.g. `qwen3.6-mlx-8bit`, `qwen3.6-27b-optiQ-SFT`). Confirm coverage with `cat ~/.pi/agent/models.json | grep '"id"'` before relying on Pi-column recommendations.
- **Design rationale:** full design doc with scope decisions, known gaps, and future work is at `docs/superpowers/specs/2026-05-12-model-routing-design.md`.

## [1.10.0] - 2026-04-29

### Added
- **`/macos-e2e-scaffold` skill** — One-shot XCUITest scaffolding for macOS SwiftUI projects. Walks the Scene tree deterministically (Read+Grep, no LLM judgment), ranks views by interactive-control density, and generates ranked TIER-1/2/3 test stubs (Smoke + Happy-path + Error-recovery always; Modal/Menubar/Multi-window/Toolbar conditional on pattern detection). Suggests accessibility identifiers with `<ViewName>_<ControlType>_<Purpose>` convention and applies them via batch confirmation (`[a]ll`/`[c]herry-pick`/`[s]kip`). Emits a Claude-readable `scripts/run-uitests.sh` that parses xcresult to JSON (Xcode 16+) with plaintext fallback. Three project-type branches: xcodegen-managed (modifies yml), SPM-based (honest limitation — UI tests require .xcodeproj), plain .xcodeproj (manual Xcode steps; never edits project.pbxproj programmatically). Phase 0 self-check refuses non-Swift, non-SwiftUI, non-macOS, or already-scaffolded projects. Manual invocation only — distinct from artefact-review skills which auto-trigger.

### Changed
- `setup-routing` and `adapt` version markers bumped to 1.10.0.
- IDEAS.md: added three sibling stubs (`ios-e2e-scaffold`, `swiftui-snapshot-scaffold`, `appkit-e2e-scaffold`) using the same Gap/Scope/Method/Differentiation/Status template; added `macos-e2e-scaffold` to "Shipped" section.

### Notes for users
- Skill creates new files (UI test target, identifier-doc, runner script) and modifies existing view files (adds `.accessibilityIdentifier(...)` after batch confirmation). Run only after committing or stashing in-progress work.
- Skill is the first plugin-internal skill that *generates code* rather than *reviewing artefacts*. Mental model: `/setup-routing` for the project itself, `/macos-e2e-scaffold` for the project's UI test infrastructure.

## [1.9.1] - 2026-04-29

### Changed
- **README workflow integration** — the three plugin-internal review skills (`/pitfall-verification`, `/quality-review`, `/macos-native-review`) were announced in v1.5.0, v1.8.0, and v1.9.0 in the "What's Included" section but never integrated into the README's workflow guidance. Result: users knew the skills existed but couldn't see where to invoke them in practice. This patch fixes that:
  - **"The Workflow" 4-phase diagram** gains a new `PHASE 1.5: SPEC REVIEW (this plugin)` block between Phase 1 (planning) and Phase 2 (implementation).
  - **"Common Scenarios → New Feature (Full Workflow)"** now shows the spec-review trio explicitly between `/plan-eng-review` and `/superpowers:brainstorming`, plus a `/pitfall-verification` re-check after `/superpowers:writing-plans`.
  - **"Decision Tree"** gains a "Spec or plan written?" branch routing to the review trio before implementation.
- `setup-routing` and `adapt` version markers bumped to 1.9.1.

### Notes for users
- No skill or behavior changes. Documentation-only patch addressing a discoverability gap surfaced after v1.9.0 shipped.

## [1.9.0] - 2026-04-28

### Added
- **`/macos-native-review` skill** — Apple-native conformance gate for macOS PRDs, specs, and implementation plans. Walks 12 HIG-grounded categories (vocabulary, control choices, keyboard shortcuts, semantic colors, sheets/popovers/alerts, animation timing, privileged operations, accessibility, menu bar, app lifecycle, dock icon behavior, App menu) and cites `developer.apple.com/design/human-interface-guidelines/...` for every finding via WebFetch. Phase 0 self-check rejects non-macOS artifacts (returns `N/A` for iOS-only or non-Apple projects). `PROVISIONAL` fallback when the HIG site is unreachable — never silently substitutes training-data recall for verified citations. Sequential after `/pitfall-verification` and `/quality-review`: that pair asks *"will this work?"* and *"will this feel good?"*; this asks *"is this Apple-native?"*. Sibling skills (`ios-native-review`, `windows-native-review`, `material-design-review`) deferred as IDEAS.md backlog entries with consistent template.

### Changed
- `setup-routing` and `adapt` version markers bumped to 1.9.0.
- IDEAS.md: removed the `macos-native-review` proposal entry (skill shipped); added three sibling stubs (`ios-native-review`, `windows-native-review`, `material-design-review`) using the same Gap/Scope/Method/Differentiation/Status template.

## [1.8.1] - 2026-04-28

### Changed
- **Claude Code** version tracking bumped to 2.1.119 (was 2.1.114). Folds in the auto-update workflow's PR #9 — closed in favour of this patch because PR #9's `[1.7.1]` slot collided with the just-shipped `[1.8.0]`. No skill or behaviour changes.

## [1.8.0] - 2026-04-28

### Added
- **`/quality-review` skill** — perceived-quality gate run after a PRD, spec, or implementation plan, before implementation begins. Walks 15 categories of "feels cheap" risks (silent failures, missing loading/empty states, error recovery, state drift, scope leakage in workspaced apps, animations, AI structured output, sudo flows, sort order, localization-readiness) and produces severity-tiered findings (CRITICAL / SIGNIFICANT / POLISH) with concrete file/section-anchored fixes. Complementary to `/pitfall-verification`: that one asks *"will this work?"*, this one asks *"will this feel like a premium product, on the level of CleanMyMac, Raycast, Linear, Things, Stripe Dashboard?"*. Recommended flow on a fresh artifact: `/pitfall-verification` → fix bugs → `/quality-review` → fix feel → hand off to implementation.

### Changed
- `setup-routing` and `adapt` version markers bumped to 1.8.0.

## [1.7.0] - 2026-04-27

### Added
- **`/context-handoff` skill** — renamed from `/context-guard` to better describe what it does: writes a human-readable handoff file (`docs/superpowers/handoff.md`) in the project repo before `/clear` or `/compact`. Not the same as gstack's `/context-save` (which stores machine-local state in `~/.gstack/`) — this lives in the repo and works cross-machine without gstack installed.

### Fixed
- **GitHub Actions model ID** — both `check-updates.yml` and `self-repair.yml` used the retired `claude-sonnet-4-20250514` model ID, causing all CI API calls to fail. Updated to `claude-sonnet-4-6`.

### Changed
- **VERSIONS.md** — GStack bumped to v1.15.0.0 (dde5510), verified 2026-04-27.
- All references to `/context-guard` updated to `/context-handoff` across CLAUDE.md, README.md, setup-routing, adapt, and the generated CLAUDE.md template.

## [1.6.1] - 2026-04-26

### Fixed
- **`CLAUDE.md` routing rule** — replaced the stale `→ invoke checkpoint` rule with explicit rules for `/context-save`, `/context-restore`, and `/context-guard`. The `/checkpoint` command was removed from gstack in plugin v1.4.0 but the routing rule was missed at the time.

### Changed
- **Routing tables synced with gstack v1.14.0.0** — added 14 new gstack skills to `setup-routing/SKILL.md`, `adapt/SKILL.md`, and `README.md` Quick Reference: `/design-consultation`, `/design-html`, `/design-shotgun`, `/devex-review`, `/guard`, `/landing-report`, `/open-gstack-browser`, `/pair-agent`, `/plan-devex-review`, `/plan-tune`, `/setup-browser-cookies`, `/setup-deploy`, `/setup-gbrain`, `/unfreeze`.
- `VERSIONS.md` updated: GStack v1.4.0.0 → v1.14.0.0 (verified 2026-04-26).
- `.update-state.json` refreshed (last successful check was 2026-04-06).

### Notes for users
- No behavior changes to existing routing rules.
- gstack v1.x ships several internal behavior changes that don't affect plugin routing but are worth knowing about: workspace-aware `/ship` (auto-detects PR queue collisions), plan-mode review skills now run inline without an exit-and-rerun handshake, and the browser sidebar is now an interactive Claude Code REPL.

## [1.6.0] - 2026-04-22

### Added
- **Dependency check** in `setup-routing` and `adapt` — before any other action, the skills now verify that both upstream frameworks (Superpowers, GStack) are installed at their expected paths. If either is missing, the skill stops and prints the exact install commands for the missing framework(s). Prevents cryptic mid-flow failures for new users and keeps the plugin's "glue layer" contract explicit: the underlying tools are not bundled — they must be installed separately.

### Changed
- Corrected marketplace instructions across README, CLAUDE.md, and install-plugin.sh — plugin lives in `Paretofilm/claude-marketplace` (`paretofilm-plugins`), not `kjetilge/kjetil-claude-marketplace` (`kjetil-plugins`).

## [1.5.0] - 2026-04-22

### Added
- **Pitfall verification skill** (`/superpowers-gstack:pitfall-verification`) — targeted final-check skill that runs after any PRD, spec, plan, or code artifact. Not a generic review: it checks that typical pitfalls for that artifact type and domain (security, idempotency, integration contracts, edge cases, LLM output) actually do not apply. Two rounds max, domain-specific inference encouraged.

### Changed
- Plugin.json bumped to 1.5.0 (1.4.0 in CHANGELOG was auto-generated but plugin.json was not bumped in PR #6 — this release re-aligns the two).
- VERSIONS.md: GStack version label corrected from `unknown (d0782c4)` to `v1.4.0.0 (d0782c4)`; verification date rolled forward to 2026-04-22.
- Supersedes PR #4 (conflicting auto-update branch) — closes issues #5 and #7.

## [1.4.0] - 2026-04-20

### Added
- **New skill**: `/make-pdf` — Markdown to publication-quality PDFs for technical documents and reports
- **New skill**: `/benchmark-models` — Cross-model benchmark comparing Claude, GPT, and Gemini side-by-side for latency, tokens, cost, and quality
- **New skill**: `/learn` — Save cross-session learnings for long-running projects (> 2 weeks)
- **New skill**: `/codex` — OpenAI Codex CLI wrapper with three modes: code review, adversarial challenge, and consultation

### Changed
- **Skill renamed**: `/checkpoint` → `/context-save` and `/context-restore` — Claude Code was treating `/checkpoint` as a native rewind alias, causing conflicts
- `/cso` upgraded to version 2.0.0 with enhanced security audit capabilities
- `/browse` upgraded to version 1.1.0 with Puppeteer parity features including load-html, screenshot selectors, viewport scaling, and file:// support
- Updated Quick Reference with new and renamed skills
- All routing rules and CLAUDE.md templates updated to use new skill names

### Updated upstream versions
- GStack: Major version 1.0.0+ with simpler prompts and improved performance metrics
- Claude Code: 2.1.114 (from 2.1.92) with various stability improvements

### Fixed
- `/ship` now detects and repairs VERSION/package.json drift in Step 12
- Context management improvements for `/plan-ceo-review` and `/office-hours`
- Browser session management with auto-shutdown and disconnect cleanup
- Windows ngrok build issues resolved
- Security hardening with 12 fixes across multiple areas

## [1.2.0] - 2026-04-07

### Added
- Context Guard skill (`/context-guard`) — lightweight context management inspired by GSD. Saves session state to `docs/superpowers/handoff.md`, auto-resumes after `/clear` or `/compact`, and proactively suggests context resets.
- Session continuity rules in CLAUDE.md template — auto-reads handoff.md on session start, offers auto context guard after `/compact`.
- Auto-mode marker (`## Mode: auto`) in handoff.md for persistent state across compacts.
- CHANGELOG.md is now automatically updated by the GitHub Actions update pipeline.

### Changed
- Consolidated workflow manual into README. Single source of truth — scenarios, quick reference, decision tree all in README now.
- Routing rules clarified: checkpoint = git snapshot (end of day), context-guard = session state (before /clear).
- Stronger "wait for confirmation" instructions in adapt and setup-routing skills (STOP HERE blocks).
- Fixed `/freeze` description in evaluation tables — now correctly described as allow-list, not block-list.
- Plugin description updated to mention context management.
- GitHub Actions workflow updated to use README instead of removed workflow manual.

### Removed
- `superpowers-gstack-workflow-manual.md` — content merged into README.

## [0.0.1.0] - 2026-04-07

### Added
- Marketplace installation as the primary install path. Plugin is now discoverable in Claude Code's skill list after installing via `/plugin marketplace add` + `/plugin install`.
- "Run from project directory" guidance across manual, README, skills, and appendix troubleshooting. Prevents wrong project slug detection and misplaced design docs.
- "Tiny Project" fast-path scenario for projects with fewer than 5 tasks. Skip Phase 1, use executing-plans instead of SDD, tests = spec compliance.
- Design-doc handoff callout in Phase 1→2 transition. "Adopt the design as-is" is now a prominent blockquote instead of a buried tip.
- Directory check in both `setup-routing` and `adapt` skills. Stops the user before they run the skill from the wrong directory.
- Troubleshooting entries for plugin discovery via symlink vs marketplace, and wrong project detection.
- Unknown argument validation in `install-plugin.sh`. Rejects typos like `--Dev` instead of silently printing marketplace instructions.
- GStack skill routing rules in CLAUDE.md.
- Implementation plan for the 4 fixes at `docs/superpowers/plans/`.

### Changed
- `install-plugin.sh` is now dev-only (`--dev` flag). Default behavior prints marketplace install instructions instead of creating a symlink.
- README "Quick Start" renamed to "Kickstart" with tagline and restructured install flow.
- Manual install section split bash commands and Claude Code slash commands into separate code blocks.
- Phase 1 "When to skip" guidance strengthened with explicit small-project threshold (< 5 tasks, < 30 minutes).
