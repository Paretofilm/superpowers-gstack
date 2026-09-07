---
type: design-doc
title: spec-drift — frittstående spec-mot-kode-audit — forslag
status: APPROVED
decision: fase 1 godkjent 2026-09-07 for planlegging på feat/spec-drift — fase 2-3 fortsatt til diskusjon
date: 2026-09-07
author: vurdering av Sorbh/interview-me, Oslo
related:
  - IDEAS.md (forslags-entry)
  - skills/setup-routing/blocks/plan-fidelity.md
  - skills/office-hours-track-aware/SKILL.md (wrapper-presedens rundt en gstack-skill)
  - skills/pitfall-verification/SKILL.md
  - ~/.claude/skills/gstack/ship/sections/plan-completion.md (gstack, Step 8)
  - ~/.claude/skills/gstack/ship/SKILL.md (gstack, Step 8.2)
touches_skills: []
---

# Spec-drift-deteksjon i superpowers-gstack — forslag

*Skrevet 2026-09-07. Utløst av en vurdering av `Sorbh/interview-me`, hvis `--verify`-flagg
ved første øyekast så ut til å dekke et hull hos oss. Undersøkelsen viste at hullet er
mindre enn antatt: tre lag mot spec-drift finnes allerede. Dokumentet foreslår derfor ikke
en ny skill, men en tynn wrapper som kjører `/ship` sin eksisterende audit-seksjon
frittstående — uten å røre upstream.*

## Status

**Fase 1 godkjent 2026-09-07** for planlegging på `feat/spec-drift`. Ingen fil under
`skills/` er rørt ennå. Fase 2 og 3 er påbygg som vurderes hver for seg etter at fase 1 har
vært i drift.

## Kontekst

`interview-me` er en tredjeparts-skill som intervjuer utvikleren som en senior arkitekt før
koding, og som i tillegg tilbyr `/interview-me --verify <spec>`: en protokoll som
sammenligner en spec mot faktisk kode og rapporterer avvik.

Intervju-delen er klart overflødig hos oss — `superpowers:brainstorming` eier den rollen med
en hardere godkjenningsport, og `/office-hours`, plan-review-familien og
`pitfall-verification` dekker «utfordre antagelsene» med flere modellhus enn én skill kan.
Å installere den ville dessuten gitt trigger-kollisjon: to skills som begge annonserer at de
skal kjøre før implementasjon starter.

`--verify` så derimot ut som et ekte hull. Dette dokumentet er resultatet av å undersøke om
det faktisk er det.

## Vurdering: hva som allerede finnes

Det finnes fem tiltak mot spec- og plandrift i dag, fordelt på tre lag:

| Lag | Hvor | Hva det gjør | Når |
|---|---|---|---|
| **Preventivt** | `skills/setup-routing/blocks/plan-fidelity.md` (`gstack-plan-fidelity-v2`) | Regelblokk injisert i alle prosjekters CLAUDE.md av `adapt` og `setup-routing`: «fiks planen i **samme commit** som avviket». Navngir tre måter en plan blir stale, og hvordan man skriver rettelsen. | Kontinuerlig, under implementasjon |
| **Deteksjon** | `/ship` Step 8 → `~/.claude/skills/gstack/ship/sections/plan-completion.md` | Full audit, dispatchet som subagent med egen kontekst | Ved merge |
| **Scope** | `/ship` Step 8.2 | Scope Drift Detection: uspesifisert kodevekst mot «stated intent» fra commits, PR-body og `TODOS.md`. Informasjonell, ikke-blokkerende. | Ved merge |
| **Punktvis** | `skills/pitfall-verification/SKILL.md:108` | Én pitfall-linje: «Signature drift: spec references functions/fields that do not exist in the code» | Ved artefakt-review |
| **Dokumentasjon** | `/document-release` | Arkitektur-diagram-drift: entitetsnavn i ASCII/Mermaid kryssjekkes mot diffen. Advisory, redigerer aldri diagrammet selv. | Ved release |

### `/ship` Step 8 er kraftigere enn `interview-me` på én akse

Dette er hovedfunnet. `plan-completion.md` gjør allerede alt kjernearbeidet en drift-sjekk
krever:

- **Plan-discovery** med tre strategier (samtalekontekst, innholdssøk mot gren- og repo-navn,
  ferskhet), pluss relevansvalidering av treffet.
