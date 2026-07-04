# System-review og remediëringsplan — superpowers-gstack

**Dato:** 2026-07-03 · **Basis:** helhetlig review med tre parallelle lenser (skills-konsistens, executable surface, token-økonomi) + mål-gap-analyse. Alle P1-funn spot-verifisert mot kildefilene.

**Prosjektmål (målestokk):** færrest mulig feil fra start, ingen scope-creep, økonomisk drift (maks autonomi, minst tokens). Korrekt, konsistent, stringent, ikke bloated.

---

## Hovedverdikt

Kjernen er sterk: skill-skjelettet (Phase 0-selvsjekk, fail-closed-defaults, STOP-disiplin), fler-lens-maskineriet og htmlify/design-consultation-arkitekturen («logikk i kode, ikke instruksjoner») er nettopp det systemet skal være. Men systemet har vokst raskere enn sin egen vedlikeholdsevne: **flaggskip-automatikk som stille aldri virket, en ukentlig pengelekkasje, og instruksjons-drift som nå aktivt genererer feil instruksjoner inn i brukerprosjekter.** Fellesnevneren: det finnes ingen automatisk validering av instruksjons-flaten (5 700 linjer SKILL.md, null CI-sjekk) og ingen måling av det uttalte målet (verken feil eller tokens måles).

---

## P1 — Regelrette feil (fikses først)

| # | Funn | Bevis | Konsekvens |
|---|------|-------|------------|
| 1 | **htmlify PostToolUse-hook har aldri virket.** `DATA=$(python3 - <<'PYEOF' …)` + `<<<"$INPUT"` på egen linje: python leser heredoc-en som program, `sys.stdin.read()` er tom → exit 0 → hook no-op. Fail-silent by design → aldri oppdaget | `scripts/htmlify-posttooluse.sh:40-84`, empirisk reprodusert | Flaggskip-feature (auto-HTML av artefakter) død siden fødselen |
| 2 | **Update-pipelinen fyrer full Claude-API-kjøring hver mandag uansett.** Workflow-grep forventer 7-hex commit; VERSIONS.md lagrer tag (`v1.34.1.0`) → tom streng → `!= ""` alltid sann → `GSTACK_CHANGED=true` hver uke | `check-updates.yml:28` vs `VERSIONS.md` | ~40-60K prompt-tokens + PR + issue ukentlig uten endring. Forklarer de uleste issues #32/#34/#36 |
| 3 | **Generator-malene shipper fjernet `sensitive`-rolle + feil countersynthesis-rute til alle nye/adapterte prosjekter.** Rollen ble fjernet i 2.18.0; marker fortsatt `v3` så `/adapt` reparerer aldri eksisterende prosjekter | `setup-routing:430`, `adapt:415`, `README:40`, `pitfall-verification:132` | Hvert generert CLAUDE.md instruerer en rute scriptet nekter |
| 4 | **ios-visual-explore er uoppnåelig via routing.** Ikke i e2e-route-tabellen, ikke i CLAUDE.md, ikke i README | 0 grep-treff i alle tre | 3 releaser med arbeid (2.20→2.22) usynlig for dispatcher og bruker |
| 5 | **iOS-track får aldri native review av DESIGN.md.** swiftui-design-consultation Step 6.5 kaller kun macos-native-review; ios-native-review hevder den auto-chaines | `swiftui-design-consultation:669-695` vs `ios-native-review:47` | Halve dual-track-løftet brutt for design-gaten |
| 6 | **Plugin-relative stier bryter for marketplace-installasjoner.** third-lens-review, ios-visual-explore og swiftui-design-consultation antar cwd = dette repoet; ingen bruker `${CLAUDE_PLUGIN_ROOT}`/self-locating (kun htmlify gjør det riktig) | `third-lens-review:32,57`, `ios-visual-explore:29`, `swiftui-design-consultation:592` | Skills virker kun i dogfood-modus, ikke for installerte brukere |
| 7 | **CHANGELOG mangler 2.20.0–2.22.0** — plugin-ens egen ship-worthy-definisjon («bumps a version file, produces a CHANGELOG entry») brutt fire releaser på rad. *Eierskap: disse fire var agent-merges i denne sesjonen; prosessen manglet en gate, og agenten (jeg) fulgte ikke konvensjonen* | `CHANGELOG.md` topper på 2.19.0; plugin.json = 2.22.0 | Sporbarhet + oppdaterings-pipeline-antakelser brutt |

## P2 — Konsistens & robusthet (utvalg, full liste i lens-rapportene)

