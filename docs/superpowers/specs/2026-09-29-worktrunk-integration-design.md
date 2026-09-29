# Worktrunk-integrasjon — design

**Dato:** 2026-09-29 · **Status:** revidert etter pitfall-runde 1, venter på eksterne linser og brukergjennomgang · **Målversjon:** 3.4.0
**Bakgrunn:** `docs/superpowers/.handoff-last.md` (utredning av `max-sixty/worktrunk`, `wt` v0.79.0)

## Formål

Brukeren er én solo vibe-coder. Målet er at worktrees brukes **automatisk** og at
**pull requests unngås** for prosjekter uten review. Pluginen skal lære alle prosjekter
den adapterer denne arbeidsmåten, ikke bare dette repoet.

**Suksess:** Brukeren skriver aldri `git worktree` eller `gh pr create` selv, og alt arbeid
havner på `main` med lint og tester grønne. Landing skal være **én kommando**, ikke en
sekvens agenten må huske og utføre for hånd.

## Avgjørelser

| Tema | Valg |
|---|---|
| Sikkerhetsnett i stedet for PR | Lokal sperre: `pre-merge`-hook som har **samme dekning som CI** og som er grønn på `main` før den slås på. CI kjører etterpå, og resultatet sjekkes etter push. |
| Stash | Forbudt (delt mellom worktrees). Ulagret arbeid flyttes til `wip/<tema>`-branch. |
| Squash | `wt merge --no-squash`, fordi planer og `autoimplement` refererer til SHA per fase. |
| Hvor reglene bor | Egen delt blokk i `CLAUDE.md` (tilnærming A). Ingen `PreToolUse`-hook nå. |
| Hvordan landing utføres | **Ett skript** (`scripts/land-worktree.py`) som blokken og `autoimplement` kaller. Ingen håndkjørt flertrinnssekvens. |
| `--no-hooks` | Aldri. En sperre som omgås er verre enn ingen sperre. Er hooken rød, fikses hooken eller koden. |
| Parallelle agenter | Utenfor omfanget. `autoimplement` kjører faser sekvensielt. |
| `copy-ignored` | Ikke i dette repoet (se funn F5). Prosjekter med `node_modules` eller `.env` bruker `.worktreeinclude`. |
| Personlig konfig | Endres bare etter at brukeren har sett diffen og sagt ja. |
| Codex-modell | Standard byttes fra GPT-6 Astra ($10/$50 per million tokens) til GPT-6 Sol ($2/$10). Kvalitet er ikke målt for kodegjennomgang (se F9), så byttet har en utvei og et evalueringspunkt. |
| Godkjenning av hooks | Brukeren kjører `wt config approvals add` én gang. Agenter bruker aldri `--yes`. |

## Komponenter

| # | Komponent | Endring |
|---|---|---|
| 1 | `skills/adapt/blocks/worktrunk.md` (ny) | Regler for worktree-start, solo-landing via skriptet og fallback uten `wt`. Linjen `Landing mode: solo`. |
| 2 | `skills/adapt/blocks/git-hygiene.md` v11→v12 | Peker til worktrunk-blokken for solo-landing. Stash-forbud og `wip/`-regel urørt. |
| 3 | `scripts/adapt-claude-md.py` | Ny `Block(...)` i `BLOCKS` med sentinel, slik at E8-linten godtar blokken. |
| 4 | `skills/autoimplement/SKILL.md` | Check 1: på `main` opprettes worktree `autoimpl/<plan-slug>`, og renhetssjekken gjøres **i worktreet**. Sluttlanding via skriptet. |
| 5 | `scripts/check-branch-hygiene.sh` | Foreslår `wt merge` / `wt remove` og `wt step prune` når `wt` finnes. `WORKTREE_SCAN_MAX` økes fra 12 til 30. |
| 6 | `.config/wt.toml` (ny, dette repoet) | `pre-merge` som tabell (kommandoene kjører samtidig): `lint-skills.py`, `pytest tests/unit -q` og kontrakttestene `skills/*/tests/required-sections.test.sh`. Ingen `post-start`-hook. |
| 7 | Personlig konfig (etter samtykke) | `GSTACK_CODEX_MODEL=gpt-6-sol` i `~/.zshenv`, `model = "gpt-6-sol"` i `~/.codex/config.toml`, `[commit.generation]` med Claude. |
| 8 | `scripts/land-worktree.py` (ny) | Landing i én kommando med forhåndssjekker, feilkoder og opprydding. Testes med kaster-repoer. |

## Solo-landing (`scripts/land-worktree.py`)

Blokken sier: start med `wt switch --create <type>/<tema> --no-cd --format=json`, arbeid via
`git -C <sti>`, commit ved milepæler og `git push -u origin <branch>` som backup. Landing er
**ett kall**: `python3 <plugin>/scripts/land-worktree.py --worktree <sti>`. Skriptet gjør:

