# `/adapt` i et tomt prosjekt — design

**Dato:** 2026-10-11 · **Status:** implementert i 3.11.0 (se «Avvik fra utkastet» nederst) · **Målversjon:** 3.11.0

> Versjonen ble 3.11.0, ikke 3.12.0: versjonsnummer tas ved landing, ikke ved utkast, og denne
> endringen landet først. Work-state-endringen tar neste nummer når den lander.

## Formål

`/superpowers-gstack:adapt` er bygget for å oppgradere en `CLAUDE.md` som finnes fra før
uten å miste noe: snapshot, fail-closed-skript, deferred-seksjoner, «skal jeg gå videre».
Det vernet er riktig når et prosjekt har et års kunnskap i filen. I en tom mappe finnes
det ingenting å verne, og prosedyren koster likevel like mye.

**Målt 2026-10-11** (`workflow-metrics`, økten der `~/Developer/MODS/Superpowers-gstack-panel`
ble satt opp fra en tom mappe):

| Mål | Før |
|---|---:|
| Stopp der brukeren måtte svare før noe skjedde | 6 |
| Meldinger fra brukeren før `CLAUDE.md` fantes | 7 |
| Modellkall | 22 |
| Median kontekst per kall | 168k |

De seks stoppene: stack-spørsmål, bekreft stack, bekreft skill-utvalg, tre pinner i
én runde, «skal jeg gå videre», «vil du ha en gjennomgang». Det første av dem var
dessuten et brainstorming-spørsmål i forkledning: i et tomt prosjekt er stacken et
*resultat* av brainstormingen, ikke en forutsetning for den. Rekkefølgen er feil, ikke
bare antallet.

**Suksess:**
- I en tom mappe skriver `/adapt` `CLAUDE.md` og pinnene uten ett eneste spørsmål, sier
  i én linje hva som ble antatt, og sender brukeren rett til brainstorming eller
  vibe-intaket. Det første stoppet i økten er det første *innholdsspørsmålet*.
- Delen `## Project` fylles stille når stacken er kjent, uten en ny runde med
  bekreftelser.
- Den fulle prosedyren er uendret for prosjekter med eksisterende `CLAUDE.md`.
- Ingen standardverdi er dyrere å rette enn én linje i én fil.

## Avgjørelser

| Tema | Valg |
|---|---|
| Hvem avgjør om prosjektet er «ferskt» | Skriptet, ikke skillen. `--dry-run` rapporterer `fresh: true/false` med begrunnelse i JSON; skillen leser det. Én definisjon, testbar. |
| Hva «ferskt» betyr | Ingen `CLAUDE.md`, ingen pakkefil (`package.json`, `Package.swift`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `Gemfile`, `.claude-plugin/plugin.json`, `*.xcodeproj`), og færre enn fem filer utenom `.git/`, `.gstack/` og `.claude/`. Alle tre må holde. |
| Standardvalg i fersk sti | Spor `web`, arbeidsflyt `vibe`, explainer `local`, `Local state: none`, sensitivitet `medium`, ruting fra `blocks/routing-default.md`. Samme verdier som skillen i dag *anbefaler* i hvert spørsmål, så svaret «Recommended» blir svaret. |
| Hvorfor `medium`, ikke `low` | Sensitiviteten er ukjent før stacken er kjent. `medium` ruter koding til sonnet, som er riktig for det vanligste, og rettes i etterfyllingen (del 3). `low` kan sende DSP-kode til haiku før noen har sett at det er DSP. |
| Hva som *ikke* skrives i fersk sti | `## Project` får bare en linje `Stack: not yet known — filled in after the first spec` og markøren `<!-- gstack-project-pending -->`. Skriptet har lov til å erstatte denne seksjonen nøyaktig én gang. |
| Etterfylling | Ny flaggkombinasjon `--project-section <fil>` erstatter seksjonen med markøren, fjerner markøren, og tar `--set DOMAIN_SENSITIVITY=` og `--track` på nytt. Uten markør nekter skriptet: seksjonen er prosjektets. |
| Hvem utløser etterfyllingen | `vibe` steg 2 (etter intaket, før SPEC.md committes) i vibe-profilen. I classic-profilen: rutingregelen «stack bestemt → `/adapt`», og `/adapt` ser markøren og spør da bare om stacken er riktig lest av filene. Ikke en krok: en spec skrives sjelden nok til at skillen kan gjøre det. |
| Gjennomgangs-tilbudet (steg 6) | Faller bort i fersk sti. Det er en lesekontroll av en fil ingen har skrevet i. |
| Fasen «Confirm the stack» og «Evaluate skills» | Hoppes over i fersk sti. Standardrutingen er nesten lik for alle prosjekter; radene som avhenger av stack (`/qa`, `/cso`, Apple-skillene) legges til av etterfyllingen etter samme regler som i dag. |

