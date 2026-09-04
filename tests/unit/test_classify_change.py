"""Tests for scripts/classify-change.py — the mechanical tier floor (2.51.0).

The point of the script is that the tier gate stops being a model's self-report.
These tests are what stops IT from being prose in turn: each one asserts a floor
that must hold, and the --assert-tier direction (escalation allowed, downgrade
refused) which is the whole contract.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "classify-change.py"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


@pytest.fixture()
def repo(tmp_path):
    """A git repo with one committed baseline file."""
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("baseline\n")
    git(tmp_path, "add", "README.md")
    git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def run(repo, *args, expect=0):
    p = subprocess.run([sys.executable, str(SCRIPT), *args],
                       cwd=repo, capture_output=True, text=True)
    assert p.returncode == expect, f"exit {p.returncode}, stderr: {p.stderr}"
    return p


def classify(repo, *args):
    return json.loads(run(repo, *args).stdout)


# --- floor computation --------------------------------------------------------

def test_docs_only_is_trivial(repo):
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text("hello\n")
    assert classify(repo)["floor_tier"] == "trivial"


def test_tests_only_is_trivial(repo):
    (repo / "tests").mkdir()
    (repo / "tests" / "test_thing.py").write_text("def test_x():\n    assert True\n")
    assert classify(repo)["floor_tier"] == "trivial"


def test_runtime_source_is_ship_worthy(repo):
    (repo / "app.py").write_text("def add(a, b):\n    return a + b\n")
    out = classify(repo)
    assert out["floor_tier"] == "ship-worthy"
    assert any("runtime source" in r for r in out["reasons"])


def test_version_file_alone_is_ship_worthy(repo):
    (repo / "package.json").write_text('{"version": "1.2.3"}\n')
    assert classify(repo)["floor_tier"] == "ship-worthy"


def test_changelog_alone_is_ship_worthy(repo):
    """CHANGELOG is a .md file, but the tier table says an entry means ship-worthy."""
    (repo / "CHANGELOG.md").write_text("## [1.0.0]\n")
    out = classify(repo)
    assert out["floor_tier"] == "ship-worthy"
    assert any("CHANGELOG" in r for r in out["reasons"])


def test_instruction_surface_md_is_not_docs(repo):
    """A .md under skills/ is agent runtime behaviour — the product, not documentation."""
    (repo / "skills" / "thing").mkdir(parents=True)
    (repo / "skills" / "thing" / "SKILL.md").write_text("# do the thing\n")
    out = classify(repo)
    assert out["floor_tier"] == "ship-worthy"
    assert any("instruction surface" in r for r in out["reasons"])


@pytest.mark.parametrize("path", [
    "src/auth/login.py",
    "db/migrations/001_add.sql",
    "api/openapi.yaml",
    "audio/scheduler.swift",
])
def test_high_stakes_paths(repo, path):
    p = repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x = 1\n")
    out = classify(repo)
    assert out["floor_tier"] == "high-stakes", path
    assert out["signals"], path


@pytest.mark.parametrize("body,label", [
    ("import subprocess\nsubprocess.run(['ls'])\n", "security"),
    ("ALTER TABLE users ADD COLUMN x int;\n", "migration"),
    ("let q = DispatchQueue(label: \"x\")\n", "real-time-concurrency"),
])
def test_high_stakes_content(repo, body, label):
    (repo / "plain.txt.py").write_text(body)
    out = classify(repo)
    assert out["floor_tier"] == "high-stakes"
    assert label in {s["label"] for s in out["signals"]}


def test_size_proxy_promotes_to_high_stakes(repo):
    for i in range(9):
        (repo / f"mod{i}.py").write_text("value = 1\n")
    out = classify(repo)
    assert out["floor_tier"] == "high-stakes"
    assert "architecture-scale" in {s["label"] for s in out["signals"]}


def test_content_signal_reads_added_lines_only(repo):
    """A signal must describe what the change INTRODUCES, not its surroundings.

    Deleting the only concurrency line must not keep reporting concurrency.
    """
    (repo / "svc.py").write_text("import threading\nlock = threading.Lock()\nx = 1\n")
    git(repo, "add", "svc.py")
    git(repo, "commit", "-qm", "add svc")
    (repo / "svc.py").write_text("x = 2\n")
    out = classify(repo)
    assert "real-time-concurrency" not in {s["label"] for s in out["signals"]}


def test_untracked_new_file_is_seen(repo):
    """git diff shows nothing for an untracked file; a new file is the most
    review-worthy thing a change can contain."""
    (repo / "brand_new.py").write_text("def f():\n    return 1\n")
    out = classify(repo)
    assert "brand_new.py" in out["target"]["files"]
    assert out["floor_tier"] == "ship-worthy"


# --- the contract: escalate yes, downgrade no ---------------------------------

def test_assert_tier_allows_escalation(repo):
    (repo / "docs.md").write_text("hi\n")          # floor: trivial
    run(repo, "--assert-tier", "high-stakes", expect=0)


def test_assert_tier_accepts_exact_floor(repo):
    (repo / "app.py").write_text("x = 1\n")        # floor: ship-worthy
    run(repo, "--assert-tier", "ship-worthy", expect=0)


def test_assert_tier_refuses_downgrade(repo):
    (repo / "app.py").write_text("x = 1\n")        # floor: ship-worthy
    p = run(repo, "--assert-tier", "trivial", expect=1)
    assert "BELOW the computed floor" in p.stderr


def test_assert_tier_refuses_downgrade_from_high_stakes(repo):
    (repo / "auth").mkdir()
    (repo / "auth" / "session.py").write_text("x = 1\n")
    p = run(repo, "--assert-tier", "ship-worthy", expect=1)
    assert "high-stakes" in p.stderr


# --- target naming (improvement 2) --------------------------------------------

def test_target_is_named_in_the_verdict_header(repo):
    (repo / "app.py").write_text("x = 1\n")
    out = classify(repo)
    assert out["target"]["spec"]
    assert out["target"]["spec"] in out["verdict_header"]
    assert out["floor_tier"] in out["verdict_header"]


def test_files_mode_uses_the_same_spelling_as_third_lens(repo):
    """--files/--diff/--diff-base must match third-lens-review.py so Stage 0 and
    Stage 3 can be pointed at one artifact."""
    (repo / "a.py").write_text("import subprocess\nsubprocess.run([\"ls\"])\n")
    out = classify(repo, "--files", "a.py")
    assert out["target"]["mode"] == "files"
    assert out["target"]["files"] == ["a.py"]
    assert out["floor_tier"] == "high-stakes"

    tlr = (REPO / "scripts" / "third-lens-review.py").read_text()
    for flag in ('"--files"', '"--diff"', '"--diff-base"'):
        assert flag in tlr, f"{flag} missing from third-lens-review.py"
        assert flag in SCRIPT.read_text(), f"{flag} missing from classify-change.py"


def test_no_changes_exits_5(repo):
    run(repo, expect=5)


def test_floor_only_contract_is_stated_in_output(repo):
    (repo / "app.py").write_text("x = 1\n")
    assert "floor only" in classify(repo)["contract"]


# --- self-pitfall findings, round 1 (2.51.0) ----------------------------------

def load_module():
    """Import the script by path — its filename is not a valid module name."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("classify_change", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_degraded_scan_is_reported_not_silent():
    """Files changed but no diff body means the content and size signals never ran.

    That loses signal in the DOWNWARD direction — the one failure the gate exists to
    prevent — so it must be stated, never absorbed into a confident floor.
    """
    m = load_module()
    floor, signals, reasons = m.classify(["app.py"], "", "diff", degraded=True)
    assert any(r.startswith("DEGRADED") for r in reasons)
    assert floor == "ship-worthy"          # paths alone still clear trivial

    floor, _, reasons = m.classify(["app.py"], "+x = 1\n", "diff", degraded=False)
    assert not any("DEGRADED" in r for r in reasons)


