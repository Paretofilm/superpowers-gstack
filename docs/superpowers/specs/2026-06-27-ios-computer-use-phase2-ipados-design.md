# Design: Fase 2 — iPadOS-utvidelse av visuell computer-use-utforsking

- **Dato:** 2026-06-27
- **Status:** Forslag — venter på bruker-review før writing-plans
- **Tema:** Utvide Tier-2 visuell computer-use-utforsking (Fase 1: iPhone) til iPadOS-simulator, fullskjerm, med device/orientering-bevisst safe-area og en iPad-robust foreground-oracle.
- **Forutsetter:** Fase 1 (`2026-06-26-ios-computer-use-visual-explore-design.md`, landet i `06a3a89`) + `SPIKE-FINDINGS.md`.

## 1. Motivasjon og rammer

Fase 1 leverte en autonom, skjermbilde-drevet visuell utforsker for SwiftUI-apper på **iPhone-simulator** via Gemini `computer_use` + `idb`. Arkitekturen ble allerede designet «revidert for iPadOS + pluggbar executor», men selve Fase 1-koden tok flere iPhone-spesifikke snarveier som må revurderes før verktøyet er korrekt på iPad.

**Sentral innsikt fra kode-gjennomgang (endrer scope):** Den antatt største Fase 2-jobben — «@2x device-klasse-mapping» (designets §11) — er **allerede løst**. SPIKE-funnet (Task 1) viste at `idb ui tap` tar **punkter**, ikke piksler, og `coords.denormalize` mapper 0–1000 mot `executor.coordinate_space()` som leses **dynamisk** fra `describe-all` Application-frame. Koordinat-mappingen er derfor allerede device-agnostisk; @3x iPhone vs @2x iPad er irrelevant. Den reelle Fase 2-overflaten er smalere og består av tre ting: (1) device/orientering-bevisst safe-area, (2) iPad-robust foreground-oracle, (3) iPad-verifisering.

## 2. Mål og ikke-mål

### Mål
- iPad-simulator, **fullskjerm**, **fri visuell utforsking** (samme modus A som Fase 1 — ikke lagrede flyter).
- `--orientation portrait|landscape`, fast per run: pre-flight setter orientering og utleder safe-area for den orienteringen, konstant under hele runet.
- Device/orientering-bevisst safe-area som **erstatter** de hardkodede `cli.py`-konstantene `TOP_INSET=50`/`BOTTOM_INSET=40`.
- Foreground-oracle som er korrekt på iPad og **ærlig avbryter** hvis appen forlater fullskjerm (split-view), i stedet for å feil-positivere.
- iPad smoke-test (portrett + landskap) mot en enkel SwiftUI-app.

### Ikke-mål
- **Split-view / Stage Manager-utforsking** eller multi-window-navigasjon. Vi *detekterer* at appen ikke lenger er fullskjerm og avbryter; vi utforsker ikke splits. (Matcher designets R4 — Stage Manager-drag var allerede ikke-mål.)
- **Multi-touch / komplekse gestures** (pinch, rotate, Stage Manager-drag).
- **Agent-styrt rotasjon** — orientering settes av operatøren i pre-flight, ikke av agenten (idb-rotasjon midt i loop er upålitelig og utenfor touch-handlingsrommet).
- Lagrede flyter (Fase 3) og macOS (Fase 4).

### Delt-kode-konsekvens (eksplisitt beslutning)
Safe-area-utledningen lever i den **delte** `cli.py`/`coords.py`-stien, så den blir device/orientering-bevisst for **alle** mål. Det fikser den latente **iPhone-landskap-bugen** (Fase 1 antok implisitt portrett) som bieffekt. Vi smoke-verifiserer **iPhone-portrett (regresjon: må være uendret)** + **iPad-portrett** + **iPad-landskap**. iPhone-landskap blir korrekt av samme logikk, men er **ikke** en egen verifisert smoke-leveranse i Fase 2.

## 3. SPIKE-gate (FØR all implementasjon — speiler Fase 1 Task 1)