## Komponenter

| # | Komponent | Endring |
|---|---|---|
| 1 | `scripts/adapt-claude-md.py` | `fresh`-deteksjon i `--dry-run`-JSON (`fresh`, `fresh_reason`). Nytt flagg `--fresh`: skriver pinnene `.gstack/workflow` og `.gstack/explainer` om de mangler, bruker standardverdiene over, og skriver `## Project` med `gstack-project-pending`. Nytt flagg `--project-section <fil>`: erstatter den markerte seksjonen én gang. `--fresh` nekter (exit 2) når prosjektet ikke er ferskt, så en feilkjøring på et levende prosjekt ikke kan skrive over noe. |
| 2 | `skills/adapt/blocks/routing-default.md` (ny) | Rutingen uten stack-avhengige rader. Samme form som utkastet skillen skriver i dag, med `## Project` som plassholder-seksjon. |
| 3 | `skills/adapt/SKILL.md` | Nytt steg 0: kjør `--dry-run`; er `fresh` sann, kjør `--fresh --mkdirs`, skriv én linje med antakelsene, og gå til `/superpowers-gstack:vibe` (vibe) eller `/superpowers:brainstorming` (classic). Ingen av de tre `STOP HERE`-portene. Steg 2–6 uendret ellers. Nytt avsnitt i steg 4: finnes markøren, er dette en etterfylling: resolve stack fra filene og specen, still ikke pinne-spørsmålene på nytt. |
| 4 | `skills/vibe/SKILL.md` | Steg 2: finnes markøren i `CLAUDE.md`, skriv `## Project` fra intaket (stack, testkommando, deploy, sikkerhetssignaler) og kall skriptet med `--project-section`. Én linje i loggen. |
| 5 | `skills/adapt/templates/project-context.md` | Ny seksjon «Stack and how to run» som peker til `## Project` i `CLAUDE.md`, så kontekst-skillen ikke dupliserer den. |
| 6 | `scripts/lint-skills.py` | `routing-default.md` sjekkes som de andre blokkene (ingen `{{…}}` igjen, overskriftene finnes). |
| 7 | `tests/unit/test_adapt_script.py` | Se «Testing». |
| 8 | `CLAUDE.md` (rutingseksjonen), `README.md`, `CHANGELOG.md`, `plugin.json` | Versjon 3.12.0. Rutingraden for `/adapt` nevner den ferske stien. |

## Del 1 — deteksjon

`--dry-run` får to nye felt i JSON-linjen: `fresh` (bool) og `fresh_reason` (tekst).
Reglene:

| Signal | Ferskt når |
|---|---|
| `CLAUDE.md` | mangler |
| Pakkefil | ingen av: `package.json`, `Package.swift`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `Gemfile`, `.claude-plugin/plugin.json`, `*.xcodeproj`, `*.xcworkspace` i roten |
| Filer | under fem i roten og undermapper, utenom `.git/`, `.gstack/`, `.claude/` og `docs/superpowers/` |

