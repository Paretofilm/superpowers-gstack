"""Guard skills/spec-drift/SKILL.md — a wrapper that must stay a wrapper.

The failure this skill invites is not a crash but a slow copy: someone pastes
Step 8's text into SKILL.md "for robustness", brings back the plan-discovery
heuristics "for convenience", or drops the hash check "because it keeps
failing". Each is a one-line edit that turns the wrapper into a fork. These
tests make each of those edits red.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO / "skills" / "spec-drift"
SKILL = (SKILL_DIR / "SKILL.md").read_text()
UPSTREAM_PATH = "~/.claude/skills/gstack/ship/sections/plan-completion.md"


def test_skill_reads_the_upstream_section_from_disk():
    assert UPSTREAM_PATH in SKILL
    assert "<SECTION_PATH>" in SKILL and "Read this file in full" in SKILL, \
        "the dispatched subagent must be told to read the section, not handed a copy"


def test_skill_never_inlines_step_8():
    """Phrases that exist only in the upstream section. Any of them in SKILL.md
    means the text was copied — and the hash pin now guards a copy. The line
    budget is the structural half of the same guard: a paraphrased paste dodges
    the needles but not the size."""
    for needle in ("Path concreteness rule", "Be conservative with DONE",
                   "_PLAN_SLUG=", "VAS-449", "Validator detection"):
        assert needle not in SKILL, f"{needle!r} is Step 8 text — read it from disk, do not paste it"
    assert SKILL.count("\n") < 300, \
        "Step 8 alone is ~190 lines; a wrapper that grew past 300 has probably swallowed it"


def test_skill_has_no_plan_discovery_heuristics():
    for needle in (r"-mmin", r"ls -t", r"grep -l", r"\.gstack/plans", r"\.claude/plans"):
        assert not re.search(needle, SKILL), f"{needle!r} is a discovery fallback — the plan path is an argument"
    assert "The plan path is an argument, never discovered." in SKILL


def test_hash_check_runs_before_the_audit_is_dispatched():
    check = SKILL.index('spec-drift.py" check')
    dispatch = SKILL.index("run_in_background: false")
    assert check < dispatch


def test_repin_shows_the_diff_and_asks_before_writing():
    repin = SKILL[SKILL.index("## Re-pin mode"):]
    shown = repin.index('spec-drift.py" repin')
    ask = repin.index("AskUserQuestion")
    yes = repin.index("repin --yes")
    assert shown < ask < yes, "diff first, then the question, then --yes"


def test_output_contract_matches_step_8():
    for key in ("total_items", "done", "changed", "deferred", "unverifiable", "summary"):
        assert f'"{key}"' in SKILL
    for code in ("exit 0", "exit 1", "exit 2"):
        assert code in SKILL
    assert 'spec-drift.py" verdict' in SKILL, "the exit code is computed, not judged"


def test_skill_reports_only():
    assert re.search(r"never\s+(edits?|modif(y|ies))\s+(source|code)", SKILL, re.I)
    assert "Do not commit, push" in SKILL


def test_pin_and_snapshot_are_committed_together():
    pin = json.loads((SKILL_DIR / "pin.json").read_text())
    snapshot = SKILL_DIR / "pin" / "plan-completion.md"
    assert pin["sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()
    assert pin["gstack_version"] != "unknown"


def test_skill_is_routed_everywhere_the_lint_does_not_check():
    """Lint E3 checks CLAUDE.md only. The two generator tables, the model-routing
    table and the README are where every OTHER project learns the skill exists."""
    for rel in ("skills/setup-routing/SKILL.md", "skills/adapt/SKILL.md",
                "skills/setup-routing/model-routing.md", "README.md"):
        assert "superpowers-gstack:spec-drift" in (REPO / rel).read_text(), rel
