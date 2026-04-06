#!/bin/bash
# Check for pending manual update PRs/issues on kjetilge/superpowers-gstack
# Used as a SessionStart hook notification

# Only run if gh is available and authenticated
command -v gh &>/dev/null || exit 0

# Check for open issues with notification label
notifications=$(gh issue list --repo kjetilge/superpowers-gstack --label notification --state open --json title,url,createdAt --limit 3 2>/dev/null)

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
