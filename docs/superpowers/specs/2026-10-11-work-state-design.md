# Arbeidstilstand og installerbar app — design

**Dato:** 2026-10-11 · **Status:** utkast, venter på brukergjennomgang · **Målversjon:** 3.11.0

## Formål

Brukeren spør stadig «er alt committet, mapper ryddet og appen installerbar?» etter en
oppgave. Svaret skal komme av seg selv, som én linje målt av et skript, ikke som en
vurdering agenten setter sammen fra hukommelsen.

For Mac-apper betyr «installerbar» mer enn at koden ligger på `main`. Når brukeren
klikker på appen i Docken, skal den nyeste `main` starte, ikke en eldre kopi i
`/Applications`. I dag bygger `verify-and-land` grenen og åpner den, men kopien i
`/Applications` blir stående gammel.

**Suksess:**
- Etter hver landing og før siste melding i en oppgave som har endret filer, står
  det én tilstandslinje, for eksempel
  `Tilstand: committet ✓ · pushet ✓ · mapper ryddet ✓ · installerbar ✓ (3.10.1 på main, du har 3.10.0)`.
- Agenten rydder bare det den kan bevise at er trygt. Alt annet nevnes i linjen, og
  agenten spør én gang.
- I et Mac-app-prosjekt ligger et Release-bygg av `main` i `/Applications` etter
  landingen, uten at brukeren har skrevet en kommando.
- Brukeren trenger aldri å huske kommandoene.

## Avgjørelser

| Tema | Valg |
|---|---|
| Tilnærming | Ett skript, `scripts/work-state.py`, med to underkommandoer: `report` endrer ingenting, `install` bygger og installerer. Skillene og regelen i git-hygiene-blokken kaller det. Ingen krok (`Stop`) i første versjon. |
| Hva «installerbar» betyr | Prosjektet bestemmer én gang, med en linje `Installable:` i `CLAUDE.md` (del 1). Mangler linjen, gjetter ikke skriptet. |
| Mac-app | Release-bygg av `main`, med prosjektets eget skjema og egen signering, installert i `/Applications`. |
| Andre plattformer (iOS m.fl.) | Prosjektet skriver sin egen sjekk: `Installable: command <kommando>`. |
| Hvem installerer | Agenten, uten å spørre, unntatt i fire tilfeller (del 3). |
| Rydding | `report` endrer ingenting. Den skriver de nøyaktige kommandoene for det som er bevist trygt (`safe_actions`), og agenten kjører dem. Det samme mønsteret bruker `land` med `remaining`. |
| Aldri uten å spørre | Versjonsøkning, publisering, tvangspush, `git branch -D`, sletting av noe som ikke er bevist landet eller bevist hurtigbuffer, og å avslutte en app med tvang. |

## Komponenter

| # | Komponent | Endring |
|---|---|---|
| 1 | `scripts/work-state.py` (ny) | `report` og `install`, som beskrevet i del 2 og 3. Bare standardbiblioteket. Trenger Python 3.11 eller nyere, som `land-worktree.py`. |
| 2 | `skills/work-state/SKILL.md` (ny) | Finner skriptet ut fra skillens egen mappe og tolker kodene. En delt blokk i `CLAUDE.md` kan ikke peke på en sti i pluginen, så blokken og skillene peker på denne skillen. Ruting: «er alt committet», «er det ryddet», «installer appen», «tilstand». |
| 3 | `skills/land/SKILL.md` | Etter kode 0 og ryddingen i `remaining`: kjør `/superpowers-gstack:work-state` og avslutt med linjen (del 4). |
| 4 | `skills/verify-and-land/SKILL.md` | Fase 6: valget nevner installeringen i `/Applications`. Fase 7: bunten fra fase 5 sendes videre som `--quit-path`. Når landingen går til `/ship` (`pr`), kjøres `work-state` etterpå. Ved `solo` gjør `land` det allerede. |
| 5 | `skills/adapt/blocks/git-hygiene.md` v13 → v14 | Ny regel: før siste melding i en oppgave som har endret filer, kjør `work-state`, rydd det som er trygt, og avslutt med linjen. |
| 6 | `scripts/lint-skills.py` | Utvid mønsteret mot gamle markører til å fange `v13`. Ny skill i rutingdekningen. |
| 7 | `scripts/adapt-claude-md.py` + `skills/adapt/SKILL.md` | `--installable`, skrevet én gang under en overskrift prosjektet eier, slik som `Local state:`. Spørsmålet i steg 4. |
| 8 | `CLAUDE.md` (rutingseksjonen), `README.md`, `CHANGELOG.md`, `plugin.json`, `scripts/sync-own-claude-md.py` | Ny skill, versjon 3.11.0. Repoets egen `CLAUDE.md` får blokken v14 gjennom synkroniseringsskriptet, og sin egen linje `Installable: plugin`. `report` leser linjen fra `origin/main`, så den virker først når landingen er pushet. |
| 9 | `tests/unit/test_work_state.py` (ny) | Se «Testing». |

