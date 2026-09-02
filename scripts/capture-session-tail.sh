#!/usr/bin/env bash
# SessionEnd hook: salvage the tail of the session that is ending.
#
# The failure this exists for: /clear (or a plain exit) discards the in-memory
# context, and whatever happened after the last handoff/progress.md write is
# gone with it. No model is available at SessionEnd — hooks are shell-only —
# so this is a deterministic capture, not a resumé: the last user and
# assistant messages from the on-disk transcript, plus a git snapshot. The
# companion SessionStart hook (session-resume.sh) surfaces it next session.
#
# The capture is written INSIDE the git dir (.git/gstack-last-session.md),
# never into the working tree: transcript excerpts can contain anything, and
# a file that `git add -A` cannot reach cannot be committed by accident.
#
# Signal discipline: acts only in git repos that use the workflow (a
# docs/superpowers/ directory exists). Never fails the session — every path
# out of here is exit 0.
set -uo pipefail

command -v python3 >/dev/null 2>&1 || exit 0

# Read the hook payload from stdin BEFORE starting python: a heredoc would
# otherwise steal stdin, and the payload carries transcript_path and cwd.
PAYLOAD="$(cat 2>/dev/null || true)"
export PAYLOAD

python3 - <<'PY' 2>/dev/null || true
import json, os, subprocess, datetime

def sh(*args, cwd=None):
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    return r.stdout.strip() if r.returncode == 0 else None

try:
    payload = json.loads(os.environ.get("PAYLOAD", ""))
    if not isinstance(payload, dict):
        payload = {}
except Exception:
    payload = {}

cwd = payload.get("cwd") or os.getcwd()
if not os.path.isdir(cwd):
    raise SystemExit(0)

root = sh("git", "-C", cwd, "rev-parse", "--show-toplevel")
if not root or not os.path.isdir(os.path.join(root, "docs", "superpowers")):
    raise SystemExit(0)
gitdir = sh("git", "-C", cwd, "rev-parse", "--absolute-git-dir")
if not gitdir:
    raise SystemExit(0)

branch = sh("git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD") or "?"
head = sh("git", "-C", cwd, "log", "-1", "--format=%h %s") or "(no commits)"
status = sh("git", "-C", cwd, "status", "--porcelain") or ""
dirty = len(status.splitlines())

CAP = 700
def clip(text):
    text = " ".join(text.split())
    return text if len(text) <= CAP else text[:CAP] + " …[truncated]"

# Transcript lines are JSONL: {"type": "user"|"assistant", "message": {...}}.
# User content may be a plain string; assistant content is a block list where
# only "text" blocks are prose. Tool results are type "user" with no text
# blocks and fall through the empty-text check.
last_user = last_assistant = ""
try:
    with open(payload.get("transcript_path") or "", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except Exception:
                continue
            typ = entry.get("type")
            if typ not in ("user", "assistant"):
                continue
            content = (entry.get("message") or {}).get("content")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "\n".join(b.get("text", "") for b in content
                                 if isinstance(b, dict) and b.get("type") == "text")
            else:
                continue
            text = text.strip()
            if not text:
                continue
            if typ == "user":
                last_user = text
            else:
                last_assistant = text
except Exception:
    pass

now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
lines = [
    "# Last session capture (gstack)",
    f"- captured: {now}",
    f"- reason: {payload.get('reason') or 'unknown'}",
    f"- branch: {branch} @ {head}",
    f"- uncommitted: {dirty} file(s)",
    "",
]
if last_user:
    lines += ["## Last user message", clip(last_user), ""]
if last_assistant:
    lines += ["## Last assistant message", clip(last_assistant), ""]

with open(os.path.join(gitdir, "gstack-last-session.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
PY
exit 0
