# Design: Visuell computer-use-utforsking for SwiftUI-apper (Tier 2)

- **Dato:** 2026-06-26
- **Status:** Godkjent design (revidert for iPadOS + pluggbar executor) — klar for implementasjonsplan
- **Tema:** Agentisk, skjermbilde-drevet visuell QA for SwiftUI-apper på iOS, iPadOS og macOS, som eskaleringsnivå over eksisterende accessibility-basert e2e.

## 1. Motivasjon

Repoet har allerede en accessibility-tre-basert e2e-mekanisme (XCUITest-scaffolds + `ios-simulator`/`XcodeBuildMCP`-primitiver). Den er rask, gratis og deterministisk, men leser UI-treet — den «ser» ikke skjermen og fanger derfor ikke visuelle feil (overlapp, avkutting, kontrast, justering, layout-brudd), og krever ofte accessibility-identifikatorer.

Vi vil ha et **mer avansert nivå som tar over når den faste mekanismen ikke lenger avslører bugs**: en agent som ser selve skjermbildet som et menneske, navigerer fra naturlig språk, og rapporterer hva som ser galt ut. Dette er **Tier 2** — det erstatter ikke Tier 1 (accessibility-e2e), det eskalerer fra den.

## 2. Mål og ikke-mål

### Mål
- Et autonomt CLI-script som driver en **fri visuell utforsking** av en SwiftUI-app fra et naturlig-språk-oppdrag, på **iOS-, iPadOS- og macOS**-mål.
- Produsere en **strukturert rapport** med visuelle funn + skjermbilder.
- Holde Claudes kontekst ren: skjermbilder går til Gemini, ikke gjennom hovedsamtalen.
- En tynn skill-wrapper som dokumenterer når/hvordan det brukes.

### Ikke-mål (fase 1)
- **iPadOS, lagrede flyter og macOS** — egne faser (se §11). Fase 1 dekker iPhone-simulator + fri utforsking.
- Erstatte accessibility-e2e eller XCUITest. Tier 1 består uendret.
- CI-integrasjon. Verktøyet er manuelt/lokalt (koster penger per kjøring).
- Full multi-touch/komplekse gestures (pinch, rotate, Stage Manager-drag) — se R4.

## 3. Arkitektur

Valgt tilnærming: **autonomt loop-script + tynn skill-wrapper** (alternativ A av tre vurderte). Begrunnelse: skjermbildene går til Gemini og ikke gjennom Claudes kontekst (avgjørende for en agent som tar mange skjermbilder), gjenbruker `gemini-media`-mønsteret, og gir én motor som dekker alle tre plattformer. Alternativ B (Claude orkestrerer via MCP) og C (full MCP-server) løser ikke kontekst-/kostnadsproblemet og ble forkastet.

**Pluggbar executor.** Motoren er plattform-agnostisk; *executoren* — det som tar skjermbilde og utfører handlingen — velges etter målets natur:

| Mål | Natur | Executor |
|---|---|---|
| iOS-simulator | touch | **idb** (`idb ui tap/swipe/text/button`) |
| iPadOS-simulator | touch | **idb** (samme) |
| macOS-desktop | cursor | **cliclick** (skjermbilde av vindu + skjermkoordinat-klikk) |

Touch-plattformene bruker idb fordi det injiserer touch-events i **simulatorens eget koordinatrom** — det rører aldri den fysiske skjermen. Det er både en riktigere touch-modell og vesentlig tryggere/enklere enn muse-emulering: det eliminerer en hel klasse fysisk-skjerm-pitfalls (utenfor-vindu-klikk, tastatur-fokus-kapring, stale vindusrekt, Retina/zoom-mapping) som bare gjelder cliclick/desktop. macOS *er* et cursor-miljø, så der er cliclick riktig.

### Loop (i scriptet, ikke i Claudes kontekst)
```
oppdrag (naturlig språk) + første skjermbilde
  → Gemini computer_use → function_call {action, x, y, intent}
  → denormaliser 0–1000 → executor-koordinatrom → valider → utfør (tap/swipe/type)
  → settling-delay → nytt skjermbilde → gjenta til ferdig / maks-steg
  → visuell kritiker-pass over dedupede skjermbilder
  → strukturert rapport (funn + skjermbilder)
```

