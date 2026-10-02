"""Guard the "fixed but I can't see it" path — skill + blocks.

The defect these protect against is not a crash; it is an omission. `xcode-tools`
went v1 through v4 describing only the simulator, so a macOS app — half of this
plugin's declared tracks — had no build or launch path at all, and nobody noticed
because nothing failed. An omission needs a test more than a bug does.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "verify-and-land" / "SKILL.md"
XCODE = ROOT / "skills" / "adapt" / "blocks" / "xcode-tools.md"
HYGIENE = ROOT / "skills" / "adapt" / "blocks" / "git-hygiene.md"


def test_xcode_block_can_build_and_launch_a_macos_app():
    """Every row in v1-v4 assumed a simulator. macOS has none."""
    t = XCODE.read_text()
    assert "platform=macOS" in t, "no macOS build command"
    assert "BUILT_PRODUCTS_DIR" in t, "no way to resolve what was just built"
    assert "ps -o comm=" in t, "no way to prove which bundle is running"


def test_xcode_block_warns_that_opening_by_name_gets_the_installed_copy():
    """Verified on a real project: `open -a SwiftConfig` resolved to
    /Applications/SwiftConfig.app, one month older than the branch build. That is
    the whole reported bug — a correct fix, invisible in the app the user opens."""
    t = XCODE.read_text()
    assert "/Applications" in t
    assert re.search(r"absolute path", t, re.I), "must say to launch by absolute path"


def test_skill_launches_by_path_and_proves_it_rather_than_assuming():
    """A skill that opens the app and asks "is it fixed?" without establishing which
    build it opened reproduces the bug it exists to prevent."""
    t = SKILL.read_text()
    assert 'open "$BUILT_PRODUCTS_DIR' in t, "must launch the absolute built path"
    assert "ps -o comm=" in t, "must prove what came up"
    assert "quit" in t.lower(), "must quit the running instance first"


def test_skill_pushes_before_landing():
    """Pushing is backup, landing is completion. Landing before the work exists
    anywhere else inverts the safety order that git-hygiene establishes. (3.5.0: the
    second step is no longer an offer in a solo or pr project, so the anchor is the
    new heading; the ordering invariant is unchanged.)"""
    t = SKILL.read_text()
    push = t.index("Push first")
    land = t.index("Then land it by the project's landing mode")
    assert push < land


def _phase7():
    t = SKILL.read_text()
    return t[t.index("## Phase 7"):t.index("## What this skill is not")]


def test_phase7_lands_by_the_projects_landing_mode_without_a_second_question():
    """3.5.0: the yes in Phase 6 is the one human review. A solo project lands through
    /land and a pr project through /ship, each directly. The old menu cost a second
    question for a decision the project had already made."""
    p7 = _phase7()
    assert re.search(r"`solo`.*?/superpowers-gstack:land", p7, re.S)
    assert re.search(r"`pr`.*?/ship", p7, re.S)
    assert "Landing mode: solo" in p7 and "Landing mode: pr" in p7
    assert "outside fenced code blocks" in " ".join(p7.split()), \
        "same line-reading rule as autoimplement Step F"


def test_phase7_never_hands_over_to_the_finishing_branch_menu():
    """That skill shows its own menu, so a handover is the double menu this change
    removes. It may only appear as a prohibition."""
    p7 = _phase7()
    assert "Merge into the default branch" not in p7
    assert re.search(r"Never hand over to `/superpowers:finishing-a-development-branch`", p7)
    assert p7.count("/superpowers:finishing-a-development-branch") == 1


def test_phase7_asks_exactly_one_question_and_only_when_the_line_is_missing():
    p7 = _phase7()
    assert p7.count("AskUserQuestion") == 1
    missing = p7[p7.index("The line is missing"):]
    assert "AskUserQuestion" in missing
    assert "Open a pull request" in missing and "keep the branch" in missing
    assert "Landing mode: solo" in missing, "must say how to make this automatic next time"


def test_phase6_gate_still_asks_the_user_to_look():
    """The human gate is the point of the skill; Phase 7 changes must not touch it."""
    t = SKILL.read_text()
    gate = t[t.index("## Phase 6"):t.index("## Phase 7")]
    assert "AskUserQuestion" in gate
    assert "Yes, it works" in gate


def test_skill_does_not_land_when_the_user_says_it_is_still_broken():
    t = SKILL.read_text()
    gate = t[t.index("## Phase 6"):t.index("## Phase 7")]
    assert re.search(r"land nothing|do not land", gate, re.I), \
        "a negative answer must explicitly forbid landing, in whatever wording"


def test_landing_guidance_requires_seeing_it_run_first():
    """The rule has to live in the emitted block, not only in the skill — otherwise
    it applies only when someone remembers to invoke the skill."""
    t = HYGIENE.read_text()
    assert "verify-and-land" in t
    assert "Tests answer" in t, "must distinguish tests from watching it run"
