# Vibe-profilen — design (3.6.0, med trinn 2 i 3.7.0)

Dato: 2026-10-03 · Status: godkjent for trinnvis implementering (brukerens valg «Trinnvis») · Eier: pluginens eier

## 1. Bakgrunn

En måling av 17 dager med transkripter (36 570 modellkall, fem apper) viste at det som koster, ikke er
pluginens tekst (ca. 2 % av gjenbrukt kontekst), men atferden rundt den:

- **Stopp som venter på brukeren.** 244 strukturerte spørsmål, 89 % besvart med anbefalt alternativ. Når
  anbefalingen var merket, ble den fulgt i 93 % av tilfellene. Fem ubesvarte seremonispørsmål sto for
  50,9 av 54,1 timer ventetid i én app. Avvikene var nesten alltid ekte produktvalg eller verifisering.
- **Lange sesjoner.** 87 % av hovedtrådens kall skjer over 200k kontekst, og delen over 200k er 60 % av
  alle kontekst-tokens. Subagenter starter på 80–110k grunnlinje.
- **Gjentatte reviewkjeder.** Linsene finner reelle feil, men kjøres flere ganger per feature.
- **Regler i minnet ble ikke fulgt.** En autonomi-regel lagret i minnet ble overkjørt av skillenes porter;
  regler som skal overstyre porter må ligge i et lag som alltid lastes (CLAUDE.md).
- **Grønne tester er ikke nok.** I et videoprosjekt passerte alle sjekker mens resultatet var feil; i en
  ekstern Karpathy-løkke passerte alle sjekker mens featuren ikke var koblet til appen.

Arbeidsflyten som svar på dette ble skrevet som en prosjektlokal «vibe-kontrakt» (v1 testes i et privat SwiftUI-prosjekt,
v2 er en videreutviklet utgave i et privat analysearkiv). Den hjelper bare det ene prosjektet. Denne
specen gjør den gjenbrukbar gjennom pluginen.

## 2. Mål og ikke-mål

**Mål (3.6.0)**
1. Et prosjekt kan velge arbeidsflytprofilen `vibe` én gang, og `/adapt` skriver da en kort kontraktblokk i
   CLAUDE.md som overstyrer skillenes porter.
2. En skill, `/superpowers-gstack:vibe`, kjører én feature fra intake til landing etter kontrakten.
3. Akseptansetester kan låses mekanisk og verifiseres uendret før landing.
4. Prosjektkunnskap lever i en prosjektlokal skill som hentes ved behov, ikke i CLAUDE.md.
5. Effekten kan måles: et verktøy teller spørsmål, stopp og tokens per prosjekt før og etter.

**Mål (3.7.0, trinn 2)**
6. En generisk Karpathy-løkke (`/superpowers-gstack:karpathy-loop`) for oppgaver med en tallfestet poengsum,
   generalisert fra den første ekte instansen (fargekorrigering i et privat videograderingsprosjekt).

**Ikke-mål**
- Endre standard for andre brukere. Uten valgt profil er alt som i 3.5.1 (`classic`).
- Endre superpowers- eller gstack-skillene (oppstrøms; overskrives ved oppdatering).
- Endre brukerens globale konfigurasjon (MCP, skill-overstyringer, modell). Det er personlige valg.
- Automatisk start av `/goal`: ifølge dokumentasjonen startes den av brukeren.

## 3. Akseptkriterier for 3.6.0

1. `/adapt` spør om profil én gang når `.gstack/workflow` mangler, skriver valget dit, og spør ikke igjen.
2. Med `vibe` skriver `adapt-claude-md.py` blokken `gstack-vibe-v1`; med `classic` eller manglende fil skrives
   den ikke, og en eksisterende vibe-blokk fjernes som annen plugin-prosa.
3. Alle eksisterende tester og lint er grønne; nye tester dekker profilfilteret, blokken, låseskriptet og
   målingsverktøyet.
4. `lock-acceptance-tests.py lock` committer testene, skriver `deny`-regler og en kvittering; `verify` gir exit 0
   bare når testfilene er identiske med den låste committen (også ikke-committede endringer teller).
5. Med `vibe` oppretter `/adapt` `.claude/skills/<prosjekt>-context/SKILL.md` fra mal hvis den mangler, og
   skriver aldri over en eksisterende.
6. `workflow-metrics` gir samme tall som analyseskriptene fra 2026-10-02 på samme data (dedup på `message.id`).
7. Release gate: versjon 3.6.0, CHANGELOG, README, ruting i CLAUDE.md, lint grønn.

## 4. Design

### 4.1 Profilvalg

- Ny pinfil `.gstack/workflow` med `vibe` eller `classic`, samme mønster som `.gstack/e2e-executor`
  (spørres én gang i `/adapt` steg 4, committes).
- Spørsmålet: «Hvordan skal dette prosjektet jobbe? **Vibe** (anbefalt): ett intake, så autonom
  ferdigstilling og én samlet gjennomgang. **Klassisk**: skillenes egne godkjenningsporter.»
