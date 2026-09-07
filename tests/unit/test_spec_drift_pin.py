"""Guard scripts/spec-drift.py check/repin — the hash pin on /ship Step 8's section.

The skill executes an upstream file it does not own (gstack auto-updates weekly).
The pin is what makes "same bytes" a checked fact instead of an assumption, and
--repin is what keeps the override from becoming a reflex: no diff shown, no pin.

Every unexpected state must be a named reason on stderr and exit 2 — never exit 0,
never a Python traceback (exit 1). Most tests below pin one of those paths.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
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


def run(*args, expect):
    p = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
    assert p.returncode == expect, (
        f"exit {p.returncode} (wanted {expect})\nstdout: {p.stdout}\nstderr: {p.stderr}")
    assert "Traceback" not in p.stderr, f"a traceback is never a verdict:\n{p.stderr}"
    return p


def shown_sha(diff_run) -> str:
    """The sha the diff run tells the user to pass back with --yes."""
    return re.search(r"--yes --sha ([0-9a-f]{12})", diff_run.stdout).group(1)


def accept(upstream, pin_dir):
    """The two-step accept the skill performs: show the diff, then --yes bound to it."""
    p = run("repin", *common(upstream, pin_dir), expect=3)
    return run("repin", "--yes", "--sha", shown_sha(p), *common(upstream, pin_dir), expect=0)


def module():
    """The script as a module, for the two helpers worth calling directly."""
    spec = importlib.util.spec_from_file_location("spec_drift", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def write_pin(pin_dir, text, **overrides):
    """A hand-built, self-consistent pin for `text` — the shape a marketplace install ships."""
    (pin_dir / "pin").mkdir(exist_ok=True)
    (pin_dir / "pin" / "plan-completion.md").write_text(text)
    pin = {"source": "test", "sha256": hashlib.sha256(text.encode()).hexdigest(),
           "gstack_version": "9.9.9.9", "pinned_at": "2026-01-01", **overrides}
    (pin_dir / "pin.json").write_text(json.dumps(pin))


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
    assert not (pin_dir / ".repin-receipt").exists(), "the receipt is consumed by the accept"
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


def test_repin_over_an_existing_pin_updates_snapshot_and_check_passes(rig):
    """The primary upgrade flow: upstream drifted, the diff was read, the new bytes
    replace the old pin end to end."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    new = SECTION.replace("line two", "line two, reworded upstream")
    upstream.write_text(new)
    accept(upstream, pin_dir)
    assert (pin_dir / "pin" / "plan-completion.md").read_text() == new
    assert json.loads((pin_dir / "pin.json").read_text())["sha256"] == hashlib.sha256(new.encode()).hexdigest()
    p = run("check", *common(upstream, pin_dir), expect=0)
    assert "PIN OK" in p.stdout


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


def test_yes_without_a_diff_run_is_refused_even_with_the_right_sha(rig):
    """`check` prints the current digest too, so --sha alone would let a caller go
    straight from PIN MISMATCH to --yes without ever seeing a diff. The receipt a
    diff run writes is what --yes actually consumes."""
    upstream, pin_dir = rig
    sha = hashlib.sha256(SECTION.encode()).hexdigest()
    p = run("repin", "--yes", "--sha", sha, *common(upstream, pin_dir), expect=2)
    assert "no diff run recorded" in p.stderr
    assert not (pin_dir / "pin.json").exists()


def test_sha_receipt_boundary_is_twelve_chars(rig):
    upstream, pin_dir = rig
    run("repin", *common(upstream, pin_dir), expect=3)
    full = hashlib.sha256(SECTION.encode()).hexdigest()
    run("repin", "--yes", "--sha", full[:11], *common(upstream, pin_dir), expect=2)
    assert not (pin_dir / "pin.json").exists()
    run("repin", "--yes", "--sha", full, *common(upstream, pin_dir), expect=0)


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
    with a Python traceback — exit 1, which nothing above treats as 'refused'.
    A pin missing a schema field is corrupt too: the fields are the contract."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    sha = hashlib.sha256(SECTION.encode()).hexdigest()
    for wrong in ("[]", '"a string"', '{"sha256": 5}', "{not json",
                  json.dumps({"sha256": sha}), json.dumps({"sha256": sha, "source": "", "gstack_version": "x", "pinned_at": "y"}),
                  "[" * 100000 + "]" * 100000):
        (pin_dir / "pin.json").write_text(wrong)
        p = run("check", *common(upstream, pin_dir), expect=2)
        assert "PIN CORRUPT" in p.stderr, wrong[:40]