## 4. Komponenter

| Komponent | Ansvar | Avhenger av |
|---|---|---|
| **Loop-motor** | Kjør turn-loopen, kall Gemini, dispatch handlinger, stopp-betingelser | Gemini SDK, action-adapter |
| **Action-adapter** | Map computer_use-handlinger → executor-primitiver (kanonisk schema) | executor-grensesnitt |
| **Executor-grensesnitt** | `screenshot()`, `tap()`, `swipe()`, `type()`, `coordinate_space()` — abstraherer plattform | (definisjon) |
| **idb-executor** (touch) | Skjermbilde + touch-injeksjon i sim mot device-UDID | `idb`, booted sim |
| **cliclick-executor** (cursor) | Skjermbilde av vindu + skjermkoordinat-klikk (macOS, fase 4) | `screencapture`, `cliclick`, vindus-deteksjon |
| **Koordinat-mapper** | 0–1000 → executor-koordinatrom; valider mot bounds | (ren funksjon, per executor) |
| **Visuell kritiker** | Vurder dedupede skjermbilder for visuelle problemer | Gemini vision-modell |
| **Rapport-bygger** | Sett sammen handlingslogg + funn + skjermbilder til Markdown | (ren funksjon) |
| **Skill-wrapper** | Dokumenter når/hvordan; kall script; presenter rapport | scriptet |

Hver komponent har én klar oppgave og kan testes uavhengig. Executor-grensesnittet gjør at idb og cliclick er utbyttbare bak samme motor; koordinat-mapper og rapport-bygger er rene funksjoner (deterministisk testbare).

## 5. Gemini computer_use — API-detaljer

- **Modell:** `gemini-3.5-flash` (Googles anbefalte computer-use-modell per juni 2026).
- **Tool-deklarasjon:** `{"type": "computer_use", "environment": "mobile", "enable_prompt_injection_detection": true}` for iOS/iPadOS; `"desktop"` for macOS-fasen.
- **API:** `client.interactions.create()`; turene kjedes via `previous_interaction_id`. Hvert svar fra et utført steg sendes tilbake som `function_result` med ny skjermbilde-`image`.
- **Handlinger:** `click`/`tap`, `type`, `scroll`, `press_key`, `drag_and_drop`, `wait`, m.fl. Argumenter inkluderer `x`, `y`, `intent`. **Action-adapter-kontrakt:** modellens handlingsrom er bredere enn executor-primitivene, så et adapter-lag mapper hver computer_use-handling til en executor-primitiv: `scroll` → retnings-`swipe` (scroll er **kjerne**-navigasjon på mobil, ikke edge case — må ikke returneres som `unsupported`), `press_key` → `idb ui button` der støttet, `wait` → bounded no-op, `drag_and_drop` → `swipe`/drag eller eksplisitt `unsupported` hvis idb ikke dekker det. Adapteren testes med innspilte action-fixtures.
- **Koordinater:** normalisert **0–1000**, ikke piksler. Denormaliseres mot skjermbildets dimensjon, deretter inn i executorens koordinatrom (§6).
- **Nøkkel:** `gemini-api-key-paid` fra Keychain (samme mønster som `gemini-media`; fjern arvet `GOOGLE_API_KEY`/`GEMINI_API_KEY` fra env så kun eksplisitt nøkkel gjelder).

> Risiko (R1): **hele API-formen over stammer fra en oppsummert dokumentasjons-henting, ikke fra kjørt SDK-kode.** Det gjelder `interactions.create`-vs-`models.generate_content`-valget, `function_result`-strukturen, kjedingen via `previous_interaction_id`, handlingsnavnene, OG environment-verdien. **Første implementasjonssteg er et minimalt spike-kall** som verifiserer faktisk request/response-form mot installert `google-genai`, før resten bygges. Alt nedenfor som avhenger av API-formen er betinget av denne verifiseringen.

## 6. Executorer

### 6a. idb (touch — iOS + iPadOS simulator) — primær for fase 1–3

