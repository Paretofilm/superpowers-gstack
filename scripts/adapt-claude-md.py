#!/usr/bin/env python3
"""adapt-claude-md — the one writer of a project's CLAUDE.md.

/superpowers-gstack:adapt decides WHAT a project gets (project type, selected
skills, domain sensitivity, placeholder values). This script does everything that
touches the file, deterministically:

  1. snapshot   `.gstack/CLAUDE.md.pre-adapt` — rotated, never overwritten,
                excluded via .git/info/exclude; skipped (and said) when no
                CLAUDE.md exists yet
  2. header     the two HTML comment lines at the top, rewritten every run
  3. retired    a marker-carrying `Autonomy and user interruption` section is
                removed within its size bound; a grown one is deferred
  4. renames    retired skill names outside marker-managed sections and fences
  5. routing    `--routing-file` is inserted only when `## Skill routing` is absent
  6. blocks     every block in BLOCKS: skip / replace / attribute-then-replace /
                append, with the growth check (provenance, ratio, volume — any one
                fires), sentinel attribution, H3 demotion, `<!-- emitted=N -->`
  7. model      Model Routing: a stale table is replaced, a user's own is kept
  8. verify     every removed line the new block does not carry is reported

Exit 0: written (or --dry-run completed). Exit 2: refused — nothing written; the
reason is on stderr (BLOCKED, UNRESOLVED PLACEHOLDER, UNREADABLE, INTERNAL). Never
a traceback. The report ends with one JSON line the skill reads for its questions.

Why a script: the prose version of these rules was ~550 lines and lint E13 pinned
twenty of its sentences because a reword could delete a guard. A model performing
markdown surgery once replaced a 198-line section with a 73-line block and reported
nothing; a script cannot forget the growth check.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_BLOCKS = REPO / "skills" / "adapt" / "blocks"
PLUGIN_JSON = REPO / ".claude-plugin" / "plugin.json"

REMOVED_LABEL = "**Removed (not plugin prose):**"
NOTHING_REMOVED = "Nothing project-authored was removed."
DEFERRED_LABEL = "**Deferred (grown past its block, not upgraded):**"

HEADER_LINE2 = (
    "<!-- Sections whose heading carries a gstack-<name>-vN marker are plugin-managed: "
    "/adapt replaces each one wholesale on upgrade. Put project-specific findings — the "
    "measurement you took, the flag that worked — in your own H2 section with no marker; "
    "/adapt leaves those alone. One exception: the headings it manages are reserved even "
    "when unmarked (the marked ones in this file, plus Model Routing), because an unmarked "
    "copy of one reads as an older emitted section. Prefix your own headings with this "
    "project's name and none of them can collide. -->")
HEADER_VERSION_RE = re.compile(r"^<!-- superpowers-gstack: \d+\.\d+\.\d+ -->[ \t]*$")
HEADER_WARN_PREFIX = "<!-- Sections whose heading carries"

NATIVE = frozenset({"ios", "macos", "both"})
TRACKS = NATIVE | {"web"}
SENSITIVITIES = ("very high", "high", "medium", "low")

RATIO = 1.5          # section more than 1.5x the block's line count
GROWTH_LINES = 20    # more than ~20 lines over `emitted=`, or ~20 lines the block lacks
PLAUSIBLE_BAND = 20  # an `emitted=` more than this above the block is a miscount

MARKER_RE = re.compile(r"<!-- (gstack-[a-z-]+)-v(\d+) -->")
EMITTED_RE = re.compile(r"<!-- emitted=(\d+) -->")
HEADING_RE = re.compile(r"^(#{1,6}) (.*)$")
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


@dataclass(frozen=True)
class Block:
    file: str
    marker: str                         # `gstack-<name>`, without the version
    heading: str                        # regex on the heading text, anchored at its start
    sentinels: tuple[str, ...] | None   # None: a heading only this plugin writes — always attributed
    case3: str = "replace"              # "preserve": never replace a markerless copy, insert nothing
    tracks: frozenset | None = None     # None: every track


BLOCKS = (
    Block("git-hygiene.md", "gstack-git-hygiene", r"Git hygiene",
          ("Hygiene rules (NEVER violate)", "Committing is not backing up")),
    Block("multi-lens-review.md", "gstack-multi-lens-review", r"Multi-lens review",
          ("What counts as ship-worthy", "pitfall-verification")),
    Block("code-reuse.md", "gstack-code-reuse", r"Code reuse discipline", (), case3="preserve"),
    Block("plan-fidelity.md", "gstack-plan-fidelity", r"Keep the plan true to the code",
          ("The three ways a plan goes stale", "fix the plan in the same commit")),
    Block("session-continuity.md", "gstack-session-continuity", r"Session [Cc]ontinuity",
          ("docs/superpowers/handoff.md",)),
    Block("track-routing.md", "gstack-routing", r"Track-aware routing \(dual-track\)", None),
    Block("xcode-tools.md", "gstack-xcode-tools", r"Native Apple development tools",
          ("XcodeBuildMCP", "MUST be performed by the agent"), tracks=NATIVE),
    Block("companion-skills.md", "gstack-companion-skills", r"Companion skills",
          ("swiftui-expert-skill", "discovery — not routing"), tracks=NATIVE),
)
MODEL_ROUTING_FILE = "model-routing-section.md"
MODEL_ROUTING_TABLE_RE = re.compile(r"Pi/MLX|\|\s*(Model|Sensitivity|Base tier|Claude)\s*\|")

# The retired autonomy block: shipped 56 lines at v1 and 31 at v2. Removed only
# within `emitted`+3, else the marker version's size +3; a grown one is deferred.
AUTONOMY_HEADING = "Autonomy and user interruption"
AUTONOMY_MARKER = "gstack-autonomy"
AUTONOMY_SIZE = {1: 56, 2: 31}
AUTONOMY_TOLERANCE = 3
AUTONOMY_SENTINELS = ("The only five reasons to stop and ask", "Forbidden phrases")
AUTONOMY_SUBSECTIONS = ("The only five reasons to stop and ask", "Do NOT stop to",
                        "Forbidden phrases", "Status updates DURING work, not AS wait-states")

RENAMES = (
    (("macos-native-review", "ios-native-review"), "apple-native-review"),
    (("macos-e2e-scaffold", "ios-e2e-scaffold"), "e2e-scaffold"),
)
REMOVED_SKILLS = ("ios-visual-explore",)


def _skill_ref(names) -> re.Pattern:
    alt = "|".join(re.escape(n) for n in names)
    return re.compile(r"(?<![\w/-])/(superpowers-gstack:)?(" + alt + r")(?![\w/-])")


# --- document primitives ---------------------------------------------------------

def fence_mask(lines: list[str]) -> list[bool]:
    """True for every line inside a fenced code block, fence lines included. A
    `# comment` inside a bash block is not a heading; the prose never said so."""
    mask = [False] * len(lines)
    open_char, open_len = None, 0
    for i, line in enumerate(lines):
        m = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$", line)
        if open_char is None:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                open_char, open_len = m.group(1)[0], len(m.group(1))
                mask[i] = True
        else:
            mask[i] = True
            if m and m.group(1)[0] == open_char and len(m.group(1)) >= open_len and not m.group(2).strip():
                open_char = None
    return mask


def heading_text(line: str) -> str:
    """The heading's words: level stripped, HTML comments and ATX closers removed."""
    m = HEADING_RE.match(line)
    t = m.group(2) if m else line
    t = re.sub(r"<!--.*?-->", "", t)
    return re.sub(r"\s+#+\s*$", "", t).strip()


def headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(index, level, raw line) for every heading outside a fence."""
    mask = fence_mask(lines)
    out = []
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        m = HEADING_RE.match(line)
        if m:
            out.append((i, len(m.group(1)), line))
    return out


def section_end(lines: list[str], start: int, level: int) -> int:
    for i, lvl, _ in headings(lines):
        if i > start and lvl <= level:
            return i
    return len(lines)


def content_end(lines: list[str], start: int, end: int) -> int:
    """`end` with the section's trailing blank lines excluded — the size a bound
    or a growth count is measured on. Blank separators are nobody's content."""
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return end


def norm(line: str) -> str:
    return " ".join(line.split())


def words(line: str) -> set[str]:
    return {w for w in re.findall(r"[\w'`./-]+", line.lower()) if len(w) > 2}


def is_plugin_prose(line: str, block_norm: set[str], block_words: list[set[str]]) -> bool:
    """A section line the block carries — verbatim, or reworded (four of five of
    its words sit in one block line). Everything else is at risk. Short lines
    match verbatim only; a five-word line has too few words to reword."""
    n = norm(line)
    if not n:
        return True
    if n in block_norm:
        return True
    w = words(n)
    if len(w) < 5:
        return False
    return any(len(w & bw) / len(w) >= 0.8 for bw in block_words)


