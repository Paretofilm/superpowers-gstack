"""Guard scripts/spec-drift.py check/repin — the hash pin on /ship Step 8's section.

The skill executes an upstream file it does not own (gstack auto-updates weekly).
The pin is what makes "same bytes" a checked fact instead of an assumption, and
--repin is what keeps the override from becoming a reflex: no diff shown, no pin.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "spec-drift.py"

# A miniature of the upstream section. It carries every anchor the wrapper's
# overrides name (ANCHORS in the script), so the anchor check has something to pass.
SECTION = (
    "## Step 8: Plan Completion Audit\n\n"
    "> ### Plan File Discovery\n"
    "line two\n"
    "### Gate Logic\n"
    "Use `<base>`. **Include in PR body (Step 8):** ... **Parent processing:** ...\n"
    '`{"total_items":N,"done":N}`\n'
    "\n## Step 8.1: Plan Verification\n"
    "line three\n"
)


def run(*args, expect, stdin=None):
    p = subprocess.run([sys.executable, str(SCRIPT), *args],
                       capture_output=True, text=True, input=stdin)
    assert p.returncode == expect, (
        f"exit {p.returncode} (wanted {expect})\nstdout: {p.stdout}\nstderr: {p.stderr}")
    return p


def shown_sha(diff_run) -> str:
    """The sha the diff run tells the user to pass back with --yes."""
    return re.search(r"--yes --sha ([0-9a-f]{12})", diff_run.stdout).group(1)


def accept(upstream, pin_dir):
    """The two-step accept the skill performs: show the diff, then --yes bound to it."""
    p = run("repin", *common(upstream, pin_dir), expect=3)
    return run("repin", "--yes", "--sha", shown_sha(p), *common(upstream, pin_dir), expect=0)


@pytest.fixture()
def rig(tmp_path):
    """A fake gstack install (VERSION + ship/sections/plan-completion.md) and an empty pin dir."""
    gstack = tmp_path / "gstack"
    (gstack / "ship" / "sections").mkdir(parents=True)
    (gstack / "VERSION").write_text("9.9.9.9\n")
    upstream = gstack / "ship" / "sections" / "plan-completion.md"
    upstream.write_text(SECTION)
    pin_dir = tmp_path / "skill"
    pin_dir.mkdir()
    return upstream, pin_dir


def common(upstream, pin_dir):
    return ["--upstream", str(upstream), "--pin-dir", str(pin_dir)]


def test_check_refuses_without_a_pin(rig):
    upstream, pin_dir = rig
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "NO PIN" in p.stderr


def test_repin_shows_the_diff_and_refuses_without_yes(rig):
    upstream, pin_dir = rig
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert "+## Step 8: Plan Completion Audit" in p.stdout, "the diff must be shown"
    assert "REPIN REQUIRES CONFIRMATION" in p.stdout
    assert not (pin_dir / "pin.json").exists(), "nothing may be written without --yes"


def test_repin_yes_writes_pin_and_snapshot_and_check_passes(rig):
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    pin = json.loads((pin_dir / "pin.json").read_text())
    assert pin["sha256"] == hashlib.sha256(SECTION.encode()).hexdigest()
    assert pin["gstack_version"] == "9.9.9.9"
    assert (pin_dir / "pin" / "plan-completion.md").read_text() == SECTION
    p = run("check", *common(upstream, pin_dir), expect=0)
    assert "PIN OK" in p.stdout


def test_one_changed_line_upstream_is_refused_and_named(rig):
    """Spec, Verifisering 4: change one line in a local copy of the section — the
    wrapper must refuse to run and name the hash mismatch."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.write_text(SECTION.replace("line two", "line two, reworded upstream"))
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "PIN MISMATCH" in p.stderr
    assert "repin" in p.stderr, "the refusal must name the way out"
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert "-line two\n" in p.stdout and "+line two, reworded upstream" in p.stdout


def test_repin_is_a_noop_when_nothing_changed(rig):
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    p = run("repin", *common(upstream, pin_dir), expect=0)
    assert "PIN UNCHANGED" in p.stdout


def test_repin_yes_is_bound_to_the_bytes_the_diff_showed(rig):
    """Between the diff and the --yes, a weekly gstack update can rewrite the file.
    Accepting whatever is on disk at --yes time would pin bytes nobody read."""
    upstream, pin_dir = rig
    shown = shown_sha(run("repin", *common(upstream, pin_dir), expect=3))
    p = run("repin", "--yes", "--sha", shown[:4], *common(upstream, pin_dir), expect=2)
    assert "REPIN REFUSED" in p.stderr, "a 4-char prefix is a guess, not the receipt the diff run printed"
    upstream.write_text(SECTION + "changed after the diff was shown\n")
    p = run("repin", "--yes", "--sha", shown, *common(upstream, pin_dir), expect=2)
    assert "REPIN REFUSED" in p.stderr
    assert not (pin_dir / "pin.json").exists(), "nothing may be written on a refused accept"
    p = run("repin", "--yes", *common(upstream, pin_dir), expect=2)   # no --sha at all
    assert "REPIN REFUSED" in p.stderr


def test_snapshot_that_disagrees_with_pin_json_is_refused(rig):
    """pin.json and the snapshot are one artefact; edit one without the other and
    --repin's diff would lie about what was accepted."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    (pin_dir / "pin" / "plan-completion.md").write_text(SECTION + "tampered\n")
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "PIN CORRUPT" in p.stderr


def test_pin_json_of_the_wrong_shape_is_corrupt_not_a_traceback(rig):
    """Valid JSON that is not the pin's shape used to reach `.get`/slicing and die
    with a Python traceback — exit 1, which nothing above treats as 'refused'."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    for wrong in ("[]", '"a string"', '{"sha256": 5}', "{not json"):
        (pin_dir / "pin.json").write_text(wrong)
        p = run("check", *common(upstream, pin_dir), expect=2)
        assert "PIN CORRUPT" in p.stderr, wrong
        assert "Traceback" not in p.stderr, wrong


def test_repin_refuses_a_section_that_lost_an_anchor(rig):
    """The overrides name Step 8's structure. A section that dropped an anchor can
    still hash fine after a blind accept — and then the wrapper would run Step 8.1
    too, or find no Gate Logic to override. So the anchor check is mechanical."""
    upstream, pin_dir = rig
    upstream.write_text(SECTION.replace("### Gate Logic", "### Decision Logic"))
    p = run("repin", *common(upstream, pin_dir), expect=2)
    assert "ANCHORS MISSING" in p.stderr and "### Gate Logic" in p.stderr
    sha = hashlib.sha256(upstream.read_bytes()).hexdigest()[:12]
    p = run("repin", "--yes", "--sha", sha, *common(upstream, pin_dir), expect=2)
    assert "ANCHORS MISSING" in p.stderr
    assert not (pin_dir / "pin.json").exists()


def test_missing_upstream_is_could_not_run_not_clean(rig):
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.unlink()
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "UPSTREAM MISSING" in p.stderr
