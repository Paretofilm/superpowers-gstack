"""The vibe skill's contract: one intake, one checkpoint, locked tests, one review, landing.

The skill is prose an agent follows; these tests pin the sentences whose loss would
silently bring back the stops the workflow exists to remove, or drop a guard.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAW = (REPO / "skills" / "vibe" / "SKILL.md").read_text()
# The prose wraps lines; assert against whitespace-normalised text.
VIBE = " ".join(RAW.split())


def test_the_description_fits_the_budget():
    desc = re.search(r"^description: (.+)$", RAW, re.M).group(1)
    assert len(desc.split()) <= 30


def test_intake_is_one_round_with_acceptance_criteria_and_out_of_scope():
    assert "one `AskUserQuestion` round" in VIBE
    assert "at most eight questions" in VIBE
    assert "acceptance criteria" in VIBE and "out of scope" in VIBE


def test_the_one_checkpoint_carries_a_goal_line_and_locks_the_tests():
    assert "/goal All tasks in PLAN.md are done" in VIBE
    assert "scripts/lock-acceptance-tests.py" in VIBE
    assert '"$LOCK" lock --feature' in VIBE
    assert '"$LOCK" verify' in VIBE


def test_the_two_fixed_rules_for_every_phase():
    assert "wire what you build into the app in the same round" in VIBE
    assert "every place the app already does the same job" in VIBE


def test_the_stop_list_and_the_ruling_format():
    for item in ("irreversible or destructive", "security-sensitive", "outside the worktree",
                 "push to a remote", "money", "licence", "real blocker"):
        assert item in VIBE, item
    assert "Ruling: <choice> — <why> — <cost if wrong>" in VIBE


def test_one_review_at_the_end_and_landing_by_the_landing_mode():
    assert "/superpowers-gstack:pitfall-verification" in VIBE
    assert "once, after the last phase" in VIBE
    assert "Landing mode:" in VIBE and "/superpowers-gstack:land" in VIBE


def test_lessons_go_to_the_context_skill_not_claude_md():
    assert "ROUNDS.md" in VIBE and "at most three" in VIBE
    assert "How we work" in VIBE
    assert "never into CLAUDE.md" in VIBE


def test_the_skill_never_enters_plan_mode_itself():
    assert "Do not enter plan mode yourself" in VIBE


ADAPT_RAW = (REPO / "skills" / "adapt" / "SKILL.md").read_text()
ADAPT = " ".join(ADAPT_RAW.split())


def test_adapt_asks_for_the_profile_once_and_pins_it_committably():
    assert "**Workflow profile.**" in ADAPT
    assert "If `.gstack/workflow` exists the script reads and validates it; do not re-ask." in ADAPT
    assert "printf '%s\\n' \"$PROFILE\" > .gstack/workflow" in ADAPT_RAW
    assert "git add -f .gstack/workflow" in ADAPT


def test_adapt_defaults_to_classic_with_nobody_to_answer():
    assert "nobody to answer" in ADAPT and "writes no `.gstack/workflow`" in ADAPT


def test_adapt_lists_contradictions_with_the_vibe_contract():
    assert "contradicts the vibe contract" in ADAPT


def test_adapt_points_a_vibe_project_at_the_vibe_skill():
    assert "/superpowers-gstack:vibe" in ADAPT
