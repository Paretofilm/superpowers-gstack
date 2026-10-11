#!/usr/bin/env bash
# Verifies SKILL.md contains required anchors (catches accidental body deletion).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_FILE="$SCRIPT_DIR/../SKILL.md"
[ -f "$SKILL_FILE" ] || { echo "FAIL: SKILL.md not found"; exit 1; }

REQUIRED=(
  "scripts/adapt-claude-md.py"
  "**Dependency check:**"
  "**Directory check:**"
  # 3.11.0: an empty folder takes the short path — no gate, one Assumed line,
  # straight on to the intake; the script decides what fresh means
  "### Step 0: An empty folder gets the short path"
  '--dry-run --set DOMAIN_SENSITIVITY=medium | tail -1'
  '--fresh --mkdirs'
  'BLOCKED — not a fresh project'
  'blocks/routing-default.md'
  '<!-- gstack-project-pending -->'
  'Assumed: web track, vibe workflow, local explainer, no local state, medium sensitivity'
  'no "is this right?", no "shall I proceed?", no offer of a review'
  "### Step 1: Analyze the project"
  "### Step 2: Confirm the stack"
  "### Step 3: Evaluate skills and model routing"
  "### Step 4: Resolve the script's inputs"
  # the fill-in once the stack is known: one confirmation, --project-section, no merge gate
  "**A pending \`## Project\` first.**"
  '--project-section .gstack/adapt-project.md'
  "### Routing for this stack"
  "**Workflow profile.**"
  "**Explainer page.**"
  "### Step 5: Dry run, then ask"
  "### Step 6: Apply and report"
  "**Removed (not plugin prose):**"
  "**Deferred (grown past its block, not upgraded):**"
  "### Step 7: Suggest next steps"
)

failed=0
for anchor in "${REQUIRED[@]}"; do
  if ! grep -qF -- "$anchor" "$SKILL_FILE"; then
    echo "FAIL: missing anchor: $anchor"
    failed=1
  fi
done
[ "$failed" -eq 0 ] && echo "OK: all $(echo "${#REQUIRED[@]}") required anchors present"
exit "$failed"
