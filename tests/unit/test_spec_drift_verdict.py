"""Guard scripts/spec-drift.py verdict — Step 8's JSON -> the standalone exit code.

/ship turns the audit into AskUserQuestion gates. Standalone there is nobody to
ask at a phase boundary; the exit code IS the gate, so its mapping cannot be a
judgement call the model makes differently on each run.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "spec-drift.py"


def verdict(text: str):
    p = subprocess.run([sys.executable, str(SCRIPT), "verdict"],
                       capture_output=True, text=True, input=text)
    out = p.stdout + p.stderr
    assert "Traceback" not in out and "INTERNAL" not in out, \
        f"the verdict line is the contract; a traceback or an INTERNAL fallback is not it:\n{out}"
    return p.returncode, out


def verdict_json(text: str, stdin: str = ""):
    p = subprocess.run([sys.executable, str(SCRIPT), "verdict", "--json", text],
                       capture_output=True, text=True, input=stdin)
    return p.returncode, p.stdout + p.stderr


def verdict_bytes(data: bytes, **env):
    p = subprocess.run([sys.executable, str(SCRIPT), "verdict"], capture_output=True,
                       input=data, env={**os.environ, **env})
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


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
    """A JSON-looking line mid-report must not be mistaken for the contract — in
    BOTH directions: an early clean-looking line must never outrank a later
    drift line (that is the false green), and vice versa."""
    rc, _ = verdict(step8(2, 0) + "\n" + step8(2, 2) + "\n")
    assert rc == 0
    rc, _ = verdict(step8(2, 2) + "\n" + step8(2, 0) + "\n")
    assert rc == 1, "a CLEAN line above the final DRIFT line must not win"


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


@pytest.mark.parametrize("line,why", [
    ('{"total_items": ' + "1" * 5000 + ', "done": 1, "changed": 0, "deferred": 0, "unverifiable": 0, "summary": ""}',
     "an int literal past sys.get_int_max_str_digits() is a ValueError, not a JSONDecodeError"),
    ("[" * 100_000 + "]" * 100_000, "a deeply nested last line is a RecursionError"),
    (step8(1, 1)[:-1] + ', "summary": ' + "[" * 100_000 + "]" * 100_000 + "}", "same, inside a value"),
])
def test_pathological_last_line_is_named_could_not_run(line, why):
    rc, out = verdict("PLAN COMPLETION AUDIT\n" + line + "\n")
    assert rc == 2 and "SPEC-DRIFT: COULD-NOT-RUN (exit 2)" in out, why


@pytest.mark.parametrize("text,why", [
    ("[1, 2]\n", "valid JSON, but a list — not Step 8's object"),
    ("42\n", "valid JSON scalar"),
    ("null\n", "valid JSON null — `k not in None` would be a TypeError without the dict guard"),
    (json.dumps(json.loads(step8(1, 1)), indent=2) + "\n", "pretty-printed JSON: the last line is `}`"),
])
def test_non_object_or_multiline_json_is_named_could_not_run(text, why):
    rc, out = verdict(text)
    assert rc == 2 and "SPEC-DRIFT: COULD-NOT-RUN (exit 2)" in out, why


def test_duplicate_keys_are_a_contradiction_not_a_correction():
    """json.loads keeps the last value: a line that says done=2 of 4 and later
    done=4 would read as CLEAN — the one input that hands the caller a false green."""
    line = ('{"total_items":4,"done":2,"changed":0,"deferred":2,"unverifiable":0,'
            '"summary":"x","done":4,"deferred":0}')
    rc, out = verdict(line + "\n")
    assert rc == 2 and "COULD-NOT-RUN" in out


def test_a_restated_count_must_agree_with_the_derived_one():
    obj = json.loads(step8(3, 3))
    obj["partial"] = 2                      # contradicts the derived 0
    rc, out = verdict(json.dumps(obj) + "\n")
    assert rc == 2 and "contradicts" in out
    obj = json.loads(step8(3, 1, deferred=2))
    obj["not_done"] = 7                     # not a contract key: ignored, whatever it says
    obj["partial"] = 0                      # agrees with the derived remainder
    rc, _ = verdict(json.dumps(obj) + "\n")
    assert rc == 1


def test_json_flag_is_the_input_and_stdin_is_ignored():
    rc, out = verdict_json("```json\n" + step8(2, 1, changed=1) + "\n```\n", stdin=step8(2, 0))
    assert rc == 0 and "SPEC-DRIFT: CLEAN (exit 0)" in out
    rc, out = verdict_json("not json", stdin=step8(2, 2))
    assert rc == 2 and "COULD-NOT-RUN" in out, "a clean line on stdin must not rescue --json"
    rc, out = verdict_json("")
    assert rc == 2 and "COULD-NOT-RUN" in out, "--json '' is empty input, not 'read stdin'"


def test_verdict_does_not_depend_on_the_callers_locale():
    """One stray non-UTF-8 byte on a line the verdict never reads must give the
    same answer under every stdin codec setting — the gate is mechanical."""
    data = b"\xff garbage line\n" + step8(1, 1).encode() + b"\n"
    results = {enc: verdict_bytes(data, PYTHONIOENCODING=enc)
               for enc in ("utf-8:strict", "utf-8:surrogateescape", "ascii")}
    assert {rc for rc, _ in results.values()} == {0}, results
    for _, out in results.values():
        assert "Traceback" not in out and "INTERNAL" not in out, out


def test_unicode_line_separators_inside_a_string_are_not_line_breaks():
    """str.splitlines() splits on U+2028/U+2029/U+0085, which JSON permits raw inside
    a string; only "\\n" ends the line. A trailing line of zero-width padding is
    not a line either."""
    obj = json.loads(step8(2, 2)); obj["summary"] = "a" + chr(0x2028) + "b" + chr(0x85) + "c"
    rc, out = verdict(json.dumps(obj, ensure_ascii=False) + "\n" + chr(0x200B) + "\n")
    assert rc == 0 and "CLEAN" in out


def test_the_verdict_line_is_on_stdout_for_every_outcome():
    """A caller capturing stdout for the SPEC-DRIFT line must get it on exit 2 too."""
    for text, code in (("garbage\n", 2), (step8(2, 1), 1), (step8(2, 2), 0)):
        p = subprocess.run([sys.executable, str(SCRIPT), "verdict"],
                           capture_output=True, text=True, input=text)
        assert p.returncode == code
        assert f"SPEC-DRIFT: " in p.stdout and f"(exit {code})" in p.stdout, (text, p.stdout, p.stderr)


def test_terminal_stdin_is_refused_not_hung():
    """No --json and a TTY on stdin used to block forever with no prompt."""
    master, slave = os.openpty()
    try:
        p = subprocess.run([sys.executable, str(SCRIPT), "verdict"], stdin=slave,
                           capture_output=True, text=True, timeout=10)
    finally:
        os.close(master)
        os.close(slave)
    assert p.returncode == 2 and "COULD-NOT-RUN" in p.stdout and "terminal" in p.stdout


@pytest.mark.parametrize("summary", ["null", "[]", '{"a":1}', "7", "true"])
def test_summary_must_be_a_string(summary):
    """Codex, Fase-1 verification: valid counts with a non-string summary read as
    CLEAN. Step 8 specifies a markdown string; anything else is not the audit's
    line, and the contract fails closed on every other malformed shape."""
    line = ('{"total_items":4,"done":4,"changed":0,"deferred":0,"unverifiable":0,'
            f'"summary":{summary}}}')
    rc, out = verdict(line)
    assert rc == 2 and "SPEC-DRIFT: COULD-NOT-RUN (exit 2)" in out and "summary is not a string" in out
