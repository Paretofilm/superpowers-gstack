# swiftui-view-gate (3.12.0) — implementeringsplan

**Mål:** En SwiftUI-endring i et native prosjekt er ikke «ferdig» før visningen er slått opp, linted og *sett*, og agenten kan se den uten å avbryte brukeren.

**Spec:** `docs/superpowers/specs/2026-10-15-swiftui-view-gate-design.md`

## Global Constraints

- Bare standardbiblioteket i Python, `from __future__ import annotations`; bash med `set -uo pipefail`.
- Skript: exit 0 ok, 2 avvist med `BLOCKED — …` / `USAGE ERROR: …` på stderr, aldri en traceback (`view-gate.py nudge` er unntaket: alltid exit 0).
- Blokkfiler på engelsk, linje 1 er H2 med `<!-- gstack-<navn>-vN -->`, aldri `emitted=` i fila, egne skills med prefikset `/superpowers-gstack:` (lint E9).
- Skill-beskrivelse høyst 30 ord. `python3 scripts/lint-skills.py` skal gi `0 error(s), 0 warning(s)` etter hver oppgave.
- gstack- og superpowers-skills endres ikke.
- Versjon 3.12.0 bumpes bare i oppgave 7.
- Hver commit slutter med attribusjonslinjene fra økten. Ingen landing uten brukerens ja; push er backup og gjøres.
- Grunnlinje: lint grønn, `pytest tests/unit` gir 222 passed før første feil; `test_branch_hygiene_hook.py::test_a_killed_hook_leaves_no_transport_running` feiler fra før i skymiljøet og hører ikke til denne endringen.

## Review Focus

1. `window-shot.sh` skal aldri ta skjermbilde uten `host`-pinnen, og aldri av hele skjermen.
2. `view-gate.py nudge` må aldri blokkere eller krasje en filskriving.
3. Pinne-validering skal avvise `Host`, `host ` og tom fil, ikke tolke dem som `off`.
4. Blokkversjonen v10 må erstatte v1–v9 uten at lint-denylisten treffer selve v10.

## Oppgaver

- [x] **1. `scripts/view-gate.py`** (4b93d27, sammen med 2) (`nudge`, `files --base`) + `tests/unit/test_view_gate.py`. Visningsfil = `.swift` som matcher `\b(struct|class|extension)\s+\w+\s*:\s*[^{]*\bView\b` eller `some View`, eller ligger under `Views/` / `Components/`. Tilstand per økt i tempkatalogen som `explainer-nudge.py`. Commit: `feat(view-gate): påminnelse og filliste for SwiftUI-visninger`.
- [x] **2. Hook-oppføring** (4b93d27) i `hooks/hooks.json`: `PostToolUse` med matcher `Write|Edit|MultiEdit|mcp__.*review_(macos_hig|accessibility|liquid_glass)`. Test at JSON er gyldig og peker på et eksisterende, kjørbart skript. Commit: `feat(view-gate): koble påminnelsen til PostToolUse`.
- [x] **3. `.gstack/visual-verify` + `scripts/window-shot.sh`** + tester (`tests/unit/test_window_shot.py`): ugyldig/manglende pinne, ikke-macOS, feil argumenter. `adapt-claude-md.py` validerer pinnen (`read_visual_verify`, samme form som `read_executor`) og skriver den aldri. Commit 7c07859. Avvik: `window-shot.sh` tar valgfri `WINDOW_SHOT_EXPECT` (full kjørbar sti) i stedet for en egen «prosjektets egen PID»-sjekk, fordi bare beviset fra verify-and-land Phase 5 kan si hva som er prosjektets egen; testene bruker falske `uname`/`swift`/`screencapture`/`sips` på `PATH`.
- [x] **4. Skill `skills/swiftui-view-gate/SKILL.md`** + `skills/swiftui-view-gate/tests/required-sections.test.sh`. Commit 4620825 (sammen med 6: lint E3 krever ruting før skillen kan committes grønn).
- [x] **5. `xcode-tools` v10 + `verify-and-land`**: nytt avsnitt og anti-pattern i blokken, Phase 1/5b/6 i `verify-and-land`, lint-denylist `v[0-8]` → `v[0-9]` unntatt v10, oppdaterte tester (`test_e2e_executor_marker.py`, `test_lint_adapt_and_blocks.py`, `test_verify_and_land.py`). Commits 8a5779c og 38fe2d9 (den andre retter en test jeg brøt med linjeskift midt i «land nothing»).
- [x] **6. Routing og README**: rute i `CLAUDE.md`, skill-liste i `README.md`. Commit: `docs(view-gate): routing og README`.
- [x] **7. Utgivelse**: `plugin.json` → 3.12.0, CHANGELOG-oppføring (med hva som ikke er verifisert på Mac og teksten til hook-endringen brukeren bør gjøre), `IDEAS.md` → SHIPPED, fullt sett: lint, pytest, `required-sections`-tester. Commit: `chore(release): 3.12.0 swiftui-view-gate`.
- [x] **8. Pitfall-verification** (self-pitfall + uavhengig lesing i samme hus; Codex og tredje hus fantes ikke i skybeholderen, se CHANGELOG 3.12.0 «Review») på det samlede resultatet (`scripts/classify-change.py` gir gulvet), funn rettet i egne commits, så push og draft-PR.

## Utsatt (med utløser)

- Rute 3 (datamaskinbruk for interaksjon) — utløses hvis en vertsinnstilling for forhåndsgodkjente apper finnes.
- Automatisk `#Preview`-generering — utløses hvis `live-swiftui`-fallbacken i praksis oftest trengs.
