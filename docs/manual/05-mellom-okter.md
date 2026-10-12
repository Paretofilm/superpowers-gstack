---
nummer: 5
tag: Mellom økter
tittel: Ikke mist tråden
aksent: amber
oppdatert: 2026-10-12
bruk: konteksten er lang, du skal skrive /clear, eller du kommer tilbake til et prosjekt etter en pause
ferdig: neste økt åpner med et banner som sier hvor du slapp, og du vet hvilken fil som bærer tråden
---

![[okt-tidslinje.svg]]

### Hva som går tapt

Claude husker bare det som står i konteksten (samtalen den har foran seg akkurat nå). `/clear` tømmer den helt. `/compact` presser den sammen til et kort sammendrag, og detaljer forsvinner. Begge er vanlige kommandoer i Claude Code, ikke deler av denne pluginen.

Det som ligger i filer på disken, forsvinner ikke. Derfor bæres tråden av to filer i prosjektet:

- `docs/superpowers/handoff.md` er overleveringsfilen (handoff). Den sier hva du holdt på med og hva det neste steget er. Den er ment å leses én gang og så tømmes.
- `progress.md` i mappen `docs/superpowers/plans/` er den rullerende framdriftsfilen. Den blir stående og viser hva som er ferdig og hva som gjenstår.