- **Double-Codex i autoimplement:** Step D kjører pitfall (som selv auto-chainer Codex siden 2.16.0) og deretter `/codex review` — to Codex-pass per fase. Aldri avstemt mot 2.16.0-omskrivingen.
- **self-repair.yml:** modell-valgte filstier skrives uvalidert (path traversal → kan overskrive workflows); ingen dedupe av åpne auto-repair-PR-er; trigges også av transiente API-feil; `git diff --quiet` ser ikke nye filer.
- **Prompt-injection-flate:** upstream SKILL-innhold mates ufencet inn i API-kall som skriver executable skill-filer; eneste gate er menneskelig PR-review.
- **Claude Code patch-releaser** (nesten ukentlig) trigger full API-regenerering av hele manualen når eneste delta er et versjonsnummer.
- **e2e-scaffold-avvik:** macos-varianten har WindowGroup-fellen ios-varianten ble herdet mot i 2.19.0 (ren iOS-app består macos-Phase 0); ios-varianten motsier seg selv om multiplatform-navning (Phase 0 sier `<App>iOSUITests/`, Step 10/runner bruker `<App>UITests` hardkodet).
- **Tre versjons-identiteter:** setup-routing sier «writes version 1.11.0», adapt sier «version 1.11.2», Step 6 sier les plugin.json (2.22.0).
- **README tre releaser bak** («twelve skills», lister 13, repoet har 16); quality-review-kategoritall feil (13 vs 15); hooks skrives med absolutte klone-stier og ingen `hooks/hooks.json` i plugin-en; repoet mangler sin egen versjons-markør (hooken nagger ved hver sesjonsstart).

## P2 — Token-økonomi (kvantifisert)

| Funn | Kost i dag | Fiks | Besparelse |
|------|-----------|------|-----------|
| 5 verste frontmatter-descriptions (110/108/91/76/70 ord — implementasjonsdetalj + versjonshistorikk) | ~1 700 tokens/sesjon totalt for 16 descriptions, i alle prosjekter | Trigger + én-linjes kontrakt (≤30 ord) | **~800 tokens/sesjon, overalt** |
| setup-routing vs adapt: 477 av ~760 linjer identiske (62 %) — de emitterte CLAUDE.md-blokkene transkriberes gjennom modellen | ~6 000 dupliserte tokens/invokasjon + drift (H3/H4-buggen oppsto nettopp her) | `blocks/*.md` single source; begge skills kopierer fil→CLAUDE.md via Bash, ikke transkripsjon | ~5-6K/invokasjon + eliminerer drift-klassen |
| autoimplement: ~30 % changelog-narrasjon i body (988 ord audit-tabell + regex-historikk) | ~1 900 tokens/invokasjon | Flytt til CHANGELOG | ~1 900/invokasjon |
| CLAUDE.md routing-seksjon dupliserer descriptions (549 ord; pre-flight-regexen finnes 4 steder) | ~1 060 tokens/sesjon i dette repoet + emitteres til brukerprosjekter | Én linje per rute: trigger → skillnavn | ~800/sesjon + slankere genererte CLAUDE.md |
| ios/macos-e2e-scaffold 79 % identiske; tier-tabellen forklart 5 steder | ~2K vedlikeholdt flate + drift | Merge bak e2e-route / én kanonisk tier-tabell | ~2K + én sannhet |

## Hull / muligheter (nivå-løft)

1. **Skill-lint CI (viktigst).** Instruksjons-flaten har null validering — det er rotårsaken til P1 #3/#4 og det meste av P2-drift. Et lite script (kjøres i CI + pre-push): frontmatter-gyldighet, refererte stier/skills eksisterer, routing-tabell ↔ skill-inventar begge veier, CHANGELOG-entry ved versjonsbump, description-lengdebudsjett, forbudte mønstre (`sensitive`-klassen). Systemet som skal hindre feil i brukerkode må hindre feil i seg selv — og linten *låser fast* alle fasene under.
2. **Release-gate.** Én kommando/skill for dette repoet som håndhever bump + CHANGELOG + README-sync + lint før push — gjør 2.20-2.22-klassen umulig å gjenta.
3. **Kost-ledger.** Målet «minst mulig tokens» er umålt. La pitfall/codex/third-lens-kjedene appende én JSONL-linje (lens, tokens, $) til `~/.gstack/` — synlig økonomi, og datagrunnlag for å tune tier-gatene.
4. **Update-pipeline → digest-modus.** Etter fiks av P1 #2: vurder ukentlig *digest-issue* (hva har endret seg upstream) i stedet for auto-PR med full regenerering — mennesket i loopen bestemmer om regenerering trengs. Lukk/behandle #32/#34/#36.

---

## Plan

