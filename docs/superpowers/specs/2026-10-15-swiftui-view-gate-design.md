# swiftui-view-gate (3.12.0) — design

Kilde: `IDEAS.md` → `swiftui-view-gate` (foreslått 2026-10-13, utvidet 2026-10-14). Omfang C, godkjent av brukeren 2026-10-15: skill + `PostToolUse`-påminnelse + `verify-and-land`-kobling + `.gstack/visual-verify` + `scripts/window-shot.sh`.

## Problemet

Ingenting i pluginen fyller øyeblikket der en SwiftUI-visning skrives. `apple-native-review` leser planer, `swiftui-design-consultation` bare designsystem-pakken, og `xcode-tools`-blokkens verktøytabell er råd, ikke en sperre. Feltfunnet (fagfilm-pipeline, 2026-10-13): en nedtrekksmeny uten synlig indikator, og to linter (`review_macos_hig`, `review_accessibility`) som ga «ren» på en kontroll brukeren ikke kunne bruke. Bare en gjengivelse av visningen *i beholderen* (menyen, tabellraden) avslørte feilen.

## Beslutninger

1. **Skill `swiftui-view-gate`** med fem steg: slå opp, lint, se, rapporter ærlig, affordance-sjekk. Sporbevisst: `macos` → `review_macos_hig`; `ios` hopper over den; `both` kjører begge; `web` avviser. Linterne er mønstersjekker; skillen sier det, og «ren» betyr aldri «ser riktig ut».
2. **Gate-linjen er posten.** Skillen avslutter med én linje i chat: `View gate: rendered and seen | built, appearance unverified | waived by user`, med filene og skjermbildestien. Ingen fil i `.gstack/`: en fil ville overleve økten og påstå noe om en diff den ikke har sett. `verify-and-land` leser linjen fra økten.
3. **Påminnelsen er `scripts/view-gate.py nudge`**, modellert etter `explainer-nudge.py`: stille, aldri blokkerende, alltid exit 0. Den utløses av `Write|Edit|MultiEdit` på en `.swift`-fil som deklarerer en `View` (eller ligger under `Views/` eller `Components/`), og er stille hvis `review_macos_hig`, `review_accessibility` eller `review_liquid_glass` har kjørt i økten etter siste utløsning. Samme skript registrerer lint-kjøringene (matcher på verktøynavnet) i øktens tilstandsfil. Samme skript har `files --base <ref>`, som lister visningsfiler i en diff; `verify-and-land` bruker den.
4. **`.gstack/visual-verify`** = `host` | `vm` | `off`, nøyaktige strenger (som `e2e-executor`): ugyldig innhold er `BLOCKED`, ikke en stille standard; fravær betyr `off`. `host` er prosjekteierens stående tillatelse til vindusavgrenset skjermbilde av appen agenten selv startet, og til ingenting videre. `adapt` validerer pinnen, men skriver den aldri.
5. **`scripts/window-shot.sh <pid> <out.png>`**: finner vindu-id for PID-en med `CGWindowListCopyWindowInfo` (ingen tillatelse trengs), tar `screencapture -x -l <id>`, aldri hele skjermen. Feilmoduser med egne exit-koder: 2 bruk/ugyldig pinne/ikke `host`, 3 ikke macOS, 4 ingen vindu etter gjentatte forsøk, 5 bildet er tomt eller bare bakgrunn (manglende Screen Recording), 6 PID-en er ikke prosjektets egen. Skriptet tar aldri skjermbilde uten `host`-pinnen.
6. **`xcode-tools` → v10**: nytt avsnitt «SwiftUI view changes are not done until seen» (gate, rutene i rekkefølge, window-shot, VM-ruten) og en anti-pattern-linje. Lint-denylisten utvides til `v[0-9]` unntatt v10.
7. **`verify-and-land`**: ny Phase 5b «Look yourself first» (kun med `host`-pinnen), og Phase 1/6 bruker `view-gate.py files` og gate-linjen: en diff med visninger og uten gate-linje får ikke «klar til landing» uten at brukeren fraskriver seg det.
8. **Hook-konflikten** (`PreToolUse` på `screencapture` som peker mot `vm-run --screenshot`) bor i brukerens globale innstillinger, ikke i repoet. Pluginen kan ikke endre den; blokken og skillen skiller mellom vindusavgrenset opptak av en agent-startet app (tillatt under `host`) og hel skjerm (frarådet), og CHANGELOG gir teksten brukeren bør sette inn.

## Utenfor omfanget

- `/ship` er gstack-oppstrøms og endres ikke; regelen om gate-linjen står i `xcode-tools`-blokken, som en generert CLAUDE.md bærer inn i `/ship`-økter.
- Ruten med datamaskinbruk (route 3) er en vertstillatelse pluginen ikke kan gi; skillen nevner den og peker på rutene 1, 2 og 4.
- Ingen automatisk generering av `#Preview`; skillen beskriver fallbacken.

## Verifisering

Alt som er stdlib/bash testes her (Linux): hook-logikk, `files`, pinne-validering, `window-shot.sh`s feilveier og skill-/blokkinnhold. Selve opptaket (`CGWindowListCopyWindowInfo`, `screencapture`) kan ikke kjøres på Linux og er ikke verifisert på Mac; CHANGELOG sier det, og første kjøring på brukerens Mac er den manglende verifiseringen.
