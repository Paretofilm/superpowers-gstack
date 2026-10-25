---
type: backlog
source: /doctor prompt-audit kjørt i prosjektet sing-replay, 2026-10-25
checked_against: superpowers-gstack 3.16.0 (commit 0b13d57)
status: løst i 3.17.0 (A, B, C rettet; D avgjort og rettet; E verifisert, ingen endring — se CHANGELOG)
---

# Funn fra prompt-revisjon av sing-replay — tre åpne plugin-endringer

Fra en revisjon av `CLAUDE.md` i `~/Developer/sing-replay` (generert av `/adapt`
2.53.3) og `~/.claude/CLAUDE.md`. Alle funn ble krysssjekket mot 3.16.0-malene i
`skills/adapt/` før denne meldingen ble skrevet. Det som allerede er rettet i 3.16.0
står nederst, så ingen jobber med det på nytt.

Brukerens egne rettelser (prosjektfila, brukerfila) er **ikke** en del av dette.
Bare det som hører hjemme i pluginen.

## /goal

Kopier denne linjen inn i `/goal`:

```
/goal Fiks de tre åpne punktene i docs/superpowers/backlog/2026-10-25-prompt-audit-sing-replay.md (A, B, C) og verifiser de to «verifiser først»-punktene (D, E): lint-skills.py er GRØNN, adapt-testene (skills/adapt/tests/run.sh) er grønne med nye tester for A, B og C, blokkmarkører er bumpet der blokkteksten endret seg, plugin.json er bumpet med CHANGELOG-oppføring, og en kjøring av /superpowers-gstack:adapt mot en kopi av sing-replay/CLAUDE.md viser de nye tekstene. Ikke ferdig før alle fem er avgjort og dokumentert i CHANGELOG.
```

Ferdig betyr, målbart:

1. `python3 scripts/lint-skills.py` er GRØNN.
2. Testene under `skills/adapt/tests/` er grønne. A, B og C har hver minst én test som feiler før endringen og passerer etter.
3. Hver endret blokk i `skills/adapt/blocks/` har bumpet markørversjon (for eksempel `gstack-xcode-tools-v10` til `-v11`), slik at `/adapt` erstatter eldre kopier.
4. `.claude-plugin/plugin.json` er bumpet, og CHANGELOG har `## [X.Y.Z]` med ett punkt per A–E, inkludert de som ble avgjort «ingen endring».
5. Mot en kopi av `~/Developer/sing-replay/CLAUDE.md` (aldri originalen) gir `scripts/adapt-claude-md.py` de nye tekstene i `xcode-tools`-seksjonen, og lar prosjektets umarkerte seksjoner stå urørt.

## Åpne punkter (bekreftet mot 3.16.0)

### A. Entitlements i XcodeGen-prosjekter — modellen motsier seg selv

- **Sted:** `skills/adapt/blocks/xcode-tools.md:142`, `:148`, `:157`.
- **Nå:** «`*.entitlements` file … **Agent** — edit declaratively as XML»; «agent declares the capability + container in `*.entitlements` (declarative XML)»; «declare entitlements in `*.entitlements` + `project.yml`».
- **Feil:** Blokka anbefaler XcodeGen. Der genereres entitlements-fila fra `entitlements.properties` i `project.yml`, og `xcodegen generate` overskriver håndredigeringer. Bevis fra et ekte prosjekt: `~/Developer/sing-replay/project.yml:68-87`, med kommentaren «DENNE FILA GENERERES. Å rette entitlements-fila direkte holder ikke — `xcodegen generate` skriver den tilbake, og funksjonen feiler først ved kjøring.» Agenten som følger malen redigerer fila som så blir skrevet over, og feilen viser seg først ved kjøring.
- **Ønsket endring:** For XcodeGen-prosjekter skal blokka si at kilden er `entitlements.properties` i `project.yml`, og at `*.entitlements` er generert utdata som ikke redigeres for hånd. For prosjekter uten XcodeGen står dagens tekst ved. Tabellraden på `:142` og XML-eksempelet må skille de to tilfellene. Ta også med at `icloud-services` og begge container-listene (`icloud-container-identifiers` og `ubiquity-container-identifiers`) er separate nøkler.

### B. Signeringsfeil: «STOP» bør være «prøv flagget først»

- **Sted:** `skills/adapt/blocks/xcode-tools.md:148`, punkt (4) i «Capability workflow».
- **Nå:** «if signing fails with "container not registered" / "no matching provisioning profile" — STOP and hand the user the exact portal steps … The portal requires Apple ID + 2FA that no MCP/CLI tool automates».
- **Feil:** Målt 2026-08-15 i sing-replay: `xcodebuild … -allowProvisioningUpdates -allowProvisioningDeviceRegistration build` registrerte App ID-en med iCloud-kapabiliteten automatisk og bygget på tre sekunder, der et manuelt brukersteg var budsjettert. Prosjektets egen CLAUDE.md (`## Apple-lærdommer`, «CloudKit-arbeidsflyten her», steg 4) sier uttrykkelig at den eldre påstanden «was wrong». Fordi `xcode-tools` erstattes ved hver `/adapt`, kommer feilpåstanden tilbake i prosjektfila hver gang, og den står i strid med det prosjektet har målt.
- **Ønsket endring:** Steg (4) skal først prøve `-allowProvisioningUpdates` (og `-allowProvisioningDeviceRegistration` ved ny enhet), og bare hvis det også feiler, stoppe og gi brukeren portal-stegene. Behold forbudet mot å gå i løkke. Nyanser setningen «no MCP/CLI tool automates»: portalen krever 2FA, men Xcodes automatiske signering kan opprette App ID og kapabilitet når brukeren allerede er innlogget.

