# adapt som deterministisk merge-script — design

Grunnlag: `2026-09-11-modernisering-audit.md`, punkt 2 og 3 under «Forenkle eller slå
sammen»; Fase 4 i `docs/superpowers/plans/2026-09-11-modernisering.md`.

## Problemet

`skills/adapt/SKILL.md` var 769 linjer, hvorav rundt 550 var vern mot at
markdown-kirurgi utført av modellen skulle slette prosjektinnhold: snapshot, growth
check med tre triggere, attribution-sentineler, heading-demotering, provenance
(`emitted=N`), ni nesten identiske fire-case-blokker, og et rapportformat med tre
ordrette etiketter som lint E13 (20 nåler + to rekkefølgeregler) pinnet fordi
prosaen ellers kunne omformuleres bort. `setup-routing` dupliserte roster-tabellene
og plassholder-prosaen. Alt dette er *mekanikk* — finn markør, erstatt til neste
overskrift, tell linjer — og mekanikk hører i et script, ikke i instruksjoner.

## Løsningen

### `scripts/adapt-claude-md.py`

Én skriver av prosjektets `CLAUDE.md`. Skillen bestemmer *hva* (prosjekttype,
valgte skills, domene-følsomhet, plassholderverdier); scriptet gjør *alt* som rører
filen, deterministisk og idempotent.

```
python3 scripts/adapt-claude-md.py [--project-dir DIR] [--track ios|macos|both|web]
    [--set TOKEN=value]... [--routing-file F] [--rescue <marker-name>]...
    [--no-model-routing] [--mkdirs] [--dry-run] [--plugin-version X.Y.Z] [--blocks DIR]
```

Rekkefølge per kjøring (alt beregnes i minne; `--dry-run` skriver ingenting):

1. **Snapshot** `.gstack/CLAUDE.md.pre-adapt` — roter, aldri overskriv; ekskluder via
   `.git/info/exclude`; hopp over (og si det) når ingen CLAUDE.md finnes.
2. **Header** — de to HTML-kommentarlinjene øverst, skrevet på nytt hver gang; en
   gammel énlinjers header erstattes på stedet.
3. **Pensjonerte seksjoner** — `gstack-autonomy-vN` slettes innenfor størrelses-
   grensene (v1 ≤ 59, v2 ≤ 34, eller `emitted`+3); vokst → utsatt; markørløs uten
   sentinel røres aldri.
4. **Omdøping av pensjonerte skill-navn** utenfor markørstyrte seksjoner og
   code-fences; rader som kollapser til samme skill dedupliseres.
5. **Skill routing** — settes inn fra `--routing-file` bare når `## Skill routing`
   mangler; finnes den, røres den ikke (de markørstyrte underseksjonene håndteres
   av punkt 6 uansett nivå).
6. **Blokkene** (`skills/adapt/blocks/`, `BLOCKS`-rosteret i scriptet): for hver
   blokk de fire casene fra den gamle prosaen — skip / erstatt / attribuer-så-erstatt
   / legg til — med growth check (provenance, ratio 1,5×, volum ~20 linjer; hvilken
   som helst utløser), sentinel-attribusjon, H3-demotering av rot og underoverskrifter,
   og `<!-- emitted=N -->` (N = `wc -l` av blokkfila før substitusjon). En vokst
   seksjon **utsettes** — aldri erstattes — med mindre `--rescue <marker>` er gitt:
   da flyttes linjene blokken ikke har (og seksjonens egne overskrifter) til en ny
   umarkert H2 `## <prosjekt> — notes rescued from "<overskrift>"` rett under, og
   seksjonen erstattes.
7. **Model Routing** — en gammel blokk med modell-/tier-kolonne erstattes; en
   overskrift uten slik tabell er prosjektets egen (la stå, hopp over, rapporter).
8. **Plassholdere** — `{{TOKEN}}` i emitterte blokker løses fra `--set`;
   `E2E_EXECUTOR` også fra `.gstack/e2e-executor` (`host`|`vm`, fravær = `host`,
   annet = BLOCKED). Én uløst plassholder i en blokk som skal skrives → exit 2, ingen
   skriving. Det er den mekaniske formen av «aldri la en rå `{{…}}` nå CLAUDE.md».
