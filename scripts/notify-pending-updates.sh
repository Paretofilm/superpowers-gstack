#!/bin/bash
# Check for pending manual update PRs/issues on Paretofilm/superpowers-gstack
# Used as a SessionStart hook notification
#
# Network calls (gh) run at most once per day: the rendered output is cached in
# CACHE_FILE, and while the cache is fresher than 24h we print it (possibly
# nothing) without touching the network. All failure paths stay silent so
# session start is never blocked.

CACHE_FILE="$HOME/.claude/.superpowers-gstack-notify-cache"

# Cache hit: fresher than 24h → print cached output (empty = no notifications)
if [ -f "$CACHE_FILE" ] && [ -n "$(find "$CACHE_FILE" -mtime -1 2>/dev/null)" ]; then
  cat "$CACHE_FILE" 2>/dev/null
  exit 0
fi

# Only run if gh is available and authenticated (cache the empty result so we
# don't re-check on every session start)
if ! command -v gh &>/dev/null || ! gh auth status &>/dev/null; then
  : > "$CACHE_FILE" 2>/dev/null
  exit 0
fi

# Detect repo from git remote (fallback to hardcoded)
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -d "$REPO_DIR/.git" ]; then
  REPO=$(cd "$REPO_DIR" && git remote get-url origin 2>/dev/null | sed 's|.*github.com[:/]||;s|\.git$||')
fi
REPO="${REPO:-Paretofilm/superpowers-gstack}"

# Check for open issues with notification label (public repo, works with any authenticated user)
notifications=$(gh issue list --repo "$REPO" --label notification --state open --json title,url,createdAt --limit 3 2>/dev/null)

if [ -z "$notifications" ] || [ "$notifications" = "[]" ]; then
  : > "$CACHE_FILE" 2>/dev/null
  exit 0
fi

{
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo " SUPERPOWERS/GSTACK MANUAL: Updates pending"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "$notifications" | python3 -c "
import json, sys
items = json.load(sys.stdin)
for item in items:
    print(f\"  • {item['title']}\")
    print(f\"    {item['url']}\")
    print()
" 2>/dev/null
  echo "Review and close issues after merging PRs."
  echo ""
} | tee "$CACHE_FILE" 2>/dev/null
exit 0
