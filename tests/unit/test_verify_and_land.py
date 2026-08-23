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
XCODE = ROOT / "skills" / "setup-routing" / "blocks" / "xcode-tools.md"
HYGIENE = ROOT / "skills" / "setup-routing" / "blocks" / "git-hygiene.md"


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


def test_skill_pushes_before_offering_the_landing():
    """Pushing is backup, landing is completion. Offering a merge before the work
    exists anywhere else inverts the safety order that git-hygiene establishes."""
    t = SKILL.read_text()
    push = t.index("Push first")
    offer = t.index("Then offer the landing")
    assert push < offer


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