- **Claim-ekstraksjon** fra planprosa — avkryssingsbokser, nummererte steg, imperativer,
  filnivå-spesifikasjoner, testkrav, datamodellendringer — med eksplisitt ignoreringsliste
  (kontekst-seksjoner, åpne spørsmål, bevisst utsatt arbeid) og tak på 50 punkter.
- **Verifikasjonsmodus** før dom: `DIFF-VERIFIABLE`, `CROSS-REPO`, `EXTERNAL-STATE`,
  `CONTENT-SHAPE`, med egen dispatch per modus og en «path concreteness»-regel som nekter
  `UNVERIFIABLE` når punktet navngir en konkret filsti.
- **Verdikter** `DONE` / `PARTIAL` / `NOT DONE` / `CHANGED` / `UNVERIFIABLE`, med
  ærlighetsregel («kode som *håndterer* en leveranse er ikke leveransen»).
- **Port med per-punkt-bekreftelse** — eksplisitt forbud mot å blankobekrefte alle
  `UNVERIFIABLE`-punkter i én dialog, fordi det er den observerte feilformen.
- **Maskinlesbar kontrakt** (JSON på siste linje) og **fail-closed** fallback: hvis auditen
  ikke kan kjøre, er standardvalget å stoppe, ikke å slippe gjennom.

`interview-me` sin protokoll har ingen tilsvarende verifikasjonsmodus-akse. Den antar at
diffen kan bevise eller motbevise enhver påstand, og har dermed ingen måte å skille «dette
er ikke gjort» fra «dette er en Cloudflare-innstilling som git aldri kan se». Å portere
VERIFY.md ville derfor vært et tilbakeskritt på den aksen og en duplisering på resten.

## Hull som overlever undersøkelsen

Fem hull står igjen. Tre av dem er skrevet ned i repoet fra før — av `plan-fidelity.md`
selv, i seksjonen «Why this is not the ship gate's job».

1. **Ingen frittstående invokasjon.** Auditen finnes kun som Step 8 inne i ship-pipelinen.
   Spørsmålet «stemmer denne specen fortsatt med koden?» kan ikke stilles uten å kjøre hele
   `/ship` med sine tjue steg.

2. **Funn skrives aldri tilbake i specen.** `plan-fidelity.md`: `/ship` «writes its findings
   to the PR body rather than back into the plan». PR-body er et arkiv ingen leser igjen;
   specen er det neste agent leser som instruks.

3. **Kjører ikke på grener som ikke shippes.** `plan-fidelity.md`: «never runs at all on a
   branch that is not shipped». Utforskende arbeid, spikes og forlatte grener får aldri
   auditen — og det er nettopp der avvik fra specen er størst.

4. **Ingen hukommelse mellom kjøringer.** Bevisst akseptert drift har ingen fingeravtrykk og
   re-rapporteres ved hver kjøring. Det trener brukeren til å klikke forbi porten, som
   undergraver den samme per-punkt-bekreftelsen `plan-completion.md` innførte for å hindre
   nettopp blankobekreftelse.

5. **Baseline er `git diff base...HEAD`.** Bare grenens egne endringer sammenlignes. En spec
   som har drevet fra hovedgrenen over måneder — fordi ti små grener hver for seg var
   uskyldige — er strukturelt usynlig.

I tillegg mangler vi én mekanisme `interview-me` faktisk har:

**Uavhengig kode-inventering.** VERIFY.md kjører to agenter i parallell: en som ser specen og
dømmer påstandene, og en som inventerer repoet **uten å se specen**. Poenget er retningen:
den første finner manglende krav, den andre finner udokumentert kodevekst. `/ship` Step 8.2
nærmer seg, men måler mot «stated intent» fra commit-meldinger og PR-body — ikke mot specen —
og er uttrykkelig ikke-blokkerende.

Dette er samme prinsipp som fler-lense-doktrinen i `pitfall-verification`: uavhengige
observatører med ulike blindsoner. Her er distansen ikke treningsdistribusjon, men
informasjonstilgang.

## Motforestillingen: prevensjon var et bevisst valg

