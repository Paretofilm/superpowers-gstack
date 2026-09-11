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
    "**Validator detection.** ... scan the target repo's `package.json` ...\n"
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


def shown_token(diff_run) -> str:
    """The one-time token the diff run ends with — what --yes consumes."""
    return re.search(r"--yes --token ([0-9a-f]{16})", diff_run.stdout).group(1)


def accept(upstream, pin_dir):
    """The two-step accept the skill performs: show the diff, then --yes bound to it."""
    p = run("repin", *common(upstream, pin_dir), expect=3)
    return run("repin", "--yes", "--token", shown_token(p), *common(upstream, pin_dir), expect=0)


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
    """--yes is bound twice: the token proves a diff run happened and reached the
    reader, and the digest recorded beside it proves the file has not changed
    since. A weekly gstack update between the two must not be pinned unread."""
    upstream, pin_dir = rig
    shown = shown_token(run("repin", *common(upstream, pin_dir), expect=3))
    p = run("repin", "--yes", "--token", shown[:8], *common(upstream, pin_dir), expect=2)
    assert "REPIN REFUSED" in p.stderr, "half a token is a guess, not the token the run printed"
    upstream.write_text(SECTION + "changed after the diff was shown\n")
    p = run("repin", "--yes", "--token", shown, *common(upstream, pin_dir), expect=2)
    assert "upstream changed since the diff was shown" in p.stderr, \
        "the right token must not accept bytes the diff never showed"
    assert not (pin_dir / "pin.json").exists(), "nothing may be written on a refused accept"
    p = run("repin", "--yes", *common(upstream, pin_dir), expect=2)   # no --token at all
    assert "REPIN REFUSED" in p.stderr


def test_yes_without_a_diff_run_is_refused_even_with_the_right_digest(rig):
    """`check` prints the current digest, so a digest could never be the credential:
    a caller could go straight from PIN MISMATCH to --yes without seeing a diff.
    The token cannot be obtained that way — it exists only in a diff run's output."""
    upstream, pin_dir = rig
    sha = hashlib.sha256(SECTION.encode()).hexdigest()
    for candidate in (sha, sha[:16]):
        p = run("repin", "--yes", "--token", candidate, *common(upstream, pin_dir), expect=2)
        assert "no diff run recorded" in p.stderr
    assert not (pin_dir / "pin.json").exists()


def test_a_truncated_diff_cannot_yield_a_usable_token(rig):
    """The P1 the structured review found: flushing proves the kernel took the
    bytes, not that anyone read them, so `repin | head -1` completed normally and
    left a receipt — and the old --sha credential was independently obtainable
    from `check`. The token appears ONLY in the last line, after the diff."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.write_text(SECTION.replace("line two", "line two, changed upstream"))
    proc = subprocess.run(
        f"{sys.executable} {SCRIPT} repin --upstream {upstream} --pin-dir {pin_dir} | head -1",
        shell=True, capture_output=True, text=True)
    assert "--yes --token" not in proc.stdout, "a one-line view must not carry the token"
    # Even holding the digest — which `check` hands out freely — accepts nothing.
    digest = hashlib.sha256(upstream.read_bytes()).hexdigest()
    for guess in (digest[:16], "0" * 16, "f" * 16):
        run("repin", "--yes", "--token", guess, *common(upstream, pin_dir), expect=2)
    assert json.loads((pin_dir / "pin.json").read_text())["sha256"] == \
        hashlib.sha256(SECTION.encode()).hexdigest(), "the old pin must still stand"


def test_the_token_must_match_whole_not_by_prefix(rig):
    """A prefix rule would shrink the search space the token exists to provide."""
    upstream, pin_dir = rig
    shown = shown_token(run("repin", *common(upstream, pin_dir), expect=3))
    for near in (shown[:-1], shown[1:], shown[:-1] + ("0" if shown[-1] != "0" else "1")):
        run("repin", "--yes", "--token", near, *common(upstream, pin_dir), expect=2)
        assert not (pin_dir / "pin.json").exists()
    run("repin", "--yes", "--token", shown, *common(upstream, pin_dir), expect=0)


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
    p = run("repin", "--yes", "--token", "0" * 16, *common(upstream, pin_dir), expect=2)
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
    assert "--yes --token" in p.stdout


def test_usage_errors_carry_a_named_token(rig):
    """argparse also exits 2; without a token a caller would read a quoting bug
    in a user-typed path as a pin refusal."""
    upstream, pin_dir = rig
    p = run("chek", *common(upstream, pin_dir), expect=2)
    assert "USAGE ERROR" in p.stderr
    p = run("repin", "--token", *common(upstream, pin_dir), expect=2)
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
    for args in (("repin",), ("repin", "--yes", "--token", "0" * 16)):
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
    p = run("repin", "--yes", "--token", shown_token(p), *common(upstream, pin_dir), expect=2)
    assert "PIN WRITE FAILED" in p.stderr
    assert not (pin_dir / "pin.json").exists()


def test_carriage_return_in_the_diff_is_escaped(rig):
    """Codex, Fase-1 verification: a bare \\r survived visible(). splitlines keeps
    it at the end of its line, and a terminal then returns to column 0 and lets
    the next diff line overwrite the one the reader just saw — the review the
    receipt vouches for would have been of a repainted diff. Asserted on the
    escaped form: subprocess's universal newlines would hide a raw \\r."""
    upstream, pin_dir = rig
    upstream.write_text(SECTION.replace("line two", "line visible\rHIDDEN two"), newline="")
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert "\\u000d" in p.stdout, "the CR must be shown, not executed by the terminal"


