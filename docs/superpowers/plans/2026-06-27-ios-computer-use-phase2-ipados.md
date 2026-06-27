# iOS Computer-Use Visual Explore — Fase 2 (iPadOS) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Phase-1 iPhone visual-explorer to iPadOS — fullscreen, operator-chosen orientation — by replacing hardcoded safe-area constants with device/orientation-aware derivation and an iPad-robust foreground oracle.

**Architecture:** The loop/coords/gemini core stays untouched (coordinate mapping is already device-agnostic via `coordinate_space()`). The work is concentrated in `preflight.py` (owns pre-flight `describe-all`, builds `SafeArea`, redesigned oracle) and `coords.py` (pure `derive_insets` + `INSET_TABLE` fallback), wired through `cli.py`. A SPIKE task gates all production code: it verifies seven iPad assumptions against a live sim before any implementation.

**Tech Stack:** Python 3 (stdlib only), `idb` + `xcrun simctl` (touch + screenshots), pytest. Gemini `computer_use` via the existing `gemini.py` client.

**Spec:** `docs/superpowers/specs/2026-06-27-ios-computer-use-phase2-ipados-design.md`

## Global Constraints

- **Python stdlib only** in `scripts/computer_use/` — no new third-party deps (matches Phase 1; Pillow was deliberately dropped).
- **Coordinate model is POINTS, not pixels** — `idb ui tap` takes points; `denormalize` maps 0–1000 against `coordinate_space()` (describe-all Application-frame). Do NOT reintroduce backing-scale math.
- **`loop.py`, `gemini.py`, `coords.denormalize`, `coords.in_safe_area` stay byte-for-byte unchanged** — regression surface control (R-iPad-5). Only `coords.py` *additions* (new functions) are allowed.
- **`--orientation` default is `portrait`** — preserves Phase-1 iPhone behavior.
- **Fail-closed on ambiguity:** unknown `device_class`, orientation that never settles, or baseline that does not match device full-width → raise `PreflightError`, never proceed with a guessed value.
- **SPIKE-gate:** no task numbered ≥ 2 starts until Task 1's addendum to `docs/superpowers/specs/SPIKE-FINDINGS.md` exists and every assumption S1–S7 is confirmed or explicitly downgraded to its fallback.
- **Tests live in** `tests/unit/computer_use/` and run green via `python3 -m pytest tests/unit/computer_use/ -q`.

---

### Task 1: SPIKE — verify iPad assumptions (GATE, no production code)

**Files:**
- Modify: `docs/superpowers/specs/SPIKE-FINDINGS.md` (append a "Fase 2 (iPadOS) addendum")
- No `scripts/` changes in this task.

**Interfaces:**
- Consumes: a booted iPad simulator with `idb-companion` connected + a simple SwiftUI app installed.
- Produces: concrete answers that later tasks reference — the `describe-all` Application-element schema (does it carry `bundleID`? a `frame` with `x/y/width/height`?), whether status-bar/home-indicator frames are exposed, the orientation-setting mechanism, and the `spotlight-pill` presence on iPad. Each S1–S7 ends "CONFIRMED" or "DOWNGRADED → <fallback>".

- [ ] **Step 1: Boot an iPad sim and capture raw `describe-all`**

```bash
# pick a booted iPad; install/boot if needed
xcrun simctl list devices | grep -i ipad
IPAD_UDID=<chosen-udid>
xcrun simctl bootstatus "$IPAD_UDID" -b
idb ui describe-all --udid "$IPAD_UDID" > /tmp/ipad-describe-portrait.json
python3 -c "import json,sys; d=json.load(open('/tmp/ipad-describe-portrait.json')); app=[e for e in d if e.get('type')=='Application'][0]; print(json.dumps(app, indent=2)[:1200])"
```

Record in the addendum: the Application element's keys (S7: is `bundleID` present? what exact key?), its `frame` (S6: origin `x/y` == 0? width == device full-width?), and whether any status-bar / home-indicator child elements expose frames (S1).

- [ ] **Step 2: Verify the home-screen marker (S2)**

```bash
# go to home, dump, check for spotlight-pill
xcrun simctl spawn "$IPAD_UDID" launchctl list >/dev/null   # sanity
idb ui describe-all --udid "$IPAD_UDID" | python3 -c "import json,sys; d=json.load(sys.stdin); print('spotlight-pill present:', any(e.get('AXUniqueId')=='spotlight-pill' for e in d))"
```

Record S2: present → oracle home-detection works on iPad. Absent → find an alternative iPad home marker, or DOWNGRADE (document that home-exit is undetected on iPad).

