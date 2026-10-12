---
nummer: 2
tag: Beslutning
tittel: Hva kjører jeg nå?
aksent: violet
oppdatert: 2026-10-12
bruk: du vet hvor du er, men ikke hvilken kommando som passer
ferdig: du har én kommando å skrive
---

![[hva-na.svg]]

### Slik bruker du tabellen

Finn raden som ligner mest på situasjonen din, og skriv kommandoen i midtkolonnen. Radene følger rutingreglene i `CLAUDE.md` i dette prosjektet (rutingreglene er tabellen Claude leser for å velge skill). Der en kommando starter med `/superpowers-gstack:` er den en skill fra denne pluginen. `superpowers:` er en skill fra Superpowers, og de andre er fra GStack. Vil du se hele flyten først, finnes den i [kartet](#k0).

| Situasjon | Kjør | Hvorfor |
|---|---|---|
| Feil, krasj eller «hvorfor virker ikke dette» | `/investigate` | Finner årsaken før noe rettes |
| Ny idé du vil bygge, i et prosjekt med arbeidsmåten classic | `superpowers:brainstorming` | Claude stiller spørsmål og lager et design før noe bygges |
| Ny funksjon i et prosjekt med arbeidsmåten vibe | `/superpowers-gstack:vibe` | Én spørsmålsrunde, så bygger Claude ferdig og lander |
| Du lurer på om ideen er verdt å bygge | `/superpowers-gstack:office-hours-track-aware` | Pakker inn GStacks `/office-hours` og legger designdokumentet i `docs/` |
| En spec (spesifikasjon) er nettopp skrevet | `/superpowers-gstack:pitfall-verification` | Leter etter feller i spesifikasjonen |
| En plan er nettopp skrevet | `/superpowers-gstack:quality-review` | Spør om resultatet vil føles bra, i tillegg til om det virker |
| Spec eller plan for en Apple-app | `/superpowers-gstack:apple-native-review` | Sjekker mot Apples designretningslinjer (HIG) før noe bygges |
| Du vil se en spec eller plan som figurer | `/superpowers-gstack:htmlify` | Lager en forklaringsside med så lite tekst som mulig |
| Planen er ferdig og skal bygges uten at du følger med | `/superpowers-gstack:autoimplement` | Én underagent per fase, med gjennomgang mellom fasene |
| Plan og kode kan ha gått fra hverandre | `/superpowers-gstack:spec-drift` | Sammenligner planen med koden og rapporterer, uten å endre noe |
| Du har rettet noe, men ser det ikke i appen | `/superpowers-gstack:verify-and-land` | Bygger og starter akkurat denne grenen, så du ser om rettelsen er der |
| Ferdig arbeid i et prosjekt uten gjennomgang | `/superpowers-gstack:land` | Kjører prosjektets sjekker og lander på main |
| Ferdig arbeid i et prosjekt med gjennomgang | `/ship` | Tester, gjennomgang og pull request |
| Du vil teste en Swift-app gjennom grensesnittet | `/superpowers-gstack:e2e-route` | Velger riktig kjøremåte for ende-til-ende-test |
| Konteksten er lang, eller du skal skrive `/clear` | `/superpowers-gstack:context-handoff` | Skriver ned hvor du er, så neste økt kan fortsette |
| Du kommer tilbake til et prosjekt | `/context-restore` | Henter tilbake det du lagret med `/context-save`. Har prosjektet en overleveringsfil, viser startbanneret hvor du slapp |
| Sikkerhetskritisk kode: innlogging, nøkler, betaling | `/cso` | Sikkerhetsrevisjon av koden |

> 💡 Velg raden for der du er nå, ikke den du håper å komme til. Hver rad er ett steg på kartet, og Claude tar resten av steget selv.
