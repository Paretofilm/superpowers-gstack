# Design: Visuell computer-use-utforsking for SwiftUI-apper (Tier 2)

- **Dato:** 2026-06-26
- **Status:** Godkjent design — klar for implementasjonsplan
- **Tema:** Agentisk, skjermbilde-drevet visuell QA for SwiftUI-apper, som eskaleringsnivå over eksisterende accessibility-basert e2e.

## 1. Motivasjon

Repoet har allerede en accessibility-tre-basert e2e-mekanisme (XCUITest-scaffolds + `ios-simulator`/`XcodeBuildMCP`-primitiver). Den er rask, gratis og deterministisk, men leser UI-treet — den «ser» ikke skjermen og fanger derfor ikke visuelle feil (overlapp, avkutting, kontrast, justering, layout-brudd), og krever ofte accessibility-identifikatorer.

Vi vil ha et **mer avansert nivå som tar over når den faste mekanismen ikke lenger avslører bugs**: en agent som ser selve skjermbildet som et menneske, navigerer fra naturlig språk, og rapporterer hva som ser galt ut. Dette er **Tier 2** — det erstatter ikke Tier 1 (accessibility-e2e), det eskalerer fra den.

## 2. Mål og ikke-mål

### Mål (fase 1)
- Et autonomt CLI-script som driver en **fri visuell utforsking** av en SwiftUI-app i **iOS-simulatoren** fra et naturlig-språk-oppdrag.
- Produsere en **strukturert rapport** med visuelle funn + skjermbilder.
- Holde Claudes kontekst ren: skjermbilder går til Gemini, ikke gjennom hovedsamtalen.
- En tynn skill-wrapper som dokumenterer når/hvordan det brukes.

### Ikke-mål (fase 1)
- **Lagrede levende flyter** (modus B) — kommer som et lag oppå samme motor senere.
- **macOS-desktop** (fase 2) — gjenbruker motor + executor; bare vindus-deteksjon skifter.
- Erstatte accessibility-e2e eller XCUITest. Tier 1 består uendret.
- CI-integrasjon. Fase 1 er manuell/lokal (koster penger per kjøring).

## 3. Arkitektur

Valgt tilnærming: **autonomt loop-script + tynn skill-wrapper** (alternativ A av tre vurderte). Begrunnelse: skjermbildene går til Gemini og ikke gjennom Claudes kontekst (avgjørende for en agent som tar mange skjermbilder), gjenbruker `gemini-media`-mønsteret, og gir en motor som kobles rett på macOS senere. Alternativ B (Claude orkestrerer via MCP) og C (full MCP-server) løser ikke kontekst-/kostnadsproblemet og ble forkastet.

### Loop (i scriptet, ikke i Claudes kontekst)
```
oppdrag (naturlig språk) + første skjermbilde
  → Gemini computer_use → function_call {action, x, y, intent}
  → denormaliser 0–1000 → vindus-piksler → bounds-reject hvis utenfor → utfør (tap/type/swipe)
  → nytt skjermbilde → gjenta til ferdig / maks-steg
  → visuell kritiker-pass over innsamlede skjermbilder
  → strukturert rapport (funn + skjermbilder)
```

## 4. Komponenter

| Komponent | Ansvar | Avhenger av |
|---|---|---|
| **Loop-motor** | Kjør turn-loopen, kall Gemini, dispatch handlinger, stopp-betingelser | Gemini SDK, executor |
| **Executor (iOS)** | Skjermbilde av Simulator-vindu + utfør tap/type/swipe via cliclick | `screencapture`, `cliclick`, vindus-deteksjon |
| **Koordinat-mapper** | 0–1000 → bilde-piksel → dynamisk skala → skjerm-offset → bounds-reject hvis utenfor | (ren funksjon) |
| **Visuell kritiker** | Vurder innsamlede skjermbilder for visuelle problemer | Gemini vision-modell |
| **Rapport-bygger** | Sett sammen handlingslogg + funn + skjermbilder til Markdown | (ren funksjon) |
| **Skill-wrapper** | Dokumenter når/hvordan; kall script; presenter rapport | scriptet |

