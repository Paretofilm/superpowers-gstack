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
  "## Stop policy"
  "STOP_POLICY"
  # 3.5.0: fix-then-continue is the default and nothing is asked about it. The two
  # other values stay reachable by naming them in the invocation.
  "fix-then-continue"
  "any-issue"
  "Stop policy: fix-then-continue (default). Proceeding through N phases."
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
  "## When STOPping"
  "## Final summary"
  # 3.5.0: the fix round — bounded, scoped, re-runs only the review that raised it
  "##### Fix round"
  "fix_rounds"
  "pre_fix_head"
  'fix(phase-<N>): <short description>'
  "after 2 fix rounds"
  "Deferred"
  # 3.4.0 fix wave 2: the plan path is re-resolved inside the worktree, and a plan
  # commit that is not on origin refuses up front (landing would stop with code 4)
  'plan_rel='
  'git rev-list --count "origin/$git_branch..$git_branch"'
  # fix wave 3: an unverifiable count refuses instead of reading as 0
  'cannot verify that the plan commit is pushed'
)

# Text that must NOT come back: the 3.4.x policy question (it made every run start
# with a question whose recommended answer stopped at the first blocking finding).
FORBIDDEN=(
  'Invoke `AskUserQuestion` with'
  'Stop on any review issue (recommended)'
  'Asking one policy question'
)

failed=0
for anchor in "${REQUIRED[@]}"; do
  if ! grep -qF "$anchor" "$SKILL_FILE"; then
    echo "FAIL: missing anchor: $anchor"
    failed=1
  fi
done
for banned in "${FORBIDDEN[@]}"; do
  if grep -qF "$banned" "$SKILL_FILE"; then
    echo "FAIL: stale text is back: $banned"
    failed=1
  fi
done
[ "$failed" -eq 0 ] && echo "OK: all $(echo "${#REQUIRED[@]}") required anchors present"
exit "$failed"
