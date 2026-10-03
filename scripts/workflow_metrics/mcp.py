"""MCP servers per project: which user-level servers are actually called, and where?

Reads only the server NAMES (the keys of `mcpServers`) from the claude.json, never
the values (env, tokens, headers). Changes nothing.
"""
from __future__ import annotations

import collections
import json
import os
import re

from . import lib

EMPTY = "No transcripts in scope.\n"


def prefix(name: str) -> str:
    """The server name as it appears in tool names: characters other than [A-Za-z0-9_-] become _."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


def server_names(claude_json: str):
    """(names, note). A missing file gives ([], note); invalid JSON or a non-object raises OSError."""
    path = os.path.expanduser(claude_json)
    try:
        with open(path, errors="ignore") as fh:
            cj = json.load(fh)
    except FileNotFoundError:
        return [], f"{path} not found: the server list is unknown, so only per-project call counts are shown."
    except json.JSONDecodeError as exc:
        raise OSError(f"{path} is not valid JSON ({exc})")
    if not isinstance(cj, dict):
        raise OSError(f"{path} is not a JSON object")
    servers = cj.get("mcpServers")
    return (sorted(str(k) for k in servers.keys()) if isinstance(servers, dict) else []), None


def report(scope: lib.Scope, claude_json: str = "~/.claude.json") -> str:
    used = collections.defaultdict(collections.Counter)   # label -> prefix -> calls
    files = 0
    for label, d, f, is_sub in lib.sessions(scope):
        files += 1
        for o in lib.events(f):
            for b in lib.blocks(o):
                n = str(b.get("name", ""))
                if b.get("type") == "tool_use" and n.startswith("mcp__"):
                    parts = n.split("__")
                    if len(parts) > 1 and parts[1]:
                        used[label][parts[1]] += 1
    if not files:
        return EMPTY
    names, note = server_names(claude_json)
    allused = collections.Counter()
    for a in used.values():
        allused.update(a)
    out = ["# MCP servers per project\n"]
    if note:
        out.append(note + "\n")
        out.append("## MCP calls per server prefix and project\n\n| Server prefix | calls | projects |\n|---|---:|---|")
        for p, c in sorted(allused.items(), key=lambda x: (-x[1], x[0])):
            ps = [f"{a} ({used[a][p]})" for a in sorted(used) if used[a][p]]
            out.append(f"| {p} | {c} | {', '.join(ps)} |")
        return "\n".join(out) + "\n"
    out.append(f"User-level servers (loaded in every project): **{len(names)}**.\n")
    out.append("## User-level server: calls in total and in which projects\n\n| Server | calls | projects where it is used |\n|---|---:|---|")
    for n in names:
        p = prefix(n)
        apps = [f"{a} ({used[a][p]})" for a in sorted(used) if used[a][p]]
        out.append(f"| {n} | {allused[p]} | {', '.join(apps) or '–'} |")
    never = [n for n in names if not allused[prefix(n)]]
    out.append(f"\n**Never used in any project ({len(never)}):** {', '.join(never) or '–'}")
    return "\n".join(out) + "\n"
