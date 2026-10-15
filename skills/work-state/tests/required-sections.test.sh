#!/usr/bin/env bash
# Verifies the work-state SKILL.md keeps the sentences the agent's behaviour rests on.
set -euo pipefail
f="$(dirname "$0")/../SKILL.md"
[ -f "$f" ] || { echo "FAIL: SKILL.md not found" >&2; exit 1; }
for s in '## Run' '## Read the result' '## Do what is safe' '## Ask once' '## Install codes' '## Never' \
         'Run `safe_actions` as printed' 'one `AskUserQuestion`' '--quit-path' \
         'never `git branch -D`' 'never says ✓ while something is left'; do
  grep -qF -- "$s" "$f" || { echo "work-state SKILL.md lacks: $s" >&2; exit 1; }
done
echo "OK: work-state SKILL.md has every required anchor"
