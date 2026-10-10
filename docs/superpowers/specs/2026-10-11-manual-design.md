# Manual for superpowers-gstack — designspesifikasjon

Dato: 2026-10-11 · Status: utkast til gjennomgang · Sti: `docs/superpowers/specs/2026-10-11-manual-design.md`

## 1. Mål og målgruppe

En norsk manual for en vibe-koder som bygger apper sammen med Claude Code. Brukeren jobber alene, har mange parallelle prosjekter og glemmer lett hva som ble besluttet i forrige økt. Manualen skal fjerne fem friksjoner:

1. Vet ikke hvilken kommando som passer nå.
2. Mister tråden mellom økter.
3. Forstår ikke hva som skjer under panseret.
4. Vet ikke når resultatet kan stoles på.
5. Vet ikke hvordan et helt blankt prosjekt (tom mappe) startes.

**Bruksmåte:** kart + kapitler. Én side med hele flyten som diagram øverst, deretter korte kapitler man hopper til ved behov.

**Innhold:** den ideelle arbeidsflyten. Kjernen er brukerens faktiske rytme (se kapittel 2). De ubrukte verktøyene som lukker hull står i et eget, tydelig merket kapittel (anbefalt, ikke vane).

**Spor:** felles kjerne, med eget kapittel for Swift/SwiftUI (sing-replay, live-swiftui, spare-mac) og for web/Python/pipeline (Kvitteria, Resolve-ai-worker, fagfilm-pipeline).

**Utenfor omfanget:** manualen erstatter ikke `README.md` (439 linjer, engelsk, utdatert ruting fra v0.2). README får én lenke til manualen, ellers røres den ikke. Ingen endring i skills, hooks eller `adapt`.

## 2. Datagrunnlag (målt 2026-10-10)

Kilde: Claude Code-transkripter under `~/.claude/projects/` for live-swiftui, Resolve-ai-worker, fagfilm-pipeline, KvitteriAi, spare-mac og superpowers-gstack, pluss `~/.claude/history.jsonl`. Transkriptene starter 2026-09-15, og `sing-replay` har ingen transkripter igjen. Der er grunnlaget 151 commits og `docs/superpowers/` (planer, spec, `progress.md`).

Skill-kall i de seks prosjektene (61 hovedøkter): `pitfall-verification` 39, `third-lens-review` 27, `/review` 27, `brainstorming` 23, `writing-plans` 16, `subagent-driven-development` 15, `adapt` 14, `land` 10, `context-handoff` 9 (15 i historikken), `codex` 9, `test-driven-development` 7, `finishing-a-development-branch` 4, `using-git-worktrees` 4, `investigate` 3, `systematic-debugging` 2, `vibe` 2. Omtrent 700 subagent-kall.

Ikke brukt eller knapt brukt: `/ship` (1), `/qa`, `/design-review`, `/retro`, `/health`, `/document-release`, `/office-hours` (0 i loggene, 7 i historikken), `verification-before-completion` (0), `requesting-code-review` (0), `dispatching-parallel-agents` (0), `quality-review` (1), `spec-drift` (0), `e2e-scaffold` (0), `swiftui-design-consultation` (0), `htmlify` (1).

**Regel for tallene i manualen:** hvert tall står med måledato og kilde, og kapittelet «Lukk hullene» kan regenereres med `scripts/workflow-metrics.py skills`. Tallene er et øyeblikksbilde, ikke en egenskap ved verktøyene.

## 3. Kapitler

| # | Fil | Innhold |
|---|---|---|
| 0 | `00-kartet.md` | Hele flyten på én side: idé → spec → plan → bygg → bevis → landing, med stoppesteder for brukeren. |
| 1 | `01-start-her.md` | Quickstart fra tom mappe: `git init`, `/superpowers-gstack:adapt`, første funksjon, første landing. |
| 2 | `02-hva-kjorer-jeg-na.md` | Beslutningstre: bug, ny feature, før landing, lang kontekst, ny økt. |
| 3 | `03-flyten.md` | Steg for steg: brainstorming → spec → plan → subagent-drevet bygging → TDD. |
| 4 | `04-bevis.md` | Når kan resultatet stoles på: verifiseringskjeden, `verify-and-land`, landing. |
| 5 | `05-mellom-okter.md` | `handoff.md`, `progress.md`, `/clear`, `/compact`, sesjonsgjenopptak. |
| 6 | `06-under-panseret.md` | Subagenter, worktrees, de tre modellhusene, hooks. |
| 7 | `07-spor-swift.md` | Native apper: Liquid Glass, HIG-gjennomgang, simulator, E2E. |
| 8 | `08-spor-web.md` | Web/Python/pipeline: `/qa`, nettleser, sikkerhetsgjennomgang. |
| 9 | `09-lukk-hullene.md` | De ubrukte verktøyene, merket som anbefalt: `verification-before-completion`, `/qa`, `/investigate`, `quality-review`, `spec-drift`, `/retro`, `/health`. |
| 10 | `10-verktoykassa.md` | Halvsides forklaringer med figur: worktrunk (`wt`), modellhus (Codex, tredje linse, `agy`), Swift-verktøy (live-swiftui, swiftui-rag, XcodeBuildMCP), Calyx og reserve-Mac (`vm-run`). |

Rekkefølgen er godkjent av brukeren 2026-10-11.

Hvert kapittel starter med to linjer: «Bruk denne når …» og «Du er ferdig når …».

## 4. Byggemåte (valgt: A)

```
docs/manual/
  00-kartet.md … 10-verktoykassa.md   kapitler (kildesannhet)
  figurer/*.svg                       håndtegnede diagrammer
  manual.css                          Liquid Glass, lys og mørk
  manual.html                         bygget, sjekkes inn
scripts/build-manual.py               kapitler + figurer → manual.html
```

