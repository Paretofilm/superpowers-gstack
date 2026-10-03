"""Token and session overview per project, deduplicated on message.id."""
from __future__ import annotations

import collections
import statistics

from . import lib

EMPTY = "No transcripts in scope.\n"


def report(scope: lib.Scope) -> str:
    A = collections.defaultdict(collections.Counter)
    per_sess = collections.defaultdict(list)
    ctx = collections.defaultdict(list)
    tool_calls = collections.Counter()
    files = 0
    for label, d, f, is_sub in lib.sessions(scope):
        files += 1
        kind = "sub" if is_sub else "main"
        n = 0
        s = 0
        for o, u, C in lib.api_calls(f):
            if not C:
                continue
            a = A[label]
            a[kind + "_calls"] += 1
            a[kind + "_ctx"] += C
            a[kind + "_out"] += lib._int(u.get("output_tokens"))
            a[kind + "_cr"] += lib._int(u.get("cache_read_input_tokens"))
            a[kind + "_cc"] += lib._int(u.get("cache_creation_input_tokens"))
            n += 1
            s += C
        if not is_sub and n:
            per_sess[label].append(n)
            ctx[label].append(s / n)
        # tool calls: tool_use blocks have unique ids, no dedup needed
        for o in lib.events(f):
            for b in lib.blocks(o):
                if b.get("type") == "tool_use":
                    tool_calls[(label, str(b.get("name")))] += 1
    if not files:
        return EMPTY
    out = ["# Tokens and sessions per project (deduplicated on message.id)\n",
           "| Project | model calls (main / sub) | output tokens | reused context (cache_read) | new context written (cache_creation) | subagent share of cache_read | main sessions | median calls/session | median context/call |\n|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for label, a in sorted(A.items(), key=lambda x: -(x[1]["main_cr"] + x[1]["sub_cr"])):
        cr = a["main_cr"] + a["sub_cr"]
        ps = per_sess[label]
        cx = ctx[label]
        out.append(f"| {label} | {a['main_calls']:,} / {a['sub_calls']:,} | {(a['main_out'] + a['sub_out']) / 1e6:.1f} M | {cr / 1e9:.2f} G | {(a['main_cc'] + a['sub_cc']) / 1e6:.0f} M | {lib.pct(a['sub_cr'], cr)} | {len(ps)} | {statistics.median(ps) if ps else 0:.0f} (max {max(ps) if ps else 0}) | {statistics.median(cx) / 1000 if cx else 0:.0f}k |")
    tot = collections.Counter()
    for a in A.values():
        tot.update(a)
    calls = tot["main_calls"] + tot["sub_calls"]
    out_t = tot["main_out"] + tot["sub_out"]
    cr = tot["main_cr"] + tot["sub_cr"]
    cc = tot["main_cc"] + tot["sub_cc"]
    out.append(f"\nTotal: {calls:,} model calls; output {out_t / 1e6:.1f} M; cache_read {cr / 1e9:.2f} G; cache_creation {cc / 1e6:.0f} M.")
    out.append("\n## Tool calls (top 6 per project)\n")
    for label in sorted(A):
        top = sorted(((n, c) for (a, n), c in tool_calls.items() if a == label), key=lambda x: -x[1])[:6]
        out.append(f"- {label}: " + ", ".join(f"{n} {c}" for n, c in top))
    return "\n".join(out) + "\n"
