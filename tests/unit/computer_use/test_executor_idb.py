import json
from test_smoke import load
ex = load("executor_idb")


def ex_point(x, y):
    coords = load("coords")
    return coords.Point(x, y)


def test_run_surfaces_stderr_on_failure(monkeypatch):
    # A non-zero idb exit must raise with stderr included so the model can self-correct;
    # the default CalledProcessError hides stderr ("returned non-zero exit status 1").
    class R:
        returncode = 1
        stdout = b""
        stderr = b"element not found: foo"
    monkeypatch.setattr(ex.subprocess, "run", lambda *a, **k: R())
    e = ex.IdbExecutor("UDID-1")
    try:
        e._run(["idb", "ui", "tap", "1", "2"])
        assert False, "should have raised"
    except Exception as exc:
        assert "element not found: foo" in str(exc), f"stderr must surface, got {exc!r}"


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


def test_long_press_is_zero_length_swipe_with_duration(monkeypatch):
    calls = []
    monkeypatch.setattr(ex.IdbExecutor, "_run", lambda self, args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1")
    e.long_press(ex_point(300.0, 500.0))
    args = calls[-1]
    assert "swipe" in args and "--duration" in args
    # same start and end point (a press, not a drag)
    assert args.count("300") == 2 and args.count("500") == 2


def test_go_back_edge_swipes_from_left(monkeypatch):
    calls = []
    monkeypatch.setattr(ex.IdbExecutor, "_run", lambda self, args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1")
    e.go_back(402.0, 874.0)
    args = calls[-1]
    assert "swipe" in args
    # starts at (or near) the left edge and moves right, mid-height
    sx = float(args[args.index("swipe") + 1])
    ex_x = float(args[args.index("swipe") + 3])
    assert sx <= 2 and ex_x > sx, "go_back must be a left-edge swipe moving inward"


def test_press_key_maps_known_name_to_hid(monkeypatch):
    calls = []
    monkeypatch.setattr(ex.IdbExecutor, "_run", lambda self, args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1")
    e.press_key("Return")
    args = calls[-1]
    assert "key" in args and "40" in args  # HID usage id for Return/Enter


def test_press_key_passes_numeric_keycode(monkeypatch):
    calls = []
    monkeypatch.setattr(ex.IdbExecutor, "_run", lambda self, args: calls.append(args) or b"")
    e = ex.IdbExecutor("UDID-1")
    e.press_key(42)
    assert "42" in calls[-1]


def test_press_key_unknown_name_raises(monkeypatch):
    monkeypatch.setattr(ex.IdbExecutor, "_run", lambda self, args: b"")
    e = ex.IdbExecutor("UDID-1")
    try:
        e.press_key("Nonsense")
        assert False, "unknown key name should raise (loop marks it failed)"
    except ValueError:
        pass


def test_coordinate_space_reads_point_frame(monkeypatch):
    app = [{"type": "Application", "frame": {"x": 0, "y": 0, "width": 402, "height": 874}}]
    monkeypatch.setattr(ex.IdbExecutor, "_run",
                        lambda self, a: json.dumps(app).encode() if "describe-all" in a else b"")
    e = ex.IdbExecutor("UDID-1")
    pw, ph = e.coordinate_space()
    assert pw == 402.0 and ph == 874.0


def test_coordinate_space_retries_on_degenerate_tree(monkeypatch):
    # iPad describe-all can be degenerate (no Application) right after a transition; coordinate_space
    # must settle-retry (SPIKE: applies to ALL describe-all calls) instead of crashing on the first.
    app = [{"type": "Application", "frame": {"x": 0, "y": 0, "width": 402, "height": 874}},
           {"type": "Button"}, {"type": "Cell"}, {"type": "StaticText"}, {"type": "Image"}]
    degenerate = [{"type": "DockFolderViewService"}]
    seq = [degenerate, degenerate, app]
    calls = {"n": 0}

    def fake_run(self, a):
        if "describe-all" in a:
            r = seq[min(calls["n"], len(seq) - 1)]
            calls["n"] += 1
            return json.dumps(r).encode()
        return b""
    monkeypatch.setattr(ex.IdbExecutor, "_run", fake_run)
    monkeypatch.setattr(ex.time, "sleep", lambda s: None)
    e = ex.IdbExecutor("UDID-1")
    pw, ph = e.coordinate_space()
    assert (pw, ph) == (402.0, 874.0)
    assert calls["n"] == 3  # retried past the two degenerate trees


def test_coordinate_space_raises_after_settle_budget(monkeypatch):
    monkeypatch.setattr(ex.IdbExecutor, "_run",
                        lambda self, a: json.dumps([{"type": "DockFolderViewService"}]).encode())
    monkeypatch.setattr(ex.time, "sleep", lambda s: None)
    e = ex.IdbExecutor("UDID-1")
    try:
        e.coordinate_space()
        assert False, "should have raised"
    except ValueError:
        pass


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
