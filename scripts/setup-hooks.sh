#!/bin/bash
# Configure the MAINTAINER-ONLY SessionStart hook (update notifications).
# Adds it to ~/.claude/settings.json.
#
# NOTE (2.26.0): the version-check hook (check-plugin-version.sh) now ships
# plugin-wide via hooks/hooks.json with ${CLAUDE_PLUGIN_ROOT} — every plugin
# user gets it automatically, and it survives plugin updates. This script no
# longer installs it. The notify hook stays opt-in here because it is
# maintainer-facing: it surfaces pending auto-update PRs on the plugin repo,
# which only the repo owner can act on.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NOTIFY_SCRIPT="$REPO_DIR/scripts/notify-pending-updates.sh"
SETTINGS_FILE="$HOME/.claude/settings.json"

if [ ! -f "$NOTIFY_SCRIPT" ]; then
  echo "Error: $NOTIFY_SCRIPT not found"
  exit 1
fi

# Create settings file if missing
if [ ! -f "$SETTINGS_FILE" ]; then
  mkdir -p "$(dirname "$SETTINGS_FILE")"
  echo '{}' > "$SETTINGS_FILE"
fi

# Add the notify hook; warn about a stale check-plugin-version entry (now
# shipped by the plugin itself — a settings.json copy produces a DOUBLE nag).
python3 << PYEOF
import json

settings_path = "$SETTINGS_FILE"
notify_script = "$NOTIFY_SCRIPT"

with open(settings_path) as f:
    settings = json.load(f)

settings.setdefault("hooks", {}).setdefault("SessionStart", [])

existing_commands = []
for entry in settings["hooks"]["SessionStart"]:
    for hook in entry.get("hooks", []):
        existing_commands.append(hook.get("command", ""))

if any("check-plugin-version" in cmd for cmd in existing_commands):
    print("WARNING: settings.json still has a check-plugin-version hook.")
    print("         That hook now ships with the plugin (hooks/hooks.json),")
    print("         so the settings.json copy causes a DOUBLE version nag.")
    print(f"         Remove it manually from {settings_path}.")

if not any("notify-pending-updates" in cmd for cmd in existing_commands):
    settings["hooks"]["SessionStart"].append({
        "hooks": [
            {
                "type": "command",
                "command": notify_script,
                "timeout": 10
            }
        ]
    })
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print("Added: notify-pending-updates (maintainer hook)")
    print(f"Saved to {settings_path}. Restart Claude Code to activate.")
else:
    print("notify-pending-updates already configured.")
PYEOF
