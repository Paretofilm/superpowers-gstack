# VM-executor for E2E i superpowers-gstack — design

*Skrevet 2026-09-07. Forener og erstatter `docs/vm-e2e-integrasjon.md` (plugin-siden) og
`~/Developer/virtual-mac/docs/2026-09-07-vm-e2e-funn.md` (riggens beslutningsgrunnlag), som
foreslo to ulike eiere for executor-valget. Bygger på riggen i `~/Developer/virtual-mac` og
fagfilm-encoder som referanseprosjekt.*

## Status

- **Fase 0 (riggen)** implementeres 2026-09-07 i `~/Developer/virtual-mac`: generalisering av
  `bin/vm-e2e`, prosjekt-hook, `vm-stop`, `vm-e2e-flake`, installasjon på `PATH`.
- **Fase 1–3** er ikke påbegynt. Ingen fil under `skills/` i denne plugin-en er rørt; riggen
  skal gå mot ekte arbeid noen dager før rutingen legges om, slik riggens egne dokumenter
  anbefaler.

## Kontekst

Riggen i `virtual-mac` er verifisert i drift: `bin/vm-e2e` bygger på verten, tar lease på
én av to macOS-gjester, overfører testbundle, resignerer ad hoc, kjører XCUITest i gjesten og
henter resultatet. Ekvivalens med verten er bekreftet (16 tester, 9 hopp, 0 feil begge
steder), parallell drift er validert, og syklustiden er 92 s med inkrementelt bygg.

Plugin-en er urørt. `e2e-route` ruter «committed regression / macOS» til
`/macos-e2e-scaffold` + `scripts/run-uitests.sh` på verten. Ingen skill kjenner til VM, Lume
eller lease. Det tidligere plugin-dokumentet foreslo en ruting-akse (`.gstack/e2e-executor`)
og at `adapt`/`setup-routing` skriver fila. Beslutningsdokumentet i riggen sa i tillegg at
**runneren** skal eie lease og dispatch, ikke agentminnet.

Målet er at plugin-en kan bruke riggen når et prosjekt melder seg inn, uendret ellers — og
at de andre stedene der VM-isolasjon gir verdi (flakiness-jakt, ubemannede kjøringer,
ren-maskin-verifisering, macOS computer-use) får en vei inn.

## Vurdering: hva som faktisk mangler

### A. Riggen er FagfilmEncoder-formet, ikke generell

`bin/vm-e2e` er verifisert, men fire ting i den er bundet til referanseprosjektet og vil
brekke eller lyve for et annet prosjekt:

| Sted i `vm-e2e` | Antakelse | Konsekvens for et annet prosjekt |
|---|---|---|
| linje 135–151 | `/opt/homebrew/bin/ffprobe` **må** være kjørbar i gjesten, ellers `exit 1` | Et prosjekt uten ffprobe-avhengighet feiler hardt før testen starter |
| linje 158 | fixturer ligger i `$PROJ/test-assets/generated` | Andre fixturstier speiles ikke; tester hopper stille (XCTSkip ser ut som pass) |
| linje 66 | `.xctestrun` heter `*_<PLAN>_*` — krever **Xcode-testplaner** | Scaffold-genererte prosjekter bruker `-only-testing:<Target>` uten testplan; ingen match, `exit 1` |
| linje 244–246 | resultat = grep av loggen + exit-kode; `.xcresult` blir igjen i gjesten | Ingen strukturert `{total, passed, failed, skipped}`; akseptansekriteriet «antall utførte tester» kan ikke håndheves av kalleren |

I tillegg: `vm-e2e` ligger ikke på `PATH` (kun `lume` i `~/.local/bin`), og
`.gstack/e2e-executor` leses av riggen selv (linje 18–22) — den nekter ved eksplisitt
`host`, men aksepterer fravær. Det er forenlig med plugin-semantikken «fravær = vert» så
lenge det er runneren/rutingen, ikke riggen, som velger.