idb injiserer touch-events direkte i simulatoren mot dens device-UDID, i **device-koordinatrom (points)** — uavhengig av vindusposisjon, fokus og skjermskala.

1. Ta skjermbilde av simulatoren (`xcrun simctl io <udid> screenshot` eller `idb`), som er rent app-innhold i device-piksler.
2. Modellen gir koordinat normalisert 0–1000 mot det skjermbildet.
3. Denormaliser 0–1000 → device-piksel → device-points (del på device-backing-scale, som er kjent fra device-typen — ingen vindus-zoom inne i bildet).
4. **Valider mot app-safe interaksjonsområde**, ikke bare det rå device-rektangelet (§7): en koordinat innenfor device-bounds kan likevel treffe status-bar/home-indicator eller trigge system-edge-gestures (Control Center, app-switcher, Notification Center). Reserver orientering-/device-bevisste edge-exclusion-soner; edge-gestures krever eksplisitt override. Helst utledes app-frame/safe-area i pre-flight (accessibility-spørring/XCTest-helper).
5. Utfør via `idb ui tap/swipe/text/button` mot UDID.

Dette krever ingen vindus-deteksjon, ingen skjerm-offset, ingen fysisk-skjerm-klikk. **`idb`-avhengighet:** `brew install facebook/fb/idb-companion` + `pip install fb-idb`; pre-flight resolver `idb`-stien eksplisitt (`command -v idb`) og verifiserer at companion er tilkoblet mål-UDID, ellers fail-closed med install/connect-kommando.

> Risiko (R2): to idb-antagelser verifiseres i spiken: (a) **idbs koordinatkonvensjon** for `ui tap` (points vs. pixels) — antatt points, men bekreftes empirisk mot en kjent treff-flate; (b) **device-backing-scale** utledes riktig per device-klasse (varierer: de fleste moderne iPhones @3x, enkelte @2x; iPad @2x — utled fra faktisk device, ikke en konstant). Enhetstestes per device-klasse. Multi-touch/komplekse gestures er begrenset i idb (se R4).

### 6b. cliclick (cursor — macOS desktop) — fase 4

macOS-appen er et ekte cursor-miljø, men cliclick klikker på den **fysiske** skjermen, så den arver fysisk-skjerm-pitfalls som idb slipper unna:

1. Finn mål-appvinduets **innholdsområde** (eksklusive macOS-tittellinje).
2. Skjermbilde av innholdsområdet.
3. Denormaliser 0–1000 → bilde-piksel → logiske punkter. **Skalafaktoren er ikke fast 2×** — utled dynamisk fra innholds-pikselstørrelse vs. vinduets logiske størrelse (Retina-backing-scale, ev. ikke-100%-zoom).
4. Legg til innholdsområdets skjerm-offset → absolutt skjermkoordinat.
5. **Bounds-reject** hvis utenfor innholdsområdet (§7).
6. **Vindusrekt re-leses hvert steg** (vinduet kan flyttes/resizes mellom steg → stale box → feil klikk som likevel passerer bounds). cliclick-sti resolveres i pre-flight.

> Risiko (R2, macOS): vindus-/skala-mapping er den skjøre delen her. Enhetstestes mot reelle zoom-nivåer.

### Felles: settling

Etter hver utført handling, **vent et fast kort settling-delay (~300 ms) før neste skjermbilde** — ikke en «to like skjermbilder»-deteksjon (skjør mot SwiftUI-transiente frames og ikke-innhold som status-bar-klokke). Settling er et **sub-budsjett inne i per-steg-timeouten** (§7): per-steg = Gemini-kall + handling + settling, samlet bounded — loopen venter aldri mer enn settling-cap per steg uansett om appen aldri stabiliserer (kontinuerlig spinner/video).

## 7. Sikkerhet og guardrails

