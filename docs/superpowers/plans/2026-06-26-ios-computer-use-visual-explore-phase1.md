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

**Interfaces:**
- Consumes: ingen.
- Produces:
  - `ExecutorAction` (dataclass `kind: str`, `params: dict`) — `kind` ∈ {`tap`,`swipe`,`type`,`wait`,`unsupported`}
  - `adapt(cu_action: dict) -> ExecutorAction` — mapper computer_use-handling → executor-primitiv

- [ ] **Step 1: Write the failing test**

`tests/unit/computer_use/test_actions.py`:
```python
from test_smoke import load
actions = load("actions")


def test_tap_passthrough():
    a = actions.adapt({"name": "click", "x": 500, "y": 400})
    assert a.kind == "tap" and a.params["x"] == 500 and a.params["y"] == 400


def test_scroll_maps_to_swipe():
    a = actions.adapt({"name": "scroll", "x": 500, "y": 500, "direction": "down"})
    assert a.kind == "swipe"
    assert a.params["direction"] == "down"   # scroll er KJERNE-navigasjon, ikke unsupported


def test_wait_is_noop():
    a = actions.adapt({"name": "wait"})
    assert a.kind == "wait"


def test_unknown_is_unsupported():
    a = actions.adapt({"name": "teleport"})
    assert a.kind == "unsupported"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_actions.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/actions.py`:
```python
from dataclasses import dataclass


@dataclass
class ExecutorAction:
    kind: str
    params: dict


def adapt(cu: dict) -> ExecutorAction:
    name = cu.get("name", "")
    if name in ("click", "tap"):
        return ExecutorAction("tap", {"x": cu["x"], "y": cu["y"]})
    if name == "scroll":
        return ExecutorAction("swipe", {
            "x": cu.get("x"), "y": cu.get("y"),
            "direction": cu.get("direction", "down"),
        })
    if name in ("type", "press_key"):
        return ExecutorAction("type", {"text": cu.get("text", "")})
    if name == "wait":
        return ExecutorAction("wait", {})
    return ExecutorAction("unsupported", {"original": name})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_actions.py -v`
Expected: PASS (4 tester).

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

**Interfaces:**
- Consumes: `coords.Point`, `coords.SafeArea`.
- Produces:
  - `IdbExecutor(udid: str)` med metoder:
    - `screenshot() -> bytes` (PNG)
    - `tap(p: Point) -> None`
    - `swipe(p: Point, direction: str) -> None`
    - `type_text(text: str) -> None`
    - `coordinate_space() -> tuple[int,int,float]` (img_w, img_h, backing_scale)
  - Bruker subprocess til `xcrun simctl` + `idb`. **Justér kommando-form per SPIKE-FINDINGS.md (Task 1).**

- [ ] **Step 1: Write the failing test (kommando-bygging, mocket subprocess)**

`tests/unit/computer_use/test_executor_idb.py`:
```python
from test_smoke import load
ex = load("executor_idb")


def test_tap_builds_idb_command(monkeypatch):
    calls = []
    monkeypatch.setattr(ex, "_run", lambda args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1")
    e.tap(ex_point(195.0, 400.0))
    assert calls and "tap" in calls[-1]
    assert "UDID-1" in " ".join(calls[-1])


def ex_point(x, y):
    coords = load("coords")
    return coords.Point(x, y)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_executor_idb.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/executor_idb.py` (kommando-former per SPIKE-FINDINGS):
```python
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

    def swipe(self, p, direction: str) -> None:
        dx, dy = {"down": (0, 300), "up": (0, -300),
                  "left": (-300, 0), "right": (300, 0)}.get(direction, (0, 300))
        x2, y2 = round(p.x) + dx, round(p.y) + dy
        self._run(["idb", "ui", "swipe", str(round(p.x)), str(round(p.y)),
                   str(x2), str(y2), "--udid", self.udid])

    def type_text(self, text: str) -> None:
        self._run(["idb", "ui", "text", text, "--udid", self.udid])

    def coordinate_space(self) -> tuple[int, int, float]:
        """(img_w_px, img_h_px, backing_scale). Leser skjermbilde-piksler +
        utleder scale fra device logical size (per SPIKE-FINDINGS, Task 1)."""
        from PIL import Image  # eller minimal PNG-header-parse om PIL unngås
        import io
        png = self.screenshot()
        w, h = Image.open(io.BytesIO(png)).size
        scale = self._device_backing_scale()  # f.eks. 3.0 for de fleste moderne iPhones
        return (w, h, scale)

    def _device_backing_scale(self) -> float:
        # Utled fra device-typen (SPIKE-FINDINGS Task 1 Step 2). Placeholder-default 3.0;
        # erstatt med faktisk oppslag mot `simctl list devices` / device-klasse-tabell.
        return 3.0
```

> Merk: `coordinate_space` legger til `Pillow` som dep i `ios-visual-explore`-shimmen (Task 11), eller bruk en minimal PNG-IHDR-parse (bytes 16–24) for å unngå avhengigheten.

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

