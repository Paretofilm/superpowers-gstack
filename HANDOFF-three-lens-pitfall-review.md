---
type: handoff
topic: integrer GLM-5.2 som tredje lens i pitfall-review
date: 2026-06-21
source_evidence: LiveSet Pro (Fase 1) — ~/Developer/LiveSetPro
status: proposed
active_task: gstack-three-lens-pitfall-review
next_step: "Legg en tredje-lens-tier (GLM via OpenRouter) inn i pitfall-review-flyten: enten som steg 4 i pitfall-verification-skillen, eller som en egen /glm-review-skill analog med /codex, gatet på ship-worthy/arkitektur-endringer. Se ## Gjenstående arbeid."
---

# Handoff — tre-lens pitfall-review (Claude + Codex + GLM)

## Hva dette er

Et forslag, med feltbevis, om å gjøre pitfall-review til en **tre-modell-prosess** for ship-worthy
endringer: Claude (self-pitfall) → Codex → GLM-5.2, avsluttet med en obligatorisk Claude-synthese.
Bevisene kommer fra en faktisk sesjon på LiveSet Pro der GLM-5.2 ble kjørt som tredje lens *etter*
at Claude + Codex allerede hadde fikset 14 issues — og likevel fant reell ny verdi.

## Hvorfor (feltbevis fra LiveSet Pro)

GLM-5.2 (`z-ai/glm-5.2` via OpenRouter, $0,054, hele repoet i 1M-kontekst) fant ting de to andre
lensene bommet på:

| GLM-funn | Type | Hvorfor de to andre bommet |
|----------|------|-----------------------------|
| Den testede kjernen var **dead code** — adapteren instansierte den aldri | Nytt, arkitektur | Claude/Codex review'de hver del isolert; ingen så at adapteren bypasset hele den testede modellen |
| `reassign` detacher noder under aktiv render → `EXC_BAD_ACCESS` | Skjerpet | Codex nevnte pause-vs-stop; GLM skjerpet til use-after-free under render |
| C-scheduler: sene events emitteres med fortids-sampletid; overflow droppes stille | Nytt | Begge fokuserte på den normale sorterte stien, ikke degraderte tilstander |
| `instantiateAU`-timeout lekker den sent-ankommende AU-en (~100-vis MB) | Skjerpet | Claude noterte P3; GLM løftet til P2 med minnetall |
| `outputVolume` ikke sample-nøyaktig for crossfade | Overdrevet, men nyttig | Ingen utfordret gain-mekanismen |

**Den ikke-åpenbare verdien:** GLM sine *overdrevne* funn (sample-nøyaktighet) var teknisk feil for
en musikalsk crossfade — men å motargumentere dem tvang fram en presis grense ingen lens hadde
formulert: *MIDI-levering trenger sample-presisjon; fade-envelope og takt-følging tåler 20–50 ms.*

**Generelt mønster:** cross-modell **enighet = høy tillit; uenighet = der verdien sitter** — den
tvinger en eksplisitt, begrunnet beslutning i stedet for en uuttalt antakelse.

## Hvilken lens fanger hva (observert)

- **Claude (self-pitfall, Anthropic):** domene-logikk, edge-cases, idempotens, kontrakt-konsistens
  *innen* ett artefakt. Svakhet: forfatter-bias (egne blindsoner).
- **Codex (OpenAI):** cross-file drift, concurrency-kontrakter, konkrete kjør-bugs (falsk timeout,
  stale async-resume, dobbel-acquire-lekkasje). Skarpest på «vil koden faktisk kjøre riktig».
- **GLM-5.2 (Zhipu):** arkitektur-nivå («du wiret det aldri sammen»), utfordrer kjerne-antakelser.
  Annet trenings-distribusjon → ser det de to andre tar for gitt. Tendens til å over-generalisere
  strenghet → MÅ synthesiseres.

Ingen var redundant: hver fant noe de to andre ikke fant.

## Forslaget

### Tiering — når hvor mange lenser
| Endring | Lenser |
|---------|--------|
| Triviell (docs, typo, rename) | Claude self-pitfall |
| Standard (feature, bugfix) | Claude + Codex |
| **Ship-worthy / arkitektur / RT / sikkerhet / kontrakter** | **Claude + Codex + GLM** |