def test_degraded_flag_is_present_on_a_normal_run(repo):
    (repo / "app.py").write_text("x = 1\n")
    assert classify(repo)["target"]["degraded"] is False


def test_binary_diff_does_not_crash_the_gate(repo):
    """text=True decodes strictly; a binary hunk must not kill the gate with a
    traceback instead of a tier."""
    (repo / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)))
    out = classify(repo)          # non-zero exit would fail in run()
    assert out["floor_tier"] in ["trivial", "ship-worthy", "high-stakes"]


# --- multi-lens review findings on the gate itself (2.51.0) -------------------
# Codex and a re-read of the resolver found four ways the computed floor came out
# BELOW the truth — the only failure direction that matters, since a low floor
# silently skips the lens that would have caught the bug.

@pytest.mark.parametrize("path,label", [
    # CamelCase: the boundary used to require a separator, so every Swift and
    # TypeScript name below scored no signal at all. This repo is dual-track.
    ("AuthManager.swift", "security"),
    ("authService.ts", "security"),
    ("Sources/App/SessionStore.swift", "security"),
    ("OAuthClient.swift", "security"),
    ("KeychainStore.swift", "security"),
    ("AudioEngine.swift", "real-time-concurrency"),
    ("WebSocketClient.swift", "real-time-concurrency"),
    ("StreamingPlayer.swift", "real-time-concurrency"),
    ("SchemaBuilder.swift", "migration"),
    # plurals
    ("sessions/store.py", "security"),
    ("tokens/mint.go", "security"),
    # still-working snake_case, so the fix did not trade one convention for another
    ("src/auth/login.py", "security"),
    ("lib/audio_engine.c", "real-time-concurrency"),
    ("db/migrations/001.py", "migration"),
])
def test_high_stakes_paths_survive_camelcase_and_plurals(path, label):
    m = load_module()
    hits = {lbl for lbl, rx in m.HIGH_STAKES_PATH if rx.search(path)}
    assert label in hits, f"{path} should signal {label}, got {hits or 'nothing'}"


