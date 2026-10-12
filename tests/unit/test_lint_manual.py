"""scripts/lint-skills.py E15: the manual cannot drift from the skills it describes.

E15a every skill reference in docs/manual/*.md exists (own namespace and superpowers: via
the existing E2 and E10 checks; bare /name via docs/manual/kommandoer.txt or an own skill)
E15b every plugin skill is referenced as a command in some chapter
E15c docs/manual/manual.html is what the builder gives now
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lint = load("lint_skills_e15", "scripts/lint-skills.py")
bm = load("build_manual_for_lint", "scripts/build-manual.py")


def chapter(body: str) -> str:
    return ("---\nnummer: 0\ntag: Kartet\ntittel: Kartet\naksent: cyan\n"
            "bruk: Bruk denne når du vil se alt.\nferdig: Du er ferdig når du har sett det.\n"
            f"oppdatert: 2026-10-12\n---\n{body}\n")


def write(manual: pathlib.Path, body: str) -> None:
    (manual / "00-kartet.md").write_text(chapter(body))
    (manual / "manual.html").write_text(bm.build(manual))


GOOD = "Kjør `/superpowers-gstack:adapt`, så `/superpowers-gstack:land`. Bruk `/qa` og `/clear`."


@pytest.fixture
def manual(tmp_path, monkeypatch):
    skills = tmp_path / "skills"
    for name in ("adapt", "land"):
        (skills / name).mkdir(parents=True)
        (skills / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n")
    d = tmp_path / "docs" / "manual"
    (d / "figurer").mkdir(parents=True)
    (d / "manual.css").write_text(".x{color:var(--fg)}\n")
    (d / "kommandoer.txt").write_text("# test\ngstack: qa\nclaude-code: clear\n")
    monkeypatch.setattr(lint, "REPO", tmp_path)
    monkeypatch.setattr(lint, "SKILLS", skills)
    write(d, GOOD)
    return d


def test_a_clean_manual_has_no_findings(manual):
    assert lint.check_manual(manual) == []


def test_no_chapters_means_nothing_to_check(tmp_path, monkeypatch):
    monkeypatch.setattr(lint, "REPO", tmp_path)
    (tmp_path / "docs" / "manual").mkdir(parents=True)
    assert lint.check_manual(tmp_path / "docs" / "manual") == []


def test_e15a_an_own_skill_that_does_not_exist(manual):
    write(manual, GOOD + " Prøv `/superpowers-gstack:nope`.")
    found = lint.check_manual(manual)
    assert len(found) == 1 and found[0].startswith("E15a") and "nope" in found[0]


def test_e15a_an_upstream_skill_that_does_not_exist(manual):
    write(manual, GOOD + " Prøv `superpowers:made-up`.")
    found = lint.check_manual(manual)
    assert len(found) == 1 and found[0].startswith("E15a") and "made-up" in found[0]


def test_e15a_a_bare_command_must_be_listed_or_own(manual):
    write(manual, GOOD + " Prøv `/zzz` og `/adapt`.")
    found = lint.check_manual(manual)
    assert len(found) == 1 and "/zzz" in found[0]


def test_e15a_paths_and_namespaced_names_are_not_mistaken_for_commands(manual):
    write(manual, GOOD + " Se `/tmp/x` og `/Users/me/prosjekt` og `/superpowers-gstack:land`.")
    assert lint.check_manual(manual) == []


def test_e15a_a_command_at_the_start_of_a_code_fence_line_is_checked(manual):
    write(manual, GOOD + "\n\n```\n/zzz --hjelp\n```")
    found = lint.check_manual(manual)
    assert len(found) == 1 and "/zzz" in found[0]


def test_e15b_a_skill_no_chapter_mentions(manual):
    (lint.SKILLS / "vibe").mkdir()
    (lint.SKILLS / "vibe" / "SKILL.md").write_text("---\nname: vibe\ndescription: x\n---\n")
    found = lint.check_manual(manual)
    assert len(found) == 1 and found[0].startswith("E15b") and "vibe" in found[0]


def test_e15b_the_word_alone_is_not_a_mention(manual):
    (lint.SKILLS / "vibe").mkdir()
    (lint.SKILLS / "vibe" / "SKILL.md").write_text("---\nname: vibe\ndescription: x\n---\n")
    write(manual, GOOD + " Det er en god vibe i dag.")
    assert any(f.startswith("E15b") for f in lint.check_manual(manual))


def test_e15c_a_page_older_than_its_chapters(manual):
    (manual / "00-kartet.md").write_text(chapter(GOOD + " Mer tekst."))
    found = lint.check_manual(manual)
    assert len(found) == 1 and found[0].startswith("E15c") and "build-manual.py" in found[0]


def test_e15c_a_missing_page(manual):
    (manual / "manual.html").unlink()
    found = lint.check_manual(manual)
    assert len(found) == 1 and found[0].startswith("E15c")


def test_e15c_a_source_the_builder_refuses(manual):
    (manual / "00-kartet.md").write_text(chapter(GOOD).replace("aksent: cyan", "aksent: rosa"))
    found = lint.check_manual(manual)
    assert len(found) == 1 and found[0].startswith("E15c") and "build failed" in found[0]


def test_the_check_leaves_the_global_error_list_alone(manual):
    before = list(lint.errors)
    write(manual, GOOD + " Prøv `/superpowers-gstack:nope`.")
    lint.check_manual(manual)
    assert lint.errors == before


# ── the command list ─────────────────────────────────────────────────────────

def test_manual_commands_reads_labelled_lines_and_skips_comments(tmp_path):
    p = tmp_path / "k.txt"
    p.write_text("# kommentar\n\ngstack: qa ship\nclaude-code: clear compact\n")
    assert lint.manual_commands(p) == {"gstack": {"qa", "ship"}, "claude-code": {"clear", "compact"}}
    assert lint.manual_commands(tmp_path / "missing.txt") == {}


def test_w5_names_a_listed_gstack_command_the_installed_gstack_lacks(tmp_path):
    p = tmp_path / "k.txt"
    p.write_text("gstack: qa nope\nclaude-code: clear\n")
    home = tmp_path / "skills"
    (home / "qa").mkdir(parents=True)
    (home / "qa" / "SKILL.md").write_text("x")
    assert lint.manual_gstack_missing(p, home) == ["nope"]


# ── the author's shortcut ────────────────────────────────────────────────────

def test_manual_report_prints_findings_and_returns_the_exit_code(manual, capsys):
    assert lint.manual_report(manual) == 0
    write(manual, GOOD + " Prøv `/zzz`.")
    assert lint.manual_report(manual) == 1
    assert "E15a" in capsys.readouterr().out


def test_the_real_manual_passes_e15():
    """The shipped manual: every reference resolves, every skill is mentioned, the page is current."""
    assert lint.check_manual() == []
