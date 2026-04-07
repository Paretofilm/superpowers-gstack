#!/bin/bash
# Check if the project's CLAUDE.md was generated with an older plugin version
# Used as a SessionStart hook — runs in the project directory

CLAUDE_MD="CLAUDE.md"

# Only run if CLAUDE.md exists and has our version marker
[ -f "$CLAUDE_MD" ] || exit 0
grep -q "superpowers-gstack:" "$CLAUDE_MD" || exit 0

# Extract version from marker in CLAUDE.md
project_version=$(grep -oE 'superpowers-gstack: [0-9]+\.[0-9]+\.[0-9]+' "$CLAUDE_MD" | head -1 | awk '{print $2}')
[ -n "$project_version" ] || exit 0

# Find installed plugin version from cache
plugin_json=$(find ~/.claude/plugins/cache -path "*/superpowers-gstack/*/plugin.json" 2>/dev/null | sort -V | tail -1)
[ -n "$plugin_json" ] || exit 0

plugin_version=$(python3 -c "import json; print(json.load(open('$plugin_json'))['version'])" 2>/dev/null)
[ -n "$plugin_version" ] || exit 0

# Compare versions
if [ "$project_version" != "$plugin_version" ]; then
  echo "⚠️  superpowers-gstack updated ($project_version → $plugin_version). Run /adapt to update routing and session rules."
  echo ""
fi
