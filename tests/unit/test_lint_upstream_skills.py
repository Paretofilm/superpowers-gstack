"""Guard scripts/lint-skills.py E10 — upstream skill-reference validation.

E2 only ever validated THIS plugin's own skill names. Upstream names
(`superpowers:<skill>`) were unvalidated everywhere — which is precisely the
content the weekly auto-update job generates from upstream release notes. A
2026-08-17 auto-update PR proposed routing to `superpowers:writing-good-tests`,
a skill the installed Superpowers 6.3.0 does not have, and the whole gate passed.
Merged, it would have shipped a dead routing row into every generated CLAUDE.md.
"""

import importlib.util
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_lint():
    path = REPO_ROOT / "scripts" / "lint-skills.py"
    spec = importlib.util.spec_from_file_location("lint_skills_e10", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lint = load_lint()


def run_check(text: str):
    """Run E10 over `text`, returning the errors it produced (and only those)."""
    before = len(lint.errors)
    lint.check_upstream_skills(REPO_ROOT / "CLAUDE.md", text)
    found = lint.errors[before:]
    del lint.errors[before:]  # module-level list — don't leak into other tests
    return found


@pytest.mark.parametrize("name", sorted(lint.SUPERPOWERS_SKILLS))
def test_every_rostered_skill_is_accepted(name):
    assert run_check(f"invoke `/superpowers:{name}` here") == []


@pytest.mark.parametrize(
    "name,why",
    [
        ("writing-good-tests", "the exact phantom a 2026-08-17 auto-update PR proposed"),
        ("totally-made-up", "generic hallucination"),
        ("brainstorm", "near-miss on a real name (brainstorming)"),
    ],
)
def test_unknown_upstream_skill_is_rejected(name, why):
    found = run_check(f"invoke `/superpowers:{name}` here")
    assert len(found) == 1, why
    assert name in found[0] and "E10" in found[0]


def test_our_own_namespace_is_not_mistaken_for_upstream():
    """`superpowers-gstack:adapt` contains the substring `superpowers:`-adjacent
    text; the negative lookbehind must keep E10 off our own namespace (E2 owns it)."""
    assert run_check("invoke `/superpowers-gstack:adapt` here") == []


def test_roster_matches_installed_upstream_when_present():
    """Layer 2. Skipped in CI (no upstream installed) — that is why the checked-in
    roster exists at all; this asserts the roster hasn't drifted where it can be
    checked. A None return must not read as 'upstream has no skills'."""
    installed = lint.installed_superpowers_skills()
    if installed is None:
        pytest.skip("no Superpowers install on this machine (expected in CI)")
    assert installed, "found an install but zero skills — glob or SKILL.md probe is wrong"
    assert installed == lint.SUPERPOWERS_SKILLS, (
        f"roster drift — only in installed: {sorted(installed - lint.SUPERPOWERS_SKILLS)}; "
        f"only in roster: {sorted(lint.SUPERPOWERS_SKILLS - installed)}"
    )
