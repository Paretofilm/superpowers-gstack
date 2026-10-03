#!/usr/bin/env python3
"""workflow-metrics — measure what a workflow change did to questions, stops and tokens.

Commands: tokens, asks, overhead, skills, triggers, mcp, digest. Reads Claude Code transcripts (default ~/.claude/projects), which are
deleted after `cleanupPeriodDays` — copy them aside before a long before/after study.

Exit 0 report printed, 2 refused (reason on stderr). Never a traceback.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workflow_metrics import asks, digest, lib, mcp, overhead, skills, tokens, triggers  # noqa: E402

COMMANDS = {"tokens": tokens.report, "asks": asks.report, "overhead": overhead.report,
            "skills": skills.report, "triggers": triggers.report, "mcp": mcp.report, "digest": digest.report}


def scope_from(a) -> lib.Scope:
    try:
        since = lib.parse_date(a.since) if a.since else None
        until = lib.parse_date(a.until) if a.until else None
    except ValueError as exc:
        raise SystemExit(f"USAGE ERROR: --since/--until must be ISO dates like 2026-10-02 ({exc})")
    root = os.path.expanduser(a.root)
    if not os.path.isdir(root):
        raise SystemExit(f"UNREADABLE: {root} is not a directory")
    return lib.Scope(root=root, project=a.project, since=since, until=until)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=sorted(COMMANDS))
    ap.add_argument("--root", default=lib.DEFAULT_ROOT)
    ap.add_argument("--project", help="substring of the transcript directory name")
    ap.add_argument("--since", help="transcript files starting on or after this ISO date/time (local time unless a zone is given). Each file, a subagent's included, is filtered by its own first timestamp, so a subagent file can be in scope while its parent session is not")
    ap.add_argument("--until", help="transcript files starting before this ISO date/time (exclusive; same per-file rule as --since)")
    ap.add_argument("--claude-json", default="~/.claude.json", help="mcp: file whose mcpServers KEYS (never values) are read")
    ap.add_argument("--session", help="digest: one transcript file to turn into a timeline")
    ap.add_argument("--top", type=int, help="digest: list the N longest main sessions per project")
    ap.add_argument("--out", help="also write the report to this file")
    a = ap.parse_args(argv)
    try:
        scope = scope_from(a)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        if a.command == "mcp":
            text = mcp.report(scope, a.claude_json)
        elif a.command == "digest":
            if not a.session and a.top is None:
                print("USAGE ERROR: digest needs --session <file.jsonl> or --top N", file=sys.stderr)
                return 2
            if a.top is not None and a.top < 1:
                print("USAGE ERROR: --top must be at least 1", file=sys.stderr)
                return 2
            text = digest.report(scope, a.session, a.top)
        else:
            text = COMMANDS[a.command](scope)
    except OSError as exc:
        print(f"UNREADABLE: {exc}", file=sys.stderr)
        return 2
    if a.out:
        try:
            Path(a.out).write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"UNREADABLE: cannot write {a.out} ({exc})", file=sys.stderr)
            return 2
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
