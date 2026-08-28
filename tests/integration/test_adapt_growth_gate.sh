#!/usr/bin/env bash
#
# tests/integration/test_adapt_growth_gate.sh
#
# Verifies that /adapt's growth check (2.48.0) refuses to silently replace a
# marker-managed section that has grown past its block.
#
# The regression this guards is the QUIET one: a run that reports
# "Nothing project-authored was removed." while the diff says otherwise. So the
# assertions read the FILE, never the report.
#
# --print is non-interactive, so the gate's rule 4 (preserving branch) is the
# path under test: the section must be left at its old version, not replaced.
#
# Cost: ~1-2 minutes and a few cents. Requires ANTHROPIC_API_KEY or an active
# Claude Code session.
#
# Usage: bash tests/integration/test_adapt_growth_gate.sh
# Exit codes: 0 = pass, 1 = assertion failed, 2 = setup error.

set -uo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
FIXTURE="$PLUGIN_DIR/tests/fixtures/adapt-growth/CLAUDE.md"
FAILURES=()

if ! command -v claude >/dev/null 2>&1; then
  echo "SETUP ERROR: claude CLI not found in PATH." >&2
  exit 2
fi
if [ ! -f "$FIXTURE" ]; then
  echo "SETUP ERROR: fixture missing at $FIXTURE" >&2
  exit 2
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp "$FIXTURE" "$WORK/CLAUDE.md"
mkdir -p "$WORK/.gstack" && echo "ios" > "$WORK/.gstack/track"
git -C "$WORK" init -q && git -C "$WORK" add -A
git -C "$WORK" -c user.email=t@t -c user.name=t commit -qm "fixture"

echo "Running /adapt against $WORK ..."
( cd "$WORK" && claude --print --plugin-dir "$PLUGIN_DIR" \
    "/superpowers-gstack:adapt" ) > "$WORK/run.log" 2>&1
echo "(exit $?; log at $WORK/run.log)"

assert() {  # $1 = description, $2 = 0/1 condition result
  if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; FAILURES+=("$1"); fi
}

# 1. The snapshot exists — Task 1's guard actually ran.
[ -f "$WORK/.gstack/CLAUDE.md.pre-adapt" ]; assert "snapshot written to .gstack/CLAUDE.md.pre-adapt" $?

# 2. Every sentinel line survives. This is the assertion that matters: it reads
#    the file, so a run that CLAIMS nothing was removed still fails here.
MISSING=0
for n in 001 002 003 004 005; do
  grep -q "SENTINEL-LINE-$n" "$WORK/CLAUDE.md" || { echo "  lost SENTINEL-LINE-$n"; MISSING=1; }
done
[ "$MISSING" -eq 0 ]; assert "all 5 project-authored sentinel lines survive" $?

# 3. The grown section was NOT silently upgraded to v6 — non-interactive runs
#    take the preserving branch.
! grep -q "gstack-xcode-tools-v6" "$WORK/CLAUDE.md"; assert "grown section left at its old marker, not replaced" $?

# 4. The report names the deferral rather than passing over it in silence.
grep -qi "Removed (not plugin prose)" "$WORK/run.log"; assert "report contains the Removed block" $?

echo ""
if [ ${#FAILURES[@]} -eq 0 ]; then
  echo "test_adapt_growth_gate: PASS"
  exit 0
fi
printf 'test_adapt_growth_gate: %d assertion(s) failed\n' "${#FAILURES[@]}"
printf '  - %s\n' "${FAILURES[@]}"
exit 1
