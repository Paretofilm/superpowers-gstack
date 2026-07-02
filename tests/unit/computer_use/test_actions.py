from test_smoke import load
actions = load("actions")


def test_click_maps_to_tap():
    # SPIKE-verifisert nested form
    a = actions.adapt({"name": "click",
                       "arguments": {"x": 450, "y": 365, "intent": "tap row"}})
    assert a.kind == "tap"
    assert a.params["x"] == 450 and a.params["y"] == 365


def test_drag_and_drop_maps_to_swipe_two_points():
    # SPIKE runde-2: scroll kommer som drag_and_drop med start/end
    a = actions.adapt({"name": "drag_and_drop",
                       "arguments": {"start_x": 500, "start_y": 800,
                                     "end_x": 500, "end_y": 200}})
    assert a.kind == "swipe"
    assert a.params["start_x"] == 500 and a.params["start_y"] == 800
    assert a.params["end_x"] == 500 and a.params["end_y"] == 200


def test_scroll_derives_swipe_endpoints():
    # 'scroll down' => innhold nedover => finger opp => end_y < start_y
    a = actions.adapt({"name": "scroll",
                       "arguments": {"x": 500, "y": 500, "direction": "down"}})
    assert a.kind == "swipe"
    assert a.params["end_y"] < a.params["start_y"]
    # klampet til [0,1000]
    assert 0 <= a.params["end_y"] <= 1000 and 0 <= a.params["start_y"] <= 1000


def test_scroll_direction_is_case_insensitive():
    # LLMs frequently capitalize ('Down'/'DOWN'); a case-sensitive lookup would give a
    # zero-length no-op swipe that reports success and can loop. Normalize the direction.
    for d in ("Down", "DOWN", " down "):
        a = actions.adapt({"name": "scroll", "arguments": {"x": 500, "y": 500, "direction": d}})
        assert a.params["end_y"] < a.params["start_y"], f"direction {d!r} should scroll down"
    a = actions.adapt({"name": "scroll", "arguments": {"x": 500, "y": 500, "direction": "Right"}})
    assert a.params["end_x"] < a.params["start_x"], "Right should produce a non-zero horizontal swipe"


def test_type_passthrough():
    a = actions.adapt({"name": "type", "arguments": {"text": "hei"}})
    assert a.kind == "type" and a.params["text"] == "hei"


def test_wait_is_noop():
    a = actions.adapt({"name": "wait", "arguments": {}})
    assert a.kind == "wait"


def test_unknown_is_unsupported():
    a = actions.adapt({"name": "teleport", "arguments": {}})
    assert a.kind == "unsupported"


def test_press_key_is_unsupported():
    """F8: press_key is phase-2-deferred; must be rejected as unsupported, not silently no-op'd."""
    a = actions.adapt({"name": "press_key", "arguments": {"key": "Return"}})
    assert a.kind == "unsupported", (
        f"press_key should be 'unsupported', got {a.kind!r}")