Du skriver overleveringsfilen med `/superpowers-gstack:context-handoff` (skillen som skriver ned hvor du er) før du skriver `/clear`. Skillen lagrer tilstanden og stopper. Den svarer med at du kan skrive `/clear`, og at Claude plukker opp tråden selv. Filen skal ligge i hovedmappen til prosjektet og ikke i et arbeidstre ([se kapittel 6](#k6)), fordi arbeidstreet slettes etter landing og tar filer som ikke ligger i git med seg.

### De fire tilstandene til handoff.md

Når en økt begynner, eller etter `/compact`, ser Claude på `handoff.md` og avgjør hva slags fil det er før den rører den. Å bruke opp en overleveringsfil tømmer den, så en feil vurdering ødelegger det som lå der.

| Tilstand | Hva Claude gjør | Hva du gjør |
|---|---|---|
| Tom, eller bare mellomrom | Sier ingenting. Dette er hvilestillingen etter at en overlevering er brukt | Ingenting |
| Stubb med `mode: continuous` og uten `next_step` | Sier ingenting og lar filen stå urørt. Kontinuerlig overlevering regnes som påslått | Ingenting |
| Fullstendig overlevering: `type: handoff` og et brukbart `next_step` | Kopierer filen til `docs/superpowers/.handoff-last.md`, sier i én linje hvor du slapp, siterer `next_step` ordrett og tømmer filen (unntaket står under). Så fortsetter den uten å spørre om du er klar | Ingenting. Sier fra hvis den peker feil vei |
| Alt annet: mangler `next_step`, er avkuttet midt i, eller har ingen frontmatter | Presenterer den ikke og tømmer den ikke. Sier i én linje at filen ikke kan brukes | Står det egne notater i den, flytt dem først. Så sletter du filen, eller overskriver den med `/superpowers-gstack:context-handoff` |

Frontmatter er blokken med felt øverst i filen, mellom to linjer med `---`. `next_step` er én setning med et konkret verb, helst med fil og linje, for eksempel `Read src/auth/session.ts:45-78, decide middleware vs hook`. Står det bare «fortsett med innloggingen», er den ikke god nok.

En halvskrevet overlevering tømmes aldri. Minst ett prosjekt har brukt stien til egne, varige notater, og en automatisk lesing som tømte dem, ødela notatene. Kopien i `.handoff-last.md` gjør en feilvurdering mulig å rette opp.

Én unntaksregel gjelder en fullstendig overlevering (`type: handoff` og `next_step`) som også har `mode: continuous`. Claude kopierer og bruker den som vanlig, men tømmer den ikke helt. Den skriver den om til en stubb med bare `type: handoff` og `mode: continuous`, slik at valget overlever til neste `/compact`. Finner Claude senere en slik stubb, lar den den stå urørt (andre rad i tabellen). Ellers ville Claude spurt om det samme igjen og igjen. Kontinuerlig overlevering betyr at Claude oppdaterer `handoff.md` etter hvert viktige delmål og foreslår `/clear` når konteksten blir tung. Etter en `/compact` spør Claude én gang om du vil ha det, og spør ikke igjen ved senere `/compact`. Kontinuerlig overlevering har ingenting med Claude Codes auto-modus for tillatelser å gjøre: den styrer bare hvor ofte filen skrives.

### Banneret ved oppstart

Før du har skrevet noe, kan økten åpne med en blokk som heter «Where this project left off» (på engelsk, slik skriptet skriver den). Den skrives av en hook (et lite skript som Claude Code kjører av seg selv ved en bestemt hendelse) som heter `scripts/session-resume.sh`. Den kjører når en økt starter, og når den starter etter `/clear`. Den leser tre kilder, og viser bare det som finnes:

- `progress.md`: tittelen, hvor mange faser som er ferdige, hva som står først under «Gjenstår», og datoen filen sist ble endret.
- `handoff.md`: bare hvis det er en fullstendig overlevering, og da med `next_step`.
- Siste-økt-opptaket (se under): de første 200 tegnene av Claudes siste melding, hvorfor og når forrige økt sluttet, og hvilken gren du var på. Din egen siste melding vises ikke i banneret.

Banneret leser bare. Det tømmer ikke noe, og klassifiseringen i tabellen over er fortsatt Claudes jobb. Finnes ingen av de tre kildene, sier banneret ingenting. Teksten går både til deg og inn i det Claude ser, så du får bevis på at tilstanden overlevde, og Claude vet hvilke filer den skal lese videre i.

### Opptaket når en økt slutter

Skriver du `/clear` uten å ha skrevet en overlevering først, er det ingen modell igjen som kan oppsummere. Derfor finnes en hook som kjører når økten slutter: `scripts/capture-session-tail.sh`. Den bruker ikke Claude. Den leser de siste meldingene fra utskriften av økten på disken og tar vare på den siste fra deg og den siste fra Claude (hver kuttet til omtrent 700 tegn), grenen, siste commit og hvor mange filer som ikke er committet.

Opptaket legges i git-mappen (`.git`) som `gstack-last-session.md`, ikke i selve prosjektet. Utskrifter kan inneholde hva som helst, og en fil utenfor prosjektmappen kan ikke bli committet ved en feil. Hooken gjør ingenting i prosjekter uten mappen `docs/superpowers/`. Opptaket inneholder begge meldingene, men banneret i neste økt viser bare begynnelsen av Claudes.

### Lange prosjekter

Er oppgaven for stor til én økt, holder du en rullerende `progress.md`. Den har fire deler: Meta (arbeidsmappe og hvordan testene kjøres), Ferdig (hver fase med commit og hva den ble verifisert med), Lærdom (fellene neste fase bør kjenne) og Gjenstår.

Et ekte eksempel er `docs/superpowers/plans/progress.md` i prosjektet sing-replay, «Framdrift — mobilversjonen». Filen sier at grenen `ios-mobilversjon` har 13 commits, og at siste testkjøring ga 435 grønne tester på macOS og 417 på iOS, mot 387 og 369 i starten. Filen daterer ikke selve testkjøringen. Den nyeste datoen den nevner er 16. august 2026, da fase 3 ble levert i commiten `65774b4`. Fase 0 til 3 står som ferdige, og det som gjenstår krever en ekte telefon. Tabellen under «Ferdig» har én rad per levert del. Her er et utdrag på tre av radene:

| Fase | Oppgave | Commit |
|---|---|---|
| 0 | Oppstartsskjerm | `4eb140f` |
| 2 | Delt søyle-geometri, bølgeform og lyd i takt | `c5268b2` |
| 3 | Oppgave 8, 9, 10 og personvern-rettelsen | `65774b4` |

Den som åpner prosjektet igjen, enten du, en ny økt eller en underagent ([se kapittel 6](#k6)), slipper å lete opp hvor arbeidet står. Filen oppdateres og committes etter hver fase.

> 💡 Før `/clear` skriver du `/superpowers-gstack:context-handoff`, og neste økt åpner med et banner som sier hvor du slapp. Claude tømmer aldri en fil den ikke kjenner igjen som en fullstendig overlevering.
