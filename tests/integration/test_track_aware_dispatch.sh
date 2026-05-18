#!/usr/bin/env bash
#
# tests/integration/test_track_aware_dispatch.sh
#
# Verifies that the track-aware routing rules in setup-routing's
# generated CLAUDE.md actually cause /design-consultation to dispatch
# to the right skill based on .gstack/track.
#
# Two cases:
#   A) track=ios → expect dispatch to /superpowers-gstack:swiftui-design-consultation
#   B) no track marker → expect dispatch to /design-consultation (gstack web variant)
#
# Cost: ~1 minute per case (2 cases = ~2 min total). Requires
# ANTHROPIC_API_KEY or active Claude Code session credentials.
#
# Usage: bash tests/integration/test_track_aware_dispatch.sh
# Exit codes: 0 = all pass, 1 = at least one assertion failed,
#             2 = setup error (missing dependency, claude CLI missing).

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PASS_COUNT=0
FAIL_COUNT=0
FAILURES=()

# --- Sanity checks ---

if ! command -v claude >/dev/null 2>&1; then
  echo "SETUP ERROR: claude CLI not found in PATH. Install Claude Code first." >&2
  exit 2
fi

CLAUDE_VERSION="$(claude --version 2>&1 | head -1)"
echo "Using Claude Code: $CLAUDE_VERSION"
echo "Plugin under test: $PLUGIN_DIR"
echo ""

# --- Fixture: minimal project CLAUDE.md with track-aware routing block ---
# Mirrors the block that setup-routing/adapt would emit. Kept inline so
# the test does not depend on those skills running successfully — it
# tests the dispatch rule in isolation.

read -r -d '' PROJECT_CLAUDE_MD <<'CLAUDE_MD' || true
# Project CLAUDE.md (test fixture)

## Track-aware routing (dual-track) <!-- gstack-routing-v1 -->

This project follows superpowers-gstack's dual-track convention.
Track is declared in `.gstack/track` (`ios` | `macos` | `both`).
Missing marker = `web` (gstack default).

### When user invokes /design-consultation (no namespace)

Read `.gstack/track`:
- `ios` / `macos` / `both` → invoke `/superpowers-gstack:swiftui-design-consultation`
- Absent or `web` → invoke `/design-consultation` (gstack)

User can always bypass by typing the namespaced version directly.
CLAUDE_MD

# --- Helper: run a single dispatch case ---
# $1 = case name (for reporting)
# $2 = track marker value (empty string = no marker)
# $3 = expected skill name to appear in output
# $4 = forbidden skill name (should NOT appear)

run_case() {
  local case_name="$1"
  local track_marker="$2"
  local expected="$3"
  local forbidden="$4"

  echo "=== Case: $case_name ==="
  local tmpdir
  tmpdir="$(mktemp -d -t sgstack-test-XXXXXX)"
  trap "rm -rf '$tmpdir'" RETURN

  # Build fixture project
  echo "$PROJECT_CLAUDE_MD" >"$tmpdir/CLAUDE.md"

  if [ -n "$track_marker" ]; then
    mkdir -p "$tmpdir/.gstack"
    echo "$track_marker" >"$tmpdir/.gstack/track"
    echo "  Fixture: .gstack/track=$track_marker"
  else
    echo "  Fixture: no .gstack/track marker"
  fi

  # Invoke claude --print in the fixture dir, loading this plugin.
  # Budget cap as safety net (one prompt should cost well under $0.50).
  echo "  Invoking: claude --print '/design-consultation' (in $tmpdir)"
  local output
  if ! output=$(
    cd "$tmpdir" && claude \
      --print \
      --plugin-dir "$PLUGIN_DIR" \
      --no-session-persistence \
      --max-budget-usd 1.00 \
      --output-format text \
      "Read this project's CLAUDE.md. The user said: /design-consultation. \
According to the track-aware routing rules in CLAUDE.md, which skill should you invoke? \
Reply with the full skill name (including any namespace prefix) on the first line, then a one-line reason. \
Do not actually invoke the skill — just name it." \
      2>&1
  ); then
    echo "  ✗ claude --print FAILED (exit $?)" >&2
    echo "  Output (first 200 chars): ${output:0:200}" >&2
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAILURES+=("$case_name: claude --print returned non-zero")
    return
  fi

  echo "  Output (first 300 chars):"
  echo "$output" | head -c 300 | sed 's/^/    /'
  echo ""

  # Assertions
  local pass=true
  if ! echo "$output" | grep -qF "$expected"; then
    echo "  ✗ Expected '$expected' in output but NOT found" >&2
    pass=false
  fi
  if [ -n "$forbidden" ] && echo "$output" | grep -qF "$forbidden"; then
    # Only flag if forbidden appears AS the dispatch choice (first line),
    # not if mentioned in passing. Simplest heuristic: forbidden must NOT
    # appear before expected.
    local first_expected
    local first_forbidden
    first_expected=$(echo "$output" | grep -n -F "$expected" | head -1 | cut -d: -f1)
    first_forbidden=$(echo "$output" | grep -n -F "$forbidden" | head -1 | cut -d: -f1)
    if [ -n "$first_forbidden" ] && [ -n "$first_expected" ] && [ "$first_forbidden" -lt "$first_expected" ]; then
      echo "  ✗ Forbidden '$forbidden' appears before expected '$expected'" >&2
      pass=false
    fi
  fi

  if $pass; then
    echo "  ✓ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAILURES+=("$case_name: assertion failed")
  fi
  echo ""
}

# --- Cases ---

run_case "track=ios → expect swiftui-design-consultation" \
  "ios" \
  "swiftui-design-consultation" \
  ""

run_case "no marker → expect gstack /design-consultation (NOT swiftui variant)" \
  "" \
  "design-consultation" \
  "swiftui-design-consultation"

# --- Summary ---

echo "==========================================="
echo "Track-aware dispatch tests: $PASS_COUNT pass / $FAIL_COUNT fail"
if [ $FAIL_COUNT -gt 0 ]; then
  echo ""
  echo "Failures:"
  for f in "${FAILURES[@]}"; do
    echo "  - $f"
  done
  exit 1
fi
exit 0