@pytest.mark.parametrize("path", [
    "src/tokenizer.py",      # token + izer — NLP, not auth
    "streamlit_app.py",      # stream + lit
    "lib/streamline.js",
    "docs/authors.md",       # auth + ors
    "README.md",
    "scripts/lint-skills.py",
])
def test_high_stakes_paths_stay_narrow(path):
    """A signal that fires on everything gates nothing — the widened boundary must
    still reject a longer lowercase word."""
    m = load_module()
    hits = {lbl for lbl, rx in m.HIGH_STAKES_PATH if rx.search(path)}
    assert not hits, f"{path} falsely signalled {hits}"


def test_diff_base_without_diff_is_honoured_not_silently_dropped(repo):
    """`--diff-base main` used to fall through to auto mode, which on a dirty tree
    classifies the WORKING TREE — a downgrade reached by typo."""
    (repo / "auth.py").write_text("import subprocess\n")
    git(repo, "add", "auth.py")
    git(repo, "commit", "-qm", "add auth")
    git(repo, "checkout", "-qb", "feature")
    (repo / "migrations.py").write_text("ALTER TABLE users ADD COLUMN x\n")
    git(repo, "add", "migrations.py")
    git(repo, "commit", "-qm", "migration")
    (repo / "stray.txt").write_text("untracked noise\n")   # the hijacker

    out = classify(repo, "--diff-base", "main")
    assert out["target"]["mode"] == "diff"
    assert "main" in out["target"]["spec"]
    assert out["floor_tier"] == "high-stakes"


def test_diff_wins_over_files_matching_third_lens_precedence(repo):
    """third-lens-review.py resolves --diff and ignores --files. Winning the other
    way here would hand Stage 0 and Stage 3 different artifacts for one argv."""
    (repo / "plain.md").write_text("nothing interesting\n")
    (repo / "sched.py").write_text("import threading\nthreading.Lock()\n")
    git(repo, "add", "sched.py")
    git(repo, "commit", "-qm", "sched")
    git(repo, "checkout", "-qb", "feature")
    (repo / "sched.py").write_text("import threading\nthreading.Lock()\nDispatchQueue\n")

    out = classify(repo, "--diff", "--diff-base", "main", "--files", "plain.md")
    assert out["target"]["mode"] == "diff"


