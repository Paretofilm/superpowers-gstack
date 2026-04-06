#!/bin/bash
# Configure the SessionStart hook for update notifications
# Adds the notify-pending-updates.sh script to ~/.claude/settings.json

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NOTIFY_SCRIPT="$REPO_DIR/scripts/notify-pending-updates.sh"
SETTINGS_FILE="$HOME/.claude/settings.json"

# Verify the notify script exists
if [ ! -f "$NOTIFY_SCRIPT" ]; then
  echo "Error: $NOTIFY_SCRIPT not found"
  exit 1
fi

# Create settings file if missing
if [ ! -f "$SETTINGS_FILE" ]; then
  mkdir -p "$(dirname "$SETTINGS_FILE")"
  echo '{}' > "$SETTINGS_FILE"
fi

# Check if hook already configured
if python3 -c "
import json, sys
settings = json.load(open('$SETTINGS_FILE'))
hooks = settings.get('hooks', {})
for hook in hooks.get('SessionStart', []):
    if 'notify-pending-updates' in hook.get('command', ''):
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
  echo "Hook already configured in $SETTINGS_FILE"
  exit 0
fi

# Add the hook
python3 << PYEOF
import json

settings_path = "$SETTINGS_FILE"
notify_script = "$NOTIFY_SCRIPT"

with open(settings_path) as f:
    settings = json.load(f)

if "hooks" not in settings:
    settings["hooks"] = {}
if "SessionStart" not in settings["hooks"]:
    settings["hooks"]["SessionStart"] = []

settings["hooks"]["SessionStart"].append({
    "type": "command",
    "command": notify_script
})

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"Hook added to {settings_path}")
print(f"  Command: {notify_script}")
print()
print("Restart Claude Code to activate.")
PYEOF
