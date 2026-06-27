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


def _elems(ax_label, width):
    return [{"type": "Application", "AXLabel": ax_label,
             "frame": {"x": 0, "y": 0, "width": width, "height": 1180}},
            {"type": "Button"}, {"type": "StaticText"},
            {"type": "Cell"}, {"type": "Image"}]


def test_foreground_true_when_target_fullscreen(monkeypatch):
    monkeypatch.setattr(pf, "_describe_all_settled", lambda udid: _elems("Innstillinger", 834))
    assert pf.is_app_foreground("U", "Innstillinger", 834.0) is True


def test_foreground_false_when_other_app_frontmost(monkeypatch):
    monkeypatch.setattr(pf, "_describe_all_settled", lambda udid: _elems("Safari", 834))
    assert pf.is_app_foreground("U", "Innstillinger", 834.0) is False


def test_foreground_false_when_split_narrow(monkeypatch):
    monkeypatch.setattr(pf, "_describe_all_settled", lambda udid: _elems("Innstillinger", 500))
    assert pf.is_app_foreground("U", "Innstillinger", 834.0) is False


def test_foreground_false_when_axlabel_none(monkeypatch):
    # caveat: AXLabel can be None for some apps -> cannot self-reference -> fail-closed False
    monkeypatch.setattr(pf, "_describe_all_settled", lambda udid: _elems(None, 834))
    assert pf.is_app_foreground("U", "Innstillinger", 834.0) is False


def test_foreground_false_when_never_settles(monkeypatch):
    def boom(udid):
        raise pf.PreflightError("never settled")
    monkeypatch.setattr(pf, "_describe_all_settled", boom)
    assert pf.is_app_foreground("U", "Innstillinger", 834.0) is False


def test_describe_all_settled_retries_until_stable(monkeypatch):
    calls = {"n": 0}
    def fake_raw(udid):
        calls["n"] += 1
        if calls["n"] < 3:
            return [{"type": "Application"}]          # degenerate: 1 typed elem
        return _elems("Innstillinger", 834)           # stable: >3 typed elems
    monkeypatch.setattr(pf, "_describe_all_raw", fake_raw)
    monkeypatch.setattr(pf.time, "sleep", lambda s: None)
    out = pf._describe_all_settled("U")
    assert calls["n"] == 3
    assert any(e.get("type") == "Application" for e in out)


def test_describe_all_settled_raises_when_never_stable(monkeypatch):
    monkeypatch.setattr(pf, "_describe_all_raw", lambda udid: [{"type": "Application"}])
    monkeypatch.setattr(pf.time, "sleep", lambda s: None)
    with pytest.raises(pf.PreflightError):
        pf._describe_all_settled("U", attempts=3, delay=0)


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
