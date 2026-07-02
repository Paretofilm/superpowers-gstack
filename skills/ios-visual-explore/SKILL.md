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
  [--max-steps N]                    # default: 25
  [--orientation portrait|landscape] # default: portrait (see iPad / orientation below)
  [--dry-run]                        # single planning probe; no actions executed
  [--out <dir>]                      # default: computer-use-runs/run-<timestamp>
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

# iPad in landscape — rotate the simulator to landscape FIRST (see below)
scripts/ios-visual-explore \
  --udid "<iPad-UDID>" \
  --bundle "com.example.MyApp" \
  "utforsk delt-visning-layouten i landskap" \
  --orientation landscape
```

## iPad and orientation (Phase 2)

The skill supports iPhone and iPad, in either orientation, but **fullscreen only**.

- **You must rotate the simulator yourself before the run.** Neither `simctl` nor `idb` can rotate a simulator programmatically, so the tool does **not** set orientation — it only *verifies* it. For landscape, rotate **left** (Simulator.app: Device → Rotate Left, or **Cmd+←**) so the app is in landscape, then launch. If the Application frame's aspect doesn't match `--orientation`, preflight fails closed with a "rotate the sim first" message rather than running against the wrong layout.
- **Landscape must be a LEFT rotation (Cmd+←).** `simctl io screenshot` always captures the device's native-portrait framebuffer, so a landscape app lands rotated inside a portrait-shaped PNG. The tool rotates that screenshot upright before the model sees it — but the rotation direction is fixed for a left-rotated device. A right-rotation (Cmd+→) would make the model see an upside-down image and mis-target taps. iPad safe-area is symmetric, so left vs right costs you nothing; just always rotate left.
- **Fullscreen only.** The app must occupy the full screen. Split View, Slide Over, and Stage Manager windows are rejected at preflight: fullscreen is confirmed empirically (screenshot pixel-width ÷ Application frame-width must be a clean @2x/@3x backing scale), so a narrower windowed frame fails closed. There is no split-view or multi-window exploration.
- **Safe-area insets** are looked up from a per-device-class × orientation table (`INSET_TABLE`), since iPad's accessibility tree exposes no status-bar / home-indicator elements to derive them from. Values are HIG-typical (iPad ≈ 24 pt top / 20 pt bottom). Taps and drags whose coordinates fall outside the safe area are **rejected** (logged as `rejected` / "outside safe area") instead of executing, so the run never fires into the status bar or home indicator.
- **Foreground oracle is self-referential.** The target app is identified by its `Application.AXLabel` (its display name, e.g. "Innstillinger"), captured at launch and compared each step — iPad's tree carries no bundle id on the Application element. A mismatch (wrong app *or* home screen, whose label differs) yields `app_left_foreground`. If the app exposes no AXLabel at all, preflight fails closed (the oracle would otherwise never confirm foreground).
- **iPad describe-all is flaky during transitions** (it briefly returns a degenerate tree). Every accessibility query retries until the tree is stable (>3 typed elements). A cold-booted iPad can also take 30–60 s after "booted" before its UI renders — wait for it before launching.

### Known limitations (honest best-effort)

- **Sim orientation persists after the run** — the tool never rotates, so the simulator stays in whatever orientation you left it. Rotate back manually if needed.
- **Slide Over with the target still frontmost** — if another app is in a Slide Over panel while the target remains the frontmost fullscreen Application, the oracle still reports foreground; the overlay is not separately detected.
- **No split/Stage Manager coverage** — by design (see fullscreen-only above); multi-window layouts are out of scope for this phase.

## Output contract

The skill writes **two artefacts** to the output directory and prints a **text-only summary** to stdout:

| Artefakt | Beskrivelse |
|----------|-------------|
| `<out>/report.md` | Full Markdown report: mission, environment info, step journal, critic findings |
| `<out>/screenshots/` | Every step's screenshot is persisted. The vision critic inspects **every screen the run reached** (baseline + each step), so visual issues on successfully-navigated screens are caught, not just on endpoints and error steps. Perceptual near-duplicate suppression (e.g. successive scrolls) is a future `ahash` optimization. |

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