- [ ] **Step 3: Verify orientation setting + settle (S5) and landscape geometry (S1)**

```bash
# try the orientation mechanism; the exact command is what this step discovers
# candidate: simctl UI; if unavailable, idb; record whichever works
xcrun simctl ui "$IPAD_UDID" 2>/dev/null | head || true   # probe available simctl ui subcommands
# after setting landscape, re-dump and confirm the Application frame aspect flips
idb ui describe-all --udid "$IPAD_UDID" > /tmp/ipad-describe-landscape.json
```

Record S5 (the working orientation command + how many polls until the frame aspect reflects it) and S1 for landscape (are side-insets `left`/`right` derivable?).

- [ ] **Step 4: Verify touch + foreground-by-bundleID (S4, S7)**

```bash
# launch target, confirm tap works, then confirm Application.bundleID == target
xcrun simctl launch "$IPAD_UDID" <bundle-id>
idb ui tap 200 400 --udid "$IPAD_UDID"   # expect a visible nav change
idb ui describe-all --udid "$IPAD_UDID" | python3 -c "import json,sys; d=json.load(sys.stdin); app=[e for e in d if e.get('type')=='Application'][0]; print('bundleID key/value:', {k:app[k] for k in app if 'undle' in k.lower() or 'identifier' in k.lower()})"
```

Record S4 (tap/swipe/text work on iPad) and S7 (the exact field name carrying the bundle id, or DOWNGRADE to an alternative frontmost probe).

- [ ] **Step 5: Write the addendum and commit (GATE)**

Append a "Fase 2 (iPadOS) addendum" to `docs/superpowers/specs/SPIKE-FINDINGS.md` with a row per S1–S7: assumption → CONFIRMED (with the concrete value) | DOWNGRADED → fallback. Include the exact `bundleID` field name, orientation command, and observed iPad insets (portrait + landscape).

```bash
git add docs/superpowers/specs/SPIKE-FINDINGS.md
git commit -m "spike(phase2): iPad describe-all schema, bundleID oracle field, orientation mechanism, insets — S1-S7 addendum"
```

Expected: the addendum names a concrete answer for every S1–S7. **If any assumption is DOWNGRADED, update this plan's affected task (per spec §3 gate-regel) before proceeding.**

---

### Task 2: `INSET_TABLE` + `table_insets` (pure fallback)

**Files:**
- Modify: `scripts/computer_use/coords.py`
- Test: `tests/unit/computer_use/test_coords.py`

**Interfaces:**
- Consumes: `SafeArea` (existing dataclass: `left, top, right, bottom` as absolute point coords).
- Produces: `table_insets(device_class: str, orientation: str, point_w: float, point_h: float) -> SafeArea`; `INSET_TABLE: dict[str, dict[str, tuple]]`. Raises `KeyError`-derived behavior handled by caller (Task 7 maps unknown → `PreflightError`).

> **SPIKE-dependency:** the exact inset values below are HIG hypotheses; replace with the addendum's measured iPad values (Task 1 Step 1/3) if they differ. The *shape* (per device_class × orientation, 4-tuple inset) is fixed.

- [ ] **Step 1: Write the failing test**

```python
# test_coords.py
from computer_use import coords  # adjust to the project's load pattern if needed

def test_table_insets_ipad_portrait():
    sa = coords.table_insets("ipad", "portrait", 820.0, 1180.0)
    # insets (left, top, right, bottom) = (0, 24, 0, 20) -> absolute
    assert (sa.left, sa.top, sa.right, sa.bottom) == (0, 24, 820.0, 1160.0)

def test_table_insets_landscape_has_side_insets():
    sa = coords.table_insets("iphone_island", "landscape", 852.0, 393.0)
    # landscape island moves to a side -> left/right insets non-zero
    assert sa.left > 0 and sa.right < 852.0

def test_table_insets_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        coords.table_insets("nosuchdevice", "portrait", 100.0, 100.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_coords.py -k table_insets -v`
Expected: FAIL with `AttributeError: module 'coords' has no attribute 'table_insets'`

- [ ] **Step 3: Write minimal implementation**