Fase 1 lærte at uverifiserte antagelser om idb/SDK koster mest (live-smoke fanget 3 integrasjonsbugs enhetstester var blinde for). Disse iPhone-antagelsene **må verifiseres mot en faktisk booted iPad-sim før kode skrives**, hver med eksplisitt fallback. Resultatene skrives som **addendum til `SPIKE-FINDINGS.md`** (samme fil som Fase 1), og planen justeres mot dem per task.

| # | Antagelse å verifisere på iPad-sim | Fallback hvis den feiler |
|---|-----------------------------------|--------------------------|
| **S1** | `describe-all` eksponerer status-bar / home-indicator-frames pålitelig (portrett **og** landskap), slik at safe-area kan utledes. **Sammenlign utledede insets mot `INSET_TABLE`-verdiene:** stemmer de overens og er stabile på tvers av iOS-versjoner? | Device-klasse×orientering-**tabell** (`INSET_TABLE`). **Hvis derive viser seg skjør** (avviker fra tabell / varierer med iOS-versjon), **flipp prioriteten: tabell primær, derive sekundær validering** — jf. tredje-lens-utfordringen. Spiken har mandat til denne flippen (slik Fase 1-spiken snudde 3 antagelser) |
| **S2** | `spotlight-pill` finnes som hjemskjerm-markør på iPad (oracle-antagelsen fra R7) | Finn alternativ iPad-hjemskjerm-markør. **Hvis ingen finnes:** `_on_home_screen` returnerer alltid `False` på iPad → oracle kan ikke fange hjemskjerm-exit (fail-open i home-deteksjonen, jf. `preflight.py:40-54`). Da må SKILL.md eksplisitt si at hjemskjerm-exit **ikke** detekteres på iPad — aldri hevdes som dekket mens degradert (Fase 1 R7-disiplin). |
| **S3** | Foreground-oracle skiller fullskjerm fra **split-view** (appen lever men deler skjerm) — heuristikk: senere Application-frame-bredde < baseline full-bredde fanget ved launch | Dokumenter split-deteksjon som best-effort; avbryt konservativt |
| **S4** | idb touch-handlinger (`tap`/`swipe`/`text`) virker mot iPad-UDID i begge orienteringer, og `environment: "mobile"` gir fornuftige iPad-handlinger (R4 for iPad) | Snevre handlingsrommet; marker udekte handlinger som `unsupported` ærlig |
| **S5** | `simctl` (eller `idb`) kan sette orientering deterministisk i pre-flight, og `describe-all` Application-frame reflekterer den **etter et settle-vindu** (orientering-animasjon kan gi stale frame) | Krev manuell orientering-oppsett før kjøring; dokumenter. Verifiser-og-vent: les `describe-all` til frame-aspekt matcher forespurt orientering, eller timeout |
| **S6** | `simctl launch` gir en **fullskjerm** baseline (ikke en gjenopprettet split-/Stage-Manager-tilstand fra forrige kjøring), slik at `baseline_full_width` faktisk er full skjermbredde | **Terminate-før-launch** (`simctl terminate`) for å nullstille vindustilstand; **valider** baseline mot kjent device-full-bredde (fra `device_class`), ikke bare «første frame». Matcher ikke baseline device-full-bredde → fail-closed med melding |
| **S7** | `describe-all` eksponerer **`bundleID`** (eller tilsvarende felt) på Application-elementet, så oracle kan verifisere at **frontmost-app ER target** (ikke bare at *en* app er fullskjerm) — fanger backgrounding (URL→Safari), SpringBoard, og Slide-Over-av-annen-app | Hvis feltet mangler: bruk en alternativ probe (`idb ui describe` / `simctl spawn launchctl` frontmost), ellers dokumenter at oracle ikke kan skille apper og fall tilbake til width+home-heuristikk |

**Gate-regel:** ingen Fase 2-implementasjonstask starter før spike-addendumet finnes og hver antagelse er enten bekreftet eller eksplisitt nedgradert til sitt fallback.

