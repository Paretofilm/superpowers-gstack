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

## First-run check

Sjekk at deps er installert. Hvis ikke, instruer brukeren — IKKE auto-installer:

```bash
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d "$SKILL_DIR/node_modules" ]; then
  echo "ERROR: htmlify deps not installed. Run:"
  echo "  cd $SKILL_DIR && bun install"
  exit 5
fi
```

## Usage

### Render én MD til HTML companion

```bash
bun run skills/htmlify/src/cli.ts <path-to-md>
```

Output: `<dir>/.superpowers-html/<name>.html`. Også en `companion.css` blir kopiert til samme katalog.

### Med auto-open (macOS)

```bash
bun run skills/htmlify/src/cli.ts <path-to-md> --open
```

### Generer dashboard for en katalog

```bash
bun run skills/htmlify/src/cli.ts dashboard <dir>
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
- 5 — setup error (run `cd skills/htmlify && bun install`)

## Auto-trigger (PostToolUse hook)

For automatisk å fyre htmlify når en skill skriver en artefakt-MD, kjør én gang:

```bash
./scripts/setup-htmlify-hook.sh
```

Hook'en matcher:
- Filnavn `handoff.md`
- Mønstre: `*-design-YYYYMMDD-HHMMSS.md`, `*-plan-YYYYMMDD-HHMMSS.md`
- Alle MD-er under `.gstack/projects/`
- Loop-prevention: skip MD-er i `.superpowers-html/`

## Development

```bash
cd skills/htmlify
bun install    # first run
bun test       # 74 tests
```

Artefakter brukt under utvikling: se design-doc og test-plan i `~/.gstack/projects/Paretofilm-superpowers-gstack/`.
