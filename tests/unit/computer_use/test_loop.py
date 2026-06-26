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
    def coordinate_space(self): return (402.0, 874.0)   # punkt-dims, ingen scale
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
    assert out["status"] == "fullført"


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