Hver komponent har én klar oppgave og kan testes uavhengig. Koordinat-mapper og rapport-bygger er rene funksjoner (deterministisk testbare).

## 5. Gemini computer_use — API-detaljer

- **Modell:** `gemini-3.5-flash` (Googles anbefalte computer-use-modell per juni 2026).
- **Tool-deklarasjon:** `{"type": "computer_use", "environment": "mobile", "enable_prompt_injection_detection": true}`.
- **API:** `client.interactions.create()`; turene kjedes via `previous_interaction_id`. Hvert svar fra et utført steg sendes tilbake som `function_result` med ny skjermbilde-`image`.
- **Handlinger:** `click`, `type`, `scroll`, `press_key`, `drag_and_drop`, `wait`, m.fl. Argumenter inkluderer `x`, `y`, `intent`.
- **Koordinater:** normalisert **0–1000**, ikke piksler. Må denormaliseres mot faktisk skjermbilde-dimensjon.
- **Nøkkel:** `gemini-api-key-paid` fra Keychain (samme mønster som `gemini-media`; fjern arvet `GOOGLE_API_KEY`/`GEMINI_API_KEY` fra env så kun eksplisitt nøkkel gjelder).

> Risiko (R1): **hele API-formen over stammer fra en oppsummert dokumentasjons-henting, ikke fra kjørt SDK-kode.** Det gjelder `interactions.create`-vs-`models.generate_content`-valget, `function_result`-strukturen, kjedingen via `previous_interaction_id`, handlingsnavnene, OG environment-verdien (`"mobile"` antatt — kan være `"desktop"` for en simulator på macOS). **Første implementasjonssteg er et minimalt spike-kall** som verifiserer faktisk request/response-form mot installert `google-genai`, før resten bygges. Alt nedenfor som avhenger av API-formen er betinget av denne verifiseringen.

## 6. Executor: cliclick mot Simulator-vinduet

Valgt over `idb` for å få **én enhetlig executor for både iOS-sim og macOS-desktop** (skjermbilde av vindu + cliclick på skjermkoordinater), uten den vedlikeholdstunge `idb-companion`-avhengigheten. `cliclick 5.1` er allerede installert.

### Skjermbilde og koordinat-mapping
1. Finn Simulator-vinduets **innholdsområde** på skjermen (posisjon + størrelse), eksklusive macOS-vindus-chrome (tittellinje). Skjermbildet og koordinatrommet må dekke kun innholdet — ellers gir modellen koordinater i tittellinjen som mapper feil.
2. Ta skjermbilde av innholdsområdet.
3. Modellen gir koordinat normalisert 0–1000 mot det skjermbildet.
4. Denormaliser → bilde-piksel, deretter konverter til logiske skjermpunkter (`cliclick` opererer i logiske punkter). **Skalafaktoren er ikke fast 2×** — den er produktet av Retina-backing-scale OG Simulators egen vindus-zoom (Window → Physical/Point-Accurate/Pixel-Accurate, eller 50/75/100%). Utled skalaen **dynamisk** fra forholdet mellom faktisk innholds-pikselstørrelse og vinduets logiske størrelse — ikke anta en konstant.
5. Legg til innholdsområdets skjerm-offset → absolutt skjermkoordinat.
6. **Valider mot innholdsområdets bounding box — utenfor = avvis (bounds-reject), ikke clamp** (se §7).

Etter hver utført handling, **vent et fast kort settling-delay (~300 ms) før neste skjermbilde tas** — ikke en «to påfølgende skjermbilder er like»-deteksjon. SwiftUI-animasjoner produserer mange transiente frames, og to `screencapture`-kall kan tilfeldigvis treffe identiske mellom-frames (eller bytes-skille på ikke-innhold som status-bar-klokke/markør) og falskt erklære stabilitet. Et fast delay er enklere og riktigere for et manuelt Tier-2-verktøy. Settling er et **sub-budsjett inne i per-steg-timeouten** (§7): per-steg = Gemini-kall + handling + settling, samlet bounded — loopen venter aldri mer enn settling-cap per steg uansett om appen aldri stabiliserer (kontinuerlig spinner/video).

