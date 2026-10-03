"""scripts/workflow-metrics.py — before/after measurement of a workflow change.

Claude Code writes one transcript event per content block (thinking, text, each tool
call), every one carrying the same `usage`. Counting events instead of `message.id`
inflated token and turn counts 2–3x in the 2026-10-02 analysis. The fixture below
repeats a message id on purpose.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CLI = REPO / "scripts" / "workflow-metrics.py"
sys.path.insert(0, str(REPO / "scripts"))
from workflow_metrics import lib  # noqa: E402

USAGE = {"input_tokens": 10, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 100, "output_tokens": 50}
ASK_ANSWER = ('User has answered your questions: "Which store?"="SQLite (Recommended)". '
              'You can now continue with the user\'s answers in mind.')


def human(t, text):
    return {"type": "user", "timestamp": t, "origin": {"kind": "human"}, "message": {"role": "user", "content": text}}


def assistant(t, mid, content, usage=USAGE):
    return {"type": "assistant", "timestamp": t, "message": {"id": mid, "role": "assistant", "content": content, "usage": usage}}


def write(path: Path, events: list, broken_line: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e) for e in events]
    if broken_line:
        lines.insert(2, '{"type": "assistant", "message": {"id": "trunc')
    path.write_text("\n".join(lines) + "\n")


def fixture(root: Path) -> Path:
    d = root / "-Users-ann-Developer-demo"
    write(d / "s1.jsonl", [
        human("2026-10-01T10:00:00Z", "build the importer"),
        assistant("2026-10-01T10:00:05Z", "m1", [{"type": "thinking", "thinking": "…"}]),
        assistant("2026-10-01T10:00:05Z", "m1", [{"type": "tool_use", "id": "q1", "name": "AskUserQuestion",
                                                   "input": {"questions": [{"question": "Which store?", "header": "Store",
                                                                            "options": [{"label": "SQLite (Recommended)"}, {"label": "JSON"}]}]}}]),
        {"type": "user", "timestamp": "2026-10-01T10:01:00Z",
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "q1", "content": ASK_ANSWER}]}},
        assistant("2026-10-01T10:01:05Z", "m2", [{"type": "text", "text": "Done. Shall I land it?"}],
                  usage={**USAGE, "cache_read_input_tokens": 2000}),
        human("2026-10-01T10:02:00Z", "ja"),
    ], broken_line=True)
    write(d / "s1" / "subagents" / "agent-a.jsonl", [
        {"type": "user", "timestamp": "2026-10-01T10:00:30Z", "message": {"role": "user", "content": "phase 1"}},
        assistant("2026-10-01T10:00:40Z", "m3", [{"type": "text", "text": "ok"}]),
    ])
    write(root / "-Users-ann-Developer-other" / "s2.jsonl", [
        human("2026-09-01T09:00:00Z", "old work"),
        assistant("2026-09-01T09:00:05Z", "m9", [{"type": "text", "text": "done"}]),
    ])
    return root


def cli(root: Path, *args: str, expect: int = 0):
    p = subprocess.run([sys.executable, str(CLI), *args, "--root", str(root)], capture_output=True, text=True)
    assert p.returncode == expect, p.stderr
    assert "Traceback" not in p.stderr
    return p.stdout


def test_api_calls_are_one_per_message_id_and_broken_lines_are_skipped(tmp_path):
    root = fixture(tmp_path)
    calls = list(lib.api_calls(str(root / "-Users-ann-Developer-demo" / "s1.jsonl")))
    assert [o["message"]["id"] for o, u, C in calls] == ["m1", "m2"]
    assert calls[0][2] == 1110


def test_project_label_strips_the_home_prefix_and_worktree_suffix():
    assert lib.project_label("-Users-ann-Developer-live-swiftui") == "live-swiftui"
    assert lib.project_label("-Users-ann-Developer-live-swiftui--claude-worktrees-radid") == "live-swiftui"


def test_tokens_counts_model_calls_not_events(tmp_path):
    out = cli(fixture(tmp_path), "tokens")
    assert "Total: 4 model calls" in out          # m1, m2, m3, m9 — not 5 events
    assert "| demo | 2 / 1 |" in out


def test_the_date_filter_keeps_only_sessions_that_start_in_range(tmp_path):
    out = cli(fixture(tmp_path), "tokens", "--since", "2026-09-15")
    assert "Total: 3 model calls" in out and "| other |" not in out


def test_the_project_filter_is_a_substring_of_the_directory(tmp_path):
    out = cli(fixture(tmp_path), "tokens", "--project", "other")
    assert "Total: 1 model calls" in out


def test_asks_recognises_the_recommended_answer_and_short_approvals(tmp_path):
    out = cli(fixture(tmp_path), "asks")
    assert "Total: 1 questions, 100% answered with the recommended option." in out
    assert "Total: 3 messages from you; 33% are short approvals" in out


def test_overhead_reports_the_first_call_baseline(tmp_path):
    out = cli(fixture(tmp_path), "overhead")
    # main: s1 first call m1 = 10+1000+100 = 1110 (F), m2 = 2110; baseline = min(F, C):
    # 1110 + 1110; s2 m9 = 1110, baseline 1110. Baseline 3330 of 4330 context = 76.9% -> 77%.
    assert "main: 3 model calls, 0.00 billion context tokens reused; the baseline alone 0.00 billion (77%)." in out
    # subagent: one call, so the baseline is the whole context -> 100%.
    assert "subagent: 1 model calls, 0.00 billion context tokens reused; the baseline alone 0.00 billion (100%)." in out


def test_a_missing_root_is_exit_two(tmp_path):
    p = subprocess.run([sys.executable, str(CLI), "tokens", "--root", str(tmp_path / "nope")],
                       capture_output=True, text=True)
    assert p.returncode == 2 and "UNREADABLE" in p.stderr


def test_a_bad_date_is_a_usage_error(tmp_path):
    p = subprocess.run([sys.executable, str(CLI), "tokens", "--root", str(fixture(tmp_path)), "--since", "last week"],
                       capture_output=True, text=True)
    assert p.returncode == 2 and "USAGE ERROR" in p.stderr


@pytest.mark.parametrize("command", ["tokens", "asks", "overhead"])
def test_an_empty_scope_prints_a_notice_instead_of_crashing(tmp_path, command):
    out = cli(fixture(tmp_path), command, "--project", "nomatch")
    assert "No transcripts in scope." in out


def test_odd_events_are_skipped_not_fatal(tmp_path):
    d = tmp_path / "-Users-ann-Developer-odd"
    odd = [
        {"type": "assistant", "timestamp": "2026-10-01T10:00:06Z", "message": "oops"},
        {"type": "user", "timestamp": "2026-10-01T10:00:06Z", "message": "oops"},
        {"type": "assistant", "timestamp": "2026-10-01T10:00:07Z", "message": {"id": "x1", "content": 5, "usage": [1]}},
        {"type": "assistant", "timestamp": "2026-10-01T10:00:08Z",
         "message": {"id": "x2", "content": ["str", 3, None, {"type": "tool_use", "name": ["l"], "input": "s"},
                                             {"type": "tool_use", "name": "AskUserQuestion", "input": {"questions": "q"}}],
                     "usage": {"input_tokens": None, "cache_read_input_tokens": "n/a"}}},
        {"type": "assistant", "timestamp": "2026-10-01T10:00:09Z", "message": {"id": ["unhashable"], "content": [], "usage": USAGE}},
        {"type": "user", "timestamp": "2026-10-01T10:00:10Z", "message": {"role": "user", "content": [None, 1, {"type": "tool_result"}]}},
        [1, 2], "string-line", None,
    ]
    events = [human("2026-10-01T10:00:00Z", "ja"), assistant("2026-10-01T10:00:05Z", "m1", [{"type": "text", "text": "hi"}])]
    events[1:1] = odd
    write(d / "s.jsonl", events)
    for command in ("tokens", "asks", "overhead"):
        out = cli(tmp_path, command)
        assert "Traceback" not in out
    # valid numbers unchanged: m1 and the id-less-hashable event count; x1/x2 have no tokens and are skipped
    assert "Total: 2 model calls" in cli(tmp_path, "tokens")
    assert "Total: 1 messages from you" in cli(tmp_path, "asks")


def test_an_unreadable_transcript_is_exit_two(tmp_path):
    import os
    root = fixture(tmp_path)
    target = root / "-Users-ann-Developer-demo" / "s1.jsonl"
    target.chmod(0)
    try:
        if os.geteuid() == 0 or os.access(target, os.R_OK):
            pytest.skip("file is still readable here")
        p = subprocess.run([sys.executable, str(CLI), "tokens", "--root", str(root)], capture_output=True, text=True)
        assert p.returncode == 2 and "UNREADABLE:" in p.stderr and "Traceback" not in p.stderr
    finally:
        target.chmod(0o644)


def test_until_is_exclusive_and_since_is_inclusive_at_the_boundary(tmp_path):
    root = fixture(tmp_path)
    boundary = "2026-10-01T10:00:00+00:00"   # the demo session's first timestamp
    until = cli(root, "tokens", "--until", boundary)
    assert "| demo |" not in until and "| other |" in until
    since = cli(root, "tokens", "--since", boundary)
    assert "| demo |" in since and "| other |" not in since


def test_out_writes_what_it_prints_and_an_unwritable_out_is_exit_two(tmp_path):
    root = fixture(tmp_path)
    dest = tmp_path / "report.md"
    printed = cli(root, "tokens", "--out", str(dest))
    assert dest.read_text() == printed
    p = subprocess.run([sys.executable, str(CLI), "tokens", "--root", str(root), "--out", str(tmp_path / "nodir" / "r.md")],
                       capture_output=True, text=True)
    assert p.returncode == 2 and "UNREADABLE:" in p.stderr
