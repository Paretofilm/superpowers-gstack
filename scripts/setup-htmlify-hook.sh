#!/bin/bash
# Install the htmlify PostToolUse hook in ~/.claude/settings.json.
# This fires after Write/Edit on artifact-pattern .md files and auto-generates
# HTML companions + dashboard.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SCRIPT="$REPO_DIR/scripts/htmlify-posttooluse.sh"
SETTINGS_FILE="$HOME/.claude/settings.json"

if [ ! -f "$HOOK_SCRIPT" ]; then
  echo "Error: $HOOK_SCRIPT not found"
  exit 1
fi

if [ ! -x "$HOOK_SCRIPT" ]; then
  chmod +x "$HOOK_SCRIPT"
fi

if [ ! -f "$SETTINGS_FILE" ]; then
  mkdir -p "$(dirname "$SETTINGS_FILE")"
  echo '{}' > "$SETTINGS_FILE"
fi

python3 <<PYEOF
import json

settings_path = "$SETTINGS_FILE"
hook_script = "$HOOK_SCRIPT"

with open(settings_path) as f:
    settings = json.load(f)

settings.setdefault("hooks", {})
settings["hooks"].setdefault("PostToolUse", [])

# Idempotency: check if our hook script is already wired up
already = False
for entry in settings["hooks"]["PostToolUse"]:
    for hook in entry.get("hooks", []):
        if hook_script in hook.get("command", ""):
            already = True
            break
    if already:
        break

if already:
    print(f"htmlify PostToolUse hook already configured.")
else:
    settings["hooks"]["PostToolUse"].append({
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
            {
                "type": "command",
                "command": hook_script,
                "timeout": 5
            }
        ]
    })
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print(f"htmlify PostToolUse hook installed.")
    print(f"Restart Claude Code to activate.")
PYEOF