```python
# coords.py — append (do NOT touch denormalize / in_safe_area)
# insets in POINTS as (left, top, right, bottom). Values are HIG defaults;
# Task 1 spike confirms/replaces them.
INSET_TABLE = {
    "ipad":          {"portrait": (0, 24, 0, 20),  "landscape": (0, 24, 0, 20)},
    "iphone_island": {"portrait": (0, 59, 0, 34),  "landscape": (59, 0, 59, 21)},
    "iphone_notch":  {"portrait": (0, 47, 0, 34),  "landscape": (47, 0, 47, 21)},
}

def table_insets(device_class, orientation, point_w, point_h):
    left, top, right, bottom = INSET_TABLE[device_class][orientation]
    return SafeArea(left, top, point_w - right, point_h - bottom)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_coords.py -k table_insets -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/coords.py tests/unit/computer_use/test_coords.py
git commit -m "feat(phase2): INSET_TABLE + table_insets device/orientation fallback"
```

---

### Task 3: `derive_insets` from describe-all + sanity guard (pure)

**Files:**
- Modify: `scripts/computer_use/coords.py`
- Test: `tests/unit/computer_use/test_coords.py`

**Interfaces:**
- Consumes: `elems` (list of describe-all element dicts), `point_w`, `point_h`.
- Produces: `derive_insets(elems: list, point_w: float, point_h: float) -> SafeArea | None`. Returns `None` when insets cannot be derived OR fail the sanity guard (caller falls through to `table_insets`).

> **SPIKE-dependency:** the element-identification logic (which `type`/`AXUniqueId` marks the status bar / home indicator) comes from Task 1's addendum. The fixtures below MUST be replaced with real spike-captured `describe-all` snippets before this task is considered done.

- [ ] **Step 1: Write the failing test**

```python
def _ipad_portrait_elems():
    # spike-captured fixture (placeholder shape — replace with real Task 1 dump)
    return [
        {"type": "Application", "frame": {"x": 0, "y": 0, "width": 820, "height": 1180}},
        {"type": "StatusBar",   "frame": {"x": 0, "y": 0, "width": 820, "height": 24}},
        {"type": "Other", "AXUniqueId": "home-indicator", "frame": {"x": 0, "y": 1160, "width": 820, "height": 20}},
    ]

def test_derive_insets_ipad_portrait():
    sa = coords.derive_insets(_ipad_portrait_elems(), 820.0, 1180.0)
    assert sa is not None
    assert sa.top == 24 and sa.bottom == 1160.0

def test_derive_insets_sanity_guard_rejects_oversized():
    elems = [
        {"type": "Application", "frame": {"x": 0, "y": 0, "width": 820, "height": 1180}},
        {"type": "StatusBar",   "frame": {"x": 0, "y": 0, "width": 820, "height": 600}},  # 600 > 25% of 1180
    ]
    assert coords.derive_insets(elems, 820.0, 1180.0) is None

def test_derive_insets_returns_none_when_no_markers():
    elems = [{"type": "Application", "frame": {"x": 0, "y": 0, "width": 820, "height": 1180}}]
    assert coords.derive_insets(elems, 820.0, 1180.0) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_coords.py -k derive_insets -v`
Expected: FAIL with `AttributeError: ... 'derive_insets'`

- [ ] **Step 3: Write minimal implementation**

```python
# coords.py — append
_MAX_INSET_FRACTION = 0.25  # an inset larger than this of its dimension is suspect

def derive_insets(elems, point_w, point_h):
    """Derive a SafeArea from describe-all elements, or None to fall through to table.
    Element identification per SPIKE-FINDINGS Fase 2 addendum."""
    top = bottom = left = right = 0.0
    for e in elems:
        f = e.get("frame") or {}
        uid = e.get("AXUniqueId", "")
        etype = e.get("type", "")
        if etype == "StatusBar":
            top = max(top, float(f.get("y", 0)) + float(f.get("height", 0)))
        elif uid == "home-indicator":
            bottom = max(bottom, point_h - float(f.get("y", 0)))
    # sanity guard: reject misidentified elements
    for inset, dim in ((top, point_h), (bottom, point_h), (left, point_w), (right, point_w)):
        if inset < 0 or inset > _MAX_INSET_FRACTION * dim:
            return None
    if top == 0 and bottom == 0 and left == 0 and right == 0:
        return None  # nothing derived -> use table
    return SafeArea(left, top, point_w - right, point_h - bottom)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_coords.py -k derive_insets -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/coords.py tests/unit/computer_use/test_coords.py
git commit -m "feat(phase2): derive_insets from describe-all + sanity guard"
```

---

### Task 4: `device_class` detection

**Files:**
- Modify: `scripts/computer_use/preflight.py`
- Test: `tests/unit/computer_use/test_preflight.py`

**Interfaces:**
- Consumes: `udid`.
- Produces: `device_class(udid: str) -> str` returning one of `INSET_TABLE`'s keys (`"ipad"`, `"iphone_island"`, `"iphone_notch"`). Unknown device type → raises `PreflightError` (Global Constraint: fail-closed).

