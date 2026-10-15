#!/usr/bin/env bash
# Verifies SKILL.md contains required anchors (catches accidental body deletion).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_FILE="$SCRIPT_DIR/../SKILL.md"
[ -f "$SKILL_FILE" ] || { echo "FAIL: SKILL.md not found"; exit 1; }

REQUIRED=(
  "## Phase 0 — scope"
  "## Phase 1 — look up before writing"
  "## Phase 2 — lint after writing"
  "## Phase 3 — see it"
  "## Phase 4 — affordance check"
  "## Phase 5 — the report"
  "scripts/view-gate.py"
  "scripts/window-shot.sh"
  ".gstack/visual-verify"
  "View gate: rendered and seen"
  "View gate: built, appearance unverified"
  "View gate: waived by user"
  "pattern checks"
  "real container"
  "packagePath"
  "Whole-display"
)
missing=0
for needle in "${REQUIRED[@]}"; do
  grep -qF -- "$needle" "$SKILL_FILE" || { echo "FAIL: missing anchor: $needle"; missing=1; }
done
exit "$missing"
