---
status: presentert
opprettet: 2026-09-22
---

# Forslag: Jev som rådgiver for valg av ferdighet

## Til neste agent: avklar med brukeren

Brukeren ba om utforsking og et forslag som neste prosjektagent skal presentere.
Dette dokumentet er ikke en bestilling på implementering. Økten som oppretter
eller redigerer forslaget skal bare gjøre dokumentarbeidet.

- Ved neste interaktive prosjektøkt: hvis `status` er `ikke_presentert`, presenter
  anbefalingen kort og still spørsmålet nedenfor. Spør én gang, selv om både
  AGENTS.md og CLAUDE.md peker hit. Sett så status til `presentert` og noter at
  svar avventes i beslutningsloggen.
- Fortsett en eventuell annen bestilt oppgave mens avklaringen venter. Ikke
  implementer piloten, installer en hook eller kjør betalte evalueringer uten ja.
- Lagre svaret med dato og avtalt omfang; bruk `godkjent`, `utsatt` eller `avslått`.
  Et ja til spørsmålet nedenfor gjelder bare pilot A, ikke senere utvidelser.
- Ikke spør automatisk igjen ved `presentert`, `godkjent` eller `avslått`.
  Ved `utsatt`: spør først ved avtalt dato eller hendelse. Uten avtalt utløser
  tar brukeren selv initiativ. En uttrykkelig ny beskjed gjelder foran lagret status.
- I ikke-interaktive kjøringer: la status stå og ikke start avklaringen.

## Spørsmålet til brukeren

> Vil du at jeg skal implementere pilot A: en separat evaluering av Jev som
> rådgiver for ferdighetsvalg, sammenlignet med dagens ruting og enklere alternativer,
> uten å endre rutingen i aktive agentøkter?

## Anbefalingen

Start med å måle **valg av neste ferdighet**, med prosjekt og arbeidsfase som
kontekst. Behold eksplisitte brukerønsker, faste omdirigeringer, plattformregler,
modellgrenser og obligatoriske kontroller utenfor Jevs myndighet. Jev kan foreslå
et valg; programmet validerer det, og hovedagenten vurderer om det passer oppgaven.

Mulig gevinst er færre feilaktige eller unødvendige ferdighetskall og bedre dekning
av tilgjengelige ferdigheter. Høyere hastighet og lavere totalkostnad er hypoteser:
rutingen skjer allerede inne i hovedagentens behandling, så et ekstra API-kall er
ikke automatisk en besparelse.

## Hva som finnes i repoet

Undersøkt mot kildekoden som oppgir pluginversjon 3.3.0. Dette er status for denne
arbeidskopien, ikke en påstand om hvilken versjon alle aktive økter bruker.

| Kilde | Betydning for forslaget |
| --- | --- |
| [Ferdighetskatalogen](skills/adapt/roster.md) | Felles vurderingsgrunnlag for `/adapt`; ikke en garantert liste over det som er installert og aktivt i en bestemt økt. |
| [Adapt-ferdigheten](skills/adapt/SKILL.md) | Lager prosjektspesifikk ruting. En eksisterende `Skill routing`-seksjon bevares i hovedsak, mens enkelte administrerte deler oppdateres. |
| [Modellrutingen](skills/adapt/model-routing.md) | Rådgivende tabell med grunnnivå per ferdighet og justering etter konsekvensen av feil. |
| [Plattformrutingen](skills/adapt/blocks/track-routing.md) | Avtalte omdirigeringer for blant annet office-hours og design-consultation. |
| [Testdispatcher](skills/e2e-route/SKILL.md) | Egen ruting for plattform, testhensikt og hvor testen skal kjøres. |
| [Kontrollnivå](scripts/classify-change.py) | Beregner et minimumsnivå; agenten kan heve, men ikke senke dette. |
| [Hook-oppsettet](hooks/hooks.json) | Har SessionStart og SessionEnd, men ingen UserPromptSubmit-rådgiver. |