### C. Påstanden om automatisk signering på macOS er for bred

- **Sted:** `skills/adapt/blocks/xcode-tools.md:146`, siste setning i «Default signing».
- **Nå:** «automatic `Apple Development` signing does NOT work headlessly on macOS (portal registration needs Apple ID + 2FA and `xcodebuild` fails with "No signing certificate found")».
- **Feil, eller i det minste for bred:** `~/Developer/sing-replay` bygger og tester macOS headless med `CODE_SIGN_STYLE: Automatic` (`project.yml:19`) og `-allowProvisioningUpdates` (`.config/wt.toml:17` og `:21`: hele macOS-testpakka og Release-bygget). Det fungerer. Reservasjonen «iOS er annerledes» på samme linje stemmer, men selve påstanden er ikke generelt sann.
- **Ønsket endring:** Skill mellom «ny app uten registrert App ID eller sertifikat» (der påstanden kan stemme) og «innlogget Xcode-konto med `-allowProvisioningUpdates`» (der automatisk signering virker). Regelen om aldri ad-hoc og om Developer ID for nye macOS-prosjekter står, men begrunnelsen må ikke avvise en fungerende konfigurasjon. Vurder om «MUST declare» skal gjelde bare ved nyoppretting, som teksten allerede antyder («every new»).

## Verifiser først (kan allerede være dekket)

### D. Eksisterende, umarkert `## Skill routing` oppdateres aldri

- **Observasjon:** `skills/adapt/SKILL.md:322` sier at scriptet lar en eksisterende `## Skill routing` stå urørt, og bare omdøper noen kjente skillnavn. `routing-default.md:7` og `:22` er riktig for nye prosjekter (`/land` når landingsmodus er solo), men sing-replay fikk `## Skill routing` fra en eldre `/adapt` og har fortsatt «Branch is ready to merge to main → `/ship`» (`CLAUDE.md:94`), i strid med prosjektets egen «Landing mode: solo».
- **Spørsmål å avgjøre og teste:** Skal `adapt-claude-md.py` også (a) omskrive «ready to merge»-raden når `Landing mode:` er satt, og (b) omdøpe skillnavn i *prosa*, ikke bare i tabeller? Prosjektets `CLAUDE.md:118` og `:852` har samme navn i løpende tekst («Native review skills (`macos-native-review`, `ios-native-review`) run BEFORE…»). Les omdøpingskoden og sjekk med en test mot en kopi av filen. Hvis dagens oppførsel er bevisst (umarkert = prosjektets eget), dokumenter det i `adapt/SKILL.md`, og si hva som forventes av brukeren etter en skillrename.

### E. Hva gjør `/adapt` med en gammel `gstack-autonomy-v2`-seksjon?

- **Observasjon:** Prosjektfila har en markert seksjon `## Autonomy and user interruption <!-- gstack-autonomy-v2 -->`, men det finnes ingen `autonomy`-blokk i `skills/adapt/blocks/` i 3.16.0. Avklar og test hva som skjer: fjernes seksjonen, bevares den som den er, eller blir den liggende som en foreldreløs markert seksjon som ingen kan oppdatere? Seksjonen inneholder en «Forbidden phrases»-liste som siterer ordrett en enkelt tidligere hendelse, og som antakelig ikke bør leve videre uten eier.

## Allerede rettet i 3.16.0 — ikke gjør noe

- `ios-native-review` / `macos-native-review` i **tabeller**: omdøpes av scriptet (se likevel D for prosa).
- «Ready to ship» etter landingsmodus i **nye** routing-seksjoner: `routing-default.md:7` og `:22`.
- Relative skriptstier: `multi-lens-review.md:12` sier nå «`scripts/classify-change.py` in the plugin».
- `Model Routing`-blokka (`model-routing-section.md`) pinner ikke lenger modell-ID-er. Referansetabellen i `adapt/model-routing.md:36-45` har fortsatt `claude-opus-5`, `claude-sonnet-5` og `claude-haiku-4-5`. Den holdes av `scripts/check-new-models.py`, så ingen manuell endring, men se at jobben faktisk fanger Opus 5.5, Sonnet 5.5 og Haiku 5.5.

## Merk om prosess

- Repoets regler (`CLAUDE.md:155-156`): `lint-skills.py` må være grønn, og et ship-verdig endringssett krever `plugin.json`-bump og CHANGELOG-oppføring. A, B og C er `fix`/`refactor` som endrer generert tekst, altså ship-verdige.
- A og B rører signering og kapabiliteter. Det er høyrisiko i forstand «stille feil i et brukerprosjekt», så kjør `/superpowers-gstack:pitfall-verification` på endringen slik repoets egne regler krever.
- Test mot en **kopi** av `~/Developer/sing-replay/CLAUDE.md`, aldri originalen. Prosjektets umarkerte seksjoner (`Apple-lærdommer fra dette prosjektet`, `Sing Replay — landing`) skal komme uskadet ut.