## Del 1 — linjen `Installable:`

Én linje i prosjektets `CLAUDE.md`, under en overskrift prosjektet eier, utenfor
pluginens seksjoner og utenfor kodeblokker. Linjen leses på samme måte som
`Landing mode:`.

| Linje | Installerbar ✓ når |
|---|---|
| `Installable: macos-app <Scheme>` | Stempelet fra siste `install` viser nøyaktig `origin/main`, appen finnes på stien i stempelet, og bundle-ID-en stemmer. |
| `Installable: plugin` | `claude plugin validate` godtar treet til `origin/main` (pakket ut i en midlertidig mappe), versjonen i `plugin.json` har en `## [X.Y.Z]`-oppføring i `CHANGELOG.md`, og lokal `main` er pushet. Linjen viser også hvilken versjon som er installert (`~/.claude/plugins/installed_plugins.json`, oppføringen `<navn>@…`). |
| `Installable: command <kommando>` | Kommandoen gir kode 0. Den kjøres med `sh -c` i hovedmappen, med 120 sekunders tidsgrense. Den skal bare lese. Det er prosjektets eget ansvar, akkurat som krokene i `.config/wt.toml`. |
| `Installable: none` | Ikke aktuelt. Linjen viser `installerbar –`. |

- **Skjemanavnet står i linjen.** Et Xcode-prosjekt kan ha flere apper, og agenten skal
  aldri gjette hvilken som hører hjemme i Docken.
- **`/adapt` spør én gang** og foreslår et svar:
  - finnes `.claude-plugin/plugin.json`: `plugin`
  - er sporet `macos` eller `both`, og finnes det et skjema med `SUPPORTED_PLATFORMS` som inneholder `macosx`: `macos-app <Scheme>`
  - ellers `command` eller `none`.
  
  Svaret skrives med `--installable` under `## <prosjekt> install`. Linjen endres aldri
  av `/adapt` etterpå.
- **Mangler linjen, eller er den ugyldig,** viser linjen
  `installerbar: ikke definert, kjør /adapt`. Agenten spør ikke om det midt i en annen
  oppgave.
- **Leses linjen fra `origin/main` eller fra arbeidsmappen?** `report` leser den fra
  `origin/main` (`git show origin/main:CLAUDE.md`, med symlenke fulgt som i `land`).
  En gren skal ikke kunne endre hva som installeres. Uten fjern-repo leses den fra
  lokal `main`, og linjen viser `pushet – (ingen fjern-repo)` i stedet for å late som om
  arbeidet er sikkerhetskopiert.

## Del 2 — `report`

```
work-state.py report [--repo <sti>] [--json-only]
```

Skriptet endrer ingenting. Det eneste unntaket er `git fetch --quiet origin` med 15
sekunders tidsgrense, fordi en påstand om origin krever ferske data. Feiler henting,
står `pushet ?` og årsaken. Utdata er én linje på stdout og et JSON-svar på siste linje:

```json
{"line": "Tilstand: …", "committed": {…}, "pushed": {…}, "tidy": {…},
 "installable": {"kind": "macos-app", "status": "stale", "detail": "…"},
 "safe_actions": [["git", "-C", "…", "branch", "-d", "…"]], "ask": ["…"]}
```

Hver av de fire delene har `status`: `ok`, `open`, `unknown` eller `undefined`, i
tillegg til `detail` og `items`. Kode 0 betyr at alt er ✓ eller –, kode 1 at noe står
åpent, kode 2 at mappen ikke er et git-repo, og kode 64 feil bruk.

