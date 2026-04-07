#!/bin/bash
# Configure SessionStart hooks for update notifications and version checks
# Adds hooks to ~/.claude/settings.json

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

# Add hooks using correct Claude Code format: { hooks: [{ type, command, timeout }] }
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

# Check existing hooks — look inside the nested hooks array
existing_commands = []
for entry in settings["hooks"]["SessionStart"]:
    for hook in entry.get("hooks", []):
        existing_commands.append(hook.get("command", ""))

added = []
for name, script in scripts.items():
    if not any(name in cmd for cmd in existing_commands):
        settings["hooks"]["SessionStart"].append({
            "hooks": [
                {
                    "type": "command",
                    "command": script,
                    "timeout": 10
                }
            ]
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
