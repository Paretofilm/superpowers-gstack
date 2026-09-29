# Worktrunk-integrasjon — design

**Dato:** 2026-09-29 · **Status:** revidert etter self-pitfall (runde 1) og Codex-utfordring; venter på tredje linse og brukergjennomgang · **Målversjon:** 3.4.0
**Bakgrunn:** `docs/superpowers/.handoff-last.md` (utredning av `max-sixty/worktrunk`, `wt` v0.79.0)

## Formål

Brukeren er én solo vibe-coder. Målet er at worktrees brukes **automatisk** og at
**pull requests unngås** for prosjekter uten review. Pluginen skal lære alle prosjekter
den adapterer denne arbeidsmåten, ikke bare dette repoet.

**Suksess:** Brukeren skriver aldri `git worktree` eller `gh pr create` selv, og alt arbeid
havner på `main` med lint og tester grønne. Landing er **én kommando**, ikke en sekvens
agenten må huske. Enhver feil stopper med all tilstand intakt, og aldri med automatisk reparasjon.

## Avgjørelser

| Tema | Valg |
|---|---|
| Sikkerhetsnett i stedet for PR | Lokal sperre: `pre-merge`-hook som har **samme kommandoer som CI** og er grønn på `main` før den slås på. Prosjekter uten `pre-merge`-hook får ikke solo-landing (kode 9). CI kjører etterpå som bakstopper. |
| Stash | Forbudt (delt mellom worktrees). Ulagret arbeid flyttes til `wip/<tema>`-branch. |
| Squash | `wt merge --no-squash`. SHA per fase bevares så lenge `main` ikke har flyttet seg; flytter den seg, rebaseres grenen og SHA-ene omskrives (se F5). |
| Hvor reglene bor | Egen delt blokk i `CLAUDE.md` (tilnærming A). Ingen `PreToolUse`-hook nå. |
| Hvordan landing utføres | **Ett skript** (`scripts/land-worktree.py`), kalt av blokken og av `autoimplement`. Det er bevisst lite: lås, hent, sjekk, merge med hook, push, stopp ved enhver feil. |
| Ingen automatisk reparasjon | Skriptet kjører aldri `git reset`, og prøver aldri landing på nytt av seg selv. Feil stopper med worktree, gren og `main` urørt, og skriptet skriver kommandoene brukeren kan kjøre. |
| `--no-hooks` | Aldri. En sperre som omgås er verre enn ingen sperre. |
| Hvordan økten kommer inn i worktreet | `wt switch --create <gren> --no-cd --format=json`, deretter verktøyet `EnterWorktree` med `path`. Da er arbeidsmappen worktreet, og vanlige `git`-kall og `/review` virker uten `-C`. Reserve: `git -C <sti>`. Må verifiseres i planens fase 0. |
| Parallelle agenter | Utenfor omfanget. `autoimplement` kjører faser sekvensielt. |
| `copy-ignored` | Ikke i dette repoet. Prosjekter med `node_modules` eller `.env` bruker `.worktreeinclude`. |
| Personlig konfig og Codex-modell | Uavhengig av resten (komponent 7), valgfri, og endres bare etter at brukeren har sett diffen. Standard byttes fra GPT-6 Astra ($10/$50 per million tokens) til GPT-6 Sol ($2/$10); kvalitet er ikke målt for kodegjennomgang (F9). |
| Godkjenning av hooks | Brukeren kjører `wt config approvals add` én gang. Agenter bruker aldri `--yes`. |

## Komponenter

| # | Komponent | Endring |
|---|---|---|
| 1 | `skills/adapt/blocks/worktrunk.md` (ny) | Regler for worktree-start, `EnterWorktree`, solo-landing via skriptet og fallback uten `wt`. Linjen `Landing mode: solo`. Ber agenten foreslå en `.config/wt.toml` med `pre-merge` hvis prosjektet mangler en (krever brukerens godkjenning). Handoff skrives til primærmappen. |
| 2 | `skills/adapt/blocks/git-hygiene.md` v11→v12 | Peker til worktrunk-blokken for solo-landing. Stash-forbud og `wip/`-regel urørt. |
| 3 | `scripts/adapt-claude-md.py`, `scripts/lint-skills.py`, `scripts/sync-own-claude-md.py` | Ny `Block(...)` i `BLOCKS` med sentinel. Blokken føres også inn i `MARKER_BLOCKS` (lint E8) og i `UNIVERSAL` (repoets egen `CLAUDE.md`). Uten de to siste blir lint rød og dette repoet lærer ikke regelen. |
| 4 | `skills/autoimplement/SKILL.md` | Check 1: er `HEAD` på `main`, opprettes worktree `autoimpl/<plan-slug>` fra `main` og økten går inn i det med `EnterWorktree`. Da virker de 15 eksisterende git-kallene uten endring. Er `HEAD` allerede på en feature-gren, gjelder dagens oppførsel. Sluttlanding via skriptet. |
| 5 | `scripts/check-branch-hygiene.sh` | Foreslår landingsskriptet og `wt step prune` når `wt` finnes. Tilbyr ikke `/ship` når modusen er `solo`. `WORKTREE_SCAN_MAX` beholdes på 12 (økning gir flere `git status`-kall ved hver sesjonsstart). |
| 6 | `.config/wt.toml` (ny, dette repoet) | `pre-merge` som tabell (kommandoene kjører samtidig): `lint-skills.py`, `pytest tests/unit -q` og kontrakttestene `skills/*/tests/required-sections.test.sh`. Ingen `post-start`-hook. |
| 7 | Personlig konfig (valgfri, etter samtykke) | `GSTACK_CODEX_MODEL=gpt-6-sol` i `~/.zshenv`, `model = "gpt-6-sol"` i `~/.codex/config.toml`, `[commit.generation]` med Claude. |
| 8 | `scripts/land-worktree.py` (ny) | Landing i én kommando med lås, forhåndssjekker og feilkoder. Fjerner aldri worktreet selv. Testes med kaster-repoer. |

