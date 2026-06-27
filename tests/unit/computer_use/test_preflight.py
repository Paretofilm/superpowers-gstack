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


def _ipad_app_elems(width=834, height=1210, label="Innstillinger"):
    return [{"type": "Application", "AXLabel": label,
             "frame": {"x": 0, "y": 0, "width": width, "height": height}},
            {"type": "Button"}, {"type": "Cell"}, {"type": "StaticText"}, {"type": "Image"}]


def _patch_preflight_happy(monkeypatch, elems, shot_dims, dc="ipad"):
    monkeypatch.setattr(pf, "resolve_tool", lambda n: "/bin/true")
    monkeypatch.setattr(pf, "_terminate", lambda u, b: None)
    monkeypatch.setattr(pf, "_launch", lambda u, b: None)
    monkeypatch.setattr(pf, "_describe_all_settled", lambda u: elems)
    monkeypatch.setattr(pf, "device_class", lambda u: dc)
    monkeypatch.setattr(pf, "_screenshot_dims", lambda u: shot_dims)


def test_preflight_builds_safe_area_and_strips_elems(monkeypatch):
    elems = _ipad_app_elems(834, 1210, "Innstillinger")
    _patch_preflight_happy(monkeypatch, elems, shot_dims=(1668, 2420))  # exact @2x both axes
    env = pf.preflight("U", "com.apple.Preferences", "portrait")
    assert env["safe_area_source"] == "table"
    assert env["baseline_full_width"] == 834.0
    assert env["baseline_app_label"] == "Innstillinger"
    assert env["device_class"] == "ipad"
    assert env["orientation"] == "portrait"
    assert "describe_all_elems" not in env
    assert env["safe_area"].top == 24
    assert env["safe_area"].bottom == 1210 - 20


def test_preflight_landscape_accepts_unrotated_screenshot(monkeypatch):
    # landscape app frame 1210x834; simctl may keep the native-portrait buffer 1668x2420.
    # sorted-dimension comparison must still accept it as fullscreen (@2x on both axes).
    elems = _ipad_app_elems(1210, 834, "Innstillinger")
    _patch_preflight_happy(monkeypatch, elems, shot_dims=(1668, 2420))
    env = pf.preflight("U", "com.apple.Preferences", "landscape")
    assert env["orientation"] == "landscape"
    assert env["baseline_full_width"] == 1210.0


def test_preflight_landscape_accepts_rotated_screenshot(monkeypatch):
    # same landscape app, but simctl DID rotate the screenshot to 2420x1668 -> must also pass
    elems = _ipad_app_elems(1210, 834, "Innstillinger")
    _patch_preflight_happy(monkeypatch, elems, shot_dims=(2420, 1668))
    env = pf.preflight("U", "com.apple.Preferences", "landscape")
    assert env["orientation"] == "landscape"


def test_preflight_fails_closed_on_wrong_orientation(monkeypatch):
    elems = _ipad_app_elems(834, 1210, "Innstillinger")  # h>w = portrait, but we ask landscape
    _patch_preflight_happy(monkeypatch, elems, shot_dims=(1668, 2420))
    with pytest.raises(pf.PreflightError):
        pf.preflight("U", "com.apple.Preferences", "landscape")


def test_preflight_fails_closed_on_non_fullscreen(monkeypatch):
    elems = _ipad_app_elems(500, 1210, "Innstillinger")  # split: short-axis 1668/500=3.336 not clean
    _patch_preflight_happy(monkeypatch, elems, shot_dims=(1668, 2420))
    with pytest.raises(pf.PreflightError):
        pf.preflight("U", "com.apple.Preferences", "portrait")


def test_preflight_fails_closed_on_stage_manager_one_aligned_axis(monkeypatch):
    # 556pt SM window on @2x: short-axis 1668/556=3.0 aligns, but long-axis 2420/1210=2.0 differs.
    # non-uniform scale -> rejected (the theoretical single-axis false-accept is closed).
    elems = _ipad_app_elems(556, 1210, "Innstillinger")
    _patch_preflight_happy(monkeypatch, elems, shot_dims=(1668, 2420))
    with pytest.raises(pf.PreflightError):
        pf.preflight("U", "com.apple.Preferences", "portrait")


def test_preflight_fails_closed_on_missing_axlabel(monkeypatch):
    elems = _ipad_app_elems(834, 1210, None)
    _patch_preflight_happy(monkeypatch, elems, shot_dims=(1668, 2420))
    with pytest.raises(pf.PreflightError):
        pf.preflight("U", "com.apple.Preferences", "portrait")