**Konkret regelkonflikt:** CLAUDE.md ruter generelt feil til `investigate`.
README, ferdighetskatalogen og adapt-malen skiller mellom feil under implementering
(`systematic-debugging`) og feil funnet under kvalitetskontroll eller i produksjon
(`investigate`). Avklar og test denne prioriteten i pilotarbeidet; ikke la Jev
avgjøre hvilken regelkilde som skal vinne.

**Tidligere forsøk er relevant:** CHANGELOG for 3.0.0 beskriver at den adaptive
kontrollruteren `cost-ledger` ble fjernet. Ulike navn på samme modellkontroll og
domene splittet målingene, og systemet hoppet aldri over noen kontroll. Den gamle
spesifikasjonen finnes fortsatt, men beskriver ikke aktiv funksjonalitet.
Dette forslaget gjeninnfører ikke funksjonen. Bruk stabile identifikatorer og mål
nytte før noe får justere arbeidsflyten. Se [endringsloggen](CHANGELOG.md).

## Fire mulige anvendelser — med ulik prioritet

| Anvendelse | Vurdering | Avgrensning |
| --- | --- | --- |
| Neste ferdighet i samtalen | Første pilot. Nyttig ved like ferdighetsnavn, korte meldinger, norsk språk og tvetydig hensikt. | Foreslå høyst ett neste steg; ikke oppfinn en hel kjede. |
| Bredere ferdighetsutvalg under adapt | Senere forsøk hvis piloten avdekker manglende katalogdekning. | Suppler katalogen med faktisk tilgjengelige ferdigheter. Behold brukeravklaring og eksisterende skript for skriving. |
| Modellvalg per oppgave | Senere, separat måling av resultatkvalitet og totalforbruk. | Slå opp gjeldende tabell etter ferdighetsvalg. Jev får ikke endre modellidentifikatorer eller senke domenets minimum. |
| Ekstra kontroll av en endring | Eventuelt forslag om mer kontroll. | Aldri redusere minimum fra classify-change eller droppe obligatoriske kontroller for å spare penger. |

## Foreslått beslutningsflyt

Dette er en skisse for piloten og en eventuell senere integrasjon, ikke et nytt
aktivt regelsett. Eksisterende tillatelser og prosjektavtaler gjelder fortsatt.

1. **Avklar det faste først.** Et uttrykkelig ferdighetsvalg følger dagens avtalte
   aliaser og omdirigeringer; Jev overstyrer det ikke. Kjente, entydige ruter og
   avtalte neste steg trenger normalt ikke API-kall. Skill mellom å nevne en
   kommando i et spørsmål og å faktisk be om at den kjøres.
2. **Avgrens kandidatene.** Finn ferdigheter som faktisk er tilgjengelige i den
   aktive økten, med gyldig navnerom og riktig versjon. Bruk lokale fakta til
   harde avgrensninger; ikke utelukk en mulig kandidat bare fordi et nøkkelord mangler.
3. **Vurder behov og relevans.** Jev får meldingen, nødvendig samtalekontekst,
   prosjektfakta og korte kandidatbeskrivelser. Choice velger mellom navngitte
   alternativer, inkludert «ingen passer». Separate Noul-spørsmål kan vurdere om
   konkrete kandidater faktisk passer. Spørsmålene kjøres samlet når de er uavhengige.
4. **Les et lite utvalg grundigere ved behov.** Hent relevante deler av de beste
   to–tre kandidatenes SKILL.md, særlig formål, når de ikke skal brukes og
   forutsetninger. Sammenlign én og to Jev-forespørsler i evalueringen; den andre
   er bare aktuell hvis forbedringen forsvarer ekstra tid og kostnad.
5. **Valider og foreslå.** Godta bare kjente ferdighets-ID-er fra kandidatlisten.
   Kontroller forutsetninger og faste grenser på nytt. Hovedagenten får eventuelt
   ett kort, rådgivende forslag og kan forkaste det. Manglende grunnlag betyr at
   dagens agentruting fortsetter, ikke at hele arbeidsflyten stoppes.

