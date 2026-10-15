"""scripts/pytest-gate.sh picks an interpreter that has pytest and Python >= 3.11."""
import stat
import subprocess
from pathlib import Path

GATE = Path(__file__).resolve().parents[2] / "scripts" / "pytest-gate.sh"


def fake(tmp_path, name, body):
    d = tmp_path / "bin dir"
    d.mkdir(exist_ok=True)
    f = d / name
    f.write_text("#!/bin/sh\n" + body)
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
    return d


def run(tmp_path, bins, *args):
    env = {"PATH": f"{bins}:/usr/bin:/bin", "HOME": str(tmp_path)}
    return subprocess.run(["bash", str(GATE), *args], capture_output=True, text=True, env=env)


def test_uses_python3_when_it_has_pytest(tmp_path):
    bins = fake(tmp_path, "python3", 'case "$*" in *"import pytest"*) exit 0;; *) echo "py3 $*";; esac')
    fake(tmp_path, "uv", 'echo "uv $*"')
    r = run(tmp_path, bins, "-q")
    assert "py3 -m pytest -q" in r.stdout
    assert "uv " not in r.stdout


def test_falls_back_to_uv_when_python3_lacks_pytest(tmp_path):
    bins = fake(tmp_path, "python3", 'touch "$(dirname "$0")/py3-ran"; exit 1')
    fake(tmp_path, "uv", 'echo "uv $*"')
    r = run(tmp_path, bins, "-q")
    assert (bins / "py3-ran").exists()  # the python3 branch was really tried first
    assert "uv run --python 3.14 --with pytest python -m pytest -q" in r.stdout


def test_exits_70_with_a_remedy_when_neither_exists(tmp_path):
    bins = fake(tmp_path, "python3", 'touch "$(dirname "$0")/py3-ran"; exit 1')
    r = run(tmp_path, bins, "-q")
    assert (bins / "py3-ran").exists()  # the python3 branch was really tried first
    assert r.returncode == 70
    assert "pytest-gate: no interpreter with pytest and Python >= 3.11" in r.stderr
    assert "install uv" in r.stderr


def test_arguments_with_spaces_survive(tmp_path):
    bins = fake(tmp_path, "python3", 'case "$*" in *"import pytest"*) exit 0;; *) printf "[%s]" "$@";; esac')
    assert "[tests/unit dir]" in run(tmp_path, bins, "tests/unit dir").stdout


def test_script_is_executable():
    assert GATE.stat().st_mode & stat.S_IXUSR