**Vindusrekt re-leses HVERT steg, ikke bare i pre-flight.** Loopen tar mange skjermbilder; flyttes/resizes Simulator-vinduet mellom steg (bruker drar det, Mission Control, Spaces), blir en cachet bounding box stale — og hvert klikk lander feil *mens det fortsatt passerer bounds-sjekken*. Re-les innholdsrekt før hver mapping; ved rekt-endring re-map mot frisk rekt (eller avbryt). Samtidig kjøring av noe som flytter vindusgeometri er ikke støttet.

**cliclick-stien resolveres eksplisitt i pre-flight** (`command -v cliclick` + versjonssjekk), ikke antatt på PATH — et script spawnet med minimal PATH (slik en agent ofte gjør) ser ikke nødvendigvis Homebrew-cliclick. Mangler den → fail-closed med install-kommando.

> Risiko (R2): vindus-/innholds-deteksjon og dynamisk skala-utledning er den skjøre delen, ikke en fast Retina-konstant. Krever synlig Simulator-vindu på kjent posisjon. Pre-flight verifiserer vindu + leser faktisk skala; mapping enhetstestes mot reelle zoom-nivåer (inkl. ikke-100%).

## 7. Sikkerhet og guardrails

- **Bounds-reject (fail-closed, kritisk):** cliclick klikker på den **fysiske** skjermen. Bommer koordinat-mappingen, kan agenten klikke utenfor simulatorvinduet på den ekte desktopen. Derfor: hvert klikk valideres mot innholdsområdets bounding box, og koordinat **utenfor → avvises, logges og utføres ALDRI** (matet tilbake til modellen som `rejected`, se §9). Merk: dette er **reject, ikke clamp** — en clamp ville flyttet et ugyldig klikk til nærmeste kant *inni* appen, truffet feil element, og maskert mapping-feil som en gyldig handling. Kun sub-piksel avrundingsdrift justeres etter at validering har passert.
- **Frontmost-/fokus-guard for tastatur (fail-closed, kritisk):** bounds-reject beskytter kun *klikk*-koordinater. `cliclick` sin `type`/`press_key` sender tastetrykk til det **OS-fokuserte vinduet** — uten koordinat. Er ikke det riktige simulatorvinduet fokusert, går teksten til en vilkårlig app (i verste fall terminalen som kjører Claude, eller en editor). Det holder **ikke** å sjekke at «Simulator er frontmost» — med flere Simulator-vinduer eller flere bootede enheter kan feil sim være fremst. Derfor: pre-flight fanger **mål-vinduets identitet** (vindu-id + device-UDID + bounding box), og **før hver tastatur-handling aktiveres nettopp det vinduet, og det verifiseres at det aktive vinduet matcher den lagrede identiteten**. Match feiler → **avbryt handlingen, ikke send tastetrykk** (matet tilbake som `rejected`). Samme vindu-aktivering gjøres før klikk; for tastatur er identitets-matchen sikkerhetskritisk. **Ærlig forbehold:** dette er **best-effort, ikke ekte fail-closed** — det er et TOCTOU-vindu mellom verifisering og `cliclick type` der fokus kan stjeles (system-varsel, annen app). Vi minimerer det (verifiser umiddelbart før, send raskt), men kan ikke garantere det bort. Restrisikoen aksepteres for et utforskende verktøy med ikke-destruktiv intensjon.
- **Begrensning av bounds-reject:** reject hindrer klikk *utenfor* vinduet, men garanterer ikke *korrekt* targeting *innenfor* — en systematisk skjev mapping (f.eks. feil utledet zoom) kan treffe feil element uten å bryte bounds. Det er sikkerhet, ikke korrekthet; korrekthet hviler på riktig skala-utledning (§6) + `--dry-run`-verifisering.
- **Maks-steg:** default ~25, hard stopp mot runaway-loop som koster penger. Konfigurerbar via flagg.
- **Per-steg timeout:** hindrer henging på et enkelt API-kall eller cliclick-kommando.
- **Pre-flight-sjekk + launch-state-kontrakt:** verifiser booted simulator + at Simulator-vinduet er funnet + at `cliclick` er resolvbar. **Etabler også en kjent app-tilstand** for reproduserbare rapporter: relaunch mål-appen via `simctl` (evt. erase/uninstall for ren kjøring), sett orientering/appearance/tekststørrelse, håndter eller fail på system-permission-dialoger, og loggfør device-UDID + bundle-id + app/state i rapporten. Avbryt med tydelig melding ved feil.
- **App-i-forgrunn-invariant (per steg):** mål-appen kan krasje midt i loopen, eller forgrunnen kan tapes (system-dialog, URL åpner Safari, permission-prompt). Da ville loopen fortsette å skjermbilde irrelevant UI og klikke koordinater mot feil skjerm. Derfor: før hvert steg, verifiser at simulatorens frontmost-app (via `xcrun simctl`) fortsatt matcher target bundle-id. Mismatch → avbryt med status `app_left_foreground`, bevar delvise skjermbilder.
- **Prompt injection-deteksjon:** `enable_prompt_injection_detection: true` på tool-en.
- **Ingen destruktiv intensjon:** oppdrags-prompten instruerer agenten til å utforske/observere, ikke utføre kjøp/sletting/sending. Risikoen er uansett lav i en simulator uten ekte konto-tilgang.

