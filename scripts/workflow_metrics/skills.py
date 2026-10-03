"""Skill use: which skills sit in the context, and which are never used?

Three sources per skill:
  1) the Skill tool (Claude started the skill)        - transcripts
  2) a /command typed by the user in a session         - transcripts (<command-name>)
  3) a /command in ~/.claude/history.jsonl             - longer than the transcripts; read
     only when the scope is the default transcript root (a copied root has no matching history)
"""
from __future__ import annotations

import collections
import datetime
import json
import os
import re

from . import lib

EMPTY = "No transcripts in scope.\n"
HISTORY = os.path.expanduser("~/.claude/history.jsonl")


def listing(scope: lib.Scope) -> dict:
    """The skill list as it sat in the context (from the newest main session in scope)."""
    files = [f for _, _, f, sub in lib.sessions(scope, include_sub=False)]
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        for o in lib.events(f):
            a = o.get("attachment") if o.get("type") == "attachment" else None
            if isinstance(a, dict) and a.get("type") == "skill_listing" and isinstance(a.get("content"), str):
                items = {}
                for ln in a["content"].split("\n- "):
                    ln = ln.lstrip("- ").strip()
                    if ": " in ln:
                        n, desc = ln.split(": ", 1)
                        items[n.strip()] = desc.strip()
                return items
    return {}


def group(name: str, desc: str) -> str:
    if ":" in name:
        return name.split(":", 1)[0]
    if desc.rstrip().endswith("(gstack)"):
        return "gstack"
    return "other (user/built-in)"


def _history():
    hist = collections.Counter()
    first = None
    try:
        fh = open(HISTORY, errors="ignore")
    except OSError:
        return hist, first
    with fh:
        for ln in fh:
            try:
                h = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if not isinstance(h, dict):
                continue
            disp = h.get("display")
            disp = disp.strip() if isinstance(disp, str) else ""
            if disp.startswith("/") and disp[1:].split():
                hist[disp[1:].split()[0]] += 1
                tt = h.get("timestamp")
                if isinstance(tt, (int, float)) and not isinstance(tt, bool) and tt > 0 and (first is None or tt < first):
                    first = tt
    return hist, first


def _date(t, divisor) -> str:
    try:
        return datetime.datetime.fromtimestamp(t / divisor).strftime("%Y-%m-%d") if t else "–"
    except (OverflowError, OSError, ValueError):
        return "–"


def report(scope: lib.Scope) -> str:
    tool_uses = collections.Counter()
    typed = collections.Counter()
    last = {}
    files = 0
    for label, d, f, is_sub in lib.sessions(scope):
        files += 1
        for o in lib.events(f):
            t = lib.ts(o)
            for b in lib.blocks(o):
                if b.get("type") == "tool_use" and b.get("name") == "Skill":
                    s = str(lib.tool_input(b).get("skill", "?"))
                    tool_uses[s] += 1
                    if t and t > last.get(s, 0):
                        last[s] = t
            if o.get("type") == "user" and not is_sub:
                c = lib.message(o).get("content")
                m = re.search(r"<command-name>/?([^<\s]+)</command-name>", c if isinstance(c, str) else "")
                if m:
                    s = m.group(1)
                    typed[s] += 1
                    if t and t > last.get(s, 0):
                        last[s] = t
    if not files:
        return EMPTY
    items = listing(scope)
    use_history = os.path.abspath(scope.root) == os.path.abspath(lib.DEFAULT_ROOT)
    hist, first_hist = _history() if use_history else (collections.Counter(), None)
    rows = [(group(n, d), n, len(n) + len(d) + 4, tool_uses[n], typed[n], hist[n], last.get(n)) for n, d in items.items()]
    out = ["# Skill use\n"]
    if not items:
        out.append("No skill listing found in the transcripts in scope, so the never-used analysis is skipped.\n")
    else:
        out.append(f"Skills in the context: **{len(items)}**. The descriptions alone are about **{sum(r[2] for r in rows) // 4:,} tokens** on every turn.\n")
    src = "Skill-tool calls and typed /commands in the transcripts in scope"
    out.append(src + (", and /commands in ~/.claude/history.jsonl.\n" if use_history else " (history.jsonl is read only for the default transcript root).\n"))
    if use_history and (scope.project or scope.since is not None or scope.until is not None):
        out.append("Note: history counts are all-time and global; transcript counts are scoped.\n")
    if items:
        zero = [r for r in rows if r[3] + r[4] + r[5] == 0]
        out.append(f"**Never used: {len(zero)} of {len(rows)}** (≈ {sum(r[2] for r in zero) // 4:,} tokens of descriptions).\n")
        by = collections.defaultdict(list)
        for r in rows:
            by[r[0]].append(r)
        out.append("## Per package\n\n| Package | skills | never used | via Skill tool | typed in session | typed (history) | ≈ description tokens |\n|---|---:|---:|---:|---:|---:|---:|")
        for g, rs in sorted(by.items(), key=lambda x: -len(x[1])):
            out.append(f"| {g} | {len(rs)} | {sum(1 for r in rs if r[3] + r[4] + r[5] == 0)} | {sum(r[3] for r in rs)} | {sum(r[4] for r in rs)} | {sum(r[5] for r in rs)} | {sum(r[2] for r in rs) // 4:,} |")
        for g, rs in sorted(by.items(), key=lambda x: -len(x[1])):
            out.append(f"\n### {g}\n\n| Skill | Skill tool | typed (session) | typed (history) | last (transcript) |\n|---|---:|---:|---:|---|")
            for r in sorted(rs, key=lambda r: -(r[3] + r[4] + r[5])):
                ld = _date(r[6], 1)
                out.append(f"| {'**' + r[1] + '**' if r[3] + r[4] + r[5] == 0 else r[1]} | {r[3]} | {r[4]} | {r[5]} | {ld} |")
    extra = [(s, tool_uses[s] + typed[s]) for s in set(tool_uses) | set(typed) if s not in items]
    if extra:
        out.append("\n### Used, but not in the listing (removed, renamed, or from another session type)\n")
        out.append(", ".join(f"`{s}` ({n})" for s, n in sorted(extra, key=lambda x: (-x[1], x[0]))[:25]))
    if first_hist and _date(first_hist, 1000) != "–":
        out.append(f"\n\nhistory.jsonl starts {_date(first_hist, 1000)}.")
    return "\n".join(out) + "\n"
