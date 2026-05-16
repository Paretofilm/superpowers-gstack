#!/bin/bash
# PostToolUse hook for htmlify.
#
# Reads Claude Code's hook JSON from stdin. When a Write or Edit creates/modifies
# an MD file matching known artifact patterns (design-*.md, handoff.md, plan-*.md,
# or .gstack/projects/<slug>/*-design-*.md), regenerate the HTML companion + dashboard.
#
# Loop prevention: ignore writes to .superpowers-html/* (those are our outputs).
#
# This hook is best-effort: fails silently to never block Claude Code's main flow.

set +e  # never exit non-zero — Claude Code would treat it as blocking

# Locate the htmlify CLI: this script lives in <repo>/scripts/, CLI lives in
# <repo>/skills/htmlify/src/cli.ts.
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$REPO_DIR/skills/htmlify/src/cli.ts"

if [ ! -f "$CLI" ]; then
  exit 0  # skill not installed yet — silently skip
fi

if ! command -v bun >/dev/null 2>&1; then
  exit 0  # bun missing — silently skip
fi

# Check node_modules. If missing, the hook can't run — exit silently.
if [ ! -d "$REPO_DIR/skills/htmlify/node_modules" ]; then
  exit 0
fi

# Read hook JSON from stdin
INPUT=""
if [ -t 0 ]; then
  exit 0  # no stdin — nothing to do
fi
INPUT=$(cat)

# Extract tool_name and file_path. Use python for robust JSON parsing.
DATA=$(python3 - <<'PYEOF' 2>/dev/null
import json, sys
try:
    data = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

tool = data.get("tool_name", "")
inp = data.get("tool_input", {}) or {}
fp = inp.get("file_path", "") or ""

# Only act on Write/Edit
if tool not in ("Write", "Edit", "MultiEdit"):
    sys.exit(0)

# Only act on .md
if not fp.endswith(".md"):
    sys.exit(0)

# Loop prevention: ignore .superpowers-html/ outputs
if "/.superpowers-html/" in fp or fp.startswith(".superpowers-html/"):
    sys.exit(0)

# Filename filter: match known artifact patterns
import os, re
base = os.path.basename(fp)
artifact = False
if base == "handoff.md":
    artifact = True
elif re.search(r"-design-\d{8}-\d{6}\.md$", base):
    artifact = True
elif re.search(r"-plan-\d{8}-\d{6}\.md$", base):
    artifact = True
elif re.search(r"-eng-review-test-plan-\d{8}-\d{6}\.md$", base):
    artifact = True
elif "/.gstack/projects/" in fp and base.endswith(".md"):
    # any MD under .gstack/projects is an artifact
    artifact = True

if not artifact:
    sys.exit(0)

print(fp)
PYEOF
<<<"$INPUT")

if [ -z "$DATA" ]; then
  exit 0
fi

MD_PATH="$DATA"
MD_DIR="$(dirname "$MD_PATH")"

# Fire htmlify --open in background (don't block Claude Code)
(
  cd "$REPO_DIR/skills/htmlify" || exit 0
  bun run src/cli.ts --open "$MD_PATH" >/dev/null 2>&1 &
  bun run src/cli.ts dashboard "$MD_DIR" >/dev/null 2>&1 &
) &

exit 0