Alle tre må holde. En mappe med bare `README.md` og `.gitignore` er fersk. En mappe
med `package.json` og ingenting annet er det ikke: da kan stacken leses av filen, og den
vanlige stien passer. `fresh_reason` sier hvilket signal som felte avgjørelsen, så
skillen kan sitere den når den *ikke* tar den ferske stien.

## Del 2 — fersk sti

`python3 adapt-claude-md.py --fresh --mkdirs` gjør i én kjøring det skillen i dag gjør
over seks stopp:

1. Nekter med exit 2 og `BLOCKED — not a fresh project: <fresh_reason>` når del 1
   ikke holder. Dette er den eneste nye porten, og den vender mot skriptet, ikke
   brukeren.
2. Skriver `.gstack/workflow` = `vibe` og `.gstack/explainer` = `local` om de mangler,
   og `git add`-er dem som skillen gjør i dag. Finnes en pinne, respekteres den.
3. Skriver `CLAUDE.md` med header, rutingen fra `routing-default.md`, alle
   markør-blokkene, `Model Routing` med `DOMAIN_SENSITIVITY=medium`, `Local state: none`,
   og `## Project` med markøren `gstack-project-pending`.
4. Oppretter kontekst-skillen og `docs/superpowers/` som i dag.
5. Rapporterer som før, med én ekstra linje øverst:
   `Assumed: web track, vibe workflow, local explainer, no local state, medium sensitivity — change any of them in .gstack/ or CLAUDE.md, or run /adapt again after the first spec.`

Skillen videresender linjen og går rett videre: i vibe-profilen til
`/superpowers-gstack:vibe` med det brukeren sa; i classic til `/superpowers:brainstorming`.
Ingen «stemmer dette?», ingen «skal jeg gå videre?», intet tilbud om gjennomgang.

Hva som bevisst *ikke* spørres om, og hvorfor det er trygt:

| Spørsmål i dag | Standard | Koster å rette |
|---|---|---|
| Arbeidsflyt | vibe | én linje i `.gstack/workflow` |
| Explainer | local | én linje i `.gstack/explainer` |
| Lokal tilstand | none | én linje under prosjektets egen overskrift |
| Sensitivitet | medium | ett `--set` i etterfyllingen |
| Stack, test, deploy | utsatt | fylles i del 3 |
| Skill-utvalg | standardruting | radene som avhenger av stack legges til i del 3 |

## Del 3 — etterfylling når stacken er kjent

Markøren `<!-- gstack-project-pending -->` på `## Project` betyr «skriptet får erstatte
denne seksjonen én gang». `--project-section <fil>` gjør det, tar samtidig
`--set DOMAIN_SENSITIVITY=` og `--track` på nytt, og fjerner markøren. Deretter er
seksjonen prosjektets, som i dag.

Hvem kaller:

- **Vibe:** `vibe` steg 2 har alt den trenger etter intaket: stack og testkommando fra
  det brukeren svarte eller fra kontekst-skillen, sikkerhetssignaler fra
  akseptansekriteriene. Den skriver `## Project` til en midlertidig fil og kaller
  skriptet. Går spor fra `web` til `macos`/`ios`/`both`, skrives `.gstack/track` nå, og
  skriptet tar inn `xcode-tools`-blokken med sine plassholdere, som i dag.
- **Classic:** rutingen i `CLAUDE.md` sier «stack bestemt → `/adapt`». Skillen ser
  markøren, leser stacken av filene og specen, og viser **ett** spørsmål: «Jeg leser
  dette som X med tester via Y. Riktig?» Det er dagens steg 2, men med et svar å
  bekrefte i stedet for et spørreskjema å fylle ut.

Uten markør nekter `--project-section` (exit 2). Det er garantien for at en
etterfylling aldri treffer et prosjekt som allerede har skrevet sin egen `## Project`.

## Del 4 — den fulle prosedyren er uendret

Et prosjekt som ikke er ferskt går gjennom steg 1–7 som i 3.10. Snapshot, deferred,
rescue, `STOP HERE`-portene og gjennomgangs-tilbudet er riktige der, og denne
endringen rører dem ikke. Den eneste forskjellen et slikt prosjekt ser, er at
`--dry-run`-JSON har to felt til.