## 4. Komponentendringer (per fil)

| Fil | Endring |
|-----|---------|
| `coords.py` | `denormalize` / `SafeArea` / `in_safe_area` **uendret** (allerede device-agnostisk). **Ny** ren funksjon `derive_insets(elems, point_w, point_h) -> SafeArea \| None` (utled fra describe-all-elementer; ren → fixture-testbar). **Sanity-guard:** hvis en utledet inset er negativ eller > **25 %** av tilhørende dimensjon (feilidentifisert element, f.eks. en in-app `StatusBar`-view), returner `None` → fall til tabell. **Ny** `INSET_TABLE[device_class][orientation]` + `table_insets(device_class, orientation, point_w, point_h) -> SafeArea` fallback (ren). |
| `executor_idb.py` | **Sannsynligvis uendret.** `coordinate_space()` (loop.py:27 kaller den) gjør allerede sitt eget `describe-all`; det er idempotent og akseptert. Pre-flight describe-all eies av `preflight.py` (sheller idb direkte, som `_on_home_screen` allerede gjør) — **ikke** via executoren, siden executoren konstrueres etter preflight. `tap`/`swipe`/`type_text`/`coordinate_space` uendret. |
| `preflight.py` | **`preflight` eier all pre-flight `describe-all`** og **bygger ferdig `SafeArea`** (kaller `coords.derive_insets`/`table_insets`) — executoren konstrueres etter preflight (`cli.py:95-96`), så safe-area kan ikke avhenge av den. Sekvens: **(1)** `simctl terminate` (nullstill split-/Stage-tilstand, S6) → **(2)** sett orientering (S5) → **(3)** `simctl launch` → **(4)** **bounded settle:** les `describe-all` til frame-aspekt matcher orientering, **maks 10 polls / ~15s**, ellers `PreflightError` (S5) → **(5)** fang `baseline_full_width` = Application-frame-bredde, **valider** mot device-full-bredde fra `device_class`; **ukjent `device_class` → fail-closed `PreflightError`** (kan verken validere baseline eller slå opp insets-tabell) → **(6)** bygg `SafeArea` fra samme elems. **Oracle-redesign (S7):** `is_app_foreground(udid, bundle_id, baseline_full_width)` gjør **ett** `describe-all`, henter Application-elementet, og krever `Application.bundleID == bundle_id` **AND** `NOT hjemskjerm` (S2) **AND** bredde ≥ `0.95 × baseline_full_width` (S3). `bundleID`-sjekken fanger backgrounding (URL→Safari), SpringBoard og Slide-Over-av-annen-app som width+home alene ikke fanger; den erstatter ikke de andre, den legger til. **Ny** `device_class(udid) -> str`. Returner i env (skalarer, **ikke** rå elems): `orientation`, `device_class`, `safe_area`, `safe_area_source`, `baseline_full_width`. |
| `cli.py` | **Fjern** `TOP_INSET`/`BOTTOM_INSET`. Legg til `--orientation {portrait,landscape}` (default `portrait` → bakoverkompatibel med Fase 1). Pass `orientation` til `preflight`. Bruk **`env["safe_area"]`** direkte (preflight bygde den) i begge stier (dry-run + hovedløkke) — cli rører ikke rå elems. **Foreground-closure utvides:** `foreground_check=lambda: preflight.is_app_foreground(udid, bundle, env["baseline_full_width"])`. |
| `loop.py` | **Uendret.** Split-view fanges av eksisterende `foreground_check`-callback (returnerer `False` når ikke fullskjerm) → loop avbryter med status `app_left_foreground`. **Merk (loop.py:82-88):** callbacken er en ren `bool`, og loop registrerer **ingen detail/reason** — split-view er derfor **ikke skillbar** fra andre forgrunns-tap (krasj, backgrounding) i rapporten. Det aksepteres for et best-effort-verktøy; å skille dem ville krevd en kontrakt-endring i `loop.run` (utenfor scope). Status-vokabular uendret (`completed`/`step_limit`/`app_left_foreground`/`error`). |
| `report.py` | Env-seksjon viser nå `orientation`, `device_class`, `safe_area_source` (`derived` vs `table`). |
| `gemini.py` | **Uendret** — `environment: "mobile"` dekker iPad (bekreftes i S4). |
| `skills/ios-visual-explore/SKILL.md` | Dokumenter iPad-støtte, `--orientation`, fullskjerm-only-begrensning; fjern iPad-Fase-2-deferral-noten. |
| `scripts/ios-visual-explore` | Argv-passthrough for `--orientation` (sannsynligvis uendret utover dokumentasjon). |

