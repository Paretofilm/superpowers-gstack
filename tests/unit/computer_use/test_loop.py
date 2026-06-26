from test_smoke import load
loop = load("loop")


def _turn(action, done):
    return load("loop").Turn(action=action, done=done)


def _safe():
    return load("coords").SafeArea(0, 0, 402, 874)


class FakeExec:
    def __init__(self):
        self.taps = []
        self.swipes = []
    def screenshot(self): return b"PNG"
    def coordinate_space(self): return (402.0, 874.0)   # point dims, no scale
    def tap(self, p): self.taps.append(p)
    def swipe(self, start, end): self.swipes.append((start, end))
    def type_text(self, t): pass


class TapThenDone:
    def __init__(self): self.results = []
    def start(self, mission, shot):
        return _turn({"name": "click", "arguments": {"x": 500, "y": 500}}, False)
    def respond(self, kind, shot, reason):
        self.results.append(kind)
        return _turn(None, True)


def test_loop_executes_tap_then_sends_result_and_journals():
    ex, cl = FakeExec(), TapThenDone()
    out = loop.run("utforsk", ex, cl, max_steps=5, safe_area=_safe())
    assert ex.taps, "tap skulle blitt utført"
    assert cl.results == ["success"], "function_result måtte sendes etter handling"
    assert out["journal"][0]["state"] == "result_sent"
    assert out["status"] == "completed"


class DragThenDone:
    def __init__(self): self.results = []
    def start(self, mission, shot):
        return _turn({"name": "drag_and_drop",
                      "arguments": {"start_x": 500, "start_y": 800,
                                    "end_x": 500, "end_y": 200}}, False)
    def respond(self, kind, shot, reason):
        self.results.append(kind); return _turn(None, True)


def test_drag_and_drop_swipes_two_points():
    ex, cl = FakeExec(), DragThenDone()
    loop.run("scroll", ex, cl, max_steps=5, safe_area=_safe())
    assert ex.swipes, "swipe skulle blitt utført med to punkter"
    start, end = ex.swipes[0]
    assert end.y < start.y   # 'scroll ned' => end_y < start_y


class TapOutOfBounds:
    def __init__(self): self.results = []
    def start(self, mission, shot):
        return _turn({"name": "click", "arguments": {"x": 500, "y": 5}}, False)
    def respond(self, kind, shot, reason):
        self.results.append(kind); return _turn(None, True)


def test_out_of_safe_area_is_rejected_not_executed():
    safe = load("coords").SafeArea(0, 60, 402, 800)  # y=5 -> 4.4pt, over top=60
    ex, cl = FakeExec(), TapOutOfBounds()
    loop.run("x", ex, cl, max_steps=5, safe_area=safe)
    assert not ex.taps, "utenfor safe-area skulle IKKE tappes"
    assert cl.results == ["rejected"]


def test_screenshot_persistence(tmp_path):
    import pathlib
    ex, cl = FakeExec(), TapThenDone()
    out = loop.run("utforsk", ex, cl, max_steps=5, safe_area=_safe(),
                   screenshot_dir=tmp_path)

    # baseline screenshot (index 0) must exist
    baseline = out["baseline_screenshot"]
    assert baseline is not None, "baseline_screenshot should be set"
    assert pathlib.Path(baseline).exists(), "shot_000.png should exist on disk"
    assert pathlib.Path(baseline).name == "shot_000.png"

    # post-action screenshot for step 1 must exist
    shot_001 = tmp_path / "shot_001.png"
    assert shot_001.exists(), "shot_001.png should exist after one executed step"

    # journal entry for step 1 must carry a screenshot path pointing to an existing file
    step_entry = out["journal"][0]
    assert "screenshot" in step_entry, "journal entry must have 'screenshot' key"
    assert step_entry["screenshot"] is not None
    assert pathlib.Path(step_entry["screenshot"]).exists()


class TapThenContinue:
    """Client that always requests another tap (never done), used for foreground-check test."""
    def __init__(self): self.calls = 0
    def start(self, mission, shot):
        return _turn({"name": "click", "arguments": {"x": 200, "y": 400}}, False)
    def respond(self, kind, shot, reason):
        self.calls += 1
        return _turn({"name": "click", "arguments": {"x": 200, "y": 400}}, False)


def test_foreground_check_breaks_loop_with_app_left_foreground():
    """foreground_check returning False after the first action stops the run with
    status == 'app_left_foreground' and the step's result is 'app_left_foreground'."""
    ex = FakeExec()
    cl = TapThenContinue()
    call_count = [0]

    def fg_check():
        call_count[0] += 1
        # Return False after the first foreground check (i.e. after first action)
        return call_count[0] < 1

    out = loop.run("explore", ex, cl, max_steps=10, safe_area=_safe(),
                   foreground_check=fg_check)

    assert out["status"] == "app_left_foreground", (
        f"Expected 'app_left_foreground', got {out['status']!r}")
    assert len(out["journal"]) >= 1, "should have at least one journal entry"
    last_entry = out["journal"][-1]
    assert last_entry.get("result") == "app_left_foreground", (
        f"Last journal entry result should be 'app_left_foreground', got {last_entry.get('result')!r}")
