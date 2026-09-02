#!/usr/bin/env bash
# SessionStart hook: show where the project left off, before the user asks.
#
# The failure this exists for: progress.md and handoff.md can be rich and
# current, and the session still opens in silence — the model-driven Session
# Continuity flow only speaks in the first reply, AFTER the user has typed
# something. The trust moment is startup itself. SessionStart stdout is both
# shown in the terminal and injected into the model's context, so one banner
# serves the user (proof the state survived) and the agent (what to expand).
#
# Three sources, all optional, all read-only — classification and consumption
# of handoff.md remain the model's job per the Session Continuity rules:
#   1. docs/superpowers/plans/progress.md   (rolling phase file)
#   2. docs/superpowers/handoff.md          (only if it is a complete handoff)
#   3. <git-dir>/gstack-last-session.md     (SessionEnd tail capture)
#
# Signal discipline: silent unless at least one source has something to say.
# Never fails the session — every path out of here is exit 0.
set -uo pipefail

command -v python3 >/dev/null 2>&1 || exit 0

python3 - <<'PY' 2>/dev/null || true
import datetime, os, re, subprocess

def sh(*args):
    r = subprocess.run(args, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None

root = sh("git", "rev-parse", "--show-toplevel")
gitdir = sh("git", "rev-parse", "--absolute-git-dir")
if not root or not gitdir:
    raise SystemExit(0)

sections = []

def item_text(line):
    """'3. **Upgrade-test dev→staging**: kjør scriptet.' → 'Upgrade-test dev→staging'"""
    text = re.sub(r"^\s*(?:\d+\.|[-*])\s*(?:\[.\]\s*)?", "", line).strip()
    m = re.match(r"\*\*(.+?)\*\*", text)
    if m:
        return m.group(1).strip()
    return text.split(":")[0].strip()[:70] or text[:70]

progress = os.path.join(root, "docs", "superpowers", "plans", "progress.md")
if os.path.isfile(progress):
    try:
        lines = open(progress, encoding="utf-8", errors="replace").read().splitlines()
        updated = datetime.date.fromtimestamp(os.path.getmtime(progress)).isoformat()
        title = next((l[2:].strip() for l in lines if l.startswith("# ")), "progress.md")
        completed, next_item, section = 0, "", ""
        for line in lines:
            if re.match(r"^##+\s", line):
                low = line.lower()
                section = ("done" if re.search(r"fullf|completed", low)
                           else "todo" if re.search(r"gjenst|remaining", low) else "")
                continue
            if re.match(r"^\s*(?:\d+\.|[-*])\s+\S", line):
                # Items struck through or checked off are finished even when
                # they still sit in the remaining section — real progress
                # files mark done-out-of-order work exactly like that. Only
                # whole-item markers count (leading ~~ or [x]): a checkmark
                # mid-text means partially done, and that IS the next phase.
                finished = bool(re.match(r"^\s*(?:\d+\.|[-*])\s*(?:\[x\]|~~)",
                                         line, re.IGNORECASE))
                if section == "done":
                    completed += 1
                elif section == "todo" and not next_item and not finished:
                    next_item = item_text(line)
        body = [f"  progress.md: {title}"]
        if completed or next_item:
            detail = f"{completed} phase(s) completed"
            if next_item:
                detail += f" · next: {next_item}"
            body.append(f"      {detail}")
        body.append(f"      updated {updated}")
        sections.append("\n".join(body))
    except Exception:
        pass

handoff = os.path.join(root, "docs", "superpowers", "handoff.md")
if os.path.isfile(handoff):
    try:
        text = open(handoff, encoding="utf-8", errors="replace").read()
        m = re.match(r"\s*---\n(.*?)\n---", text, re.DOTALL)
        front = m.group(1) if m else ""
        keys = dict(re.findall(r"^(\w+):\s*(.*)$", front, re.MULTILINE))
        next_step = keys.get("next_step", "").strip().strip('"').strip("'")
        # Legacy form (session_end + next_step) counts ONLY when type: is
        # absent — `type: notes` beside those keys is a different artifact.
        is_handoff = (keys.get("type") == "handoff"
                      or ("type" not in keys and "session_end" in keys))
        if is_handoff and next_step:
            sections.append(f'  handoff.md next step:\n      "{next_step}"')
    except Exception:
        pass

capture = os.path.join(gitdir, "gstack-last-session.md")
if os.path.isfile(capture):
    try:
        lines = open(capture, encoding="utf-8", errors="replace").read().splitlines()
        meta = dict(re.findall(r"^- (\w+): (.*)$", "\n".join(lines), re.MULTILINE))
        tail = ""
        for i, line in enumerate(lines):
            if line.startswith("## Last assistant message"):
                tail = " ".join(l for l in lines[i + 1:] if l and not l.startswith("#"))
                break
        body = [f"  Last activity before previous session ended "
                f"({meta.get('reason', '?')}, {meta.get('captured', '?')}):"]
        if tail:
            body.append(f"      {tail[:200]}")
        if meta.get("branch"):
            body.append(f"      was on: {meta['branch']}")
        sections.append("\n".join(body))
    except Exception:
        pass

if not sections:
    raise SystemExit(0)

bar = "━" * 42
print(bar)
print(" Where this project left off")
print(bar)
print()
print("\n".join(sections))
print()
print("  Agent: if the user's first message continues this work, expand from")
print("  these files before proceeding. Session Continuity rules in CLAUDE.md")
print("  govern handoff.md (classify before touching; this banner consumed nothing).")
PY
exit 0
