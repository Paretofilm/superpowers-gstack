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


def test_scroll_is_first_class_action():
    # scroll er nå en egen 'scroll'-action (loopen ruter til executor.scroll() på macOS, ELLER
    # faller tilbake til finger-drag-swipe via swipe_from_scroll() på iOS — se test under).
    a = actions.adapt({"name": "scroll",
                       "arguments": {"x": 500, "y": 500, "direction": "down"}})
    assert a.kind == "scroll"
    assert a.params == {"x": 500, "y": 500, "direction": "down"}


def test_scroll_direction_is_case_insensitive():
    # LLMs frequently capitalize ('Down'/'DOWN'); a case-sensitive lookup would give a
    # zero-length no-op that reports success and can loop. Normalize the direction.
    for d in ("Down", "DOWN", " down "):
        a = actions.adapt({"name": "scroll", "arguments": {"x": 500, "y": 500, "direction": d}})
        assert a.params["direction"] == "down", f"direction {d!r} should normalize to 'down'"


def test_swipe_from_scroll_ios_fallback_parity():
    # iOS/idb-fallback: swipe_from_scroll() må reprodusere den gamle scroll→swipe-atferden
    # byte-for-byte (loopen bruker denne når executoren IKKE har en scroll()-metode).
    # 'scroll down' => innhold nedover => finger opp => end_y < start_y.
    sp = actions.swipe_from_scroll(500, 500, "down")
    assert sp["end_y"] < sp["start_y"]
    assert 0 <= sp["end_y"] <= 1000 and 0 <= sp["start_y"] <= 1000
    right = actions.swipe_from_scroll(500, 500, "right")
    assert right["end_x"] < right["start_x"], "Right should produce a non-zero horizontal swipe"


def test_type_passthrough():
    a = actions.adapt({"name": "type", "arguments": {"text": "hei"}})
    assert a.kind == "type" and a.params["text"] == "hei"


def test_wait_is_noop():
    a = actions.adapt({"name": "wait", "arguments": {}})
    assert a.kind == "wait"


def test_unknown_is_unsupported():
    a = actions.adapt({"name": "teleport", "arguments": {}})
    assert a.kind == "unsupported"


def test_press_key_maps_to_press_key():
    a = actions.adapt({"name": "press_key", "arguments": {"key": "Return"}})
    assert a.kind == "press_key" and a.params["key"] == "Return"


def test_press_key_accepts_keys_list_form():
    # computer-use may send {"keys": [...]}; take the first
    a = actions.adapt({"name": "press_key", "arguments": {"keys": ["Escape"]}})
    assert a.kind == "press_key" and a.params["key"] == "Escape"


def test_press_key_without_a_key_is_unsupported():
    a = actions.adapt({"name": "press_key", "arguments": {}})
    assert a.kind == "unsupported"


def test_long_press_maps_to_long_press():
    a = actions.adapt({"name": "long_press", "arguments": {"x": 400, "y": 600, "intent": "hold"}})
    assert a.kind == "long_press" and a.params["x"] == 400 and a.params["y"] == 600


def test_go_back_maps_to_go_back():
    a = actions.adapt({"name": "go_back", "arguments": {}})
    assert a.kind == "go_back"