> **SPIKE-dependency:** the mapping from `simctl` device-type identifier to class comes from Task 1; the test uses a stub of the simctl call.

- [ ] **Step 1: Write the failing test**

```python
# test_preflight.py
from computer_use import preflight

def test_device_class_ipad(monkeypatch):
    monkeypatch.setattr(preflight, "_device_type_id", lambda udid: "com.apple.CoreSimulator.SimDeviceType.iPad-Pro-11-inch")
    assert preflight.device_class("X") == "ipad"

def test_device_class_unknown_fails_closed(monkeypatch):
    monkeypatch.setattr(preflight, "_device_type_id", lambda udid: "com.apple.CoreSimulator.SimDeviceType.Apple-Watch")
    import pytest
    with pytest.raises(preflight.PreflightError):
        preflight.device_class("X")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_preflight.py -k device_class -v`
Expected: FAIL with `AttributeError: ... 'device_class'`

- [ ] **Step 3: Write minimal implementation**

```python
# preflight.py — append
def _device_type_id(udid):
    out = subprocess.run(["xcrun", "simctl", "list", "devices", "-j"],
                         capture_output=True, text=True, timeout=20).stdout
    data = json.loads(out)
    for devs in data.get("devices", {}).values():
        for d in devs:
            if d.get("udid") == udid:
                return d.get("deviceTypeIdentifier", "")
    return ""

def device_class(udid):
    tid = _device_type_id(udid).lower()
    if "ipad" in tid:
        return "ipad"
    if any(m in tid for m in ("iphone-15", "iphone-16", "iphone-17", "pro-max", "iphone-14-pro")):
        return "iphone_island"
    if "iphone" in tid:
        return "iphone_notch"
    raise PreflightError(f"Unknown device type '{tid}' for {udid}; add it to device_class()")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_preflight.py -k device_class -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/preflight.py tests/unit/computer_use/test_preflight.py
git commit -m "feat(phase2): device_class detection (fail-closed on unknown)"
```

---

### Task 5: Redesigned foreground oracle (`is_app_foreground` + `bundleID`)

**Files:**
- Modify: `scripts/computer_use/preflight.py`
- Test: `tests/unit/computer_use/test_preflight.py`

**Interfaces:**
- Consumes: `udid`, `bundle_id`, `baseline_full_width`.
- Produces: `is_app_foreground(udid, bundle_id, baseline_full_width) -> bool` — `True` iff one `describe-all` shows an Application element whose bundle id == `bundle_id` AND it is not the home screen AND its width ≥ `0.95 * baseline_full_width`. **Signature change** from Phase-1's `is_app_foreground(udid, bundle_id)`.

> **SPIKE-dependency:** the bundle-id field name on the Application element comes from Task 1 S7. The helper `_app_element(elems)` and `_BUNDLE_KEY` below use the spike's confirmed key.

