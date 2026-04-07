#!/bin/bash
# Check for updates to GStack, Superpowers, and Claude Code
# Run periodically to detect changes that may require manual updates

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_FILE="$REPO_DIR/.update-state.json"
REPORT=""
CHANGES_FOUND=false

# Initialize state file if missing
if [ ! -f "$STATE_FILE" ]; then
  cat > "$STATE_FILE" << 'EOF'
{
  "gstack_commit": "",
  "claude_code_version": "",
  "superpowers_hash": "",
  "last_check": ""
}
EOF
fi

prev_gstack=$(jq -r '.gstack_commit' "$STATE_FILE")
prev_claude=$(jq -r '.claude_code_version' "$STATE_FILE")
prev_superpowers=$(jq -r '.superpowers_hash' "$STATE_FILE")

# --- GStack ---
GSTACK_DIR="$HOME/.claude/skills/gstack"
if [ -d "$GSTACK_DIR/.git" ]; then
  cd "$GSTACK_DIR"
  git fetch origin --quiet 2>/dev/null || true
  current_gstack=$(git rev-parse HEAD)
  remote_gstack=$(git rev-parse origin/main 2>/dev/null || echo "$current_gstack")

  if [ "$current_gstack" != "$prev_gstack" ] || [ "$current_gstack" != "$remote_gstack" ]; then
    CHANGES_FOUND=true
    if [ "$current_gstack" != "$remote_gstack" ]; then
      new_commits=$(git log --oneline "$current_gstack..$remote_gstack" 2>/dev/null | head -20)
      REPORT+="## GStack: remote update available\n\nCurrent: $(git log --oneline -1 $current_gstack)\nNew commits on origin/main:\n\`\`\`\n$new_commits\n\`\`\`\n\nRun: \`cd ~/.claude/skills/gstack && git pull && ./setup\`\n\n"
    elif [ "$current_gstack" != "$prev_gstack" ]; then
      changes=$(git log --oneline "$prev_gstack..$current_gstack" 2>/dev/null | head -20)
      REPORT+="## GStack: updated since last check\n\nNew commits:\n\`\`\`\n$changes\n\`\`\`\n\n"
    fi
  fi
  cd "$REPO_DIR"
else
  REPORT+="## GStack: not found at $GSTACK_DIR\n\n"
fi

# --- Claude Code ---
current_claude=$(claude --version 2>/dev/null | head -1 | awk '{print $1}' || echo "unknown")
if [ "$current_claude" != "$prev_claude" ] && [ "$prev_claude" != "" ]; then
  CHANGES_FOUND=true
  REPORT+="## Claude Code: version changed\n\nPrevious: $prev_claude\nCurrent: $current_claude\n\nCheck release notes for changes that may affect plugin loading, skill discovery, or context window.\n\n"
fi

# --- Superpowers ---
SUPERPOWERS_DIR=""
for dir in "$HOME/.claude/plugins/cache/claude-plugins-official/superpowers"/* "$HOME/.claude/plugins/cache/"*"/superpowers"/*; do
  if [ -d "$dir" ] 2>/dev/null; then
    SUPERPOWERS_DIR="$dir"
    break
  fi
done

if [ -n "$SUPERPOWERS_DIR" ] && [ -d "$SUPERPOWERS_DIR" ]; then
  current_superpowers=$(find "$SUPERPOWERS_DIR" -name "SKILL.md" -exec md5 -q {} \; 2>/dev/null | sort | md5 -q)
  if [ "$current_superpowers" != "$prev_superpowers" ] && [ "$prev_superpowers" != "" ]; then
    CHANGES_FOUND=true
    REPORT+="## Superpowers: skill files changed\n\nHash changed from $prev_superpowers to $current_superpowers.\nReview skill changes: \`ls $SUPERPOWERS_DIR/skills/\`\n\n"
  fi
else
  current_superpowers="$prev_superpowers"
fi

# --- Save state ---
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
cat > "$STATE_FILE" << EOF
{
  "gstack_commit": "${current_gstack:-$prev_gstack}",
  "claude_code_version": "$current_claude",
  "superpowers_hash": "$current_superpowers",
  "last_check": "$now"
}
EOF

# --- Ensure plugin is installed ---
"$REPO_DIR/scripts/install-plugin.sh" 2>/dev/null || true

# --- Output ---
if [ "$CHANGES_FOUND" = true ]; then
  echo "---"
  echo "# Update Report — $(date +%Y-%m-%d)"
  echo ""
  echo -e "$REPORT"
  echo "### Action needed"
  echo "Review changes above and update README.md if affected."
  exit 2  # Signal: changes found
else
  echo "No updates detected. Last check: $now"
  exit 0
fi
