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
  E8  emitted blocks are single-sourced: every shared block file in
      skills/setup-routing/blocks/ exists, carries its version marker on the
      H2 heading line, and is referenced by BOTH generators (setup-routing,
      adapt); neither generator carries an inline copy (no marker heading in
      a SKILL.md). Replaced the old byte-identity drift guard in 2.33.0 —
      one source can't drift from itself.

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
DESCRIPTION_WARN_WORDS = 30
BODY_WARN_LINES = 500

# Patterns that must never reappear in instruction files (skills/, CLAUDE.md,
# README.md — CHANGELOG is history and may mention them). Add an entry whenever
# a stale-reference class is purged, so it stays purged.
DENYLIST = [
    (re.compile(r"`sensitive`\s*="), "third-lens 'sensitive' role was removed in 2.18.0"),
    (re.compile(r"--role\s+sensitive|--sensitive\b"), "third-lens --sensitive flag was removed in 2.18.0"),
    (re.compile(r"gstack-multi-lens-review-v[0-4]\b"), "stale multi-lens marker (current: v5+)"),
    (re.compile(r"Pi \(local|Pi \(hybrid"), "local-model (Pi) routing columns removed in v0.2 (2.27.0)"),
    (re.compile(r"start-mlx"), "MLX local-server routing removed in v0.2 (2.27.0)"),
    (re.compile(r"models\.json"), "Pi models.json runtime detection removed in v0.2 (2.27.0)"),
    (re.compile(r"WXNUGGYB2B"), "hardcoded Apple Team ID removed in 2.33.0 — use the {{DEVELOPMENT_TEAM}} placeholder"),
    # Usage form only (with a subcommand) — prose explaining that no such slash
    # command exists ("there is no `/cost-ledger` slash command") must pass.
    (re.compile(r"(?<![\w.~])/cost-ledger\s+(pause|status|reset|explain|gate|record|tune)"),
     "no /cost-ledger slash command exists — use python3 scripts/cost-ledger/cli.py <subcommand> (2.34.1)"),
]