- `adapt-claude-md.py`: `Block` får feltet `profiles: frozenset | None` (None = alle), som `tracks`. Skriptet
  leser pinfilen (ukjent verdi gir `BLOCKED — invalid .gstack/workflow`), standard `classic`.
- En kjøring uten noen å spørre (subagent, `--print`) velger `classic` og sier det.

### 4.2 Kontraktblokken `gstack-vibe-v1` (`skills/adapt/blocks/vibe-contract.md`)

Kort (mål: under 30 linjer), engelsk som de andre blokkene, og bare regler, ikke prosedyre. Innhold:
- Stående godkjenninger etter intake: design, spec og plan er forhåndsgodkjent; ingen valg av utførelsesmetode;
  ingen «hva nå» mellom faser; ingen avslutningsmeny (landing etter `Landing mode`). Overstyrer uttrykkelig
  HARD-GATE i `superpowers:brainstorming`, metodevalget i `superpowers:writing-plans` og menyen i
  `superpowers:finishing-a-development-branch`.
- Stopplisten: irreversibelt eller destruktivt, sikkerhetsfølsomt, bivirkninger utenfor worktreen, push til
  remote, penger, lisens, ekte blokkering. Alt annet: «Ruling: valg — hvorfor — kostnad hvis feil».
- Kontrollpunktet: testoversikten (akseptansetestene) er brukerens ene kontroll underveis; etter godkjenning er
  testene låst og endres aldri for å få rødt til grønt.
- Kontekst: hovedtråden under ca. 150k, fersk subagent per fase, `STATUS.md` ved fasegrenser.
- Review: multi-lens-kjeden kjøres én gang per feature, på slutten, risikotiert. Blokken
  `gstack-multi-lens-review` beskriver rekkefølgen og gjelder fortsatt; vibe-blokken sier bare når.
- Peker: «Kjør `/superpowers-gstack:vibe` for prosedyren.»

### 4.3 Skillen `vibe`

Prosedyren for én feature (detaljene som ikke trenger å ligge i CLAUDE.md):
0. Les prosjektets kontekst-skill (4.5) og koden; klassifiser omfang.
1. Intake: alle spørsmål i én `AskUserQuestion`-runde (høyst åtte; anbefalt først og merket),
   alltid fasit/akseptkriterier (5–10) og utenfor omfang. Skillen går ikke selv inn i plan-modus (å forlate den
   spør brukeren én gang til); intaket er skrivebeskyttet for kode.
2. `docs/superpowers/vibe/<dato>-<feature>/SPEC.md` (mål, ikke-mål, akseptkriterier) og `PLAN.md` (små
   oppgaver med én test og én «ferdig når»-linje; ingen kode).
3. Akseptansetester fra kriteriene; én melding med testoversikt og en ferdig `/goal`-linje
   (`/goal Alle oppgaver i PLAN.md er ferdige: testene grønne, bygg uten advarsler, STATUS.md oppdatert. Eller
   stopp etter 60 turer.`). For visuelt arbeid: sannhetsprøve mot referansen (skjermbilde/render), ikke bare
   enhetstester. Etter brukerens «ok»: `lock-acceptance-tests.py lock`.
4. Én fersk subagent per fase (`superpowers:subagent-driven-development`), med to faste regler: koble det som
   bygges til appen i samme runde som testene blir grønne; finn alle steder appen allerede gjør samme jobb og
   la dem følge de nye reglene. `STATUS.md` per fase, én linje per runde i `ROUNDS.md`.
5. Tester under arbeid: bare berørte (`--filter`); hel suite ved fasegrensen og før landing.
6. Én reviewlinse til slutt via `/superpowers-gstack:pitfall-verification` (tier beregnes som før).
7. Lærdom før landing: feil som gikk igjen i to faser eller mer blir høyst tre arbeidsregler i
   kontekst-skillens «Slik jobber vi»-seksjon (ikke i CLAUDE.md), og endringen committes på feature-grenen;
   lærdom skrevet etter landing når aldri hovedgrenen.
8. `lock-acceptance-tests.py verify --feature <feature>` må gi exit 0 før landing. Låsen forsvarer mot feil og
   snarveier, ikke mot bevisst omskriving av historikk.
9. Landing etter `Landing mode` (`/superpowers-gstack:land` eller `/ship`); ett spørsmål om push hvis det
   kreves av prosjektet. Låsen blir stående som oppføring.
10. Sluttrapport: bygget, hvordan verifisere, Rulings, utsatte funn.

### 4.4 `scripts/lock-acceptance-tests.py`

- `lock --path <glob> [--path ...]`: krever at stiene finnes og er rene; committer dem
  (`test(acceptance): lock <feature>`); legger `deny`-regler `Edit(<glob>)` og `Write(<glob>)` i prosjektets
  `.claude/settings.json` (opprettes om den mangler; eksisterende innhold bevares; ugyldig JSON gir refusal);
  skriver kvitteringen `.gstack/acceptance-lock.json`; committer settings og kvittering i en egen commit rett
  etter (kvitteringen inneholder SHA-en til test-committen); kvitteringen holder én lås per feature
  (`{"locks": [...]}`).
