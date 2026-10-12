---
nummer: 9
tag: Anbefalt
tittel: Verktøy du ikke bruker, men burde
aksent: amber
oppdatert: 2026-10-12
bruk: du vil vite hvilke verktøy som finnes, men som du så godt som aldri starter
ferdig: du har valgt ett verktøy å prøve, og du vet hvordan du måler om det ble en vane
---

### Råd, ikke vane

Dette kapittelet er et råd, ikke en beskrivelse av hvordan du jobber. Verktøyene under er ferdige og virker, men i loggene dine ble de brukt lite eller ikke i det hele tatt. Hvert tall er et øyeblikksbilde: målt 10. oktober 2026 i seks prosjekter, 61 hovedøkter, fra Claude Code-transkripter (loggene Claude Code skriver av hver samtale) fra og med 15. september. Tallene sier hva som skjedde i den perioden. De sier ikke at verktøyene er dårlige, og de blir gamle. Hvordan du måler på nytt, står nederst.

### Verktøyene

Kolonnene «Hva det fanger» og «Bruk det når» er hentet fra verktøyets egen skill-fil (skill er en ferdig arbeidsmåte Claude laster inn). Tallene er antall kall i målingen: Skill-verktøyet og slash-kommandoer du skrev selv.

| Verktøy | Hva det fanger | Bruk det når | Brukt (målt 10. okt) |
|---|---|---|---|
| `superpowers:verification-before-completion` | At Claude sier «ferdig», «rettet» eller «består» uten at kommandoen som beviser det er kjørt og utskriften lest | Rett før noe kalles ferdig, rettet eller bestått, og før commit eller pull request | 0 |
| `/qa` | Feil i nettleser, API, kommandolinje, jobber og webhooks (anrop andre tjenester sender til programmet). Hver bekreftede rettelse blir en egen commit | Du sier at en funksjon er klar til å testes, eller vil ha «test og rett» | 0 |
| `/ios-qa` | Feil i en iPhone- eller iPad-app, funnet ved at Claude trykker gjennom appen på en ekte enhet koblet til med USB | Du vil teste SwiftUI-appen på en ekte telefon eller et ekte nettbrett | 0 |
| `/investigate` | Gjetting. Fire faser: undersøk, analyser, still en hypotese, rett. Regelen er at ingenting rettes før årsaken er funnet | Noe feiler, du får en feilmelding eller en stakk-trace (utskriften som viser hvor i koden det gikk galt), eller noe som virket i går ikke virker nå | 3 |
| `/superpowers-gstack:quality-review` | Det som får et produkt til å kjennes billig: stille feil, manglende lasting og tomme tilstander, dårlig feilhåndtering | En spec eller plan er ferdig, før noe bygges ([se kapittel 7](#k7)) | 1 |
| `/superpowers-gstack:spec-drift` | At en plan ikke lenger stemmer med koden. Gir en rapport, et tall-sammendrag og en utgangskode, og endrer aldri kode | Du vil vite om en plan fortsatt stemmer på en gren som ikke sendes ut med `/ship` | 0 |
| `/retro` | Hva som ble levert i uka, regnet ut fra commit-historikken, med trend over tid | Slutten av en uke eller en periode | 0 |
| `/health` | Kodens tilstand. Kjører prosjektets egne verktøy for typesjekk, lint (verktøy som finner slurv i koden) og tester, og gir en samlet poengsum fra 0 til 10 som følges over tid | Du vil ha et tall på hvor sunn koden er | 0 |
| `/document-release` | At dokumentasjonen ikke følger med det som ble sendt ut: leser dokumentene mot endringen, oppdaterer README og CLAUDE.md og pusser endringsloggen | Etter en utsending, og før en pull request slås sammen | 0 |
| `/superpowers-gstack:e2e-scaffold` | Mangel på UI-tester i en Apple-app. Lager grunnlaget for dem og endrer prosjektfiler, så den kjører bare når du ber om det ([se kapittel 7](#k7)) | Appen har ingen UI-test, og du vil låse en test som skal vare | 0 |
| `/superpowers-gstack:swiftui-design-consultation` | At utseendet i et SwiftUI-prosjekt ikke er skrevet ned og sjekket. Du får et forslag som side, og først når du godkjenner, skrives `DESIGN.md` og en Swift-pakke `DesignSystem/`, som så sjekkes mot Apples HIG med en grense du velger for hvor mange funn som er greit ([se kapittel 7](#k7)) | Du starter eller friske opp designsystemet i et SwiftUI-prosjekt | 0 |

Til sammenligning ble disse brukt mest i samme måling: `/superpowers-gstack:pitfall-verification` 39 ganger, `/superpowers-gstack:third-lens-review` 27, `/review` 27 og `superpowers:brainstorming` 23 (målt 10. oktober 2026).

### Hvor tallene peker

Tallene viser et mønster. Kontrollene som leser koden og planen, brukes ofte: feller-sjekken, det tredje modellhuset og `/review`. Verktøyene som kjører programmet eller ser på resultatet, brukes lite eller aldri: `/qa` og `/ios-qa`. Det samme gjelder `superpowers:verification-before-completion`, som krever at beviset er kjørt før noe kalles ferdig. Det passer med [kapittel 4](#k4): tester sier at ingenting annet gikk i stykker, og bare en kjøring du har sett sier at rettelsen er rettet.

Du trenger ikke ta alle. Velg ett som passer det du holder på med nå. Bygger du en nettside eller et Python-program ([se kapittel 8](#k8)), prøv `/qa` neste gang en funksjon er klar. Bygger du en Apple-app, prøv `/superpowers-gstack:e2e-scaffold`.

### Mål selv

Vil du vite om det ble en vane, eller om tallene over fortsatt stemmer, skriv `/superpowers-gstack:workflow-metrics` i Claude Code. Du kan legge til et prosjektnavn og en dato for en endring, for eksempel `/superpowers-gstack:workflow-metrics sing-replay 2026-10-01`. Skillen kjører et skript som leser transkriptene på disken og teller én gang per kall til modellen. Den rapporterer disse målingene:

- `asks`: hvor mange strukturerte spørsmål Claude stilte, hvor mange du svarte på med det anbefalte alternativet, og hvor lenge Claude jobbet mellom meldingene dine.
- `tokens`: antall kall til modellen i hovedsamtalen og hos underagenter, og hvor mye som ble skrevet ut, og hvor mye kontekst som ble gjenbrukt og skrevet.
- `overhead`: hvor mye av konteksten som er grunnlast, og hvor mye som brukes over 150 000, 200 000, 300 000 og 500 000 tokens.
- `triggers`: hvilke bygg og testkjøringer som skjedde, hvor lenge de tok og hvem som ba om dem.
- `skills`: hvilke skills som er listet hver runde, og hvilke som aldri ble brukt. Det er denne som viser om et verktøy fra tabellen er blitt tatt i bruk.
- `mcp`: kall per MCP-server og prosjekt (MCP er standarden som kobler verktøy til Claude).
- `digest`: en kortfattet tidslinje over én økt, eller de lengste øktene.

Skillen vil ha et før og et etter. Du velger tidspunktet for endringen, og den kjører hver måling to ganger for samme prosjekt. Er det færre enn omtrent ti økter på en av sidene, er det en anekdote og ikke et tall du kan bygge på. Transkripter slettes etter 30 dager som standard (innstillingen `cleanupPeriodDays` i `~/.claude/settings.json`), så en ny måling ser bare de siste ukene med mindre du har hevet den.

> 💡 Du bruker mest tid på å sjekke at det er riktig, og minst på å se at det virker.
