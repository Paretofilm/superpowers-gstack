---
nummer: 6
tag: Under panseret
tittel: Hva skjer bak kulissene
aksent: magenta
oppdatert: 2026-10-12
bruk: du lurer på hvorfor en fil, en mappe eller en melding dukker opp uten at du ba om den
ferdig: du vet hvem som ser hva, hvor arbeidet bor mens det pågår, og hvilke skript som kjører av seg selv
---

![[subagent.svg]]

### Subagenter ser ikke samtalen din

En subagent er en egen Claude-instans som får én oppgave. Den arver ikke samtalen din. `superpowers:subagent-driven-development` sier det rett ut: subagenter skal aldri arve økten din, og Claude bygger selv nøyaktig det de trenger. Det holder dem på sporet, og det sparer plassen i hovedsamtalen. Prisen er at det de trenger å vite fra før, må stå i oppgaveteksten eller i en fil på disken.

Derfor finnes `progress.md` ([se kapittel 5](#k5)). I et langt prosjekt er den filen det som forteller en ny instans hvor arbeidet står, uten at noen må gjenfortelle historien. Samtalen blir borte når konteksten tømmes. Filen blir.

### Modellvalg: råd, ikke tvang

Når du kjører `/superpowers-gstack:adapt`, kan den skrive en seksjon som heter «Model Routing» inn i prosjektets `CLAUDE.md`. Seksjonen er en rådgivende tabell: for hver skill står det hvilket nivå av modell (fra den enkleste til den kraftigste) en subagent bør få. Nivået justeres etter hvor stille en liten feil kan vokse i prosjektet. I lyd i sanntid, innlogging og migrering av data veier risikoen tyngre enn prisen. Claude i hovedsamtalen leser tabellen når den deler ut oppgaver, så den er et råd til den, ikke en lås. Sier du nei til seksjonen når `adapt` spør, får du den ikke. Konkrete modellnavn og priser står ikke i manualen, for de endres.

`/model` er en egen kommando i Claude Code, og den bytter modell for hovedsamtalen din. Tabellen over styrer bare subagentene.

### Ett arbeidstre per oppgave

![[worktree.svg]]

Et arbeidstre (worktree) er en ekstra mappe med sin egen gren, hentet fra samme git-prosjekt. Slik brukes de her:

- Hver oppgave får sitt eget arbeidstre, så du kan ha flere i gang uten å bytte gren i en mappe.
- En gren kan bare stå i ett arbeidstre om gangen. Prøver du å sjekke den ut et annet sted, nekter git.
- Alle mappene deler ett stash (et gjemmested for halvferdige endringer). En parallell økt som tømmer det, tar med seg dine endringer, og det blir aldri sendt til GitHub. Bruk derfor aldri `git stash`. Skal du bytte oppgave, la det halvferdige ligge der det er og åpne et nytt arbeidstre.
- Landing er en fast-forward: `main` flyttes fremover langs grenens commits, uten en ny sammenslåings-commit. Det gjør `/superpowers-gstack:land`, som først kjører prosjektets sjekker ([se kapittel 4](#k4)).
- Etterpå fjerner du arbeidstreet, så grenen. Rekkefølgen er `git worktree remove <sti>`, så `git branch -d <gren>`. Snur du den, nekter git. Bruk aldri `git branch -D` for å komme rundt en nektelse: den nektelsen er sikringen mot å miste commits som ikke er landet.

### Skript som kjører av seg selv

En hook er et skript som Claude Code kjører ved en bestemt hendelse, uten at du eller Claude ber om det. Pluginen leverer blant annet disse, definert i `hooks/hooks.json`:

| Når | Hva skjer | Skjer hvor |
|---|---|---|
| Økten starter | Sammenligner versjonen reglene i `CLAUDE.md` ble laget med, mot pluginen du har. Er de ulike, ber den Claude tilby `/superpowers-gstack:adapt` | Prosjekter hvis `CLAUDE.md` bruker superpowers-gstack, ikke pluginens eget repo |
| Økten starter | Viser grener med ulandet arbeid som har stått urørt i sju dager | Alle git-prosjekter |
| Økten starter, også etter `/clear` | Skriver banneret «Where this project left off» fra `progress.md`, `handoff.md` og opptaket | Prosjekter der minst én av filene finnes |
| Økten slutter | Tar vare på de siste meldingene og en git-oversikt i `gstack-last-session.md` | Prosjekter med mappen `docs/superpowers/` |
| En spec eller plan skrives | Minner Claude på å lage forklaringssiden med `/superpowers-gstack:htmlify explain` | Filer under `docs/superpowers/specs/` og `docs/superpowers/plans/`, ikke `progress.md` |

Ingen av dem blokkerer deg. De skriver ut en melding eller tar vare på en fil, og går videre. Det siste skriptet gir bare Claude en påminnelse, og lager ikke selve siden.

### Tre modellhus

Kontrollen av ferdig arbeid bruker modeller fra flere selskaper, fordi hvert selskap har sine egne blindsoner. Claude leser først, Codex fra OpenAI leser neste gang, og for de farligste endringene leser et tredje hus utenfor Anthropic og OpenAI til slutt ([se figuren i kapittel 4](#k4)). Hvilke modeller det er, hvor nøklene ligger og hva det koster, står i [kapittel 10](#k10).

> 💡 Subagenter ser bare det de får, så alt som må overleve står i en fil. Arbeidstrærne gir hver oppgave sin egen mappe, og hookene passer på trådene i bakgrunnen.