def test_oversized_upstream_is_refused_by_both_commands(rig):
    """MAX_UPSTREAM_BYTES is the one guard between a botched gstack sync — or a
    hostile file dropped at the pinned path — and reading it all into memory to
    hash, decode and diff. It had no test at any size."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.write_bytes(b"x" * (4 * 1024 * 1024 + 1))
    for cmd in ("check", "repin"):
        p = run(cmd, *common(upstream, pin_dir), expect=2)
        assert "UPSTREAM UNREADABLE" in p.stderr and "larger than" in p.stderr, cmd


def test_receipt_write_failure_is_named_not_a_traceback(rig, tmp_path):
    """Its sibling PIN WRITE FAILED is tested; this branch was neither tested nor
    listed among the docstring's named exit-2 reasons, so it could regress twice
    over without anything noticing."""
    upstream, _ = rig
    blocked = tmp_path / "pin_dir_is_actually_a_file"
    blocked.write_text("not a directory")
    p = run("repin", "--upstream", str(upstream), "--pin-dir", str(blocked), expect=2)
    assert "RECEIPT WRITE FAILED" in p.stderr


def test_repin_preserves_the_committed_files_permissions(rig):
    """_atomic_write reads the OLD file's mode before replacing it, because mkstemp
    creates 0600 and a committed, world-readable file must not flip to owner-only
    on every repin. Every other test writes a file that did not exist yet — the
    0o644 fallback — so hardcoding 0o644 would pass all of them."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    pin_json, snap = pin_dir / "pin.json", pin_dir / "pin" / "plan-completion.md"
    os.chmod(pin_json, 0o640)
    os.chmod(snap, 0o640)
    upstream.write_text(SECTION.replace("line two", "line two, reworded upstream"))
    accept(upstream, pin_dir)
    assert pin_json.stat().st_mode & 0o777 == 0o640
    assert snap.stat().st_mode & 0o777 == 0o640


@pytest.mark.parametrize("cp,name", [(0x200E, "LRM"), (0x200F, "RLM"), (0x061C, "ALM")])
def test_bidi_marks_are_escaped_and_warned_like_the_overrides(rig, cp, name):
    """Security lens, 2.52.0: LRM/RLM/ALM are Bidi_Control and invisible in a
    terminal, but sat outside both _BIDI and _ZERO_WIDTH — so a crafted upstream
    reached the confirmation diff unescaped AND unflagged, which is exactly what
    the code's own comment promises cannot happen."""
    ch, esc = chr(cp), f"\\u{cp:04x}"
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.write_text(SECTION.replace("line two", f"line {ch}two"))
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert ch not in p.stdout, f"{name} reached the diff unescaped"
    assert esc in p.stdout, f"{name} should render as {esc}"
    assert "INVISIBLE CHARS" in p.stderr, name


def test_format_set_is_exactly_unicode_category_cf():
    """Two review rounds each found one more invisible character the hand-picked
    set had missed (LRM/RLM/ALM, then U+2060 WORD JOINER). The set is now the
    whole Cf category, enumerated as ranges for speed — this test is what keeps
    the enumeration honest, and what will tell a future reader exactly which
    codepoints to add when Python ships a newer Unicode."""
    import unicodedata
    invisible = module()._INVISIBLE
    cf = {c for c in range(0x110000) if unicodedata.category(chr(c)) == "Cf"}
    missing = sorted(c for c in cf if not invisible.fullmatch(chr(c)))
    extra = sorted(c for c in range(0x110000)
                   if invisible.fullmatch(chr(c)) and unicodedata.category(chr(c)) != "Cf")
    assert not missing, (f"Unicode {unicodedata.unidata_version} has Cf characters _FORMAT "
                         f"does not cover: {[hex(c) for c in missing]}")
    assert not extra, f"_FORMAT covers non-Cf characters: {[hex(c) for c in extra]}"


