"""scripts/adapt-claude-md.py — the one writer of a project's CLAUDE.md.

Everything /adapt used to ask a model to do by hand — snapshot, header, the four
cases per marker-managed section, the growth check, attribution sentinels, H3
demotion, `emitted=` provenance, retired-section removal, skill renames, the
Removed / Deferred report — is now this script. These tests run it against
temporary projects with the REAL block files, so a block that changes shape
changes the expectations with it (nothing below hardcodes a block's line count
or marker version).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "adapt-claude-md.py"
BLOCKS = REPO / "skills" / "adapt" / "blocks"
FIXTURE = REPO / "tests" / "fixtures" / "adapt-growth" / "CLAUDE.md"

REMOVED = "**Removed (not plugin prose):**"
NOTHING = "Nothing project-authored was removed."
DEFERRED = "**Deferred (grown past its block, not upgraded):**"

NATIVE_SETS = ["--set", "IOS_SIMULATOR=iPhone 17", "--set", "DEVELOPMENT_TEAM=ABCDE12345",
               "--set", "DOMAIN_SENSITIVITY=medium"]
WEB_SETS = ["--set", "DOMAIN_SENSITIVITY=low"]


def block(name: str) -> str:
    return (BLOCKS / name).read_text()


def marker(name: str) -> str:
    """`gstack-x-vN` from the block's first line."""
    return re.search(r"<!-- (gstack-[a-z-]+-v\d+) -->", block(name).split("\n", 1)[0]).group(1)


def emitted(name: str) -> int:
    return block(name).count("\n")


def module():
    spec = importlib.util.spec_from_file_location("adapt_claude_md", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m   # dataclasses resolve string annotations through sys.modules
    spec.loader.exec_module(m)
    return m


def project(tmp_path, claude_md: str | None = None, track: str | None = None) -> Path:
    p = tmp_path / "proj"
    p.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=p, check=True)
    if claude_md is not None:
        (p / "CLAUDE.md").write_text(claude_md)
    if track:
        (p / ".gstack").mkdir(exist_ok=True)
        (p / ".gstack" / "track").write_text(track + "\n")
    return p


def run(proj: Path, *args, expect=0):
    p = subprocess.run([sys.executable, str(SCRIPT), "--project-dir", str(proj),
                        "--plugin-version", "9.9.9", *args],
                       capture_output=True, text=True)
    assert p.returncode == expect, (
        f"exit {p.returncode} (wanted {expect})\nstdout: {p.stdout}\nstderr: {p.stderr}")
    assert "Traceback" not in p.stderr, f"a traceback is never a verdict:\n{p.stderr}"
    return p


def last_json(p) -> dict:
    return json.loads(p.stdout.strip().splitlines()[-1])


def headings(text: str) -> list[str]:
    return [l for l in text.splitlines() if re.match(r"^#{1,6} ", l)]


# --- a project with no CLAUDE.md: adapt IS setup -------------------------------

def test_fresh_project_gets_the_header_and_every_universal_block(tmp_path):
    proj = project(tmp_path)
    p = run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    lines = text.splitlines()
    assert lines[0] == "<!-- superpowers-gstack: 9.9.9 -->"
    assert lines[1].startswith("<!-- Sections whose heading carries a gstack-<name>-vN marker are plugin-managed")
    assert "<!--" not in lines[1][4:], "the header must not nest a comment opener"
    for name in ("git-hygiene.md", "multi-lens-review.md", "code-reuse.md",
                 "plan-fidelity.md", "session-continuity.md", "track-routing.md"):
        head = block(name).split("\n", 1)[0]
        assert f"{head}<!-- emitted={emitted(name)} -->\n" in text, name
        assert block(name).split("\n", 1)[1].rstrip("\n") in text, f"{name} body not verbatim"
    assert "gstack-xcode-tools" not in text and "gstack-companion-skills" not in text, \
        "native-only blocks must not reach a web project"
    assert "## Model Routing" in text and "domain sensitivity: low" in text
    assert "{{" not in text
    assert NOTHING in p.stdout and REMOVED in p.stdout
    assert "no prior CLAUDE.md" in p.stdout
    assert not (proj / ".gstack" / "CLAUDE.md.pre-adapt").exists()


