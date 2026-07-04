#!/usr/bin/env python3
"""Lint the plugin's instruction surface (skills/, CLAUDE.md, README.md).

The 2026-07-03 system review found that 5 700 lines of SKILL.md had zero
validation — which is how a removed third-lens role kept shipping in generator
templates, three releases of work became unreachable by routing, and four
releases went out without CHANGELOG entries. This lint makes that whole drift
class impossible to reintroduce silently.

ERRORS (exit 1, CI-blocking):
  E1  SKILL.md frontmatter parses, `name` matches its directory, `description` present
  E2  cross-references resolve: `superpowers-gstack:<skill>` names and repo
      `scripts/<file>` paths mentioned in instruction files actually exist
  E3  routing coverage: every skill directory is mentioned in CLAUDE.md
  E4  plugin.json version has a matching `## [X.Y.Z]` entry in CHANGELOG.md
  E5  all `gstack-multi-lens-review-vN` markers carry the same N
  E6  no `version:` field in skill frontmatter (plugin.json is the version)
  E7  denylist: patterns that must never reappear in instruction files
      (e.g. the third-lens `sensitive` role removed in 2.18.0)

WARNINGS (reported, exit 0):
  W1  frontmatter description over budget (target <=30 words; hard cap comes
      with the Phase-3 description rewrites)
  W2  SKILL.md body over 500 lines (bloat radar)

Run: python3 scripts/lint-skills.py   (from the repo root or anywhere)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
DESCRIPTION_WARN_WORDS = 60
BODY_WARN_LINES = 500

# Patterns that must never reappear in instruction files (skills/, CLAUDE.md,
# README.md — CHANGELOG is history and may mention them). Add an entry whenever
# a stale-reference class is purged, so it stays purged.
DENYLIST = [
    (re.compile(r"`sensitive`\s*="), "third-lens 'sensitive' role was removed in 2.18.0"),
    (re.compile(r"--role\s+sensitive|--sensitive\b"), "third-lens --sensitive flag was removed in 2.18.0"),
    (re.compile(r"gstack-multi-lens-review-v[0-3]\b"), "stale multi-lens marker (current: v4+)"),
    (re.compile(r"Pi \(local|Pi \(hybrid"), "local-model (Pi) routing columns removed in v0.2 (2.27.0)"),
    (re.compile(r"start-mlx"), "MLX local-server routing removed in v0.2 (2.27.0)"),
    (re.compile(r"models\.json"), "Pi models.json runtime detection removed in v0.2 (2.27.0)"),
]

errors: list[str] = []
warnings: list[str] = []


def frontmatter(text: str) -> dict | None:
    """Minimal YAML-ish frontmatter reader: top-level `key:` lines between --- markers.
    Values are not fully parsed (multi-line descriptions concatenate); enough for linting."""
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    fm: dict[str, str] = {}
    key = None
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if km:
            key = km.group(1)
            fm[key] = km.group(2).strip()
        elif key and (line.startswith("  ") or line.startswith("\t")):
            fm[key] = (fm[key] + " " + line.strip()).strip()
    return fm


def check_refs(path: Path, text: str, repo_doc: bool) -> None:
    """E2: skill-name and repo-script references must resolve.

    Path semantics learned on the lint's first run: a bare `scripts/<x>` inside a
    SKILL.md body is a USER-project path by convention (scaffolds emit
    scripts/run-uitests.sh into the target project; generated CLAUDE.md rows name
    project scripts). Repo assets are referenced via `$SKILL_DIR/../../scripts/<x>`
    — those must resolve. In repo docs (CLAUDE.md, README) bare `scripts/` refs
    mean this repo and are checked too."""
    for name in set(re.findall(r"superpowers-gstack:([a-z0-9-]+)", text)):
        if not (SKILLS / name).is_dir():
            errors.append(f"E2 {path.relative_to(REPO)}: reference to nonexistent skill 'superpowers-gstack:{name}'")
    for line in text.splitlines():
        # skip external-path lines (gstack's own skills/bin live under ~/.claude)
        if ".claude/skills" in line or "gstack/bin" in line:
            continue
        for script in set(re.findall(r"\$SKILL_DIR/\.\./\.\./scripts/([A-Za-z0-9_.-]+)", line)):
            if not (REPO / "scripts" / script).exists():
                errors.append(f"E2 {path.relative_to(REPO)}: repo-asset reference to nonexistent 'scripts/{script}'")
        if repo_doc:
            for script in set(re.findall(r"(?<![\w/.])scripts/([A-Za-z0-9_.-]+)", line)):
                if not (REPO / "scripts" / script).exists():
                    errors.append(f"E2 {path.relative_to(REPO)}: reference to nonexistent script 'scripts/{script}'")


def main() -> int:
    skill_dirs = sorted(d for d in SKILLS.iterdir() if d.is_dir())
    claude_md = (REPO / "CLAUDE.md").read_text()
    readme = (REPO / "README.md").read_text()

    # E1 + E6 + W1 + W2 per skill
    for d in skill_dirs:
        skill_md = d / "SKILL.md"
        if not skill_md.is_file():
            errors.append(f"E1 {d.name}: missing SKILL.md")
            continue
        text = skill_md.read_text()
        fm = frontmatter(text)
        if fm is None:
            errors.append(f"E1 {d.name}: no frontmatter block")
            continue
        if fm.get("name") != d.name:
            errors.append(f"E1 {d.name}: frontmatter name '{fm.get('name')}' != directory name")
        desc = fm.get("description", "")
        if not desc:
            errors.append(f"E1 {d.name}: missing/empty description")
        elif len(desc.split()) > DESCRIPTION_WARN_WORDS:
            warnings.append(f"W1 {d.name}: description is {len(desc.split())} words (target <=30 — per-session tax in every project)")
        if "version" in fm:
            errors.append(f"E6 {d.name}: frontmatter 'version:' field — plugin.json is the only version")
        if text.count("\n") > BODY_WARN_LINES:
            warnings.append(f"W2 {d.name}: SKILL.md body is {text.count(chr(10))} lines (>500 — bloat radar)")
        check_refs(skill_md, text, repo_doc=False)

    # E2 on CLAUDE.md + README too
    check_refs(REPO / "CLAUDE.md", claude_md, repo_doc=True)
    check_refs(REPO / "README.md", readme, repo_doc=True)

    # E3 routing coverage
    for d in skill_dirs:
        if d.name not in claude_md:
            errors.append(f"E3 CLAUDE.md: skill '{d.name}' has no mention — unreachable by routing")

    # E4 version <-> CHANGELOG
    version = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text())["version"]
    if f"## [{version}]" not in (REPO / "CHANGELOG.md").read_text():
        errors.append(f"E4 CHANGELOG.md: no entry for plugin.json version {version} — ship-worthy releases require a CHANGELOG entry")

    # E5 multi-lens marker consistency
    marker_versions = set()
    for d in skill_dirs:
        for m in re.finditer(r"gstack-multi-lens-review-v(\d+)", (d / "SKILL.md").read_text()):
            marker_versions.add(m.group(1))
    if len(marker_versions) > 1:
        errors.append(f"E5 multi-lens markers disagree across skills: v{sorted(marker_versions)}")

    # E7 denylist
    targets = [(REPO / "CLAUDE.md", claude_md), (REPO / "README.md", readme)]
    targets += [(d / "SKILL.md", (d / "SKILL.md").read_text()) for d in skill_dirs if (d / "SKILL.md").is_file()]
    # Also scan the canonical routing table — the file most likely to regress a
    # purged local-model (Pi/MLX) pattern, yet it is not a SKILL.md.
    _mr = REPO / "skills" / "setup-routing" / "model-routing.md"
    if _mr.is_file():
        targets.append((_mr, _mr.read_text()))
    for path, text in targets:
        for pattern, why in DENYLIST:
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    errors.append(f"E7 {path.relative_to(REPO)}:{i}: denylisted pattern ({why})")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\nlint-skills: {len(errors)} error(s), {len(warnings)} warning(s) across {len(skill_dirs)} skills")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