| Del | Måles slik | I `safe_actions` (agenten gjør) | I `ask` (agenten spør én gang) |
|---|---|---|---|
| **committet** | `git status --porcelain` i mappen økten står i og i hovedmappen (første oppføring i `git worktree list`) | Ingenting. Skriptet vet ikke hvem som endret hva. Agenten committer bare filer den selv har endret i oppgaven. | Filer agenten ikke selv har endret |
| **pushet** | `@{upstream}..HEAD` på gjeldende gren (uten upstream: commits som ingen fjern-ref har), og `origin/main..main` i hovedmappen | `git push` av en gren med upstream når origin ikke har flyttet seg | Hver push som ville krevd tvang, og `main` med commits som ikke er landet gjennom `land` |
| **mapper ryddet** | Arbeidsmapper utenom hovedmappen. Lokale grener. Mapper `<foreldremappe>/<repo>.*` som ikke er arbeidsmapper. | En arbeidsmappe er ren og grenen er forfeder til `origin/main`: `wt -C <hovedmappe> remove <gren>` (uten `wt`: `git worktree remove`, så `git branch -d`). En gren som er forfeder til `origin/main` og ikke sjekket ut: `git branch -d`. En rest som bare inneholder hurtigbuffer: flytt til papirkurven. | Grener som ikke er bevist landet, også dem som ble squash-flettet via en pull request. Rester med annet innhold. Arbeidsmappen økten står i. |
| **installerbar** | Del 1 | Ved `macos-app` og status `stale`: `install` (del 3) | Det `install` stopper på |

- **«Bare hurtigbuffer»** betyr at hver fil i mappen ligger under en av `.gstack/`,
  `node_modules/`, `.build/`, `DerivedData/`, `__pycache__/` eller `.pytest_cache/`.
  Listen er én konstant i skriptet.
- **«Bevist landet»** betyr at begge vilkårene holder:
  - `git merge-base --is-ancestor <gren> origin/main`
  - grenens reflog har minst én oppføring etter opprettelsen, altså en commit. En tom eller utløpt reflog beviser ingenting.

  En gren som nettopp er laget fra `main`, er også forfar til `origin/main`, og uten det
  andre vilkåret ville en annen økts ferske arbeidsmappe sett landet ut. En
  squash-fletting er ikke bevist, og grenen nevnes da i `ask`. Skriptet foreslår aldri
  `-D`. `git branch -d` kjøres fra hovedmappen etter `pull --ff-only`, så git selv også
  ser grenen som flettet.
- **«Ren»** betyr at `git status --porcelain --ignored` er tom, eller at de eneste
  ignorerte filene er hurtigbuffer. `wt remove` og `git worktree remove` sletter
  ignorerte filer uten å spørre, og slike filer kan være data noen la der.
- **I bruk:** En arbeidsmappe eller rest der en prosess har arbeidsmappe
  (`lsof -d cwd -Fn`, sammenlignet med stiprefiks), står aldri i `safe_actions`. Det kan
  være en annen økt som står der. Den nevnes som `i bruk`.
- **Arbeidsmappen økten står i** ryddes aldri av `report`. Etter `land` er den allerede
  borte.
- **Linjen sier aldri ✓ når noe står igjen.** Den skriver hva som står igjen, for
  eksempel `mapper ryddet ✗ (1 gren ikke landet: feat/x)`.

## Del 3 — `install` for `macos-app`

```
work-state.py install [--repo <sti>] [--quit-running | --quit-path <app>] [--accept-migration] [--replace-unstamped]
```

- **Én installering om gangen per repo.** En kjernelås på `gstack-install.lock` i
  git-mappen, som i `land`.
- **Rester etter avbrutte kjøringer.** Blir en kjøring avbrutt, kan den midlertidige
  kopien `/Applications/.<navn>.gstack-new-<pid>` bli liggende. Den som holder låsen er
  den eneste installeringen som kjører. Derfor er alle slike kopier for samme bundle-ID
  rester, og de fjernes uten at PID-en sjekkes. En PID kan bli brukt på nytt.
- **Resultatet lagres.** Hver kjøring skriver koden, årsaken og commiten atomisk til
  `gstack-install-result.json` i git-mappen. Står det en stoppkode der, viser `report`
  den under `ask` til en ny kjøring lykkes. En stopp i bakgrunnen går derfor aldri tapt,
  selv når økten er ferdig.

