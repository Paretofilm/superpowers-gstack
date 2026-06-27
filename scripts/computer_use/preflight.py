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
    # F3: timeout=10 for launchctl probe; timeout → treat as not-running (conservative)
    try:
        out = subprocess.run(["xcrun", "simctl", "spawn", udid, "launchctl", "list"],
                             capture_output=True, text=True, timeout=10).stdout
    except subprocess.TimeoutExpired:
        return False
    return f"UIKitApplication:{bundle_id}" in out


def _on_home_screen(udid: str) -> bool:
    # F3: timeout=30 for idb UI call; timeout → treat as not-home (conservative)
    try:
        out = subprocess.run(["idb", "ui", "describe-all", "--udid", udid],
                             capture_output=True, text=True, timeout=30).stdout
    except subprocess.TimeoutExpired:
        return False
    try:
        elems = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return False
    if not isinstance(elems, list):
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
