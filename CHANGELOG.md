# Changelog

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