def test_invalid_utf8_upstream_and_pin_are_refused_not_a_traceback(rig):
    """The real section has 64 non-ASCII lines; a weekly update truncated inside a
    multibyte sequence is the realistic trigger."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.write_bytes(SECTION.encode() + b"\xff\n")
    for cmd in ("check", "repin"):
        p = run(cmd, *common(upstream, pin_dir), expect=2)
        assert "UNREADABLE" in p.stderr, cmd
    upstream.write_text(SECTION)
    (pin_dir / "pin.json").write_bytes(b'{"sha256": "\xff"}')
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "PIN CORRUPT" in p.stderr


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


def test_anchors_are_headings_not_substrings(rig):
    """The words inside a code fence or a comment do not make a heading. And Step 8
    must come before Step 8.1, because the wrapper stops at the second heading."""
    upstream, pin_dir = rig
    inert = SECTION.replace("### Gate Logic", "text mentioning ### Gate Logic inline")
    upstream.write_text(inert)
    p = run("repin", *common(upstream, pin_dir), expect=2)
    assert "### Gate Logic" in p.stderr
    head, _, tail = SECTION.partition("\n## Step 8.1: Plan Verification\n")
    upstream.write_text("## Step 8.1: Plan Verification\n" + head + "\n" + tail)
    p = run("repin", *common(upstream, pin_dir), expect=2)
    assert "order" in p.stderr
    upstream.write_text(SECTION.replace("## Step 8: Plan", "### Step 8: Plan"))   # demoted to h3
    p = run("repin", *common(upstream, pin_dir), expect=2)
    assert "## Step 8: Plan Completion Audit" in p.stderr


def test_a_stale_pin_json_never_yields_an_empty_diff(rig):
    """Red team, 2.52.0: copy upstream over the snapshot while pin.json is stale —
    the old code diffed against the snapshot blind, showed '+0 -0', handed out a
    receipt, and --yes pinned a line nobody had seen."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    injected = SECTION.replace("line two", "line two\nrm -rf / # injected upstream")
    upstream.write_text(injected)
    (pin_dir / "pin" / "plan-completion.md").write_text(injected)   # snapshot == upstream, pin.json stale
    run("check", *common(upstream, pin_dir), expect=2)
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert "+rm -rf / # injected upstream" in p.stdout, "the injected line must be shown"
    assert "no usable baseline" in p.stdout
    assert "+0 -0" not in p.stdout


def test_empty_pin_dir_is_refused_and_tilde_expands(rig, tmp_path):
    """Path('') is the cwd — a planted pin.json in a project root would satisfy
    check; and a literal '~' the shell never expanded must not become a directory
    named '~'."""
    upstream, _ = rig
    p = run("check", "--upstream", str(upstream), "--pin-dir", "", expect=2)
    assert "PIN DIR INVALID" in p.stderr
    env = dict(os.environ, HOME=str(tmp_path))
    p = subprocess.run([sys.executable, str(SCRIPT), "repin", "--upstream", str(upstream),
                        "--pin-dir", "~/tilde-pin"], capture_output=True, text=True, env=env)
    assert p.returncode == 3, p.stderr
    assert (tmp_path / "tilde-pin" / ".repin-receipt").exists()
    assert not (Path.cwd() / "~").exists()


def test_ascii_stdout_does_not_turn_a_shown_diff_into_a_traceback(rig):
    """The diff carries third-party text (the real section has 168 em dashes);
    a non-UTF-8 terminal must degrade to backslash escapes, not exit 1."""
    upstream, pin_dir = rig
    env = dict(os.environ, PYTHONIOENCODING="ascii")
    p = subprocess.run([sys.executable, str(SCRIPT), "repin", *common(upstream, pin_dir)],
                       capture_output=True, text=True, env=env)
    assert p.returncode == 3 and "Traceback" not in p.stderr, p.stderr
    assert "--yes --sha" in p.stdout


def test_usage_errors_carry_a_named_token(rig):
    """argparse also exits 2; without a token a caller would read a quoting bug
    in a user-typed path as a pin refusal."""
    upstream, pin_dir = rig
    p = run("chek", *common(upstream, pin_dir), expect=2)
    assert "USAGE ERROR" in p.stderr
    p = run("repin", "--sha", *common(upstream, pin_dir), expect=2)
    assert "USAGE ERROR" in p.stderr


