#!/usr/bin/env bash
# The adapt skill's tests in one command: the SKILL.md contract
# (required-sections.test.sh) and the suite for scripts/adapt-claude-md.py, which
# runs the script against temporary projects with the real block files.
#   bash skills/adapt/tests/run.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$DIR/../../.." && pwd)"

bash "$DIR/required-sections.test.sh"
bash "$REPO/scripts/pytest-gate.sh" "$REPO/tests/unit/test_adapt_script.py" -q -p no:cacheprovider
