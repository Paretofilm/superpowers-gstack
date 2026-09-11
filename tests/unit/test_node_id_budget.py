"""Guard the suite's own test ids against a Linux-only CI failure.

pytest derives a parametrized test's id from the parameter value unless an
explicit `id=` is given, and writes that id into the PYTEST_CURRENT_TEST
environment variable. Every subprocess a test spawns inherits it. A parameter
of 100_000 characters therefore produces a ~200 KB environment, and execve
refuses that on Linux with E2BIG ("Argument list too long") while macOS allows
it — so the suite is green on a developer's machine and red in CI, with a
traceback that points at subprocess internals rather than at the id.

That happened on 2026-09-08 (2.52.0 landed red on main). The fix is
`pytest.param(..., id="short-name")` on every large parameter; this test is what
makes the next one impossible to merge unnoticed.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Linux's per-string limit is MAX_ARG_STRLEN = 128 KB, and the whole environment
# competes for ARG_MAX besides. 4 KB is far below either, and far above any id a
# human would write on purpose — the longest legitimate id in this suite is ~260.
MAX_NODE_ID = 4096


def test_no_test_id_can_blow_up_a_subprocess_environment():
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit",
         "-q", "--collect-only", "-p", "no:cacheprovider"],
        cwd=REPO, capture_output=True, text=True,
    )
    assert p.returncode == 0, f"collection failed:\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}"
    ids = [line for line in p.stdout.splitlines() if "::" in line]
    assert len(ids) > 100, f"expected the full suite, collected {len(ids)}"
    oversized = [i for i in ids if len(i) > MAX_NODE_ID]
    assert not oversized, (
        f"{len(oversized)} test id(s) exceed {MAX_NODE_ID} chars — pytest puts the id in "
        f"PYTEST_CURRENT_TEST, which every spawned subprocess inherits, and Linux execve "
        f"refuses an oversized environment with E2BIG while macOS does not. Give the "
        f"parameter an explicit short id: pytest.param(<value>, id=\"...\"). First offender "
        f"({len(oversized[0])} chars): {oversized[0][:120]}..."
    )
