from test_smoke import load
gemini = load("gemini")

PATHS = ["a/shot_000.png", "a/shot_001.png", "a/shot_002.png"]


def test_resolve_int_index():
    assert gemini._resolve_screenshot(2, PATHS) == "a/shot_001.png"


def test_resolve_string_index():
    assert gemini._resolve_screenshot("2", PATHS) == "a/shot_001.png"


def test_resolve_bilde_prefix():
    # the critic prompt asks it to reference the image number -> "Bilde 3" must map, not leak through
    assert gemini._resolve_screenshot("Bilde 3", PATHS) == "a/shot_002.png"


def test_resolve_already_a_path_passes_through():
    # a path with its own digits (timestamp) must NOT be reindexed
    assert gemini._resolve_screenshot("runs/123456/shot_002.png", PATHS) == "runs/123456/shot_002.png"


def test_resolve_out_of_range_falls_back():
    assert gemini._resolve_screenshot(99, PATHS) == "99"
    assert gemini._resolve_screenshot(None, PATHS) == ""
