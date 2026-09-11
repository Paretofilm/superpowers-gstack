#!/bin/bash
# Check if the project's CLAUDE.md was generated with an older plugin version
# Used as a SessionStart hook — runs in the project directory

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

# The version that is RUNNING, not the newest one on disk. hooks.json invokes this
# script as ${CLAUDE_PLUGIN_ROOT}/scripts/..., so that variable already names the plugin
# root this session resolved at startup — and a session keeps that root even after a
# newer version lands in the cache (observed: a session served 2.51.1 while
# installed_plugins.json said 2.53.1; the cache holds nine versions, all runnable).
#
# Taking the cache's newest instead produced a nudge that could never be satisfied:
# it told the user to run /adapt to reach a version their /adapt does not come from,
# so /adapt wrote the running version's marker back and the next session nudged again.
# "Different" is not "older", and a self-heal keyed on difference can be a downgrade.
plugin_json=""
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json" ]; then
  plugin_json="$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json"
else
  # Not running as a plugin hook (direct invocation, a test). Fall back to the cache's
  # newest — the old behaviour, and the best guess available without a root.
  plugin_json=$(find ~/.claude/plugins/cache -path "*/superpowers-gstack/*/plugin.json" 2>/dev/null | sort -V | tail -1)
fi
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
