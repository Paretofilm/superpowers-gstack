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


def _mode_bullet(p7, label):
    m = re.search(rf"^\s*- \*\*`{label}`\*\* →(.*?)(?=^\s*- \*\*|\Z)", p7, re.S | re.M)
    assert m, f"no {label} bullet in Phase 7"
    return m.group(1)


def test_phase7_lands_by_the_projects_landing_mode_without_a_second_question():
    """3.5.0: the yes in Phase 6 is the one human review. A solo project lands through
    /land and a pr project through /ship, each directly. Each mode bullet must invoke its
    own landing skill and not the other one (a swap would land a pr project on main)."""
    p7 = _phase7()
    solo, pr = _mode_bullet(p7, "solo"), _mode_bullet(p7, "pr")
    assert "/superpowers-gstack:land" in solo and "/ship" not in solo
    assert "/ship" in pr and "/superpowers-gstack:land" not in pr
    assert "Landing mode: solo" in p7 and "Landing mode: pr" in p7
    assert "outside fenced code blocks" in " ".join(p7.split()), "same line-reading rule as land"


def test_phase7_follows_lands_exit_codes_and_offers_no_menu_of_its_own():
    """The old Phase 7 handed over to finishing-a-development-branch, which shows its own
    menu (two menus for one landing). land's exit-code table is the authority now; the
    finishing skill is reachable only through land's exit-8 row."""
    p7 = " ".join(_phase7().split())
    assert "Merge into the default branch" not in p7
    assert "follow `land`'s own exit-code table" in p7
    assert p7.count("/superpowers:finishing-a-development-branch") == 1
    assert "never offer `/superpowers:finishing-a-development-branch` from this skill except through that row" in p7


def test_phase7_asks_only_when_the_branch_changes_the_landing_mode():
    """A missing line is land's question (its exit-2 row asks once and records the answer),
    so Phase 7 does not ask it too. The one question left is a branch that changes the
    policy it would be landed under."""
    p7 = _phase7()
    assert p7.count("AskUserQuestion") == 1
    changes = p7[p7.index("The branch changes the landing mode"):p7.index("**`solo`**")]
    assert "AskUserQuestion" in changes
    assert 'git show "$DEFAULT_REF":CLAUDE.md' in p7
    novalid = " ".join(p7[p7.index("**No valid line**"):].split())
    assert "/superpowers-gstack:land" in novalid and "Do not ask it here as well" in novalid


def test_phase7_rechecks_the_verified_commit_before_pushing():
    """The yes covers the build the user saw. A commit made while they looked must not
    be pushed and landed on the strength of that yes."""
    p7 = _phase7()
    push = p7.index("**Push first**")
    assert "VERIFIED_HEAD" in p7[:push]
    assert "land nothing" in p7[:push]


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


def test_phase6_yes_names_the_landing_it_triggers():
    """3.5.0: Phase 7 acts on the yes without asking again (push + land, or push + PR),
    so the yes must be an informed one: the option pairs each mode with its landing, and
    records the commit the yes is about."""
    t = SKILL.read_text()
    gate = " ".join(t[t.index("## Phase 6"):t.index("### Phase 6b")].split())
    assert "lands without asking again" in gate
    assert "VERIFIED_HEAD=$(git rev-parse HEAD)" in gate
    assert re.search(r"`solo` —[^;]*?/superpowers-gstack:land", gate)
    assert re.search(r"`pr` —[^;]*?/ship", gate)
    assert "no valid line" in gate
    assert "a yes lands nothing" in gate and "detached HEAD" in gate