**`build-manual.py`:**
- Leser kapitlene i filnavnrekkefølge. Limer inn SVG der kapittelet har `![[figurer/navn.svg]]` på egen linje.
- Lager innholdsfortegnelse med ankerlenker.
- Skriver én selvstendig HTML-fil uten eksterne avhengigheter (fungerer lokalt og som Artifact).
- Deterministisk: samme kilder gir byte-lik utdata, slik at «bygget fra gjeldende kapitler» kan sjekkes ved å bygge på nytt og sammenligne.
- Kjører `skills/htmlify/bin/explain-check` på resultatet (avklipt og overlappende tekst, skjermbilde).

**Gjenbruk:** `htmlify` leverer `styles/explainer.css` og `explain-check`. Antakelsen er at `explain-check` brukes som den er, og at `manual.css` låner fargetokens og glassflater fra `explainer.css` i stedet for å kopiere dem (manualen er én lang side, `explainer.css` er laget for én spec). Ingen av filene er lest ennå; kodegjenbrukssjekken (søk, les, velg gjenbruk/utvid/skriv nytt) gjøres første steg i planfasen, og planen oppdateres hvis antakelsen ikke holder.

**Alternativer som ble forkastet:** håndskrevet HTML (lint-sjekken må tolke HTML, teksten driver fra virkeligheten, slik README gjorde) og `htmlify explain` per kapittel (laget for én spec om gangen; gir mange sider, og brukeren valgte én).

## 5. Lint-sjekk E15

Ny sjekk i `scripts/lint-skills.py`, i release-porten (CI og `pre-merge`-hooken i `.config/wt.toml`):

- **E15a:** hver skill-referanse i `docs/manual/*.md` (`/superpowers-gstack:<navn>`, `superpowers:<navn>`, gstack-kommandoer som `/qa`) må finnes. Plugin-skills sjekkes mot `skills/`. Superpowers-skills sjekkes mot den innsjekkede listen fra E10. gstack-kommandoer sjekkes mot en innsjekket liste over gstack-kommandoer manualen får lov å nevne.
- **E15b:** hver skill i `skills/` må være nevnt minst én gang i manualen.
- **E15c:** `docs/manual/manual.html` må være identisk med det `build-manual.py` lager nå.
- Sjekken følger E10s mønster, slik at maskiner uten oppstrøms installasjon ikke feiler (gstack-listen er innsjekket, ikke lest fra `~/.claude/skills`).

Ny skill, fjernet skill eller omdøpt skill uten manualoppdatering gir rød lint. Teksten oppdateres fortsatt for hånd; sjekken sørger bare for at det ikke kan glemmes.

## 6. Figurer

Håndtegnede SVG, ingen Mermaid (brukerens preferanse). Liquid Glass-stil, lys og mørk via CSS-variabler.

1. Hovedkartet (kapittel 0).
2. Beslutningstreet «hva kjører jeg nå?» (2).
3. Verifiseringskjeden: egen sjekk → Codex → tredje modellhus → syntese (4, 6).
4. Hva en subagent ser og ikke ser, og hvorfor `progress.md` finnes (6).
5. Worktree-bildet: én mappe per oppgave, landing på `main` (6, 10).
6. Tidslinje over en økt: handoff → `/clear` → gjenopptak (5).
7. Swift-sporet kontra web-sporet side ved side (7, 8).

Alle figurer måles med `explain-check` før manualen regnes som ferdig.

## 7. Tone og skriveregler

- Norsk, du-form, korte setninger. Riktig norsk bøying (aldri «synke» for «sync»).
- Forkortelser skrives ut ved første bruk og ved tvil, slik brukerens globale regel krever.
- Fagbegrep forklares i samme setning som de brukes.
- Hver kommando står fullt ut, klar til å limes inn. Kommandoer som stiller spørsmål underveis markeres som «må kjøres i et ekte terminalvindu».
- Eksempler hentes fra brukerens egne prosjekter.
- Ikke-avhengigheter (alt utenfor Superpowers og gstack) forklares enkelt og kort, uten innstillingsdetaljer.

## 8. Kvalitetssikring

1. Egen gjennomgang: plassholdere, motsigelser, omfang, tvetydighet.
2. `/superpowers-gstack:pitfall-verification`. Nivået settes av `scripts/classify-change.py`; manualen med ny lint-sjekk og byggeskript regnes som ship-worthy minimum.
3. Hver påstand om hva en skill gjør sjekkes mot skill-filen (`SKILL.md`), ikke mot hukommelsen.
4. Release-porten: `python3 scripts/lint-skills.py` grønn, versjonsbump i `.claude-plugin/plugin.json`, CHANGELOG-oppføring, README-lenke.
5. Testing: pytest for `build-manual.py` (deterministisk utdata, manglende figur gir feil, ankere) og for E15 (positiv og negativ test per delsjekk).
6. Brukeren åpner `manual.html` og leser den før landing.

## 9. Leveranse

- Markdown-kilde og bygget HTML i repoet (`docs/manual/`).
- Publisert som Artifact (privat som standard), lenken gis til brukeren.
- Landing: `Landing mode: solo`, altså `/superpowers-gstack:land`.

## 10. Åpne punkter

- **Ingen blokkerende.** Under planfasen avgjøres: eksakt navn på gstack-listen som E15a bruker, og om `manual.css` kan arve tokens fra `explainer.css` direkte eller må kopiere dem.
- Manualens tall om bruk regenereres ved neste større utgivelse; datoen står i teksten.
