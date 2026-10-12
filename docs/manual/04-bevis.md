---
nummer: 4
tag: Bevis
tittel: Når kan du stole på resultatet?
aksent: emerald
oppdatert: 2026-10-12
bruk: noe er bygget, og du vil vite om du kan stole på det før det lander
ferdig: du vet hvilke kontroller som har kjørt, og du har sett det virke selv
---

![[verifiseringskjeden.svg]]

### Tre nivåer, regnet ut av en maskin

`/superpowers-gstack:pitfall-verification` (skillen som leter etter feller) er ikke én gjennomgang. Hvor mange kontrollører som leser koden, avhenger av hvor mye som står på spill. Jo høyere nivå, jo flere modellhus (selskaper med hver sin opplæring, og dermed hver sine blindsoner) leser den.

| Nivå | Hva det gjelder | Hvem leser |
|---|---|---|
| Trivielt | Dokumentasjon, skrivefeil, kommentarer, kun nye tester, midlertidige lagringspunkter | Claude selv, i opptil to runder |
| Ship-worthy (verdt å sende ut) | Nytt versjonsnummer, ny linje i endringsloggen, `feat` (ny funksjon), `fix` (rettelse) eller `refactor` (omskriving) som endrer hva programmet gjør, eller endringer i det andre er avhengige av, som API-er (grensesnitt programmer snakker med hverandre gjennom) og filformater | Claude selv, så Codex (OpenAIs modell) gjennom `/review` |
| High-stakes (høy innsats) | En ship-worthy endring som i tillegg rører arkitektur, sanntid, sikkerhet, kontrakter eller migrering av data | Alle over, så et tredje modellhus |

Trivielt stopper etter Claudes egen sjekk. Når Codex eller det tredje huset har kjørt, kommer en adversariell syntese (en sammenslåing som er bygget for å være uenig). Reglen er at et funn regnes som reelt helt til noen har motbevist det med en begrunnelse. Uenighet mellom modellene er selve signalet, så den glattes ikke ut.

Nivået regnes ut, ikke gjettes. Skriptet `scripts/classify-change.py` leser endringen (filstier, nye linjer, størrelse) og skriver ut et gulv: det laveste nivået endringen kan få. Claude kan gå høyere hvis den mener endringen er farligere enn skriptet kan se. Den kan aldri gå lavere. Med `--assert-tier` får den et nei (utgangskode 1) hvis den prøver, og skriptet sier hvilke signaler den hoppet over. Mangler skriptet eller feiler det, regnes endringen som ship-worthy som minimum. Dette skjer uten at du blir spurt, og prisen rapporteres etter hvert kall.

Kjører ikke Codex av en eller annen grunn, for eksempel fordi den ikke er logget inn, bytter `/review` stille til en Claude-underagent. Det er samme modellfamilie. Skillen leser derfor en statuslinje og skriver `lens 2 absent` (kontroll nummer to mangler) i dommen, i stedet for å late som Codex var med. Skillen regner da ship-worthy-nivået som ikke oppfylt og kaller det tredje modellhuset inn som utenforstående lesning, selv på en endring som ikke har høy innsats.

### Et tredje modellhus kan ikke se alt

Det tredje modellhuset kjøres av `/superpowers-gstack:third-lens-review`, som du vanligvis ikke starter selv. Pitfall-verification kaller den automatisk på høy innsats, og også når Codex ikke har kjørt (se over). Hvilken modell den bruker, avhenger av rollen: Zhipu for arkitektur og DeepSeek for logikk, begge gjennom OpenRouter (en tjeneste som videreformidler til flere modellselskaper), og OpenAI gjennom `codex`-programmet for å motbevise Claudes egne avgjørelser.

Advarsel: Zhipu- og DeepSeek-modellene i det tredje huset kjører på ikke-vestlig infrastruktur. Koden og dataene som håndterer innlogging, nøkler, helse eller økonomi skal derfor bare leses av Claude selv og Codex, og aldri sendes til det tredje huset. Et eksempel er KvitteriAi, som håndterer fakturaer: selve fakturahåndteringen er økonomimateriale og hører til de to første kontrollene, Claude og Codex. Kildene sier at det tredje huset starter av seg selv på høy innsats, og at slikt materiale skal holdes til Claude og Codex. Regelen gjelder like mye når Codex mangler, men da kaller skillen likevel det tredje huset inn på en vanlig ship-worthy endring, så en fakturarettelse kan nå Zhipu eller DeepSeek uten at noe er høy innsats. Kildene sier ingenting om en bryter for dette. Før du starter kontrollen på slik kode, sjekk derfor at Codex er logget inn og tilgjengelig, eller si til Claude at den skal holde seg til de to første kontrollene. Dette er en beskjed til Claude, ikke en innstilling.

### Se at det virker

Tester svarer på om noe annet gikk i stykker. De svarer ikke på om det du rettet faktisk er rettet. Det må noen se.

`/superpowers-gstack:verify-and-land` bygger grenen du står på, starter akkurat den appen og viser på skjermen hvilken bygging som kjører. Så spør den om rettelsen er der. Grunnen er en vanlig felle: åpner du appen ved navn, starter macOS kopien i `/Applications`, som er forrige utgivelse, ikke grenen din. Mange konkluderer da at rettelsen ikke virket, når de egentlig så en gammel bygging. Skillen er laget for macOS-apper og iOS-simulator, og har en kortere vei for utviklingsservere på nett. Er det ikke en app (et bibliotek eller et kommandolinjeverktøy), nekter den og sier at du bør kjøre testene.

Har du endringer som ikke er committet, ber skillen deg committe først. Ellers ville du godkjent noe annet enn det som lander. Svarer du ja, lander grenen slik prosjektet har bestemt, uten et nytt spørsmål ([se kapittel 0](#k0)).

`superpowers:verification-before-completion` er en annen sikring, og den er anbefalt, ikke vane: i loggene fra seks prosjekter ble den brukt 0 ganger (målt 10. oktober 2026). Regelen er: ingen påstand om at noe er ferdig, rettet eller består uten at kommandoen som beviser det er kjørt i samme melding, med utskriften lest. Beviset kommer før påstanden.

### Landing

Hvordan ferdig arbeid lander, avgjør prosjektets egen linje i CLAUDE.md: `Landing mode: solo` eller `Landing mode: pr`.

- `solo`: `/superpowers-gstack:land` kjører prosjektets lokale sjekker, flytter main fremover (fast-forward, uten ny sammenslåings-commit) og sender til GitHub. Ingen pull request.
- `pr`: `/ship` kjører testene, kjører gjennomgang og lager en pull request (en forespørsel om gjennomgang på GitHub).

Sjekkene i `.config/wt.toml` (pre-merge-sperren) er det som erstatter gjennomgangen når ingen andre leser, så de hoppes aldri over. Land bruker ikke `--no-hooks` eller `--yes`. En rød sjekk rettes, og land kjøres på nytt. Mangler prosjektet sperren, lander ingenting før du har godkjent en. De vanligste stoppkodene fra land står i [kapittel 1](#k1).

> 💡 Du kan stole på resultatet når nivået er regnet ut, kontrollørene har lest det, og du selv har sett akkurat den bygde versjonen virke. Sjekkene før landing hoppes aldri over.
