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
    e.swipe(ex_point(200.0, 700.0), ex_point(200.0, 300.0))
    args = calls[-1]
    assert "swipe" in args
    # begge endepunktene i kommandoen
    assert "200" in args and "700" in args and "300" in args


def test_coordinate_space_reads_point_frame(monkeypatch):
    app = [{"type": "Application", "frame": {"x": 0, "y": 0, "width": 402, "height": 874}}]
    monkeypatch.setattr(ex.IdbExecutor, "_run",
                        lambda self, a: json.dumps(app).encode() if "describe-all" in a else b"")
    e = ex.IdbExecutor("UDID-1")
    pw, ph = e.coordinate_space()
    assert pw == 402.0 and ph == 874.0
