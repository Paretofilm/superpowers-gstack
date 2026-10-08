#!/bin/bash
# SessionStart hook (maintainer-only, installed by scripts/setup-hooks.sh):
# list the repo's unread reports — open `notification` / `model-review` issues,
# `auto-repair` PRs, and files in ~/.claude/superpowers-gstack/reports/ — each
# with a link that marks it read when clicked. Silent when everything is read.
#
# The work is done by report-inbox.py; this wrapper keeps the path that
# existing settings.json entries point at. It never fails a session start.

rm -f "$HOME/.claude/.superpowers-gstack-notify-cache" 2>/dev/null  # pre-3.7.0 cache
command -v python3 >/dev/null 2>&1 || exit 0
python3 "$(dirname "$0")/report-inbox.py" banner 2>/dev/null || true
exit 0