`plan-fidelity-v2` er ikke en forglemmelse. Den har en egen seksjon som argumenterer for
hvorfor drift skal fikses i commit-øyeblikket og ikke ved porten, og den er en delt,
single-sourced blokk som `adapt` injiserer i **alle** prosjekter uavhengig av spor
(`skills/adapt/SKILL.md:520`: «plan drift is not track-specific»). Et forslag som legger
deteksjon oppå uten å svare på det, fortjener å bli avvist.

Svaret er at prevensjon og deteksjon løser ulike feil:

- Prevensjonsregelen er en **atferdsregel uten håndhevelse**. Den forutsetter at agenten
  leser CLAUDE.md, husker regelen gjennom en lang sesjon, og selv oppdager at den avvek. Den
  har ingen mekanisme som fanger opp at den ble glemt — og et avvik som ikke ble oppdaget i
  øyeblikket, blir ikke oppdaget senere heller.
- `autoimplement` har allerede møtt denne feilen i praksis: en Codex-review av v2.14.0 fant
  at pre-flight kunne redigere planen mens fasekøen ble bygget fra det gamle innholdet
  (`skills/autoimplement/SKILL.md:449`). Det er stale plan-innhold som overlever en
  regel — funnet av en lense, ikke av regelen.

Deteksjon er sikkerhetsnettet under prevensjonen, ikke en erstatning for den. Forslaget
under skal derfor ikke svekke `plan-fidelity`; fase 2 er tvert imot bygget for å skrive
tilbake **etter `plan-fidelity` sine egne skriveregler**.

## Forslag: pakk inn, ikke bygg parallelt

Repoets egen guardrail i `CLAUDE.md` sier at eksisterende implementasjoner skal gjenbrukes
før nye skrives. Det gjelder her: `plan-completion.md` er allerede den vanskelige delen.
Problemet er ikke at logikken mangler, men at den sitter fast inne i `/ship`.

### Fase 1 — wrapper, ikke utløfting (anbefalt)

Første utkast av dette dokumentet sa «løft logikken ut, og la `/ship` Step 8 kalle den».
Det går ikke: `/ship` er upstream gstack (`garrytan/gstack`, `CLAUDE.md` «Upstream
sources»), og `plan-completion.md` er autogenerert fra en `.tmpl` der («do not edit
directly»). Denne plugin-en kan ikke få `/ship` til å kalle noe, og en lokal endring i
seksjonen overskrives ved neste upstream-synkronisering. Retningen må være den samme som for
`office-hours-track-aware`, som pakker inn gstack via `Skill(skill="office-hours")` framfor
å endre den.

`spec-drift` **leser** derfor `~/.claude/skills/gstack/ship/sections/plan-completion.md` fra
disk ved kjøring og utfører seksjonen frittstående — nøyaktig slik `/ship` Step 8.1 selv leser
`qa-only/SKILL.md` inline. Fem konsekvenser:

- **Null duplisert logikk**, fordi det er samme filbytes som kjøres. Wrapperen pinner en
  hash av seksjonen og feiler høyt («upstream-seksjonen har endret form — verifiser
  wrapperen») når den avviker. Det er samme klasse guard som `test_lint_upstream_skills.py`
  innførte etter at en auto-oppdatering foreslo ruting til en upstream-skill som ikke fantes.
  Fordi gstack auto-oppdateres ukentlig, vil pinnen ryke ofte; derfor er re-pin en egen,
  bevisst kommando (`--repin`) som først viser diffen av seksjonen og krever bekreftelse,
  og pinnen ligger i skillen (committet), ikke per maskin. En guard som må overstyres
  rutinemessig uten å vise hva som endret seg, trener bort sin egen effekt.
- **Eksplisitt mål, ingen heuristikk.** Frittstående kall tar plan-stien som argument. Step 8
  sine discovery-fallbacks (grep etter grennavn, «nyeste fil siste 24 timer») finnes fordi
  `/ship` ikke vet hvilken plan som gjelder. Et frittstående kall vet det — og fallbacken
  ville i `docs/superpowers/specs/` med tretten filer valgt sist rørte fil, ikke riktig fil.
- **Planer, ikke specer.** Step 8 ekstraherer *handlingspunkter* — avkryssingsbokser,
  nummererte steg, imperativer — og hopper over med «no actionable items» ellers.
  Designdokumenter, dette inkludert, består av prosa og tabeller og gir null eller tre
  tilfeldige punkter. Fase 1 dekker derfor `docs/superpowers/plans/` og `progress.md`.
  Påstander i spec-prosa krever et eget utledningssteg og hører til fase 3.