1. **Modus:** avvis hvis `Landing mode` er `pr` (da gjelder `/ship`).
2. **Hooks godkjent?** Hvis ikke: avslutt med melding om `wt config approvals add`. Aldri `--yes`.
3. **Oppdater `main`:** `git fetch origin`, deretter `git -C <primær> merge --ff-only origin/main`.
   `wt merge` henter aldri selv. Feiler ff (lokal `main` har commits som ikke er pushet): avslutt og si det.
4. **Overlapp-sjekk:** kjør `git status --porcelain` i primærmappen og sammenlign med filene grenen
   endrer. Overlapper de, avslutt og nevn filene. `wt merge` nekter uansett (verifisert), men
   skriptet sier det **før** de to minuttene med tester.
5. **Landing:** `wt -C <sti> merge --no-squash --no-remove`. `pre-merge` kjører, grenen rebaseres
   og lokal `main` fast-forwardes. Worktree og gren blir stående **til pushen har gått gjennom**.
6. **Push:** `git -C <primær> push origin main`.
7. **Opprydding etter vellykket push:** `wt -C <primær> remove <gren>` og
   `git push origin --delete <gren>` hvis grenen ble pushet.
8. **CI-resultat:** hent siste kjøring på `main` med `gh run list --branch main -L1` og skriv URL og
   status. Er den rød, er neste oppgave å fikse `main`. Sjekken blokkerer ikke.

Ship-worthy endringer går gjennom `/review` og `pitfall-verification` **før** skriptet kalles,
som i dag.

## `autoimplement`

- Check 1 endres: på `main` opprettes worktree `autoimpl/<plan-slug>`, og `git status` kjøres
  med `git -C <worktree>`. Primærmappens rene eller skitne tilstand avgjør ikke, siden brukerens
  uavhengige, ikke-committede filer ellers ville stoppet alle kjøringer. Overlapp mellom
  primærmappens skitne filer og planens filer avvises, med filene nevnt.
- **Ny avvisning:** planen må være committet, ellers finnes den ikke i worktreet.
- Subagentene får worktree-stien i prompten, uten `isolation: "worktree"`.
- Etter siste fase og grønn sluttreview kaller den landingsskriptet hvis modusen er `solo`.
  Ved `pr` stopper den og nevner `/ship`.
- Eksisterende avvisninger (migrasjoner, hemmeligheter, credentials, `.env`, `.ssh`) beholdes.

## Feilhåndtering

Skriptet bruker distinkte avslutningskoder, så agenten aldri gjetter:

| Kode | Situasjon | Handling |
|---|---|---|
| 2 | Modus er `pr` | Bruk `/ship`. |
| 3 | Hooks ikke godkjent | Be brukeren kjøre `wt config approvals add`. |
| 4 | Lokal `main` kan ikke fast-forwardes til `origin/main`: enten ligger lokal `main` foran med ikke-pushede commits, eller skitne filer overlapper filer `origin/main` endrer | Skriptet skriver commitene eller filene som er årsaken. Brukeren bestemmer. |
| 5 | Skitne filer i primærmappen overlapper grenen | Filene nevnes. Brukeren committer eller flytter dem til egen gren. Aldri stash. |
| 6 | `pre-merge` rød | Worktreet står. Fiks og kall skriptet på nytt. Aldri `--no-hooks`. |
| 7 | Push avvist (`origin/main` flyttet seg under testene) | Worktree og gren står ennå. Skriptet verifiserer at commitene ligger på grenen, kjører `git -C <primær> reset --keep origin/main`, rebaserer grenen på `origin/main` og kaller seg selv på nytt én gang. Feiler også det, avslutt med koden og la brukeren se. |
| 8 | `wt` mangler | Fall tilbake til `git worktree add` og `/superpowers:finishing-a-development-branch`. |

Uten `--no-remove` ville kode 7 ha etterlatt en lokal `main` som har divergert fra `origin/main`,
og en slettet gren (verifisert).

## Verifisert under pitfall-runde 1

Alt under er målt eller kjørt, ikke antatt:

- **Hook-grunnlinje:** full `pytest` på grenen gir 2 røde av 576 (`test_roster_matches_installed_upstream_when_present`,
  `test_pin_matches_installed_gstack_when_present`), fordi installert gstack (1.91.2) ikke er pinnet versjon.
  CI passerer (gstack ikke installert). Tid: 141 sekunder.
