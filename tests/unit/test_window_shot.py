"""window-shot.sh: consent first, one window only, and an honest failure for every way
a capture can show nothing. The macOS tools are replaced by fakes on PATH, so the control
flow is tested on any machine; the real capture is verified on a Mac, not here."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "window-shot.sh"
SKILL_FAKES = {
    "uname": 'echo "${FAKE_UNAME:-Darwin}"',
    "ps": 'if [ -n "${FAKE_COMM:-}" ]; then echo "  $FAKE_COMM"; fi',
    "swiftc": 'if [ "${FAKE_SWIFTC:-ok}" = fail ]; then echo "error: no such toolchain" >&2; exit 1; fi; '
              'while [ $# -gt 0 ]; do [ "$1" = -o ] && out=$2; shift; done; '
              'printf \'#!/bin/bash\\ncase "$1" in id) echo "${FAKE_WID:-}";; uniform) echo "${FAKE_UNIFORM:-varied}";; esac\\n\' > "$out"; chmod +x "$out"',
    "screencapture": 'for a; do last=$a; done; if [ "${FAKE_CAPTURE:-ok}" = fail ]; then exit 1; fi; '
                     'echo "$@" > "${FAKE_ARGS:-/dev/null}"; head -c 5000 /dev/zero > "$last"',
    "sleep": "true",
    "kill": 'exit "${FAKE_KILL:-0}"',
}


@pytest.fixture
def env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in SKILL_FAKES.items():
        f = bin_dir / name
        f.write_text(f"#!/bin/bash\n{body}\n")
        f.chmod(0o755)
    project = tmp_path / "proj"
    (project / ".gstack").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    e = {"PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path), "TMPDIR": str(tmp_path),
         "FAKE_COMM": "/b/App.app/Contents/MacOS/App", "FAKE_WID": "4242",
         "FAKE_ARGS": str(tmp_path / "args")}
    return project, e


def pin(project: Path, content: str | None):
    f = project / ".gstack" / "visual-verify"
    if content is None:
        f.unlink(missing_ok=True)
    else:
        f.write_text(content)


def run(project, e, *args, **extra):
    return subprocess.run(["bash", str(SCRIPT), *args], cwd=project, env={**e, **extra},
                          capture_output=True, text=True)


def test_happy_path_captures_one_window_by_id(env):
    project, e = env
    pin(project, "host\n")
    out = project / "shots" / "a.png"
    r = run(project, e, "123", str(out))
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == str(out) and out.stat().st_size > 0
    args = Path(e["FAKE_ARGS"]).read_text().split()
    assert "-l" in args and args[args.index("-l") + 1] == "4242", "must capture a window id"
    assert "-x" in args, "silent: no sound, no UI"


@pytest.mark.parametrize("content", [None, "vm\n", "off\n", "Host\n", "host \n", "", "host\n\n", "yes"])
def test_only_exact_host_authorises_a_capture(env, content):
    project, e = env
    pin(project, content)
    r = run(project, e, "123", str(project / "a.png"))
    assert r.returncode == 2 and "BLOCKED" in r.stderr
    assert not (project / "a.png").exists()
    assert not Path(e["FAKE_ARGS"]).exists(), "no screencapture may run without consent"


def test_not_macos_refuses_with_its_own_code(env):
    project, e = env
    pin(project, "host\n")
    assert run(project, e, "123", str(project / "a.png"), FAKE_UNAME="Linux").returncode == 3


@pytest.mark.parametrize("args", [[], ["1"], ["x", "a.png"], ["1", "a.jpg"], ["1", "a.png", "extra"]])
def test_usage_errors(env, args):
    project, e = env
    pin(project, "host\n")
    r = run(project, e, *args)
    assert r.returncode == 2 and "USAGE ERROR" in r.stderr


def test_dead_pid_is_exit_6(env):
    project, e = env
    pin(project, "host\n")
    assert run(project, e, "123", str(project / "a.png"), FAKE_COMM="").returncode == 6


def test_expected_executable_must_match_exactly(env):
    project, e = env
    pin(project, "host\n")
    ok = run(project, e, "123", str(project / "a.png"), WINDOW_SHOT_EXPECT="/b/App.app/Contents/MacOS/App")
    assert ok.returncode == 0
    bad = run(project, e, "123", str(project / "b.png"), WINDOW_SHOT_EXPECT="/other/App.app/Contents/MacOS/App")
    assert bad.returncode == 6 and "not" in bad.stderr


def test_no_window_is_exit_4_and_never_falls_back_to_the_screen(env):
    project, e = env
    pin(project, "host\n")
    r = run(project, e, "123", str(project / "a.png"), FAKE_WID="")
    assert r.returncode == 4
    assert not Path(e["FAKE_ARGS"]).exists(), "no screencapture without a window id"


def test_process_that_exits_while_waiting_is_exit_4(env):
    project, e = env
    pin(project, "host\n")
    r = run(project, e, "123", str(project / "a.png"), FAKE_WID="", FAKE_KILL="1")
    assert r.returncode == 4 and "exited" in r.stderr


def test_screencapture_failure_is_exit_5(env):
    project, e = env
    pin(project, "host\n")
    assert run(project, e, "123", str(project / "a.png"), FAKE_CAPTURE="fail").returncode == 5


def test_uniform_image_is_exit_5(env):
    project, e = env
    pin(project, "host\n")
    r = run(project, e, "123", str(project / "a.png"), FAKE_UNIFORM="uniform")
    assert r.returncode == 5 and "Screen Recording" in r.stderr


def test_helper_that_cannot_be_built_is_exit_7_not_a_fake_no_window(env):
    project, e = env
    pin(project, "host\n")
    r = run(project, e, "123", str(project / "a.png"), FAKE_SWIFTC="fail")
    assert r.returncode == 7 and "no such toolchain" in r.stderr
    assert not Path(e["FAKE_ARGS"]).exists()


def test_helper_is_compiled_once_not_per_retry(env):
    """Interpreting the source on every one of 20 retries costs seconds each."""
    code = "\n".join(l for l in SCRIPT.read_text().splitlines() if not l.lstrip().startswith("#"))
    assert code.count("swiftc ") == 1 and "swift \"" not in code


def test_script_never_names_a_whole_display_capture():
    text = SCRIPT.read_text()
    code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    assert "screencapture -x -o -l" in code
    calls = [l for l in code.splitlines() if l.lstrip().startswith("screencapture")]
    assert len(calls) == 1 and "-l" in calls[0], "exactly one capture call, and it is window-scoped"
