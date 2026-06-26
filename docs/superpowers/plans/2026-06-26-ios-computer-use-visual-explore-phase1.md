# iOS Computer-Use Visual Explore — Fase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Et autonomt CLI-script som driver en fri visuell utforsking av en SwiftUI-app i iPhone-simulatoren via Gemini computer_use + idb, og produserer en strukturert rapport med visuelle funn.

**Architecture:** Autonomt loop-script (alt. A i spec). En plattform-agnostisk loop-motor kaller Gemini computer_use, mapper handlinger gjennom et action-adapter-lag til en pluggbar executor (idb for touch), tar skjermbilder, og kjører til slutt et visuelt kritiker-pass. Rene funksjoner (koordinat-mapping, action-adapter, dedup, rapport) er deterministisk testbare; sim-/API-avhengige deler er gated på en spike (Task 1).

**Tech Stack:** Python 3.12 (uv-script + pakke), `google-genai` SDK, `idb`/`idb-companion`, `xcrun simctl`, pytest. Nøkkel: `gemini-api-key-paid` fra macOS Keychain.

## Global Constraints

- **Modell:** `gemini-3.5-flash` med tool `{"type":"computer_use","environment":"mobile","enable_prompt_injection_detection":true}` — verdier verifiseres i Task 1.
- **Koordinater:** computer_use returnerer normalisert **0–1000**; må mappes til device-points.
- **Nøkkel:** hentes via `security find-generic-password -a $USER -s gemini-api-key-paid -w`; fjern arvet `GOOGLE_API_KEY`/`GEMINI_API_KEY` fra env før klient-init.
- **Bounds:** koordinat utenfor app-safe-area → **reject** (aldri clamp), matet tilbake som `rejected`.
- **Tastatur (idb):** `idb ui text` går til mål-UDID direkte (ingen OS-fokus-fare — den guarden gjelder kun macOS/cliclick, ikke fase 1).
- **Maks-steg:** default 25, konfigurerbar. Per-steg-budsjett = Gemini-kall + handling + settling (~300 ms), samlet bounded.
- **Action-result-protokoll:** hvert `function_call` besvares med `function_result` (`success`/`rejected`/`unsupported`/`timeout`) + ferskt skjermbilde.
- **Per-steg-journal:** `planned→validated→executed→result_sent`; re-eksekver aldri et `executed`-steg. Tapt interaction-kjede = terminal-stopp med delvis rapport.
- **Kontekst-renhet:** skill-wrapper returnerer tekst-only oppsummering + filstier til Claude, aldri inline-bilder.
- **Tester kjøres:** `python3 -m pytest tests/unit/computer_use/ -v` fra repo-rot.

---

## File Structure

- `scripts/computer_use/__init__.py` — pakke-markør
- `scripts/computer_use/coords.py` — koordinat-mapping + safe-area-validering (ren)
- `scripts/computer_use/actions.py` — action-adapter: computer_use → executor-primitiv (ren)
- `scripts/computer_use/dedup.py` — perceptuell-hash + dedup/retensjon-regler (ren)
- `scripts/computer_use/report.py` — rapport-bygger til Markdown (ren)
- `scripts/computer_use/executor_idb.py` — idb-executor (screenshot/tap/swipe/type)
- `scripts/computer_use/preflight.py` — pre-flight + launch-state + foreground-oracle
- `scripts/computer_use/loop.py` — loop-motor + per-steg-journal
- `scripts/computer_use/critic.py` — visuell kritiker-pass
- `scripts/computer_use/gemini.py` — computer_use-klient-wrapper (interactions)
- `scripts/computer_use/cli.py` — CLI-entry
- `scripts/ios-visual-explore` — kjørbart uv-shim som kaller `cli.py`
- `skills/ios-visual-explore/SKILL.md` — skill-wrapper
- `tests/unit/computer_use/test_*.py` — pytest
- `docs/superpowers/specs/SPIKE-FINDINGS.md` — output fra Task 1

---

## Task 1: Spike — verifiser computer_use API + idb + touch-egnethet (GATE)

Dette er en utforskende gate (R1/R4/R7 i spec). Ingen TDD — målet er å bekrefte eller justere antagelsene resten av planen bygger på, og skrive funnene ned. **Senere tasks som rører Gemini-API-formen (Task 9, 10) er betinget av disse funnene.**

**Files:**
- Create: `docs/superpowers/specs/SPIKE-FINDINGS.md`

- [ ] **Step 1: Verifiser idb installert + companion tilkoblet**

Run:
```bash
which idb || echo "MANGLER: brew install facebook/fb/idb-companion && pip install fb-idb"
xcrun simctl list devices booted | grep -i booted || echo "boot en iPhone-sim først"
```
Boot en iPhone-sim og noter UDID. Verifiser `idb ui describe-all --udid <UDID>` svarer.

- [ ] **Step 2: Verifiser idb tap/koordinatkonvensjon**

Ta et skjermbilde, tapp et kjent element, bekreft treff:
```bash
xcrun simctl io <UDID> screenshot /tmp/sim.png
# noter device logical size (points) og bilde-pixelstørrelse
idb ui tap <x_points> <y_points> --udid <UDID>
```
**Noter i SPIKE-FINDINGS.md:** tar `idb ui tap` points eller pixels? Hva er device-backing-scale for denne device-typen (utled = pixel_w / point_w)?

- [ ] **Step 3: Verifiser computer_use API-form mot faktisk SDK**

Skriv en minimal spike i `/tmp/cu_spike.py` (uv-script, dep `google-genai`), hent nøkkel fra Keychain, og prøv ett computer_use-kall med et sim-skjermbilde. Bekreft:
- Er det `client.interactions.create()` eller `client.models.generate_content()`?
- Eksakt felt for tool-deklarasjon + `environment`-verdi (`"mobile"`?)
- Strukturen på returnert handling (`steps`/`function_call`, felt `name`/`x`/`y`/`intent`)
- Hvordan sendes `function_result` tilbake (felt, `previous_interaction_id`/`call_id`)
- Er koordinatene 0–1000 normalisert?

**Noter alle svar i SPIKE-FINDINGS.md.**

- [ ] **Step 4: Verifiser touch-egnethet (R4)**

Gi modellen et reelt oppdrag («tap fortsett-knappen», «scroll ned») mot en enkel app, og se om de returnerte handlingene + idb-utførelsen faktisk driver appen riktig. **Noter:** klarer modellen tap/scroll/tekst via idb? Hvilke handlinger den emitterer (er `scroll` vanlig?).

- [ ] **Step 5: Verifiser foreground-oracle (R7)**