- **Baseline blir et argument — men fortsatt en diff.** Standard er `git diff <base>...HEAD`.
  Hull 5 lukkes ved å gi en eldre commit som base, slik at akkumulert drift på hovedgrenen
  blir synlig. En «hele treet»-modus er *ikke* samme ting: uten diff kollapser
  `DIFF-VERIFIABLE` til «finnes i treet», og `PARTIAL`/`CHANGED` mister referansepunktet.
  Bygges den, får den egne verdikter (`PRESENT`/`ABSENT`/`UNVERIFIABLE`) og er eneste
  mulighet i et repo uten git.
- **Utdata-kontrakt frittstående.** Samme menneskelesbare rapport som Step 8, samme JSON på
  siste linje, og exit-kode `0` rent / `1` drift funnet / `2` kunne ikke kjøre — slik at
  `autoimplement` kan kalle den mekanisk ved fasegrenser uten å parse prosa.

Dette lukker hull 1, 3 og 5. Fase 1 er billig fordi den kjører eksisterende tekst framfor å
skrive ny.

### Fase 2 — skriv-tilbake og hukommelse

To tillegg som forutsetter fase 1:

- **Skriv-tilbake i specen.** Et bekreftet `CHANGED`- eller `NOT DONE`-funn kan tilbys skrevet
  inn i specen, etter reglene `plan-fidelity.md` allerede fastsetter: erstatt den
  utdaterte seksjonen framfor å føye til en rettelse under, behold *grunnen* til at utkastet
  ble forlatt, og flytt eventuell gjenstående verdi til et «utsatt»-notat **med trigger**.
  Skillen skal aldri redigere kildekode — bare specen, og bare etter bekreftelse.
  Skriv-tilbake skjer nødvendigvis i en senere commit enn avviket; commit-meldingen
  navngir derfor commit-en(e) auditen sammenlignet mot, så historikken viser hvilket
  avvik som ble innhentet.
- **Drift-ledger.** Akseptert drift får et fingeravtrykk (`claimId:kind:path`) i
  `.gstack/spec-drift.jsonl`. `.gstack/` er gitignorert som standard, og hver fil som skal
  deles løftes ut eksplisitt — `!.gstack/track`, `!.gstack/e2e-executor` i VM-specen.
  Ledgeren **committes** på samme måte; ellers er akseptert drift per maskin, og hull 4
  åpner seg igjen på neste maskin. JSON Lines og append-only, så to grener som aksepterer
  ulik drift fletter uten konflikt. Suppresjon skjer på fingeravtrykk, ikke på rekkefølge,
  slik at et akseptert avvik forblir akseptert når nabopunktene endrer seg.

Dette lukker hull 2 og 4.

### Fase 3 — uavhengig inventering og sikkerhetseskalering

- **Inventeringsagent uten spec-tilgang.** En andre subagent inventerer det som faktisk finnes
  i repoet uten å ha lest specen, og resultatene forenes først etterpå. Fanger udokumentert
  kodevekst i den retningen dagens Step 8.2 ikke måler. Isolasjonen er *instruert*, ikke
  sandkasset: en subagent har ingen foreldrekontekst, men full lesetilgang, og vil lese
  specen når den inventerer `docs/` med mindre den bes la være. Agenten får derfor
  repo-roten og en eksplisitt ekskluderingsliste (spec-stien og `docs/superpowers/`), og
  resultatet merkes «instruksjons-isolert». Kjøres inventeringen *før* spec-stien er navngitt
  i sesjonen, er isolasjonen reell uten ekstra mekanikk — det er standardrekkefølgen.
- **Påstander fra spec-prosa.** Det er her — ikke i fase 1 — designdokumenter kommer inn:
  et utledningssteg som siterer verifiserbare påstander ordrett fra prosaen, aldri
  omskrevet, før de sendes gjennom samme verdikt-sett som handlingspunktene.
- **Sikkerhetskategori.** Drift som berører hemmeligheter, autentisering, injeksjon,
  datahåndtering, rate limiting eller oppbevaringstid tvinges til `critical` og kan ikke
  batch-avvises — den krever skriftlig begrunnelse i ledgeren. Dette er `interview-me` sin
  beste enkeltidé, og den passer vår eksisterende fail-closed-linje i `plan-completion.md`.