## 8. Rapport-format (to interne faser)

Computer-use-modellen er optimalisert for å **navigere**, ikke **kritisere design**. Derfor skilles fasene:

- **Fase A — utforsk:** loop-motoren driver app-en og lagrer skjermbilder, men kun ved **faktisk skjerm-endring** (perceptuell-hash-delta over terskel mot forrige lagrede) — ikke ett per steg. Uten denne deduppen gir en modell som sitter fast og tapper samme sted 25 nesten-identiske skjermbilder som forsøpler både kritiker og rapport.
- **Fase B — visuell kritiker:** de **dedupede** skjermbildene sendes til en Gemini vision-modell med en kritiker-prompt («finn visuelle problemer: overlapp, avkutting, kontrast, justering, layout-brudd, off-screen-elementer»). Kritiker-passet er O(N) vision-kall uavhengig av steg-antall, så input cappes og kjøres evt. i chunks med en sluttsammenstilling. **Kostnadsmodell** som loggføres: `steg × (computer_use + opplasting) + unike_skjermbilder × vision-kall`.

**Output:** en Markdown-rapport + skjermbilde-mappe som inneholder:
- Oppdrag og miljø
- Handlingslogg: steg-nr, action, intent, (validert/avvist) koordinat
- Kritiker-funn, rangert etter alvorlighet, med referanse til skjermbilde
- Sluttstatus: `fullført` / `maks-steg-nådd` / `feilet` (+ årsak)

## 9. Feilhåndtering

**Action-result-protokoll (kritisk for loop-integritet):** computer_use er en kjedet interaksjon — *hvert* `function_call` fra modellen må besvares med et `function_result` i neste tur, også når handlingen feilet. Å «logge og hoppe over» lokalt desynkroniserer interaction-staten: modellen vet ikke at handlingen feilet og gjentar den. Derfor sendes **alltid** et normalisert resultat tilbake — `success` / `rejected` (bounds/fokus) / `unsupported` (ukjent handling) / `timeout` — med årsak + ferskt skjermbilde, før neste steg hentes.