Bekreft en pålitelig måte å lese om mål-appen er i forgrunnen. Prøv en XCTest-probe på `XCUIApplication(bundleIdentifier:).state == .runningForeground`, eventuelt `idb`-prosess-state. **Noter hvilken mekanisme som faktisk virker** — dette er en fase-1-blokker.

- [ ] **Step 6: Skriv SPIKE-FINDINGS.md og commit**

Dokumenter alle funn + eventuelle nødvendige justeringer av planen (API-form, koordinatkonvensjon, oracle-mekanisme).
```bash
git add docs/superpowers/specs/SPIKE-FINDINGS.md
git commit -m "spike(computer-use): verify API form, idb coords, touch-fit, foreground oracle"
```
Expected: SPIKE-FINDINGS.md inneholder konkrete svar på Step 2–5. **Hvis API-formen avviker vesentlig fra spec §5, oppdater Task 9/10-signaturene før de bygges.**

---

## Task 2: Pakkeoppsett + pytest-infrastruktur

**Files:**
- Create: `scripts/computer_use/__init__.py`
- Create: `tests/unit/computer_use/__init__.py`
- Create: `tests/unit/computer_use/test_smoke.py`

**Interfaces:**
- Produces: importerbar pakke `computer_use` for tester via `importlib`/sys.path.

- [ ] **Step 1: Opprett pakke-markører**

Opprett `scripts/computer_use/__init__.py` med innhold:
```python
"""computer_use — agentisk visuell utforsking av SwiftUI-apper (fase 1: iOS-sim)."""
```
Opprett tom `tests/unit/computer_use/__init__.py`.

- [ ] **Step 2: Skriv smoke-test som importerer pakken**

`tests/unit/computer_use/test_smoke.py`:
```python
import importlib.util
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PKG = REPO_ROOT / "scripts" / "computer_use"


def load(mod_name):
    path = PKG / f"{mod_name}.py"
    spec = importlib.util.spec_from_file_location(f"computer_use_{mod_name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_package_dir_exists():
    assert PKG.is_dir()
```

- [ ] **Step 3: Kjør testen**

Run: `python3 -m pytest tests/unit/computer_use/test_smoke.py -v`
Expected: PASS (1 test).

- [ ] **Step 4: Commit**

```bash
git add scripts/computer_use/__init__.py tests/unit/computer_use/
git commit -m "chore(computer-use): package + pytest scaffold"
```

---

## Task 3: Koordinat-mapper (ren funksjon, TDD)

**Files:**
- Create: `scripts/computer_use/coords.py`
- Test: `tests/unit/computer_use/test_coords.py`

> **SPIKE-justert (Task 1):** `idb ui tap` tar **device-points**, og computer_use-koordinater er
> 0–1000 normalisert mot **punkt-rommet** (`describe-all` Application-frame, f.eks. 402×874 for
> iPhone 17 Pro). Denormaliser derfor direkte mot punkt-dimensjoner — **ingen piksler, ingen
> backing-scale, ingen Pillow**. Verifisert: `(450,365)` → `(181,319)` pt traff "Generelt"-raden.

**Interfaces:**
- Produces:
  - `Point` (namedtuple `x: float`, `y: float`) — device-points
  - `SafeArea` (dataclass `left: float`, `top: float`, `right: float`, `bottom: float`) — points
  - `denormalize(x: int, y: int, point_w: float, point_h: float) -> Point` — 0–1000 → device-points (mot punkt-rommet)
  - `in_safe_area(p: Point, safe: SafeArea) -> bool`

- [ ] **Step 1: Write the failing test**

`tests/unit/computer_use/test_coords.py`:
```python
from test_smoke import load
coords = load("coords")


def test_denormalize_against_points():
    # SPIKE-verifisert: (450,365) normalisert mot 402x874 pt (iPhone 17 Pro) → "Generelt"-raden
    p = coords.denormalize(450, 365, 402, 874)
    assert round(p.x, 1) == round(450 / 1000 * 402, 1)  # 180.9
    assert round(p.y, 1) == round(365 / 1000 * 874, 1)  # 319.0


def test_denormalize_center():
    p = coords.denormalize(500, 500, 402, 874)
    assert round(p.x, 1) == 201.0
    assert round(p.y, 1) == 437.0


def test_in_safe_area_rejects_status_bar():
    safe = coords.SafeArea(left=0, top=60, right=390, bottom=800)
    assert coords.in_safe_area(coords.Point(200, 400), safe) is True
    assert coords.in_safe_area(coords.Point(200, 30), safe) is False   # i status-bar
    assert coords.in_safe_area(coords.Point(200, 810), safe) is False  # under home-indicator
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_coords.py -v`
Expected: FAIL ("No module named coords" / attribuutt mangler).

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/coords.py`:
```python
from collections import namedtuple
from dataclasses import dataclass

Point = namedtuple("Point", ["x", "y"])


@dataclass
class SafeArea:
    left: float
    top: float
    right: float
    bottom: float


def denormalize(x: int, y: int, point_w: float, point_h: float) -> Point:
    """0–1000 normalisert → device-points, mot punkt-rommet (describe-all Application-frame).
    Ingen piksel/scale-konvertering: idb ui tap tar punkter (SPIKE-FINDINGS, Task 1)."""
    return Point(x / 1000.0 * point_w, y / 1000.0 * point_h)


def in_safe_area(p: Point, safe: SafeArea) -> bool:
    return safe.left <= p.x <= safe.right and safe.top <= p.y <= safe.bottom
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_coords.py -v`
Expected: PASS (3 tester).

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/coords.py tests/unit/computer_use/test_coords.py
git commit -m "feat(computer-use): coordinate mapper + safe-area validation"
```

---

## Task 4: Action-adapter (ren funksjon, TDD)

**Files:**
- Create: `scripts/computer_use/actions.py`
- Test: `tests/unit/computer_use/test_actions.py`

> **SPIKE-justert (Task 1 + runde 2):** computer_use-handlinger er **nestet** —
> `{"name": ..., "arguments": {...}, "id": ..., "signature": ...}` — koordinatene ligger i
> `arguments`, ikke flatt. Scroll emitteres som **`drag_and_drop`** med to punkter
> (`start_x/start_y` → `end_x/end_y`, 0–1000 normalisert), bekreftet i ekte kjøring. Adapteren
> normaliserer derfor alle dra/scroll-handlinger til **én `swipe`-primitiv med to punkter**
> (normalisert), slik at executoren (Task 7) bare trenger `swipe(start, end)`. `scroll` (hvis det
> dukker opp) utledes til start/end fra retning med en fast, klampet delta.

