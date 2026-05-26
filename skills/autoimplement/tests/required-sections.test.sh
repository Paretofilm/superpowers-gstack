#!/usr/bin/env bash
# Verifies SKILL.md contains required anchors (catches accidental body deletion).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_FILE="$SCRIPT_DIR/../SKILL.md"
[ -f "$SKILL_FILE" ] || { echo "FAIL: SKILL.md not found"; exit 1; }

REQUIRED=(
  "## When to use"
  "## Plan path resolution"
  "## Startup checks"
  "### Check 1:"
  "### Check 2:"
  "### Check 3:"
  "### Check 4:"
  "### Check 5:"
  "### Check 6:"
  "## Policy question"
  "AskUserQuestion"
  "STOP_POLICY"
  "## Per-phase procedure"
  "### A."
  "### B."
  "### C."
  "### D."
  "### E."
  "<PHASE_CONTENT>"
  "DONE"
  "BLOCKED"
  "FAILED"
  "clean"
  "advisory"
  "blocking"
  "severe"
  "/review"
  "pitfall-verification"
  "/codex review"
  "## When STOPping"
  "## Final summary"
  "## Audit trail"
)

failed=0
for anchor in "${REQUIRED[@]}"; do
  if ! grep -qF "$anchor" "$SKILL_FILE"; then
    echo "FAIL: missing anchor: $anchor"
    failed=1
  fi
done
[ "$failed" -eq 0 ] && echo "OK: all $(echo "${#REQUIRED[@]}") required anchors present"
exit "$failed"
