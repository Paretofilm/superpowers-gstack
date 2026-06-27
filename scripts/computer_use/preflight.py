import json
import shutil
import subprocess
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


def preflight(udid: str, bundle_id: str) -> dict:
    resolve_tool("idb")
    # F3: timeout=30 for simctl launch
    subprocess.run(["xcrun", "simctl", "launch", udid, bundle_id], check=True, timeout=30)
    return {"udid": udid, "bundle_id": bundle_id, "platform": "ios"}


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
