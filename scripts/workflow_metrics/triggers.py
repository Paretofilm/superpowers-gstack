"""Who triggers the build and test runs? (xcodebuild, swift test/build, vm-e2e, vm-run)

For every real build/test command in Bash:
  - subagent: was the command in the brief the subagent got, or did it act on its own?
  - main session: which skill was active, and how long since the user's last message?
Time = timestamp from tool call to result (waiting included).
"""
from __future__ import annotations

import collections
import re
import statistics

from . import lib

EMPTY = "No transcripts in scope.\n"
CMD = re.compile(r"(^|&&|;|\|\||\n|\()\s*(?:[A-Z_]+=\S+\s+)*(xcodebuild|swift\s+(?:test|build)|vm-e2e|vm-run)\b")


def kind(cmd):
    m = CMD.search(cmd) if isinstance(cmd, str) else None
    return re.sub(r"\s+", " ", m.group(2)) if m else None


def mentions(prompt, k):
    if k == "xcodebuild":
        return bool(re.search(r"xcodebuild|build-for-testing|UITest|XCUITest|xcresult", prompt, re.I))
    if k.startswith("swift"):
        return bool(re.search(r"swift (test|build)|enhetstest|unit test", prompt, re.I))
    return bool(re.search(r"vm-e2e|vm-run|e2e|guest", prompt, re.I))


def report(scope: lib.Scope) -> str:
    rows = []   # (label, kind, where, why, secs, gap)
    files = 0
    for label, d, f, is_sub in lib.sessions(scope):
        files += 1
        prompt = ""
        active = None
        last_human = None
        pend = {}
        first_user = True
        for o in lib.events(f):
            t = lib.ts(o)
            if o.get("type") == "user":
                has_result = any(b.get("type") == "tool_result" for b in lib.blocks(o))
                if is_sub and first_user and not has_result:
                    prompt = lib.text_of(o)
                    first_user = False
                if not is_sub and lib.is_human(o):
                    last_human = t
            for b in lib.blocks(o):
                if b.get("type") == "tool_use":
                    if b.get("name") == "Skill":
                        active = str(lib.tool_input(b).get("skill"))
                    if b.get("name") == "Bash":
                        k = kind(lib.tool_input(b).get("command", ""))
                        bid = lib.key(b.get("id"))
                        if k and bid:
                            pend[bid] = (k, t, active, last_human)
                elif b.get("type") == "tool_result":
                    rid = lib.key(b.get("tool_use_id"))
                    if rid not in pend:
                        continue
                    k, t0, act, lh = pend.pop(rid)
                    secs = (t - t0) if (t and t0 and 0 <= t - t0 < 3600) else 0
                    if is_sub:
                        why = "instructed in the brief" if mentions(prompt, k) else "the subagent's own initiative"
                    else:
                        why = f"main session, active skill: {act or '(none)'}"
                    rows.append((label, k, "subagent" if is_sub else "main", why, secs, (t0 - lh) if (lh and t0) else None))
    if not files:
        return EMPTY
    out = ["# Who triggers builds and tests?\n"]
    if not rows:
        out.append("No build or test commands found in scope.")
        return "\n".join(out) + "\n"
    tot = collections.Counter()
    tsec = collections.Counter()
    for r in rows:
        tot[r[2]] += 1
        tsec[r[2]] += r[4]
    out.append(f"{len(rows)} commands, {sum(r[4] for r in rows) / 3600:.1f} hours elapsed. Subagents: {tot['subagent']} calls / {tsec['subagent'] / 3600:.1f} h; main sessions: {tot['main']} calls / {tsec['main'] / 3600:.1f} h.\n")
    out.append("## Per project and command\n\n| Project | command | calls | hours | mean s | >5 min |\n|---|---|---:|---:|---:|---:|")
    agg = collections.defaultdict(list)
    for r in rows:
        agg[(r[0], r[1])].append(r[4])
    for (label, k), v in sorted(agg.items(), key=lambda x: (-sum(x[1]), x[0])):
        out.append(f"| {label} | {k} | {len(v)} | {sum(v) / 3600:.1f} | {sum(v) / len(v):.0f} | {sum(1 for x in v if x > 300)} |")
    out.append("\n## Why did it run?\n\n| Reason | calls | hours |\n|---|---:|---:|")
    why = collections.defaultdict(lambda: [0, 0.0])
    for r in rows:
        why[r[3]][0] += 1
        why[r[3]][1] += r[4]
    for w, (n, s) in sorted(why.items(), key=lambda x: (-x[1][1], x[0]))[:12]:
        out.append(f"| {w} | {n} | {s / 3600:.1f} |")
    gaps = [r[5] for r in rows if r[2] == "main" and r[5] is not None]
    if gaps:
        out.append(f"\nMain sessions: median {statistics.median(gaps) / 60:.0f} min from the user's last message to the command "
                   f"({sum(1 for g in gaps if g > 1800) / len(gaps):.0%} started more than 30 min after it, i.e. without the user asking).")
    return "\n".join(out) + "\n"