**Ikke-atomisk eksekusjon (idempotens):** handling-eksekusjon (cliclick) og result-innsending (nettverk) er *ikke* atomisk. Feiler `function_result`-opplastingen *etter* at handlingen alt er utført på simulatoren, må handlingen **ikke** re-eksekveres ved retry — send i stedet et syntetisk «utført, resultat utilgjengelig»-resultat, eller start en frisk interaction fra siste kjente skjermbilde. Spec'en slår eksplisitt fast at de to ikke er atomiske.

Øvrige tilfeller:
- Ingen booted sim / vindu ikke funnet / cliclick ikke resolvbar → avbryt i pre-flight med handlingsbar melding.
- Gemini-kall feiler (kvote/nettverk) → retry med backoff; etter N forsøk, avslutt med delvis rapport.
- Mål-app forlot forgrunnen (krasj/dialog/Safari) → avbryt med `app_left_foreground` (se §7), bevar delvise skjermbilder.
- Koordinat utenfor innholdsrekt → bounds-reject (§7), matet tilbake som `rejected`.
- cliclick-feil → logg, returner `timeout`/feil-resultat, tell mot per-steg-budsjett.

## 10. Testing

Loopen er ikke-deterministisk (LLM), så **infrastrukturen testes deterministisk** og **agenten kjøres som smoke-test**:
- **Enhetstester:** koordinat-mapper (0–1000 → bilde-piksel → dynamisk skala → offset → bounds-reject, inkl. utenfor-vindu-tilfeller og ikke-100%-zoom), vindus-deteksjon-parsing, rapport-bygger.
- **`--dry-run`:** kjør loopen og logg planlagte handlinger uten å utføre cliclick.
- **Smoke-test:** kjør mot en enkel SwiftUI-app i simulatoren; verifiser at rapport + skjermbilder produseres.

## 11. Faser

1. **Fase 1 (denne specen):** iOS-sim, fri visuell utforsking, cliclick-executor, to-fase-rapport, skill-wrapper.
2. **Fase 2 — lagrede levende flyter (modus B):** samme motor, men med en lagret naturlig-språk-flyt-beskrivelse i stedet for fri utforsking; kan kjøres gjentatte ganger som «levende» regresjon.
3. **Fase 3 — macOS-desktop:** gjenbruk motor + executor; bytt vindus-deteksjon fra Simulator til mål-appens vindu.
4. **Mulig senere:** `e2e-route` ruter til dette som sitt Tier-2-mål.

## 12. Åpne risikoer (sammendrag)

- **R1:** Hele computer_use-API-formen er uverifisert (se §5) — adresseres av et tidlig spike-kall før resten bygges.
- **R2:** vindus-/innholds-deteksjon + dynamisk skala-utledning (ikke fast Retina-konstant) er den skjøre delen — pre-flight + per-steg rekt-relesing + enhetstester demper.
- **R3:** ikke-determinisme i visuell kritiker — kan gi varierende funn mellom kjøringer; akseptabelt for et utforskende Tier-2-verktøy, ikke et regresjonsgate.
- **R4 (premiss-risiko, høyest verdi å avklare tidlig):** computer_use-modellene er trent på **desktop-cursor-miljøer**. Vi driver en **simulert touch-enhet** via skjermkoordinat-*muse*-klikk. Touch-semantikk skiller seg fra cursor: ingen hover-tilstander, ingen multi-touch, annen scroll/gesture-oppførsel. Det kan gi subtilt feil interaksjoner og undergrave executor-valget for *mobil* (fase 3 macOS-desktop er upåvirket, siden det faktisk *er* et cursor-miljø). **Verifiser i samme tidlige spike som R1:** klarer modellen å drive enkle iOS-flyter (tap, scroll, tekstfelt) korrekt via muse-klikk i simulatoren? Hvis ikke, revurder mobil-executoren (f.eks. `idb`-gesture-injeksjon i stedet for cliclick) før videre bygging.
- **R5 (akseptert restrisiko):** tastatur-fokus-guarden er best-effort, ikke ekte fail-closed (TOCTOU-vindu, §7). Akseptert for et ikke-destruktivt utforskingsverktøy.
