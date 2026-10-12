---
nummer: 1
tag: Kom i gang
tittel: Start fra en tom mappe
aksent: cyan
oppdatert: 2026-10-12
bruk: du har en tom mappe og vil til første endring på hovedgrenen
ferdig: den første endringen ligger på main og er sendt til GitHub
---

### Før du begynner

Du trenger Claude Code, de to rammeverkene Superpowers og GStack og denne pluginen. Installasjonen står i README.md under «Kickstart». Du trenger også `gh` (GitHubs kommandolinjeverktøy, logget inn med `gh auth login`) og `wt` (worktrunk, verktøyet som lager og rydder arbeidstrær). Sjekk begge med `gh auth status` og `wt --version`.

### Fra tom mappe til første landing

Hver kommando under er komplett og kan limes inn. Navnet `min-app` kan du bytte ut.

1. Lag mappen med `mkdir min-app`.
2. Gå inn i den med `cd min-app`.
3. Gjør den til et git-prosjekt med `git init -b main`. Grenen heter main (grenen alt det ferdige samles på).
4. Start Claude Code i mappen med `claude`.
5. Skriv `/superpowers-gstack:adapt` i Claude Code. Skillen (en ferdig arbeidsmåte Claude laster inn) setter opp prosjektet og stopper tre ganger for å spørre deg.
6. Første stopp: i en tom mappe spør adapt om prosjekttype, testverktøy, hvor det skal kjøre ut, om det har nettleser-grensesnitt, sikkerhetshensyn og plattform for en Apple-app. Den oppsummerer og spør «Is this correct?»
7. Andre stopp: adapt viser hvilke skills den velger og en følsomhetsgrad for prosjektet, og spør «Does this look right?» Svar ja, eller si hva som skal endres.
8. Underveis spør adapt om arbeidsmåte, og foreslår Vibe. Velg Classic for å følge dette kapittelet. Vibe gir én spørsmålsrunde og låste akseptansetester som eneste sjekkpunkt, og Claude bygger resten selv med `/superpowers-gstack:vibe` ([se kapittel 0](#k0)).
9. Adapt spør også om filer utenfor git, og hvor forklaringssiden etter hver spec og plan skal ligge: lokal fil eller Artifact-side på claude.ai.
10. Tredje stopp: adapt viser hva den vil endre og spør «Shall I proceed with these changes?» Svar ja. Den skriver CLAUDE.md og lager mappene `docs/superpowers/specs/` og `plans/`.
11. La Claude Code stå, og åpne et vanlig terminalvindu i samme mappe (`min-app`) for de neste fire kommandoene.
12. Legg til landingsvalget med `printf '\n## Prosjektvalg\n\nLanding mode: solo\n' >> CLAUDE.md`. Solo betyr at ferdig arbeid lander rett på main etter lokale sjekker, uten pull request (en forespørsel om gjennomgang på GitHub). Velger du gjennomgang, bruk `pr` og senere `/ship`.
13. Lagre oppsettet med `git add CLAUDE.md docs .gstack`.
14. Lag det første commit-et (et lagret punkt i historikken) med `git commit -m "chore: adapt"`.
15. Lag fjernlageret på GitHub og send det opp med `gh repo create min-app --private --source=. --push`. Flaggene betyr: privat, bruk denne mappen, send commit-ene.
16. Gå tilbake til Claude Code-vinduet.
17. Beskriv den første funksjonen i én setning, for eksempel «lag en side som viser dagens dato».
18. Claude starter `superpowers:brainstorming`. En tom mappe har ingen eksisterende flyt, så Claude behandler det som stor oppgave: spørsmål ett om gangen, to eller tre tilnærminger, design i deler.
19. Ja nummer 1: du godkjenner designet. Claude skriver en spesifikasjon (spec) i `docs/superpowers/specs/`, og du leser og godkjenner den.
20. Ja nummer 2: Claude skriver en plan med små oppgaver. Du leser den og velger hvordan den kjøres.
21. Claude bygger i et eget arbeidstre (worktree, en ekstra mappe med sin egen gren) og committer underveis. Du gjør ingenting.
22. Ja nummer 3: du ser at det virker. Er det en app, bygger og starter `/superpowers-gstack:verify-and-land` akkurat denne grenen, og ditt ja lander den.
23. Vil du lande direkte, skriv `/superpowers-gstack:land` i arbeidstreet. Skillen kjører prosjektets sjekker, flytter main fremover og sender til GitHub.
24. Første gang mangler prosjektet en `pre-merge`-sperre (sjekkene som må være grønne før noe lander, i `.config/wt.toml`). Land stopper da, og Claude foreslår en som kjører de samme kommandoene som testene dine. Du godkjenner forslaget.
25. Så må kontrollene godkjennes en gang: `wt config approvals add` må kjøres i et ekte terminalvindu, for den spør deg om å si ja. Land skriver ut den nøyaktige kommandoen med riktig sti. Har du Calyx (terminalprogrammet Claude kan åpne faner i), kan Claude åpne en fane der du svarer selv.

### Hva CLAUDE.md inneholder etter adapt

CLAUDE.md er prosjektets husregler til Claude. Adapt legger inn rutingstabellen (hvilken skill som kjøres når), regler for commit og push, flerlinse-gjennomgang (flere modeller leser det ferdige), gjenbruk av kode, at planen skal følge koden, overlevering mellom økter og arbeidstrær med solo-landing. Har du valgt vibe, kommer en egen vibe-kontrakt. Alt står i seksjoner med en merkelapp som adapt eier. Dine egne valg skriver du i egne seksjoner, som `## Prosjektvalg` over, så skriver ikke neste adapt over dem.

### Hvis noe stopper

Land forklarer hvert stopp med en kode. De tre du oftest treffer første gang:

| Kode | Hva det betyr | Hva du gjør |
|---|---|---|
| 2 | Linjen `Landing mode:` mangler, eller sier `pr` | Mangler den, spør Claude deg og skriver den på main, som i trinn 12. Sier den `pr`, bruk `/ship` |
| 9 | Prosjektet har ingen `pre-merge`-sperre i `.config/wt.toml` | La Claude foreslå en som kjører de samme kommandoene som CI (automatiske tester på GitHub), og godkjenn den |
| 3 | Kontrollene er ikke godkjent ennå | Kjør `wt config approvals add` i et ekte terminalvindu, svar ja der, og kjør land på nytt |

Finnes ingen sperre, lander ingenting. Kode 6 betyr at en sjekk feilet: rett feilen og land på nytt, aldri hopp over sjekken.

> 💡 Land lander bare når prosjektet selv har sagt `Landing mode: solo` på main og har en `pre-merge`-sperre. Det er sjekkene som erstatter gjennomgangen, så de hoppes aldri over.