**Parallellkjøring (flakiness-jakt) er ikke støttet av `vm-e2e` slik den er.** To samtidige
kall bygger begge (`build-for-testing` mot samme `-derivedDataPath`), og dokumentasjonens
regel er nettopp «parallelliser kjøringer, ikke bygg». Det trengs et `--skip-build`-flagg og
en bygg-én-gang-wrapper.

### B. Plugin-en har ett rutingshull som VM-endringen ikke må forverre

`e2e-route` sier at «committed regression / macOS» → `/macos-e2e-scaffold` + runner, og at
fallback til MCP-live skjer når scaffold-en nekter, blant annet fordi *«a UI-test target
already exists»* (refuse-condition 3). Lest bokstavelig faller et **allerede scaffoldet**
prosjekt til MCP-live ved en regresjonsforespørsel. `macos-e2e-scaffold` linje 281 avslører
intensjonen: neste handling er `./scripts/run-uitests.sh`. Den nye rutingsraden må gjøre
«kjør den eksisterende suiten» eksplisitt, uavhengig av executor.

Referanseprosjektet fagfilm-encoder har **hverken** `scripts/run-uitests.sh` **eller**
`.gstack/`. Det kjører E2E via `scripts/verify.sh e2e` (Unit + Integration + E2E-røyk, alt
på verten, med testplaner). Rutingen må derfor ha en «neste handling» også for prosjekter
uten scaffold-runner.

### C. To dokumenter, to design — de må forenes

| | `2026-09-07-vm-e2e-funn.md` (rigg, beslutning) | `vm-e2e-integrasjon.md` (plugin) |
|---|---|---|
| Hvem leser `.gstack/e2e-executor`? | **Runneren** (`scripts/run-uitests.sh`) | **`e2e-route`** |
| Agentens neste handling | `./scripts/run-uitests.sh` som i dag | `vm-e2e <proj> <scheme> <plan> [config]` |
| Prinsipp | Korrekthet i mekanismen, ikke i agentens oppførsel | Løs kobling, opt-in per prosjekt |

Begge har rett på hvert sitt nivå. Løsningen er lagdelt (se Design), slik at agenten aldri
er den eneste som håndhever invarianten.

### D. Ingen presedens å gjenbruke — men to integrasjonspunkter som er gratis

gstack-basen (`~/.claude/skills/gstack`, 1.79.0.0) har **ingen** skill som kjører tester N
ganger, ingen sandbox/VM/container-begrep, og ingen parallell testkjøring for brukerens
prosjekter. superpowers-gstack nevner verken vm, lume eller lease noe sted; `e2e-route:57`
påbyr tvert imot sekvensiell kjøring for multiplatform. Flakiness-skillen i fase 2 er altså
genuint ny, ikke en variant av noe eksisterende.

To ting faller derimot på plass uten endring:

- **`/ship` steg 4–5** persisterer prosjektets testkommando i `## Testing` i CLAUDE.md og
  kjører den i to samtidige baner pakket i `bin/gstack-evidence run --label …`. Står
  `./scripts/run-uitests.sh` der, går ship-ens E2E-bane til VM-en via lag 2 — null endring i
  ship. Flake-wrapperen bør skrive samme evidence-format så `/ship` steg 16 kan sitere den.
- **`autoimplement`** kjører ingen tester selv (verifiserer kun ren tre + flyttet HEAD, linje
  330, og kjeder `/review` + `/pitfall-verification`, linje 345). Testene ligger i planens
  egne per-fase-kommandoer, kjørt av fase-subagenten. En plan som kaller runneren får derfor
  VM-dispatch gratis. «Asynkron E2E» er dermed en plan-konvensjon, ikke en autoimplement-
  endring (se fase 3).

`.gstack/` i gstack-basen har to kategorier: gitignorert artefakt-state (`qa-reports/`,
`browse.json`; `cso` flagger det som funn hvis `.gstack/` *ikke* er ignorert) og committede
konfigurasjonspinner (`version-path`, `package-json-path`, `track`). `e2e-executor` er en
pinne. Derfor trengs `!.gstack/e2e-executor`-negasjonen. Pinnene valideres strengt fordi de
er repo-kontrollert innhold (`gstack-version-bump:86-115` avviser stier som rømmer repoet);
vår markør er en enum (`host|vm`), alt annet avvises med `BLOCKED — invalid
.gstack/e2e-executor`, samme formulering som `.gstack/track`-sjekken.

