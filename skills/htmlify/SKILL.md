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

- `--open` — Åpne resulterende HTML i nettleser (macOS only)
- `--no-clobber` — Skip render hvis HTML er nyere enn MD
- `--force-rebuild` — Tving render selv ved no-clobber

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
bun test       # 74 tests
```

Artefakter brukt under utvikling: se design-doc og test-plan i `~/.gstack/projects/Paretofilm-superpowers-gstack/`.
