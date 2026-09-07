# VM-basert E2E-testing: hva som må gjøres i superpowers-gstack

*Skrevet 2026-09-07. Riggen ligger i `~/Developer/virtual-mac` og er verifisert i drift.
Dette dokumentet forteller hva som gjenstår **her**, i plugin-en.*

## Bakgrunn i én setning

macOS-XCUITest-suiter teller app-instanser maskin-globalt og krever derfor eksklusiv tilgang
til maskinen. Én VM per testkjøring gir hver kjøring sitt eget prosessrom, sin egen
WindowServer og sin egen TCC-database — og dermed kan to kjøringer gå samtidig uten at
testkoden endres.

## Ingenting er endret i plugin-en ennå

`e2e-route` og `macos-e2e-scaffold` er urørt. Alle prosjekter kjører E2E på verten som før.
Det er med vilje: riggen bør gå mot ekte arbeid noen dager før rutingen legges om.

## Endringen som skal gjøres

### Prinsipp: løs kobling

Fravær av konfigurasjon betyr **vert**, altså dagens oppførsel. Prosjekter melder seg inn.
Plugin-en fungerer uendret på maskiner uten Lume. Samme mønster som `.gstack/track`.

### 1. Ny ruting-akse i `skills/e2e-route/SKILL.md`

Under «Routing inputs (read in order)», som punkt 4:

> ### 4. Executor location — host vs VM
>
> Read `.gstack/e2e-executor` in the project root:
>
> - `vm` → dispatch through `~/Developer/virtual-mac/bin/vm-e2e`
> - `host`, or file absent → run locally, as before
>
> Only meaningful for **committed regression** runs on **macOS**. Exploratory MCP-live runs
> always use the host — a live simulator session cannot be driven inside a headless guest.

Ny rad i rutingstabellen:

| Intent | Platform | `.gstack/e2e-executor` | Executor |
|---|---|---|---|
| Committed regression | macOS | `vm` | `vm-e2e <proj> <scheme> <plan> [config]` |
| Committed regression | macOS | `host` / fraværende | `scripts/run-uitests.sh` |

### 2. `adapt` og `setup-routing`

Bør kunne skrive `.gstack/e2e-executor` når et prosjekt adopteres, med `host` som default.

### 3. Ikke legg dette i agent-minne

Kravet om én kjøring per macOS-instans er en **korrekthets-invariant**, ikke en preferanse.
Et minne kan ikke hindre at to kjøringer lander på samme maskin — det kan bare be agenten om
å la være. Leasen i `bin/vm-lease` er mekanismen.

## Én VM eller to? Vurderingen

Taket er to samtidige macOS-gjester; den tredje avvises av Virtualization.framework. Men to
er ikke alltid riktig.

### Bruk to når

- **Flakiness-jakt.** Samme kode kjøres N ganger for å se om den holder. Embarrassingly
  parallel, ingen delt tilstand, og gevinsten er lineær: fire kjøringer tar to bølger.
  Dette er den klart viktigste bruken.
- **Uavhengige testplaner.** `Integration` og `E2E` samtidig, eller `E2ESmoke` og `E2EFull`.
- **To prosjekter** som skal verifiseres i samme tidsrom.

### Bruk én når

- **Du bygger samtidig.** Xcode-bygging er minnetungt. Målt på en M1 Max med 64 GB: bygg
  pluss to VM-er drepte kjøringen tre ganger. Bygg først, kjør så — dispatcheren gjør det i
  den rekkefølgen, men to *samtidige* dispatcher-kall bygger samtidig.
- **Du feilsøker en enkelt test.** Parallellitet gir ingenting når du venter på ett svar, og
  to VM-er gjør loggbildet vanskeligere å lese.
- **Verten skal være brukbar.** To gjester à 4 GB tar 8 GB pluss overhead. På en maskin som
  har stått lenge er det nok til at alt annet blir tregt.
- **Kjøringen er kort.** Under et minutt per kjøring er oppstartskostnaden — boot, overføring,
  resignering — en større andel enn selve testen.

### Måltall som grunnlag

| | Testutførelse |
|---|---|
| Én VM alene | 27,8 s |
| To VM-er samtidig | 27,6 s og 29,1 s |

**Ingen målbar degradering.** Ressurskonkurransen mellom to gjester er ikke problemet —
minnet på verten er det, og bare når du bygger samtidig.

### Tommelfingerregel

> Parallelliser **kjøringer**, ikke **bygg**. Bygget betales én gang på verten uansett (671 s
> fullt, ~10 s inkrementelt). Det er testutførelsen som skal fordeles.

## Forutsetninger riggen har som verten ikke dokumenterer

Disse ble oppdaget ved å flytte testene, og gjelder ethvert nytt kjøremiljø:

- **Testfixturer** finnes ikke i et ferskt miljø. `E2EUITestCase` bruker `#filePath`, så
  fixturstien er byggemaskinens absolutte sti. Mangler de, kastes `XCTSkip` — og et hopp ser
  ut som en pass. Riggen rapporterte grønt mens den kjørte to av sju tester før dette ble
  fanget.
- **Verktøy fra Homebrew.** `FagfilmEncoder` kaller `/opt/homebrew/bin/ffprobe` ved import.
- **Automasjonsmodus.** `automationmodetool enable-automationmode-without-authentication`.
  Dette gjelder også verten: uten det virker E2E der bare når noen er logget inn med opplåst
  skjerm.

**Akseptansekriteriet må være antall utførte tester, ikke exit-koden.** Uten en baseline fra
verten er «grønn og rask» ikke til å skille fra «grønn og tom».

## Videre lesning

`~/Developer/virtual-mac/docs/xcuitest-i-vm.md` — oppskrift, fallgruver, alle måltall.