### E. Verten har endret status siden dokumentet ble skrevet

`automationmodetool` på verten svarer nå «DOES NOT REQUIRE user authentication» — altså er
ubemannet E2E på verten *mulig* igjen. Det svekker ikke VM-argumentet (isolasjon, parallellitet,
ren tilstand), men rutingsteksten skal ikke påstå at verten alltid feiler om natten. Ingen VM
kjørte ved måling; ~12 GB fritt minne.

## Andre bruksområder for VM-ene (utover E2E-ruting)

Rangert etter verdi delt på kostnad. De to første er små tillegg til samme mekanisme; de
neste er egne skills eller senere faser.

1. **Flakiness-jakt** (`/e2e-flake <N>`): bygg én gang, kjør samme plan N ganger fordelt på
   to gjester, rapporter pass-rate per test. Dokumentert som «den klart viktigste bruken».
   Krever `vm-e2e --skip-build` (rigg) og en wrapper som kjører med konkurrens 2.
2. **Ubemannede/planlagte kjøringer**: `/loop`, `schedule`, natt-kjøringer og subagenter
   uten skjerm. VM-en er alltid ulåst med automasjonsmodus på; verten avhenger av
   brukerens sesjon. Ruting: ikke-interaktiv sesjon + executor `vm` → VM er obligatorisk,
   ikke valgfri.
3. **Asynkron verifisering i `autoimplement`**: E2E for fase N kjører i VM i bakgrunnen
   (`run_in_background`) mens agenten fortsetter med fase N+1 på verten. Verten forblir fri
   til bygging. Krever bare at fase-verifiseringen kaller runneren med `&`-semantikk og
   samler resultatet ved neste fasegrense.
4. **Ren-maskin-verifisering** (`/fresh-machine-check`): kjør Unit/Integration i en gjest
   som *ikke* får Homebrew delt inn. Avdekker skjulte vertsavhengigheter (absolutte stier
   via `#filePath`, `/opt/homebrew`-verktøy, miljøvariabler) — nøyaktig feilklassen riggen
   selv fant. Passer før `/ship`.
5. **Gatekeeper/første-start-test av Release-bygget**: kjør det ferdige `.app` i en gjest
   som aldri har sett utviklersertifikatet. Tester notarisering, første-start-dialoger og
   krasj uten Xcode. Komplementerer `/ship` og `/verify-and-land` (som med vilje kjører på
   verten fordi brukeren skal se appen).
6. **macOS computer-use uten å kapre brukerens skjerm**: `IDEAS.md` planlegger macOS-driveren
   (Fase 4) via cliclick på *fysisk* skjerm og kaller den «den skjøreste fasen» (fokus-kapring,
   zoom-mapping). I en gjest med `screencapture` + VNC forsvinner hele den feilklassen:
   agenten klikker i VM-ens skjerm, ikke i din. Bør nevnes i den åpne beslutningen om
   `live-swiftui` vs cliclick.
7. **Flere macOS-versjoner**: copy-on-write gjør en `golden-26.3`-klon nesten gratis.
   Deployment-target-testing uten en ekstra maskin.
8. **iOS-simulator i gjest** (senere): mulig i prinsippet — simulatoren er en prosess,
   ikke en VM — men krever iOS-runtime (16–19 GB) i golden. Ikke nå; `e2e-route`-aksen
   holdes macOS-only til noen ber om det.

Ikke aktuelt: web-`/qa` (headless Chromium trenger ingen VM), `/verify-and-land`
(brukeren skal se appen på verten), agent-i-VM (opprinnelig motivasjon for golden-imaget,
men krever Claude Code + auth i gjesten — eget prosjekt).

## Design: tre lag, én fil