- [ ] **Step 1: Write the failing test**

`tests/unit/computer_use/test_preflight.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_preflight.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/preflight.py` (oracle-kropp per SPIKE-FINDINGS):
```python
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


def is_app_foreground(udid: str, bundle_id: str) -> bool:
    # MEKANISME PER SPIKE-FINDINGS (R7). Default: XCTest-probe eller idb-state.
    # Erstatt med den verifiserte oracle-en fra Task 1.
    raise NotImplementedError("Sett inn verifisert foreground-oracle fra SPIKE-FINDINGS.md")


def preflight(udid: str, bundle_id: str) -> dict:
    resolve_tool("idb")
    subprocess.run(["xcrun", "simctl", "launch", udid, bundle_id], check=True)
    return {"udid": udid, "bundle_id": bundle_id, "platform": "ios"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_preflight.py -v`
Expected: PASS (2 tester).

- [ ] **Step 5: Implementer `is_app_foreground` per SPIKE-FINDINGS + manuell verifisering**

Sett inn den verifiserte oracle-mekanismen (Task 1 Step 5). Verifiser manuelt at den returnerer `True` når appen er fremme og `False` når du sender den til hjemskjermen.

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

**Interfaces:**
- Consumes: `actions.adapt`, `coords.denormalize`/`in_safe_area`, `IdbExecutor`, `dedup`, `report`.
- Produces:
  - `gemini.ComputerUseClient` med `start(mission, screenshot_png) -> Turn` og `respond(result_kind, screenshot_png, reason) -> Turn` (kjeding per SPIKE-FINDINGS)
  - `Turn` (dataclass: `action: dict | None`, `done: bool`)
  - `loop.run(mission, executor, client, *, max_steps=25, safe_area, scale) -> dict` (rapport-data + journal)

- [ ] **Step 1: Write the failing test (mocket klient + executor, verifiserer journal + result-protokoll)**

`tests/unit/computer_use/test_loop.py`:
```python
from test_smoke import load
loop = load("loop")


class FakeExec:
    def __init__(self): self.taps = []
    def screenshot(self): return b"PNG"
    def coordinate_space(self): return (1170, 2532, 3.0)
    def tap(self, p): self.taps.append(p)
    def swipe(self, p, d): pass
    def type_text(self, t): pass


class FakeClient:
    """Emitterer ett tap så 'done'."""
    def __init__(self): self.results = []
    def start(self, mission, shot):
        return loop_turn({"name": "click", "x": 500, "y": 500}, False)
    def respond(self, kind, shot, reason):
        self.results.append(kind)
        return loop_turn(None, True)


def loop_turn(action, done):
    T = load("loop").Turn
    return T(action=action, done=done)


def test_loop_executes_then_sends_result_and_journals():
    co = load("coords")
    safe = co.SafeArea(0, 0, 390, 844)
    ex, cl = FakeExec(), FakeClient()
    out = loop.run("utforsk", ex, cl, max_steps=5, safe_area=safe, scale=3.0)
    assert ex.taps, "tap skulle blitt utført"
    assert cl.results == ["success"], "function_result måtte sendes etter handling"
    assert out["journal"][0]["state"] == "result_sent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_loop.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`scripts/computer_use/gemini.py` — tynn wrapper rundt computer_use (interactions) **per SPIKE-FINDINGS**; eksponerer `ComputerUseClient`, `Turn`. (Konkret request/response-form settes fra Task 1.)

`scripts/computer_use/loop.py`:
```python
import time
from dataclasses import dataclass


@dataclass
class Turn:
    action: dict | None
    done: bool


def run(mission, executor, client, *, max_steps=25, safe_area, scale, settle=0.3):
    # importer rene moduler via samme loader som testene bruker
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
        img_w, img_h, sc = executor.coordinate_space()
        kind, reason = "success", None
        if ea.kind in ("tap", "swipe"):
            p = coords.denormalize(turn.action["x"], turn.action["y"], img_w, img_h, sc)
            if not coords.in_safe_area(p, safe_area):
                kind, reason = "rejected", "outside safe area"
            else:
                entry["state"] = "validated"
                (executor.tap(p) if ea.kind == "tap" else executor.swipe(p, ea.params["direction"]))
                entry["state"] = "executed"
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

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_loop.py -v`
Expected: PASS.

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

`scripts/computer_use/cli.py`:
```python
import argparse


def parse_args(argv):
    p = argparse.ArgumentParser(prog="ios-visual-explore")
    p.add_argument("--udid", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("mission")
    p.add_argument("--max-steps", type=int, default=25, dest="max_steps")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    # orkestrer: preflight → loop.run → dedup → critic → report; skriv rapport til disk,
    # skriv text_summary til stdout (kontekst-renhet). --dry-run: single-turn planning-probe.
    ...
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
Expected: PASS (2 tester).

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
