"""Guard scripts/spec-drift.py verdict — Step 8's JSON -> the standalone exit code.

/ship turns the audit into AskUserQuestion gates. Standalone there is nobody to
ask at a phase boundary; the exit code IS the gate, so its mapping cannot be a
judgement call the model makes differently on each run.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "spec-drift.py"


def verdict(text: str):
    p = subprocess.run([sys.executable, str(SCRIPT), "verdict"],
                       capture_output=True, text=True, input=text)
    return p.returncode, p.stdout + p.stderr


def step8(total, done, changed=0, deferred=0, unverifiable=0):
    return json.dumps({"total_items": total, "done": done, "changed": changed,
                       "deferred": deferred, "unverifiable": unverifiable,
                       "summary": "- [x] ..."})


@pytest.mark.parametrize("line,code,label", [
    (step8(4, 4), 0, "CLEAN"),
    (step8(4, 3, changed=1), 0, "CLEAN"),
    (step8(4, 3, deferred=1), 1, "DRIFT"),
    (step8(4, 3, unverifiable=1), 1, "DRIFT"),
    (step8(4, 3), 1, "DRIFT"),                 # the remainder is PARTIAL (D5)
    (step8(0, 0), 2, "COULD-NOT-RUN"),         # no actionable items (D6)
])
def test_mapping(line, code, label):
    rc, out = verdict("PLAN COMPLETION AUDIT\n...\n" + line + "\n")
    assert rc == code
    assert f"SPEC-DRIFT: {label} (exit {code})" in out


def test_partial_is_reported_in_the_breakdown():
    rc, out = verdict(step8(5, 2, changed=1, deferred=1))
    assert rc == 1 and "partial=1" in out and "not_done=1" in out


def test_only_the_last_line_counts():
    """A JSON-looking line mid-report must not be mistaken for the contract."""
    rc, _ = verdict(step8(2, 0) + "\n" + step8(2, 2) + "\n")
    assert rc == 0


def test_missing_or_malformed_json_is_could_not_run():
    for text in ("no json here\n", '{"total_items": 3}\n', "{not json}\n", ""):
        rc, out = verdict(text)
        assert rc == 2, text
        assert "COULD-NOT-RUN" in out


@pytest.mark.parametrize("line,why", [
    (step8(2, 2, changed=1), "three verdicts for two items"),
    (step8(2, 3, changed=-1), "a negative count that makes done+changed add up to total"),
    (step8(1, True), "a boolean where a count belongs (int(True) == 1)"),
    (step8(2, 1.9, changed=1), "a float that int() would truncate into a CLEAN"),
    (step8(2, "2"), "a numeric string — the contract is integers, not whatever int() accepts"),
])
def test_inconsistent_counts_are_could_not_run(line, why):
    """Assert the message too: argparse rejecting an unknown subcommand is ALSO
    exit 2, so a bare exit-code check passes before verdict exists at all."""
    rc, out = verdict(line)
    assert rc == 2 and "COULD-NOT-RUN" in out, why


def test_fenced_last_line_is_tolerated():
    rc, _ = verdict("```json\n" + step8(1, 1) + "\n```\n")
    assert rc == 0