```
.gstack/e2e-executor  (host | vm; fravær = host; committes som .gstack/track)
        │
        ├─ lag 3  e2e-route            leser fila kun for å NAVNGI executor i beslutningsblokken
        │                              og velge inngangspunkt (runner / vm-e2e / MCP-live)
        ├─ lag 2  scripts/run-uitests.sh   leser fila og DISPATCHER: vm-e2e hvis vm og rigg finnes,
        │         (scaffold-mal v2)        ellers xcodebuild på verten — samme JSON-kontrakt begge veier
        └─ lag 1  vm-e2e + vm-lease    eier lease, boot, overføring, resignering, kjøring (finnes)
```

Prinsipp: **lag 1 håndhever invarianten, lag 2 velger, lag 3 forklarer.** Agenten kan ta
feil i lag 3 uten at to kjøringer lander på samme macOS-instans. Det er beslutningen fra
riggens funn-dokument («plugin og runner — ikke minne») og plugin-dokumentets løse kobling
forent.

### Kontrakten mellom lag 2 og lag 1

`vm-e2e` får en bakoverkompatibel CLI. Posisjonsargumentene beholdes; nye flagg:

```
vm-e2e <proj> <scheme> [<plan> [<config>]]
       [--only-testing <Target>]   # scaffold-prosjekter uten testplan
       [--skip-build]              # flakiness-jakt: bygg én gang utenfor
       [--json <fil>]              # skriv {total,passed,failed,skipped,executed,xcresult} på verten
       [--result-bundle <sti>]     # hent .xcresult tilbake til verten (rsync fra gjest)
```

Prosjektspesifikke gjesteforberedelser flyttes ut av `vm-e2e` og inn i en valgfri
prosjekt-hook: `scripts/vm-guest-prepare.sh` kjøres hvis den finnes (ffprobe-symlink,
fixtur-speiling, hva som helst). `vm-e2e` beholder kun det generelle: lease, boot,
overføring, resignering, kjøring, opprydding.

`vm-e2e` legges på `PATH` via symlink `~/.local/bin/vm-e2e` (samme mappe som `lume`). Plugin-en
resolver med `command -v vm-e2e`; ingen hardkodet `~/Developer/virtual-mac`.

### Resultatkontrakt (felles for vert og VM)

Samme JSON som scaffold-runneren allerede lager, utvidet med `skipped` og `executed`:

```json
{"total": 16, "passed": 7, "failed": 0, "skipped": 9, "executed": 7,
 "executor": "vm", "xcresult": "/path/on/host.xcresult", "results": []}
```

`skipped` skrives **alltid** ut i klartekst i runnerens sammendrag, fordi «grønn og tom» var
riggens farligste feil. Ingen baseline-sammenligning i første omgang (YAGNI) — men
flakiness-wrapperen (fase 2) sammenligner `executed` mellom kjøringene og flagger avvik.

### Fallback når `vm` er satt men riggen mangler

`command -v vm-e2e` feiler (annen Mac, CI, rigg ikke installert) → kjør på verten **med en
tydelig linje** i både runner-output og beslutningsblokk: «executor=vm requested, rig not
found on this host — running on host without lease». Aldri stille. Ikke nekt: det ville
gjøre en committet `vm`-markør til en blokkering på hver maskin uten Lume, i strid med
«plugin-en fungerer uendret på maskiner uten Lume».

Unntak: ikke-interaktiv sesjon (`CI`, `--print`, planlagt kjøring) + `vm` + rigg mangler →
**feil**, fordi ingen ser advarselen og vertskjøring uten lease kan kollidere.

### Ruting (lag 3) — endringen i `e2e-route/SKILL.md`

Ny akse 4 under «Routing inputs», og rutingstabellen får en executor-kolonne, med to
presiseringer det tidligere plugin-dokumentet manglet:

- «Committed regression / macOS» får **tre** inngangspunkter i prioritert rekkefølge:
  `./scripts/run-uitests.sh` hvis den finnes → ellers `vm-e2e` direkte hvis executor=vm →
  ellers `/macos-e2e-scaffold` (kun når ingen UI-test-target finnes). Det lukker hullet i B.