9. **Verifisering** — diff snapshot→ny fil; hver fjernet ikke-tom linje som ikke
   finnes (normalisert) i den nye blokken den ble erstattet av, listes under
   **Removed (not plugin prose):** med seksjon og linjetall. Over-inkluderende med
   vilje.
10. **Rapport** — menneskelesbar med de tre ordrette etikettene
    (`**Removed (not plugin prose):**`, `Nothing project-authored was removed.`,
    `**Deferred (grown past its block, not upgraded):**`), deretter én JSON-linje
    sist med alt skillen trenger for å stille spørsmål (utsatte seksjoner med
    linjer i risiko, uattribuerbare seksjoner, uløste plassholdere).

Exit: 0 (skrevet, eller dry-run fullført) / 2 (nektet — ingenting skrevet; årsak på
stderr). Aldri traceback.

Overskrifter inne i code-fences telles ikke — en `# kommentar` i en bash-blokk er
ikke en H1. Den gamle prosaen sa ingenting om dette.

### `skills/adapt/SKILL.md` (~200 linjer)

Analyse → bekreft stack (spør prosjekttype/tester/deploy/UI/sikkerhet når CLAUDE.md
mangler eller ikke svarer) → velg skills fra `roster.md` → løs plassholdere per
`blocks/PLACEHOLDERS.md` og skriv `.gstack/e2e-executor`-pinnen ved behov → skriv
routing-utkast til en midlertidig fil → `--dry-run` → vis rapporten + gap-analyse,
**stopp** → ved utsatte seksjoner: spør flytt/behold per seksjon → kjør scriptet →
relé rapporten ordrett + «Where project knowledge belongs» → tilby review.

`setup-routing` finnes ikke lenger: adapt på et prosjekt uten CLAUDE.md *er* oppsett.
Roster-tabellene ligger én gang i `skills/adapt/roster.md`; blokkene og
`model-routing.md` under `skills/adapt/`.

### Lint

- E8: generatoren er scriptet. Hver blokkfil i `MARKER_BLOCKS` må finnes, ha markør på
  H2-linjen, og stå i scriptets `BLOCKS`-roster (importert, ikke grep-et); ingen
  foreldreløs blokkfil; ingen inline-kopi i `adapt/SKILL.md`; SKILL.md refererer
  `PLACEHOLDERS.md`.
- E13 (ny mening): `adapt/SKILL.md` delegerer hver skriving til scriptet — den nevner
  `scripts/adapt-claude-md.py` og inneholder ingen av de gamle håndkirurgi-
  instruksjonene (`cp CLAUDE.md`, `sed -n`, `Growth check —`, `Attribution check —`).
  De 20 prosa-nålene og rekkefølgereglene er borte; det de vernet er nå kode med
  tester.

### Tester

`tests/unit/test_adapt_script.py` kjører scriptet mot midlertidige prosjekter med de
ekte blokkfilene: fixturen `tests/fixtures/adapt-growth/CLAUDE.md` (sentinel-linjer
overlever, xcode-tools og git-hygiene utsettes, Session Continuity demoteres med
provenance), volum-nøytral fixture (bare provenance-triggeren fyrer — den utsatte
fixturen fra 2.49.0), attribusjon (preserve-and-insert), code-reuse markørløs,
autonomy-grenser, omdøpingstabell + dedup, fences ignorert i overskriftsskann, Model
Routing gammel vs. prosjektets egen, rescue, uløst plassholder nekter, idempotens.
Integrasjonstesten `test_adapt_growth_gate.sh` beholdes som ende-til-ende-bevis for
skillen.

## Ikke i scope

- Innholds-hash i markøren (same-length edit) — fortsatt utsatt, samme trigger som før.
- Generering av selve `## Skill routing`-teksten — det er dømmekraft og blir i skillen.
