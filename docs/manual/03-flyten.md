---
nummer: 3
tag: Flyten
tittel: Fra idé til kode, steg for steg
aksent: violet
oppdatert: 2026-10-12
bruk: du vil vite hva som skjer mellom at du beskriver en idé og at koden er bygget
ferdig: du vet hva du får i hvert steg og hvor Claude stopper og venter på deg
---

### Først velger Claude hvor tungt det skal være

Når du beskriver en idé, starter Claude `superpowers:brainstorming` (skillen som gjør en idé om til et design før noe bygges). Før det første spørsmålet sier Claude høyt hvilken av tre stier den velger, så du kan si ifra hvis du er uenig. Er den i tvil, velger den den tyngste. Oppdager den underveis at oppgaven er større enn antatt, går den opp en sti og sier det. Den går aldri ned.

| Sti | Når | Hva du får | Hvor du sier ja |
|---|---|---|---|
| Spike (et billig forsøk) | Et gjennomførbarhetsspørsmål: «går det an å ...», «rask og skitten er greit» | Et svar og en anbefaling. Det Claude bygde underveis er kasteprodukt, ikke kode du beholder | Etter at Claude har lagt fram spørsmålet og forsøket i to–tre setninger. Et nikk holder |
| Bounded (avgrenset) | En liten endring i kode som allerede finnes i prosjektet: et flagg, et lite endepunkt, en rettelse i én fil | Et kort design i chatten, fra noen setninger til noen korte avsnitt. Ingen spec-fil og ingen plandokument | Etter det korte designet. Claude stopper til du har sagt ja |
| Architectural (arkitektonisk) | Nytt prosjekt, nytt delsystem, eller en endring som flytter på hvordan deler henger sammen | Spørsmål ett om gangen, to eller tre tilnærminger, design i deler, en skrevet spec og så en plan | Designet, den skrevne spec-en og planen (se under) |

Et nytt prosjekt har ingen eksisterende flyt å endre. Det er derfor alltid arkitektonisk, selv om det er en enkel liste-app. Resten av kapittelet følger den tyngste stien, for den inneholder de andre.

### Spec-en og forklaringssiden

Etter at du har godkjent designet i deler, skriver Claude det ned som en spesifikasjon (spec, et dokument som sier hva som skal bygges). Filen havner i `docs/superpowers/specs/` og heter `ÅÅÅÅ-MM-DD-<tema>-design.md`. Claude leser den selv først, for hull og selvmotsigelser, og ber deg så lese den.

Når spec-en er ferdig og Claude har lest den selv, lager `/superpowers-gstack:htmlify` en forklaringsside ved siden av spec-en, uten at du ber om det. Den er tegnet for hånd, med figurer og så lite tekst som mulig, slik at du forstår designet på to minutter og bare åpner dokumentet for detaljer. Hvor siden ligger, avgjør filen `.gstack/explainer` i prosjektet. Der står enten `local` (en HTML-fil ved siden av dokumentet) eller `artifact` (en side på claude.ai). Mangler filen, bruker den `local`. Det var `/superpowers-gstack:adapt` som spurte om dette i [kapittel 1](#k1). Les siden før du sier ja. Du godkjenner spec-en, og først da får Claude lov til å skrive planen.

### Planen

`superpowers:writing-plans` gjør spec-en om til en plan: små oppgaver som kan bygges og sjekkes hver for seg. Planen lagres i `docs/superpowers/plans/`, og får også en forklaringsside.

Så ber Claude deg lese planen og velge hvordan den skal kjøres. Du har to valg:

- Subagent-driven: en ny underagent bygger hver oppgave, og en ny gjennomleser sjekker den før neste oppgave starter. Til slutt leser en gjennomleser hele grenen. Grundigst, men koster en ny kontekst (samtalen modellen har foran seg) per oppgave og per gjennomlesing.
- Native: Claude bygger alle oppgavene selv i denne økten. Til slutt leser én ny gjennomleser på den sterkeste modellen hele grenen. Billigst og raskest, men ingen uavhengig gjennomlesing før til slutt.

Claude anbefaler ett av dem for akkurat denne planen, med en setning som begrunner det: hvor mye oppgavene avhenger av hverandres grensesnitt, hvor mange de er, og hva en feil i produksjon ville koste. Du kan følge anbefalingen eller velge det andre. Har du allerede sagt hvordan du vil ha det kjørt, spør Claude bare om planen er riktig. Valget bestemmer hvilken skill som tar over: `superpowers:subagent-driven-development` eller `superpowers:executing-plans`.

### Selve byggingen

Her gjør du ingenting. Dette er det som skjer, og hvilken skill som står bak:

- Én ny underagent per oppgave og en ny gjennomleser etter hver oppgave. Gjennomleseren sjekker både at oppgaven følger planen og at koden er god. Det er `superpowers:subagent-driven-development`.
- Testen skrives først. Ingen produksjonskode uten en test som feiler først. Det er test-drevet utvikling, og skillen heter `superpowers:test-driven-development`.
- Ett arbeidstre (worktree, en ekstra mappe med sin egen gren) per arbeidsoppgave, altså per gren du skal lande. Claude lager det med kommandoen under og går så inn i det, slik at alle kommandoer og skills kjører der. `--create` lager grenen, `--no-cd` flytter ikke terminalen din, og `--format=json` skriver ut stien til arbeidstreet slik at Claude kan gå inn i det.
- Commit (et lagret punkt i historikken) ved hvert ferdige delmål, ikke ved hver filendring og ikke bare ved slutten. Rett etterpå kommer `git push`, for en commit som ikke er sendt opp finnes bare på én disk.

```
wt switch --create feat/min-funksjon --no-cd --format=json
```

Navnet er `<type>/<tema>`: typen er for eksempel `feat`, `fix` eller `docs`, og temaet er det oppgaven handler om. Gjør Claude mer enn fem commits på rad uten å teste den samlede tilstanden, skal den stoppe og bygge og kjøre testene før den fortsetter.

Når alt er bygget, venter beviset. Det handler [kapittel 4](#k4) om.

> 💡 Du sier ja tre steder: designet og spec-en, planen og hvordan den kjøres, og når du har sett at det virker ([se kapittel 4](#k4)). Underveis committer og sender Claude ved hvert delmål, og samlet tilstand testes senest etter fem commits.