### Safe-area-utledningskontrakt
**Eierskap (løser ordering + report-lekkasje):** `preflight` gjør pre-flight `describe-all` **og bygger ferdig `SafeArea`** — fordi executoren konstrueres *etter* preflight (`cli.py:95-96`), og fordi rå `describe-all`-elems (titalls KB JSON) **ikke skal** havne i env som sendes til `report.build_markdown`. `preflight` returnerer kun skalarer + den ferdige `SafeArea` i env. Bygge-rekkefølge inne i preflight:
1. `derive_insets(elems, point_w, point_h)` → `SafeArea` eller `None` (`None` ved manglende insets **eller** sanity-guard-utslag).
2. Ved `None`: `table_insets(device_class, orientation, point_w, point_h)` (`safe_area_source="table"`); ellers `safe_area_source="derived"`.
3. **Primær/fallback-prioritet er spike-styrt (S1):** default er derive-primær (brukerens valg), men hvis spiken viser at derive er skjør, flippes til tabell-primær.
4. Resultatet er samme `SafeArea`-form som `loop.run` allerede konsumerer — `loop`/`coords` ser ingen forskjell.

**Frame-origin-antagelse (fullskjerm):** `coords.denormalize` (coords.py:15) mapper 0–1000 til `(0..point_w, 0..point_h)` og **ignorerer Application-frame `x`/`y`-origin** (executor leser kun width/height). For et **fullskjerm**-mål er origin `(0,0)`, så dette er korrekt. Spike (S6) bekrefter at fullskjerm-iPad-frame har origin `(0,0)` i begge orienteringer; hvis ikke (non-zero origin), trenger `denormalize` et origin-offset — flagges som spike-funn, ikke antatt bort.

**Landskap setter alle fire kantene:** i landskap flytter dynamic island / home-indicator til **sidene**, så `derive_insets` og `INSET_TABLE` må sette `left`/`right` (ikke bare `top`/`bottom` som Fase 1-portrett-snarveien). `SafeArea`-dataclass har allerede alle fire felt; det er kun bygge-logikken som må fylle dem orienteringskorrekt. Enhetstestene (§5) dekker landskap-fixtures eksplisitt.

## 5. Testing

**Enhetstester (deterministisk, ingen sim):**
- `derive_insets` mot **spike-fangede** describe-all-fixtures: iPad portrett, iPad landskap, iPhone portrett, iPhone landskap. Asserterer korrekte insets per fixture.
- `table_insets` fallback-oppslag per device-klasse × orientering.
- **`derive_insets` sanity-guard:** fixture med feilidentifisert element (inset > 25 % / negativ) → returnerer `None` (faller til tabell).
- **Ukjent `device_class` → fail-closed:** `PreflightError` med handlingsbar melding (ikke KeyError / zero-insets).
- **Oracle (S7):** Application-element med `bundleID != target` → `is_app_foreground == False` (backgrounding/SpringBoard/Slide-Over-fixtures); `bundleID == target` + fullskjerm → `True`.
- `denormalize` med iPad-frame-case (f.eks. 820×1180) — bekreft device-agnostisk mapping.
- Split-view frame-bredde-heuristikk (fullskjerm vs split fixtures).
- Regresjon: iPhone-portrett-insets via ny sti == gammel hardkodet `(0, 50, w, h-40)`-oppførsel (eller dokumentert forbedring).