def test_a_diff_that_never_reached_stdout_leaves_no_receipt(rig):
    """The receipt certifies that a human SAW the diff. stdout is buffered, so a
    closed pipe (`repin | head`) failed at flush AFTER the receipt was already on
    disk — and --yes would then accept never-shown bytes, with the credential lifted
    from `check`'s output. Codex, 2.52.0; reproduced before the fix."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.write_text(SECTION.replace("line two", "line two, changed upstream"))
    p = subprocess.Popen([sys.executable, str(SCRIPT), "repin", *common(upstream, pin_dir)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.stdout.close()          # the reader goes away before the diff is flushed
    p.stderr.read()
    assert p.wait() == 2, "an undelivered diff is not a confirmation"
    assert not (pin_dir / ".repin-receipt").is_file(), \
        "a receipt for a diff nobody saw re-authorises --yes"


def test_an_astral_format_character_is_escaped_readably(rig):
    """Tag characters (U+E0020-E007F) are the astral half of the invisible
    problem. `\\u{:04x}` would render U+E0020 as a 5-digit escape no convention
    defines; above the BMP the escape is `\\U` + 8 digits, like Python's own."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.write_text(SECTION.replace("line two", "line \U000e0020two"))
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert "\U000e0020" not in p.stdout and r"\U000e0020" in p.stdout
    assert "INVISIBLE CHARS" in p.stderr


def test_the_receipt_stores_a_hash_not_the_token(rig):
    """Truncated tool output still writes a receipt, and the agent this guard
    constrains can read files. A token stored verbatim would be recoverable with
    one `cat` by the very reader who never saw the diff — so the file holds
    sha256(token), and the token itself exists only in that run's last line.
    Codex structured review, 2.52.0."""
    upstream, pin_dir = rig
    p = run("repin", *common(upstream, pin_dir), expect=3)
    token = shown_token(p)
    receipt = (pin_dir / ".repin-receipt").read_text()
    assert token not in receipt, "the token must not be recoverable by reading the receipt"
    stored_hash, stored_sha = receipt.splitlines()
    assert stored_hash == hashlib.sha256(token.encode()).hexdigest()
    assert stored_sha == hashlib.sha256(SECTION.encode()).hexdigest()
    # Submitting what the file contains gets nowhere; the real token still works.
    run("repin", "--yes", "--token", stored_hash, *common(upstream, pin_dir), expect=2)
    run("repin", "--yes", "--token", token, *common(upstream, pin_dir), expect=0)


