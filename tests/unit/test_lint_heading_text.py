"""Guard scripts/lint-skills.py::heading_text — E8's inline-copy detector.

E8 exists to stop an emitted block from being hand-duplicated in a generator.
For four releases it missed the Session Continuity duplication because the copy
sat indented inside a fenced example and the check was a bare
`line.startswith("#")`. Normalizing fixed that but opened the opposite risk: a
blanket `[-*+]*` prefix class also eats a `---` rule and exposes a following
`#`, flagging lines that are not headings at all.

Both directions are release-gating, so both are pinned here.
"""

import importlib.util
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_lint():
    """Load scripts/lint-skills.py (hyphenated → not import-able normally)."""
    path = REPO_ROOT / "scripts" / "lint-skills.py"
    spec = importlib.util.spec_from_file_location("lint_skills", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lint = load_lint()


# Every disguise a re-paste of an emitted block can wear. Each of these must
# normalize to the same text, or E8 silently stops guarding that form.
@pytest.mark.parametrize(
    "line,why",
    [
        ("## Session Continuity", "plain H2"),
        ("### Session Continuity", "H3 root, as pre-2.36.0 setup-routing emitted"),
        ("  ## Session Continuity", "indented — the form that hid for four releases"),
        ("> ## SESSION CONTINUITY ##", "blockquote + case + ATX closing hashes"),
        ("- ## Session Continuity", "list-marker prefix"),
        (
            "## Session Continuity <!-- gstack-session-continuity-v1 -->",
            "carrying the version marker",
        ),
    ],
)
def test_heading_disguises_all_normalize(line, why):
    assert lint.heading_text(line) == "session continuity", why


# Lines that are NOT headings. A false positive here blocks a legitimate
# release, which erodes trust in the gate faster than a missed duplication.
@pytest.mark.parametrize(
    "line,why",
    [
        ("--- # not a heading", "horizontal rule followed by a hash"),
        ("well-formed # inline hash", "hyphenated token, hash mid-line"),
        ("1. **Heading present + marker matches**", "numbered-list prose"),
        ("Scan for `^#{2,3} Session Continuity`", "prose quoting the scan regex"),
        ("", "empty line"),
        ("-*+->#", "prefix chars with no separating space — not a list item"),
    ],
)
def test_non_headings_return_none(line, why):
    assert lint.heading_text(line) is None, why


def test_block_headings_are_discoverable():
    """The shared blocks must all expose a parseable H2 heading — E8 builds its
    comparison set from exactly this call, so a block whose first line stopped
    parsing would disable the guard for that block without failing loudly."""
    blocks = REPO_ROOT / "skills" / "setup-routing" / "blocks"
    for name in lint.MARKER_BLOCKS:
        first = (blocks / name).read_text().split("\n", 1)[0]
        assert lint.heading_text(first), f"{name} first line is not a parseable heading"


# --- E9: bare plugin-skill references inside emitted blocks (2.36.1) ----------
# blocks/*.md is pasted verbatim into other projects, where `/htmlify` does not
# resolve — only `/superpowers-gstack:htmlify` does. Three bare references had
# shipped to every adopting project before this guard existed.

OWN = ["htmlify", "adapt", "e2e-route", "pitfall-verification", "context-handoff"]


@pytest.mark.parametrize(
    "line,hit,why",
    [
        ("- `/htmlify --open` renders it", "htmlify", "the reference that shipped broken"),
        ("run `/pitfall-verification` after", "pitfall-verification", "same class"),
        ("see `/e2e-route` for routing", "e2e-route", "hyphenated name matches whole"),
    ],
)
def test_bare_plugin_skill_refs_are_caught(line, hit, why):
    m = lint.bare_skill_ref_re(OWN).search(line)
    assert m and m.group(1) == hit, why


@pytest.mark.parametrize(
    "line,why",
    [
        ("`/superpowers-gstack:htmlify --open`", "namespaced — the correct form"),
        ("read skills/htmlify/SKILL.md", "a path, not a reference"),
        ("invoke `/ship` then `/review`", "gstack skills are correctly bare"),
        ("`/investigate` for bugs", "Superpowers/gstack skill, not ours"),
        ("`/superpowers-gstack:e2e-route`", "namespaced hyphenated name"),
    ],
)
def test_legitimate_forms_are_not_flagged(line, why):
    assert lint.bare_skill_ref_re(OWN).search(line) is None, why


def test_longest_name_wins_over_prefix():
    """`/e2e-route` must not be reported as `/e2e` — alternation is longest-first."""
    m = lint.bare_skill_ref_re(["e2e", "e2e-route"]).search("use `/e2e-route` here")
    assert m and m.group(1) == "e2e-route"
