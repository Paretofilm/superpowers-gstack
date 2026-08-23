#!/bin/bash
# Check if the project's CLAUDE.md was generated with an older plugin version
# Used as a SessionStart hook — runs in the project directory

# Surface pending cost-ledger notices (lens skips / auto-reverts written by
# tune.py/monitor.py) BEFORE the early exits below — the notices file is
# user-global and must be shown regardless of which project the session
# starts in. Read-and-clear, mirroring the handoff.md pattern.
NOTICES="$HOME/.claude/cost-ledger/session_notices.txt"
if [ -s "$NOTICES" ]; then
  # mv is atomic on the same filesystem — an append landing after the mv goes
  # to a fresh file and survives for the next session (no read-then-clear race)
  _NTMP=$(mktemp "${NOTICES}.XXXXXX" 2>/dev/null) && mv "$NOTICES" "$_NTMP" 2>/dev/null && {
    # read + delete BEFORE printing — if the consumer closes the pipe early
    # (SIGPIPE), the tmp file must not leak
    _NOTICE_CONTENT=$(cat "$_NTMP")
    rm -f "$_NTMP"
    echo "📒 cost-ledger notices since last session:"
    printf '%s\n\n' "$_NOTICE_CONTENT"
  }
fi

CLAUDE_MD="CLAUDE.md"

# Only run if CLAUDE.md exists and uses superpowers-gstack
[ -f "$CLAUDE_MD" ] || exit 0
grep -qiE "Skill routing|superpowers|gstack|/review|/ship|/adapt" "$CLAUDE_MD" || exit 0

# The plugin's own dev repo IS the source of the routing — its CLAUDE.md is always
# current by definition and carries no generated version marker. Without this
# exemption the hook nags "run /adapt" at every session start in the plugin repo.
if [ -f ".claude-plugin/plugin.json" ] && grep -q '"name": "superpowers-gstack"' ".claude-plugin/plugin.json" 2>/dev/null; then
  exit 0
fi

# Find installed plugin version from cache
plugin_json=$(find ~/.claude/plugins/cache -path "*/superpowers-gstack/*/plugin.json" 2>/dev/null | sort -V | tail -1)
[ -n "$plugin_json" ] || exit 0

plugin_version=$(python3 -c "import json; print(json.load(open('$plugin_json'))['version'])" 2>/dev/null)
[ -n "$plugin_version" ] || exit 0

# Extract version from marker in CLAUDE.md (may not exist in older setups)
project_version=$(grep -oE 'superpowers-gstack: [0-9]+\.[0-9]+\.[0-9]+' "$CLAUDE_MD" | head -1 | awk '{print $2}')

# No marker at all = old setup, needs update
if [ -z "$project_version" ]; then
  echo "⚠️  superpowers-gstack v$plugin_version is installed, but this project's rules were never generated."
  echo "   Offer to run /superpowers-gstack:adapt now and carry it out on a yes — it sets up routing and"
  echo "   session rules, preserves everything already in CLAUDE.md, and normally asks nothing."
  echo ""
  exit 0
fi

# Compare versions
if [ "$project_version" != "$plugin_version" ]; then
  echo "⚠️  superpowers-gstack updated ($project_version → $plugin_version), but this project still runs the old rules."
  echo "   Offer to run /superpowers-gstack:adapt now and carry it out on a yes — it upgrades the rules in"
  echo "   place, preserves everything already in CLAUDE.md, and normally asks nothing. Until then, where"
  echo "   this project's older copied rules disagree with the plugin's current hooks and skills, the"
  echo "   plugin's current behavior wins."
  echo ""
fi