def test_a_heading_only_inside_a_code_fence_is_not_an_anchor(rig):
    """Upstream can rename a real heading while an old copy survives in a ```
    example. The override targeting it would then silently stop applying, so
    structural anchors are matched with fenced blocks masked out. Phrase anchors
    like `<base>` keep the raw text — those genuinely live in Step 8's own bash
    blocks. Codex structured review, 2.52.0."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    fenced = SECTION.replace("### Gate Logic", "### Decision Logic", 1) \
                    .replace("## Step 8.1", "```\n### Gate Logic\n```\n\n## Step 8.1", 1)
    upstream.write_text(fenced)
    p = run("repin", *common(upstream, pin_dir), expect=2)
    assert "ANCHORS MISSING" in p.stderr and "### Gate Logic" in p.stderr
    assert not (pin_dir / ".repin-receipt").exists(), "a blocked repin writes no receipt"


def test_an_unclosed_fence_masks_to_the_end_of_the_document(rig):
    """Third lens (DeepSeek) argued a mismatched fence (open ~~~~, close ```) goes
    unmasked, letting a planted heading extend the checked span. It does the
    opposite: `_FENCE`'s `\\Z` branch means an unclosed fence masks everything
    after it, so a planted boundary heading DISAPPEARS and the check refuses.
    Fail-closed. This test exists because the claim was plausible enough to need
    a permanent answer."""
    upstream, pin_dir = rig
    planted = SECTION.replace(
        "\n## Step 8.1: Plan Verification",
        "\n~~~~\n## Step 8.1 planted inside an unclosed fence\n```\n\n## Step 8.1: Plan Verification", 1)
    upstream.write_text(planted)
    p = run("repin", *common(upstream, pin_dir), expect=2)
    assert "ANCHORS MISSING" in p.stderr and "## Step 8.1" in p.stderr


def test_unfenced_preserves_offsets_and_line_numbers(rig):
    """missing_anchors indexes the masked text and slices the raw one with the
    same offsets. If masking changed either length, the two spans would drift
    apart and a phrase anchor could be searched in the wrong region."""
    m = module()
    for text in (SECTION,
                 SECTION + "\n```python\nx = 1\n```\ntail\n",
                 SECTION + "\n~~~\nunclosed to the end\n"):
        masked = m.unfenced(text)
        assert len(masked) == len(text)
        assert masked.count("\n") == text.count("\n")


# --- gstack ≥ 1.83: the subagent prompt lives inside a ````text fence -----------
#
# Upstream 1.83 moved Step 8's subagent prompt out of a `> ` blockquote and into a
# four-backtick `text` fence, so the prompt's own headings (`### Plan File
# Discovery`, `**Validator detection.**`) now sit inside a fence. The fence mask
# that keeps a heading in a ``` example from counting as structure blanked the
# prompt too, and `repin` refused every 1.83+ install with ANCHORS MISSING. The
# prompt fence IS the section — the text the wrapper's overrides address — so it is
# scanned like prose, while fences nested inside it stay masked.

SECTION_PROMPT_FENCED = (
    "## Step 8: Plan Completion Audit\n\n"
    "**Subagent prompt:** Pass these instructions to the subagent:\n\n"
    "````text\n"
    "You are running a ship-workflow plan completion audit. The base branch is `<base>`.\n\n"
    "### Plan File Discovery\n"
    "line two\n"
    "```bash\n"
    "PLAN=$(ls -t \"$PLAN_DIR\"/*.md)\n"
    "```\n"
    "**Validator detection.** ... scan the target repo's `package.json` ...\n"
    '{"total_items":N,"done":N,"changed":N,"partial":N,"not_done":N}\n'
    "````\n\n"
    "**Parent processing:**\n\n"
    "### Gate Logic\n"
    "**Include in PR body (Step 19):** ...\n"
    "\n## Step 8.1: Plan Verification\n"
    "line three\n"
)


def test_the_subagent_prompt_fence_is_the_section_not_an_example(rig):
    """The shape gstack 1.84.1 ships: every anchor is present, two of them only
    inside the prompt fence. repin must show the diff and hand out a token."""
    upstream, pin_dir = rig
    upstream.write_text(SECTION_PROMPT_FENCED)
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert "ANCHORS: all present" in p.stdout, p.stderr
    accept(upstream, pin_dir)
    p = run("check", *common(upstream, pin_dir), expect=0)
    assert "PIN OK" in p.stdout


def test_a_text_fence_without_the_subagent_prompt_label_is_still_masked(rig):
    """Only the fence that follows `**Subagent prompt:**` is transparent. A
    ````text block anywhere else is an example, and a heading inside it is not
    structure."""
    upstream, pin_dir = rig
    upstream.write_text(SECTION_PROMPT_FENCED.replace(
        "**Subagent prompt:** Pass these instructions to the subagent:\n\n", ""))
    p = run("repin", *common(upstream, pin_dir), expect=2)
    assert "ANCHORS MISSING" in p.stderr and "### Plan File Discovery" in p.stderr


def test_a_heading_in_a_fence_nested_inside_the_prompt_is_not_an_anchor(rig):
    """The prompt fence is transparent; fences INSIDE it are not. A renamed real
    heading with the old name surviving in the prompt's own bash example must
    still refuse."""
    upstream, pin_dir = rig
    nested = SECTION_PROMPT_FENCED.replace(
        "### Plan File Discovery\nline two\n",
        "### Plan Discovery\nline two\n").replace(
        "PLAN=$(ls -t \"$PLAN_DIR\"/*.md)\n",
        "PLAN=$(ls -t \"$PLAN_DIR\"/*.md)\n### Plan File Discovery\n")
    upstream.write_text(nested)
    p = run("repin", *common(upstream, pin_dir), expect=2)
    assert "ANCHORS MISSING" in p.stderr and "### Plan File Discovery" in p.stderr


def test_an_unclosed_prompt_fence_is_transparent_to_the_end(rig):
    """Only a CLOSED prompt fence is transparent. An unclosed one is a broken
    upstream: `_FENCE` masks it to EOF, the boundary heading after it disappears,
    and the check refuses — the fail-closed direction."""
    upstream, pin_dir = rig
    upstream.write_text(SECTION_PROMPT_FENCED.replace("````\n\n**Parent processing:**", "**Parent processing:**", 1))
    p = run("repin", *common(upstream, pin_dir), expect=2)
    assert "ANCHORS MISSING" in p.stderr and "## Step 8.1" in p.stderr


def test_unfenced_keeps_offsets_with_a_prompt_fence():
    m = module()
    for text in (SECTION_PROMPT_FENCED,
                 SECTION_PROMPT_FENCED + "\n~~~\nunclosed\n",
                 SECTION_PROMPT_FENCED.replace("````\n\n**Parent", "**Parent", 1)):
        masked = m.unfenced(text)
        assert len(masked) == len(text)
        assert masked.count("\n") == text.count("\n")
    masked = m.unfenced(SECTION_PROMPT_FENCED)
    assert "### Plan File Discovery" in masked, "the prompt fence is scanned as prose"
    assert 'PLAN=$(ls' not in masked, "a fence nested in the prompt stays masked"
    assert "### Gate Logic" in masked
