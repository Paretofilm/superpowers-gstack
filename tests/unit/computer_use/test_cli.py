from test_smoke import load
cli = load("cli")


def test_parse_args_minimal():
    ns = cli.parse_args(["--udid", "U1", "--bundle", "com.x", "utforsk onboarding"])
    assert ns.udid == "U1" and ns.bundle == "com.x" and ns.mission == "utforsk onboarding"
    assert ns.max_steps == 25


def test_dry_run_flag():
    ns = cli.parse_args(["--udid", "U1", "--bundle", "com.x", "--dry-run", "x"])
    assert ns.dry_run is True


def test_journal_to_action_log_click():
    """Test mapping click action with x,y coordinates."""
    j = [{"step": 1, "state": "result_sent", "result": "success",
          "raw": {"name": "click", "arguments": {"x": 450, "y": 365, "intent": "tap row"}},
          "screenshot": "/p/shot_001.png"}]
    log = cli.journal_to_action_log(j)
    assert len(log) == 1
    assert log[0]["action"] == "click"
    assert log[0]["intent"] == "tap row"
    assert log[0]["coord"] == "(450,365)"
    assert log[0]["result"] == "success"
    assert log[0]["step"] == 1
    assert log[0]["produced_by_steps"] == [1]
    assert log[0]["screenshot"] == "/p/shot_001.png"


def test_journal_to_action_log_swipe():
    """Test mapping swipe/drag action with start/end coordinates."""
    j = [{"step": 2, "state": "result_sent", "result": "success",
          "raw": {"name": "drag_and_drop",
                  "arguments": {"start_x": 500, "start_y": 800, "end_x": 500, "end_y": 200}},
          "screenshot": None}]
    log = cli.journal_to_action_log(j)
    assert len(log) == 1
    assert log[0]["action"] == "drag_and_drop"
    assert "->" in log[0]["coord"]
    assert "(500,800)" in log[0]["coord"]
    assert "(500,200)" in log[0]["coord"]
    assert log[0]["step"] == 2
    assert log[0]["produced_by_steps"] == [2]


def test_journal_to_action_log_scroll():
    """Test mapping scroll action without coordinates."""
    j = [{"step": 3, "state": "result_sent", "result": "success",
          "raw": {"name": "scroll", "arguments": {"direction": "down"}},
          "screenshot": "/p/shot_003.png"}]
    log = cli.journal_to_action_log(j)
    assert len(log) == 1
    assert log[0]["action"] == "scroll"
    assert log[0]["coord"] == "-"
    assert log[0]["result"] == "success"


def test_mapped_log_renders_markdown():
    """Test that mapped log can be rendered by report.build_markdown without KeyError."""
    rep = load("report")
    j = [{"step": 1, "state": "result_sent", "result": "success",
          "raw": {"name": "click", "arguments": {"x": 1, "y": 2, "intent": "test action"}},
          "screenshot": None}]
    action_log = cli.journal_to_action_log(j)
    md = rep.build_markdown("test mission", {"platform": "ios", "udid": "U1", "bundle_id": "com.x"},
                            action_log, [], "fullført")
    assert "test mission" in md
    assert "click" in md
    assert "test action" in md