- Exploratory/MCP-live og visual-regression er alltid vert. Aksen leses ikke for dem.
- Beslutningsblokken får feltet `executor=<host|vm|vm→host-fallback>`.

## Implementasjon i faser

Rekkefølgen følger riggens egen anbefaling: riggen generaliseres og går mot ekte arbeid
først, plugin-rutingen legges om etterpå. Fase 0 og 1 er hver sin PR i hvert sitt repo.
Fase 2–3 er separate, senere PR-er som bygger på at fase 1 har vært i drift.

### Fase 0 — Riggen (`~/Developer/virtual-mac`)

Forutsetning for alt under. Grønn mot fagfilm-encoder (testplaner) **og** `swiftconfig`
(scaffold-generert, `SDKROOT = macosx`, ingen testplaner, target `SwiftConfigUITests`,
runner v1.10.0) før fase 1 vurderes.

**0.1 `bin/vm-e2e` — CLI og resultatkontrakt.** Posisjonsargumentene beholdes; `<plan>`
blir valgfri når `--only-testing` gis. Flagg parses i en enkel `while`-løkke før dagens
`${1:?}`-sjekker:

- `--only-testing <Target>` → `-only-testing:<Target>` i gjestens `test-without-building`;
  `.xctestrun` slås opp som `${SCHEME}_*.xctestrun` (nyeste) i stedet for `*_${PLAN}_*`.
  *Antakelse som verifiseres i 0.6:* uten testplaner heter bunten
  `<Scheme>_macosx<v>-arm64.xctestrun` — ingen slik finnes på disk ennå (swiftconfig er
  aldri bygget for testing).
- `--skip-build` → hopp over steg 1, men krev at `.xctestrun` finnes; feil ellers.
- `--result-bundle <dir>` (default `$DD/Results/<tidsstempel>.xcresult` på verten) →
  gjesten kjører med `-resultBundlePath /tmp/e2e-<ts>.xcresult`; bunten rsync-es tilbake
  **før** `cleanup` stopper VM-en (flytt hentingen inn før `stop_vm` i trap-rekkefølgen).
- `--json <fil>` → på verten: `xcrun xcresulttool get test-results summary --format json`
  → jq til `{total, passed, failed, skipped, executed, executor:"vm", vm, seconds,
  xcresult, results:[…]}` med `executed = total − skipped`. Skjemaet på Xcode 26 har
  `totalTestCount/passedTests/failedTests/skippedTests` (bekreftet). Samme JSON skrives til
  stdout som eneste stdout-artefakt; dagens grep-linjer flyttes til stderr.
- Exit-kode: 0 kun når `failed == 0` **og** kjøringen ga `EXIT=0`. `skipped > 0` er ikke feil,
  men skrives som egen advarselslinje på stderr («N tester hoppet over — sjekk fixturer»).

**0.2 Prosjekt-hook i stedet for FagfilmEncoder-logikk.** Linje 129–151 (ffprobe-symlink,
fatal sjekk) og 153–171 (fixtur-speiling) fjernes fra `vm-e2e`. Tilbake står den generelle
delen: `--shared-dir` for Homebrew og vent på at mounten finnes (`[ -d "$BREW_MOUNT" ]`, ikke
`ffprobe`). Etter overføring og før resignering kjører `vm-e2e` hooken
`$PROJ/scripts/vm-guest-prepare.sh` **på verten** hvis den finnes, med miljø:

```
VM_NAME VM_IP VM_USER=lume VM_SSH_KEY VM_PASSWORD VM_DD VM_SCHEME VM_PROJ VM_BREW_MOUNT
VM_SSH="ssh -i $KEY -o StrictHostKeyChecking=no lume@$IP"   # ferdig streng, bruk $VM_SSH "<kmd>"
```

Hooken kan dermed både rsync-e (host-side) og kjøre kommandoer i gjesten. Ikke-null exit
fra hooken er fatal. Hooken er repo-kontrollert kode som kjører på verten med brukerens
rettigheter — samme tillitsnivå som prosjektets egne `scripts/`, og dokumenteres slik.
fagfilm-encoder får `scripts/vm-guest-prepare.sh` med nøyaktig dagens innhold (ffprobe-
symlink + fixtur-speiling), så referansen får null atferdsendring.

