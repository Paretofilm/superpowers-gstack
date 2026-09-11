# superpowers-gstack: hva bør bort, forenkles eller endres per 2026-09-11

**Status:** vurdering, ikke plan. Ingen filer i pluginen er endret.
**Grunnlag:** alle 18 SKILL.md (7 325 linjer), 11 emitterte CLAUDE.md-blokker (648 linjer), hooks, scripts, CHANGELOG 2.39–2.53.3; gstack 1.78→1.84.1 (upstream changelog); superpowers 6.3.0; Claude Code 2.1.268; Codex CLI 0.153.4/0.154.0; OpenRouter modell-liste; kostnadsloggen i `~/.claude/cost-ledger/ledger.jsonl` (91 rader, 2026-07-05 → 2026-09-07).

## Kort svar

Ja. Tre ting har skjedd siden pluginen ble designet, og hver av dem gjør en del av pluginen overflødig:

1. **Modellene verifiserer seg selv.** Anthropic beskriver Sonnet 5, Opus 5 og Fable 5.1 med «checks its own output without being asked», «caught its own logical faults during planning» og 38-timers ubemannede kjøringer. Mye av pluginens «tving modellen til å ikke hoppe over steget»-prosa er nå kontekstskatt uten målbar gevinst.
2. **Claude Code har tatt over flere av pluginens roller innebygd.** `/code-review` (lokal og `ultra` med uavhengig verifisering av hvert funn), Workflow-verktøyet for subagent-orkestrering, fork-subagenter, Monitor, `/skill-doctor`, auto-memory, `--resume`/`--continue` og harness-instruksen «You are operating autonomously».
3. **Upstream har flyttet seg.** gstack 1.84.1 velger selv modell (GPT-6 Astra for Codex, Fable 5.1 for Claude-stemmer, via `GSTACK_CODEX_MODEL`/`GSTACK_CLAUDE_MODEL`), kjører adversariell Claude+Codex i `/review` og har design-detektor i `/ship`. superpowers 6.x har slanket seg med «ceremony scales to the task» og inline selvreview i stedet for subagent-løkker.

Det som **ikke** er tatt over av noen: et tredje modellhus i review, HIG-validering på plan-nivå, XCUITest-scaffolding for macOS, verify-and-land («stale bundle»-problemet) og CLAUDE.md-ruting. Det er kjernen som bør overleve.

## Hva kostnadsloggen faktisk sier

| Linse | Kjøringer | Funn | Overlevde syntese | Andel |
|---|---|---|---|---|
| self-pitfall | 30 | 83 | 83 | 100 % |
| codex | 41 | 389 | 348 | 89 % |
| tredjehus (alle varianter) | 20 | 96 | 74 | 77 % |

Tre observasjoner:

- **Tredjehuset leverer fortsatt.** 74 overlevende funn på 20 kjøringer til ~0,07 USD per kjøring. Argumentet om treningsdistribusjons-avstand holder, og verken Claude Code eller Codex tilbyr det.
- **«Adversariell syntese» filtrerer nesten ingenting.** 89 % av Codex-funn og 100 % av selv-funn overlever. Enten er syntesen konsiliatorisk (det motsatte av hensikten), eller så rapporteres tallene av samme modell som gjorde jobben. Uansett er tallet ikke et mål på kvalitet.
- **Den adaptive ruteren (cost-ledger) kan aldri virke.** Lens-navnet for tredjehuset er logget i fem varianter (`third-house`, `third-lens`, `third-lens-glm`, `third-house-glm`, `third-lens-deepseek`) og domenene i to (`shell-infra` og `shell-infra-scripting`, `plan` og `planning-docs`). Terskelen er ti *rene* reviews per domene, og med 89 % overlevelse finnes det nesten ingen rene reviews. På to måneder har den aldri hoppet over noe. Den er død vekt.

## Ta bort