### Felles (begge executorer)
- **Koordinat-validering (fail-closed):** koordinat utenfor gyldig mål-område → **avvises, logges og utføres ALDRI** (matet tilbake som `rejected`, §9). For idb er dette en device-bounds-sjekk; for cliclick er det bounds-reject mot vindus-innholdet (reject, **ikke** clamp — clamp ville maskert mapping-feil som gyldig handling).
- **Maks-steg:** default ~25, hard stopp mot runaway-loop som koster penger. Konfigurerbar.
- **Per-steg-budsjett:** Gemini-kall + handling + settling, samlet bounded; hindrer henging.
- **Pre-flight + launch-state-kontrakt:** verifiser booted sim/vindu + at executor-verktøyet (idb/cliclick) er resolvbart og tilkoblet. **Etabler kjent app-tilstand** for reproduserbarhet: relaunch mål-appen via `simctl`, sett orientering/appearance/tekststørrelse, håndter eller fail på system-permission-dialoger, loggfør device-UDID + bundle-id + state i rapporten.
- **App-i-forgrunn-invariant (per steg, fase-1-blokker):** mål-appen kan krasje eller miste forgrunnen (system-dialog, URL→Safari, permission-prompt). Før hvert steg, verifiser at mål-appen er i forgrunnen; mismatch → avbryt med `app_left_foreground`, bevar delvise skjermbilder. Dette er **hovedguarden mot runaway/feil-skjerm**, så den må ikke shippe degradert: **fase 1 er blokkert på en verifisert forgrunns-oracle.** Foretrukket mekanisme er en XCTest-probe på `XCUIApplication(bundleIdentifier:).state == .runningForeground` (`xcrun simctl` har ingen dokumentert «frontmost»-spørring). Klarer ikke spiken å etablere en pålitelig oracle, må kontrakten i designet svekkes eksplisitt — ikke hevdes som fail-closed.
- **Teardown (signal-trygg):** pre-flight muterer sim-state (relaunch, orientering, appearance, permission-dialoger). Killes scriptet midt i en kjøring (Ctrl-C, hard timeout, krasj), står simulatoren i ukjent tilstand som neste `relaunch` ikke nødvendigvis nullstiller (in-app-navigasjon, åpne system-dialoger, gitte permissions). Legg en teardown som kjører både på normal exit og signal (trap SIGINT/SIGTERM) — minimum dokumenter hvilke pre-flight-steg som er idempotente (relaunch) vs. ikke (permission-grants, in-app-state), slik at operatøren vet når manuell sim-reset trengs.
- **Prompt injection-deteksjon:** `enable_prompt_injection_detection: true`.
- **Ingen destruktiv intensjon:** oppdrags-prompten instruerer agenten til å utforske/observere, ikke utføre kjøp/sletting/sending. Lav risiko i en simulator uten ekte konto-tilgang.

### Kun cliclick/macOS (fase 4)
- **Tastatur-fokus-guard (best-effort):** `cliclick type` sender tastetrykk til det **OS-fokuserte vinduet** — uten koordinat. Bind til mål-vinduets identitet (vindu-id), aktiver og verifiser før hver tastatur-handling; match feiler → avbryt. **Ærlig forbehold:** dette er best-effort, ikke ekte fail-closed (TOCTOU-vindu mellom verifisering og `type` der fokus kan stjeles). Restrisiko aksepteres (R5).
- idb/sim-executoren har **ikke** denne risikoen: `idb ui text` går til mål-UDID direkte, ikke til det OS-fokuserte vinduet.

## 8. Rapport-format (to interne faser)

Computer-use-modellen er optimalisert for å **navigere**, ikke **kritisere design**. Derfor skilles fasene:

- **Fase A — utforsk:** loop-motoren driver app-en. **Dedup gjelder kritiker-*input*, ikke evidens-*retensjon*.** Til evidens beholdes alltid: skjermbilder for `rejected`/`failed`/`unsupported`/`app_left_foreground`-steg, første og siste skjerm, og en lav-rate sample — slik at en transient error-overlay eller modal som vises og forsvinner ikke går tapt. Til kritiker dedupes nesten-like skjermbilder (perceptuell-hash-delta) så en fastlåst modell ikke sender 25 like bilder. Hvert lagrede skjermbilde bærer `produced_by_steps: [12,13,14]` (hvilke steg som ledet til den skjermtilstanden), så et kritiker-funn på «skjermbilde #7» kan spores tilbake til handlingene — de to nummereringsrommene (steg vs. skjermbilde) må eksplisitt lenkes.
- **Fase B — visuell kritiker:** de **dedupede** skjermbildene sendes til en Gemini vision-modell med en kritiker-prompt («finn visuelle problemer: overlapp, avkutting, kontrast, justering, layout-brudd, off-screen-elementer»). O(N) vision-kall uavhengig av steg-antall, så input cappes og kjøres evt. i chunks. **Kostnadsmodell** som loggføres: `steg × (computer_use + opplasting) + unike_skjermbilder × vision-kall`.