def test_a_second_run_changes_nothing(tmp_path):
    proj = project(tmp_path)
    run(proj, *WEB_SETS)
    once = (proj / "CLAUDE.md").read_bytes()
    p = run(proj, *WEB_SETS)
    assert (proj / "CLAUDE.md").read_bytes() == once
    assert last_json(p)["changes"] == [], p.stdout


def test_native_track_emits_the_native_blocks_with_placeholders_resolved(tmp_path):
    proj = project(tmp_path, track="ios")
    run(proj, *NATIVE_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert marker("xcode-tools.md") in text and marker("companion-skills.md") in text
    assert "{{" not in text
    assert "name=iPhone 17'" in text and "ABCDE12345" in text
    assert "run on: **host**" in text, "no pin file means host, by definition"


def test_an_unresolved_placeholder_refuses_and_writes_nothing(tmp_path):
    proj = project(tmp_path, claude_md="# P\n\nkeep me\n", track="ios")
    p = run(proj, "--set", "DOMAIN_SENSITIVITY=medium", expect=2)
    assert "IOS_SIMULATOR" in p.stderr and "DEVELOPMENT_TEAM" in p.stderr
    assert (proj / "CLAUDE.md").read_text() == "# P\n\nkeep me\n"
    assert not (proj / ".gstack" / "CLAUDE.md.pre-adapt").exists()


def test_e2e_executor_pin_is_read_validated_and_never_normalised(tmp_path):
    proj = project(tmp_path, track="macos")
    (proj / ".gstack" / "e2e-executor").write_text("vm\n")
    run(proj, *NATIVE_SETS)
    assert "run on: **vm**" in (proj / "CLAUDE.md").read_text()
    (proj / ".gstack" / "e2e-executor").write_text("vm \n")
    p = run(proj, *NATIVE_SETS, expect=2)
    assert "BLOCKED" in p.stderr and "e2e-executor" in p.stderr


def test_an_invalid_track_is_blocked(tmp_path):
    proj = project(tmp_path, track="tvos")
    p = run(proj, *NATIVE_SETS, expect=2)
    assert "BLOCKED" in p.stderr and "track" in p.stderr
    assert not (proj / "CLAUDE.md").exists()


def test_dry_run_writes_nothing_and_still_reports(tmp_path):
    proj = project(tmp_path, claude_md="# P\n\nkeep me\n")
    p = run(proj, "--dry-run", *WEB_SETS)
    assert (proj / "CLAUDE.md").read_text() == "# P\n\nkeep me\n"
    assert not (proj / ".gstack").exists()
    j = last_json(p)
    assert j["applied"] is False and j["changes"], p.stdout
    assert marker("git-hygiene.md") in p.stdout or "Git hygiene" in p.stdout


def test_the_old_one_line_header_is_replaced_not_stacked(tmp_path):
    proj = project(tmp_path, claude_md="<!-- superpowers-gstack: 2.47.0 -->\n# P\n\nkeep me\n")
    run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert text.count("superpowers-gstack: ") == 1
    assert text.startswith("<!-- superpowers-gstack: 9.9.9 -->\n<!-- Sections whose heading")
    assert "\n# P\n\nkeep me\n" in text


# --- the growth gate, on the fixture that motivated it --------------------------

def test_the_growth_fixture_keeps_every_sentinel_and_defers_the_grown_sections(tmp_path):
    proj = project(tmp_path, claude_md=FIXTURE.read_text(), track="ios")
    p = run(proj, *NATIVE_SETS)
    text = (proj / "CLAUDE.md").read_text()
    for n in range(1, 6):
        assert f"SENTINEL-LINE-00{n}" in text and f"PROV-SENTINEL-00{n}" in text
    assert "gstack-xcode-tools-v3" in text and marker("xcode-tools.md") not in text, \
        "the 2.7x section stays at its old marker"
    assert "gstack-git-hygiene-v8" in text and marker("git-hygiene.md") not in text
    assert len([h for h in headings(text) if "Git hygiene" in h]) == 1, "deferred, not duplicated"
    sc = [h for h in headings(text) if "Session Continuity" in h]
    assert sc == [f"### Session Continuity <!-- {marker('session-continuity.md')} --><!-- emitted={emitted('session-continuity.md')} -->"], sc
    assert "## Project conventions" in text and "## Skill routing" in text
    assert DEFERRED in p.stdout
    deferred = p.stdout[p.stdout.index(DEFERRED):]
    assert "Native Apple development tools" in deferred and "Git hygiene" in deferred
    j = last_json(p)
    assert {d["marker"] for d in j["deferred"]} == {"gstack-xcode-tools", "gstack-git-hygiene"}
    at_risk = next(d for d in j["deferred"] if d["marker"] == "gstack-xcode-tools")["at_risk"]
    assert any("SENTINEL-LINE-001" in l for l in at_risk)
    # the v1 Session Continuity body was old plugin prose the v4 block no longer
    # carries; the verify step cannot tell that from project text, so it is listed
    assert REMOVED in p.stdout and "Session Continuity" in p.stdout[p.stdout.index(REMOVED):p.stdout.index(DEFERRED)]


def _section_from_block(name: str, extra_lines: int, emitted_value: int | None,
                        marker_version: str = "v1") -> str:
    """A section built from the block's own lines: under 1.5x, and volume-neutral
    (every line already in the block), so only provenance can see the growth."""
    raw = block(name)
    head, _, body = raw.rstrip("\n").partition("\n")
    head = re.sub(r"-v\d+ -->", f"-{marker_version} -->", head)
    if emitted_value is not None:
        head += f"<!-- emitted={emitted_value} -->"
    body_lines = [l for l in body.splitlines() if l.strip() and not l.startswith("#")]
    padding = (body_lines * 3)[:extra_lines]
    return head + "\n" + body + "\n" + "\n".join(padding) + "\n"


def test_provenance_alone_defers_a_volume_neutral_section(tmp_path):
    """The deferred fixture from 2.49.0: >20 over emitted=, ~0 lines absent from
    the block, ratio under 1.5x. Neither proxy fires; provenance must."""
    name = "git-hygiene.md"
    n = emitted(name)
    grown = _section_from_block(name, extra_lines=30, emitted_value=n)
    proj = project(tmp_path, claude_md="# P\n\n" + grown)
    p = run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert "gstack-git-hygiene-v1 -->" in text and marker(name) not in text
    assert "Git hygiene" in p.stdout[p.stdout.index(DEFERRED):]
    # the same section with no provenance: no trigger fires, and it upgrades
    proj2 = project(tmp_path / "b", claude_md="# P\n\n" + _section_from_block(name, 30, None))
    run(proj2, *WEB_SETS)
    assert marker(name) in (proj2 / "CLAUDE.md").read_text()


def test_an_implausible_emitted_count_is_ignored(tmp_path):
    name = "git-hygiene.md"
    n = emitted(name)
    for bad in (n + 200, 1):   # far above the block; at or below the section's size is impossible too
        grown = _section_from_block(name, extra_lines=30, emitted_value=bad)
        proj = project(tmp_path / str(bad), claude_md="# P\n\n" + grown)
        run(proj, *WEB_SETS)
        text = (proj / "CLAUDE.md").read_text()
        if bad == 1:
            # emitted=1 on a 130-line section: "section at or below N" is false, so the
            # count is NOT implausible by that rule; N well below the block is ordinary.
            # Provenance fires (130 - 1 > 20) and the section is deferred.
            assert marker(name) not in text
        else:
            assert marker(name) in text, "a count 200 above the block silences nothing"


def test_rescue_moves_the_at_risk_lines_into_an_unmarked_section_then_upgrades(tmp_path):
    proj = project(tmp_path, claude_md=FIXTURE.read_text(), track="ios")
    p = run(proj, "--rescue", "gstack-xcode-tools", *NATIVE_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert f"{marker('xcode-tools.md')} --><!-- emitted={emitted('xcode-tools.md')} -->" in text
    assert "gstack-xcode-tools-v3" not in text
    rescued = [h for h in headings(text) if h.startswith("## Fixture Project") and "rescued" in h]
    assert len(rescued) == 1, headings(text)
    after = text[text.index(rescued[0]):]
    for n in range(1, 6):
        assert f"SENTINEL-LINE-00{n}" in after
    assert "### Provisioning and signing, the hard way" in after, "the section's own headings travel with their lines"
    body = after.split("\n## ", 1)[0]
    assert "MUST be performed by the agent" not in body, "block prose does not travel"
    removed = p.stdout[p.stdout.index(REMOVED):p.stdout.index(DEFERRED)] if DEFERRED in p.stdout else p.stdout[p.stdout.index(REMOVED):]
    assert "moved to" in removed and "Native Apple development tools" in removed
    # git-hygiene was not rescued, so it is still deferred
    assert "gstack-git-hygiene-v8" in text


# --- attribution ----------------------------------------------------------------

USER_GIT = ("## Git hygiene & commit cadence\n\n"
            "Rebase onto main before opening a PR. Squash-merge only.\n"
            "Tag releases as app-vX.Y.Z.\n")


def test_a_markerless_section_without_a_sentinel_is_preserved_and_the_block_inserted_below(tmp_path):
    proj = project(tmp_path, claude_md="# P\n\n" + USER_GIT + "\n## Other\n\nx\n")
    p = run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert USER_GIT in text, "byte-for-byte"
    hs = headings(text)
    i = hs.index("## Git hygiene & commit cadence")
    assert hs[i + 1].startswith("## Git hygiene & commit cadence <!-- gstack-git-hygiene-v"), hs
    assert "cannot attribute this section to a past emitter" in p.stdout
    assert "delete your copy and re-run" in p.stdout
    assert any(u["heading"].startswith("Git hygiene") for u in last_json(p)["unattributed"])


def test_a_markerless_section_with_a_sentinel_is_replaced(tmp_path):
    legacy = "## Git hygiene & commit cadence\n\n### Hygiene rules (NEVER violate)\n\n- no --no-verify\n"
    proj = project(tmp_path, claude_md="# P\n\n" + legacy)
    run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert len([h for h in headings(text) if "Git hygiene" in h]) == 1
    assert marker("git-hygiene.md") in text
    assert "no --no-verify" not in text


def test_a_markerless_code_reuse_section_is_preserved_and_nothing_inserted(tmp_path):
    user = "## Code reuse discipline (before writing)\n\nOur own rule: grep first.\n"
    proj = project(tmp_path, claude_md="# P\n\n" + user)
    p = run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert user in text
    assert "gstack-code-reuse" not in text
    assert "preserved as-is" in p.stdout and "Code reuse discipline" in p.stdout


def test_session_continuity_attribution_keys_on_the_handoff_path(tmp_path):
    emitted_old = "## Session Continuity\n\nRead `docs/superpowers/handoff.md` on start and clear it.\n"
    proj = project(tmp_path, claude_md="# P\n\n" + emitted_old)
    run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert len([h for h in headings(text) if "Session Continuity" in h]) == 1
    assert marker("session-continuity.md") in text
    users = "## Session Continuity\n\nWe hand over in Slack, not in files.\n"
    proj2 = project(tmp_path / "b", claude_md="# P\n\n" + users)
    p = run(proj2, *WEB_SETS)
    text = (proj2 / "CLAUDE.md").read_text()
    assert users in text
    assert len([h for h in headings(text) if "Session Continuity" in h]) == 2
    assert "cannot attribute" in p.stdout


# --- retired content ------------------------------------------------------------

def _autonomy(lines: int, mark: str | None, sentinel: bool = True) -> str:
    head = "## Autonomy and user interruption" + (f" <!-- {mark} -->" if mark else "")
    body = ["You are operating autonomously."]
    if sentinel:
        body.append("### Forbidden phrases")
    body += [f"filler {i}" for i in range(lines - 1 - len(body))]
    return head + "\n" + "\n".join(body) + "\n"


@pytest.mark.parametrize("lines,mark,sentinel,removed", [
    (31, "gstack-autonomy-v2", True, True),     # exactly the v2 block
    (34, "gstack-autonomy-v2", True, True),     # +3 tolerance
    (35, "gstack-autonomy-v2", True, False),    # grown: deferred, never destroyed
    (56, "gstack-autonomy-v1", True, True),
    (40, None, True, True),                     # markerless with sentinel: a pre-2.8.0 emit, v1 bound
    (40, None, False, False),                   # markerless without: the user's, never touched
])
def test_the_retired_autonomy_section(tmp_path, lines, mark, sentinel, removed):
    sec = _autonomy(lines, mark, sentinel)
    proj = project(tmp_path, claude_md="# P\n\n" + sec + "\n## Keep\n\nme\n")
    p = run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert ("## Autonomy and user interruption" in text) is (not removed), p.stdout
    assert "## Keep\n\nme\n" in text
    if removed:
        assert "removed the retired `Autonomy and user interruption` section" in p.stdout
    elif mark:
        assert "Autonomy" in p.stdout[p.stdout.index(DEFERRED):]


def test_an_emitted_count_bounds_the_autonomy_removal(tmp_path):
    sec = _autonomy(40, "gstack-autonomy-v2 --><!-- emitted=38")   # 40 <= 38 + 3
    proj = project(tmp_path, claude_md="# P\n\n" + sec)
    run(proj, *WEB_SETS)
    assert "Autonomy" not in (proj / "CLAUDE.md").read_text()


def test_retired_skill_names_are_renamed_and_collapsed(tmp_path):
    routing = (
        "# P\n\n## Skill routing\n\n"
        "| Skill | When |\n|---|---|\n"
        "| `/superpowers-gstack:macos-native-review` | macOS specs |\n"
        "| `/superpowers-gstack:ios-native-review` | iOS specs |\n"
        "| `/superpowers-gstack:ios-visual-explore` | look around |\n"
        "| `/superpowers-gstack:autoimplement` | plans |\n\n"
        "Bug in a Swift spec → /ios-native-review\n\n"
        "```\nexample: /macos-native-review stays as typed inside a fence\n```\n"
    )
    proj = project(tmp_path, claude_md=routing)
    p = run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert text.count("| `/superpowers-gstack:apple-native-review` |") == 1
    assert "ios-native-review" not in text.replace("stays as typed", "")  # only the fenced copy survives
    assert "ios-visual-explore" not in text
    assert "→ /apple-native-review" in text
    assert "/macos-native-review stays as typed inside a fence" in text
    assert "| `/superpowers-gstack:autoimplement` |" in text
    assert "renamed" in p.stdout


# --- structure ------------------------------------------------------------------

def test_headings_inside_code_fences_are_not_section_boundaries(tmp_path):
    user = ("## Our scripts\n\n```bash\n# not a heading\n## also not\n"
            "echo hi\n```\n\nstill ours\n")
    legacy = "## Git hygiene & commit cadence <!-- gstack-git-hygiene-v1 -->\n\nold prose\n"
    proj = project(tmp_path, claude_md="# P\n\n" + user + "\n" + legacy)
    run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert user in text
    assert "old prose" not in text and marker("git-hygiene.md") in text


def test_an_h3_root_is_replaced_at_h3_with_demoted_subsections_and_provenance(tmp_path):
    proj = project(tmp_path, claude_md=(
        "# P\n\n## Skill routing\n\nrows\n\n"
        "### Git hygiene & commit cadence <!-- gstack-git-hygiene-v1 -->\n\nold\n\n"
        "### Routing Logic\n\ntree\n"))
    run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    head = f"### Git hygiene & commit cadence <!-- {marker('git-hygiene.md')} --><!-- emitted={emitted('git-hygiene.md')} -->"
    assert head in text
    sec = text[text.index(head):text.index("### Routing Logic")]
    assert "\n#### When to commit" in sec and "\n### When to commit" not in sec
    assert "\n## " not in sec, "an H2 inside the replaced H3 would reparent every sibling below it"
    assert "### Routing Logic\n\ntree\n" in text


def test_a_stale_model_routing_block_is_replaced_and_a_users_own_is_kept(tmp_path):
    stale = ("## Skill routing\n\nrows\n\n### Model Routing\n\n"
             "| Skill | Claude | Pi/MLX |\n|---|---|---|\n| /review | sonnet | qwen |\n")
    proj = project(tmp_path, claude_md="# P\n\n" + stale + "\n## Tail\n\nt\n")
    run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert "Pi/MLX" not in text
    assert [h for h in headings(text) if "Model Routing" in h] == ["## Model Routing"]
    assert text.index("## Model Routing") < text.index("## Tail")
    assert "domain sensitivity: low" in text
    own = "## Model Routing\n\nWe route everything to the cheapest model. Deal with it.\n"
    proj2 = project(tmp_path / "b", claude_md="# P\n\n" + own)
    p = run(proj2, *WEB_SETS)
    text = (proj2 / "CLAUDE.md").read_text()
    assert own in text and "domain sensitivity" not in text
    assert "Model Routing" in p.stdout and "rename" in p.stdout


def test_model_routing_lands_after_the_skill_routing_subtree(tmp_path):
    proj = project(tmp_path, claude_md=(
        "# P\n\n## Skill routing\n\n### Rules\n\nr\n\n### Session Management\n\ns\n\n## Project\n\np\n"))
    run(proj, *WEB_SETS)
    hs = headings((proj / "CLAUDE.md").read_text())
    assert hs.index("## Model Routing") == hs.index("### Session Management") + 1
    assert hs.index("## Model Routing") < hs.index("## Project")


def test_routing_file_is_inserted_only_when_skill_routing_is_absent(tmp_path):
    routing = tmp_path / "routing.md"
    routing.write_text("## Skill routing\n\nGenerated rows.\n")
    proj = project(tmp_path, claude_md="# P\n\nintro paragraph\n\n## Conventions\n\nc\n")
    run(proj, "--routing-file", str(routing), *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    hs = headings(text)
    assert hs[:4] == ["# P", "## Skill routing", "## Model Routing", "## Conventions"], hs
    assert "intro paragraph" in text[:text.index("## Skill routing")]
    routing.write_text("## Skill routing\n\nDIFFERENT rows.\n")
    run(proj, "--routing-file", str(routing), *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert "Generated rows." in text and "DIFFERENT rows." not in text, "an existing Skill routing is never rewritten"


def test_the_snapshot_is_rotated_never_overwritten_and_excluded_from_git(tmp_path):
    proj = project(tmp_path, claude_md="# P\n\nv1\n")
    run(proj, *WEB_SETS)
    snap = proj / ".gstack" / "CLAUDE.md.pre-adapt"
    assert snap.read_text() == "# P\n\nv1\n"
    (proj / "CLAUDE.md").write_text((proj / "CLAUDE.md").read_text() + "\n## Mine\n\nnew\n")
    p = run(proj, *WEB_SETS)
    assert not list((proj / ".gstack").glob("CLAUDE.md.pre-adapt.*")), "nothing changed: no write, no snapshot"
    p = run(proj, "--plugin-version", "9.9.10", *WEB_SETS)   # the header changes, so the file is rewritten
    rotated = list((proj / ".gstack").glob("CLAUDE.md.pre-adapt.*"))
    assert len(rotated) == 1 and rotated[0].read_text() == "# P\n\nv1\n"
    assert "## Mine" in snap.read_text()
    assert ".gstack/CLAUDE.md.pre-adapt*" in (proj / ".git" / "info" / "exclude").read_text()
    assert "Snapshot:" in p.stdout and "cp .gstack/CLAUDE.md.pre-adapt CLAUDE.md" in p.stdout
    assert rotated[0].name in p.stdout, "a rotated-aside snapshot is named in the report"


def test_mkdirs_creates_the_docs_structure(tmp_path):
    proj = project(tmp_path)
    run(proj, "--mkdirs", *WEB_SETS)
    for d in ("specs", "plans"):
        assert (proj / "docs" / "superpowers" / d / ".gitkeep").is_file()


def test_the_report_ends_with_one_json_line_the_skill_can_read(tmp_path):
    proj = project(tmp_path, claude_md=FIXTURE.read_text(), track="ios")
    p = run(proj, "--dry-run", *NATIVE_SETS)
    j = last_json(p)
    for key in ("applied", "changes", "preserved", "removed", "deferred", "unattributed", "snapshot"):
        assert key in j, key
    assert j["applied"] is False
    d = {x["marker"]: x for x in j["deferred"]}
    assert d["gstack-xcode-tools"]["heading"].startswith("Native Apple development tools")
    assert d["gstack-xcode-tools"]["lines"] > d["gstack-xcode-tools"]["block_lines"]
    assert d["gstack-git-hygiene"]["emitted"] == 162


def test_the_blocks_roster_is_exactly_the_marker_blocks_on_disk():
    m = module()
    on_disk = {f.name for f in BLOCKS.glob("*.md")} - {"PLACEHOLDERS.md", "model-routing-section.md"}
    assert {b.file for b in m.BLOCKS} == on_disk
    for b in m.BLOCKS:
        assert re.match(r"^## .*<!-- " + re.escape(b.marker) + r"-v\d+ -->$", block(b.file).split("\n", 1)[0]), b.file
    assert m.REMOVED_LABEL == REMOVED and m.NOTHING_REMOVED == NOTHING and m.DEFERRED_LABEL == DEFERRED


def test_a_project_name_prefixes_the_rescue_heading_and_defaults_to_the_h1(tmp_path):
    m = module()
    assert m.project_name("<!-- x -->\n# My App\n\ntext\n", Path("/tmp/dir-name")) == "My App"
    assert m.project_name("no heading at all\n", Path("/tmp/dir-name")) == "dir-name"