- `verify`: exit 0 når `git diff --name-only <commit> -- <paths>` er tom (arbeidstre inkludert); ellers exit 1
  med de endrede filene. Exit 2 uten kvittering.
- `unlock`: fjerner bare reglene skriptet selv la til; skal bare kjøres på brukerens uttrykkelige ønske.
- Svakhet som dokumenteres: en `deny`-regel stopper ikke `sed` via Bash; derfor er `verify` den egentlige porten.

### 4.5 Prosjektkunnskap som skill

- Mal `skills/adapt/templates/project-context.md` med seksjonene: hva produktet er, arkitektur, domenesannheter,
  fallgruver, funn med henvisninger, kjøring og testing, «Slik jobber vi», «Slik holdes skillen oppdatert».
- Med `vibe`: `/adapt` oppretter `.claude/skills/<prosjekt>-context/SKILL.md` hvis den mangler (navnet fra
  `--project-name`), med en `description` under 40 ord, og vibe-blokken peker til den gjennom `{{CONTEXT_SKILL}}` (skriptet skriver aldri i umarkerte seksjoner).
  Standardnavn `<prosjekt>-context`; en eksisterende `*-context` eller `*-kontekst` brukes. Eksisterende skill
  røres aldri.
- Første ekte instans: en kontekst-skill i et privat videograderingsprosjekt (laget 2026-10-03 på
  egen gren); malen kalibreres mot den.

### 4.6 `workflow-metrics`

- Pakke `scripts/workflow_metrics/` (bare standardbiblioteket) med inngang `scripts/workflow-metrics.py`:
  `tokens`, `asks`, `overhead`, `skills`, `triggers`, `mcp`, `digest`. Valg: `--root` (standard
  `~/.claude/projects`), `--project <delstreng>`, `--since <dato>`, `--until <dato>`.
- Alle token- og kalltall dedupliseres på `message.id`; tool_use-blokker telles uten dedup.
- Skill `/superpowers-gstack:workflow-metrics` beskriver før/etter-måling av en arbeidsflytendring og minner om
  at transkripter slettes etter `cleanupPeriodDays`.
- Fikstur-tester med små syntetiske JSONL-filer (inkludert duplisert `message.id`).

### 4.7 Ruting og dokumentasjon

Nye skills inn i CLAUDE.md-rutingen, README og rosteren; `vibe` og `workflow-metrics` som modellstyrte,
`karpathy-loop` (3.7.0) som tilvalg. Versjon 3.6.0 og CHANGELOG.

## 5. Trinn 2 (3.7.0): `karpathy-loop`

Generaliseres fra Resolve-instansen etter at den er prøvd. Skissen: når en løkke lønner seg (oppgaven gjentas,
budsjettet tåler den, en klar poengsum finnes, agenten kan kjøre det den bygde); én fil løkka får endre; en
låst evaluator (gjenbruker låsemekanismen fra 4.4); mal for `program.md`; `results.tsv`; behold eller angre per
runde; holdt-av testsett; budsjett og stoppkriterier. Egen spec når instansen har resultater.

## 6. Risiko

| Risiko | Avbøtning |
|---|---|
| Arbeidsflyten er ikke målt ennå | Tilvalg; `workflow-metrics` måler før/etter; v1 måles i et privat SwiftUI-prosjekt |
| Overstyringen av HARD-GATE slår ikke gjennom | Målbart med `asks`; blokken navngir portene eksplisitt |
| Agenten svekker en låst test via Bash | `verify` før landing er porten, ikke `deny`-regelen |
| `/goal` kan bare startes av brukeren | Ferdig linje ved kontrollpunktet; uten `/goal` fortsetter flyten med subagenter |
| Prosjektets egne regler strider mot kontrakten (f.eks. «PRD før kode») | `/adapt` sin gap-analyse lister motstriden; brukeren velger |
| Kontraktblokken vokser | Mål under 30 linjer; prosedyren ligger i skillen |

## 7. Testplan

- `adapt-claude-md.py`: profilpin (mangler, `vibe`, `classic`, ugyldig), blokken skrives/fjernes, idempotens.
- `lock-acceptance-tests.py`: midlertidige repoer for lock, verify (ren, endret, ikke-committet), unlock,
  ugyldig settings-JSON.
- `workflow_metrics`: fikstur med duplisert `message.id` gir halverte tall; `asks` gjenkjenner anbefalt svar.
- Lint (E3-ruting, W1-ordbudsjett, E8-blokkroster, E11 egne blokker) og eksisterende suiter.

## 8. Åpne spørsmål (med anbefalt svar)

1. Skal `vibe` bli standard etter målingen? Anbefalt: avgjøres med `workflow-metrics`-tall, ikke nå.
2. Skal kontekst-skillen også lages i `classic`-prosjekter? Anbefalt: nei i 3.6.0.
