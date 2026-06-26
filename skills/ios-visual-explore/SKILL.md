---
name: ios-visual-explore
description: Tier-2 visual exploration of an iOS app via Gemini computer-use. Invoke when accessibility-based end-to-end testing (XCTest/XCUITest) does not surface enough — e.g. layout regressions, visual glitches, missing UI elements not reachable via the accessibility tree, or when a mission requires following visual cues across screens. Produces a text-only Markdown report (file paths, never inline images) to keep agent context clean.
---

# iOS Visual Explore

## When to use

Use this skill as a **Tier-2 escalation** after standard accessibility-based testing has already been attempted or is insufficient:

- Visual or layout regressions that accessibility assertions cannot detect
- Flows driven by visual landmarks (images, icons, colour cues) rather than labels
- Exploratory missions ("find any visual issues on the onboarding flow") where the goal is open-ended
- Debugging a user-reported visual issue that doesn't reproduce in unit tests

Do **not** use as a first resort — prefer deterministic XCUITest flows when the app's accessibility tree is well-formed.

## Prerequisites

- A booted iOS simulator (or physical device via idb) with the target app installed
- `idb_companion` available on PATH (or installed via Homebrew)
- `GEMINI_API_KEY` / `gemini-api-key-paid` in macOS Keychain (for the Gemini vision backend)
- `uv` available on PATH (for the shim runner)

## How to invoke

```bash
scripts/ios-visual-explore \
  --udid <SIMULATOR_UDID> \
  --bundle <BUNDLE_ID> \
  "<mission description>" \
  [--max-steps N]        # default: 25
  [--dry-run]            # single planning probe; no actions executed
  [--out <dir>]          # default: computer-use-runs/run-<timestamp>
```

**Examples:**

```bash
# Full exploration run (up to 15 steps)
scripts/ios-visual-explore \
  --udid "A1B2C3D4-..." \
  --bundle "com.example.MyApp" \
  "trykk gjennom onboarding-flyten og rapporter visuelle problemer" \
  --max-steps 15

# Dry run — shows the planned first action without executing anything
scripts/ios-visual-explore \
  --udid "A1B2C3D4-..." \
  --bundle "com.example.MyApp" \
  "utforsk innstillinger-skjermen" \
  --dry-run
```

## Output contract

The skill writes **two artefacts** to the output directory and prints a **text-only summary** to stdout:

| Artefakt | Beskrivelse |
|----------|-------------|
| `<out>/report.md` | Full Markdown report: mission, environment info, step journal, critic findings |
| `<out>/screenshots/` | Retained screenshots from the run (every step is persisted; the critic input is selected by status + first/last endpoints via `should_retain`) |

**Stdout** contains only text: file paths and a structured summary of findings. It never includes inline images or base64 data. This keeps the Claude context clean when the summary is captured or pasted into a conversation.

## Interpreting results

The `status` field in the report and stdout summary is a stable machine token with exactly four possible values:

- **`completed`** — the model signalled it was done before hitting the step limit
- **`step_limit`** — the run exhausted `--max-steps`; consider increasing it or narrowing the mission
- **`app_left_foreground`** — the foreground oracle detected the target app was no longer in the foreground (e.g. backgrounded or crashed); the partial journal is still written
- **`error`** — abnormal failure (idb error, API error, screenshot failure); check the journal in `report.md` for the first failing step

Findings in the report are produced by the Gemini vision critic and may include false positives; treat them as leads, not definitive bugs. A report is always written even on `error` status — the journal up to the point of failure is preserved.

## Architecture note

The skill orchestrates five layers built in Phase 1:
`preflight` → `executor_idb` → `loop` (Gemini computer-use) → `dedup` → `critic` + `report`.
VisionCritic (in `scripts/computer_use/gemini.py`) runs the evidence screenshots through Gemini vision; it degrades gracefully to an empty findings list on any API error — the run never crashes on critic failure.

## Deferred to Phase 2

The following capabilities are implemented but not yet wired into the live pipeline:

- **Perceptual near-duplicate dedup** — `ahash`/`is_critic_dup` in `dedup.py` are present but intentionally not wired (avoids an image-decode dependency). Phase 2 will gate critic input on visual similarity.
- **Gemini-3 `signature` echo** — multi-step thought continuity via interaction signatures.
- **Richer action coverage** — `go_back`, `long_press`, `press_key` action kinds are not yet handled in `actions.py`.