## Avgrensning

- **Ikke en intervju-skill.** Ingenting her overlapper `brainstorming`, `/office-hours` eller
  plan-review-familien. Forslaget gjelder utelukkende sammenligningen spec mot kode.
- **Redigerer aldri kildekode.** Skillen rapporterer, og skriver i verste fall i specen.
- **Rører aldri upstream.** Wrapperen leser `/ship` sin seksjon; den patcher den ikke, og
  den forutsetter ikke at `/ship` kjenner til den. Ønskes Step 8 eksponert frittstående i
  gstack selv, er det en upstream-PR til `garrytan/gstack` — ikke noe dette repoet kan
  planlegge med.
- **Erstatter ikke `plan-fidelity`.** Prevensjonsregelen står; dette er nettet under den.
- **Erstatter ikke `pitfall-verification`.** Den spør «ville dette virke?» om et artefakt sett
  innenfra. Dette spør «stemmer artefaktet med virkeligheten?». Ulike spørsmål, ulike
  feilklasser.
- **Ingen ny tier-gate.** Skillen er lesende og billig i fase 1, og trenger ikke
  fler-lense-orkestreringen `pitfall-verification` har. Om et funn fortjener flere lenser, er
  det `pitfall-verification` som skal kalles på funnet — ikke omvendt.

## Verifisering hvis fase 1 bygges

```bash
cd ~/Developer/superpowers-gstack
python3 scripts/lint-skills.py          # grønn, inkl. routing coverage for ny skill
bash tests/run.sh --unit
```

Deretter, i et prosjekt med en kjent stale plan:

1. `/superpowers-gstack:spec-drift docs/superpowers/plans/<plan>.md` — finner planen, dømmer
   punktene, gir samme verdikt-sett som `/ship` Step 8 gir i dag.
2. Samme prosjekt, `/ship` — Step 8 gir **samme dom på DONE/NOT DONE-aksen** som det
   frittstående kallet, over tre kjøringer av hver. Kravet er *ikke* bytelik utdata: to
   kjøringer av samme prosainstruks er ikke deterministiske, og et krav om identisk utdata
   ville enten rullet tilbake en riktig wrapper på støy eller blitt stille ignorert.
   Strukturell ekvivalens sikres av hash-pinnen (samme filbytes kjøres); atferdsekvivalens
   måles som lik `total_items` og lik dom på DONE/NOT DONE-aksen. Uenighet begrenset til
   `PARTIAL`↔`CHANGED` er støy; uenighet på DONE/NOT DONE er regresjon.
3. En gren som ikke skal shippes: det frittstående kallet virker, `/ship` kjøres aldri.
   Dette er hull 3 demonstrert lukket.
4. Bytt én linje i en lokal kopi av `plan-completion.md`: wrapperen skal nekte å kjøre og
   navngi hash-avviket. Det er guarden mot stille upstream-drift demonstrert.

**Beviser skillen sin plass?** Etter ti kjøringer i reelle prosjekter: tell funn der brukeren
valgte «fiks» eller «aksepter med begrunnelse», mot funn avvist som støy. Er andelen reelle
funn nær null, var `plan-fidelity` tilstrekkelig, og skillen trekkes. Det er det ærlige
utfallet av motforestillingen over — og samme måleform `scripts/cost-ledger/` allerede
bruker per lense («findings that survived synthesis»).

Til slutt `superpowers-gstack:pitfall-verification` på diffen. Endringen avhenger av en
upstream-kontrakt den ikke eier (Step 8 sin seksjon og JSON) og er dermed ship-worthy med
Codex-lens; berører den i tillegg ledger-formatet i fase 2, går den til tredje hus.

## Verifisering — resultat (fase 1, 2026-09-07)

Plan under test: `tests/fixtures/spec-drift/stale-plan.md` (9 punkter; 5 finnes på `feat/spec-drift`, 4 er fase 2–3). Baseline `main` (= `origin/main`, `88a9c70`); HEAD under alle seks kjøringene `09e3b12`. gstack 1.81.0.0, pin sha256 `e329e5ef7699`.