1. **Hovedmappen holder `main`, og den er ren.** Det sjekkes med `git status --porcelain --untracked-files=no`. Ignorerte lokale filer er i orden, de hører til `Local state`. Deretter kjøres `git pull --ff-only` mens skriptet holder `land`s lås (`gstack-land.lock`). Låsen holdes bare under hentingen, ikke under bygget. Står hovedmappen på en annen gren, er den skitten, eller feiler hentingen, bygges ingenting (kode 3). Commiten som bygges, noteres.
2. **Beholder, skjema og innstillinger** finnes slik `verify-and-land` fase 2 gjør:
   - `xcodegen generate` når `project.yml` er nyere
   - arbeidsområde før prosjekt
   - skjemaet fra linjen
   - `-configuration Release -destination 'platform=macOS'`
   - `BUILT_PRODUCTS_DIR`, `FULL_PRODUCT_NAME`, `PRODUCT_BUNDLE_IDENTIFIER` og `EXECUTABLE_NAME` lest gjennom den samme destinasjonen. Mangler én av dem, stopper skriptet.
3. **Spør i fire tilfeller.** Skriptet stopper med en kode, og skillen spør brukeren én gang. Ved ja kjøres skriptet igjen med flagget:
   - **Appen kjører,** kode 4. Prosessene finnes med `ps -Axo pid=,comm=`. På macOS er `comm` den fulle stien til programfilen, og den sammenlignes som tekst med `…/Contents/MacOS/<EXECUTABLE_NAME>`, ikke som regulært uttrykk. Med `--quit-running` bes appen avslutte seg selv (`tell application id "<bundle-id>" to quit`), og skriptet venter i inntil 20 sekunder. Kjører den fortsatt, stopper skriptet. Det bruker aldri `kill`, og appen startes ikke på nytt etterpå.
     `--quit-path <app>` er for `verify-and-land`, der brukeren nettopp har sett gren-bygget og sagt ja. Det gjør det samme, men bare når hver kjørende instans har sin programfil inne i akkurat den bunten. Kjører også en annen kopi, for eksempel den i `/Applications`, er koden fortsatt 4.
   - **Landingen kan endre data på disk,** kode 5. `classify-change.py --diff --diff-base <stempel-commit>` mot `origin/main` gir signalet `migration`. Uten stempel kan dette ikke måles, og da gjelder neste punkt. Finnes ikke stempelets commit lenger i historikken, for eksempel etter en omskriving, regnes spennet som ukjent og gir også kode 5. Flagg: `--accept-migration`.
   - **Første installering over en kopi uten stempel,** kode 6. Det finnes en app med samme navn i `/Applications`, men ikke noe stempel. Da er forrige versjon ukjent. Flagg: `--replace-unstamped`.
   - **Kopien i `/Applications` er en annen app** (annen bundle-ID), kode 7. Det finnes ikke noe flagg for dette. Brukeren rydder selv.
4. **Bygger** med `-derivedDataPath <git-mappe>/gstack-install-build`, så neste bygg tar med bare det som er endret. Ingen overstyring av signering. Feiler bygget, er det kode 8, med stien til loggen.
5. **Kontrollerer før byttet.** Kopierer med `ditto` til `/Applications/.<navn>.gstack-new-<pid>`. Sjekker `codesign --verify --deep --strict` og leser bundle-ID-en med `plutil`. Feiler noe, fjernes den midlertidige kopien, den gamle står urørt, og koden er 9.
6. **Bytter i ett steg.** Finnes en gammel kopi, byttes de med `renamex_np(RENAME_SWAP)` via `ctypes`. Den gamle, som nå har det midlertidige navnet, legges i papirkurven gjennom Finder, så «Legg tilbake» virker. Uten Finder flyttes den til `~/.Trash` med tidsstempel. Finnes ingen gammel kopi, holder `os.rename`. Er `/Applications` ikke skrivbar, er det kode 10. Skriptet bruker aldri `sudo`.
   Før byttet sjekkes det at hovedmappens `HEAD` fortsatt er commiten som ble bygget. Har en landing i en annen arbeidsmappe flyttet `main` under bygget, kan bygget blande to versjoner. Da byttes ingenting, ingenting stemples, og koden er 11. En ny kjøring bygger det som er endret.
7. **Registrerer og stempler.** `lsregister -f <app>` kjøres (`/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister`), og signaturen kontrolleres én gang til på den endelige stien. Deretter skrives `gstack-installed-app.json` atomisk i git-mappen, med `scheme`, `bundle_id`, `commit`, `app_path`, `version` og `installed_at`.