### Sekvens — tre hus, hver på PATCHET artefakt
1. Claude self-pitfall (2 runder maks) → fiks.
2. Codex-lesing på patchet kode → fiks.
3. GLM-lesing på patchet kode → fiks.
4. **Synthese (Claude, obligatorisk):** dedupe, flagg overdrevne funn med begrunnelse, forsone
   uenighet til eksplisitte beslutninger, prioriter fix-nå vs utsett.

Rekkefølge Claude→Codex→GLM gir hver senere lens en renere artefakt og maksimerer hus-diversitet.

### Mekanisme
- GLM via OpenRouter, `z-ai/glm-5.2` (1M ctx → hele repoet i ett kall).
- Nøkkel: macOS Keychain, account `openrouter-api-key`
  (`security find-generic-password -a openrouter-api-key -w`).
- Kost: ~$0,05–0,15/kjøring (input ~30k tokens; $1,20/$4,10 per Mtok). Sjekk saldo via
  `GET https://openrouter.ai/api/v1/credits`.
- Råoutput presenteres + Claude-synthese på toppen (aldri bare dump).

### Guardrails
- **Data-routing:** GLM kjører på Zhipu-infra (Kina). OK for ikke-sensitiv kode; si det eksplisitt.
  For sensitiv kode (auth, nøkler, helse/finans): hopp over GLM eller bruk en vestlig tredje-lens
  (`google/gemini-3.1-pro-preview`) i stedet.
- **Kost-tak:** unngå `*-pro` extended-reasoning ($30–180/Mtok) for rutine-review; non-pro holder.
- **Skip trivial:** tiering-tabellen styrer; ikke kjør tre lenser på en typo.
- **Synthese ikke valgfri:** en tredje lens uten forsoning gir støy (overdrevne funn tatt for
  pålydende).

## Gjenstående arbeid (implementasjon i gstack)

1. **Velg form:** (a) nytt steg 4 i `skills/pitfall-verification/SKILL.md` for ship-worthy
   artefakter, ELLER (b) egen `skills/glm-review/SKILL.md` analog med codex-skillen, kalt fra
   pitfall-flyten. Anbefaling: (b) — gjenbrukbar standalone + referert fra pitfall-verification,
   speiler hvordan `/codex` allerede er strukturert.
2. **Script:** pakk `glm_review.py`-mønsteret (fra LiveSet Pro-sesjonen) til et parameterisert
   script under `scripts/` — filliste-glob + prompt-mal + OpenRouter-POST + kost/usage-utskrift.
3. **Skill-tekst:** speil codex-skillens struktur (auth-probe, timeout, presenter-verbatim +
   synthese, kost-estimat). Bruk Keychain-nøkkel, ikke env.
4. **Tiering-regel:** dokumenter tre-lens-tieringen i pitfall-verification-skillen og/eller i
   verifiserings-prosess-seksjonen som CLAUDE.md-templates genererer (`setup-routing`/`adapt`).
5. **Guardrail-håndheving:** data-routing-sjekk (sensitiv kode → Gemini-fallback) + saldo-sjekk
   før kjøring.
6. **CHANGELOG + versjon:** ship-worthy endring → bump + CHANGELOG-entry.

## Åpne spørsmål for implementer
- Skal GLM-lensen være default-PÅ for ship-worthy, eller opt-in (`/pitfall --three-lens`)?
- Vestlig tredje-lens-default for sensitiv kode: Gemini 3.1 Pro vs xAI Grok 4.3 (begge ikke-Kina)?
- Bør synthese-steget formaliseres som en egen sub-skill, eller forbli inline i orchestrator?

## Kilder
Feltbevis-sesjon: `~/Developer/LiveSetPro` (branch `feat/phase1-source-mixer`), commit-historikk
rundt 2026-06-21 (codex-fikser `eb38dd9`, GLM-review-syntese i samtalen). Original notat-versjon
ble flyttet hit fra LiveSet Pro-repoet.