- **CI-dekning:** `lint.yml` kjører lint, `pytest tests/unit` og kontrakttestene i `skills/*/tests/`.
- **`main` er ubeskyttet:** `gh api …/branches/main/protection` gir 404. Direkte push er teknisk mulig, og ingenting på serversiden stopper en rød `main`.
- **`wt merge` mot skitten primærmappe:** avviser når samme fil er endret (`conflicting uncommitted changes`), lykkes når det er en annen fil.
- **Push avvist etter merge:** `git pull --ff-only` feiler med `Not possible to fast-forward`.
- **`.gitignore`-filer som `copy-ignored` ville kopiert:** `docs/superpowers/handoff.md`, `.handoff-last.md`, `.superpowers/`, `.update-state.json`, `.DS_Store`, `__pycache__`, `.pytest_cache`.

## Funn og hvordan de er håndtert

| # | Funn | Håndtering |
|---|---|---|
| F1 | Sperren er rød fra første merge på brukerens maskin. Da fristes man til `--no-hooks`. | De to `_when_present`-testene gjøres uavhengige av installert gstack, eller utelates fra hooken med CI som eier. Grunnlinjen er akseptansekrav: `wt hook pre-merge` må være grønn på `main` før hooken slås på. |
| F2 | Gjenopprettingsraden «pull --ff-only, så wt merge igjen» virker ikke. | Erstattet av `--no-remove` og kode 7 over. |
| F3 | En skitten primærmappe blokkerer landing, og dette repoets `CLAUDE.md` er skitten og endres av vår egen blokk. | Forhåndssjekk (steg 4) og kode 5. De tre uavklarte filene må avklares av brukeren før denne endringen lander. |
| F4 | Check 1 i `autoimplement` ville avvist alle kjøringer fra en vanlig skitten `main`. | Renhet vurderes i worktreet. |
| F5 | `copy-ignored` ville duplisert `handoff.md` til hvert worktree, så samme oppsummering kan «konsumeres» to ganger. | Ingen `post-start` i dette repoet. Prosjekter som trenger det bruker `.worktreeinclude`. |
| F6 | Hooken hadde svakere dekning enn CI og tok to minutter i serie. | Tabell med tre samtidige kommandoer som speiler CI. Måltid: omtrent tiden til den tregeste (testene, ca. 2,4 min). |
| F7 | `wt merge` må kjøres inne i worktreet, men Bash-verktøyet nullstiller arbeidsmappen. | Skriptet bruker `wt -C <sti>` (flagget finnes). Blokken forbyr `cd` + relativ sti i samme kall. |
| F8 | Forlatte worktrees hoper seg opp. | `check-branch-hygiene.sh` foreslår `wt step prune`. |
| F9 | Sol som Codex-linse er ikke målt for kodegjennomgang. Testkallet viste bare at modellen svarer. gstack angir `model_reasoning_effort` selv i mange kall, så miljøvariabelen bytter modell, ikke innsats. | Byttet beholdes som standard, med `GSTACK_CODEX_MODEL=gpt-6-astra` som utvei for høyrisiko-endringer. Evaluer etter de første gjennomgangene: sammenlign hva Sol og Astra finner på samme diff. |
| F10 | En rød `main` etter push stoppes ikke av noe. | Steg 8: CI-status skrives ut etter hver landing. |

## Utenfor omfanget

- Parallelle agenter via `wt` i `autoimplement`.
- `PreToolUse`-hook som håndhever `wt` (alternativ B). Kandidat senere hvis reglene glemmes.
- Beskyttelse av `main` på GitHub. Anbefales ikke nå, siden solo-flyten skal pushe direkte.

## Utgivelse og testing

- Bump `.claude-plugin/plugin.json` til 3.4.0 og legg til `## [3.4.0]` i CHANGELOG.
- Oppdater README (skill- og blokkoversikt) og nevn den nye blokken i rutingseksjonen der det trengs.
- Legg `gstack-git-hygiene-v11` i `DENYLIST` i `scripts/lint-skills.py`.
- `python3 scripts/lint-skills.py` og `python3 -m pytest -q` grønne, **også på brukerens maskin** (F1).
- Pytest for blokkemisjonen: E8-roster, sentinel og v11→v12.
- Pytest for `land-worktree.py` med kaster-repoer, som dekker hver avslutningskode 3–7: skitten primær
  med samme og annen fil, avvist push, rød hook, `main` foran `origin/main`.
- E2E-testen for `adapt` kjøres manuelt etter endringene i skript og blokker.
- Manuell dry-run av `autoimplement` på en liten plan.
- Ship-worthy og berører kontrakt ⇒ pitfall-verification med Codex-pass via `/review`.

## Åpne punkter

- Skal de to `_when_present`-testene gjøres maskinuavhengige, eller utelates fra hooken? Avgjøres i planen.
- De tre uavklarte filene på `main` (`CLAUDE.md`, `AGENTS.md`, `JEV-FORSLAG.md`) må avklares av brukeren
  før landing, siden `CLAUDE.md` overlapper. De skal ikke inn i denne branchen.
