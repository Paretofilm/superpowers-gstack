import json
import os
import shutil
import struct
import subprocess
import tempfile
import time

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


SETTLE_ATTEMPTS = 8
SETTLE_DELAY = 2.0


def _describe_all_raw(udid):
    out = subprocess.run(["idb", "ui", "describe-all", "--udid", udid],
                         capture_output=True, text=True, timeout=30).stdout
    elems = json.loads(out)
    if not isinstance(elems, list):
        raise ValueError("describe-all did not return a list")
    return elems


def _describe_all_settled(udid, attempts=SETTLE_ATTEMPTS, delay=SETTLE_DELAY):
    """iPad describe-all returns a degenerate tree during transitions (SPIKE Fase 2).
    Retry until the tree has >3 typed elements; raise PreflightError if it never settles."""
    last = []
    for i in range(attempts):
        try:
            last = _describe_all_raw(udid)
        except (subprocess.TimeoutExpired, ValueError, json.JSONDecodeError):
            last = []
        if sum(1 for e in last if e.get("type")) > 3:
            return last
        if i < attempts - 1:
            time.sleep(delay)
    raise PreflightError(f"describe-all never settled (>3 typed elems) after {attempts} attempts")


def _app_element(elems):
    return next((e for e in elems if e.get("type") == "Application"), None)


def is_app_foreground(udid, baseline_app_label, baseline_full_width):
    """S7 oracle: target app is frontmost AND fullscreen, via AXLabel self-reference.
    AXLabel-mismatch subsumes home detection (home label != target). Fail-closed to False."""
    try:
        elems = _describe_all_settled(udid)
    except PreflightError:
        return False
    app = _app_element(elems)
    if app is None:
        return False
    label = app.get("AXLabel")
    if label is None or label != baseline_app_label:
        return False
    width = float((app.get("frame") or {}).get("width", 0))
    return width >= 0.95 * baseline_full_width


def _terminate(udid, bundle_id):
    subprocess.run(["xcrun", "simctl", "terminate", udid, bundle_id],
                   capture_output=True, timeout=15)  # ok if not running


def _launch(udid, bundle_id):
    subprocess.run(["xcrun", "simctl", "launch", udid, bundle_id], check=True, timeout=30)


def _frame_matches_orientation(app, orientation):
    f = app.get("frame") or {}
    w, h = float(f.get("width", 0)), float(f.get("height", 0))
    return (w >= h) if orientation == "landscape" else (h >= w)


def _screenshot_dims(udid):
    """Full-screen screenshot (width, height) in pixels via PNG IHDR header (stdlib only, no Pillow)."""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        subprocess.run(["xcrun", "simctl", "io", udid, "screenshot", path],
                       capture_output=True, check=True, timeout=30)
        with open(path, "rb") as f:
            head = f.read(24)
    finally:
        os.unlink(path)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise PreflightError("screenshot is not a PNG")
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def _validate_fullscreen(point_w, point_h, shot_w_px, shot_h_px):
    """S6: app is fullscreen iff the screenshot matches the Application frame at the SAME clean
    @2x/@3x backing scale on BOTH axes.

    Compares SORTED dimensions so the check is robust to whether simctl rotates the screenshot
    buffer to match landscape UI (it may capture the native-portrait buffer instead — unverified
    across Xcode versions). Requiring ONE shared integer scale across both axes also rejects a
    split-view / Stage-Manager window whose narrow frame coincidentally aligns on a single axis
    (e.g. a 556pt window on @2x: short-axis 3x but long-axis 2x -> not uniform -> rejected)."""
    fp = sorted((float(point_w), float(point_h)))
    sp = sorted((float(shot_w_px), float(shot_h_px)))
    if fp[0] <= 0:
        raise PreflightError("Application frame has zero dimension")
    nearest = round(sp[1] / fp[1])  # long-axis scale is the reference
    if nearest not in (2, 3) or any(abs(s / p - nearest) > 0.02 for s, p in zip(sp, fp)):
        raise PreflightError(
            f"app not fullscreen: screenshot {sp[0]:.0f}x{sp[1]:.0f}px vs frame "
            f"{fp[0]:.0f}x{fp[1]:.0f}pt is not a uniform @2x/@3x backing scale "
            f"(split view / Stage Manager? make the app fullscreen)")
    return nearest


def _load_coords():
    import importlib.util, pathlib
    p = pathlib.Path(__file__).resolve().parent / "coords.py"
    s = importlib.util.spec_from_file_location("computer_use_coords", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def preflight(udid, bundle_id, orientation):
    """Terminate -> launch -> settle -> verify orientation (operator-set, S5) ->
    validate fullscreen via screenshot/scale (S6) -> capture baseline -> build SafeArea from table (S1)."""
    coords = _load_coords()
    resolve_tool("idb")
    _terminate(udid, bundle_id)
    _launch(udid, bundle_id)
    elems = _describe_all_settled(udid)
    app = _app_element(elems)
    if app is None:
        raise PreflightError("no Application element after launch/settle")
    if not _frame_matches_orientation(app, orientation):
        raise PreflightError(
            f"Application frame does not match '{orientation}'. "
            f"Rotate the sim to {orientation} first (Simulator.app: Cmd+Left/Right), then re-run.")
    label = app.get("AXLabel")
    if label is None:
        raise PreflightError("Application has no AXLabel; cannot establish foreground oracle reference")
    f = app.get("frame") or {}
    point_w, point_h = float(f.get("width", 0)), float(f.get("height", 0))
    shot_w, shot_h = _screenshot_dims(udid)
    _validate_fullscreen(point_w, point_h, shot_w, shot_h)
    dc = device_class(udid)
    sa = coords.table_insets(dc, orientation, point_w, point_h)
    return {"udid": udid, "bundle_id": bundle_id, "platform": "ios",
            "orientation": orientation, "device_class": dc,
            "safe_area": sa, "safe_area_source": "table",
            "baseline_full_width": point_w, "baseline_app_label": label}


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
    # Dynamic Island debuted on iPhone 14 Pro; allowlist by generation.
    # NOTE: "pro-max" omitted on purpose — it false-matches notch 11/12/13 Pro Max,
    # and every island Pro Max is already caught by its iphone-1N / iphone-14-pro prefix.
    if any(m in tid for m in ("iphone-15", "iphone-16", "iphone-17", "iphone-14-pro", "iphone-air")):
        return "iphone_island"
    if "iphone" in tid:
        return "iphone_notch"
    raise PreflightError(f"Unknown device type '{tid}' for {udid}; add it to device_class()")