## Solo-landing (`scripts/land-worktree.py`)

Arbeidsflyt: `wt switch --create <type>/<tema> --no-cd --format=json`, `EnterWorktree` med stien,
commit ved milepæler, `git push -u origin <gren>` som backup. Landing er ett kall:
`python3 <plugin>/scripts/land-worktree.py --worktree <sti>`. Skriptet er uavhengig av
arbeidsmappen. Rekkefølge:

1. **Lås** per repo (atomisk `mkdir` i `git rev-parse --git-common-dir`, med pid og gammel-lås-sjekk), frigitt ved avslutning. To samtidige landinger serialiseres i stedet for å tråkke på hverandre (kode 12).
2. **Modus:** `Landing mode: pr` → kode 2, bruk `/ship`.
3. **Sperre finnes:** prosjektet må ha minst én `pre-merge`-hook (kode 9) og den må være godkjent (kode 3). Aldri `--yes`.
4. **`git fetch origin`** (kode 11 hvis den feiler).
5. **Overlapp-sjekk, før noe flyttes:** skitne filer i primærmappen (`git status --porcelain`) mot filene grenen endrer **og** filene `origin/main` endrer (kode 5, filene nevnes). `wt merge` nekter uansett (verifisert), men skriptet sier det før de to minuttene med tester og før `main` flyttes.
6. **Oppdater `main`:** `git -C <primær> merge --ff-only origin/main`. Feiler den, ligger lokal `main` foran med ikke-pushede commits (kode 4, commitene listes).
7. **Landing:** `wt -C <sti> merge --no-squash --no-remove`. Hooken kjører, grenen rebaseres, lokal `main` fast-forwardes. Rød hook gir kode 6, rebase-konflikt kode 10. Worktree og gren står.
8. **Push:** hent på nytt. Har `origin/main` flyttet seg siden steg 4, eller avvises pushen, avslutter skriptet med kode 7. Ingenting repareres. Skriptet skriver tilstanden og kommandoene brukeren kan kjøre.
9. **Slett fjerngrenen** (`git push origin --delete <gren>`) hvis den ble pushet.
10. **CI:** finn kjøringen for **den pushede SHA-en** (`gh run list --commit <sha>`, vent opptil 30 sekunder på at den opprettes) og skriv `gh run watch <id> --exit-status`. Agenten kjører den i bakgrunnen. Er den rød, er neste oppgave å fikse `main`.
11. **Skriv hva som gjenstår lokalt:** `ExitWorktree` med `keep` hvis økten står i worktreet, deretter `wt -C <primær> remove <gren>`. Skriptet gjør ikke dette selv, fordi et worktree som fjernes under økten etterlater en ugyldig arbeidsmappe.

Ship-worthy endringer går gjennom `/review` og `pitfall-verification` **før** skriptet kalles.

## `autoimplement`

- Check 1: er `HEAD` på `main`, opprettes worktree `autoimpl/<plan-slug>` fra `main`, og økten går inn med `EnterWorktree`. Kravet om at planen er committet gjelder da **på `main`**, ellers finnes ikke planen i worktreet. Ligger planen bare på en annen feature-gren, brukes den grenen som i dag (ingen nytt worktree).
- Renhet vurderes i worktreet. Primærmappens skitne filer stopper ikke kjøringen med mindre de overlapper planens filer (da nevnes de).
- Subagentene arver arbeidsmappen, og worktree-stien oppgis i prompten i tillegg. Uten `isolation: "worktree"`.
- Etter siste fase og grønn sluttreview kaller den landingsskriptet hvis modusen er `solo`. Ved `pr` stopper den og nevner `/ship`. `progress.md` får SHA-ene fra `main` etter landing, siden rebase kan ha omskrevet dem.
- Eksisterende avvisninger (migrasjoner, hemmeligheter, credentials, `.env`, `.ssh`) beholdes.

