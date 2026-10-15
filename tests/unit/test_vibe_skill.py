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
    assert '"$LOCK" verify --feature <feature>' in VIBE


def test_locks_stay_after_landing_as_the_record():
    assert "The lock stays after landing as the record" in VIBE
    assert "only the user unlocks" in VIBE


def test_the_two_fixed_rules_for_every_phase():
    assert "wire what you build into the app in the same round" in VIBE
    assert "every place the app already does the same job" in VIBE


def test_the_stop_list_and_the_ruling_format():
    for item in ("irreversible or destructive", "security-sensitive", "outside the worktree",
                 "force-push or a push to the default branch outside the `Landing mode:` line", "money", "licence", "real blocker"):
        assert item in VIBE, item
    assert "Pushing the feature branch for backup is pre-approved" in VIBE
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


def test_adapt_asks_the_profile_before_the_routing_draft():
    assert ADAPT.index("**Workflow profile.**") < ADAPT.index("**Skill routing draft**")
    assert "`/superpowers-gstack:vibe` with the vibe profile, `/superpowers:brainstorming` with classic" in ADAPT


def test_adapt_stages_the_created_context_skill():
    assert "run `git add` on that file" in ADAPT


def test_lessons_come_before_verify_and_landing_and_are_committed():
    steps = [m.group(0) for m in re.finditer(r"^## Step \d+: .+$", RAW, re.M)]
    idx = {k: next(i for i, s in enumerate(steps) if k in s) for k in ("Lessons", "lock must hold", "Land", "Final report")}
    assert idx["Lessons"] < idx["lock must hold"] < idx["Land"] < idx["Final report"]
    assert "lessons written after landing never reach the default branch" in VIBE
    assert "Commit the change now, on the feature branch" in VIBE


def test_the_overview_lists_the_exact_files_and_the_lock_sha_is_reported():
    assert "lists the exact files" in VIBE and "`lock` commits what is on disk" in VIBE
    assert "Send the lock commit SHA" in VIBE


def test_the_threat_model_is_stated():
    assert "mistakes and shortcuts, not against deliberate history rewriting" in VIBE


def test_verify_is_described_as_a_gate_not_proof_with_its_limits():
    assert "`verify` is a gate, not proof" in VIBE
    assert "conftest.py" in VIBE and "pytest configuration" in VIBE
    assert "After a rebase it warns" in VIBE


def test_verify_notes_the_pr_mode_relock_and_the_exemptions():
    assert "receipt changed by commit" in VIBE and "re-lock" in VIBE
    assert "`__pycache__`, `.pytest_cache` and `.DS_Store`" in VIBE


def test_the_start_choice_comes_first_with_four_ways_in():
    assert "## Step 0b: Choose how to start" in VIBE
    step = VIBE.split("## Step 0b: Choose how to start")[1].split("## Step 1")[0]
    for way in ("Brainstorm", "Hurtig", "Fra ferdig spec/plan", "Utforsk først"):
        assert way in step
    assert "one `AskUserQuestion`" in step


def test_hurtig_is_todays_intake_and_the_others_end_in_it():
    step = VIBE.split("## Step 0b: Choose how to start")[1].split("## Step 1")[0]
    assert "Hurtig" in step and "Step 1 as written" in step
    assert "every way ends in step 1" in step.lower()


def test_brainstorm_runs_without_the_gate_and_writes_no_spec():
    step = VIBE.split("## Step 0b: Choose how to start")[1].split("## Step 1")[0]
    assert "superpowers:brainstorming" in step
    assert "no spec" in step and "no HARD-GATE" in step


def test_a_ready_spec_is_reused_as_spec_md():
    step = VIBE.split("## Step 0b: Choose how to start")[1].split("## Step 1")[0]
    assert "reuse the file as `SPEC.md`" in step


def test_explore_is_read_only_and_uses_the_tier_classifier():
    step = VIBE.split("## Step 0b: Choose how to start")[1].split("## Step 1")[0]
    assert "read-only" in step and "classify-change.py" in step


def test_the_contract_names_brainstorm_as_a_start_choice_and_the_marker_is_v2():
    block = (REPO / "skills" / "adapt" / "blocks" / "vibe-contract.md").read_text()
    assert "gstack-vibe-v2" in block
    assert "Brainstorm" in block
    assert "gstack-vibe-v2" in VIBE


def test_a_pasted_goal_counts_as_approval_and_the_lock_runs_first():
    assert "whether they say ok or paste the `/goal` line, run the lock first" in VIBE


def test_step_7_names_the_file_when_no_context_skill_exists():
    assert (
        "If the project has no context skill, create "
        "`.claude/skills/<project>-context/SKILL.md`" in VIBE
    )


def test_step_8_handles_rebase_and_pr_receipt_before_the_generic_exit_1():
    i_special = VIBE.index("Re-lock cases first")
    i_generic = VIBE.index("Any other exit 1")
    assert i_special < i_generic
    assert (
        "re-locking after a rebase or a squash-merge receipt change is not editing a test"
        in VIBE
    )
