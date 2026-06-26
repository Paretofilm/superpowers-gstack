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
