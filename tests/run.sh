#!/usr/bin/env bash
#
# tests/run.sh — entry point for all superpowers-gstack tests.
#
# Usage:
#   bash tests/run.sh                # run all tests (currently only integration)
#   bash tests/run.sh --integration  # run integration tests only (slow, costs API)
#   bash tests/run.sh --unit         # run unit tests only (none yet)
#
# Integration tests shell out to `claude --print` and cost ~1 minute
# and a few cents per case. They require ANTHROPIC_API_KEY or an
# active Claude Code session. See tests/README.md for details.
#
# Exit code: 0 if all selected suites pass, non-zero otherwise.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-all}"

case "$MODE" in
  --integration|integration)
    RUN_INTEGRATION=true; RUN_UNIT=false
    ;;
  --unit|unit)
    RUN_INTEGRATION=false; RUN_UNIT=true
    ;;
  all|"")
    RUN_INTEGRATION=true; RUN_UNIT=true
    ;;
  -h|--help)
    sed -n '2,15p' "$0"
    exit 0
    ;;
  *)
    echo "Unknown mode: $MODE. See --help." >&2
    exit 2
    ;;
esac

FAIL=0

if [ "${RUN_UNIT:-false}" = "true" ]; then
  echo "=========================================="
  echo "Unit tests (pytest, fast, no API)"
  echo "=========================================="
  if pytest "$REPO_ROOT/tests/unit" -q; then
    echo ">>> unit: PASS"
  else
    echo ">>> unit: FAIL"
    FAIL=$((FAIL + 1))
  fi
fi

if [ "${RUN_INTEGRATION:-false}" = "true" ]; then
  echo "=========================================="
  echo "Integration tests (slow, costs API)"
  echo "=========================================="
  for test_file in "$REPO_ROOT"/tests/integration/test_*.sh; do
    [ -f "$test_file" ] || continue
    echo ""
    echo ">>> Running: $(basename "$test_file")"
    if bash "$test_file"; then
      echo ">>> $(basename "$test_file"): PASS"
    else
      echo ">>> $(basename "$test_file"): FAIL"
      FAIL=$((FAIL + 1))
    fi
  done
fi

echo ""
echo "=========================================="
if [ $FAIL -eq 0 ]; then
  echo "All test suites passed."
  exit 0
else
  echo "$FAIL test suite(s) failed."
  exit 1
fi