## Testing

`tests/unit/test_adapt_script.py`, nye tester:

- **Deteksjon:** tom mappe → fersk. Bare `.git/` og `.gstack/` → fersk. `README.md` +
  `.gitignore` → fersk. `package.json` alene → ikke fersk, `fresh_reason` nevner
  pakkefilen. `CLAUDE.md` alene → ikke fersk. Seks tomme filer → ikke fersk.
- **`--fresh` på ikke-ferskt prosjekt** → exit 2, ingenting skrevet, `CLAUDE.md`
  byte-identisk før og etter.
- **`--fresh` på ferskt prosjekt** → `CLAUDE.md` finnes, ingen `{{…}}` igjen, markøren
  `gstack-project-pending` finnes nøyaktig én gang, begge pinnene finnes med riktig
  innhold, kontekst-skillen finnes. Kjørt to ganger: andre kjøring endrer ingenting
  (idempotens, som i dag).
- **`--fresh` med eksisterende pinne** `.gstack/workflow` = `classic` → pinnen beholdes,
  `CLAUDE.md` får ikke vibe-kontrakten.
- **`--project-section`** med markør → seksjonen erstattet, markøren borte, resten av
  filen byte-identisk utenfor `## Project` og `Model Routing`. Uten markør → exit 2,
  ingenting skrevet.
- **Vanlig sti etter `--fresh`:** en senere `--dry-run` uten `--fresh` rapporterer
  `fresh: false` (fordi `CLAUDE.md` nå finnes) og ingen `Removed`.

`skills/adapt/tests/required-sections.test.sh` får steg 0 som påkrevd seksjon.
`scripts/lint-skills.py` sjekker den nye blokken.

**Etter-måling:** sett opp én tom mappe til med `/adapt` etter landingen og kjør
`workflow-metrics asks` og `tokens` på økten. Målet er 0 stopp i `/adapt` og at
stopp nummer én i økten er intaket. Én økt på hver side er en anekdote, og det sies i
CHANGELOG.

## Utenfor første versjon

- **Krok som fyller `## Project` automatisk** når en spec skrives. Specene er for ulike
  til at en krok kan lese stacken pålitelig; skillene vet mer.
- **Sensitivitet utledet av specen** (ord som «audio», «migration», «payments»). Fristende,
  men en ordliste gir falske treff; etterfyllingen spør heller ikke, den leser sporet og
  sikkerhetssignalene som i dag.
- **Fersk sti for prosjekter med pakkefil men uten `CLAUDE.md`.** Der kan stacken
  leses av filene, og dagens steg 2 er ett spørsmål med et ferdig svar. Målingen får
  vise om det også er for mye.

## Avvik fra utkastet (implementert 2026-10-11)

- **Stack-avhengige rutingrader** legges ikke inn i `## Skill routing` ved etterfyllingen:
  det ville vært en håndredigering av CLAUDE.md, som skillen forbyr, og `--project-section`
  erstatter bare én seksjon. Radene (`/qa <url>`, `/cso`, Apple-skillene) ligger i stedet
  under `## Project` → `### Routing for this stack`, skrevet av samme kjøring.
  Plassholder-seksjonen sier at de kommer dit.
- **Kontekst-skillen** fikk ingen ny seksjon «Stack and how to run». `## Running and testing`
  finnes alt og peker nå til `## Project` i CLAUDE.md; to seksjoner om det samme var
  dupliseringen pekeren skulle hindre.
- **Tittel:** den ferske filen starter med `# <mappenavn>` (hovedutsjekkingens navn), så
  neste kjøring leser samme prosjektnavn av H1 som den første brukte.
- **Removed-rapporten** for `Model Routing` lister ikke lenger pluginens egen
  sensitivitetslinje når sensitiviteten endres; etterfyllingen gjorde det synlig.
- `skills/adapt/tests/required-sections.test.sh` fantes ikke og ble opprettet.
