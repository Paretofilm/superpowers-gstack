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


def test_device_class_ipad(monkeypatch):
    monkeypatch.setattr(pf, "_device_type_id", lambda udid: "com.apple.CoreSimulator.SimDeviceType.iPad-Pro-11-inch")
    assert pf.device_class("X") == "ipad"


def test_device_class_unknown_fails_closed(monkeypatch):
    monkeypatch.setattr(pf, "_device_type_id", lambda udid: "com.apple.CoreSimulator.SimDeviceType.Apple-Watch")
    with pytest.raises(pf.PreflightError):
        pf.device_class("X")


def test_device_class_pro_max_pre14_is_notch(monkeypatch):
    # iPhone 11/12/13 Pro Max har notch, ikke Dynamic Island (debut: 14 Pro)
    monkeypatch.setattr(pf, "_device_type_id",
                        lambda udid: "com.apple.CoreSimulator.SimDeviceType.iPhone-13-Pro-Max")
    assert pf.device_class("X") == "iphone_notch"


def test_device_class_iphone_air_is_island(monkeypatch):
    # iPhone Air har Dynamic Island
    monkeypatch.setattr(pf, "_device_type_id",
                        lambda udid: "com.apple.CoreSimulator.SimDeviceType.iPhone-Air")
    assert pf.device_class("X") == "iphone_island"


def test_device_class_iphone_17_pro_max_is_island(monkeypatch):
    # regresjon: ekte island-Pro-Max fanges fortsatt (via iphone-17-prefix), ikke pro-max-substring
    monkeypatch.setattr(pf, "_device_type_id",
                        lambda udid: "com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro-Max")
    assert pf.device_class("X") == "iphone_island"
