"""How often does Claude stop and wait for you, and how often do you just answer "recommended"?

Measures (main sessions only, not subagents):
  - AskUserQuestion: count, share answered with the recommended option, share free-text answers, per active skill
  - Your messages (origin.kind == human): count, share of short approvals ("ja", "recommended", "a" ...)
  - Autonomous stretch: model replies between two of your messages
"""
from __future__ import annotations

import collections
import json
import re
import statistics

from . import lib

APPROVE = re.compile(r"^(ja|ja takk|jepp|ok|okay|anbefalt|anbefalte|anbefaling|kjør|kjør på|kjør på da|go|yes|y|a|b|c|d|[1-9]|fortsett|enig|bra|greit|gjør det|start|neste|alt|alle|begge|go for it|ja alle|do it|sounds good|lgtm|godkjent)[.! ]*$", re.I)
ANS = re.compile(r'"((?:[^"\\]|\\.)*)"="((?:[^"\\]|\\.)*)"', re.S)
EMPTY = "No transcripts in scope.\n"


def report(scope: lib.Scope) -> str:
    ask_calls = collections.Counter()
    q_total = collections.Counter()
    q_rec = collections.Counter()
    q_free = collections.Counter()
    q_other = collections.Counter()
    ctx_q = collections.defaultdict(lambda: [0, 0])   # skill -> [questions, recommended]
    human = collections.Counter()
    approve = collections.Counter()
    after_q = collections.Counter()
    approve_after_q = collections.Counter()
    stretch = collections.defaultdict(list)
    sessions_n = collections.Counter()
    examples = collections.defaultdict(list)
    for label, d, f, is_sub in lib.sessions(scope, include_sub=False):
        sessions_n[label] += 1
        active = None
        pend = {}
        turns_since = 0
        had_human = False
        last_assistant_q = False
        seen_ids = set()
        for o in lib.events(f):
            ty = o.get("type")
            if ty == "assistant":
                mid = lib.msg_id(o)
                if mid is None or mid not in seen_ids:   # one model call counts once (one event per block)
                    turns_since += 1
                    if mid is not None:
                        seen_ids.add(mid)
                txt = lib.text_of(o).strip()
                has_tool = any(b.get("type") == "tool_use" for b in lib.blocks(o))
                if txt and not has_tool:
                    last_assistant_q = txt.rstrip().endswith("?")
                for b in lib.blocks(o):
                    if b.get("type") == "tool_use":
                        if b.get("name") == "Skill":
                            active = (b.get("input") or {}).get("skill")
                        if b.get("name") == "AskUserQuestion":
                            pend[b["id"]] = (b.get("input") or {}, active)
                            ask_calls[label] += 1
            elif ty == "user":
                for b in lib.blocks(o):
                    if b.get("type") == "tool_result" and b.get("tool_use_id") in pend:
                        inp, act = pend.pop(b["tool_use_id"])
                        res = b.get("content")
                        res = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False)
                        answers = {q: a for q, a in ANS.findall(res)}
                        for q in inp.get("questions", []):
                            qt = q.get("question", "")
                            labels = [x.get("label", "") for x in q.get("options", [])]
                            a = answers.get(qt.replace('"', '\\"')) or answers.get(qt)
                            if a is None and len(answers) == 1:
                                a = list(answers.values())[0]
                            if a is None:
                                continue
                            q_total[label] += 1
                            ctx_q[act or "(no skill)"][0] += 1
                            if "(Recommended)" in a or (labels and a == labels[0]):
                                q_rec[label] += 1
                                ctx_q[act or "(no skill)"][1] += 1
                            elif a in labels:
                                q_other[label] += 1
                            else:
                                q_free[label] += 1
                if lib.is_human(o):
                    t = lib.text_of(o).strip()
                    human[label] += 1
                    short = bool(APPROVE.match(t)) or (len(t.split()) <= 3 and len(t) <= 24 and re.search(r"anbefalt|\bja\b|\bok\b", t, re.I))
                    if short:
                        approve[label] += 1
                    if last_assistant_q:
                        after_q[label] += 1
                        if short:
                            approve_after_q[label] += 1
                    if had_human:
                        stretch[label].append(turns_since)
                    had_human = True
                    turns_since = 0
                    last_assistant_q = False
                    if len(examples[label]) < 6 and short:
                        examples[label].append(t[:40])
    if not sessions_n:
        return EMPTY
    out = ["# Questions and stops\n", "Main sessions only (not subagents).\n",
           "## Structured questions (AskUserQuestion)\n", "| Project | sessions | calls | questions | recommended chosen | other option | own answer |\n|---|---:|---:|---:|---:|---:|---:|"]
    for label in sorted(sessions_n):
        out.append(f"| {label} | {sessions_n[label]} | {ask_calls[label]} | {q_total[label]} | {lib.pct(q_rec[label], q_total[label])} ({q_rec[label]}) | {lib.pct(q_other[label], q_total[label])} | {lib.pct(q_free[label], q_total[label])} |")
    T, R = sum(q_total.values()), sum(q_rec.values())
    out.append(f"\nTotal: {T} questions, {lib.pct(R, T)} answered with the recommended option.\n")
    out.append("## Which skill asked (active skill when the question came)\n\n| Active skill | questions | recommended |\n|---|---:|---:|")
    for s, (n, r) in sorted(ctx_q.items(), key=lambda x: -x[1][0])[:14]:
        out.append(f"| {s} | {n} | {lib.pct(r, n)} |")
    out.append("\n## Your own messages\n\n| Project | messages | short approvals | messages right after a question from Claude | …of which short approvals | median model replies between your messages | p90 |\n|---|---:|---:|---:|---:|---:|---:|")
    for label in sorted(human):
        st = sorted(stretch[label])
        p90 = st[int(len(st) * 0.9) - 1] if st else 0
        out.append(f"| {label} | {human[label]} | {lib.pct(approve[label], human[label])} | {after_q[label]} | {lib.pct(approve_after_q[label], after_q[label])} | {statistics.median(st) if st else '–'} | {p90} |")
    H, A = sum(human.values()), sum(approve.values())
    AQ, AAQ = sum(after_q.values()), sum(approve_after_q.values())
    out.append(f"\nTotal: {H} messages from you; {lib.pct(A, H)} are short approvals; {lib.pct(AAQ, AQ)} of the replies right after a question are.\n")
    out.append("Examples of short approvals: " + "; ".join(f"“{e}”" for a in sorted(examples) for e in examples[a][:2]) + "\n")
    return "\n".join(out) + "\n"
