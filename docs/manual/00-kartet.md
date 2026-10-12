---
nummer: 0
tag: Kartet
tittel: Hele flyten på én side
aksent: cyan
oppdatert: 2026-10-12
bruk: Bruk denne når du har glemt hvor i flyten du er.
ferdig: Du er ferdig når du vet hva som er neste stopp.
---

![[kartet.svg]]

### Slik leser du kartet

Flyten går fra venstre mot høyre, fra en idé til ferdig arbeid på hovedgrenen (main, grenen alt det ferdige samles på). Under hver stasjon står skillen (en ferdig arbeidsmåte Claude laster inn) som driver den. De fire merkene med hånd er stoppene: der går ikke Claude videre før du har svart. Mellom stoppene arbeider Claude selv.

Pilen under kartet viser at flyten kan deles over flere økter. Da skriver Claude en overleveringsfil (handoff) som neste økt leser først. Mer om den i kapittel 5.

### Stasjonene

| Stasjon | Hva skjer | Skill | Du må |
|---|---|---|---|
| Idé | Claude stiller spørsmål og foreslår et design | brainstorming | Godkjenne designet |
| Spec | Designet skrives ned som en spesifikasjon (spec) | brainstorming | Lese den hvis den er stor |
| Plan | Spesifikasjonen blir en plan med små oppgaver | writing-plans | Lese planen og velge hvordan den skal kjøres |
| Bygg | En ny underagent (subagent) bygger hver oppgave | subagent-driven-development | Ingenting, Claude kjører selv |
| Bevis | Claude sjekker at det virker og leter etter feller | pitfall-verification | Se at det virker når appen kan kjøres |
| Landing | Det ferdige samles på hovedgrenen | land | Si ja til landingen |

### Snarveier

- `/superpowers-gstack:vibe` bygger én funksjon fra start til landing med én runde spørsmål, låste akseptansetester som eneste sjekkpunkt og en ny underagent per fase.
- `/superpowers-gstack:autoimplement` kjører en ferdig plan med flere faser: én underagent per fase, gjennomgang og feller-sjekk mellom hver fase, og stopp når den finner noe du må ta stilling til.

> 💡 Du stopper fire steder: godkjenne designet, lese planen, se at det virker og la den lande. Alt annet gjør Claude.