def test_untracked_file_does_not_mask_a_failed_tracked_diff():
    """Synthesised untracked hunks are appended to the diff body, so a failed
    `git diff` plus one untracked file used to report degraded=False — hiding the
    loss behind unrelated content."""
    m = load_module()
    # tracked file present in the file list, but no tracked diff body: degraded.
    floor, _, reasons = m.classify(["tracked.py", "new.py"], "+x = 1\n", "diff",
                                   degraded=True)
    assert any(r.startswith("DEGRADED") for r in reasons)


def test_third_lens_sees_the_untracked_files_the_floor_was_computed_from():
    """Stage 0 can escalate BECAUSE of a new file; Stage 3 must not then review an
    artifact that excludes it."""
    tlr = (REPO / "scripts" / "third-lens-review.py").read_text()
    assert "--others" in tlr and "--exclude-standard" in tlr, \
        "third-lens-review.py must fold in untracked files like classify-change.py"


# --- third-house (GLM-5.2) findings on the patched gate ----------------------

def test_degraded_travels_on_the_verdict_header_not_only_in_reasons():
    """The skill tells the agent to copy verdict_header into its verdict. A degraded
    run whose warning lived only in `reasons` produced an audit line identical to a
    fully computed clean result."""
    m = load_module()
    target = {"spec": "git diff main", "degraded": True}
    assert "DEGRADED" in m.header(target, "ship-worthy", [])
    assert "DEGRADED" not in m.header({"spec": "git diff main", "degraded": False},
                                      "ship-worthy", [])


def test_target_carries_degraded_in_every_mode(repo):
    """A consumer reading target['degraded'] must not KeyError depending on which
    flag the caller used."""
    (repo / "a.py").write_text("x = 1\n")
    assert classify(repo, "--files", "a.py")["target"]["degraded"] is False
    assert classify(repo)["target"]["degraded"] is False


def test_diff_base_with_files_warns_instead_of_being_dropped(repo):
    (repo / "a.py").write_text("x = 1\n")
    p = run(repo, "--files", "a.py", "--diff-base", "main")
    assert "--diff-base" in p.stderr and "ignored" in p.stderr


def test_stage0_and_stage3_resolve_the_same_file_set(repo):
    """The 'one artifact by construction' claim, asserted behaviourally rather than
    by grepping both files for the same flag strings."""
    (repo / "tracked.py").write_text("import subprocess\n")
    git(repo, "add", "tracked.py")
    git(repo, "commit", "-qm", "tracked")
    git(repo, "checkout", "-qb", "feature")
    (repo / "tracked.py").write_text("import subprocess\nsubprocess.run(['ls'])\n")
    (repo / "brand_new.py").write_text("DispatchQueue.main.async {}\n")   # untracked

    stage0 = classify(repo, "--diff", "--diff-base", "main")
    assert set(stage0["target"]["files"]) == {"tracked.py", "brand_new.py"}

    tlr = REPO / "scripts" / "third-lens-review.py"
    p = subprocess.run([sys.executable, str(tlr), "--diff", "--diff-base", "main",
                        "--dry-run"], cwd=repo, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    # Stage 3 must have seen the untracked file the floor was escalated from.
    body = subprocess.run([sys.executable, "-c",
                           "import sys;sys.path.insert(0,%r);" % str(tlr.parent) +
                           "import importlib.util;"
                           "spec=importlib.util.spec_from_file_location('t',%r);" % str(tlr) +
                           "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
                           "import argparse;"
                           "a=argparse.Namespace(diff=True,diff_base='main',files=[]);"
                           "print(m.gather_content(a))"],
                          cwd=repo, capture_output=True, text=True)
    assert "brand_new.py" in body.stdout, \
        "third-lens-review.py did not include the untracked file Stage 0 classified"