def demote(block_lines: list[str]) -> list[str]:
    """Root H2 -> H3 and every H3 subsection -> H4, outside fences. Unconditional:
    a no-op for a block without subsections, the fix for one that grows them."""
    mask = fence_mask(block_lines)
    out = []
    for i, line in enumerate(block_lines):
        if not mask[i] and line.startswith("## "):
            line = "#" + line
        elif not mask[i] and line.startswith("### "):
            line = "#" + line
        out.append(line)
    return out


def project_name(text: str, project_dir: Path) -> str:
    for line in text.splitlines():
        m = re.match(r"^# (.+)$", line)
        if m:
            return heading_text(line)
    return project_dir.name


# --- the report -------------------------------------------------------------------

@dataclass
class Report:
    applied: bool = False
    changes: list = field(default_factory=list)
    preserved: list = field(default_factory=list)
    removed: list = field(default_factory=list)      # {"section", "lines", "where"}
    deferred: list = field(default_factory=list)     # {"marker","heading","lines","block_lines","emitted","at_risk"}
    unattributed: list = field(default_factory=list) # {"heading", "reason"}
    notes: list = field(default_factory=list)
    snapshot: str | None = None
    rotated: str | None = None

    def as_json(self) -> str:
        return json.dumps({
            "applied": self.applied, "changes": self.changes, "preserved": self.preserved,
            "removed": self.removed, "deferred": self.deferred,
            "unattributed": self.unattributed, "notes": self.notes,
            "snapshot": self.snapshot, "rotated": self.rotated,
        }, ensure_ascii=False)


# --- the merge --------------------------------------------------------------------

@dataclass
class Context:
    blocks: dict[str, str]          # file name -> raw text
    version: str
    track: str
    sets: dict[str, str]
    rescue: set[str]
    routing: str | None
    model_routing: bool
    project: str
    needed: set[str] = field(default_factory=set)   # placeholders in blocks emitted this run


def _block_meta(raw: str) -> tuple[str, int, int]:
    """(marker name, version, emitted line count) of a block file."""
    head = raw.split("\n", 1)[0]
    m = MARKER_RE.search(head)
    return m.group(1), int(m.group(2)), raw.count("\n")


def _resolve(text: str, ctx: Context) -> str:
    ctx.needed |= set(PLACEHOLDER_RE.findall(text))
    return PLACEHOLDER_RE.sub(lambda m: ctx.sets.get(m.group(1), m.group()), text)


def _emitted_block(raw: str, ctx: Context, level: int) -> list[str]:
    """The block as a generator writes it: provenance beside the marker (never
    inside it), demoted when the root it replaces is H3, placeholders resolved."""
    n = raw.count("\n")
    lines = raw.rstrip("\n").split("\n")
    lines[0] = f"{lines[0]}<!-- emitted={n} -->"
    if level == 3:
        lines = demote(lines)
    return _resolve("\n".join(lines), ctx).split("\n")


def _splice(lines: list[str], start: int, end: int, new: list[str]) -> list[str]:
    """Replace lines[start:end] with `new`, keeping one blank line after it when
    something follows."""
    tail = lines[end:]
    if tail and tail[0].strip():
        new = new + [""]
    if new and not new[-1].strip() and tail and not tail[0].strip():
        new = new[:-1]
    return lines[:start] + new + tail


