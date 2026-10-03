"""Compressed timeline of one session, for case studies.

Segments the session on the user's messages. Per segment: what the user asked, what
Claude did (tool counts, skills, questions with answers, subagent dispatches, commands
over 2 minutes) and what Claude said when it stopped.

  --top N          list the longest main sessions per project
  --session FILE   return the timeline of one transcript as text
"""
from __future__ import annotations

import collections
import json
import os
import re

from . import lib

EMPTY = "No transcripts in scope.\n"
ANS = re.compile(r'"((?:[^"\\]|\\.)*)"="((?:[^"\\]|\\.)*)"', re.S)


def clip(s, n):
    s = re.sub(r"\s+", " ", s.strip() if isinstance(s, str) else "")
    return s if len(s) <= n else s[:n - 1] + "…"


def longest(scope: lib.Scope, n: int) -> str:
    best = collections.defaultdict(list)
    files = 0
    for label, d, f, is_sub in lib.sessions(scope, include_sub=False):
        files += 1
        replies = sum(1 for _ in lib.api_calls(f))
        best[label].append((replies, os.path.getsize(f) // 1024, f))
    if not files:
        return EMPTY
    out = [f"# Longest main sessions per project (top {n}; replies deduplicated on message.id)\n",
           "| Project | replies | KB | file |\n|---|---:|---:|---|"]
    for label in sorted(best):
        for replies, kb, f in sorted(best[label], reverse=True)[:max(n, 0)]:
            out.append(f"| {label} | {replies} | {kb} | `{f}` |")
    return "\n".join(out) + "\n"


def _segment(human="(start)", t=0, ctx=0):
    return {"human": human, "t": t, "tools": collections.Counter(), "skills": [], "asks": [], "agents": [],
            "slow": [], "turns": 0, "last": "", "ctx": ctx, "marks": []}


def digest(scope: lib.Scope, path: str) -> str:
    real = os.path.realpath(path)
    label = next((a for a, d, f, s in lib.sessions(scope, include_sub=False) if os.path.realpath(f) == real), "unknown")
    evs = list(lib.events(path))
    if not evs:
        return f"No events in {path}.\n"
    t0 = next((lib.ts(o) for o in evs if lib.ts(o)), 0)
    segs = []
    cur = _segment()
    pend_ask = {}
    pend_bash = {}
    seen_ids = set()
    for o in evs:
        t = lib.ts(o) or t0
        ty = o.get("type")
        if o.get("isCompactSummary"):
            cur["marks"].append("COMPACTION")
            continue
        if ty == "user" and lib.is_human(o):
            segs.append(cur)
            cur = _segment(clip(lib.text_of(o), 600), (t - t0) / 60, cur["ctx"])
            continue
        if ty == "assistant":
            mid = lib.msg_id(o)
            if mid is None or mid not in seen_ids:   # one model call counts once
                cur["turns"] += 1
                if mid is not None:
                    seen_ids.add(mid)
                u = lib.message(o).get("usage")
                u = u if isinstance(u, dict) else {}
                C = lib._int(u.get("input_tokens")) + lib._int(u.get("cache_read_input_tokens")) + lib._int(u.get("cache_creation_input_tokens"))
                cur["ctx"] = C or cur["ctx"]
            txt = lib.text_of(o).strip()
            has_tool = any(b.get("type") == "tool_use" for b in lib.blocks(o))
            if txt and not has_tool:
                cur["last"] = clip(txt, 500)
            for b in lib.blocks(o):
                if b.get("type") != "tool_use":
                    continue
                nm = str(b.get("name"))
                inp = lib.tool_input(b)
                bid = lib.key(b.get("id"))
                cur["tools"][nm] += 1
                if nm == "Skill":
                    cur["skills"].append(inp.get("skill"))
                if nm in ("Agent", "Task"):
                    cur["agents"].append(clip(inp.get("description") or inp.get("prompt", ""), 90))
                if nm == "AskUserQuestion" and bid:
                    pend_ask[bid] = inp
                if nm == "Bash" and bid:
                    pend_bash[bid] = (clip(inp.get("command", ""), 110), t)
        elif ty == "user":
            for b in lib.blocks(o):
                if b.get("type") != "tool_result":
                    continue
                rid = lib.key(b.get("tool_use_id"))
                if rid in pend_ask:
                    inp = pend_ask.pop(rid)
                    res = b.get("content")
                    res = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False)
                    ans = dict(ANS.findall(res))
                    qs = inp.get("questions")
                    for q in (qs if isinstance(qs, list) else []):
                        if not isinstance(q, dict):
                            continue
                        qtext = lib.key(q.get("question")) or ""
                        a = ans.get(qtext) or (list(ans.values())[0] if len(ans) == 1 else "?")
                        cur["asks"].append(f"[{clip(lib.key(q.get('header')) or '', 40)}] {clip(qtext, 160)} → {clip(a, 80)}")
                if rid in pend_bash:
                    cmd, ts0 = pend_bash.pop(rid)
                    if t - ts0 > 120:
                        cur["slow"].append(f"{(t - ts0) / 60:.1f} min: {cmd}")
    segs.append(cur)
    tot_turns = sum(s["turns"] for s in segs)
    dur = (max((lib.ts(o) or 0) for o in evs) - t0) / 3600
    L = [f"# Session digest - {label}\n", f"File: `{path}`  ",
         f"{len(segs) - 1} messages from the user, {tot_turns} model replies, {dur:.1f} hours from first to last event.\n"]
    for i, s in enumerate(segs):
        L.append(f"## [{i}] +{s['t']:.0f} min · {s['turns']} replies · context {s['ctx'] // 1000}k")
        L.append(f"**User:** {s['human']}")
        if s["marks"]:
            L.append("**" + ", ".join(s["marks"]) + "**")
        if s["turns"]:
            L.append("Tools: " + ", ".join(f"{k} {v}" for k, v in s["tools"].most_common(6)))
        if s["skills"]:
            L.append("Skills: " + ", ".join(map(str, s["skills"])))
        for a in s["asks"]:
            L.append(f"Question: {a}")
        if s["agents"]:
            L.append(f"Subagents ({len(s['agents'])}): " + " | ".join(s["agents"][:5]))
        for sl in s["slow"][:4]:
            L.append(f"Slow command: {sl}")
        if s["last"]:
            L.append(f"**Claude stopped with:** {s['last']}")
        L.append("")
    text = "\n".join(L)
    if len(text) > 120_000:   # drop dull segments if the digest gets too large
        keep = []
        for blk in text.split("\n## ")[1:]:
            if any(m in blk for m in ("Question:", "Skills:", "Slow command", "COMPACTION", "Subagents")):
                keep.append("## " + blk)
            else:
                keep.append("## " + blk.split("\n")[0] + "\n" + "\n".join(blk.split("\n")[1:3]))
        text = "\n".join(L[:3]) + "\n" + "\n".join(keep)
    return text + "\n"


def report(scope: lib.Scope, session: str | None = None, top: int | None = None) -> str:
    if session:
        return digest(scope, os.path.expanduser(session))
    return longest(scope, top if top is not None else 3)