| Hva | Hvorfor | Hvor |
|---|---|---|
| **cost-ledger** (scripts + ni linjer i pitfall-verification) | Se over. Kan aldri nå terskelen. | `scripts/cost-ledger/`, `pitfall-verification:526-534` |
| **ios-visual-explore** + `scripts/computer_use/` | Betalt Gemini computer-use for noe vertsmodellen gjør multimodalt via XcodeBuildMCP `screenshot`/`snapshot_ui`. Lukk IDEAS.md Fase 4 (cliclick) samtidig. | `skills/ios-visual-explore`, `IDEAS.md:513-526` |
| **autonomy-blokken** i emitterte CLAUDE.md | Claude Code-harnessen sier nå det samme ordrett («You are operating autonomously … Do not stop»). 31 linjer per prosjekt for null netto. | `blocks/autonomy.md` |
| **Personlige stier** i office-hours-track-aware | `~/super-me/brain/ideas/seeds` og 28 linjer spesialtilfelle for `$HOME/super-me/` i en publisert plugin. | `office-hours-track-aware:90-124` |
| **Review-historikk inne i skills** (~250 linjer) | «Hvordan vi kom hit» hjelper ikke modellen som kjører. Hører hjemme i CHANGELOG. Inkluderer sju «(Codex, 2.53.0)»-notater i en runner-mal som genereres inn i brukerprosjekter. | `autoimplement:433-457`, `:151-156`, `:234-244`; `macos-e2e-scaffold:352-452`; `adapt:420-447` |
| **Hardkodede modellnavn, priser og benchmarks** | `codex (gpt-5.5)` ti ganger; `claude-fable-5` (Fable 5.1 er ute); «$10/$50», «63.2 % SWE-bench Pro», «GLM ≈18 pts below Fable 5»; `z-ai/glm-5.2` (OpenRouter serverer `z-ai/glm-5.3` nå). gstack 1.84.1 løser modellvalg via miljøvariabler; la scriptene resolve, hold tier-navn som ord. | `autoimplement:440-453`, `model-routing.md:34-49`, `third-lens-review:44-56,114`, `scripts/third-lens-review.py:36-50`, `blocks/multi-lens-review.md:29-30`, `blocks/model-routing-section.md:7` |
| **Legacy-formater i session-continuity** | `mode: auto`, `## Mode: auto`, v1.12-frontmatter uten `type:`. Tre lesestier for én kontrakt, i hvert prosjekt. | `blocks/session-continuity.md`, `context-handoff:84,105-112` |

## Forenkle eller slå sammen

1. **Halver emittert CLAUDE.md.** Et native prosjekt får ~550 linjer fra pluginen. Anthropics egen anbefaling er under 200 linjer totalt («longer files consume more context and reduce adherence»), og pluginens eget budsjett sier det samme (`setup-routing:414`). Flytt de 60 linjene som forklarer hook-rapporten (`git-hygiene.md`, «When the session-start hook reports unlanded work») inn i hookens egen stdout, så betales de bare når hooken faktisk fyrer. Prosa som *må* skje, skal være hooks, ikke instruksjoner.
2. **adapt (770 linjer) → deterministisk merge-script.** Growth check, attribution check, `emitted=`-provenance og ni nesten identiske firecase-blokker eksisterer fordi LLM-utført markdown-kirurgi en gang slettet 125 linjer. Et Python-script som finner markør, erstatter til neste overskrift, teller linjer og skriver diff-rapport pensjonerer hele apparatet og lint-regel E13. SKILL.md blir ~150 linjer.
3. **setup-routing inn i adapt.** Skill-rostertabellene er dupliserte (`setup-routing:76-172` ≈ `adapt:82-176`), provenance-prosa og `{{E2E_EXECUTOR}}`-resolver likeså. adapt på tom CLAUDE.md *er* setup.
4. **ios- og macos-e2e-scaffold → én skill.** ~80 % tekstlig overlapp, og tvillingene har allerede driftet (identifier-skann 5 vs 25 linjer, runner-header v1.0.0 vs v2.53.0). Runner-scriptet ut i `templates/`.
5. **ios- og macos-native-review → `apple-native-review`.** Kategorikunnskapen beholdes per plattform; stillaset skrives én gang. Bytt WebFetch-mot-SPA-hacket med `mcp__apple-docs__get_apple_doc_content`, som xcode-tools-blokken allerede anbefaler.
6. **swiftui-design-consultation (851 linjer).** Fjern MCP-parameter-verifiseringstabellen, YAML-schema-pipelinen, monotonisitetsvakten og historikk-notatene. Vurder tynn SwiftUI-mal-wrapper rundt gstack `/design-consultation`, som nå genererer font- og fargeforhåndsvisninger selv.
7. **Én eier for Codex-passet.** Codex kan i dag kjøre på samme diff fra fire steder: pitfall Stage 2, autoimplement steg D, gstack `/ship` steg 9 og gstack `/review` 5.7. Forslag: gstack eier Codex (det er upstream, med GPT-6 Astra som standard); pitfall-verification beholder domain-inference og tredjehuset; autoimplement kaller `/review` og får Codex derfra.
8. **autoimplement: Workflow-verktøyet som runtime.** Behold policyen (refusals, review-kjede ved fasegrenser, pre-flight på selve planen); la Claude Codes Workflow gjøre dispatch, parallellisering og resume. Vurder også den blanke «aldri retry»-regelen, som var tilpasset svakere subagenter.
9. **htmlify: demoter Safari-flyten, behold stilen.** Artifact-verktøyet gir hostet, tema-bevisst side med kommentarer og live republish. Det som er verdt å beholde er `companion.css` som designsystem (den er kanon for HTML-utseendet). «Lukk alle Safari-vinduer» og PostToolUse-hooken bør bort.
10. **e2e-route: routing-tabell + executor-pin, ~120 linjer.** Beredskapsstigen fra hendelsen 2026-06-27 («hvis din eneste plan er å bli varslet, har du ingen plan») er løst av Monitor-verktøyet.
11. **context-handoff: behold YAML-kontrakten, dropp resten.** Fortsatt nyttig på tvers av maskiner; på samme maskin dekker `--resume` og 2.50-hookparet det meste.
12. **spec-drift: døm etter egen ti-kjøringer-regel** (`IDEAS.md:558`) før mer herding. Sha-pin, engangstoken og Unicode Cf-escaping er tungt for en lokal solofil.

