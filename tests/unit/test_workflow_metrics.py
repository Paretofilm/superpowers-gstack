"""scripts/workflow-metrics.py — before/after measurement of a workflow change.

Claude Code writes one transcript event per content block (thinking, text, each tool
call), every one carrying the same `usage`. Counting events instead of `message.id`
inflated token and turn counts 2–3x in the 2026-10-02 analysis. The fixture below
repeats a message id on purpose.
"""
from __future__ import annotations

import json
import re
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


def fixture_more(root: Path) -> Path:
    fixture(root)
    d = root / "-Users-ann-Developer-demo"
    write(d / "s3.jsonl", [
        {"type": "attachment", "timestamp": "2026-10-02T08:00:00Z",
         "attachment": {"type": "skill_listing", "content": "- superpowers:brainstorming: Use before building\n- unused-skill: Never called"}},
        human("2026-10-02T08:00:01Z", "test it"),
        assistant("2026-10-02T08:00:05Z", "m4", [{"type": "tool_use", "id": "s1", "name": "Skill", "input": {"skill": "superpowers:brainstorming"}}]),
        assistant("2026-10-02T08:00:06Z", "m5", [{"type": "tool_use", "id": "b1", "name": "Bash", "input": {"command": "swift test --filter Foo"}}]),
        {"type": "user", "timestamp": "2026-10-02T08:02:06Z",
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "b1", "content": "ok"}]}},
        assistant("2026-10-02T08:02:10Z", "m6", [{"type": "tool_use", "id": "x1", "name": "mcp__XcodeBuildMCP__build_sim", "input": {}}]),
    ])
    return root


def test_skills_lists_used_and_never_used_skills(tmp_path):
    out = cli(fixture_more(tmp_path), "skills")
    assert "Never used: 1 of 2" in out and "unused-skill" in out


def test_skills_without_a_skill_listing_prints_a_note(tmp_path):
    out = cli(fixture(tmp_path), "skills")
    assert "No skill listing found" in out


def test_triggers_counts_build_and_test_commands(tmp_path):
    out = cli(fixture_more(tmp_path), "triggers")
    assert "| demo | swift test | 1 |" in out


def test_mcp_counts_calls_per_server_without_reading_secrets(tmp_path):
    cj = tmp_path / "claude.json"
    cj.write_text(json.dumps({"mcpServers": {"XcodeBuildMCP": {"env": {"TOKEN": "secret"}}, "idle": {}}}))
    out = cli(fixture_more(tmp_path / "root"), "mcp", "--claude-json", str(cj))
    assert "| XcodeBuildMCP | 1 | demo (1) |" in out and "| idle | 0 | – |" in out
    assert "secret" not in out


def test_mcp_with_a_missing_claude_json_still_reports_call_counts(tmp_path):
    out = cli(fixture_more(tmp_path / "root"), "mcp", "--claude-json", str(tmp_path / "nope.json"))
    assert "not found" in out and "| XcodeBuildMCP | 1 | demo (1) |" in out


@pytest.mark.parametrize("content", ["{not json", "[1, 2]"])
def test_mcp_with_an_unreadable_claude_json_is_exit_two(tmp_path, content):
    cj = tmp_path / "claude.json"
    cj.write_text(content)
    p = subprocess.run([sys.executable, str(CLI), "mcp", "--root", str(fixture_more(tmp_path / "root")), "--claude-json", str(cj)],
                       capture_output=True, text=True)
    assert p.returncode == 2 and "UNREADABLE:" in p.stderr and "Traceback" not in p.stderr


def test_digest_of_one_session(tmp_path):
    root = fixture_more(tmp_path)
    out = cli(root, "digest", "--session", str(root / "-Users-ann-Developer-demo" / "s1.jsonl"))
    assert "Which store?" in out and "SQLite (Recommended)" in out


def test_digest_top_lists_the_longest_sessions(tmp_path):
    out = cli(fixture_more(tmp_path), "digest", "--top", "1")
    assert "| demo |" in out and "| other |" in out


def test_digest_without_session_or_top_is_a_usage_error(tmp_path):
    p = subprocess.run([sys.executable, str(CLI), "digest", "--root", str(fixture(tmp_path))], capture_output=True, text=True)
    assert p.returncode == 2 and "USAGE ERROR:" in p.stderr


def test_digest_with_a_missing_session_file_is_exit_two(tmp_path):
    p = subprocess.run([sys.executable, str(CLI), "digest", "--root", str(fixture(tmp_path)), "--session", str(tmp_path / "nope.jsonl")],
                       capture_output=True, text=True)
    assert p.returncode == 2 and "UNREADABLE:" in p.stderr and "Traceback" not in p.stderr


@pytest.mark.parametrize("args", [("skills",), ("triggers",), ("mcp",), ("digest", "--top", "2")])
def test_an_empty_scope_prints_a_notice_for_the_second_half_too(tmp_path, args):
    out = cli(fixture(tmp_path), *args, "--project", "nomatch")
    assert "No transcripts in scope." in out


def test_second_half_commands_survive_odd_events(tmp_path):
    d = tmp_path / "-Users-ann-Developer-odd"
    write(d / "s.jsonl", [
        human("2026-10-01T10:00:00Z", "go"),
        {"type": "attachment", "timestamp": "2026-10-01T10:00:01Z", "attachment": {"type": "skill_listing", "content": 5}},
        assistant("2026-10-01T10:00:02Z", "a", [{"type": "tool_use", "id": ["x"], "name": "Skill", "input": "s"},
                                                {"type": "tool_use", "id": ["y"], "name": "Bash", "input": {"command": ["l"]}},
                                                {"type": "tool_use", "id": "z", "name": 7, "input": None},
                                                {"type": "tool_use", "id": "q", "name": "AskUserQuestion", "input": {"questions": [1, "s"]}},
                                                {"type": "tool_use", "id": "m", "name": "mcp__", "input": {}}]),
        {"type": "user", "timestamp": "2026-10-01T10:00:03Z",
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": ["x"]}, {"type": "tool_result", "tool_use_id": "q", "content": None}]}},
        "junk", [1],
    ])
    for args in (("skills",), ("triggers",), ("mcp", "--claude-json", str(tmp_path / "none")), ("digest", "--session", str(d / "s.jsonl")), ("digest", "--top", "1")):
        assert "Traceback" not in cli(tmp_path, *args)


def test_int_rejects_nan_infinity_negatives_and_booleans(tmp_path):
    for bad in (float("nan"), float("inf"), -1, -0.5, True, False, None, "5", [1]):
        assert lib._int(bad) == 0
    assert lib._int(7) == 7 and lib._int(7.9) == 7
    d = tmp_path / "-Users-ann-Developer-numbers"
    d.mkdir()
    ev = [human("2026-10-01T10:00:00Z", "go")]
    lines = [json.dumps(ev[0]),
             '{"type": "assistant", "timestamp": "2026-10-01T10:00:05Z", "message": {"id": "n1", "content": [], '
             '"usage": {"input_tokens": NaN, "cache_read_input_tokens": -500, "cache_creation_input_tokens": Infinity, "output_tokens": -3}}}',
             json.dumps(assistant("2026-10-01T10:00:06Z", "n2", [{"type": "text", "text": "ok"}]))]
    (d / "s.jsonl").write_text("\n".join(lines) + "\n")
    for command in ("tokens", "overhead"):
        out = cli(tmp_path, command)
        assert not re.search(r"\b(nan|inf|infinity)\b", out, re.I)
        assert not any(tok.startswith("-") and tok[1:2].isdigit() for tok in out.split())