> **Breaking-change note:** three existing Phase-1 tests use the old 2-arg signature — `test_preflight.py:35`, `:42`, `:48` (`pf.is_app_foreground("U", "com.x.app")`). They **must be rewritten** to the 3-arg form below (replace them, don't add alongside), or the suite fails to import. The new tests below are their replacements.

- [ ] **Step 1: Rewrite the existing foreground tests (replace the 2-arg ones)**

```python
def _elems(bundle, width, home=False):
    es = [{"type": "Application", "bundleID": bundle, "frame": {"x": 0, "y": 0, "width": width, "height": 1180}}]
    if home:
        es.append({"AXUniqueId": "spotlight-pill"})
    return es

def test_foreground_true_when_target_fullscreen(monkeypatch):
    monkeypatch.setattr(preflight, "_describe_all_raw", lambda udid: _elems("com.x.app", 820))
    monkeypatch.setattr(preflight, "_process_running", lambda u, b: True)
    assert preflight.is_app_foreground("U", "com.x.app", 820.0) is True

def test_foreground_false_when_other_app_frontmost(monkeypatch):
    monkeypatch.setattr(preflight, "_describe_all_raw", lambda udid: _elems("com.apple.mobilesafari", 820))
    monkeypatch.setattr(preflight, "_process_running", lambda u, b: True)
    assert preflight.is_app_foreground("U", "com.x.app", 820.0) is False

def test_foreground_false_when_split_narrow(monkeypatch):
    monkeypatch.setattr(preflight, "_describe_all_raw", lambda udid: _elems("com.x.app", 500))
    monkeypatch.setattr(preflight, "_process_running", lambda u, b: True)
    assert preflight.is_app_foreground("U", "com.x.app", 820.0) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_preflight.py -k foreground -v`
Expected: FAIL — `is_app_foreground` currently takes 2 args / has no bundleID check.

- [ ] **Step 3: Write minimal implementation**

```python
# preflight.py — replace is_app_foreground; add helpers
_BUNDLE_KEY = "bundleID"  # confirmed in SPIKE-FINDINGS Fase 2 addendum (S7)

def _describe_all_raw(udid):
    out = subprocess.run(["idb", "ui", "describe-all", "--udid", udid],
                         capture_output=True, text=True, timeout=30).stdout
    elems = json.loads(out)
    if not isinstance(elems, list):
        raise ValueError("describe-all did not return a list")
    return elems

def _app_element(elems):
    return next((e for e in elems if e.get("type") == "Application"), None)

def is_app_foreground(udid, bundle_id, baseline_full_width):
    """R7+S7 oracle: target app is frontmost AND fullscreen. Single describe-all."""
    if not _process_running(udid, bundle_id):
        return False
    try:
        elems = _describe_all_raw(udid)
    except (subprocess.TimeoutExpired, ValueError):
        return False  # caller (loop) treats probe errors as fail-open; here we say not-foreground
    if any(e.get("AXUniqueId") == "spotlight-pill" for e in elems):
        return False  # home screen
    app = _app_element(elems)
    if app is None or app.get(_BUNDLE_KEY) != bundle_id:
        return False
    width = float((app.get("frame") or {}).get("width", 0))
    return width >= 0.95 * baseline_full_width
```

After this, the old `_on_home_screen(udid)` helper is **dead** (the new oracle inlines the `spotlight-pill` check via the single `_describe_all_raw` call — this is the GLM double-describe-all fix). Remove `_on_home_screen` and confirm nothing else references it (`grep -rn _on_home_screen scripts/ tests/`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_preflight.py -k foreground -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/preflight.py tests/unit/computer_use/test_preflight.py
git commit -m "feat(phase2): foreground oracle verifies frontmost==target via bundleID (S7)"
```

---

### Task 6: Orientation + baseline in `preflight()` (terminate→set→launch→settle→validate→build SafeArea)

**Files:**
- Modify: `scripts/computer_use/preflight.py`
- Test: `tests/unit/computer_use/test_preflight.py`

**Interfaces:**
- Consumes: `udid`, `bundle_id`, `orientation`; uses `device_class`, `coords.derive_insets`, `coords.table_insets`.
- Produces: `preflight(udid, bundle_id, orientation) -> dict` returning env with keys `udid, bundle_id, platform, orientation, device_class, safe_area (SafeArea), safe_area_source ("derived"|"table"), baseline_full_width`. **Does NOT** return raw `describe_all_elems` (report-leak guard). Raises `PreflightError` on unknown device, orientation-no-settle, or baseline≠device-full-width.

> **SPIKE-dependency:** `_set_orientation(udid, orientation)` and the device full-width lookup come from Task 1 (S5, S6).

- [ ] **Step 1: Write the failing test**

```python
def test_preflight_builds_safe_area_and_strips_elems(monkeypatch):
    elems = [{"type": "Application", "bundleID": "com.x.app", "frame": {"x": 0, "y": 0, "width": 820, "height": 1180}},
             {"type": "StatusBar", "frame": {"x": 0, "y": 0, "width": 820, "height": 24}},
             {"type": "Other", "AXUniqueId": "home-indicator", "frame": {"x": 0, "y": 1160, "width": 820, "height": 20}}]
    monkeypatch.setattr(preflight, "resolve_tool", lambda n: "/bin/true")
    monkeypatch.setattr(preflight, "_terminate", lambda u, b: None)
    monkeypatch.setattr(preflight, "_set_orientation", lambda u, o: None)
    monkeypatch.setattr(preflight, "_launch", lambda u, b: None)
    monkeypatch.setattr(preflight, "_settle_orientation", lambda u, o: elems)  # returns settled elems
    monkeypatch.setattr(preflight, "device_class", lambda u: "ipad")
    monkeypatch.setattr(preflight, "_device_full_width", lambda dc, o: 820.0)
    env = preflight.preflight("U", "com.x.app", "portrait")
    assert env["safe_area_source"] == "derived"
    assert env["baseline_full_width"] == 820.0
    assert "describe_all_elems" not in env
    assert env["safe_area"].top == 24

def test_preflight_fails_closed_on_baseline_mismatch(monkeypatch):
    elems = [{"type": "Application", "bundleID": "com.x.app", "frame": {"x": 0, "y": 0, "width": 500, "height": 1180}}]
    monkeypatch.setattr(preflight, "resolve_tool", lambda n: "/bin/true")
    monkeypatch.setattr(preflight, "_terminate", lambda u, b: None)
    monkeypatch.setattr(preflight, "_set_orientation", lambda u, o: None)
    monkeypatch.setattr(preflight, "_launch", lambda u, b: None)
    monkeypatch.setattr(preflight, "_settle_orientation", lambda u, o: elems)
    monkeypatch.setattr(preflight, "device_class", lambda u: "ipad")
    monkeypatch.setattr(preflight, "_device_full_width", lambda dc, o: 820.0)  # expected 820, got 500
    import pytest
    with pytest.raises(preflight.PreflightError):
        preflight.preflight("U", "com.x.app", "portrait")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_preflight.py -k "preflight_builds or baseline_mismatch" -v`
Expected: FAIL — `preflight()` takes 2 args, has no orientation/safe_area logic.

- [ ] **Step 3: Write minimal implementation**

```python
# preflight.py — replace preflight(); add helpers (import coords via the project load pattern)
import time

_SETTLE_POLLS = 10
_SETTLE_SLEEP = 1.5  # ~15s total

def _terminate(udid, bundle_id):
    subprocess.run(["xcrun", "simctl", "terminate", udid, bundle_id],
                   capture_output=True, timeout=15)  # ok if not running

def _set_orientation(udid, orientation):
    # mechanism confirmed by SPIKE S5; placeholder uses simctl. Adjust per addendum.
    subprocess.run(["xcrun", "simctl", "ui", udid, "orientation", orientation],
                   capture_output=True, timeout=15)

def _launch(udid, bundle_id):
    subprocess.run(["xcrun", "simctl", "launch", udid, bundle_id], check=True, timeout=30)

def _frame_matches_orientation(app, orientation):
    f = app.get("frame") or {}
    w, h = float(f.get("width", 0)), float(f.get("height", 0))
    return (w >= h) if orientation == "landscape" else (h >= w)

def _settle_orientation(udid, orientation):
    for _ in range(_SETTLE_POLLS):
        elems = _describe_all_raw(udid)
        app = _app_element(elems)
        if app is not None and _frame_matches_orientation(app, orientation):
            return elems
        time.sleep(_SETTLE_SLEEP)
    raise PreflightError("orientation did not settle; set it manually before the run")

def _device_full_width(device_class, orientation):
    # full screen width in points per device_class x orientation (from spike / HIG).
    full = {"ipad": {"portrait": 820.0, "landscape": 1180.0},
            "iphone_island": {"portrait": 393.0, "landscape": 852.0},
            "iphone_notch": {"portrait": 390.0, "landscape": 844.0}}
    return full[device_class][orientation]

def preflight(udid, bundle_id, orientation):
    import importlib.util, pathlib
    s = importlib.util.spec_from_file_location("coords", pathlib.Path(__file__).resolve().parent / "coords.py")
    coords = importlib.util.module_from_spec(s); s.loader.exec_module(coords)
    resolve_tool("idb")
    _terminate(udid, bundle_id)
    _set_orientation(udid, orientation)
    _launch(udid, bundle_id)
    elems = _settle_orientation(udid, orientation)
    app = _app_element(elems)
    f = app.get("frame") or {}
    point_w, point_h = float(f.get("width", 0)), float(f.get("height", 0))
    dc = device_class(udid)
    expected_w = _device_full_width(dc, orientation)
    if abs(point_w - expected_w) > 0.05 * expected_w:
        raise PreflightError(f"baseline width {point_w} != device full-width {expected_w}; not fullscreen")
    sa = coords.derive_insets(elems, point_w, point_h)
    source = "derived"
    if sa is None:
        sa = coords.table_insets(dc, orientation, point_w, point_h)
        source = "table"
    return {"udid": udid, "bundle_id": bundle_id, "platform": "ios",
            "orientation": orientation, "device_class": dc,
            "safe_area": sa, "safe_area_source": source, "baseline_full_width": point_w}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_preflight.py -k "preflight_builds or baseline_mismatch" -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/preflight.py tests/unit/computer_use/test_preflight.py
git commit -m "feat(phase2): preflight sets orientation, validates fullscreen baseline, builds SafeArea"
```

---

### Task 7: `cli.py` wiring (`--orientation`, `env["safe_area"]`, foreground closure)

**Files:**
- Modify: `scripts/computer_use/cli.py`
- Test: `tests/unit/computer_use/test_cli.py`

**Interfaces:**
- Consumes: `preflight.preflight(udid, bundle, orientation)` env dict; `preflight.is_app_foreground(udid, bundle, baseline_full_width)`.
- Produces: CLI with `--orientation {portrait,landscape}` (default `portrait`); both dry-run and main paths use `env["safe_area"]`; foreground closure passes `baseline_full_width`.

- [ ] **Step 1: Write the failing test**

```python
# test_cli.py
from computer_use import cli

def test_parse_args_orientation_default():
    a = cli.parse_args(["--udid", "U", "--bundle", "B", "explore"])
    assert a.orientation == "portrait"

def test_parse_args_orientation_landscape():
    a = cli.parse_args(["--udid", "U", "--bundle", "B", "--orientation", "landscape", "explore"])
    assert a.orientation == "landscape"

def test_no_hardcoded_insets():
    import inspect
    src = inspect.getsource(cli)
    assert "TOP_INSET" not in src and "BOTTOM_INSET" not in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_cli.py -k "orientation or hardcoded" -v`
Expected: FAIL — no `--orientation`; `TOP_INSET`/`BOTTOM_INSET` still present.

- [ ] **Step 3: Write minimal implementation**

In `parse_args`, add:
```python
    p.add_argument("--orientation", choices=["portrait", "landscape"], default="portrait")
```
Remove the `TOP_INSET`/`BOTTOM_INSET` constants. In both the dry-run and main paths, replace the `SafeArea(...)` construction with the preflight-built area, and pass orientation:
```python
    # dry-run path
    env = preflight.preflight(args.udid, args.bundle, args.orientation)
    executor = executor_idb.IdbExecutor(args.udid)
    safe = env["safe_area"]
    ...
    # main path
    env = preflight.preflight(args.udid, args.bundle, args.orientation)
    executor = executor_idb.IdbExecutor(args.udid)
    safe = env["safe_area"]
    client = gemini.ComputerUseClient()
    result = loop.run(args.mission, executor, client, max_steps=args.max_steps,
                      safe_area=safe, screenshot_dir=str(shots),
                      foreground_check=lambda: preflight.is_app_foreground(
                          args.udid, args.bundle, env["baseline_full_width"]))
```
Keep the existing default-env-before-setup pattern (F1) but seed it with `orientation`/`safe_area_source` keys so the report never KeyErrors on abnormal failure.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_cli.py -v`
Expected: PASS (all, including the pre-existing journal_to_action_log tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/cli.py tests/unit/computer_use/test_cli.py
git commit -m "feat(phase2): cli --orientation, preflight-built safe_area, baseline_full_width closure"
```

---

### Task 8: `report.py` env display (orientation / device_class / safe_area_source)

**Files:**
- Modify: `scripts/computer_use/report.py`
- Test: `tests/unit/computer_use/test_report.py`

**Interfaces:**
- Consumes: `env` dict with `orientation`, `device_class`, `safe_area_source` (no raw elems).
- Produces: `build_markdown` env section renders the three new fields.

- [ ] **Step 1: Write the failing test**

```python
# test_report.py
from computer_use import report

def test_report_shows_orientation_and_source():
    env = {"udid": "U", "bundle_id": "com.x.app", "platform": "ios",
           "orientation": "landscape", "device_class": "ipad", "safe_area_source": "table"}
    md = report.build_markdown("explore", env, [], [], "completed")
    assert "landscape" in md and "ipad" in md and "table" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/computer_use/test_report.py -k orientation -v`
Expected: FAIL — env section omits the new fields.

- [ ] **Step 3: Write minimal implementation**

`report.py` has no separate environment section — it is a single `**Miljø:**` line (report.py:10). Extend that line (keep `_s()` + `.get()` so older env dicts still render):
```python
             f"**Miljø:** {_s(env.get('platform'))} / UDID {_s(env.get('udid'))} / {_s(env.get('bundle_id'))} "
             f"/ {_s(env.get('orientation'))} / {_s(env.get('device_class'))} / safe-area: {_s(env.get('safe_area_source'))}",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/computer_use/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/computer_use/report.py tests/unit/computer_use/test_report.py
git commit -m "feat(phase2): report shows orientation, device_class, safe_area_source"
```

---

### Task 9: SKILL.md docs (iPad support, --orientation, known limits)

**Files:**
- Modify: `skills/ios-visual-explore/SKILL.md`

**Interfaces:**
- Consumes: nothing (docs).
- Produces: documented iPad usage + the honest best-effort limits (split-view best-effort, Slide-Over-target-frontmost hole, home-exit-undetected-if-S2-downgraded, sim stays in chosen orientation).

- [ ] **Step 1: Update SKILL.md**

Add an iPad section: `--orientation portrait|landscape`, fullscreen-only (no split/Stage Manager exploration), and a "Known limitations" block covering R-iPad-3 (Slide Over with target still frontmost), R-iPad-6 (sim orientation persists after run), and the S2-downgrade case if the spike downgraded it. Remove the Phase-1 "iPad deferred" note.

- [ ] **Step 2: Commit**

```bash
git add skills/ios-visual-explore/SKILL.md
git commit -m "docs(phase2): document iPad support, --orientation, best-effort limits"
```

---

### Task 10: Full unit-suite green + iPhone-portrait regression check

**Files:**
- Test: `tests/unit/computer_use/` (all)

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a green suite + an explicit assertion that iPhone-portrait behavior via the new path matches (or is a documented improvement over) the old hardcoded `(0, 50, w, h-40)`.

- [ ] **Step 1: Write the regression test**

```python
# test_coords.py
def test_iphone_portrait_regression_vs_phase1():
    # Phase-1 hardcoded: SafeArea(0, 50, w, h-40). New table path for iphone_notch portrait.
    sa = coords.table_insets("iphone_notch", "portrait", 390.0, 844.0)
    # document the new values; assert they are within the same ballpark (top>=44, bottom>=20)
    assert sa.top >= 44 and (844.0 - sa.bottom) >= 20
```

- [ ] **Step 2: Run the full suite**

Run: `python3 -m pytest tests/unit/computer_use/ -q`
Expected: PASS (43 Phase-1 tests + all new Phase-2 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/computer_use/test_coords.py
git commit -m "test(phase2): iPhone-portrait regression vs Phase-1 hardcoded insets"
```

---

### Task 11: Live smoke (iPad portrait + landscape) + iPhone regression smoke

**Files:**
- No code; produces run artifacts under `computer-use-runs/`.

**Interfaces:**
- Consumes: a booted iPad sim + the Phase-1 iPhone sim, each with a simple SwiftUI app.
- Produces: three reports verifying end-to-end behavior on the new path.

- [ ] **Step 1: iPad portrait smoke**

```bash
./scripts/ios-visual-explore --udid <IPAD_UDID> --bundle <BUNDLE> --orientation portrait "Explore the main screen and report visual issues"
```
Expected: exit 0, `report.md` written, `safe_area_source` logged, screenshots persisted, text-only summary (no inline images).

- [ ] **Step 2: iPad landscape smoke**

```bash
./scripts/ios-visual-explore --udid <IPAD_UDID> --bundle <BUNDLE> --orientation landscape "Explore the main screen and report visual issues"
```
Expected: exit 0, landscape safe-area applied (side insets), report written.

- [ ] **Step 3: iPhone-portrait regression smoke**

```bash
./scripts/ios-visual-explore --udid 4FA4A85E-E97F-41BA-A3A7-1ED5FB2574F2 --bundle <BUNDLE> --orientation portrait "Explore the main screen"
```
Expected: behavior unchanged from Phase 1 (exit 0, report written, no regression in tap targeting).

- [ ] **Step 4: Record results**

Note the three runs (status, safe_area_source, any oracle aborts) in the PR description. No commit (artifacts are gitignored under `computer-use-runs/`).

---

## Self-Review

**Spec coverage:** §2 mål (iPad fullscreen, --orientation, device/orientation safe-area, oracle, smoke) → Tasks 2–11. §3 SPIKE S1–S7 → Task 1 (gate). §4 component changes → coords (T2/T3), preflight (T4/T5/T6), cli (T7), report (T8), SKILL.md (T9); loop/gemini explicitly untouched (Global Constraints). §5 testing → unit tests folded into each task + T10/T11. §6 risks → R-iPad-1 (T2 fallback), R-iPad-3 (T9 docs), R-iPad-5 (T10 regression), R-iPad-6 (T9 docs), R-iPad-7 (T6 baseline validation). All covered.

**Placeholder scan:** the spike-captured fixtures in T1/T3 are explicitly flagged as "replace with real dump" — that is a spike deliverable, not a code placeholder. All other steps carry real code.

**Type consistency:** `is_app_foreground(udid, bundle_id, baseline_full_width)` consistent across T5, T6, T7. `device_class(udid) -> str` consistent T4→T6. `derive_insets(...) -> SafeArea | None` consistent T3→T6. `preflight(...) -> env` keys (`safe_area`, `baseline_full_width`, `safe_area_source`) consistent T6→T7→T8. `table_insets`/`INSET_TABLE` consistent T2→T6.