# Shared emitted blocks (skills/setup-routing/blocks/): single source for the
# sections both generators write into a project's CLAUDE.md. Marker-carrying
# blocks must have their `<!-- gstack-<name>-vN -->` marker on the H2 heading.
BLOCKS_DIR_REL = Path("skills") / "setup-routing" / "blocks"
MARKER_BLOCKS = [
    "autonomy.md",
    "git-hygiene.md",
    "multi-lens-review.md",
    "code-reuse.md",
    "track-routing.md",
    "xcode-tools.md",
    "companion-skills.md",
]
PLAIN_BLOCKS = ["model-routing-section.md", "PLACEHOLDERS.md"]

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
            val = km.group(2).strip()
            # A bare block-scalar indicator (|, >, with optional chomping) is not
            # content — the value is on the following indented lines. Counting the
            # `|` as a word would over-count every block-scalar description by one.
            fm[key] = "" if val in ("|", ">", "|-", "|+", ">-", ">+") else val
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

    # E5 multi-lens marker consistency (SKILL.md files + shared block files)
    marker_versions = set()
    marker_files = [d / "SKILL.md" for d in skill_dirs]
    marker_files += sorted((REPO / BLOCKS_DIR_REL).glob("*.md")) if (REPO / BLOCKS_DIR_REL).is_dir() else []
    for f in marker_files:
        for m in re.finditer(r"gstack-multi-lens-review-v(\d+)", f.read_text()):
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
    # ... and the shared emitted blocks — they ARE the generated-CLAUDE.md content.
    if (REPO / BLOCKS_DIR_REL).is_dir():
        targets += [(f, f.read_text()) for f in sorted((REPO / BLOCKS_DIR_REL).glob("*.md"))]
    # ... and the scripts themselves — user-facing messages/docstrings drift the
    # same way instruction files do (the 2.34.1 audit found `/cost-ledger pause`
    # in cli.py output after the .md sweep missed it). lint-skills.py itself is
    # exempt: it carries the patterns by definition.
    targets += [(f, f.read_text()) for pat in ("*.py", "*.sh")
                for f in sorted((REPO / "scripts").rglob(pat))
                if f.name != "lint-skills.py" and "__pycache__" not in f.parts]
    for path, text in targets:
        for pattern, why in DENYLIST:
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    errors.append(f"E7 {path.relative_to(REPO)}:{i}: denylisted pattern ({why})")

    # E8 single-source guard for emitted blocks (2.33.0, replaces the old
    # byte-identity drift check — one source can't drift from itself):
    #   (a) every shared block file exists;
    #   (b) marker blocks carry `<!-- gstack-<x>-vN -->` on their H2 heading line;
    #   (c) BOTH generators reference every block filename (no orphaned block,
    #       no generator that forgot to emit one);
    #   (d) NEITHER generator has an inline copy — a heading line carrying a
    #       gstack marker inside a SKILL.md is a regression to hand-maintained
    #       duplication (the class the 2.27.0 pre-merge review caught).
    blocks_dir = REPO / BLOCKS_DIR_REL
    gen_texts = {name: (SKILLS / name / "SKILL.md").read_text()
                 for name in ("setup-routing", "adapt")
                 if (SKILLS / name / "SKILL.md").is_file()}
    for fname in MARKER_BLOCKS + PLAIN_BLOCKS:
        f = blocks_dir / fname
        if not f.is_file():
            errors.append(f"E8 missing shared block file {BLOCKS_DIR_REL}/{fname}")
            continue
        if fname in MARKER_BLOCKS:
            first = f.read_text().split("\n", 1)[0]
            if not re.match(r"^## .*<!-- gstack-[a-z-]+-v\d+ -->$", first):
                errors.append(f"E8 {BLOCKS_DIR_REL}/{fname}: first line must be an H2 heading with a gstack version marker")
        # PLACEHOLDERS.md included: a generator that stops referencing it could
        # emit raw {{...}} tokens into a project's CLAUDE.md.
        for gen, text in gen_texts.items():
            if fname not in text:
                errors.append(f"E8 {gen}/SKILL.md never references blocks/{fname} — generator would not emit/resolve it")
    if (blocks_dir / "model-routing-section.md").is_file():
        if "## Model Routing" not in (blocks_dir / "model-routing-section.md").read_text():
            errors.append("E8 blocks/model-routing-section.md lost its `## Model Routing` anchor")
    # Orphan guard: a blocks/*.md not in the known lists has no emitter — it
    # would silently never reach any generated CLAUDE.md.
    if blocks_dir.is_dir():
        for f in sorted(blocks_dir.glob("*.md")):
            if f.name not in MARKER_BLOCKS + PLAIN_BLOCKS:
                errors.append(f"E8 orphaned block file {BLOCKS_DIR_REL}/{f.name} — not in MARKER_BLOCKS/PLAIN_BLOCKS, no generator emits it")
    # Inline copies are forbidden WITH or WITHOUT the marker — a markerless
    # re-paste of a block heading would reopen the drift class E8 exists to
    # prevent (Codex P2 on the 2.33.0 branch caught exactly this hole).
    block_headings = set()
    for fname in MARKER_BLOCKS + ["model-routing-section.md"]:
        f = blocks_dir / fname
        if f.is_file():
            first = f.read_text().split("\n", 1)[0]
            block_headings.add(re.sub(r"\s*<!-- gstack-[a-z-]+-v\d+ -->\s*$", "", first).lstrip("#").strip())
    for gen, text in gen_texts.items():
        for i, line in enumerate(text.splitlines(), 1):
            if line.startswith("#") and re.search(r"<!-- gstack-[a-z-]+-v\d+ -->", line):
                errors.append(f"E8 {gen}/SKILL.md:{i}: inline emitted-block copy (marker heading) — blocks/ is the single source")
            elif line.startswith("#") and line.lstrip("#").strip() in block_headings:
                errors.append(f"E8 {gen}/SKILL.md:{i}: inline emitted-block copy (markerless heading '{line.lstrip('#').strip()}') — blocks/ is the single source")
        for ref in set(re.findall(r"blocks/([A-Za-z0-9_.-]+\.md)", text)):
            if not (blocks_dir / ref).is_file():
                errors.append(f"E8 {gen}/SKILL.md references nonexistent blocks/{ref}")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\nlint-skills: {len(errors)} error(s), {len(warnings)} warning(s) across {len(skill_dirs)} skills")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
