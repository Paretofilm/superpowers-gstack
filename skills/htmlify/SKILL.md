---
name: htmlify
description: Generate beautiful, pedagogical HTML companions for superpowers-gstack MD artifacts (design docs, handoffs, plans). Auto-opens via --open flag. Generates per-directory dashboards. Triggered manually or via PostToolUse hook on Write/Edit of artifact-pattern MD files.
---

# /htmlify

Lager visuelt elegante HTML-companions ved siden av MD-artefakter, og en aggregert dashboard-side per katalog. Designet for vibe-codere som ikke orker å lese verbose MD-output fra skills som /office-hours, /autoplan, /plan-eng-review, /context-handoff osv.

**Når det aktiveres:**
- Bruker sier "html-ify", "lag html av", "generer HTML companion"
- Bruker spør "kan jeg få en penere visning av denne MD-en"
- PostToolUse-hook (når installert) auto-trigger ved Write/Edit på artefakt-MD
- Invoked programmatically by `/superpowers-gstack:swiftui-design-consultation`
  for Phase 3 proposal preview and Phase 6 DESIGN.html generation

## How to invoke

Skill-katalogen oppdages av Claude Code som "Base directory for this skill" ved invokering. Wrapper-binæren `bin/htmlify` self-lokaliserer og kan kjøres fra hvilken som helst cwd:

```bash
"$SKILL_DIR/bin/htmlify" <args>
```

Hvor `$SKILL_DIR` er katalogen denne SKILL.md filen ligger i. Eksempel når installert via Claude Code marketplace:

```bash
~/.claude/plugins/cache/paretofilm-plugins/superpowers-gstack/<version>/skills/htmlify/bin/htmlify <args>
```

Wrapper-en sjekker at `bun` og deps er installert; printer feilmelding (exit 5) hvis ikke.

## First-run setup (one-time)

Deps må installeres én gang per installasjons-lokasjon. Wrapperen forteller deg den nøyaktige kommandoen hvis den feiler:

```bash
cd "$SKILL_DIR" && bun install
```

Etterpå er skill'en klar til bruk uansett antall invokeringer.

## Usage

### Render én MD til HTML companion

```bash
"$SKILL_DIR/bin/htmlify" <path-to-md>
```

Output: `<dir>/.superpowers-html/<name>.html`. Også en `companion.css` blir kopiert til samme katalog.

### Med auto-open (macOS)

```bash
"$SKILL_DIR/bin/htmlify" <path-to-md> --open
```

### Generer dashboard for en katalog

```bash
"$SKILL_DIR/bin/htmlify" dashboard <dir>
```

Output: `<dir>/.superpowers-html/index.html` med liste av alle artefakter i katalogen sortert by mtime desc.

### Flags

- `--plan <plan.json>` — Last v2 rendering plan (rik layout: comparison-matrix, flowchart-svg, pullquote, callout-box, stats-bar, two-column, expandable, diff-card, feedback-panel). Uten flagget rendres v1-template.
- `--open` — Åpne resulterende HTML i **Safari** (macOS only) som distraksjonsfri leser. **Alle eksisterende Safari-vinduer lukkes først** så HTML-en er det eneste som vises. Brukerens default-nettleser røres ikke.
- `--no-clobber` — Skip render hvis HTML er nyere enn MD
- `--force-rebuild` — Tving render selv ved no-clobber

## Enhanced rendering (v2 — plan-driven layout)

v1 gir "penere MD med strukturerte cards" — det er en god default. **v2 gjør HTML-en til en informativ plansje** med komponenter som comparison-matrix, flowchart-svg, pullquotes, stats-bar, callout-boxes, diff-cards og en interaktiv feedback-panel.

V2 fungerer via en **rendering plan** (JSON-fil) som du genererer **i Claude Code-sesjonen** (gratis under Max-plan; **bruker IKKE Anthropic API**) og sender til CLI med `--plan`.

### Når bruke v2?

- MD-en er lang/tett og ville hatt nytte av visuell hierarki
- Det er en sammenligning, et flytdiagram, før/etter, eller en tidslinje skjult i prosaen
- Du vil ha en feedback-runde fra brukeren (sjekkbokser + radio + kommentar → clipboard JSON)

### Hvordan generere en plan (i denne sesjonen)

1. **Les MD-en** med Read-tool.
2. **Identifiser visuelle muligheter**:
   - H2 med "Approaches Considered" / "Options" → `comparison-matrix`
   - H2 med arkitektur/pipeline/flyt → `flowchart-svg`
   - Memorable quote i teksten → `pullquote` med `after_section`
   - "Note:" / "Warning:" / "Insight:" → `callout-box`
   - Metrics, before/after counts → `stats-bar`
   - To kolonner som speiler hverandre → `two-column`
   - Lang side-info som ikke skal dominere → `expandable`
   - Kodeblokker som er "før/etter" → `diff-card`
3. **Skriv plan-JSON** til en temporary fil med strukturen under.
4. **Kjør CLI**: `"$SKILL_DIR/bin/htmlify" <md> --plan <plan.json> --open`
5. **Sett alltid `feedback_panel`** med relevante premises/approaches + tilpasset spørsmål. Bruker kan trykke "Copy feedback as prompt" og lime inn i neste sesjon.