**Smoke (live iPad-sim):**
- iPad-portrett mot enkel SwiftUI-app → rapport + skjermbilder, safe-area-kilde logget.
- iPad-landskap mot samme app → rapport + skjermbilder.
- **iPhone-portrett regresjons-smoke** → oppførsel uendret fra Fase 1.

**Sim-krav:** booted iPad-sim med idb-companion tilkoblet + en enkel SwiftUI-app installert. iPhone-sim fra Fase 1: iPhone 17 Pro iOS 26.5 (UDID `4FA4A85E-E97F-41BA-A3A7-1ED5FB2574F2`).

## 6. Risikoer

- **R-iPad-1:** `describe-all` gir ikke insets pålitelig på iPad → `INSET_TABLE`-fallback (gatet av S1). Akseptabelt: tabellen er eksplisitt og testbar.
- **R-iPad-2:** orientering-setting i pre-flight uverifisert (S5) → spike avgjør mekanisme; fallback er manuell oppsett dokumentert.
- **R-iPad-3:** split-view-deteksjon er **best-effort** (S3): frame-bredde-heuristikk kan gi false negatives på to konkrete måter — (a) **Slide Over** legger en flytende app *over* mål-appen uten å endre mål-appens frame-bredde, så bredde-heuristikken ser fortsatt «fullskjerm»; (b) foreground-proben er **fail-open** (`loop.py` linje 40–41/85–86: enhver exception i `foreground_check` → `alive=True`), så et describe-all-feil under sjekken antar fullskjerm og fortsetter. **Demping (S7):** `bundleID == target`-sjekken fanger Slide-Over-tilfellet *når den andre appen blir frontmost* (Application-elementet er da ikke target), så hullet i (a) er smalere enn ren bredde-heuristikk — gjenstående hull er Slide Over der target *forblir* frontmost. Begge er akseptert restrisiko for et ikke-destruktivt verktøy; dokumenteres i SKILL.md.
- **R-iPad-6 (teardown):** pre-flight muterer nå sim-state mer enn Fase 1 — **`simctl terminate` → orientering → launch** (Fase 1-design §7 flagget at sim-state ikke nullstilles ved kill). Etter en kjøring står simulatoren i den valgte orienteringen. Mitigering: dokumenter at orientering er en bevisst, vedvarende sim-mutasjon (operatøren satte den eksplisitt via `--orientation`, så vedvarenhet er forventet, ikke en lekkasje); `terminate` er idempotent. SKILL.md noterer at sim-orienteringen forblir endret.
- **R-iPad-7 (baseline-integritet):** `baseline_full_width` er fundamentet for split-deteksjonen. `simctl launch` garanterer ikke i seg selv en fullskjerm-tilstand (kan gjenopprette forrige split-/Stage-tilstand). Mitigering (S6): terminate-før-launch + valider baseline mot kjent device-full-bredde fra `device_class`, fail-closed ved avvik. Restrisiko: avhenger av at `device_class`-tabellen kjenner device-full-bredden — ukjent device → kan ikke validere, må fail-closed eller dokumentere svekkelse.
- **R-iPad-4:** `spotlight-pill` ikke til stede på iPad (S2) → alternativ markør eller svekket oracle-claim, aldri shippet som fail-closed mens degradert (samme disiplin som Fase 1 R7).
- **R-iPad-5 (regresjon):** `cli.py`/`coords.py` deles med iPhone-stien → endring kan regresjonere Fase 1. Mitigering: behold `portrait`-default, hold `denormalize`/`loop`/`gemini` urørt, kjør iPhone-portrett regresjons-smoke før merge.

## 7. Faseplan-plassering

Dette er **Fase 2** i den opprinnelige fem-fase-planen (designets §11). Fase 3 (lagrede flyter) og Fase 4 (macOS/cliclick) er uberørt. Disiplinen er identisk med Fase 1: **spec (dette dok) → 2 lens-runder → writing-plans → SPIKE-gate → subagent-drevet impl med per-task review**.
