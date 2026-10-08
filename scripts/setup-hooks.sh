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

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"  # -P: a dev-mode symlink resolves to the clone
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

# The agents store absolute paths, so they must point at a checkout that stays put:
# not a linked worktree (removed after landing), not the plugin cache (replaced on
# every plugin update), not a directory outside git at all.
case "$REPO_DIR" in
  "$HOME/.claude/plugins/"*)
    echo "Error: $REPO_DIR is the plugin cache, which plugin updates replace."
    echo "       Run this from your clone of superpowers-gstack."
    exit 1 ;;
esac
GIT_DIR_PATH="$(git -C "$REPO_DIR" rev-parse --git-dir 2>/dev/null || true)"
GIT_COMMON_PATH="$(git -C "$REPO_DIR" rev-parse --git-common-dir 2>/dev/null || true)"
if [ -z "$GIT_DIR_PATH" ]; then
  echo "Error: $REPO_DIR is not a git checkout. Run this from your clone of superpowers-gstack."
  exit 1
fi
if [ "$GIT_DIR_PATH" != "$GIT_COMMON_PATH" ]; then
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
    import os
    home = os.path.expanduser("~")
    # A hand-edited entry may start with a guard, so ~ is not always leading: expand every one.
    stale = [c for c in existing_commands if "notify-pending-updates" in c
             and notify_script not in c.replace("~/", home + "/")]
    if stale:
        print("WARNING: the notify-pending-updates hook in settings.json points at another copy:")
        for c in stale:
            print(f"         {c}")
        print(f"         Change its path to {notify_script} in {settings_path}.")
    else:
        print("notify-pending-updates already configured.")
PYEOF

# --- report inbox: launchd agents (macOS only) ---------------------------------
if [ "$(uname)" != "Darwin" ]; then
  echo "Not macOS: skipped the 17:00 reminder and click tracking."
  exit 0
fi
mkdir -p "$HOME/Library/Logs"
# report-inbox.py owns the labels, port, paths and launchd PATH; LABELS above must match
# (tests/unit/test_report_inbox.py checks it).
/usr/bin/python3 "$INBOX_SCRIPT" write-plists "$AGENTS_DIR" "$HOME/Library/Logs/sg-report-inbox.log" >/dev/null
unload_agents
for label in "${LABELS[@]}"; do
  # bootout returns before launchd has finished tearing down, and a bootstrap that
  # follows at once fails with "5: Input/output error" — retry briefly.
  for attempt in 1 2 3 4 5; do
    launchctl bootstrap "$DOMAIN" "$AGENTS_DIR/$label.plist" 2>/dev/null && break
    [ "$attempt" = 5 ] && { echo "Error: could not load $label (launchctl bootstrap failed 5 times)"; exit 1; }
    sleep 1
  done
done
echo "Loaded: daily reminder at 17:00 and click tracking on 127.0.0.1 (agents: ${LABELS[*]})"
echo "Tip: System Settings → Notifications → terminal-notifier → Alerts keeps the reminder on screen until clicked."
command -v terminal-notifier >/dev/null 2>&1 || echo "Note: install terminal-notifier (brew install terminal-notifier) for clickable reminders."