## Feilkoder

| Kode | Situasjon | Tilstand som står |
|---|---|---|
| 2 | Modus er `pr` | Alt urørt. Bruk `/ship`. |
| 3 | Hooks ikke godkjent | Alt urørt. Brukeren kjører `wt config approvals add`. |
| 4 | Lokal `main` foran `origin/main` med ikke-pushede commits | Alt urørt. Commitene listes. |
| 5 | Skitne filer i primærmappen overlapper | Alt urørt. Filene nevnes. Aldri stash. |
| 6 | `pre-merge` rød | Worktree og gren står. Fiks og kall skriptet på nytt. |
| 7 | `origin/main` har flyttet seg, eller push avvist | Lokal `main` har allerede fått commitene. Worktree og gren står. Skriptet skriver kommandoene. |
| 8 | `wt` mangler | Alt urørt. Fall tilbake til `git worktree add` og `/superpowers:finishing-a-development-branch`. |
| 9 | Ingen `pre-merge`-hook i prosjektet | Alt urørt. Agenten foreslår en `.config/wt.toml`. |
| 10 | Rebase-konflikt | Rebasen står åpen i worktreet (løs den eller `git rebase --abort`). |
| 11 | `fetch` feilet | Alt urørt. |
| 12 | Lås holdt av en annen landing | Alt urørt. Vent eller se hvem som holder den. |

## Verifisert under pitfall-review

Målt eller kjørt, ikke antatt:

