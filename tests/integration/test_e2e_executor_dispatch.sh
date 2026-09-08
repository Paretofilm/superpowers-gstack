#!/usr/bin/env bash
#
# tests/integration/test_e2e_executor_dispatch.sh
#
# Verifies that /e2e-route actually reads .gstack/e2e-executor and reports the
# resolved executor in its decision block. The unit tests assert the SKILL.md text
# says the right thing; this one checks that a real agent, reading that text,
# behaves accordingly — the gap between a documented contract and a followed one.
#
# Three cases:
#   A) e2e-executor=vm     → expect executor=vm (or vm→host-fallback if no rig here)
#   B) no marker           → expect executor=host
#   C) e2e-executor=VM     → expect a refusal, NOT a silent host run
#
# Case C is the one worth the money. A/B can fail visibly; C fails by looking fine,
# which is the whole reason the pin is validated instead of coerced.
#
# Cost: ~1 minute per case (3 cases = ~3 min). Requires ANTHROPIC_API_KEY or an
# active Claude Code session.
#
# Usage: bash tests/integration/test_e2e_executor_dispatch.sh
# Exit codes: 0 = all pass, 1 = at least one assertion failed,
#             2 = setup error (missing dependency, claude CLI missing).

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PASS_COUNT=0
FAIL_COUNT=0
FAILURES=()

if ! command -v claude >/dev/null 2>&1; then
  echo "SETUP ERROR: claude CLI not found in PATH. Install Claude Code first." >&2
  exit 2
fi

echo "Using Claude Code: $(claude --version 2>&1 | head -1)"
echo "Plugin under test: $PLUGIN_DIR"
if command -v vm-e2e >/dev/null 2>&1; then
  echo "Rig: vm-e2e found — case A expects executor=vm"
else
  echo "Rig: vm-e2e NOT on PATH — case A accepts vm→host-fallback too"
fi
echo ""

# Minimal macOS project fixture. Kept inline so the test does not depend on
# setup-routing/adapt running successfully — it tests the routing rule alone.
read -r -d '' PROJECT_CLAUDE_MD <<'CLAUDE_MD' || true
# Project CLAUDE.md (test fixture)

## Skill routing

- E2E test this app, "run the regression suite", "e2e" → invoke
  `/superpowers-gstack:e2e-route`.
CLAUDE_MD

# $1 case name · $2 marker value ("" = none) · $3 extended regex the output must match
run_case() {
  local case_name="$1" marker="$2" expect_re="$3"
  echo "=== Case: $case_name ==="
  local tmpdir; tmpdir="$(mktemp -d -t sgstack-e2ex-XXXXXX)"
  trap "rm -rf '$tmpdir'" RETURN

  echo "$PROJECT_CLAUDE_MD" >"$tmpdir/CLAUDE.md"
  # A scheme has to be discoverable or e2e-route refuses before reaching the axis.
  mkdir -p "$tmpdir/App.xcodeproj" "$tmpdir/.gstack"
  printf 'SDKROOT = macosx\n' >"$tmpdir/App.xcodeproj/project.pbxproj"
  echo macos >"$tmpdir/.gstack/track"
  if [ -n "$marker" ]; then
    echo "$marker" >"$tmpdir/.gstack/e2e-executor"
    echo "  Fixture: .gstack/e2e-executor=$marker"
  else
    echo "  Fixture: no .gstack/e2e-executor marker"
  fi

  local out
  out="$(cd "$tmpdir" && claude --print --plugin-dir "$PLUGIN_DIR" \
    "Run the committed regression suite for this macOS app." 2>&1 || true)"

  if printf '%s' "$out" | grep -qiE "$expect_re"; then
    echo "  PASS — matched /$expect_re/"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  FAIL — no match for /$expect_re/"
    echo "  --- output (last 25 lines) ---"
    printf '%s\n' "$out" | tail -25 | sed 's/^/  | /'
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAILURES+=("$case_name")
  fi
  echo ""
}

run_case "vm pin"        "vm" "executor=(vm|vm→host-fallback)"
run_case "no marker"     ""   "executor=host"
run_case "invalid pin"   "VM" "BLOCKED|invalid .gstack/e2e-executor"

echo "════════════════════════════════════════"
echo "PASS: $PASS_COUNT   FAIL: $FAIL_COUNT"
[ $FAIL_COUNT -eq 0 ] || { printf 'Failed: %s\n' "${FAILURES[@]}"; exit 1; }
echo "All executor-dispatch cases passed."