Choice sammenligner alternativer relativt; Noul vurderer en konkret påstand.
Hvis Choice velger kandidat A, må eventuell egnethetsgrense kontrolleres mot A,
ikke mot den høyeste Noul-verdien for en annen kandidat. Ellers kan en egnet B
feilaktig slippe gjennom en uegnet A. Uenighet må kunne gi intet forslag.

`confidence` er et mål beregnet fra svarfordelingen, ikke sannsynligheten for at
hele arbeidsflyten blir riktig. Noul har ikke et eget confidence-felt. Fastsett
terskler på egne eksempler; ikke kopier tersklene i TypeSafe-oppskriften ukritisk.

## Kontekst og dokumenthenting

RAG (retrieval-augmented generation), her dokumenthenting før en vurdering, kan gi
Jev den spesialkunnskapen den trenger om pluginens ferdigheter og arbeidsflyt.
Programmet henter tekst og legger den i forespørselen; Jev søker ikke selv og
blir ikke permanent trent. Bare relevant kontekst skal sendes.

- **Samtale:** siste melding og et kort, avgrenset utdrag som forklarer hva «ja»,
  «fortsett» eller «den feilen» viser til. Et slikt svar skal videreføre avtalt
  arbeid, ikke velge en ny arbeidsflyt basert på ordet alene.
- **Prosjekt:** kjent plattform, type artefakt, aktiv oppgave, observerte fullførte
  steg og faktisk tilgjengelige verktøy. Ikke la fravær av en markør automatisk
  bli bevis for plattform når andre pålitelige prosjektfakta sier noe annet.
- **Ferdigheter:** aktive beskrivelser, bruksgrenser og forutsetninger fra lokal
  installasjon. Katalogen i dette utviklingsrepoet er ikke alene nok til å avgjøre
  hva en eldre, allerede startet økt kan bruke.
- **Prioritet:** eksplisitt gjeldende brukerbeskjed og observerte fakta foran gamle
  antakelser. Merk usikkert eller utdatert fasegrunnlag som ukjent. Ikke bruk
  framtidige meldinger, testfasit eller senere verktøyresultater i klassifiseringen.

Et eksisterende handoff eller oppstartsvarsel er ikke nødvendigvis komplett eller
ferskt. Gjenbruk prosjektets forståelse av slike filer, men dokumenter hvordan
fasegrunnlaget holdes oppdatert. Piloten bruker først eksplisitt angitt fase i
testtilfellene. Automatisk utledning av fase er et eget feilledd som må måles.

## Pilot A: separat evaluering, ingen endring i aktive økter

Et ja til pilot A åpner for evalueringskode og avgrensede API-forsøk når nøkkel og
forbruksramme er avklart. Det åpner ikke for å installere en hook eller sende
løpende samtaler til TypeSafe.

**Datagrunnlag:** start med 50–100 manuelt gjennomgåtte tilfeller. Bruk syntetiske
eller uttrykkelig godkjente og anonymiserte eksempler. Ta med norsk, skrivefeil,
engelsk, korte oppfølginger, flere hensikter og tilfeller der ingen ferdighet skal
lastes. Hvert tilfelle angir tilgjengelige ferdigheter, relevant tidligere
kontekst, fase, tillatte neste valg og obligatoriske steg som ikke må forsvinne.
Tillat flere korrekte valg når arbeidsflyten faktisk tillater dem.

**Sammenligninger:** mål dagens oppsett først. Avklar deretter regelkonflikten
ovenfor og bruk samme avklarte regelgrunnlag i alle følgende varianter:

- Hovedagenten alene med de avklarte reglene.
- Samme hovedagent med lokalt utvalgte ferdighetsutdrag, uten Jev.
- Samme hovedagent med Jev-forslag basert på korte kandidatbeskrivelser.
- Samme hovedagent med Jev-forslag og grundigere lesing av kandidatene.