def _append(lines: list[str], new: list[str]) -> list[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    return lines + ([""] if lines else []) + new


def apply_header(lines: list[str], ctx: Context, report: Report) -> list[str]:
    head = lines[:6]
    kept = [l for l in head if not HEADER_VERSION_RE.match(l) and not l.startswith(HEADER_WARN_PREFIX)]
    new = [f"<!-- superpowers-gstack: {ctx.version} -->", HEADER_LINE2] + kept + lines[6:]
    if new != lines:
        old = next((l for l in head if HEADER_VERSION_RE.match(l)), None)
        report.changes.append(f"header: {old.strip('<!-> ') if old else 'none'} -> superpowers-gstack {ctx.version}")
    return new


def _find_section(lines: list[str], marker: str | None, heading_re: str):
    """The section this block owns: a marker-carrying heading wins over a bare
    heading with the right words — so a user's unmarked copy next to an emitted
    one is never mistaken for the plugin's, and a second run is a no-op."""
    by_marker, by_text = [], []
    for i, lvl, raw in headings(lines):
        if lvl not in (2, 3):
            continue
        m = MARKER_RE.search(raw)
        if marker and m and m.group(1) == marker:
            by_marker.append((i, lvl, raw, int(m.group(2))))
        elif re.match(heading_re, heading_text(raw)):
            by_text.append((i, lvl, raw, None))
    return (by_marker or by_text or [None])[0]


def growth(lines: list[str], start: int, end: int, raw_block: str) -> dict:
    sec = lines[start:content_end(lines, start, end)]
    body = sec[1:]
    block_lines = raw_block.rstrip("\n").split("\n")
    block_norm = {norm(l) for l in block_lines}
    block_words = [words(norm(l)) for l in block_lines if norm(l)]
    at_risk = [l for l in body if not is_plugin_prose(l, block_norm, block_words)]
    n_sec, n_block = len(sec), raw_block.count("\n")
    m = EMITTED_RE.search(sec[0])
    emitted = int(m.group(1)) if m else None
    triggers = []
    if emitted is not None:
        plausible = not (n_sec <= emitted or emitted > n_block + PLAUSIBLE_BAND)
        if plausible and n_sec - emitted > GROWTH_LINES:
            triggers.append("provenance")
    if n_sec > RATIO * n_block:
        triggers.append("ratio")
    if len(at_risk) > GROWTH_LINES:
        triggers.append("volume")
    return {"lines": n_sec, "block_lines": n_block, "emitted": emitted,
            "at_risk": at_risk, "triggers": triggers}


def rescue_section(lines: list[str], start: int, end: int, raw_block: str, ctx: Context) -> list[str]:
    """The old section's own lines — everything the block does not carry, with
    the section's headings and whole fenced blocks that hold any such line — under
    a new unmarked H2 the plugin will never manage."""
    body = lines[start + 1:end]
    block_lines = raw_block.rstrip("\n").split("\n")
    block_norm = {norm(l) for l in block_lines}
    block_words = [words(norm(l)) for l in block_lines if norm(l)]
    mask = fence_mask(body)
    keep = [False] * len(body)
    i = 0
    while i < len(body):
        if mask[i]:
            j = i
            while j < len(body) and mask[j]:
                j += 1
            if any(not is_plugin_prose(body[k], block_norm, block_words) and body[k].strip()
                   for k in range(i, j)):
                for k in range(i, j):
                    keep[k] = True
            i = j
            continue
        if HEADING_RE.match(body[i]) or (body[i].strip() and not is_plugin_prose(body[i], block_norm, block_words)):
            keep[i] = True
        i += 1
    out = [f'## {ctx.project} — notes rescued from "{heading_text(lines[start])}"', ""]
    prev_blank = True
    for k, line in enumerate(body):
        if keep[k]:
            if HEADING_RE.match(line) and not prev_blank:
                out.append("")
            out.append(line)
            prev_blank = False
        elif not prev_blank and not line.strip():
            out.append("")
            prev_blank = True
    while out and not out[-1].strip():
        out.pop()
    return out


def apply_block(lines: list[str], blk: Block, ctx: Context, report: Report) -> list[str]:
    raw = ctx.blocks[blk.file]
    marker, cur_version, _ = _block_meta(raw)
    name = heading_text(raw.split("\n", 1)[0])
    found = _find_section(lines, marker, blk.heading)
    wanted = blk.tracks is None or ctx.track in blk.tracks
    if found is None:
        if wanted:
            report.changes.append(f"{name}: added ({marker}-v{cur_version})")
            return _append(lines, _emitted_block(raw, ctx, 2))
        return lines
    start, level, raw_head, version = found
    end = section_end(lines, start, level)
    head_name = heading_text(raw_head)
    if version == cur_version:
        report.preserved.append(f"{head_name}: already at {marker}-v{cur_version}")
        return lines
    if version is None:
        body = "\n".join(lines[start + 1:end])
        if blk.case3 == "preserve":
            report.preserved.append(
                f"Found existing markerless `{head_name}` section in CLAUDE.md; preserved as-is. "
                f"To switch to the plugin-managed version, delete your existing section and re-run `/adapt`.")
            return lines
        attributed = blk.sentinels is None or any(s in body for s in blk.sentinels)
        if not attributed:
            report.unattributed.append({"heading": head_name, "reason": (
                f"`{head_name}`: I cannot attribute this section to a past emitter — it has no version "
                f"marker and none of the phrases an older `/adapt` would have written. I left it exactly "
                f"as it was and put the current plugin version below it, so nothing of yours was touched. "
                f"If it *is* an old plugin section, delete your copy and re-run `/adapt` and it will "
                f"upgrade cleanly.")})
            report.changes.append(f"{name}: inserted below your unmarked `{head_name}` ({marker}-v{cur_version})")
            block_lines = [""] + _emitted_block(raw, ctx, 2)
            return _splice(lines, end, end, block_lines)
    g = growth(lines, start, end, raw)
    if g["triggers"] and marker not in ctx.rescue:
        report.deferred.append({"marker": marker, "heading": head_name, "lines": g["lines"],
                                "block_lines": g["block_lines"], "emitted": g["emitted"],
                                "old_version": version, "triggers": g["triggers"],
                                "at_risk": g["at_risk"]})
        return lines
    new = _emitted_block(raw, ctx, level)
    if g["triggers"]:
        rescued = rescue_section(lines, start, end, raw, ctx)
        report.removed.append({"section": head_name, "lines": len(g["at_risk"]),
                               "where": f"moved to `{rescued[0]}`"})
        new = new + [""] + rescued
    elif g["at_risk"]:
        report.removed.append({"section": head_name, "lines": len(g["at_risk"]),
                               "where": "not in the new block — review them in the snapshot"})
    was = f"{marker}-v{version}" if version is not None else "no marker"
    report.changes.append(f"{name}: {was} -> {marker}-v{cur_version}" + (" (H3 root, demoted)" if level == 3 else ""))
    return _splice(lines, start, end, new)


def apply_autonomy(lines: list[str], report: Report) -> list[str]:
    for i, level, raw_head in reversed(headings(lines)):
        if level not in (2, 3) or heading_text(raw_head) != AUTONOMY_HEADING:
            continue
        m = MARKER_RE.search(raw_head)
        if m and m.group(1) != AUTONOMY_MARKER:
            continue
        # the block's own subsections sat at the root's level in pre-2.36.1 emits
        end = i + 1
        hs = headings(lines)
        for j, lvl, h in hs:
            if j <= i:
                continue
            if lvl > level or (lvl == level and heading_text(h) in AUTONOMY_SUBSECTIONS):
                end = section_end(lines, j, lvl) if lvl == level else max(end, j + 1)
                continue
            break
        end = max(end, section_end(lines, i, level) if all(
            heading_text(h) not in AUTONOMY_SUBSECTIONS for j, lvl, h in hs if j > i and lvl == level) else end)
        body = "\n".join(lines[i + 1:end])
        if m:
            version = int(m.group(2))
        elif any(s in body for s in AUTONOMY_SENTINELS):
            version = 1
        else:
            continue   # the user's own section — never touched
        e = EMITTED_RE.search(raw_head)
        bound = (int(e.group(1)) if e else AUTONOMY_SIZE.get(version, AUTONOMY_SIZE[1])) + AUTONOMY_TOLERANCE
        n = content_end(lines, i, end) - i
        if n <= bound:
            report.changes.append(
                f"removed the retired `{AUTONOMY_HEADING}` section ({n} lines, marker v{version})")
            lines = _splice(lines, i, end, [])
            while len(lines) > i > 0 and not lines[i].strip() and not lines[i - 1].strip():
                del lines[i]
        else:
            report.deferred.append({"marker": AUTONOMY_MARKER, "heading": AUTONOMY_HEADING,
                                    "lines": n, "block_lines": AUTONOMY_SIZE.get(version, 0),
                                    "emitted": int(e.group(1)) if e else None, "old_version": version,
                                    "triggers": ["retired block, grown"], "at_risk": []})
    return lines


def _managed_ranges(lines: list[str]) -> list[tuple[int, int]]:
    out = []
    for i, lvl, raw in headings(lines):
        if MARKER_RE.search(raw) or heading_text(raw) == "Model Routing":
            out.append((i, section_end(lines, i, lvl)))
    return out


def apply_renames(lines: list[str], report: Report) -> list[str]:
    mask = fence_mask(lines)
    managed = _managed_ranges(lines)
    editable = [not mask[i] and not any(a <= i < b for a, b in managed) for i in range(len(lines))]
    counts: dict[str, int] = {}
    removed = 0
    out = []
    for i, line in enumerate(lines):
        if not editable[i]:
            out.append(line)
            continue
        if _skill_ref(REMOVED_SKILLS).search(line):
            removed += 1
            continue
        for olds, new in RENAMES:
            pat = _skill_ref(olds)
            line, k = pat.subn(lambda m: f"/{m.group(1) or ''}{new}", line)
            if k:
                counts[new] = counts.get(new, 0) + k
        out.append(line)
    lines = out
    # rows that collapsed into the same skill become one row (keep the first)
    mask = fence_mask(lines)
    result, seen, in_table = [], set(), False
    for i, line in enumerate(lines):
        is_row = not mask[i] and line.lstrip().startswith("|")
        if is_row and not in_table:
            in_table, seen = True, set()
        elif not is_row:
            in_table = False
        if is_row:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            key = cells[0] if cells else ""
            if key and re.search(r"/(superpowers-gstack:)?[a-z0-9-]+", key) and not re.fullmatch(r"[-: ]+", key):
                if key in seen:
                    removed += 1
                    continue
                seen.add(key)
        result.append(line)
    for new, k in sorted(counts.items()):
        olds = next(o for o, n in RENAMES if n == new)
        report.changes.append(f"renamed `{'`/`'.join(olds)}` -> `{new}` ({k} places)")
    if removed:
        report.changes.append(f"removed {removed} row(s)/line(s) naming a retired skill or duplicating a renamed one")
    return result


def apply_routing(lines: list[str], ctx: Context, report: Report) -> list[str]:
    if not ctx.routing:
        return lines
    if any(lvl == 2 and heading_text(raw) == "Skill routing" for _, lvl, raw in headings(lines)):
        report.preserved.append("Skill routing: present, kept as-is (its plugin-managed subsections are handled per block)")
        return lines
    new = ctx.routing.rstrip("\n").split("\n")
    hs = headings(lines)
    if not hs:
        at = len(lines)
    else:
        first = hs[0]
        at = next((i for i, lvl, _ in hs if i > first[0]), len(lines))
    while at > 0 and not lines[at - 1].strip():
        at -= 1
    report.changes.append("Skill routing: added")
    return _splice(lines, at, at, [""] + new)


def apply_model_routing(lines: list[str], ctx: Context, report: Report) -> list[str]:
    raw = ctx.blocks[MODEL_ROUTING_FILE].rstrip("\n").split("\n")
    found = [(i, lvl, h) for i, lvl, h in headings(lines) if lvl in (2, 3) and heading_text(h) == "Model Routing"]
    if found:
        i, lvl, h = found[0]
        end = section_end(lines, i, lvl)
        body = "\n".join(lines[i + 1:end])
        if not MODEL_ROUTING_TABLE_RE.search(body):
            report.preserved.append(
                "`Model Routing`: the heading is yours — it carries no routing table with a model column, "
                "so it was left untouched and the plugin's Model Routing was not emitted. To get the "
                "plugin-managed section, rename yours and re-run `/adapt`.")
            return lines
        if not ctx.model_routing:
            return lines
        new = _resolve("\n".join(raw), ctx).split("\n")
        if lines[i:end] == new or lines[i:end] == new + [""]:
            report.preserved.append("Model Routing: already current")
            return lines
        report.changes.append("Model Routing: replaced the older block")
        return _splice(lines, i, end, new)
    if not ctx.model_routing:
        return lines
    new = _resolve("\n".join(raw), ctx).split("\n")
    sr = next(((i, lvl) for i, lvl, h in headings(lines) if lvl == 2 and heading_text(h) == "Skill routing"), None)
    report.changes.append("Model Routing: added")
    if sr is None:
        return _append(lines, new)
    at = section_end(lines, sr[0], sr[1])
    while at > 0 and not lines[at - 1].strip():
        at -= 1
    return _splice(lines, at, at, [""] + new)


def merge(text: str | None, ctx: Context) -> tuple[str, Report]:
    report = Report()
    lines = (text or "").split("\n") if text else []
    if lines and lines[-1] == "":
        lines.pop()
    if text is None:
        report.notes.append("no prior CLAUDE.md — nothing to snapshot; the file is created")
    lines = apply_header(lines, ctx, report)
    lines = apply_autonomy(lines, report)
    lines = apply_renames(lines, report)
    lines = apply_routing(lines, ctx, report)
    for blk in BLOCKS:
        lines = apply_block(lines, blk, ctx, report)
    lines = apply_model_routing(lines, ctx, report)
    return "\n".join(lines).rstrip("\n") + "\n", report


# --- report rendering -----------------------------------------------------------------

def render(report: Report, ctx: Context, dry_run: bool) -> str:
    out = [f"ADAPT REPORT — {'dry run' if dry_run else 'applied'} (superpowers-gstack {ctx.version}, track {ctx.track})", ""]
    out += ["**Changes made:**"] + [f"- {c}" for c in report.changes] + (["- none"] if not report.changes else []) + [""]
    out += ["**Preserved:**"] + [f"- {p}" for p in report.preserved]
    for u in report.unattributed:
        out += ["", "> " + u["reason"]]
    out += ["", REMOVED_LABEL]
    if report.removed:
        out += [f"- `{r['section']}`: {r['lines']} line(s) — {r['where']}" for r in report.removed]
    else:
        out.append(f"- {NOTHING_REMOVED}")
    if report.deferred:
        out += ["", DEFERRED_LABEL]
        for d in report.deferred:
            was = f"marker {d['marker']}-v{d['old_version']}" if d.get("old_version") is not None else "no marker"
            prov = f", emitted={d['emitted']}" if d.get("emitted") is not None else ""
            out.append(f"- `{d['heading']}`: {d['lines']} lines against the {d['block_lines']}-line block "
                       f"({was}{prov}; fired: {', '.join(d['triggers'])}); {len(d['at_risk'])} line(s) at risk. "
                       f"Left at its old version. Re-run with `--rescue {d['marker']}` to move those lines into an "
                       f"unmarked section and upgrade.")
    out.append("")
    if report.snapshot:
        out.append(f"**Snapshot:** `{report.snapshot}` holds CLAUDE.md exactly as it was before this run. "
                   f"Restore the whole file with `cp .gstack/CLAUDE.md.pre-adapt CLAUDE.md`."
                   + (f" The previous snapshot was rotated aside to `{report.rotated}`." if report.rotated else ""))
    elif dry_run:
        out.append("**Snapshot:** none written (dry run).")
    else:
        out.append("**Snapshot:** none — " + (report.notes[0] if report.notes else "no prior CLAUDE.md"))
    for n in report.notes:
        out.append(f"Note: {n}")
    out.append("")
    out.append(report.as_json())
    return "\n".join(out)


# --- I/O ------------------------------------------------------------------------------

def snapshot(project: Path, report: Report) -> None:
    gstack = project / ".gstack"
    gstack.mkdir(exist_ok=True)
    snap = gstack / "CLAUDE.md.pre-adapt"
    if snap.exists():
        rotated = gstack / f"CLAUDE.md.pre-adapt.{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        k = 0
        while rotated.exists():
            k += 1
            rotated = gstack / f"CLAUDE.md.pre-adapt.{datetime.now().strftime('%Y%m%d-%H%M%S')}-{k}"
        snap.rename(rotated)
        report.rotated = str(rotated.relative_to(project))
    snap.write_bytes((project / "CLAUDE.md").read_bytes())
    report.snapshot = str(snap.relative_to(project))
    try:
        excl = subprocess.run(["git", "rev-parse", "--git-path", "info/exclude"], cwd=project,
                              capture_output=True, text=True, check=True).stdout.strip()
        excl_path = Path(excl) if Path(excl).is_absolute() else project / excl
        excl_path.parent.mkdir(parents=True, exist_ok=True)
        current = excl_path.read_text() if excl_path.exists() else ""
        if ".gstack/CLAUDE.md.pre-adapt*" not in current.splitlines():
            excl_path.write_text(current + ("" if current.endswith("\n") or not current else "\n") + ".gstack/CLAUDE.md.pre-adapt*\n")
    except (subprocess.CalledProcessError, OSError):
        pass   # not a git repository: the snapshot still works


def read_track(project: Path, override: str | None) -> str:
    if override:
        value = override
    else:
        f = project / ".gstack" / "track"
        if not f.is_file():
            return "web"
        value = f.read_text().removesuffix("\n")
    if value not in TRACKS:
        raise Refusal(f"BLOCKED — invalid .gstack/track {value!r}: must be ios, macos, both or web")
    return value


def read_executor(project: Path) -> str:
    f = project / ".gstack" / "e2e-executor"
    if not f.is_file():
        return "host"
    value = f.read_text().removesuffix("\n")
    if value not in ("host", "vm"):
        raise Refusal(f"BLOCKED — invalid .gstack/e2e-executor {value!r}: must be exactly host or vm")
    return value


class Refusal(Exception):
    pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--track", choices=sorted(TRACKS))
    ap.add_argument("--set", action="append", default=[], metavar="TOKEN=value")
    ap.add_argument("--routing-file")
    ap.add_argument("--rescue", action="append", default=[], metavar="MARKER")
    ap.add_argument("--no-model-routing", action="store_true")
    ap.add_argument("--mkdirs", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--plugin-version")
    ap.add_argument("--blocks", default=str(DEFAULT_BLOCKS))
    ap.add_argument("--project-name")
    a = ap.parse_args(argv)
    try:
        project = Path(a.project_dir).expanduser().resolve()
        if not project.is_dir():
            raise Refusal(f"UNREADABLE: {project} is not a directory")
        blocks_dir = Path(a.blocks).expanduser()
        blocks = {}
        for blk in BLOCKS + (Block(MODEL_ROUTING_FILE, "", "", None),):
            f = blocks_dir / blk.file
            if not f.is_file():
                raise Refusal(f"UNREADABLE: block file {f} is missing — run `/plugin update superpowers-gstack`")
            blocks[blk.file] = f.read_text(encoding="utf-8")
        version = a.plugin_version or json.loads(PLUGIN_JSON.read_text())["version"]
        sets = {}
        for s in a.set:
            if "=" not in s:
                raise Refusal(f"USAGE ERROR: --set needs TOKEN=value, got {s!r}")
            k, v = s.split("=", 1)
            sets[k.strip()] = v
        if "DOMAIN_SENSITIVITY" in sets and sets["DOMAIN_SENSITIVITY"] not in SENSITIVITIES:
            raise Refusal(f"BLOCKED — DOMAIN_SENSITIVITY must be one of {', '.join(SENSITIVITIES)}")
        track = read_track(project, a.track)
        sets.setdefault("E2E_EXECUTOR", read_executor(project))
        claude = project / "CLAUDE.md"
        text = claude.read_text(encoding="utf-8") if claude.is_file() else None
        routing = Path(a.routing_file).expanduser().read_text(encoding="utf-8") if a.routing_file else None
        ctx = Context(blocks=blocks, version=version, track=track, sets=sets, rescue=set(a.rescue),
                      routing=routing, model_routing=not a.no_model_routing,
                      project=a.project_name or project_name(text or "", project))
        new_text, report = merge(text, ctx)
        unresolved = sorted(t for t in ctx.needed if t not in sets)
        if unresolved:
            raise Refusal("UNRESOLVED PLACEHOLDER: " + ", ".join(unresolved) +
                          " — pass --set TOKEN=value for each (see skills/adapt/blocks/PLACEHOLDERS.md); nothing was written")
        if PLACEHOLDER_RE.search("\n".join(l for l in new_text.split("\n") if "{{" in l and "PLACEHOLDERS" not in l)) \
                and set(PLACEHOLDER_RE.findall(new_text)) & ctx.needed:
            raise Refusal("INTERNAL: a placeholder survived resolution; nothing was written")
        if not a.dry_run and (text is None or new_text != text or a.mkdirs):
            if text is not None and new_text != text:
                snapshot(project, report)
            if text is None or new_text != text:
                claude.write_text(new_text, encoding="utf-8")
            if a.mkdirs:
                for d in ("specs", "plans"):
                    p = project / "docs" / "superpowers" / d
                    p.mkdir(parents=True, exist_ok=True)
                    (p / ".gitkeep").touch()
                report.changes.append("created docs/superpowers/specs and docs/superpowers/plans")
            report.applied = True
        elif not a.dry_run:
            report.applied = True
        if text is not None and new_text == text:
            report.changes = []
        print(render(report, ctx, a.dry_run))
        return 0
    except Refusal as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError, ValueError, KeyError) as exc:
        print(f"INTERNAL: {type(exc).__name__}: {exc} — nothing was written", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
