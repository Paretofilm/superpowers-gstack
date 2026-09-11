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
  4. renames    retired skill names outside marker-managed sections and fences;
                a roster row or list item that IS a removed skill goes, a prose
                line that mentions one is kept and reported
  5. routing    `--routing-file` is inserted only when `## Skill routing` is absent
  6. blocks     every block in BLOCKS: skip / replace / attribute-then-replace /
                append, with the growth check (provenance, ratio, volume — any one
                fires), sentinel attribution, H3 demotion, `<!-- emitted=N -->`
  7. model      Model Routing: an emitted or table-shaped section is replaced, a
                user's own is kept
  8. verify     every removed line the new block does not carry verbatim is
                listed, in full, under "Removed (not plugin prose)"

Exit 0: written (or --dry-run completed). Exit 2: refused — nothing written; the
reason is on stderr (BLOCKED, UNRESOLVED PLACEHOLDER, UNREADABLE, USAGE ERROR,
INTERNAL). Never a traceback. Every check that can refuse runs BEFORE the first
write, and the write itself is atomic. The report ends with one JSON line the
skill reads for its questions.

Why a script: the prose version of these rules was ~550 lines and lint E13 pinned
twenty of its sentences because a reword could delete a guard. A model performing
markdown surgery once replaced a 198-line section with a 73-line block and reported
nothing; a script cannot forget the growth check.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
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
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

NATIVE = frozenset({"ios", "macos", "both"})
TRACKS = NATIVE | {"web"}
SENSITIVITIES = ("very high", "high", "medium", "low")
EXECUTORS = ("host", "vm")
NO_TEAM_TEXT = "<none — no paid developer account was found; stable signing requires a Team ID>"

RATIO = 1.5          # section more than 1.5x the block's line count
GROWTH_LINES = 20    # more than ~20 lines over `emitted=`, or ~20 lines the block lacks
PLAUSIBLE_BAND = 20  # an `emitted=` more than this above the block is a miscount
REWORD_OVERLAP = 0.85
NEGATIONS = frozenset({"never", "not", "no", "don't", "dont", "avoid", "must", "always", "only", "except", "unless"})

MARKER_RE = re.compile(r"<!-- (gstack-[a-z-]+)-v(\d+) -->")
EMITTED_RE = re.compile(r"<!-- emitted=(\d+) -->")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*)$")
SETEXT_H1_RE = re.compile(r"^ {0,3}=+[ \t]*$")
SETEXT_H2_RE = re.compile(r"^ {0,3}-+[ \t]*$")
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


class Refusal(Exception):
    pass


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
# A Model Routing section is the plugin's when its body carries the emitted block's
# own sentence, or a routing TABLE (header row with a model/tier column, then a
# separator row). A bare mention of `Pi/MLX` in prose is the project's.
MODEL_ROUTING_SENTINEL = "**This project's domain sensitivity:"
MODEL_ROUTING_HEADER_RE = re.compile(r"^\s*\|.*\b(Model|Sensitivity|Base tier|Pi/MLX)\b.*\|\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")

# The retired autonomy block: shipped 56 lines at v1 and 31 at v2. Removed only
# within `emitted`+3 (when that count is plausible), else the marker version's
# size +3; a grown one is deferred.
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
    """True for every line inside a fenced code block or a multi-line HTML
    comment, delimiters included. A `# comment` inside a bash block is not a
    heading, and neither is a heading commented out; the prose never said so."""
    mask = [False] * len(lines)
    open_char, open_len, in_comment = None, 0, False
    for i, line in enumerate(lines):
        if in_comment:
            mask[i] = True
            if "-->" in line:
                in_comment = False
            continue
        m = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$", line)
        if open_char is None:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                open_char, open_len = m.group(1)[0], len(m.group(1))
                mask[i] = True
            elif "<!--" in line and "-->" not in line[line.index("<!--") + 4:]:
                mask[i] = True
                in_comment = True
        else:
            mask[i] = True
            if m and m.group(1)[0] == open_char and len(m.group(1)) >= open_len and not m.group(2).strip():
                open_char = None
    return mask


def unclosed_fence(lines: list[str]) -> tuple[str, int] | None:
    """("fence"|"comment", 1-based line) of a fence or HTML comment that never
    closes, or None. Appending below an open one would put every block inside
    it, invisible to the next run."""
    open_at, open_char, open_len, comment_at = None, None, 0, None
    for i, line in enumerate(lines):
        if comment_at is not None:
            if "-->" in line:
                comment_at = None
            continue
        m = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$", line)
        if open_char is None:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                open_at, open_char, open_len = i + 1, m.group(1)[0], len(m.group(1))
            elif "<!--" in line and "-->" not in line[line.index("<!--") + 4:]:
                comment_at = i + 1
        elif m and m.group(1)[0] == open_char and len(m.group(1)) >= open_len and not m.group(2).strip():
            open_char = None
    if open_char is not None:
        return ("fence", open_at)
    if comment_at is not None:
        return ("comment", comment_at)
    return None