def test_check_refuses_a_consistent_pin_whose_section_lost_an_anchor(rig):
    """repin blocks creating such a pin, so this branch is only reachable with a
    hand-built pin — the marketplace-shipped case it exists for."""
    upstream, pin_dir = rig
    bad = SECTION.replace("### Gate Logic", "### Decision Logic")
    upstream.write_text(bad)
    write_pin(pin_dir, bad)
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "ANCHORS MISSING" in p.stderr and "### Gate Logic" in p.stderr


def test_crlf_snapshot_is_corrupt_in_check_and_not_unchanged_in_repin(rig):
    """check compares bytes; repin used to compare newline-normalised text. A CRLF
    snapshot then read PIN CORRUPT from one and PIN UNCHANGED (exit 0) from the
    other, with no documented way out. Both now mean the same thing."""
    upstream, pin_dir = rig
    write_pin(pin_dir, SECTION)
    (pin_dir / "pin" / "plan-completion.md").write_bytes(SECTION.replace("\n", "\r\n").encode())
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "PIN CORRUPT" in p.stderr
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert "PIN CORRUPT" in p.stdout and "no usable baseline" in p.stdout, \
        "a snapshot pin.json does not vouch for is no baseline: show the whole section"
    accept(upstream, pin_dir)
    run("check", *common(upstream, pin_dir), expect=0)


def test_crlf_upstream_change_is_named_not_shown_as_nothing(rig):
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.write_bytes(SECTION.replace("\n", "\r\n").encode())
    run("check", *common(upstream, pin_dir), expect=2)
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert "line endings" in p.stdout, "a byte-only change must be named, not shown as +0 -0"


def test_control_chars_in_the_diff_are_escaped_and_invisibles_warned(rig):
    """The human reads a terminal rendering of the diff; an upstream that could
    repaint the prompt, or hide a change in zero-width characters, defeats the
    review the receipt is supposed to prove."""
    upstream, pin_dir = rig
    upstream.write_text(SECTION.replace("line two", "line \x1b[2Jtwo " + chr(0x200B) + "there"))
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert "\x1b" not in p.stdout and "\\u001b" in p.stdout
    assert chr(0x200B) not in p.stdout and "\\u200b" in p.stdout, "zero-width chars are escaped, not just warned about"
    assert "INVISIBLE CHARS" in p.stderr


def test_gstack_version_survives_shallow_paths_and_sanitises_content(rig, tmp_path):
    m = module()
    assert m.gstack_version(Path("/plan-completion.md")) == "unknown"
    upstream, _ = rig
    assert m.gstack_version(upstream) == "9.9.9.9"
    (tmp_path / "gstack" / "VERSION").write_text("1.81.0.0\nPIN OK sha256=spoofed\n")
    assert m.gstack_version(upstream) == "1.81.0.0", "first line only — the rest could forge a PIN OK"
    (tmp_path / "gstack" / "VERSION").write_text("not a version at all!\n")
    assert m.gstack_version(upstream) == "unknown"
    (tmp_path / "gstack" / "VERSION").write_bytes(b"\xff")
    assert m.gstack_version(upstream) == "unknown"


def test_repin_refuses_when_upstream_is_missing(rig):
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.unlink()
    for args in (("repin",), ("repin", "--yes", "--sha", "0" * 12)):
        p = run(*args, *common(upstream, pin_dir), expect=2)
        assert "UPSTREAM MISSING" in p.stderr
    assert (pin_dir / "pin" / "plan-completion.md").read_text() == SECTION, \
        "a missing upstream must not touch the pin"


def test_missing_upstream_is_could_not_run_not_clean(rig):
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.unlink()
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "UPSTREAM MISSING" in p.stderr


def test_write_failure_is_named_not_a_traceback(rig):
    """A read-only pin dir, a file where the `pin/` directory should be, a full
    disk: the accept must say so and leave nothing half-written."""
    upstream, pin_dir = rig
    p = run("repin", *common(upstream, pin_dir), expect=3)
    (pin_dir / "pin").write_text("a file where a directory belongs")
    p = run("repin", "--yes", "--sha", shown_sha(p), *common(upstream, pin_dir), expect=2)
    assert "PIN WRITE FAILED" in p.stderr
    assert not (pin_dir / "pin.json").exists()