Hold kandidattilgjengelighet, testtilfeller, modell og øvrige instruksjoner like.
Forskjellen mellom gammel og avklart ruting må rapporteres separat, slik at bedre
regler ikke feilaktig blir regnet som Jev-gevinst. Del eksemplene i et sett for
utforming og terskler og et urørt sett for sluttmåling. En serie oppfølgingsmeldinger
fra samme oppgave skal ligge i samme sett. Gjenta et utvalg for å måle variasjon.

**Mål begge ledd:** først om rådgiveren finner et tillatt neste valg, deretter hva
hovedagenten faktisk velger når den får forslaget. Kjør agentens verktøy mot
simulerte grensesnitt i målingen; ikke utfør deploy, kjøp eller filendringer for å
måle ruting. En korrekt anbefaling er ikke bevis for at agenten følger den.

| Måling | Hvorfor |
| --- | --- |
| Riktig første ferdighet, unødvendige kall og uteblitte nødvendige kall | Skiller tre ulike feil som ett treffprosenttall skjuler. |
| Kandidatdekning før og etter utvalg | Viser om riktig ferdighet falt ut før Jev fikk vurdere den. |
| Korrekt avståelse og unødvendig avståelse | Et system som alltid tier må ikke få høy score. |
| Andel forslag agenten følger, og feil som forslaget introduserer | Fanger feilaktig påvirkning på et ellers riktig valg. |
| Bevarte obligatoriske steg og eksplisitte brukerønsker | Fanger at riktig førstesteg likevel fører til feil arbeidsflyt. |
| Median, 95-persentil og samlet svartid | 95-persentilen viser forsinkelsen som 95 prosent av tilfellene ligger under. |
| Faktisk forbruk hos både Jev og hovedagenten | Inkluder henting, ekstra kontekst, gjentatte forsøk og eventuelt andre Jev-kall. |

Rapporter antall og usikkerhet, også per problemgruppe. Et lite prøveutvalg kan
avdekke feil og gi retning, men ikke dokumentere sjeldne feil eller generell
pålitelighet. Avtal akseptabel ventetid og forbruksramme før kjøring. Videreføring
krever en målbar gevinst over den beste enkle varianten, ingen observerte brudd på
faste grenser i testsettet og akseptabel samlet kostnad. Uklart resultat betyr
større måling eller at dagens løsning beholdes, ikke automatisk aktivering.

### Eksempler som må være med

| Melding og kontekst | Forventet egenskap |
| --- | --- |
| «Testen feiler etter endringen» under implementering | Systematisk feilsøking, ikke automatisk etterkontroll av produksjon. |
| «Dette krasjer hos kunden» etter levering | Undersøkelsesruten vurderes i riktig fase. |
| «Jeg ser fortsatt gammel oppførsel» etter en fiks | Vurder kontroll av hvilket bygg som kjører, ikke bare visuell design. |
| «Test appen» i et Swift-prosjekt | Gå via eksisterende e2e-route, som avklarer plattform og hensikt. |
| «Ja, gjør det» etter en konkret avtale | Viderefør avtalen; ikke start en ny brainstorm. |
| «Hva gjør /ship?» | Forklar kommandoen; ikke tolk omtale som bestilling på levering. |
| Uttrykkelig navngitt ferdighet | Behold valget og avtalte aliaser; Jev overstyrer det ikke. |
| «Bare rett skrivefeilen» | Unngå en unødvendig kjede av plan- og review-ferdigheter. |
| Fjernet/ikke installert ferdighet, nettverksfeil eller tomt kandidatsett | Intet ugyldig forslag; dagens tillatte arbeidsflyt fortsetter. |
| Instruksjoner gjemt i et ferdighetsutdrag eller et sitat | Ingen endring av tillatelser eller omgåelse av faste kontroller. |

## Mulig pilot B: rådgivning i en aktiv økt, krever eget ja

