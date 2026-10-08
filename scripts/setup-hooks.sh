#!/bin/bash
# Configure the MAINTAINER-ONLY report inbox:
#   1. the SessionStart hook (notify-pending-updates.sh) in ~/.claude/settings.json,
#      which lists unread reports with click-to-mark-read links;
#   2. two launchd agents (macOS):
#      com.paretofilm.sg-report-notify — runs `report-inbox.py notify` daily at 17:00
#      com.paretofilm.sg-report-seen   — answers http://127.0.0.1:47817/seen/<id>
#        (inetd mode: one short process per click, nothing resident)
#
# Usage: scripts/setup-hooks.sh                           install / refresh
#        scripts/setup-hooks.sh --uninstall-report-inbox  remove the launchd agents
#
# Run it from the primary checkout: the agents store absolute paths, and a
# worktree is deleted after landing.
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
INBOX_SCRIPT="$REPO_DIR/scripts/report-inbox.py"
SETTINGS_FILE="$HOME/.claude/settings.json"
AGENTS_DIR="$HOME/Library/LaunchAgents"
LABELS=(com.paretofilm.sg-report-notify com.paretofilm.sg-report-seen)
DOMAIN="gui/$(id -u)"

unload_agents() {
  for label in "${LABELS[@]}"; do
    launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
  done
}

if [ "${1:-}" = "--uninstall-report-inbox" ]; then
  unload_agents
  for label in "${LABELS[@]}"; do rm -f "$AGENTS_DIR/$label.plist"; done
  echo "Removed the report-inbox launchd agents. The SessionStart hook stays (it falls back to plain links)."
  exit 0
fi

if [ "$(git -C "$REPO_DIR" rev-parse --git-dir 2>/dev/null)" != "$(git -C "$REPO_DIR" rev-parse --git-common-dir 2>/dev/null)" ]; then
  echo "Error: $REPO_DIR is a linked worktree. Run this from the primary checkout —"
  echo "       the launchd agents store absolute paths and a worktree is removed after landing."
  exit 1
fi

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

# --- report inbox: launchd agents (macOS only) ---------------------------------
if [ "$(uname)" != "Darwin" ]; then
  echo "Not macOS: skipped the 17:00 reminder and click tracking."
  exit 0
fi
mkdir -p "$AGENTS_DIR" "$HOME/Library/Logs"
python3 - "$AGENTS_DIR" "$INBOX_SCRIPT" "$HOME/Library/Logs/sg-report-inbox.log" << 'PYEOF'
import plistlib, sys
agents_dir, script, log = sys.argv[1:4]
common = {"StandardErrorPath": log, "StandardOutPath": log, "ProcessType": "Background"}
notify = dict(common, Label="com.paretofilm.sg-report-notify",
              ProgramArguments=["/usr/bin/python3", script, "notify"],
              StartCalendarInterval={"Hour": 17, "Minute": 0})
# inetd mode: stdin/stdout are the accepted connection, so stdout must not go to the log.
seen = {"Label": "com.paretofilm.sg-report-seen", "StandardErrorPath": log, "ProcessType": "Background",
        "ProgramArguments": ["/usr/bin/python3", script, "serve-one"],
        "inetdCompatibility": {"Wait": False},
        "Sockets": {"Listener": {"SockNodeName": "127.0.0.1", "SockServiceName": "47817",
                                 "SockType": "stream", "SockFamily": "IPv4"}}}
for spec in (notify, seen):
    with open(f"{agents_dir}/{spec['Label']}.plist", "wb") as f:
        plistlib.dump(spec, f)
PYEOF
unload_agents
for label in "${LABELS[@]}"; do
  launchctl bootstrap "$DOMAIN" "$AGENTS_DIR/$label.plist"
done
echo "Loaded: daily reminder at 17:00 and click tracking on http://127.0.0.1:47817"
echo "Tip: System Settings → Notifications → terminal-notifier → Alerts keeps the reminder on screen until clicked."
command -v terminal-notifier >/dev/null 2>&1 || echo "Note: install terminal-notifier (brew install terminal-notifier) for clickable reminders."
