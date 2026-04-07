#!/bin/bash
# Configure the SessionStart hook for update notifications
# Adds the notify-pending-updates.sh script to ~/.claude/settings.json

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NOTIFY_SCRIPT="$REPO_DIR/scripts/notify-pending-updates.sh"
VERSION_CHECK_SCRIPT="$REPO_DIR/scripts/check-plugin-version.sh"
SETTINGS_FILE="$HOME/.claude/settings.json"

# Verify scripts exist
if [ ! -f "$NOTIFY_SCRIPT" ]; then
  echo "Error: $NOTIFY_SCRIPT not found"
  exit 1
fi
if [ ! -f "$VERSION_CHECK_SCRIPT" ]; then
  echo "Error: $VERSION_CHECK_SCRIPT not found"
  exit 1
fi

# Create settings file if missing
if [ ! -f "$SETTINGS_FILE" ]; then
  mkdir -p "$(dirname "$SETTINGS_FILE")"
  echo '{}' > "$SETTINGS_FILE"
fi

# Add hooks (skip any already configured)
python3 << PYEOF
import json

settings_path = "$SETTINGS_FILE"
scripts = {
    "notify-pending-updates": "$NOTIFY_SCRIPT",
    "check-plugin-version": "$VERSION_CHECK_SCRIPT",
}

with open(settings_path) as f:
    settings = json.load(f)

if "hooks" not in settings:
    settings["hooks"] = {}
if "SessionStart" not in settings["hooks"]:
    settings["hooks"]["SessionStart"] = []

existing = [h.get("command", "") for h in settings["hooks"]["SessionStart"]]
added = []

for name, script in scripts.items():
    if not any(name in cmd for cmd in existing):
        settings["hooks"]["SessionStart"].append({
            "type": "command",
            "command": script
        })
        added.append(name)

if added:
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    for name in added:
        print(f"  Added: {name}")
    print(f"\nHooks saved to {settings_path}")
    print("Restart Claude Code to activate.")
else:
    print("All hooks already configured.")
PYEOF