**0.3 `bin/vm-stop <vm>`** — `stop_vm` (linje 38–48) trekkes ut som eget script, brukt av
`vm-e2e` og flake-wrapperen. Verifiserer at Virtualization-XPC-en faktisk er borte.

**0.4 `bin/vm-e2e-flake`.**
```
vm-e2e-flake <proj> <scheme> (<plan> [config] | --only-testing T) --runs N [--out DIR]
```
Minnegate først: `vm_stat` fri+inaktiv+spekulativ × 16384 ≥ `VM_FLAKE_MIN_FREE_GB` (default
8) — ellers avbryt med beskjed om å frigjøre. Bygger **én** gang på verten (samme
`build-for-testing`-linje som `vm-e2e`), setter `VM_KEEP_WARM=1` for barna, kjører
`seq N | xargs -P2 vm-e2e … --skip-build --json DIR/run-{}.json --result-bundle DIR/run-{}.xcresult`
(leasen serialiserer naturlig til to), stopper begge gjester med `vm-stop` til slutt.
Aggregering med jq over `run-*.json`: per-test feilrate (fra `results[].test`),
`executed`-avvik mellom kjøringer (flagges rødt — det er «grønn og tom»-detektoren),
veggklokke per kjøring. Skriver `DIR/summary.json` og en tabell til stdout.

**0.5 `bin/install`** — symlink `vm-e2e`, `vm-e2e-flake`, `vm-lease`, `vm-stop` inn i
`~/.local/bin/` (samme mappe som `lume`), idempotent. README får «Installasjon».

**0.6 Verifisering** (se seksjonen nederst). **0.7 Dokumentasjon**: README (ny CLI, hook-
kontrakt, install), `docs/xcuitest-i-vm.md` (status-avkryssing + måltall for flake-kjøringen),
`docs/plugin-integrasjon.md` (peker til denne spec-en), `CLAUDE.md` i riggen (ny regel:
prosjektspesifikk gjesteforberedelse bor i prosjektets hook, aldri i `vm-e2e`).

### Fase 1 — Plugin: ruting + runner + markør (`superpowers-gstack` 2.52.0)

Filer som endres:

- `skills/e2e-route/SKILL.md` — akse 4, rutingstabell med executor-kolonne, tre
  inngangspunkter for committed/macOS, fallback-regel, `executor=`-felt i beslutningsblokken,
  ikke-interaktiv-regel. Legg VM-forbeholdet i «Fallback»-avsnittet: scaffold-refusal 3
  («UI-test target already exists») betyr «kjør eksisterende runner», ikke MCP-live.
- `skills/macos-e2e-scaffold/SKILL.md` — runner-mal v2 (`# Auto-generated by
  /macos-e2e-scaffold v2.52.0`): leser `.gstack/e2e-executor`, `command -v vm-e2e`, dispatcher
  eller kjører lokalt, samme JSON ut, `skipped` alltid synlig, fallback-advarsel, pre-flight
  `automationmodetool`-sjekk på verten (advarsel, ikke stopp). SPM-stubben uendret.
  `ios-e2e-scaffold` røres ikke (aksen er macOS-only).
- `skills/setup-routing/blocks/xcode-tools.md` — ett nytt avsnitt «E2E executor» i denne
  blokken (ikke `track-routing.md`, som kun handler om skill-intercept). Den eier allerede
  Apple-verktøytabellen med `xcodebuild test`-raden, er native-gatet i begge generatorene, og
  bruker `{{…}}`-plassholdere (`{{DEVELOPMENT_TEAM}}`, `{{IOS_SIMULATOR}}` i
  `blocks/PLACEHOLDERS.md:16,33`). Nytt: `{{E2E_EXECUTOR}}` resolvert fra
  `.gstack/e2e-executor` (fravær → `host`). Marker `<!-- gstack-xcode-tools-v6 -->` → v7;
  `adapt/SKILL.md:592` får en ny rad i fire-tilfelle-stigen (v6 superseded). Lint som fyrer:
  E8 (blokk referert av begge), E12 (ingen uresolvert plassholder), E14 (linje 1 uten
  `emitted=`).