**Interfaces:**
- Consumes: ingen.
- Produces:
  - `ExecutorAction` (dataclass `kind: str`, `params: dict`) — `kind` ∈ {`tap`,`swipe`,`type`,`wait`,`unsupported`}
  - `adapt(step: dict) -> ExecutorAction` — mapper et computer_use-steg (nestet) → executor-primitiv.
    `swipe`-params er normaliserte `{start_x,start_y,end_x,end_y}` (0–1000); `tap`-params er `{x,y}` (0–1000).
    Loop (Task 9) denormaliserer mot punkter.

- [ ] **Step 1: Write the failing test**

`tests/unit/computer_use/test_actions.py`:
```python
from test_smoke import load
actions = load("actions")


def test_click_maps_to_tap():
    # SPIKE-verifisert nested form
    a = actions.adapt({"name": "click",
                       "arguments": {"x": 450, "y": 365, "intent": "tap row"}})
    assert a.kind == "tap"
    assert a.params["x"] == 450 and a.params["y"] == 365


def test_drag_and_drop_maps_to_swipe_two_points():
    # SPIKE runde-2: scroll kommer som drag_and_drop med start/end
    a = actions.adapt({"name": "drag_and_drop",
                       "arguments": {"start_x": 500, "start_y": 800,
                                     "end_x": 500, "end_y": 200}})
    assert a.kind == "swipe"
    assert a.params["start_x"] == 500 and a.params["start_y"] == 800
    assert a.params["end_x"] == 500 and a.params["end_y"] == 200


def test_scroll_derives_swipe_endpoints():
    # 'scroll down' => innhold nedover => finger opp => end_y < start_y
    a = actions.adapt({"name": "scroll",
                       "arguments": {"x": 500, "y": 500, "direction": "down"}})
    assert a.kind == "swipe"
    assert a.params["end_y"] < a.params["start_y"]
    # klampet til [0,1000]
    assert 0 <= a.params["end_y"] <= 1000 and 0 <= a.params["start_y"] <= 1000


def test_type_passthrough():
    a = actions.adapt({"name": "type", "arguments": {"text": "hei"}})
    assert a.kind == "type" and a.params["text"] == "hei"


def test_wait_is_noop():
    a = actions.adapt({"name": "wait", "arguments": {}})
    assert a.kind == "wait"


def test_unknown_is_unsupported():
    a = actions.adapt({"name": "teleport", "arguments": {}})
    assert a.kind == "unsupported"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_actions.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/actions.py`:
```python
from dataclasses import dataclass

SCROLL_DELTA = 250  # normalisert 0–1000 dra-lengde når scroll utledes fra retning


@dataclass
class ExecutorAction:
    kind: str
    params: dict


def _clamp(v: float) -> float:
    return max(0, min(1000, v))


def adapt(step: dict) -> ExecutorAction:
    name = step.get("name", "")
    args = step.get("arguments", {}) or {}
    if name in ("click", "tap"):
        return ExecutorAction("tap", {"x": args.get("x"), "y": args.get("y")})
    if name == "drag_and_drop":
        return ExecutorAction("swipe", {
            "start_x": args.get("start_x"), "start_y": args.get("start_y"),
            "end_x": args.get("end_x"), "end_y": args.get("end_y"),
        })
    if name == "scroll":
        # 'scroll down' = se nedover = finger swiper opp = end_y < start_y
        x = args.get("x", 500); y = args.get("y", 500)
        d = args.get("direction", "down")
        dy = {"down": -SCROLL_DELTA, "up": SCROLL_DELTA}.get(d, 0)
        dx = {"left": SCROLL_DELTA, "right": -SCROLL_DELTA}.get(d, 0)
        return ExecutorAction("swipe", {
            "start_x": _clamp(x), "start_y": _clamp(y),
            "end_x": _clamp(x + dx), "end_y": _clamp(y + dy),
        })
    if name in ("type", "press_key"):
        return ExecutorAction("type", {"text": args.get("text", "")})
    if name == "wait":
        return ExecutorAction("wait", {})
    return ExecutorAction("unsupported", {"original": name})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_actions.py -v`
Expected: PASS (6 tester).

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/actions.py tests/unit/computer_use/test_actions.py
git commit -m "feat(computer-use): action adapter (scroll→swipe, etc.)"
```

---

## Task 5: Dedup + evidens-retensjon (ren funksjon, TDD)

**Files:**
- Create: `scripts/computer_use/dedup.py`
- Test: `tests/unit/computer_use/test_dedup.py`

**Interfaces:**
- Produces:
  - `ahash(gray_pixels: list[int], side: int = 8) -> int` — gjennomsnitts-hash (perceptuell)
  - `hamming(a: int, b: int) -> int`
  - `should_retain(status: str, is_first: bool, is_last: bool) -> bool` — evidens-regel
  - `is_critic_dup(new_hash: int, prev_hash: int | None, threshold: int = 5) -> bool` — kritiker-input-dedup

- [ ] **Step 1: Write the failing test**

`tests/unit/computer_use/test_dedup.py`:
```python
from test_smoke import load
dedup = load("dedup")


def test_hamming():
    assert dedup.hamming(0b1010, 0b1000) == 1


def test_retain_keeps_rejected_and_endpoints():
    assert dedup.should_retain("rejected", False, False) is True
    assert dedup.should_retain("app_left_foreground", False, False) is True
    assert dedup.should_retain("success", True, False) is True   # første
    assert dedup.should_retain("success", False, True) is True   # siste
    assert dedup.should_retain("success", False, False) is False # vanlig → dedup-kandidat


def test_critic_dup_threshold():
    assert dedup.is_critic_dup(0b1111, 0b1111, threshold=2) is True
    assert dedup.is_critic_dup(0b1111, 0b0000, threshold=2) is False
    assert dedup.is_critic_dup(0b1111, None) is False  # ingen forrige
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_dedup.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/dedup.py`:
```python
RETAIN_STATUSES = {"rejected", "failed", "unsupported", "timeout", "app_left_foreground"}


def ahash(gray_pixels, side: int = 8) -> int:
    """Gjennomsnitts-hash over en side*side nedskalert gråtoneliste."""
    avg = sum(gray_pixels) / len(gray_pixels)
    bits = 0
    for i, p in enumerate(gray_pixels):
        if p >= avg:
            bits |= (1 << i)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def should_retain(status: str, is_first: bool, is_last: bool) -> bool:
    return status in RETAIN_STATUSES or is_first or is_last


def is_critic_dup(new_hash: int, prev_hash, threshold: int = 5) -> bool:
    if prev_hash is None:
        return False
    return hamming(new_hash, prev_hash) <= threshold
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_dedup.py -v`
Expected: PASS (3 tester).

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/dedup.py tests/unit/computer_use/test_dedup.py
git commit -m "feat(computer-use): perceptual dedup + evidence retention rules"
```

