"""How much of all reused context is the baseline, and how much happens in long contexts?

Deduplicates on message.id (one model call = one call; the transcript has one event
per content block). For each file: F = context at the first model call. For each
call: C = total context. Baseline share = sum(min(F, C)) / sum(C). Long-session share
= sum(max(0, C - T)) / sum(C) for thresholds T.
"""
from __future__ import annotations

import collections
import statistics

from . import lib

THRESH = (150_000, 200_000, 300_000, 500_000)
EMPTY = "No transcripts in scope.\n"


def report(scope: lib.Scope) -> str:
    agg = collections.defaultdict(lambda: {"calls": 0, "base": 0, "ctx": 0, "first": [], "over": collections.Counter(), "n_over": collections.Counter()})
    files = 0
    for label, d, f, is_sub in lib.sessions(scope):
        files += 1
        F = None
        key = (label, "subagent" if is_sub else "main")
        for o, u, C in lib.api_calls(f):
            if not C:
                continue
            if F is None:
                F = C
                agg[key]["first"].append(F)
            a = agg[key]
            a["calls"] += 1
            a["base"] += min(F, C)
            a["ctx"] += C
            for t in THRESH:
                if C > t:
                    a["over"][t] += C - t
                    a["n_over"][t] += 1
    if not files:
        return EMPTY
    out = ["# Baseline and long contexts (deduplicated on message.id)\n",
           "| Project | type | model calls | median context at first call | baseline share | calls above 200k | context tokens above 200k |\n|---|---|---:|---:|---:|---:|---:|"]
    tot = collections.defaultdict(lambda: {"calls": 0, "base": 0, "ctx": 0, "over": collections.Counter(), "n_over": collections.Counter()})
    for (label, kind), v in sorted(agg.items(), key=lambda x: -x[1]["ctx"]):
        out.append(f"| {label} | {kind} | {v['calls']:,} | {statistics.median(v['first']) / 1000:.0f}k | {v['base'] / v['ctx']:.0%} | {v['n_over'][200_000] / v['calls']:.0%} | {v['over'][200_000] / v['ctx']:.0%} |")
        t = tot[kind]
        t["calls"] += v["calls"]
        t["base"] += v["base"]
        t["ctx"] += v["ctx"]
        for th in THRESH:
            t["over"][th] += v["over"][th]
            t["n_over"][th] += v["n_over"][th]
    out.append("")
    for kind, t in tot.items():
        out.append(f"{kind}: {t['calls']:,} model calls, {t['ctx'] / 1e9:.2f} billion context tokens reused; the baseline alone {t['base'] / 1e9:.2f} billion ({t['base'] / t['ctx']:.0%}).")
        for th in THRESH:
            out.append(f"- {kind}: {t['n_over'][th] / t['calls']:.0%} of calls happen above {th // 1000}k; context above {th // 1000}k is {t['over'][th] / t['ctx']:.0%} of all context tokens.")
        out.append("")
    return "\n".join(out) + "\n"