**Output:** en Markdown-rapport + skjermbilde-mappe: oppdrag og miljø (plattform + device-UDID); handlingslogg (steg-nr, action, intent, validert/avvist koordinat); kritiker-funn rangert med skjermbilde-referanse; sluttstatus (`fullført`/`maks-steg-nådd`/`feilet`/`app_left_foreground`).

**Skill-wrapper-grense (bevarer kontekst-renheten):** kjerne-rasjonale (§2/§3) er at skjermbilder ikke går gjennom Claudes kontekst. Derfor: rapporten *på disk* har full Markdown + skjermbilde-filer, men det skill-wrapperen **returnerer til Claude er en tekst-only oppsummering** (funn-tekst + filstier, **ingen inline-bilder**). Claude kan valgfritt åpne enkelt-skjermbilder ved behov, men default-stien holder dem ute av konteksten. Dette er en kontrakt, ikke en implementasjonsdetalj.

## 9. Feilhåndtering

**Action-result-protokoll (kritisk for loop-integritet):** computer_use er en kjedet interaksjon — *hvert* `function_call` må besvares med et `function_result` i neste tur, også når handlingen feilet. Å «logge og hoppe over» lokalt desynkroniserer interaction-staten (modellen vet ikke at handlingen feilet og gjentar den). Send **alltid** et normalisert resultat tilbake — `success` / `rejected` (bounds/fokus) / `unsupported` (ukjent handling) / `timeout` — med årsak + ferskt skjermbilde, før neste steg.

**Ikke-atomisk eksekusjon (per-steg-journal):** handling-eksekusjon (idb/cliclick) og result-innsending (nettverk) er *ikke* atomisk. For å aldri duplisere et tap/tekst-innslag ved retry, føres en **per-steg-journal** med tilstand `planned → validated → executed → result_sent` + action-id + skjermbilde-hash. Retry-logikk inspiserer journalen og **re-eksekverer aldri et `executed`-steg** — den sender kun resultatet på nytt.

**Recovery ved tapt interaction-kjede:** hvis `function_result`-opplasting er uttømt for retries, **start IKKE en naiv frisk interaction fra siste skjermbilde** — en frisk interaction har null minne om hva som er utforsket, og re-utforsker fra scratch (kan tømme maks-steg på repetisjon og gi en *dårligere* rapport enn et rent stopp). I fase 1 behandles tapt kjede som **terminal**: stopp med delvis rapport (enklest og ærligst om hva som gikk tapt). En kontekst-seedet videreføring («allerede utforsket: …, ikke gjenta») er en mulig senere optimalisering, ikke fase-1-scope.

Øvrige tilfeller:
- Ingen booted sim / vindu ikke funnet / executor-verktøy ikke resolvbart/tilkoblet → avbryt i pre-flight med handlingsbar melding.
- Gemini-kall feiler (kvote/nettverk) → retry med backoff; etter N forsøk, avslutt med delvis rapport.
- Mål-app forlot forgrunnen → avbryt med `app_left_foreground` (§7), bevar delvise skjermbilder.
- Koordinat utenfor gyldig område → reject (§7), matet tilbake som `rejected`.
- Executor-feil (idb/cliclick) → logg, returner `timeout`/feil-resultat, tell mot per-steg-budsjett.

## 10. Testing