- **Hook-grunnlinje:** full `pytest` gir 2 røde av 576 (`test_roster_matches_installed_upstream_when_present`, `test_pin_matches_installed_gstack_when_present`), fordi installert gstack (1.91.2) ikke er pinnet versjon. CI passerer. Tid: 141 sekunder.
- **CI-dekning:** `lint.yml` kjører lint, `pytest tests/unit` og kontrakttestene i `skills/*/tests/`.
- **`main` er ubeskyttet:** `gh api …/branches/main/protection` gir 404.
- **`wt merge` mot skitten primærmappe:** avviser når samme fil er endret, lykkes for annen fil.
- **Push avvist etter merge:** `git pull --ff-only` feiler (`Not possible to fast-forward`).
- **`autoimplement`:** 15 git-kall uten `-C` (Codex' påstand, telt).
- **Registre:** `MARKER_BLOCKS` (`lint-skills.py:138`) og `UNIVERSAL` (`sync-own-claude-md.py:32`) finnes.
- **Sesjonslogg:** `capture-session-tail.sh:48` og `:133` skriver i worktreets egen git-mappe, som fjernes sammen med worktreet.
- **`.gitignore`-filer `copy-ignored` ville kopiert:** `handoff.md`, `.handoff-last.md`, `.superpowers/`, `.update-state.json`, `__pycache__`, `.pytest_cache`.
- **Ikke kjørt:** `EnterWorktree` med `path` (kun lest i verktøybeskrivelsen), og at pluginens `PermissionRequest`-hook godkjenner det automatisk.

## Funn og håndtering

Kilde: S = egen runde, X = Codex-utfordring (GPT-6 Sol).

| # | Funn | Håndtering |
|---|---|---|
| F1 (S) | Sperren er rød fra første merge på brukerens maskin, så man fristes til `--no-hooks`. | De to `_when_present`-testene gjøres maskinuavhengige eller utelates fra hooken med CI som eier. Grunnlinjen er akseptansekrav: `wt hook pre-merge` grønn på `main` før hooken slås på. |
| F2 (S, X) | Gjenoppretting etter avvist push var feil, og automatisk `reset --keep` kan flytte `main` bakover av feil grunn (avvisning kan skyldes autentisering eller nettverk) og beskytter ikke andre commits på `main`. | Ingen automatisk reparasjon. Kode 7 stopper med tilstanden intakt. `--no-remove` gjør at grenen alltid er et gjenopprettingspunkt. |
| F3 (S, X) | En skitten primærmappe blokkerer landing, og dette repoets `CLAUDE.md` er skitten og endres av vår egen blokk. | Overlapp-sjekk **før** noe flyttes (steg 5). De tre uavklarte filene avklares av brukeren før denne endringen lander. |
| F4 (S, X) | `autoimplement` ville sjekket feil mappe: 15 git-kall uten `-C`, og `/review` kjører i arbeidsmappen. | `EnterWorktree` flytter hele økten inn, så ingen av kallene endres. |
| F5 (X, nedgradert til P2) | Rebase omskriver SHA-er når `main` har flyttet seg, og `--no-squash` bevarer dem ikke da. | Påstanden er presisert. `progress.md` føres med SHA-er fra `main` etter landing. |
| F6 (S) | `copy-ignored` ville duplisert `handoff.md` til hvert worktree. | Ingen `post-start` i dette repoet. Andre prosjekter bruker `.worktreeinclude`. |
| F7 (S, X) | Hooken hadde svakere dekning enn CI, tok to minutter, og kan ikke speile CIs Python-miljø. | Tabell med tre samtidige kommandoer som speiler CI. Miljøforskjellen er akseptert, og CI-sjekken (steg 10) er bakstopper. |
| F8 (S) | Forlatte worktrees hoper seg opp. | `check-branch-hygiene.sh` foreslår `wt step prune`. |
| F9 (S, X) | Sol som Codex-linse er ikke målt for kodegjennomgang, og gstack angir `model_reasoning_effort` selv i mange kall. | Byttet er valgfritt og uavhengig av flyten. Utvei: `GSTACK_CODEX_MODEL=gpt-6-astra` for høyrisiko. Evaluer etter de første gjennomgangene. |
| F10 (S, X) | En rød `main` stoppes av ingenting, og «siste kjøring» kan være en annen SHA. | Steg 10 knytter CI til den pushede SHA-en. |
| F11 (X) | Ingen samtidighetslås: to landinger kan overskrive hverandre. | Lås per repo (steg 1, kode 12). |
| F12 (X) | «Samme dekning som CI» gjelder bare dette repoet; andre adapterte prosjekter har ingen hook. | Kode 9. Blokken ber agenten foreslå en `.config/wt.toml`. |
| F13 (X) | Plan committet bare på en annen gren finnes ikke i worktreet fra `main`. | Se `autoimplement`: nytt worktree bare fra `main`, ellers dagens oppførsel. |
| F14 (X) | Handoff ligger i worktreet og sesjonsloggen i worktreets git-mappe. Begge forsvinner når worktreet fjernes. | Regel nå: handoff skrives til primærmappen. Kodeendring utsatt, utløser: første gang en handoff går tapt (`session-resume.sh` og `capture-session-tail.sh` må da slå opp `git-common-dir`). |
| F15 (X) | To register manglet (`MARKER_BLOCKS`, `UNIVERSAL`). | Komponent 3. |
| F16 (X) | Å øke `WORKTREE_SCAN_MAX` gjør sesjonsstart tregere, og menyen tilbyr fortsatt `/ship`. | Komponent 5: grensen beholdes, `/ship` skjules i modus `solo`. |
| F17 (X) | Enklere design: `wt merge` + `git push` har færre tilstander. | Skriptet er beholdt, men strippet til lås, sjekk, merge, push, stopp. Automatisk reset og nytt forsøk er fjernet. |

## Utenfor omfanget

- Parallelle agenter via `wt` i `autoimplement`.
- `PreToolUse`-hook som håndhever `wt` (alternativ B).
- Beskyttelse av `main` på GitHub (solo-flyten skal pushe direkte).
- Kodeendring for handoff i worktrees (F14), til utløseren inntreffer.

## Utgivelse og testing

- Bump `.claude-plugin/plugin.json` til 3.4.0 og legg til `## [3.4.0]` i CHANGELOG.
- Oppdater README (skill- og blokkoversikt) og rutingseksjonen der det trengs.
- Legg `gstack-git-hygiene-v11` i `DENYLIST` i `scripts/lint-skills.py`.
- `python3 scripts/lint-skills.py` og `python3 -m pytest -q` grønne, **også på brukerens maskin** (F1).
- Pytest for blokkemisjonen: E8-roster (`BLOCKS`, `MARKER_BLOCKS`, `UNIVERSAL`), sentinel og v11→v12.
- Pytest for `land-worktree.py` med kaster-repoer for hver kode 2–12: skitten primær (samme og annen fil), `origin/main` foran, rød hook, manglende hook, avvist push, samtidig lås, rebase-konflikt.
- Fase 0 i planen: kjør `EnterWorktree` med `path` mot et `wt`-worktree og bekreft at hooken godkjenner det.
- E2E-testen for `adapt` kjøres manuelt etter endringene i skript og blokker.
- Manuell dry-run av `autoimplement` på en liten plan, både fra `main` og fra en feature-gren.
- Ship-worthy og berører kontrakt ⇒ pitfall-verification med Codex-pass via `/review` og tredje linse.

## Åpne punkter

- Skal de to `_when_present`-testene gjøres maskinuavhengige, eller utelates fra hooken? Avgjøres i planen.
- De tre uavklarte filene på `main` (`CLAUDE.md`, `AGENTS.md`, `JEV-FORSLAG.md`) må avklares av brukeren før landing, siden `CLAUDE.md` overlapper. De skal ikke inn i denne branchen.
