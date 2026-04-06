#!/bin/bash
# Check for pending manual update PRs/issues on Paretofilm/superpowers-gstack
# Used as a SessionStart hook notification

# Only run if gh is available and authenticated
command -v gh &>/dev/null || exit 0
gh auth status &>/dev/null || exit 0

# Detect repo from git remote (fallback to hardcoded)
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -d "$REPO_DIR/.git" ]; then
  REPO=$(cd "$REPO_DIR" && git remote get-url origin 2>/dev/null | sed 's|.*github.com[:/]||;s|\.git$||')
fi
REPO="${REPO:-Paretofilm/superpowers-gstack}"

# Check for open issues with notification label (public repo, works with any authenticated user)
notifications=$(gh issue list --repo "$REPO" --label notification --state open --json title,url,createdAt --limit 3 2>/dev/null)

if [ -z "$notifications" ] || [ "$notifications" = "[]" ]; then
  exit 0
fi

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