Hvis pilot A viser nytte, kan en valgfri command-hook på `UserPromptSubmit` gi
Claude et kort forslag gjennom `hookSpecificOutput.additionalContext`.
Dette krever ny kode og ny registrering i hooks.json. Det finnes ikke i dagens
plugin. Hooken skal ikke selv kjøre ferdigheten, endre modell eller blokkere
brukerens melding. Bekreft kontrakten mot den faktisk installerte Claude-versjonen.

Eventuelle modi må holdes tydelig atskilt: av; observasjon som bare registrerer
forslag; rådgivning som også sender forslaget til agenten. Observasjon påvirker
fortsatt nettverksbruk og kan påvirke svartid; det er ikke en kostnadsfri modus.
Ingen automatisk overgang mellom modi basert på modellens egen vurdering.

**Praktiske grenser som må løses før pilot B:**

- Dokumentert aktivering per prosjekt og valg av hvilke data som kan sendes til
  en ny ekstern tjeneste. Ikke les inn hele samtalelogger, kode eller hemmeligheter
  som standard. Uavklart datagrunnlag betyr ingen ekstern forespørsel.
- Kort samlet frist for oppslaget, inkludert klientens gjentatte forsøk. Ved feil,
  manglende nøkkel, ukjent fase eller tidsavbrudd: ingen anbefaling og normal
  behandling av meldingen. Et tjenesteavbrudd betyr ikke «ingen ferdighet passer».
- Forslags-ID må slås opp i en godkjent lokal liste. Bygg tilleggsteksten fra en
  fast mal; ikke injiser rå dokumenttekst eller en oppdiktet modellforklaring.
  Jev returnerer strukturerte vurderinger, ikke en fri begrunnelse.
- Bufring må ta hensyn til melding, relevant samtalekontekst, prosjekt, fase,
  aktiv ferdighetskatalog, regler, terskler og modellversjon. Samme «fortsett» i
  to prosjekter eller faser er ikke samme spørsmål. Skill økter og arbeidskopier.
- Lagre bare nødvendige lokale måledata som standard: stabile ID-er, versjoner,
  valgte ruter, utfall, varighet og forbruk. Bevaring av råtekst krever et uttrykkelig
  valg. Ikke utled tillatelse til handling fra Jevs vurdering av brukerens hensikt.
- `UserPromptSubmit` dekker brukerens meldinger, ikke alle interne faseoverganger,
  underagenter eller verktøykall. Dagens ferdighetskjeder og kontrollpunkter må
  fortsatt ivareta disse overgangene. Mer omfattende automatikk er eget omfang.

## Forhold til adapt og senere utvidelser

Før en integrasjon må ruting ha en tydelig, versjonert kilde til sannhet. Avklarte
faste regler skal brukes av både vanlig ruting, evaluering og Jev-rådgiveren.
Samtidig må prosjektets egne unntak bevares; ikke bygg en ny mekanisme som
overskriver lokale CLAUDE.md-regler ved hver oppdatering.

Gjenbruk roster og aktive SKILL.md-filer fremfor en håndvedlikeholdt parallell
katalog. En lokal oversikt kan avledes og versjoneres. Verifiser at oppdateringer,
fjerning, navneendringer og eldre aktive pluginversjoner ikke gir ugyldige forslag.

Hvis Jev senere skal hjelpe adapt med et bredere utvalg ferdigheter, la den bare
foreslå relevante kandidater. Behold adapt sin avklaring med brukeren og skriptet
`adapt-claude-md.py` som skriver filene. Modellvalg og kontrollomfang krever egne
utprøvinger; lav kostnad alene er ikke et kriterium for å senke kvalitetskrav.

## Lokalt oppsett og kilder

Bruk `typesafe-ai`-ferdigheten. Den er installert i `~/.codex/skills/typesafe-ai`
og lenket fra `~/.claude/skills/typesafe-ai` på brukerens Mac. Python-klienten er
`typesafe-sdk`; `~/Developer/typesafe-playground` er et separat prøveprosjekt.
Ingen av disse lokale stiene skal bli en produksjonsavhengighet i pluginen.
API-bruk krever nøkkel, og ingen måling av Jev er utført i dette repoet.