---

## Task 6: Rapport-bygger (ren funksjon, TDD)

**Files:**
- Create: `scripts/computer_use/report.py`
- Test: `tests/unit/computer_use/test_report.py`

**Interfaces:**
- Consumes: ingen (tar plain dicts/lister).
- Produces:
  - `build_markdown(mission: str, env: dict, action_log: list[dict], findings: list[dict], status: str) -> str`
  - `text_summary(findings: list[dict], report_path: str, screenshot_dir: str) -> str` — tekst-only for skill-wrapper (ingen inline-bilder)

- [ ] **Step 1: Write the failing test**

`tests/unit/computer_use/test_report.py`:
```python
from test_smoke import load
report = load("report")

ENV = {"platform": "ios", "udid": "ABC-123", "bundle_id": "com.x.app"}
LOG = [{"step": 1, "action": "tap", "intent": "tap continue", "coord": "(195,400)", "result": "success",
        "produced_by_steps": [1]}]
FINDINGS = [{"severity": "P2", "text": "knapp avkuttet", "screenshot": "shot_001.png"}]


def test_markdown_contains_sections():
    md = report.build_markdown("utforsk onboarding", ENV, LOG, FINDINGS, "fullført")
    assert "utforsk onboarding" in md
    assert "ABC-123" in md
    assert "knapp avkuttet" in md
    assert "shot_001.png" in md
    assert "fullført" in md


def test_text_summary_has_no_inline_images():
    s = report.text_summary(FINDINGS, "/p/report.md", "/p/shots")
    assert "![" not in s              # ingen inline-bilde-markdown
    assert "/p/report.md" in s        # filsti ja
    assert "knapp avkuttet" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_report.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/report.py`:
```python
def build_markdown(mission, env, action_log, findings, status) -> str:
    lines = [f"# Visuell utforsking — rapport", "",
             f"**Oppdrag:** {mission}", "",
             f"**Miljø:** {env.get('platform')} / UDID {env.get('udid')} / {env.get('bundle_id')}",
             f"**Sluttstatus:** {status}", "", "## Handlingslogg", ""]
    for a in action_log:
        lines.append(f"- Steg {a['step']}: `{a['action']}` — {a['intent']} "
                     f"@ {a.get('coord','-')} → {a['result']} (skjerm fra steg {a.get('produced_by_steps')})")
    lines += ["", "## Funn", ""]
    for f in findings:
        lines.append(f"- **{f['severity']}** {f['text']} — `{f['screenshot']}`")
    return "\n".join(lines) + "\n"


def text_summary(findings, report_path, screenshot_dir) -> str:
    head = [f"Visuell utforsking ferdig. Full rapport: {report_path}",
            f"Skjermbilder: {screenshot_dir}", f"{len(findings)} funn:"]
    body = [f"- {f['severity']} {f['text']} ({f['screenshot']})" for f in findings]
    return "\n".join(head + body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_report.py -v`
Expected: PASS (2 tester).

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/report.py tests/unit/computer_use/test_report.py
git commit -m "feat(computer-use): markdown report builder + text-only summary"
```

---

## Task 7: idb-executor

**Files:**
- Create: `scripts/computer_use/executor_idb.py`
- Test: `tests/unit/computer_use/test_executor_idb.py`

> **SPIKE-justert (Task 1 + runde 2):** `idb ui tap`/`idb ui swipe` tar **device-points** (ingen
> piksler/scale). Swipe er **to punkter** (`drag_and_drop` gir start+end), så signaturen er
> `swipe(start, end)` → `idb ui swipe x1 y1 x2 y2`. `coordinate_space()` returnerer **punkt-
> dimensjonene** lest fra `idb ui describe-all` Application-frame — **ingen Pillow, ingen
> backing-scale, ingen piksel-parse**.

**Interfaces:**
- Consumes: `coords.Point`.
- Produces:
  - `IdbExecutor(udid: str)` med metoder:
    - `screenshot() -> bytes` (PNG)
    - `tap(p: Point) -> None` — `idb ui tap` (punkter)
    - `swipe(start: Point, end: Point) -> None` — `idb ui swipe x1 y1 x2 y2` (punkter)
    - `type_text(text: str) -> None` — `idb ui text`
    - `coordinate_space() -> tuple[float, float]` — `(point_w, point_h)` fra describe-all Application-frame
  - Bruker subprocess til `xcrun simctl` + `idb`.

- [ ] **Step 1: Write the failing test (kommando-bygging, mocket subprocess)**

`tests/unit/computer_use/test_executor_idb.py`:
```python
import json
from test_smoke import load
ex = load("executor_idb")


def ex_point(x, y):
    coords = load("coords")
    return coords.Point(x, y)


