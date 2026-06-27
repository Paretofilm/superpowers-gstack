import json
from test_smoke import load
ex = load("executor_idb")


def ex_point(x, y):
    coords = load("coords")
    return coords.Point(x, y)


def test_tap_builds_idb_command(monkeypatch):
    calls = []
    monkeypatch.setattr(ex.IdbExecutor, "_run", lambda self, args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1")
    e.tap(ex_point(195.0, 400.0))
    assert calls and "tap" in calls[-1]
    assert "195" in calls[-1] and "400" in calls[-1]
    assert "UDID-1" in calls[-1]


def test_swipe_builds_two_point_command(monkeypatch):
    calls = []
    monkeypatch.setattr(ex.IdbExecutor, "_run", lambda self, args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1")
    e.swipe(ex_point(200.0, 700.0), ex_point(250.0, 300.0))
    args = calls[-1]
    assert "swipe" in args
    # begge endepunktene i kommandoen — alle fire koordinater
    assert "200" in args and "700" in args and "250" in args and "300" in args


def test_coordinate_space_reads_point_frame(monkeypatch):
    app = [{"type": "Application", "frame": {"x": 0, "y": 0, "width": 402, "height": 874}}]
    monkeypatch.setattr(ex.IdbExecutor, "_run",
                        lambda self, a: json.dumps(app).encode() if "describe-all" in a else b"")
    e = ex.IdbExecutor("UDID-1")
    pw, ph = e.coordinate_space()
    assert pw == 402.0 and ph == 874.0


def test_screenshot_rotates_in_landscape(monkeypatch):
    # simctl captures the native-portrait buffer even in landscape UI; the executor must rotate
    # the PNG upright so the model sees the same orientation as the landscape Application frame.
    calls = []
    monkeypatch.setattr(ex.IdbExecutor, "_run", lambda self, args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1", orientation="landscape")
    e.screenshot()
    assert any("screenshot" in c for c in calls)
    assert any("sips" in c and "90" in c for c in calls), "landscape screenshot must be sips-rotated"


def test_screenshot_no_rotate_in_portrait(monkeypatch):
    calls = []
    monkeypatch.setattr(ex.IdbExecutor, "_run", lambda self, args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1")  # default portrait
    e.screenshot()
    assert any("screenshot" in c for c in calls)
    assert not any("sips" in c for c in calls), "portrait screenshot must NOT be rotated"


def test_type_text_builds_idb_command(monkeypatch):
    calls = []
    monkeypatch.setattr(ex.IdbExecutor, "_run", lambda self, args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1")
    e.type_text("hei")
    args = calls[-1]
    assert "text" in args
    assert "hei" in args
    assert "UDID-1" in args