Loopen er ikke-deterministisk (LLM), så **infrastrukturen testes deterministisk** og **agenten kjøres som smoke-test**:
- **Enhetstester:** koordinat-mapper per executor (idb: 0–1000 → device-points per device-klasse; cliclick: 0–1000 → bilde-piksel → dynamisk skala → offset → bounds-reject, inkl. ikke-100%-zoom og utenfor-bounds), executor-grensesnitt-kontrakt, rapport-bygger.
- **`--dry-run` (single-turn planning-probe):** kan *ikke* være «kjør hele loopen uten å utføre» — den kjedede interaksjonen krever et nytt skjermbilde *etter* hver handling for å gå videre, så uten utførelse staller eller repeterer modellen. Definert som: send initial-skjermbilde + oppdrag, få **ett** `function_call`, logg den planlagte (mappede) handlingen, stopp. For å teste hele loop-rørleggingen brukes i stedet en **mock-executor** som returnerer pre-seedede skjermbilder fra fixtures.
- **Smoke-test:** kjør mot en enkel SwiftUI-app i iPhone-simulatoren; verifiser rapport + skjermbilder. Gjenta for iPad i fase 2.

## 11. Faser

1. **Fase 1 (denne specen):** iPhone-simulator, fri visuell utforsking, **idb-executor**, to-fase-rapport, skill-wrapper, executor-grensesnitt.
2. **Fase 2 — iPadOS:** gjenbruk idb-executor; legg til iPad-form-faktor + device-klasse-mapping (@2x) + iPad-spesifikke navigasjons-/gesture-hensyn innenfor idbs evner.
3. **Fase 3 — lagrede levende flyter (modus B):** samme motor, men med en lagret naturlig-språk-flyt-beskrivelse i stedet for fri utforsking; kjøres gjentatte ganger som «levende» regresjon. Dekker både iPhone og iPad.
4. **Fase 4 — macOS-desktop:** legg til **cliclick-executor** (cursor-miljø, fysisk-skjerm-guardene i §6b/§7). Siste fase.
5. **Mulig senere:** `e2e-route` ruter til dette som sitt Tier-2-mål.

## 12. Åpne risikoer (sammendrag)

- **R1:** Hele computer_use-API-formen er uverifisert (se §5) — adresseres av et tidlig spike-kall før resten bygges.
- **R2:** Koordinat-mapping er den skjøre delen. For idb/sim: device-backing-scale per device-klasse (enklere — ingen vindu/zoom). For cliclick/macOS: vindus-deteksjon + dynamisk skala + per-steg rekt-relesing. Enhetstestes.
- **R3:** ikke-determinisme i visuell kritiker — kan gi varierende funn mellom kjøringer; akseptabelt for et utforskende Tier-2-verktøy, ikke et regresjonsgate.
- **R4 (premiss-risiko, høyest verdi å avklare tidlig):** computer_use-modellene er trent på desktop-cursor-miljøer, men driver her en touch-enhet. idb gir *ekte* touch-injeksjon (bedre enn muse-emulering), men (a) gir modellen fornuftige touch-handlinger for iPhone/iPad i det hele tatt, og (b) dekker idb dem? `tap`/`swipe`/`text`/`button` er solide; **multi-touch og komplekse iPad-gestures (pinch, rotate, Stage Manager-drag) er ikke garantert** og er et ikke-mål i fase 1–2. **Verifiser i samme tidlige spike som R1.**
- **R5 (akseptert restrisiko, kun macOS/cliclick):** tastatur-fokus-guarden er best-effort, ikke ekte fail-closed (TOCTOU-vindu, §7). Gjelder ikke idb/sim. Akseptert for et ikke-destruktivt utforskingsverktøy.
- **R6 (avhengighet):** `idb`/`idb-companion` er en ekstra, til tider vedlikeholdstung avhengighet. Prisen aksepteres fordi idb fjerner hele den fysisk-skjerm-pitfall-klassen og gir ekte touch. Pre-flight feiler closed med install/connect-veiledning hvis idb mangler.
- **R7 (fase-1-blokker):** forgrunns-invarianten (§7) er hovedguarden mot runaway/feil-skjerm, men deteksjonsmekanismen er uverifisert (`simctl` har ingen «frontmost»-spørring). **Fase 1 er blokkert på at spiken etablerer en pålitelig oracle** (foretrukket: XCTest `XCUIApplication.state`-probe). Lykkes ikke det, må guard-claimet svekkes eksplisitt i designet — ikke shippes som fail-closed mens det er degradert.
