from test_smoke import load
cli = load("cli")


def test_parse_args_minimal():
    ns = cli.parse_args(["--udid", "U1", "--bundle", "com.x", "utforsk onboarding"])
    assert ns.udid == "U1" and ns.bundle == "com.x" and ns.mission == "utforsk onboarding"
    assert ns.max_steps == 25


def test_dry_run_flag():
    ns = cli.parse_args(["--udid", "U1", "--bundle", "com.x", "--dry-run", "x"])
    assert ns.dry_run is True