| Kode | Betyr |
|---|---|
| 0 | Installert, eller allerede gjeldende (`"status": "current"`) |
| 2 | Linjen er ikke `macos-app`, eller den mangler |
| 3 | Hovedmappen er ikke på `main`, er skitten, eller `pull --ff-only` feilet |
| 4 / 5 / 6 | Spør: appen kjører, migreringssignal, kopi uten stempel |
| 7 | En annen app har samme navn |
| 8 | Bygget feilet (stien til loggen skrives ut) |
| 9 | Kontrollen feilet, og den gamle kopien er urørt |
| 10 | `/Applications` er ikke skrivbar |
| 11 | `main` flyttet seg under bygget, ingenting er byttet |
| 12 | En annen installering holder låsen, eller `land` holdt sin lås lenger enn 60 sekunder |
| 64 / 70 | Feil bruk / uventet feil, med tilstanden målt og skrevet ut |

**Feilprinsipp:** Prosjektets innstillinger endres aldri. Den gamle kopien står til den
nye er kontrollert. Docken har alltid en app som virker.

## Del 4 — når det skjer

- **`land`, kode 0:** Først ryddingen i `remaining`, så `work-state`. Viser `report`
  `macos-app` med status `stale`, starter `install` i bakgrunnen. Meldingen avsluttes
  med linjen.
  - **Når `install` er ferdig,** varsler Claude Code økten. Agenten skriver linjen på nytt.
  - **Stoppet `install` på et spørsmål** (kode 4–6), stiller agenten det bare hvis økten ikke er midt i en annen oppgave. Ellers står spørsmålet i `ask` ved neste `report`, fordi resultatet er lagret.
- **`verify-and-land`:** Valget i fase 6 sier nå «gjør dette til den gjeldende
  versjonen, og installer den i `/Applications`». Ja dekker da også at gren-bygget som
  ble åpnet i fase 5, avsluttes. Agenten sender `--quit-path <bunten fra fase 5>`
  videre til `install`, så den vanligste stien ikke stopper på kode 4. Ved `solo` kjører
  `land` `work-state`. Ved `pr` kjøres `work-state` etter `/ship`, og linjen sier at
  arbeidet venter på en pull request.
- **Git-hygiene v14:** Før siste melding i en oppgave som har endret filer, kjøres
  `/superpowers-gstack:work-state`. Agenten gjør det som står i `safe_actions` og
  spør én gang om det som står i `ask`. Meldingen avsluttes med linjen. Gjelder ikke
  rene spørsmål og samtaler uten filendringer.
- **Spørsmål stilles samlet:** én `AskUserQuestion` med det som står i `ask` og en eventuell
  stoppkode fra `install`, i én melding. Svarer brukeren ikke, står tilstanden ærlig i
  linjen.

## Testing

- **`tests/unit/test_work_state.py`** mot midlertidige git-repoer med et lokalt
  «origin», kjørt via `subprocess` som i de andre testene. Testene dekker:
  - hver del av linjen
  - hver grense i del 2: landet mot squash-flettet gren, ren mot skitten arbeidsmappe, hurtigbuffer mot annet innhold, gren uten upstream
  - `Installable:` mangler, er ugyldig, står i en kodeblokk, eller er endret bare på grenen
- **`install`** kjøres mot erstatninger på `PATH` for `xcodebuild`, `codesign`, `plutil`,
  `pgrep`, `osascript`, `lsregister` og `ditto`, og med en testmappe i stedet for
  `/Applications` (`--applications-dir`, skjult valg bare for tester). Testene dekker hver
  kode i tabellen, og at den gamle kopien er urørt ved kode 8 og 9. Ingen test rører den
  ekte maskinen.
- **Øvingsrunde i reserve-Mac-en** (`vm-run`): en liten testapp med ad hoc-signering
  bygges og installeres to ganger, først uten stempel og så med. Den andre runden skal
  bygge bare det som er endret.
- **Første ekte kjøring** skjer på én av brukerens Mac-apper, med brukeren til stede.
  Hvilken app avtales i planen.
- **`adapt`:** `--installable` skrives én gang og bevares ved neste kjøring, slik
  `Local state` testes i `test_adapt_script.py`.

## Utenfor første versjon

- Innebygd støtte for iOS. Det går gjennom `command`.
- TestFlight og notarisering.
- En `Stop`-krok som håndhever linjen.
- Å starte appen på nytt etter at den er avsluttet.
- Å hoppe over et bygg når `main` bare har endret dokumentasjon. Bygget er
  inkrementelt, så det koster lite.