def heading_text(line: str) -> str:
    """The heading's words: level stripped, HTML comments and ATX closers removed."""
    m = HEADING_RE.match(line)
    t = m.group(2) if m else line
    t = re.sub(r"<!--.*?-->", "", t)
    return re.sub(r"(^|\s+)#+\s*$", "", t).strip()


def headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(index, level, raw line) for every heading outside a fence or comment —
    ATX with up to three leading spaces, and Setext (`====` / `----` under a
    text line)."""
    mask = fence_mask(lines)
    out = []
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        m = HEADING_RE.match(line)
        if m:
            out.append((i, len(m.group(1)), line))
            continue
        if (line.strip() and i + 1 < len(lines) and not mask[i + 1]
                and not line.lstrip().startswith(("|", "-", "*", "+", ">", "<"))):
            nxt = lines[i + 1]
            if SETEXT_H1_RE.match(nxt):
                out.append((i, 1, line))
            elif SETEXT_H2_RE.match(nxt) and len(nxt.strip()) >= 3:
                out.append((i, 2, line))
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


def enclosing_end(lines: list[str], idx: int, level: int) -> int:
    """Where a NEW H2 may go when the section at `idx` is rooted deeper than H2:
    after the enclosing H2 subtree, so an inserted H2 never reparents the H3
    siblings that follow the section."""
    if level <= 2:
        return section_end(lines, idx, level)
    parent = None
    for i, lvl, _ in headings(lines):
        if i < idx and lvl <= 2:
            parent = (i, lvl)
    if parent is None:
        return section_end(lines, idx, level)
    return section_end(lines, parent[0], parent[1])


def norm(line: str) -> str:
    return " ".join(line.split())


def words(line: str) -> set[str]:
    return {w for w in re.findall(r"[\w'`./-]+", line.lower()) if len(w) > 2}


class BlockText:
    """A block's lines in the forms the checks need."""

    def __init__(self, raw: str):
        self.lines = raw.rstrip("\n").split("\n")
        self.norm = {norm(l) for l in self.lines}
        self.words = [(words(norm(l)), words(norm(l)) & NEGATIONS) for l in self.lines if norm(l)]
        self.count = raw.count("\n")

    def verbatim(self, line: str) -> bool:
        return not norm(line) or norm(line) in self.norm

    def reworded(self, line: str) -> bool:
        """Four of five words in one block line, with the SAME negation words —
        `Never commit at meaningful milestones` is not a reword of `Commit at
        meaningful milestones`, it is the opposite rule. Used only to size the
        Volume trigger; the report and the rescue never rely on it."""
        w = words(norm(line))
        if len(w) < 5:
            return False
        neg = w & NEGATIONS
        return any(len(w & bw) / len(w) >= REWORD_OVERLAP and bneg == neg for bw, bneg in self.words)


def demote(block_lines: list[str]) -> list[str]:
    """Root H2 -> H3 and every H3 subsection -> H4, outside fences. Unconditional:
    a no-op for a block without subsections, the fix for one that grows them."""
    mask = fence_mask(block_lines)
    out = []
    for i, line in enumerate(block_lines):
        if not mask[i] and (line.startswith("## ") or line.startswith("### ")):
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
    removed: list = field(default_factory=list)      # {"section", "lines": [...], "where"}
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
    m = MARKER_RE.search(raw.split("\n", 1)[0])
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


def _insert_after(lines: list[str], at: int, new: list[str]) -> list[str]:
    while at > 0 and not lines[at - 1].strip():
        at -= 1
    return _splice(lines, at, at, [""] + new)