- `skills/adapt/SKILL.md` (Step 5, ved linje 592-gaten) og `skills/setup-routing/SKILL.md`
  (Step 6, ved `blocks/xcode-tools.md`-punktet, linje 283) — når `.gstack/track` er
  `macos`/`both`: spør én gang «Kjør committed E2E i VM-rigg (krever `vm-e2e` på PATH) eller
  på verten?» med `host` som default, skriv `.gstack/e2e-executor`, legg til
  `!.gstack/e2e-executor` i `.gitignore` etter samme mønster som
  `swiftui-design-consultation/SKILL.md:814-829`. Web- og iOS-only-prosjekter: ingen fil.
  Merk: i dag er begge skills **rene lesere** av `.gstack/track` (skriverne er
  `office-hours-track-aware:203` og `swiftui-design-consultation:134`); dette blir første
  markør de selv skriver. Alternativet — la `macos-e2e-scaffold` skrive den — dekker ikke
  prosjekter som fagfilm-encoder uten scaffold, så onboarding-skillene er riktig eier.
  `e2e-route` forblir ren leser (den erklærer selv at den ikke endrer filer, linje 120–126).
- `scripts/vm-hygiene.sh` + `hooks/hooks.json` (SessionStart) — **kun** når
  `.gstack/e2e-executor` = `vm`: rapporter kjørende `lume run`-prosesser, foreldreløse
  `Virtualization.VirtualMachine.xpc`, og opptatte leaser (`vm-lease status`). Rapport, aldri
  handling — riggens regel er at ingen automatikk stopper en VM. Stille ellers.
- `CLAUDE.md` (rutingseksjonen), `README.md`, `CHANGELOG.md` `## [2.52.0]`,
  `.claude-plugin/plugin.json`. `IDEAS.md`: notat under live-swiftui-vs-cliclick om VM som
  macOS computer-use-mål.
- `tests/unit/test_e2e_executor_marker.py` — ren stdlib: parser markørverdi (`vm`/`host`/
  tom/ugyldig), fallback-beslutning (rigg funnet × interaktiv), og at runner-malen i
  SKILL.md inneholder både `command -v vm-e2e` og `skipped`. Speiler hvordan de andre
  unit-testene leser SKILL.md-tekst.
- `tests/integration/test_e2e_executor_dispatch.sh` — `claude --print` mot fixture med
  `.gstack/e2e-executor=vm` og en med fravær; forventer `executor=vm` hhv. `executor=host` i
  beslutningsblokken. Samme mønster som `test_track_aware_dispatch.sh`. Kjøres manuelt.

Gjenbruk: jq-uttrykket og `PIPESTATUS`-mønsteret fra dagens runner-mal
(`macos-e2e-scaffold/SKILL.md:356-373`); `.gitignore`-negasjonen fra
`swiftui-design-consultation/SKILL.md:825-829`; hook-strukturen i `hooks/hooks.json`.

### Fase 2 — Flakiness-skill (`/superpowers-gstack:e2e-flake`, 2.53.0)

Tynn skill over `vm-e2e-flake`: Phase 0 nekter uten `vm-e2e` på PATH eller uten
`e2e-executor=vm`; spør N (default 4); kjører i `run_in_background` med `ScheduleWakeup`-
fallback (readiness-ladder-reglene fra `e2e-route` gjelder); rapporterer pass-rate-tabell,
`executed`-avvik og hvilke tester som er ustabile. Rutes fra `e2e-route` ved verbene
«flaky» / «ustabil» / «kjør N ganger». Ny rad i rutingstabellen.

### Fase 3 — Asynkron E2E som plan-konvensjon (2.54.0, valgfri)

