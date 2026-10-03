"""Shared transcript readers. Standard library only.

Claude Code writes one event per content block, each with the same `usage`: every
token and turn count deduplicates on `message.id` (api_calls). tool_use blocks have
unique ids and are counted as they come.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
from dataclasses import dataclass

DEFAULT_ROOT = os.path.expanduser("~/.claude/projects")
WORKTREE_SUFFIX = re.compile(r"(--claude-worktrees-|-\.worktrees-|--worktrees-).*$")


@dataclass(frozen=True)
class Scope:
    root: str = DEFAULT_ROOT
    project: str | None = None   # substring of the transcript directory name
    since: float | None = None   # epoch seconds, inclusive
    until: float | None = None   # epoch seconds, exclusive


def parse_date(s: str) -> float:
    """`2026-10-02` or `2026-10-02T22:34`; a date without a zone is local time."""
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.astimezone()
    return d.timestamp()


def project_label(dirname: str) -> str:
    """`-Users-ann-Developer-live-swiftui--claude-worktrees-x` -> `live-swiftui`."""
    s = WORKTREE_SUFFIX.sub("", dirname)
    s = re.sub(r"^-Users-[^-]+-", "", s)
    s = re.sub(r"^(Developer|Projects|projects|src|code|repos)-", "", s)
    return s or dirname


def events(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(o, dict):
                yield o


def ts(o):
    try:
        return dt.datetime.fromisoformat(o["timestamp"].replace("Z", "+00:00")).timestamp()
    except (KeyError, AttributeError, ValueError):
        return None


def first_ts(path):
    for o in events(path):
        t = ts(o)
        if t is not None:
            return t
    return None


def sessions(scope: Scope, include_sub: bool = True):
    """(label, dirname, path, is_sub) for every transcript file in scope. The date
    filter uses each file's first timestamp."""
    for d in sorted(os.listdir(scope.root)):
        p = os.path.join(scope.root, d)
        if not os.path.isdir(p) or (scope.project and scope.project not in d):
            continue
        for f in sorted(glob.glob(os.path.join(p, "**", "*.jsonl"), recursive=True)):
            is_sub = "/subagents/" in f
            if is_sub and not include_sub:
                continue
            if scope.since is not None or scope.until is not None:
                t = first_ts(f)
                if t is None or (scope.since is not None and t < scope.since) \
                        or (scope.until is not None and t >= scope.until):
                    continue
            yield project_label(d), d, f, is_sub


def msg_id(o):
    return (o.get("message") or {}).get("id")


def api_calls(path):
    """(event, usage, total context) for the first event of each message.id: one per model call."""
    seen = set()
    for o in events(path):
        if o.get("type") != "assistant":
            continue
        i = msg_id(o)
        if i is not None:
            if i in seen:
                continue
            seen.add(i)
        u = (o.get("message") or {}).get("usage") or {}
        C = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
        yield o, u, C


def blocks(o):
    c = (o.get("message") or {}).get("content")
    return [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []


def text_of(o):
    c = (o.get("message") or {}).get("content")
    if isinstance(c, str):
        return c
    return "\n".join(b.get("text", "") for b in blocks(o) if b.get("type") == "text")


def is_human(o):
    """A real user message: not a tool result, a task notification, a peer or meta."""
    if o.get("type") != "user" or o.get("isMeta") or o.get("isCompactSummary"):
        return False
    org = o.get("origin")
    if isinstance(org, dict) and org.get("kind") not in (None, "human"):
        return False
    if any(b.get("type") == "tool_result" for b in blocks(o)):
        return False
    t = text_of(o).strip()
    return bool(t) and not t.startswith(("<task-notification", "<system-reminder", "<local-command"))


def pct(a, b) -> str:
    return f"{a / b:.0%}" if b else "–"