def _append(lines: list[str], new: list[str]) -> list[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    return lines + ([""] if lines else []) + new


def apply_header(lines: list[str], ctx: Context, report: Report) -> list[str]:
    """The two comment lines at the very top. Only the LEADING comment block is
    touched — a version comment quoted in a fenced example further down is the
    project's."""
    i = 0
    old = None
    while i < len(lines) and (HEADER_VERSION_RE.match(lines[i]) or lines[i].startswith(HEADER_WARN_PREFIX)):
        if HEADER_VERSION_RE.match(lines[i]):
            old = lines[i]
        i += 1
    new = [f"<!-- superpowers-gstack: {ctx.version} -->", HEADER_LINE2] + lines[i:]
    if new != lines:
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
        elif re.match(heading_re, heading_text(raw), re.I):
            by_text.append((i, lvl, raw, None))
    if len(by_marker) > 1:
        _DUPES.append((marker, len(by_marker)))
    return (by_marker or by_text or [None])[0]


_DUPES: list[tuple[str, int]] = []


def growth(lines: list[str], start: int, end: int, blk: BlockText) -> dict:
    sec = lines[start:content_end(lines, start, end)]
    body = sec[1:]
    at_risk = [l for l in body if not blk.verbatim(l)]
    volume = [l for l in at_risk if not blk.reworded(l)]
    n_sec, n_block = len(sec), blk.count
    m = EMITTED_RE.search(sec[0])
    emitted = int(m.group(1)) if m else None
    triggers = []
    if emitted is not None:
        plausible = not (n_sec <= emitted or emitted > n_block + PLAUSIBLE_BAND)
        if plausible and n_sec - emitted > GROWTH_LINES:
            triggers.append("provenance")
    if n_sec > RATIO * n_block:
        triggers.append("ratio")
    if len(volume) > GROWTH_LINES:
        triggers.append("volume")
    return {"lines": n_sec, "block_lines": n_block, "emitted": emitted,
            "at_risk": at_risk, "triggers": triggers}


def rescue_section(lines: list[str], start: int, end: int, blk: BlockText, ctx: Context) -> list[str]:
    """The old section's own lines — everything the block does not carry
    VERBATIM, with the section's headings and whole fenced blocks that hold any
    such line, bytes intact — under a new unmarked H2 the plugin will never
    manage. Over-inclusive on purpose: reworded plugin prose lands here too, and
    the user trims; a project rule never disappears."""
    body = lines[start + 1:end]
    mask = fence_mask(body)
    keep = [False] * len(body)
    i = 0
    while i < len(body):
        if mask[i]:
            j = i
            while j < len(body) and mask[j]:
                j += 1
            if any(body[k].strip() and not blk.verbatim(body[k]) for k in range(i, j)):
                for k in range(i, j):
                    keep[k] = True
            i = j
            continue
        if HEADING_RE.match(body[i]) or (body[i].strip() and not blk.verbatim(body[i])):
            keep[i] = True
        i += 1
    out = [f'## {ctx.project} — notes rescued from "{heading_text(lines[start])}"', ""]
    prev_blank = True
    for k, line in enumerate(body):
        if keep[k]:
            if not mask[k] and HEADING_RE.match(line) and not prev_blank:
                out.append("")
            out.append(line)
            prev_blank = not line.strip()
        elif not prev_blank and not line.strip():
            out.append("")
            prev_blank = True
    while out and not out[-1].strip():
        out.pop()
    return out


KNOWN_VALUES = {"E2E_EXECUTOR": EXECUTORS, "DOMAIN_SENSITIVITY": SENSITIVITIES}


def _placeholder_refresh(sec: list[str], raw: str, ctx: Context, level: int):
    """A current-version section whose only differences from a fresh emission sit
    on the block's placeholder lines MAY have stale placeholder VALUES (the executor
    pin changed, say). Refresh only when every such old line is the template line
    with a KNOWN value in the slot — `run on: **host**`, not `run on: **host** (chosen
    for speed)`, which is the user's edit and must stay. Returns (new lines, the old
    lines replaced) or (None, reason)."""
    needed_before = set(ctx.needed)
    new = _emitted_block(raw, ctx, level)
    ctx.needed = needed_before   # only a refresh that happens may demand values
    if sec == new:
        return None, None
    if len(sec) != len(new):
        return None, "differs from a fresh emission beyond its placeholder lines"
    template = raw.rstrip("\n").split("\n")
    if level == 3:
        template = demote(template)
    template[0] = re.sub(r"<!-- emitted=\d+ -->", "", new[0])   # `new` carries provenance; the template does not
    replaced = []
    for a, b, t in zip(sec, new, template):
        if a == b:
            continue
        tokens = PLACEHOLDER_RE.findall(t)
        if not tokens:
            return None, "differs from a fresh emission on a line with no placeholder"
        pat = re.escape(t)
        for tok in tokens:
            pat = pat.replace(re.escape("{{" + tok + "}}"), "(?P<" + tok + ">.+?)", 1)
        m = re.fullmatch(pat, a)
        if not m:
            return None, f"line `{a.strip()[:60]}` is not the block's placeholder line with a value in it"
        for tok in tokens:
            if tok in KNOWN_VALUES and m.group(tok) not in KNOWN_VALUES[tok]:
                return None, f"line `{a.strip()[:60]}` carries a value this script did not write"
            if tok not in KNOWN_VALUES and m.group(tok) != ctx.sets.get(tok):
                return None, f"line `{a.strip()[:60]}` carries a {tok} value only you can vouch for"
        replaced.append(a)
    ctx.needed |= set(PLACEHOLDER_RE.findall(raw))
    return new, replaced


def apply_block(lines: list[str], blk: Block, ctx: Context, report: Report) -> list[str]:
    raw = ctx.blocks[blk.file]
    marker, cur_version, _ = _block_meta(raw)
    bt = BlockText(raw)
    name = heading_text(raw.split("\n", 1)[0])
    _DUPES.clear()
    found = _find_section(lines, marker, blk.heading)
    for m_, n_ in _DUPES:
        report.notes.append(f"more than one section carries `{m_}` ({n_} found); only the first is managed — "
                            f"delete the copy you did not write, the snapshot has both")
    wanted = blk.tracks is None or ctx.track in blk.tracks
    if found is None:
        if wanted:
            report.changes.append(f"{name}: added ({marker}-v{cur_version})")
            return _append(lines, _emitted_block(raw, ctx, 2))
        return lines
    start, level, raw_head, version = found
    if not wanted:
        report.notes.append(f"`{heading_text(raw_head)}` is a native-track section and this run's "
                            f"track is {ctx.track} — not on this track, so it is upgraded as usual but never removed; "
                            f"delete it yourself if the project stopped being native")
    end = section_end(lines, start, level)
    head_name = heading_text(raw_head)
    if version == cur_version:
        if "{{" in raw:
            refreshed, info = _placeholder_refresh(lines[start:content_end(lines, start, end)], raw, ctx, level)
            if refreshed is not None:
                report.changes.append(f"{name}: placeholder values refreshed ({marker}-v{cur_version})")
                report.removed.append({"section": head_name, "lines": info,
                                       "where": "placeholder line(s) rewritten with the current value"})
                return _splice(lines, start, content_end(lines, start, end), refreshed)
            if info:
                report.notes.append(f"`{head_name}` is at the current version but {info}; not touched — "
                                    f"edit that line by hand if the value is stale")
        report.preserved.append(f"{head_name}: already at {marker}-v{cur_version}")
        return lines
    if version is not None and version > cur_version:
        # "Different" is not "older" (2.53.3): a newer plugin wrote this section and
        # an older cache is running now. Never downgrade it.
        report.preserved.append(f"{head_name}: {marker}-v{version} is newer than this plugin's block "
                                f"(v{cur_version}); not downgraded — run /adapt from the newer plugin")
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
            return _insert_after(lines, enclosing_end(lines, start, level), _emitted_block(raw, ctx, 2))
    g = growth(lines, start, end, bt)
    if g["triggers"] and marker not in ctx.rescue:
        report.deferred.append({"marker": marker, "heading": head_name, "lines": g["lines"],
                                "block_lines": g["block_lines"], "emitted": g["emitted"],
                                "old_version": version, "triggers": g["triggers"],
                                "at_risk": g["at_risk"]})
        return lines
    new = _emitted_block(raw, ctx, level)
    was = f"{marker}-v{version}" if version is not None else "no marker"
    report.changes.append(f"{name}: {was} -> {marker}-v{cur_version}" + (" (H3 root, demoted)" if level == 3 else ""))
    if marker in ctx.rescue and g["at_risk"]:
        rescued = rescue_section(lines, start, end, bt, ctx)
        report.removed.append({"section": head_name, "lines": g["at_risk"],
                               "where": f"moved to `{rescued[0]}` — review and trim the plugin prose that travelled with them"})
        lines = _splice(lines, start, end, new)
        return _insert_after(lines, enclosing_end(lines, start, level), rescued)
    if g["at_risk"]:
        report.removed.append({"section": head_name, "lines": g["at_risk"],
                               "where": "not in the new block — old plugin prose or yours; the snapshot has every line"})
    return _splice(lines, start, end, new)


def apply_autonomy(lines: list[str], report: Report) -> list[str]:
    for i, level, raw_head in reversed(headings(lines)):
        if level not in (2, 3) or heading_text(raw_head) != AUTONOMY_HEADING:
            continue
        m = MARKER_RE.search(raw_head)
        if m and m.group(1) != AUTONOMY_MARKER:
            continue
        # the block's own subsections sat at the root's level in pre-2.36.1 emits:
        # keep walking through deeper headings and through same-level headings
        # that are the block's own; stop at the first heading that is neither
        end = len(lines)
        for j, lvl, h in headings(lines):
            if j <= i or lvl > level or (lvl == level and heading_text(h) in AUTONOMY_SUBSECTIONS):
                continue
            end = j
            break
        body = "\n".join(lines[i + 1:end])
        if m:
            version = int(m.group(2))
        elif any(s in body for s in AUTONOMY_SENTINELS):
            version = 1
        else:
            continue   # the user's own section — never touched
        size = AUTONOMY_SIZE.get(version, AUTONOMY_SIZE[1])
        e = EMITTED_RE.search(raw_head)
        emitted = int(e.group(1)) if e else None
        # an `emitted=` is a number a past run wrote; one above what the block ever
        # was is a miscount (or a forgery) and must not widen the bound
        bound = (emitted if emitted is not None and 0 < emitted <= size + PLAUSIBLE_BAND else size) + AUTONOMY_TOLERANCE
        n = content_end(lines, i, end) - i
        if n <= bound:
            report.changes.append(
                f"removed the retired `{AUTONOMY_HEADING}` section ({n} lines, marker v{version}; the snapshot has it)")
            lines = _splice(lines, i, end, [])
            while len(lines) > i > 0 and not lines[i].strip() and not lines[i - 1].strip():
                del lines[i]
        else:
            report.deferred.append({"marker": AUTONOMY_MARKER, "heading": AUTONOMY_HEADING,
                                    "lines": n, "block_lines": size, "emitted": emitted,
                                    "old_version": version, "triggers": ["retired block, grown"], "at_risk": []})
    return lines


def _managed_ranges(lines: list[str]) -> list[tuple[int, int]]:
    out = []
    for i, lvl, raw in headings(lines):
        if MARKER_RE.search(raw) or heading_text(raw).lower() == "model routing":
            out.append((i, section_end(lines, i, lvl)))
    return out


def _is_reference_line(line: str, pat: re.Pattern) -> bool:
    """A table row whose FIRST cell is the reference, or a list item that starts
    with it. Those are roster entries and go. A prose sentence that mentions the
    skill is the project's and stays."""
    s = line.strip()
    if s.startswith("|"):
        cells = [c.strip() for c in s.strip("|").split("|")]
        return bool(cells) and bool(pat.search(cells[0]))
    m = re.match(r"^[-*+]\s+`?(/\S+)", s)
    return bool(m) and bool(pat.match(m.group(1)))


def apply_renames(lines: list[str], report: Report) -> list[str]:
    mask = fence_mask(lines)
    managed = _managed_ranges(lines)
    editable = [not mask[i] and not any(a <= i < b for a, b in managed) for i in range(len(lines))]
    counts: dict[str, int] = {}
    removed_rows: list[str] = []
    kept_mentions: list[int] = []
    renamed_at: set[int] = set()
    out: list[str] = []
    removed_pat = _skill_ref(REMOVED_SKILLS)
    for i, line in enumerate(lines):
        if not editable[i]:
            out.append(line)
            continue
        if removed_pat.search(line):
            if _is_reference_line(line, removed_pat):
                removed_rows.append(line)
                continue
            kept_mentions.append(len(out) + 1)
        for olds, new in RENAMES:
            line, k = _skill_ref(olds).subn(lambda m: f"/{m.group(1) or ''}{new}", line)
            if k:
                counts[new] = counts.get(new, 0) + k
                renamed_at.add(len(out))
        out.append(line)
    lines = out
    # rows that collapsed into the same skill become one row (keep the first) —
    # only rows a rename touched THIS run, only within one table
    mask = fence_mask(lines)
    result, seen, in_table, removed_dupes = [], set(), False, []
    for i, line in enumerate(lines):
        is_row = not mask[i] and line.lstrip().startswith("|")
        if is_row and not in_table:
            in_table, seen = True, set()
        elif not is_row:
            in_table = False
        if is_row:
            key = [c.strip() for c in line.strip().strip("|").split("|")][0]
            if key in seen and i in renamed_at:
                removed_dupes.append(line)
                continue
            seen.add(key)
        result.append(line)
    for new, k in sorted(counts.items()):
        olds = next(o for o, n in RENAMES if n == new)
        report.changes.append(f"renamed `{'`/`'.join(olds)}` -> `{new}` ({k} places)")
    if removed_rows:
        report.changes.append(f"removed {len(removed_rows)} roster row(s)/list item(s) naming a retired skill")
        report.removed.append({"section": "Skill routing (retired skill rows)", "lines": removed_rows,
                               "where": "the skill no longer exists; visual exploration is routed by e2e-route"})
    if removed_dupes:
        report.changes.append(f"collapsed {len(removed_dupes)} row(s) that a rename made identical to an earlier row")
        report.removed.append({"section": "Skill routing (collapsed rows)", "lines": removed_dupes,
                               "where": "a rename made this row's skill identical to an earlier row's; the earlier row stays"})
    for n in kept_mentions:
        report.notes.append(f"line {n} mentions a retired skill in prose; kept as written — edit it by hand")
    return result


def apply_routing(lines: list[str], ctx: Context, report: Report) -> list[str]:
    if not ctx.routing:
        return lines
    if any(lvl == 2 and heading_text(raw).lower() == "skill routing" for _, lvl, raw in headings(lines)):
        report.preserved.append("Skill routing: present, kept as-is (its plugin-managed subsections are handled per block)")
        return lines
    new = ctx.routing.rstrip("\n").split("\n")
    hs = headings(lines)
    if not hs:
        at = len(lines)
    else:
        first = hs[0]
        at = next((i for i, lvl, _ in hs if i > first[0]), len(lines))
    report.changes.append("Skill routing: added")
    return _insert_after(lines, at, new)


def _model_routing_is_emitted(body_lines: list[str]) -> bool:
    if any(MODEL_ROUTING_SENTINEL in l for l in body_lines):
        return True
    for a, b in zip(body_lines, body_lines[1:]):
        if MODEL_ROUTING_HEADER_RE.match(a) and TABLE_SEPARATOR_RE.match(b):
            return True
    return False


def apply_model_routing(lines: list[str], ctx: Context, report: Report) -> list[str]:
    raw = ctx.blocks[MODEL_ROUTING_FILE]
    bt = BlockText(raw)
    found = [(i, lvl, h) for i, lvl, h in headings(lines) if lvl in (2, 3) and heading_text(h).lower() == "model routing"]
    if found:
        i, lvl, h = found[0]
        end = section_end(lines, i, lvl)
        body = lines[i + 1:end]
        if not _model_routing_is_emitted(body):
            report.preserved.append(
                "`Model Routing`: the heading is yours — it carries neither the plugin's own sentence nor a "
                "routing table with a model column, so it was left untouched and the plugin's Model Routing "
                "was not emitted. To get the plugin-managed section, rename yours and re-run `/adapt`.")
            return lines
        if not ctx.model_routing:
            return lines
        new = _resolve("\n".join(bt.lines), ctx).split("\n")
        if lines[i:content_end(lines, i, end)] == new:
            report.preserved.append("Model Routing: already current")
            return lines
        resolved = BlockText(_resolve(raw, ctx))
        at_risk = [l for l in body if l.strip() and not bt.verbatim(l) and not resolved.verbatim(l)]
        if at_risk:
            report.removed.append({"section": "Model Routing", "lines": at_risk,
                                   "where": "not in the new block — old plugin prose or yours; the snapshot has every line"})
        # delete the old section first, then place the new one where it belongs:
        # replacing an H3 in place would put an H2 inside the Skill routing subtree
        # and reparent every H3 after it
        lines = _splice(lines, i, end, [])
        report.changes.append("Model Routing: replaced the older block")
    elif not ctx.model_routing:
        return lines
    else:
        report.changes.append("Model Routing: added")
    new = _resolve("\n".join(bt.lines), ctx).split("\n")
    sr = next(((i, lvl) for i, lvl, h in headings(lines) if lvl == 2 and heading_text(h).lower() == "skill routing"), None)
    if sr is None:
        return _append(lines, new)
    return _insert_after(lines, section_end(lines, sr[0], sr[1]), new)


def merge(text: str | None, ctx: Context) -> tuple[str, Report]:
    report = Report()
    lines = text.split("\n") if text else []
    if lines and lines[-1] == "":
        lines.pop()
    if text is None:
        report.notes.append("no prior CLAUDE.md — nothing to snapshot; the file is created")
    open_at = unclosed_fence(lines)
    if open_at is not None:
        kind, at = open_at
        what = "a code fence" if kind == "fence" else "an HTML comment"
        raise Refusal(f"BLOCKED — CLAUDE.md has {what} opened at line {at} that never closes; "
                      f"everything appended below it would land inside it. Close it and re-run")
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
        for r in report.removed:
            out.append(f"- `{r['section']}`: {len(r['lines'])} line(s) — {r['where']}")
            for l in r["lines"][:12]:
                out.append(f"    | {l}")
            if len(r["lines"]) > 12:
                out.append(f"    | … and {len(r['lines']) - 12} more (all in the JSON below and in the snapshot)")
    else:
        out.append(f"- {NOTHING_REMOVED}")
    if report.deferred:
        out += ["", DEFERRED_LABEL]
        for d in report.deferred:
            was = f"marker {d['marker']}-v{d['old_version']}" if d.get("old_version") is not None else "no marker"
            prov = f", emitted={d['emitted']}" if d.get("emitted") is not None else ""
            if d["marker"] == AUTONOMY_MARKER:
                hint = ("This block is retired, so there is nothing to upgrade to: move your own lines out of "
                        "it into an unmarked section (or delete the section) and re-run.")
            else:
                hint = (f"Left at its old version. Re-run with `--rescue {d['marker']}` to move those lines into an "
                        f"unmarked section and upgrade.")
            out.append(f"- `{d['heading']}`: {d['lines']} lines against the {d['block_lines']}-line block "
                       f"({was}{prov}; fired: {', '.join(d['triggers'])}); {len(d['at_risk'])} line(s) at risk. {hint}")
    out.append("")
    if report.snapshot:
        out.append(f"**Snapshot:** `{report.snapshot}` holds CLAUDE.md exactly as it was before this run. "
                   f"Restore the whole file with `cp .gstack/CLAUDE.md.pre-adapt CLAUDE.md`."
                   + (f" The previous snapshot was rotated aside to `{report.rotated}`." if report.rotated else ""))
    elif dry_run:
        out.append("**Snapshot:** none written (dry run).")
    else:
        out.append("**Snapshot:** none — " + (report.notes[0] if report.notes else "the file was not rewritten"))
    for n in report.notes:
        out.append(f"Note: {n}")
    out.append("")
    out.append(report.as_json())
    return "\n".join(out)


# --- I/O ------------------------------------------------------------------------------

def _atomic_write(path: Path, data: bytes) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".adapt-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def snapshot(project: Path, original: bytes, report: Report) -> None:
    gstack = project / ".gstack"
    gstack.mkdir(exist_ok=True)
    snap = gstack / "CLAUDE.md.pre-adapt"
    if snap.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        rotated = gstack / f"CLAUDE.md.pre-adapt.{stamp}"
        k = 0
        while rotated.exists():
            k += 1
            rotated = gstack / f"CLAUDE.md.pre-adapt.{stamp}-{k}"
        snap.rename(rotated)
        report.rotated = str(rotated.relative_to(project))
    _atomic_write(snap, original)
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


def read_track(project: Path, override: str | None, report: Report | None = None) -> str:
    if override:
        value = override
    else:
        f = project / ".gstack" / "track"
        if not f.is_file():
            if report is not None:
                report.notes.append("no .gstack/track file — assumed web (write `ios`, `macos` or `both` there for a native project)")
            return "web"
        value = f.read_text().removesuffix("\n")
    if value not in TRACKS:
        raise Refusal(f"BLOCKED — invalid .gstack/track {value!r}: must be ios, macos, both or web")
    return value


def read_executor(project: Path) -> str | None:
    """The pin's value, None when there is no pin. Exactly `host` or `vm`; the
    file's newline is the only thing stripped, so `vm ` is refused, never repaired."""
    f = project / ".gstack" / "e2e-executor"
    if not f.is_file():
        return None
    value = f.read_text().removesuffix("\n")
    if value not in EXECUTORS:
        raise Refusal(f"BLOCKED — invalid .gstack/e2e-executor {value!r}: must be exactly host or vm")
    return value


def load_blocks(blocks_dir: Path) -> dict[str, str]:
    blocks = {}
    for blk in BLOCKS:
        f = blocks_dir / blk.file
        if not f.is_file():
            raise Refusal(f"UNREADABLE: block file {f} is missing — run `/plugin update superpowers-gstack`")
        raw = f.read_text(encoding="utf-8")
        head = raw.split("\n", 1)[0]
        m = MARKER_RE.search(head)
        if not head.startswith("## ") or not m or m.group(1) != blk.marker or raw.count("\n") < 3:
            raise Refusal(f"UNREADABLE: block file {f} is not a block — its first line must be an H2 heading "
                          f"carrying `<!-- {blk.marker}-vN -->` and it must have a body")
        blocks[blk.file] = raw
    f = blocks_dir / MODEL_ROUTING_FILE
    if not f.is_file() or not f.read_text(encoding="utf-8").startswith("## Model Routing"):
        raise Refusal(f"UNREADABLE: block file {f} is missing or does not start with `## Model Routing`")
    blocks[MODEL_ROUTING_FILE] = f.read_text(encoding="utf-8")
    return blocks


def parse_sets(items: list[str]) -> dict[str, str]:
    sets = {}
    for s in items:
        if "=" not in s:
            raise Refusal(f"USAGE ERROR: --set needs TOKEN=value, got {s!r}")
        k, v = s.split("=", 1)
        k = k.strip()
        if "\n" in v or "\r" in v:
            raise Refusal(f"BLOCKED — --set {k} carries a newline; a value is spliced into a block verbatim "
                          f"and a line break in it could forge a heading or a marker")
        if "{{" in v:
            raise Refusal(f"BLOCKED — --set {k} carries a `{{{{` placeholder; a value must be resolved, not another token")
        sets[k] = v
    if "DOMAIN_SENSITIVITY" in sets and sets["DOMAIN_SENSITIVITY"] not in SENSITIVITIES:
        raise Refusal(f"BLOCKED — DOMAIN_SENSITIVITY must be one of {', '.join(SENSITIVITIES)}")
    if "E2E_EXECUTOR" in sets and sets["E2E_EXECUTOR"] not in EXECUTORS:
        raise Refusal("BLOCKED — E2E_EXECUTOR must be exactly host or vm")
    if sets.get("DEVELOPMENT_TEAM", None) == "":
        sets["DEVELOPMENT_TEAM"] = NO_TEAM_TEXT
    return sets


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
        blocks = load_blocks(Path(a.blocks).expanduser())
        version = a.plugin_version or json.loads(PLUGIN_JSON.read_text())["version"]
        if not VERSION_RE.match(version):
            raise Refusal(f"USAGE ERROR: --plugin-version must be X.Y.Z, got {version!r} — the header the "
                          f"next run looks for would not match it")
        sets = parse_sets(a.set)
        pre_notes = Report()
        track = read_track(project, a.track, pre_notes)
        if track in NATIVE:
            # the pin is authoritative; --set may only agree with it or stand in for it
            pin = read_executor(project)
            if pin is not None and "E2E_EXECUTOR" in sets and sets["E2E_EXECUTOR"] != pin:
                raise Refusal(f"BLOCKED — --set E2E_EXECUTOR={sets['E2E_EXECUTOR']} contradicts the pin "
                              f".gstack/e2e-executor ({pin}); the pin file is the project's decision")
            sets.setdefault("E2E_EXECUTOR", pin or "host")
        else:
            sets.setdefault("E2E_EXECUTOR", "host")
        claude = project / "CLAUDE.md"
        original = claude.read_bytes() if claude.is_file() else None
        newline = "\n"
        text = None
        if original is not None:
            try:
                text = original.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise Refusal(f"UNREADABLE: CLAUDE.md is not valid UTF-8 ({exc})")
            if "\r\n" in text:
                newline = "\r\n"
                text = text.replace("\r\n", "\n")
        routing = None
        if a.routing_file:
            routing = Path(a.routing_file).expanduser().read_text(encoding="utf-8")
            first = next((l for l in routing.splitlines() if l.strip()), "")
            if not (first.lstrip().startswith("## ") and heading_text(first) == "Skill routing"):
                raise Refusal("BLOCKED — the --routing-file must start with `## Skill routing`; anything else "
                              "would be inserted again on every run")
        if a.mkdirs:
            for d in ("docs", "docs/superpowers", "docs/superpowers/specs", "docs/superpowers/plans"):
                p = project / d
                if p.exists() and not p.is_dir():
                    raise Refusal(f"BLOCKED — --mkdirs needs {d}/ to be a directory, but a file is in the way")
        ctx = Context(blocks=blocks, version=version, track=track, sets=sets, rescue=set(a.rescue),
                      routing=routing, model_routing=not a.no_model_routing,
                      project=a.project_name or project_name(text or "", project))
        new_text, report = merge(text, ctx)
        report.notes = pre_notes.notes + report.notes
        unresolved = sorted(t for t in ctx.needed if t not in sets)
        if unresolved:
            raise Refusal("UNRESOLVED PLACEHOLDER: " + ", ".join(unresolved) +
                          " — pass --set TOKEN=value for each (see skills/adapt/blocks/PLACEHOLDERS.md); nothing was written")
        if NO_TEAM_TEXT in new_text and NO_TEAM_TEXT not in (text or ""):
            report.notes.append("DEVELOPMENT_TEAM was empty: the signing example names no Team ID and says "
                                "why — stable signing requires a paid developer account")
        changed = text is None or new_text != text
        if not changed:
            report.changes = []   # every step was a no-op; the file is not rewritten
        if not a.dry_run:
            if changed and claude.is_file() and claude.read_bytes() != original:
                raise Refusal("BLOCKED — CLAUDE.md changed on disk while this run was computing; nothing was written. Re-run")
            if changed and original is not None:
                snapshot(project, original, report)
            if changed:
                _atomic_write(claude, new_text.replace("\n", newline).encode("utf-8"))
            if a.mkdirs:
                made = []
                for d in ("specs", "plans"):
                    p = project / "docs" / "superpowers" / d
                    if not (p / ".gitkeep").exists():
                        p.mkdir(parents=True, exist_ok=True)
                        (p / ".gitkeep").touch()
                        made.append(f"docs/superpowers/{d}")
                if made:
                    report.changes.append("created " + " and ".join(made))
            report.applied = True
        print(render(report, ctx, a.dry_run))
        return 0
    except Refusal as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        print(f"INTERNAL: {type(exc).__name__}: {exc} — nothing was written", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