## Behold, med små justeringer

- **pitfall-verification, domain-inference-delen** (`:405-475`). Den eneste delen som ikke er «generic-LLM-common», som skillen selv sier. Behold tier-gaten med `classify-change.py`: mekanisk gulv i stedet for selvvurdering er riktig retning og bør bli mønster, ikke unntak.
- **third-lens-review.** Behold liten. Oppdater til `z-ai/glm-5.3`, legg til en vaktbikkje mot OpenRouter `/models` (scriptet innrømmer selv «NO watchdog»), fjern benchmark-tallet.
- **verify-and-land.** Mest konkret nyttige skill i pluginen. Dedupliser mot xcode-tools-blokken, som gjentar femstegs-sekvensen.
- **quality-review.** Behold; kategori 12 blir peker til `claude-api`-skillen, tallpåstander («5–15 % feilrate») ut.
- **Hooks for branch-hygiene og session-resume.** Deterministisk, ikke prosa. Riktig lag.

## Anslått effekt

| | Nå | Etter |
|---|---|---|
| SKILL.md-linjer | 7 325 | ~3 500 |
| Emittert CLAUDE.md, native prosjekt | ~550 | ~250 |
| Skills | 18 | 12–13 |
| Steder Codex kan kjøre på samme diff | 4 | 1 |
| Hardkodede modell-IDer/priser i emitterte blokker | 8 | 0 |

## Rekkefølge

1. **Hygiene, én dag.** glm-5.3, `gpt-5.5` ut, personlige stier ut, cost-ledger ut, ios-visual-explore fryses, legacy-formater ut, priser og benchmarks ut. Ingen atferdsendring for brukere.
2. **Kontekstskatt.** autonomy-blokken ut, hook-rapport-prosa inn i hooken, session-continuity slankes. Mål: under 250 emitterte linjer.
3. **Sammenslåinger.** e2e-scaffold, native-review, setup-routing→adapt.
4. **Arkitektur.** Codex-eier, adapt-script, autoimplement på Workflow.

Kjør `/skill-doctor` før og etter fase 2 for å måle kontekstkostnaden, og bruk `claude plugin eval --ablation with-without` når det er ute av early access for å teste om noen av de fjernede blokkene faktisk bidro.

## Forbehold

- GPT-6 Astra som Codex-standard er bekreftet via Codex' GitHub-release-notater og gstack 1.84.1, ikke via en OpenAI-kunngjøring.
- «Adversariell syntese filtrerer ingenting» er lest ut av loggen; jeg har ikke lest de enkelte syntesene. Det kan være at funnene var reelle. Det endrer ikke konklusjonen om cost-ledger.
- Anthropic sier ingen steder at stillas er unødvendig. Deres eget harness-innlegg (mars 2026) sier at en separat evaluator ble overflødig på rutinearbeid, men ga reell gevinst ved kapasitetsgrensen. Det er nøyaktig skillet denne vurderingen trekker: tredjehuset ved høy innsats overlever, seremonien på hver oppgave gjør det ikke.

## Kilder

- Claude Code changelog og docs: https://code.claude.com/docs/en/changelog, /ultrareview, /workflows, /memory, /sub-agents
- Anthropic: https://www.anthropic.com/claude-fable-and-mythos-5-1, https://www.anthropic.com/news/claude-opus-5, https://www.anthropic.com/news/claude-sonnet-5, https://www.anthropic.com/engineering/harness-design-long-running-apps
- Codex CLI: https://github.com/openai/codex/releases, https://learn.chatgpt.com/docs/developer-commands?surface=cli
- GLM-5.3: https://huggingface.co/zai-org/GLM-5.3, https://docs.z.ai/devpack/overview
- gstack changelog (upstream, 1.83–1.84.1): https://github.com/garrytan/gstack
- superpowers releases: https://github.com/obra/superpowers/releases
- Konsensus: https://addyosmani.com/blog/agent-harness-engineering/, https://mcp.directory/blog/superpowers-skill-worth-it-2026, https://tylerfolkman.substack.com/p/claude-code-workflows-are-here-dont