### Plan-JSON skjema

```json
{
  "version": 1,
  "sections": [
    {
      "heading": "Approaches Considered",
      "treatment": "comparison-matrix",
      "data": {
        "items": [
          {"title": "Option A", "summary": "...", "pros": ["..."], "cons": ["..."], "effort": "1d", "risk": "low"},
          {"title": "Option B", "pros": ["..."], "cons": ["..."], "highlighted": true}
        ]
      }
    },
    {
      "heading": "Architecture",
      "treatment": "flowchart-svg",
      "data": {
        "orientation": "LR",
        "nodes": [{"id": "a", "label": "Input"}, {"id": "b", "label": "Process", "emphasis": true}, {"id": "c", "label": "Output"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c", "label": "transform"}]
      }
    }
  ],
  "pullquotes": [
    {"text": "...", "attribution": "...", "after_section": "Problem Statement"}
  ],
  "feedback_panel": {
    "enabled": true,
    "premises": ["P1 label", "P2 label"],
    "approaches": ["A1 label", "A2 label"],
    "custom_questions": [
      {"id": "q1", "label": "Did this layout help?", "type": "radio", "options": ["yes", "no"]},
      {"id": "q2", "label": "Free notes", "type": "text"}
    ]
  }
}
```

### Treatments-katalogen

| Treatment | Når bruke | Data-form |
|-----------|----------|-----------|
| `section-card` | Default — vanlig prosakort | (ingen — bruker MD-body) |
| `comparison-matrix` | 2-5 alternativer side-ved-side | `{items: [{title, summary?, pros?, cons?, effort?, risk?, highlighted?}]}` |
| `flowchart-svg` | Pipelines, state machines, arkitektur | `{nodes: [{id, label, shape?, emphasis?}], edges: [{from, to, label?}], orientation?: "TB"\|"LR"}` |
| `pullquote` | Memorable quote (kan også stå i `pullquotes`-array) | `{text, attribution?}` |
| `callout-box` | Note/warning/insight/danger | `{level?: "info"\|"warn"\|"insight"\|"danger", title?, body}` |
| `stats-bar` | Tall, metrics, before/after counts | `{items: [{label, value, delta?, trend?: "up"\|"down"\|"flat"}]}` |
| `two-column` | Sammenligning innenfor ett tema | `{left: {heading?, body}, right: {heading?, body}}` |
| `expandable` | Lang side-info som skal kunne kollapses | `{summary, body, open?}` |
| `diff-card` | Før/etter kode eller tekst | `{title?, before: {label?, content}, after: {label?, content}}` |

### Viktige regler

- **Bruk ALDRI API** — plan-generering skjer i denne Claude Code-sesjonen (Max-plan compute = gratis)
- **Headings må matche MD-en** — case-/whitespace-insensitivt. Plan-seksjon uten matching H2 rendres som ny seksjon.
- **`treatment: "section-card"`** = ikke override; bruk default rendering
- **`feedback_panel` har alltid et kommentar-felt** — uavhengig av om premises/approaches/custom_questions er tomme
- **Plan = optional** — uten `--plan` får brukeren v1-rendering (samme som før)

## Frontmatter types som støttes

- `type: design-doc` — fra /office-hours
- `type: handoff` — fra /context-handoff (eller filnavn `handoff.md` for legacy)
- `type: plan` — fra /autoplan
- Manglende eller ukjent frontmatter → generic fallback med banner

## Exit codes

- 0 — success
- 1 — usage error (bad CLI args)
- 2 — schema validation failure
- 3 — MD parse error
- 4 — I/O error (file not found, not writable)
- 5 — setup error (deps not installed, bun missing)

## Auto-trigger (PostToolUse hook)

For automatisk å fyre htmlify når en skill skriver en artefakt-MD, kjør installeren én gang. Path avhenger av om du jobber fra repo-rota eller fra plugin-installasjonen:

**Fra repo (utvikling):**
```bash
./scripts/setup-htmlify-hook.sh
```

**Fra plugin-installasjonen (marketplace):**
```bash
~/.claude/plugins/cache/paretofilm-plugins/superpowers-gstack/<version>/scripts/setup-htmlify-hook.sh
```

Hook'en matcher:
- Filnavn `handoff.md`
- Mønstre: `*-design-YYYYMMDD-HHMMSS.md`, `*-plan-YYYYMMDD-HHMMSS.md`
- Alle MD-er under `.gstack/projects/`
- Loop-prevention: skip MD-er i `.superpowers-html/`

Hook-skriptet self-lokaliserer — det vil alltid kalle `htmlify` fra den katalogen den selv ligger i, så det er trygt å installere hooks fra plugin-cache-stien.

## Development

Kun relevant hvis du jobber fra repo-rota i `~/Developer/superpowers-gstack/`:

```bash
cd skills/htmlify
bun install    # first run
bun test       # 138 tests (v2)
```

Artefakter brukt under utvikling: se design-doc og test-plan i `~/.gstack/projects/Paretofilm-superpowers-gstack/`.
