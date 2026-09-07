"""Layer 2 of the pin: the maintainer-machine alarm.

`spec-drift.py check` refuses at use time. This fires earlier — on any
`pytest tests/unit` run on a machine where gstack is installed — so a weekly
gstack auto-update that reshapes Step 8 is seen before anyone needs the skill.
Skipped in CI (no upstream there), like test_lint_upstream_skills' roster
check. Failing here is the designed outcome, not flakiness: read the diff with
`python3 scripts/spec-drift.py repin`, accept it with --yes, commit the pin.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "spec-drift.py"
UPSTREAM = (Path.home() / ".claude" / "skills" / "gstack"
            / "ship" / "sections" / "plan-completion.md")


def test_pin_matches_installed_gstack_when_present():
    if not UPSTREAM.is_file():
        pytest.skip("no gstack install on this machine (expected in CI)")
    p = subprocess.run([sys.executable, str(SCRIPT), "check"], capture_output=True, text=True)
    assert p.returncode == 0, (
        "upstream plan-completion.md no longer matches skills/spec-drift/pin.json — "
        "gstack updated Step 8. Review: python3 scripts/spec-drift.py repin ; accept: "
        "python3 scripts/spec-drift.py repin --yes ; then commit pin.json + pin/.\n" + p.stderr)
