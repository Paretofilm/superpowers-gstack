# Worktrunk-integrasjon — design

**Dato:** 2026-09-29 · **Status:** utkast til brukergjennomgang · **Målversjon:** 3.4.0
**Bakgrunn:** `docs/superpowers/.handoff-last.md` (utredning av `max-sixty/worktrunk`, `wt` v0.79.0)

## Formål

Brukeren er én solo vibe-coder. Målet er at worktrees brukes **automatisk** og at
**pull requests unngås** for prosjekter uten review. Pluginen skal lære alle prosjekter
den adapterer denne arbeidsmåten, ikke bare dette repoet.

**Suksess:** Brukeren skriver aldri `git worktree` eller `gh pr create` selv, og alt arbeid
havner på `main` med lint og tester grønne.

## Avgjørelser fra brainstormingen

| Tema | Valg |
|---|---|
| Sikkerhetsnett i stedet for PR | Lokal sperre: `pre-merge`-hook kjører lint og pytest. CI kjører etterpå som varsel. |
| Stash | Forbudt (delt mellom worktrees). Ulagret arbeid flyttes til `wip/<tema>`-branch. |
| Squash | `wt merge --no-squash`, fordi planer og `autoimplement` refererer til SHA per fase. |
| Hvor reglene bor | Egen delt blokk i `CLAUDE.md` (tilnærming A). Ingen `PreToolUse`-hook nå. |
| Parallelle agenter | Utenfor omfanget. `autoimplement` kjører faser sekvensielt. |
| Personlig konfig | Endres bare etter at brukeren har sett diffen og sagt ja. |
| Codex-modell | GPT-6 Astra ($10/$50 per million tokens) byttes ut med GPT-6 Sol ($2/$10), nest best per 2026-09-29. Verifisert med testkall. |
| Godkjenning av hooks | Brukeren kjører `wt config approvals add` én gang. Agenter bruker aldri `--yes`. |

## Komponenter

| # | Komponent | Endring |
|---|---|---|
| 1 | `skills/adapt/blocks/worktrunk.md` (ny) | Regler for worktree-start, solo-landing og fallback uten `wt`. Linjen `Landing mode: solo`. |
| 2 | `skills/adapt/blocks/git-hygiene.md` v11→v12 | Peker til worktrunk-blokken for solo-landing. Stash-forbud og `wip/`-regel urørt. |
| 3 | `scripts/adapt-claude-md.py` | Ny `Block(...)` i `BLOCKS` med sentinel, slik at E8-linten godtar blokken. |
| 4 | `skills/autoimplement/SKILL.md` | Check 1: på `main` med ren arbeidskopi opprettes worktree `autoimpl/<plan-slug>`. Sluttlanding etter blokkens flyt. |
| 5 | `scripts/check-branch-hygiene.sh` | Foreslår `wt merge` / `wt remove` når `wt` finnes. `WORKTREE_SCAN_MAX` økes fra 12. |
| 6 | `.config/wt.toml` (ny, dette repoet) | `pre-merge`: `lint-skills.py` og `pytest -q`. `post-start`: `wt step copy-ignored`. |
| 7 | Personlig konfig (etter samtykke) | `GSTACK_CODEX_MODEL=gpt-6-sol` i `~/.zshenv`, `model = "gpt-6-sol"` i `~/.codex/config.toml`, `[commit.generation]` med Claude. |

## Solo-landing (worktrunk-blokken)

Én flyt for interaktive økter og `autoimplement`:

1. **Start:** `wt switch --create <type>/<tema> --no-cd --format=json` gir stien. Alt arbeid
   går der via `git -C <sti>`, fordi Bash-verktøyet nullstiller arbeidsmappen.
2. **Underveis:** commit ved milepæler og `git push -u origin <branch>` som backup.
3. **Før landing:** `git fetch` og `git merge --ff-only origin/main` på `main`, siden `wt merge`
   aldri henter. Ship-worthy endringer går først gjennom `/review` og `pitfall-verification`.
4. **Landing:** `wt merge --no-squash` (kjører `pre-merge`, rebaser, fast-forwarder lokal
   `main`, fjerner worktree og branch). Deretter `git push` fra `main`, og
   `git push origin --delete <branch>` hvis grenen ble pushet.
5. **Landingsmodus:** `Landing mode: solo` (standard som `/adapt` skriver) eller `pr`.
   Ved `pr` gjelder `/ship`. `/adapt` gjetter aldri modus.

## `autoimplement`

- Check 1 endres: `main` med ren arbeidskopi gir nytt worktree i stedet for avvisning.
  Dirty tree avvises som før.
- **Ny avvisning:** planen må være committet, ellers finnes den ikke i worktreet.
- Subagentene får worktree-stien i prompten, uten `isolation: "worktree"`.
- Etter siste fase og grønn sluttreview lander den etter flyten over hvis modusen er `solo`.
  Ved `pr` stopper den og nevner `/ship`.
- Eksisterende avvisninger (migrasjoner, hemmeligheter, credentials, `.env`, `.ssh`) beholdes.

## Feilhåndtering

| Situasjon | Handling |
|---|---|
| `pre-merge` rød | `wt merge` avbrytes, worktreet blir stående, fiks og prøv igjen. |
| Push avvist (`main` har flyttet seg) | `git pull --ff-only`, deretter `wt merge` på nytt. |
| `wt` mangler | Fall tilbake til `git worktree add` og `/superpowers:finishing-a-development-branch`. |
| Hooks ikke godkjent | Stopp og be brukeren kjøre `wt config approvals add`. Aldri `--yes`. |
| Plan ikke committet (`autoimplement`) | Avvis med melding om å committe planen først. |

## Utenfor omfanget

- Parallelle agenter via `wt` i `autoimplement`.
- `PreToolUse`-hook som håndhever `wt` (alternativ B). Kandidat senere hvis reglene glemmes.
- Andre endringer i pluginen.

## Utgivelse og testing

- Bump `.claude-plugin/plugin.json` til 3.4.0 og legg til `## [3.4.0]` i CHANGELOG.
- Oppdater README (skill- og blokkoversikt) og nevn den nye blokken i rutingseksjonen der det trengs.
- Legg `gstack-git-hygiene-v11` i `DENYLIST` i `scripts/lint-skills.py`.
- `python3 scripts/lint-skills.py` og `python3 -m pytest -q` grønne.
- Pytest for blokkemisjonen: E8-roster, sentinel og v11→v12.
- E2E-testen for `adapt` kjøres manuelt etter endringene i skript og blokker.
- Manuell dry-run av `autoimplement` på en liten plan.
- Ship-worthy og berører kontrakt ⇒ pitfall-verification med Codex-pass via `/review`.

## Åpne punkter

Ingen. Uavklarte filer på `main` (`CLAUDE.md`, `AGENTS.md`, `JEV-FORSLAG.md`) er utenfor omfanget og
skal ikke inn i denne branchen.