> **Status 2026-07-03:** Fase 0 ✅ KOMPLETT (7 commits, alle P1 fikset; htmlify-hook + update-pipeline-extraction empirisk verifisert). Fase 1 ✅ KOMPLETT (`scripts/lint-skills.py` + CI + release-gate; gate-selvtest bestått). Backlogg (10 PR/issues) lukket 2026-07-04; fikset pipeline produserte og landet PR #39 (2.24.0, upstream-drift à jour).
>
> **Status 2026-07-04:** Fase 2 ✅ KOMPLETT (2.25.0): dobbel-Codex eliminert (Step D + pre-flight), e2e-scaffold-paret herdet (macos-plattform-guard, TARGET_DIR-konvensjon, latent glob-bug som gjorde `both`-stien umulig, fail-open macos-runner tettet), generator-konsistens (versjonsidentitet=plugin.json, 5 manglende skill-rader i BEGGE tabeller, kategoritall, spøkelses-refs), pipeline-herding (self-repair path-allowlist/dedupe/transient-skip/porcelain, upstream-fencing, lint-før-PR i workflowen, PR-link-fangst), script-P3-sveip (notify-cache, isatty-guard m.m.). Plugin-`hooks.json`-beslutning ✅ LØST (2.26.0): version-check shippes plugin-vidt via `${CLAUDE_PLUGIN_ROOT}`; notify-hooken forblir maintainer-opt-in; settings.json-duplikatet fjernet.
>
> **Status 2026-07-04 (Fase 3):** ✅ KOMPLETT. **3a** (2.27.0): model-routing v0.2 — to-akse (base tier × domain sensitivity), Claude-only, Fable-tier; lokale modeller (Pi/MLX) ikke lenger rutbare; codex fant 5 (blokk-plassering, adapt stale-block, Swift-overklassifisering, denylist-scope, design-doc-status) — alle fikset. **3c** (2.28.0): alle 16 descriptions ≤30 ord + hard-cap innført (`DESCRIPTION_WARN_WORDS` 60→30) + lint block-scalar-tellebug fikset. **3b** (2.29.0): `blocks/*.md`-full-ekstraksjon nedskalert til en **E8 drift-guard** (håndhever byte-identitet av emittert `## Model Routing`-blokk mellom setup-routing og adapt) — treffer #1/#2-drift-klassen ved CI-tid billig; full blocks/-ekstraksjon utsatt (gjenværende gevinst = sjelden runtime-dedup). Gjenstår: fase 4 (kost-ledger + digest-modus, trenger bruker-beslutninger), + skill-tabellsync-sjekk av PR #39-løftet.

**Fase 0 — Stopp blødningen (P1, én økt).** Rekkefølge etter kost:
0.1 Fiks check-updates-extraction (commit-hash i VERSIONS.md eller tag-aware grep) + fail-loud ved tom → stopper ukentlig API-brenning. Behandle åpne issues/PR-er.
0.2 Fiks htmlify-hook (`printf '%s' "$INPUT" | python3 -c …`) + fail-loud-logging så neste regresjon synes.
0.3 Purge `sensitive`/GPT-5.5-ruta fra de 4 filene, bump multi-lens-marker → v4 (så /adapt reparerer eksisterende prosjekter).
0.4 CHANGELOG-backfill 2.20.0–2.22.0.
0.5 Wire ios-visual-explore inn i e2e-route + CLAUDE.md + README.
0.6 Branch swiftui-design-consultation Step 6.5 på `$TRACK` (ios → ios-native-review).
0.7 Self-locating stier (`${CLAUDE_PLUGIN_ROOT}`-mønster à la htmlify) i third-lens-review, ios-visual-explore, swiftui-design-consultation.

**Fase 1 — Lås fast (skill-lint + release-gate).** Bygg linten FØR resten av oppryddingen, så fase 0-fiksene ikke kan drifte tilbake: `scripts/lint-skills.py` + GitHub Action + pre-push-instruks; deretter release-gate-sjekkliste i CLAUDE.md (eller liten skill).

**Fase 2 — Konsistens (P2).** autoimplement Step D-avstemming (dropp eksplisitt Codex-steg, stol på pitfall-kjeden), self-repair-hardening (path-allowlist, PR-dedupe, transient-skip, porcelain-diff), CC-patch → sed-path uten API, macos-scaffold WindowGroup-guard, ios-scaffold multiplatform-navning, versjons-identitet (fjern 1.11.x; plugin.json er sannheten), README/kategoritall-sync, `hooks/hooks.json` med `${CLAUDE_PLUGIN_ROOT}`, versjons-markør i eget repo.

**Fase 3 — Økonomi.** Description-omskrivinger (≤30 ord, linthåndhevet), `blocks/*.md`-ekstraksjon for setup-routing/adapt, autoimplement-changelog-flytt, CLAUDE.md routing-slanking, tier-tabell single source. (e2e-scaffold-merge: utsett — reell gevinst men størst regresjonsrisiko; ta den når linten + testene står.)

**Fase 4 — Nivå-løft.** Kost-ledger, update-pipeline digest-modus, deretter re-kjør fler-lens-review på det ferdige systemet.

**Verifisering per fase:** lint grønn + berørte skills røyk-testes (setup-routing/adapt mot et scratch-prosjekt; e2e-kjedene har allerede live-smoke-mønsteret).

---

## Bevart — ikke rør

autoimplement-tillitsmaskineriet (anchored regex + refusals), adapts marker-versjonerte seksjons-oppgradering, det konsistente skill-skjelettet (Phase 0 / What-this-is-NOT / fail-closed / STOP-disiplin), htmlify- og design-consultation-arkitekturen (logikk i kode), third-lens-review.py-herdingen (Keychain, live-prising, exit-taksonomi), check-updates' LLM-output-forsvar (write_or_fail m.m. — selve *skrivingen* er god; det er *trigger* og *injection-fencing* som skal fikses).