`autoimplement` rører ikke tester, så dette er en konvensjon i `writing-plans`-malen og et
avsnitt i `xcode-tools.md`, ikke en autoimplement-endring: når `e2e-executor=vm`, skriver
planen fase-N-verifiseringen som `./scripts/run-uitests.sh --json .gstack/e2e-N.json &`
(runneren får et `--background`-flagg som returnerer umiddelbart og skriver JSON når
ferdig), og fase N+1 starter med «samle `e2e-N.json`; rød → stopp før commit». Verten
forblir fri til bygging fordi `vm-e2e` stopper gjesten når den er ferdig. Trigger for å
faktisk bygge dette: første plan der E2E-ventetiden ved fasegrenser overstiger byggetiden.

### Ikke i denne spec-en (utsatt, med utløser)

- `/fresh-machine-check` og Gatekeeper-test av Release-bygg — utløser: første gang en
  release feiler på en annen Mac, eller `/ship` får et «pre-release smoke»-steg.
- iOS-simulator i gjest — utløser: noen ber om parallell iOS-E2E.
- macOS computer-use i VM — avgjøres i den åpne `IDEAS.md`-beslutningen, ikke her.

## Verifisering

**Fase 0 (rigg).** Forutsetning: ingen VM kjører, ≥ 8 GB fritt.
```bash
export PATH="$HOME/.local/bin:$PATH"
# 1) Referansen, testplan-vei — må gi samme tall som i dag
cd ~/Developer/GitHubReposNye/FAGFILM_REPOS/fagfilm-encoder
vm-e2e "$PWD" FagfilmEncoder E2E E2ESmoke --json /tmp/smoke.json && jq . /tmp/smoke.json
# forventet: total 16, passed 7, failed 0, skipped 9, executed 7; xcresult-sti på verten finnes
# 2) Scaffold-vei uten testplan — verifiserer .xctestrun-navneantakelsen og --only-testing
cd ~/Developer/swiftconfig
vm-e2e "$PWD" SwiftConfig --only-testing SwiftConfigUITests --json /tmp/sc.json && jq . /tmp/sc.json
# forventet: JSON med executed > 0 (stubbene feiler med XCTFail — det er riktig; poenget er
# at de KJØRER i gjesten, ikke at de er grønne). Ingen ffprobe-feil.
# 3) Flakiness-jakt — to bølger, begge gjester, én bygging
cd ~/Developer/GitHubReposNye/FAGFILM_REPOS/fagfilm-encoder
vm-e2e-flake "$PWD" FagfilmEncoder E2E E2ESmoke --runs 4 --out /tmp/flake
jq . /tmp/flake/summary.json                      # executed identisk i alle fire; feilrate-tabell
# 4) Opprydding og hygiene
vm-lease status                                   # begge ledige
pgrep -fl "lume run|Virtualization.VirtualMachine.xpc" || echo "ingen gjester igjen"
# 5) Riggens negative case
echo host > /tmp/x/.gstack/e2e-executor 2>/dev/null; vm-e2e /tmp/x S P; echo "exit=$? (forventet 2)"
```
Deretter `superpowers-gstack:pitfall-verification` på rigg-diffen (bash, kontrakt, sikkerhet
rundt hook-kjøring → ship-worthy, Codex-lens).

**Fase 1 (plugin) — senere løp:**
```bash
cd ~/Developer/superpowers-gstack
python3 scripts/lint-skills.py                    # grønn: E4/E6/E8 + routing coverage
bash tests/run.sh --unit
bash tests/run.sh --integration                   # manuelt, koster noen cent
```
Deretter i fagfilm-encoder: `/superpowers-gstack:adapt` → svar `vm` → fila finnes og er
committet; `/superpowers-gstack:e2e-route` med «kjør regresjon» → beslutningsblokk med
`executor=vm` og «Next action: vm-e2e …» (prosjektet har ingen scaffold-runner). I et
scaffold-generert prosjekt: `./scripts/run-uitests.sh` gir identisk JSON på vert og i VM, og
med `PATH` uten `vm-e2e` gir den fallback-advarselen og kjører på verten.

Til slutt: `superpowers-gstack:pitfall-verification` på plugin-diffen (ship-worthy → Codex;
rutingskontrakt → tredje hus), per release-gaten i plugin-ens CLAUDE.md.