TypeSafe beskriver ferdighetsvalg i to steg: ranger katalogen, les et lite utvalg
mer grundig og tillat at ingen velges. Deres publiserte forsøk bruker en annen
agent og katalog enn denne pluginen; det dokumenterer ikke gevinst her. Det viser
også at forslag kan gjøre noen ellers riktige valg feil. Bruk mønsteret som
hypotese, ikke kopier terskler eller forventede besparelser.

- [TypeSafe: ferdighetsforslag](https://docs.typesafe.ai/cookbooks/skill_suggestion)
- [TypeSafe: ruting etter hensikt](https://docs.typesafe.ai/patterns/intent-routing)
- [TypeSafe: kontekst](https://docs.typesafe.ai/concepts/state)
- [TypeSafe: usikkerhet](https://docs.typesafe.ai/confidence)
- [TypeSafe: kjente begrensninger](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- [Claude Code: UserPromptSubmit](https://code.claude.com/docs/en/hooks#userpromptsubmit)

## API-nøkkel på brukerens Mac

Nøkkelen finnes allerede i macOS-nøkkelringen på brukerens Mac:

- Tjeneste (`service`): `typesafe-api-key`
- Konto (`account`): `macbook-pro-local-dev`
- Miljøvariabel som TypeSafe-klienten leser: `TYPESAFE_API_KEY`

Hent nøkkelen ved kjøring og gi den bare til prosessen som trenger den. Ikke be
brukeren lime den inn i chatten eller opprette en ny nøkkel når denne virker.
Ikke skriv nøkkelen til terminalutdata, logger, kildekode eller `.env`-filer.
TypeSafe-ferdigheten henter ikke nøkkelen automatisk.

Eksempel som kjører det eksisterende prøveprosjektet med oppdiktet tekst:

```zsh
(
  set +x
  TYPESAFE_API_KEY="$(/usr/bin/security find-generic-password \
    -a "macbook-pro-local-dev" -s "typesafe-api-key" -w)" || exit 1
  [ -n "$TYPESAFE_API_KEY" ] || exit 1
  export TYPESAFE_API_KEY
  cd /Users/kjetilge/Developer/typesafe-playground || exit 1
  .venv/bin/python demo.py
)
```

Parentesene avgrenser miljøvariabelen til denne kjøringen. `set +x` hindrer at
skallet logger kommandoer med den utvidede nøkkelverdien. Ved oppslagsfeil eller
tom nøkkel stopper eksemplet før API-kallet. Når prosjektet får en egen integrasjon,
gi tilsvarende miljøvariabel til den prosessen; prøveprosjektet er ikke en
produksjonsavhengighet.

Oppføringen gjelder denne Mac-en. Ikke forutsett at nøkkelen finnes i en virtuell
maskin, på en annen maskin eller i CI (automatisk bygg og testing). Bruk miljøets
avtalte hemmelighetshåndtering der; ikke kopier brukerens nøkkel automatisk.

**Verifisert 2026-09-22:** nøkkelen ble hentet fra nøkkelringen, og ett kall med
oppdiktet norsk fakturatekst fikk HTTP 200 fra `jev-1.13.0` (505 input-token).
Dette bekrefter tilgang, ikke kvaliteten på prosjektets foreslåtte pilot.
Eksemplet ovenfor gjør et fakturerbart API-kall. Tilgjengelig nøkkel endrer ikke
forslagets beslutningsstatus eller avtalt omfang og forbruksramme.

## Beslutningslogg

- 2026-09-22: Forslaget utforsket og lagret etter brukerens ønske. Ingen pilot,
  API-evaluering eller endring i operativ ruting er godkjent eller gjennomført.
- 2026-09-23: Pilot A presentert for brukeren i interaktiv økt. Svar avventes.
