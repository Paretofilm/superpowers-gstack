# Modernisering 3.0.0 — plan

Grunnlag: `docs/superpowers/specs/2026-09-11-modernisering-audit.md`. Branch `feat/modernisering`, arbeidstre `../superpowers-gstack-modernisering`.

## Fase 1 — hygiene (ingen atferdsendring)

- [x] third-lens: `z-ai/glm-5.2` → `z-ai/glm-5.3`; modell-vaktbikkje mot OpenRouter `/models`; benchmark-tall ut
- [x] autoimplement: audit-trail-tabell, regex-historikk og «Why»-essays ut (til CHANGELOG); `gpt-5.5` ut; Workflow-verktøy som dispatch-runtime
- [x] office-hours-track-aware: personlige stier ut (agent 4)
- [x] cost-ledger fjernes: `scripts/cost-ledger/`, pitfall-seksjon, tests/run.sh, lint.yml, check-plugin-version.sh
- [x] ios-visual-explore fjernes: skill, `scripts/computer_use/`, `scripts/ios-visual-explore/`, `tests/unit/computer_use/`
- [x] session-continuity: legacy `auto` / `## Mode: auto` / v1.12-format ut (v4-markør)
- [x] model-routing.md + model-routing-section: priser, benchmarks, datoer, Fable-fallback-påstand ut; ID-er kun i model-routing.md
- [x] quality-review: kategori 12 → peker til `claude-api`-skillen

## Fase 2 — kontekstskatt

- [x] autonomy-blokken fjernes (harnessen dekker den); adapt fjerner gamle seksjoner med `gstack-autonomy-vN`
- [x] git-hygiene: «When the session-start hook reports unlanded work» flyttes inn i `check-branch-hygiene.sh` sin stdout (v10)
- [x] multi-lens-blokk uten modell-ID-er og priser (v7); Codex-passet eies av gstack `/review`

## Fase 3 — sammenslåinger

- [x] `e2e-scaffold` = ios- + macos-e2e-scaffold (agent 1); runner til `templates/run-uitests.sh`; `tests/unit/test_e2e_executor_marker.py` oppdateres
- [x] `apple-native-review` = ios- + macos-native-review (agent 2); sitater via `mcp__apple-docs__*`
- [x] swiftui-design-consultation slankes (agent 3); Artifact-verktøyet for forhåndsvisning
- [x] e2e-route ~120 linjer, office-hours-track-aware ~100 linjer (agent 4)
- [x] htmlify demoteres: Safari-flyt og PostToolUse-hook ut; `companion.css` beholdes

## Fase 4 — arkitektur (utsatt, egen PR)

- spec-drift mot gstack 1.84.1: upstream flyttet subagent-prompten i `ship/sections/plan-completion.md` inn i en ````text-fence, som `scripts/spec-drift.py` maskerer før anker-skann → `repin` blokkeres med «ANCHORS MISSING». Oppdaget 2026-09-11 da gstack auto-oppgraderte midt i 3.0.0-økten; `tests/unit/test_spec_drift_upstream_alarm.py` er rød på maskiner med gstack ≥ 1.83, grønn i CI. Egen fix.

- adapt → deterministisk merge-script; setup-routing inn i adapt (rører lint E8/E13 og 6 testfiler)

## Release

- [x] lint grønn, pytest grønn, `sync-own-claude-md.py`
- [x] plugin.json 3.0.0 + CHANGELOG; README-liste; CLAUDE.md-ruting; VERSIONS.md
- [ ] pitfall-verification → /ship (after commit)
