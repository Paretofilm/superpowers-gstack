#!/usr/bin/env bash
# Runs pytest with an interpreter that has it and is Python >= 3.11 (the suite needs tomllib).
# Used by the pre-merge hook in .config/wt.toml so a bare Homebrew python3 does not fail the gate.
#   1. python3 itself, when it can import pytest and is >= 3.11
#   2. otherwise uv, which fetches Python 3.14 and pytest on demand
#   3. otherwise exit 70 with the remedy
set -u

if python3 -c 'import pytest, sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
  exec python3 -m pytest "$@"
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run --python 3.14 --with pytest python -m pytest "$@"
fi

echo "pytest-gate: no interpreter with pytest and Python >= 3.11 (install uv or: python3 -m pip install pytest)" >&2
exit 70