| Kjøring | Verktøy | total_items | DONE | NOT DONE | Annet | Exit |
|---|---|---|---|---|---|---|
| 1 | spec-drift | 9 | 1–5 | 6–9 | — | 1 |
| 2 | spec-drift | 9 | 1–5 | 6–9 | — | 1 |
| 3 | spec-drift | 9 | 1–5 | 6–9 | — | 1 |
| 4 | /ship Step 8 | 9 | 1–5 | 6–9 | — | (port: A) |
| 5 | /ship Step 8 | 9 | 1–5 | 6–9 | — | (port: A) |
| 6 | /ship Step 8 | 9 | 1–5 | 6–9 | — | (port: A) |

**Dom på DONE/NOT DONE-aksen:** lik i 6/6. Ingen PARTIAL, CHANGED eller UNVERIFIABLE i noen kjøring; hver kjøring siterte fil og linje per punkt (`scripts/spec-drift.py` subparsere, `skills/adapt/SKILL.md:176`, `test_one_changed_line_upstream_is_refused_and_named`, og for punkt 6–9 fravær av flagg, sti eller verdiktstreng i script og skill). Kjøring 1–3 endte med `SPEC-DRIFT: DRIFT (exit 1) — done=5 changed=0 partial=0 not_done=4 unverifiable=0 of 9`, beregnet av `verdict` fra JSON-linjen. Kjøring 4–6 skrev `PLAN_FILE: ~/.gstack/projects/Paretofilm-superpowers-gstack/spec-drift-stale-plan.md` fra Step 8 sitt eget innholdssøk, og porten (fire NOT DONE → prioritet 1) ble besvart med A. **Hash-guard (punkt 4):** én tilføyd linje i lokal kopi → `PIN MISMATCH` med begge hashene og `repin`-hintet, exit 2, ingen audit dispatchet — via scriptet direkte og via skillens Phase 1. Første forsøk via skillen avdekket at `${SECTION:+--upstream "$SECTION"}` er ett ord under zsh (skallet Claude Codes Bash-verktøy bruker), så `check` feilet med `USAGE ERROR` — fortsatt exit 2, men guarden var ikke kjørt; rettet i `09e3b12` før kjøring 1–6, med en test som kjører linjen ordrett under zsh, bash og sh. **Hull 3:** kjøring 1–3 gjort på en gren `/ship` aldri fullførte.

**Slik kjøringene faktisk ble gjort (avvik fra oppskriften i planens fase 4):**

- Skillen ligger ikke i den installerte plugin-cachen (2.51.1), så kjøring 1–3 kjørte `skills/spec-drift/SKILL.md` fra repoet som instruksjonene den er: Phase 0 og 1 én gang (deterministisk bash), deretter tre uavhengige audit-subagenter med Phase 2-prompten ordrett, og `verdict` per JSON-linje.
- Kjøring 4–6 kjørte Step 8-seksjonen slik `/ship` sin forelder gjør det: seksjonen lest fra disk, subagent-prompten sendt ordrett med `<base>` = `main`, discovery uberørt, port-logikken utført av forelderen. `/ship` sine Step 0–7 ble ikke kjørt: sesjonen hadde et annet repo som arbeidsmappe, og Step 3 sin merge av `origin/main` var allerede gjort i Step 1. Den fulle pipelinen kjører Step 8 én gang til ved landing, som sjuende datapunkt — forutsatt at planen ligger der Step 8 søker (`~/.gstack/projects/<slug>/`, `~/.claude/plans`, `~/.codex/plans`, `.gstack/plans`) eller i samtalekonteksten; `docs/superpowers/plans/` er ikke en søkesti, så legg en kopi i `~/.gstack/projects/Paretofilm-superpowers-gstack/` før landing og fjern den etterpå.
- Alle seks subagentene ble dispatchet parallelt fra én orkestratorsesjon, hver med frisk kontekst, i stedet for seks sekvensielle sesjoner. Én miljølinje ble lagt foran begge promptene (repo-sti og `cd`-prefiks), fordi subagentenes skall startet i et annet repo.
- Forbehold: planen med fasiten for fixturen er selv del av `main...HEAD`, og alle tre Step 8-kjøringene leste den. Verdiktene siterte likevel per-punkt-bevis. Neste fixture bør ha fasiten utenfor diffen.

**Ti-kjøringers-målet** (andel reelle funn) starter nå; føres her etter hvert.
