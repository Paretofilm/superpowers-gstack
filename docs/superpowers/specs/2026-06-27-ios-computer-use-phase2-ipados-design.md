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
| **S1** | `describe-all` eksponerer status-bar / home-indicator-frames pålitelig (portrett **og** landskap), slik at safe-area kan utledes | Device-klasse×orientering-**tabell** (`INSET_TABLE`) |
| **S2** | `spotlight-pill` finnes som hjemskjerm-markør på iPad (oracle-antagelsen fra R7) | Finn alternativ iPad-hjemskjerm-markør; ellers svekk oracle-claimet eksplisitt |
| **S3** | Foreground-oracle skiller fullskjerm fra **split-view** (appen lever men deler skjerm) — heuristikk: senere Application-frame-bredde < baseline full-bredde fanget ved launch | Dokumenter split-deteksjon som best-effort; avbryt konservativt |
| **S4** | idb touch-handlinger (`tap`/`swipe`/`text`) virker mot iPad-UDID i begge orienteringer, og `environment: "mobile"` gir fornuftige iPad-handlinger (R4 for iPad) | Snevre handlingsrommet; marker udekte handlinger som `unsupported` ærlig |
| **S5** | `simctl` (eller `idb`) kan sette orientering deterministisk i pre-flight, og `describe-all` Application-frame reflekterer den | Krev manuell orientering-oppsett før kjøring; dokumenter |

**Gate-regel:** ingen Fase 2-implementasjonstask starter før spike-addendumet finnes og hver antagelse er enten bekreftet eller eksplisitt nedgradert til sitt fallback.

## 4. Komponentendringer (per fil)

| Fil | Endring |
|-----|---------|
| `coords.py` | `denormalize` / `SafeArea` / `in_safe_area` **uendret** (allerede device-agnostisk). **Ny** ren funksjon `derive_insets(elems, point_w, point_h) -> SafeArea` (utled fra describe-all-elementer; ren → fixture-testbar). **Ny** `INSET_TABLE[device_class][orientation]` + `table_insets(device_class, orientation, point_w, point_h) -> SafeArea` fallback. |
| `executor_idb.py` | Trekk ut `_describe_all() -> list` helper; `coordinate_space()` gjenbruker den. Lar safe-area-utledning og coordinate_space dele **ett** idb-kall i pre-flight (unngå dobbel describe-all). `tap`/`swipe`/`type_text` uendret. |
| `preflight.py` | `preflight(udid, bundle, orientation)`: sett orientering via `simctl`/`idb` (mekanisme = spike S5) **før** launch, og fang **baseline full-bredde** (Application-frame-bredde rett etter launch, da appen garantert er fullskjerm). Utvid `is_app_foreground` for iPad: nå `prosess lever AND NOT hjemskjerm (S2) AND fullskjerm`, der fullskjerm = Application-frame-bredde ≈ baseline full-bredde (split-view gir smalere frame, S3). **Ny** `device_class(udid) -> str` fra `simctl` device-type (for tabell-fallback). Returner `orientation`, `device_class`, `safe_area_source`, `baseline_full_width` i env-dict. |
| `cli.py` | **Fjern** `TOP_INSET`/`BOTTOM_INSET`. Legg til `--orientation {portrait,landscape}` (default `portrait` → bakoverkompatibel med Fase 1). Bygg `SafeArea` via `derive_insets` (primær) med `table_insets` (fallback) i **begge** stier (dry-run + hovedløkke). Pass `orientation` til `preflight`. Inkluder safe-area-kilde i env for rapport. |
| `loop.py` | **Uendret.** Split-view fanges av eksisterende `foreground_check`-callback (returnerer `False` når ikke fullskjerm) → loop avbryter med `app_left_foreground`, detail `split-view/multitasking`. Status-vokabular forblir stabilt (`completed`/`step_limit`/`app_left_foreground`/`error`). |
| `report.py` | Env-seksjon viser nå `orientation`, `device_class`, `safe_area_source` (`derived` vs `table`). |
| `gemini.py` | **Uendret** — `environment: "mobile"` dekker iPad (bekreftes i S4). |
| `skills/ios-visual-explore/SKILL.md` | Dokumenter iPad-støtte, `--orientation`, fullskjerm-only-begrensning; fjern iPad-Fase-2-deferral-noten. |
| `scripts/ios-visual-explore` | Argv-passthrough for `--orientation` (sannsynligvis uendret utover dokumentasjon). |

### Safe-area-utledningskontrakt
`cli.py` bygger safe-area slik (begge stier):
1. Kjør `executor._describe_all()` én gang i pre-flight.
2. Forsøk `derive_insets(elems, point_w, point_h)` → hvis den returnerer gyldige insets, bruk dem (`safe_area_source="derived"`).
3. Ellers `table_insets(device_class, orientation, point_w, point_h)` (`safe_area_source="table"`).
4. Begge gir samme `SafeArea`-form som `loop.run` allerede konsumerer — `loop`/`coords` ser ingen forskjell.

## 5. Testing

**Enhetstester (deterministisk, ingen sim):**
- `derive_insets` mot **spike-fangede** describe-all-fixtures: iPad portrett, iPad landskap, iPhone portrett, iPhone landskap. Asserterer korrekte insets per fixture.
- `table_insets` fallback-oppslag per device-klasse × orientering, inkl. ukjent-device-fallback.
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
- **R-iPad-3:** split-view-deteksjon er **best-effort** (S3): frame-bredde-heuristikk kan gi false negatives (app i split men vi tror fullskjerm). Restrisiko aksepteres for et ikke-destruktivt utforskingsverktøy; konservativ avbrudd foretrekkes over falsk fortsettelse.
- **R-iPad-4:** `spotlight-pill` ikke til stede på iPad (S2) → alternativ markør eller svekket oracle-claim, aldri shippet som fail-closed mens degradert (samme disiplin som Fase 1 R7).
- **R-iPad-5 (regresjon):** `cli.py`/`coords.py` deles med iPhone-stien → endring kan regresjonere Fase 1. Mitigering: behold `portrait`-default, hold `denormalize`/`loop`/`gemini` urørt, kjør iPhone-portrett regresjons-smoke før merge.

## 7. Faseplan-plassering

Dette er **Fase 2** i den opprinnelige fem-fase-planen (designets §11). Fase 3 (lagrede flyter) og Fase 4 (macOS/cliclick) er uberørt. Disiplinen er identisk med Fase 1: **spec (dette dok) → 2 lens-runder → writing-plans → SPIKE-gate → subagent-drevet impl med per-task review**.