def test_tap_builds_idb_command(monkeypatch):
    calls = []
    monkeypatch.setattr(ex, "_run", lambda self, args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1")
    e.tap(ex_point(195.0, 400.0))
    assert calls and "tap" in calls[-1]
    assert "195" in calls[-1] and "400" in calls[-1]
    assert "UDID-1" in calls[-1]


def test_swipe_builds_two_point_command(monkeypatch):
    calls = []
    monkeypatch.setattr(ex, "_run", lambda self, args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1")
    e.swipe(ex_point(200.0, 700.0), ex_point(200.0, 300.0))
    args = calls[-1]
    assert "swipe" in args
    # begge endepunktene i kommandoen
    assert "200" in args and "700" in args and "300" in args


def test_coordinate_space_reads_point_frame(monkeypatch):
    app = [{"type": "Application", "frame": {"x": 0, "y": 0, "width": 402, "height": 874}}]
    monkeypatch.setattr(ex, "_run",
                        lambda self, a: json.dumps(app).encode() if "describe-all" in a else b"")
    e = ex.IdbExecutor("UDID-1")
    pw, ph = e.coordinate_space()
    assert pw == 402.0 and ph == 874.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_executor_idb.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/executor_idb.py`:
```python
import json
import subprocess


class IdbExecutor:
    def __init__(self, udid: str):
        self.udid = udid

    def _run(self, args: list[str]) -> bytes:
        return subprocess.run(args, capture_output=True, check=True).stdout

    def screenshot(self) -> bytes:
        # simctl skriver til fil; les bytes
        import tempfile, os
        path = tempfile.mktemp(suffix=".png")
        self._run(["xcrun", "simctl", "io", self.udid, "screenshot", path])
        data = open(path, "rb").read()
        os.unlink(path)
        return data

    def tap(self, p) -> None:
        self._run(["idb", "ui", "tap", str(round(p.x)), str(round(p.y)), "--udid", self.udid])

    def swipe(self, start, end) -> None:
        # idb ui swipe tar to punkter (start -> end); drag_and_drop/scroll gir begge (SPIKE).
        self._run(["idb", "ui", "swipe",
                   str(round(start.x)), str(round(start.y)),
                   str(round(end.x)), str(round(end.y)), "--udid", self.udid])

    def type_text(self, text: str) -> None:
        self._run(["idb", "ui", "text", text, "--udid", self.udid])

    def coordinate_space(self) -> tuple[float, float]:
        """(point_w, point_h) fra describe-all Application-frame. idb tar punkter, så ingen
        piksel/scale-konvertering (SPIKE-FINDINGS, Task 1)."""
        out = self._run(["idb", "ui", "describe-all", "--udid", self.udid])
        elems = json.loads(out)
        app = next(e for e in elems if e.get("type") == "Application")
        f = app["frame"]
        return (float(f["width"]), float(f["height"]))
```

> Merk: ingen tredjeparts-avhengighet — `coordinate_space` leser punkt-dimensjonene fra describe-all
> (Application-frame), så `ios-visual-explore`-shimmen (Task 11) trenger bare `google-genai`.
> `_run` er en instansmetode (tar `self`) slik at testene kan monkeypatche den per instans.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_executor_idb.py -v`
Expected: PASS.

- [ ] **Step 5: Smoke mot booted sim (manuell verifisering)**

Run (med booted sim + app åpen):
```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); from computer_use.executor_idb import IdbExecutor; \
e=IdbExecutor('<UDID>'); open('/tmp/s.png','wb').write(e.screenshot()); print('ok')"
```
Expected: `/tmp/s.png` er et gyldig skjermbilde.

- [ ] **Step 6: Commit**

```bash
git add scripts/computer_use/executor_idb.py tests/unit/computer_use/test_executor_idb.py
git commit -m "feat(computer-use): idb executor (screenshot/tap/swipe/type)"
```

---

## Task 8: Pre-flight + foreground-oracle

**Files:**
- Create: `scripts/computer_use/preflight.py`
- Test: `tests/unit/computer_use/test_preflight.py`

**Interfaces:**
- Produces:
  - `resolve_tool(name: str) -> str` — `command -v`-resolve, kaster `PreflightError` med install-hint hvis mangler
  - `PreflightError(Exception)`
  - `is_app_foreground(udid: str, bundle_id: str) -> bool` — **oracle per SPIKE-FINDINGS (Task 1, R7)**
  - `preflight(udid: str, bundle_id: str) -> dict` — kjører alle sjekker + relaunch + loggfører state

> **SPIKE-justert (Task 1, R7):** foreground-oracle = **prosess lever** (`launchctl list` inneholder
> `UIKitApplication:<bundle>`) **OG ikke på hjemskjerm**. Hjemskjerm-markør = describe-all-element
> med `AXUniqueId == "spotlight-pill"` — en **stabil, lokaliserings-uavhengig** identifikator
> (i motsetning til lokaliserte labels som "Appbibliotek"/"App Library"). XCTest `.runningForeground`
> er kanonisk men krever bygd test-bundle → utsatt forbi fase 1.

- [ ] **Step 1: Write the failing test**

`tests/unit/computer_use/test_preflight.py`:
```python
import json
import pytest
from test_smoke import load
pf = load("preflight")


def test_resolve_missing_tool_raises(monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda n: None)
    with pytest.raises(pf.PreflightError) as e:
        pf.resolve_tool("idb")
    assert "idb" in str(e.value)


def test_resolve_present_tool_returns_path(monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda n: "/opt/homebrew/bin/idb")
    assert pf.resolve_tool("idb") == "/opt/homebrew/bin/idb"


def _fake_run(launchctl_out, describe_out):
    class R:
        pass

    def run(args, **kw):
        r = R()
        r.stdout = launchctl_out if "launchctl" in args else describe_out
        r.returncode = 0
        return r
    return run


def test_foreground_true_when_running_and_not_home(monkeypatch):
    monkeypatch.setattr(pf.subprocess, "run", _fake_run(
        "501 0 UIKitApplication:com.x.app[abcd]\n",
        json.dumps([{"type": "Application", "AXUniqueId": None}])))
    assert pf.is_app_foreground("U", "com.x.app") is True


def test_foreground_false_when_on_home(monkeypatch):
    monkeypatch.setattr(pf.subprocess, "run", _fake_run(
        "501 0 UIKitApplication:com.x.app[abcd]\n",
        json.dumps([{"AXUniqueId": "spotlight-pill"}])))
    assert pf.is_app_foreground("U", "com.x.app") is False


def test_foreground_false_when_process_dead(monkeypatch):
    monkeypatch.setattr(pf.subprocess, "run", _fake_run(
        "", json.dumps([{"type": "Application"}])))
    assert pf.is_app_foreground("U", "com.x.app") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_preflight.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/preflight.py`:
```python
import json
import shutil
import subprocess

INSTALL_HINTS = {
    "idb": "brew install facebook/fb/idb-companion && pip install fb-idb",
    "cliclick": "brew install cliclick",
}


class PreflightError(Exception):
    pass


def resolve_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        hint = INSTALL_HINTS.get(name, "")
        raise PreflightError(f"Mangler '{name}'. Installer: {hint}")
    return path


def _process_running(udid: str, bundle_id: str) -> bool:
    out = subprocess.run(["xcrun", "simctl", "spawn", udid, "launchctl", "list"],
                         capture_output=True, text=True).stdout
    return f"UIKitApplication:{bundle_id}" in out


def _on_home_screen(udid: str) -> bool:
    out = subprocess.run(["idb", "ui", "describe-all", "--udid", udid],
                         capture_output=True, text=True).stdout
    try:
        elems = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return False
    # 'spotlight-pill' er en stabil, lokaliserings-uavhengig hjemskjerm-markør (SPIKE-FINDINGS R7)
    return any(e.get("AXUniqueId") == "spotlight-pill" for e in elems)


def is_app_foreground(udid: str, bundle_id: str) -> bool:
    """R7-oracle: app fremme = prosess lever OG ikke på hjemskjerm (SPIKE-FINDINGS, Task 1)."""
    if not _process_running(udid, bundle_id):
        return False
    return not _on_home_screen(udid)


def preflight(udid: str, bundle_id: str) -> dict:
    resolve_tool("idb")
    subprocess.run(["xcrun", "simctl", "launch", udid, bundle_id], check=True)
    return {"udid": udid, "bundle_id": bundle_id, "platform": "ios"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_preflight.py -v`
Expected: PASS (5 tester).

- [ ] **Step 5: Manuell live-verifisering av oracle (controller, booted sim)**

Med booted sim: bekreft `is_app_foreground(udid, bundle)` returnerer `True` når mål-appen er fremme
og `False` etter at appen termineres / hjemskjerm vises. (Logikken er enhetstestet i Step 1; dette
verifiserer de reelle `launchctl`/`describe-all`-kommandoene mot faktisk sim.)

- [ ] **Step 6: Commit**

```bash
git add scripts/computer_use/preflight.py tests/unit/computer_use/test_preflight.py
git commit -m "feat(computer-use): preflight + foreground oracle"
```

---

## Task 9: Loop-motor + per-steg-journal (API-avhengig — se SPIKE-FINDINGS)

**Files:**
- Create: `scripts/computer_use/gemini.py`
- Create: `scripts/computer_use/loop.py`
- Test: `tests/unit/computer_use/test_loop.py`

> **SPIKE-justert (Task 1 + runde 2):** (1) handlinger denormaliseres fra **`ea.params`** (adapteren
> har allerede pakket ut nested `arguments`), ikke fra rå `turn.action`. (2) `coordinate_space()`
> returnerer **`(point_w, point_h)`** (2-tuple, ingen scale). (3) `swipe` tar **to punkter** (begge
> safe-area-sjekkes). (4) terminal-signal kommer fra **`interaction.status`** — klienten setter
> `Turn.done = (status != "requires_action")`. (5) result-kjeding bruker `previous_interaction_id` +
> `call_id = step["id"]`, innkapslet i `ComputerUseClient`.

**Interfaces:**
- Consumes: `actions.adapt`, `coords.denormalize`/`in_safe_area`, `IdbExecutor`, `dedup`, `report`.
- Produces:
  - `gemini.ComputerUseClient` med `start(mission, screenshot_png) -> Turn` og `respond(result_kind, screenshot_png, reason) -> Turn`. Internt: lagrer `previous_interaction_id` + siste `call_id`; avleder `done` fra `interaction.status`.
  - `Turn` (dataclass: `action: dict | None`, `done: bool`)
  - `loop.run(mission, executor, client, *, max_steps=25, safe_area, settle=0.3) -> dict` (journal + status). **Ingen `scale`-param** — leses som punkt-dims fra `coordinate_space()`.

- [ ] **Step 1: Write the failing test (mocket klient + executor, verifiserer journal + result-protokoll)**

`tests/unit/computer_use/test_loop.py`:
```python
from test_smoke import load
loop = load("loop")


def _turn(action, done):
    return load("loop").Turn(action=action, done=done)


def _safe():
    return load("coords").SafeArea(0, 0, 402, 874)


class FakeExec:
    def __init__(self):
        self.taps = []
        self.swipes = []
    def screenshot(self): return b"PNG"
    def coordinate_space(self): return (402.0, 874.0)   # punkt-dims, ingen scale
    def tap(self, p): self.taps.append(p)
    def swipe(self, start, end): self.swipes.append((start, end))
    def type_text(self, t): pass


class TapThenDone:
    def __init__(self): self.results = []
    def start(self, mission, shot):
        return _turn({"name": "click", "arguments": {"x": 500, "y": 500}}, False)
    def respond(self, kind, shot, reason):
        self.results.append(kind)
        return _turn(None, True)


def test_loop_executes_tap_then_sends_result_and_journals():
    ex, cl = FakeExec(), TapThenDone()
    out = loop.run("utforsk", ex, cl, max_steps=5, safe_area=_safe())
    assert ex.taps, "tap skulle blitt utført"
    assert cl.results == ["success"], "function_result måtte sendes etter handling"
    assert out["journal"][0]["state"] == "result_sent"
    assert out["status"] == "fullført"


class DragThenDone:
    def __init__(self): self.results = []
    def start(self, mission, shot):
        return _turn({"name": "drag_and_drop",
                      "arguments": {"start_x": 500, "start_y": 800,
                                    "end_x": 500, "end_y": 200}}, False)
    def respond(self, kind, shot, reason):
        self.results.append(kind); return _turn(None, True)


def test_drag_and_drop_swipes_two_points():
    ex, cl = FakeExec(), DragThenDone()
    loop.run("scroll", ex, cl, max_steps=5, safe_area=_safe())
    assert ex.swipes, "swipe skulle blitt utført med to punkter"
    start, end = ex.swipes[0]
    assert end.y < start.y   # 'scroll ned' => end_y < start_y


class TapOutOfBounds:
    def __init__(self): self.results = []
    def start(self, mission, shot):
        return _turn({"name": "click", "arguments": {"x": 500, "y": 5}}, False)
    def respond(self, kind, shot, reason):
        self.results.append(kind); return _turn(None, True)


def test_out_of_safe_area_is_rejected_not_executed():
    safe = load("coords").SafeArea(0, 60, 402, 800)  # y=5 -> 4.4pt, over top=60
    ex, cl = FakeExec(), TapOutOfBounds()
    loop.run("x", ex, cl, max_steps=5, safe_area=safe)
    assert not ex.taps, "utenfor safe-area skulle IKKE tappes"
    assert cl.results == ["rejected"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_loop.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/loop.py`:
```python
import time
from dataclasses import dataclass


@dataclass
class Turn:
    action: dict | None   # computer_use-steg (nestet) eller None når ferdig
    done: bool            # avledet av interaction.status av klienten


def run(mission, executor, client, *, max_steps=25, safe_area, settle=0.3):
    import importlib.util, pathlib
    pkg = pathlib.Path(__file__).resolve().parent
    def _load(n):
        s = importlib.util.spec_from_file_location(n, pkg / f"{n}.py")
        m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
    actions, coords = _load("actions"), _load("coords")

    journal = []
    shot = executor.screenshot()
    turn = client.start(mission, shot)
    step = 0
    while turn.action and not turn.done and step < max_steps:
        step += 1
        entry = {"step": step, "state": "planned", "raw": turn.action}
        journal.append(entry)
        ea = actions.adapt(turn.action)
        point_w, point_h = executor.coordinate_space()
        kind, reason = "success", None
        if ea.kind == "tap":
            p = coords.denormalize(ea.params["x"], ea.params["y"], point_w, point_h)
            if not coords.in_safe_area(p, safe_area):
                kind, reason = "rejected", "outside safe area"
            else:
                entry["state"] = "validated"
                executor.tap(p); entry["state"] = "executed"
        elif ea.kind == "swipe":
            start = coords.denormalize(ea.params["start_x"], ea.params["start_y"], point_w, point_h)
            end = coords.denormalize(ea.params["end_x"], ea.params["end_y"], point_w, point_h)
            if not (coords.in_safe_area(start, safe_area) and coords.in_safe_area(end, safe_area)):
                kind, reason = "rejected", "outside safe area"
            else:
                entry["state"] = "validated"
                executor.swipe(start, end); entry["state"] = "executed"
        elif ea.kind == "type":
            executor.type_text(ea.params["text"]); entry["state"] = "executed"
        elif ea.kind == "wait":
            time.sleep(settle); entry["state"] = "executed"
        else:
            kind, reason = "unsupported", ea.params.get("original")
        time.sleep(settle)
        shot = executor.screenshot()
        turn = client.respond(kind, shot, reason)
        entry["state"] = "result_sent"; entry["result"] = kind
    status = "fullført" if (turn and turn.done) else "maks-steg-nådd"
    return {"journal": journal, "status": status}
```

`scripts/computer_use/gemini.py` — spike-forankret computer_use-klient (IKKE enhetstestet; loop-testene
bruker fakes; ekte form verifisert i Task 1 og kjøres live i Task 11):
```python
import base64
import importlib.util
import json
import os
import pathlib
import subprocess


def _load(n):
    s = importlib.util.spec_from_file_location(n, pathlib.Path(__file__).resolve().parent / f"{n}.py")
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


# Turn lastes via samme importlib-mønster som loop bruker for sine sibling-moduler —
# robust både under pakke-import (shim) og test-harness; loop.run leser .action/.done duck-typet.
Turn = _load("loop").Turn

TOOL = [{"type": "computer_use", "environment": "mobile",
         "enable_prompt_injection_detection": True}]


def _api_key() -> str:
    # SPIKE-FINDINGS: SDK plukker arvet GOOGLE_API_KEY/GEMINI_API_KEY — pop begge først.
    for k in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(k, None)
    return subprocess.run(
        ["security", "find-generic-password", "-a", os.environ["USER"],
         "-s", "gemini-api-key-paid", "-w"],
        capture_output=True, text=True, check=True).stdout.strip()


class ComputerUseClient:
    def __init__(self, model: str = "gemini-3.5-flash"):
        import google.genai as g
        self._client = g.Client(api_key=_api_key())
        self.model = model
        self._prev_id = None
        self._call_id = None
        self._name = None

    def _consume(self, interaction) -> Turn:
        d = interaction.model_dump()
        self._prev_id = d.get("id")
        done = d.get("status") != "requires_action"
        steps = d.get("steps") or []
        fc = next((s for s in steps if s.get("type") == "function_call"), None)
        if fc:
            self._call_id = fc.get("id")
            self._name = fc.get("name")
            return Turn(action=fc, done=done)
        return Turn(action=None, done=True)

    def start(self, mission: str, screenshot_png: bytes) -> Turn:
        b64 = base64.b64encode(screenshot_png).decode()
        inter = self._client.interactions.create(
            model=self.model,
            input=[{"type": "text", "text": mission},
                   {"type": "image", "data": b64, "mime_type": "image/png"}],
            tools=TOOL)
        return self._consume(inter)

    def respond(self, result_kind: str, screenshot_png: bytes, reason=None) -> Turn:
        b64 = base64.b64encode(screenshot_png).decode()
        fr = {"type": "function_result", "name": self._name, "call_id": self._call_id,
              "result": [{"type": "text",
                          "text": json.dumps({"status": result_kind, "reason": reason})},
                         {"type": "image", "data": b64, "mime_type": "image/png"}]}
        inter = self._client.interactions.create(
            model=self.model, previous_interaction_id=self._prev_id,
            input=[fr], tools=TOOL)
        return self._consume(inter)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_loop.py -v`
Expected: PASS (3 tester).

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/gemini.py scripts/computer_use/loop.py tests/unit/computer_use/test_loop.py
git commit -m "feat(computer-use): loop engine + per-step journal + result protocol"
```

---

## Task 10: Visuell kritiker (API-avhengig)

**Files:**
- Create: `scripts/computer_use/critic.py`
- Test: `tests/unit/computer_use/test_critic.py`

**Interfaces:**
- Produces:
  - `criticize(screenshot_paths: list[str], *, client) -> list[dict]` — funn `{severity, text, screenshot}`. Bruker Gemini vision (`gemini-3.5-flash`) — kall-form per `gemini-media`-mønster. `client` injiseres for testbarhet.

- [ ] **Step 1: Write the failing test (mocket vision-klient)**

`tests/unit/computer_use/test_critic.py`:
```python
from test_smoke import load
critic = load("critic")


class FakeVision:
    def analyze(self, paths):
        return [{"severity": "P2", "text": "knapp avkuttet", "screenshot": paths[0]}]


def test_criticize_returns_findings():
    out = critic.criticize(["shot_001.png"], client=FakeVision())
    assert out[0]["severity"] == "P2"
    assert out[0]["screenshot"] == "shot_001.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_critic.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/critic.py`:
```python
CRITIC_PROMPT = ("Finn visuelle problemer i disse app-skjermbildene: overlapp, avkutting, "
                 "kontrast, justering, layout-brudd, off-screen-elementer. "
                 "Returner JSON-liste med {severity (P1/P2/P3), text, screenshot}.")


def criticize(screenshot_paths, *, client) -> list[dict]:
    if not screenshot_paths:
        return []
    return client.analyze(screenshot_paths)
```

(Den ekte `client.analyze` bruker `google-genai` vision over de **dedupede** bildene — Task 5 — og parser JSON robust per `gemini-media`-mønsteret.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_critic.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/critic.py tests/unit/computer_use/test_critic.py
git commit -m "feat(computer-use): visual critic pass"
```

---

## Task 11: CLI + skill-wrapper + smoke

**Files:**
- Create: `scripts/computer_use/cli.py`
- Create: `scripts/ios-visual-explore` (kjørbart uv-shim)
- Create: `skills/ios-visual-explore/SKILL.md`
- Test: `tests/unit/computer_use/test_cli.py`

**Interfaces:**
- Consumes: alle moduler over.
- Produces: CLI `ios-visual-explore --udid <U> --bundle <B> "<oppdrag>" [--max-steps N] [--dry-run]`.

- [ ] **Step 1: Write the failing test (argparse)**

`tests/unit/computer_use/test_cli.py`:
```python
from test_smoke import load
cli = load("cli")


def test_parse_args_minimal():
    ns = cli.parse_args(["--udid", "U1", "--bundle", "com.x", "utforsk onboarding"])
    assert ns.udid == "U1" and ns.bundle == "com.x" and ns.mission == "utforsk onboarding"
    assert ns.max_steps == 25


def test_dry_run_flag():
    ns = cli.parse_args(["--udid", "U1", "--bundle", "com.x", "--dry-run", "x"])
    assert ns.dry_run is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_cli.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

> **SPIKE-justert:** orchestreringen bruker de ferdige interfacene: `coordinate_space() -> (pw, ph)`,
> `loop.run(..., screenshot_dir=...)` (returnerer `journal` + `status` + `baseline_screenshot`),
> `critic.criticize(paths, client=...)`. `VisionCritic` (det ekte vision-passet) ligger i `gemini.py`
> og kjøres KUN i live-smoke (degraderer grasiøst til `[]` ved feil — aldri krasj på kritiker).

`scripts/computer_use/cli.py`:
```python
import argparse
import importlib.util
import json
import pathlib
import time


def _load(n):
    s = importlib.util.spec_from_file_location(n, pathlib.Path(__file__).resolve().parent / f"{n}.py")
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


TOP_INSET = 50.0     # status-bar / dynamic island (punkter)
BOTTOM_INSET = 40.0  # home-indikator (punkter)


def parse_args(argv):
    p = argparse.ArgumentParser(prog="ios-visual-explore")
    p.add_argument("--udid", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("mission")
    p.add_argument("--max-steps", type=int, default=25, dest="max_steps")
    p.add_argument("--out", default=None, help="output-mappe (default: computer-use-runs/run-<ts>)")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    preflight, executor_idb = _load("preflight"), _load("executor_idb")
    coords, loop = _load("coords"), _load("loop")
    dedup, report, critic, gemini = _load("dedup"), _load("report"), _load("critic"), _load("gemini")

    env = preflight.preflight(args.udid, args.bundle)   # resolve idb + launch app
    executor = executor_idb.IdbExecutor(args.udid)
    point_w, point_h = executor.coordinate_space()
    safe = coords.SafeArea(0, TOP_INSET, point_w, point_h - BOTTOM_INSET)
    client = gemini.ComputerUseClient()

    if args.dry_run:
        # single-turn planning-probe (ingen handling utføres)
        turn = client.start(args.mission, executor.screenshot())
        print(json.dumps({"dry_run": True, "planned": turn.action, "done": turn.done},
                         ensure_ascii=False, indent=2))
        return

    out = pathlib.Path(args.out or f"computer-use-runs/run-{int(time.time())}")
    shots = out / "screenshots"
    out.mkdir(parents=True, exist_ok=True)

    try:
        result = loop.run(args.mission, executor, client, max_steps=args.max_steps,
                          safe_area=safe, screenshot_dir=str(shots))
    finally:
        # teardown (spec §7): aldri destruktivt; sim-state forblir som den er.
        pass

    journal = result["journal"]
    last = len(journal)
    retained = []
    if result.get("baseline_screenshot"):
        retained.append(result["baseline_screenshot"])
    for e in journal:
        if e.get("screenshot") and dedup.should_retain(
                e.get("result", "success"), e["step"] == 1, e["step"] == last):
            retained.append(e["screenshot"])

    findings = critic.criticize(retained, client=gemini.VisionCritic()) if retained else []
    report_path = out / "report.md"
    report_path.write_text(report.build_markdown(args.mission, env, journal, findings, result["status"]))
    print(report.text_summary(findings, str(report_path), str(shots)))
```

Legg til i `scripts/computer_use/gemini.py` (det ekte vision-pass; IKKE enhetstestet — live i Step 6):
```python
class VisionCritic:
    """Ekte Gemini-vision-kritiker. analyze(paths) -> findings. Degraderer til [] ved enhver feil."""
    def __init__(self, model: str = "gemini-3.5-flash"):
        import google.genai as g
        self._client = g.Client(api_key=_api_key())
        self.model = model

    def analyze(self, screenshot_paths) -> list:
        from google.genai import types
        prompt = _load("critic").CRITIC_PROMPT
        parts = [types.Part.from_text(text=prompt)]
        for p in screenshot_paths:
            parts.append(types.Part.from_bytes(data=open(p, "rb").read(), mime_type="image/png"))
        try:
            resp = self._client.models.generate_content(model=self.model, contents=parts)
            text = (resp.text or "").strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1].removeprefix("json").strip()
            data = json.loads(text)
            return data if isinstance(data, list) else []
        except Exception:
            return []
```

`scripts/ios-visual-explore` (uv-shim, `chmod +x`):
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["google-genai"]
# ///
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from computer_use.cli import main
main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_cli.py -v`
Expected: PASS (2 tester). (Orchestreringen + `VisionCritic` er live-only; enhetstestene dekker kun `parse_args`.)

- [ ] **Step 5: Skriv skill-wrapper**

`skills/ios-visual-explore/SKILL.md` — frontmatter (`name: ios-visual-explore`, `description:` som Tier-2-eskalering når accessibility-e2e ikke avslører nok), dokumenter når det brukes, hvordan kalle `scripts/ios-visual-explore`, og at den returnerer **tekst-only** oppsummering (filstier, ingen inline-bilder).

- [ ] **Step 6: Full smoke mot enkel SwiftUI-app**

Med booted iPhone-sim + en enkel app åpen:
```bash
scripts/ios-visual-explore --udid <UDID> --bundle <BUNDLE> "trykk gjennom hovedskjermen og rapporter visuelle problemer" --max-steps 8
```
Expected: en Markdown-rapport + skjermbilde-mappe skrives; stdout viser tekst-only oppsummering.

- [ ] **Step 7: Commit**

```bash
git add scripts/computer_use/cli.py scripts/ios-visual-explore skills/ios-visual-explore/ tests/unit/computer_use/test_cli.py
git commit -m "feat(computer-use): CLI + skill wrapper + smoke"
```

---

## Self-Review-notat

- **Spec-dekning:** §3 arkitektur → Task 9; §6a idb/koordinater → Task 3,7; action-adapter §4/§5-spec → Task 4; §7 bounds/foreground/teardown → Task 3,8 (teardown foldes inn i CLI-orkestrering Task 11/preflight); §8 dedup/evidens/rapport → Task 5,6; §9 result-protokoll/journal → Task 9; §10 testing → hver task; kritiker §8B → Task 10; skill-grense §8 → Task 6,11.
- **Gated antagelser:** Task 1 spike forankrer R1 (API-form), R4 (touch), R7 (oracle), idb-koordinatkonvensjon. Task 9/10 og `is_app_foreground` (Task 8) justeres mot SPIKE-FINDINGS før de er endelige.
- **Åpen oppfølging:** teardown/signal-trap (spec §7) implementeres i CLI-orkestreringen (Task 11 Step 3) — legg `trap`/`finally` rundt loop-kjøringen som relauncher/rydder sim-state.
