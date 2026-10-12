#!/usr/bin/env python3
"""Build docs/manual/manual.html from the chapters and figures.

    python3 scripts/build-manual.py            write docs/manual/manual.html
    python3 scripts/build-manual.py --check    exit 1 if the file is not what a build gives now

Standard library only. Deterministic: the same chapters and figures give the same bytes
(sorted globs, LF line endings, no clock). The page follows the htmlify explainer
contract (the first <style> is skills/htmlify/styles/explainer.css verbatim, every chapter
is one card that starts with a .tag badge and holds at most one .key) so that
skills/htmlify/bin/explain-check runs on it unchanged.

Chapter format: a frontmatter block (nummer, tag, tittel, aksent, bruk, ferdig; chapter 0
also oppdatert), then a body that uses only: ### headings, paragraphs, - lists, 1. lists,
| tables |, ``` code fences, ![[name.svg]] on its own line, and at most one > blockquote
(it becomes the card's one .key). Raw HTML is never passed through.
"""
import argparse
import html
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANUAL_DIR = REPO / "docs" / "manual"
EXPLAINER_CSS = REPO / "skills" / "htmlify" / "styles" / "explainer.css"
ACCENTS = ("cyan", "violet", "magenta", "amber", "emerald")
REQUIRED = ("nummer", "tag", "tittel", "aksent", "bruk", "ferdig")
FIGURE_LINE = re.compile(r"^!\[\[([A-Za-z0-9_.-]+\.svg)\]\]\s*$")
HEX_COLOUR = re.compile(r'(?:fill|stroke|stop-color|color)\s*[=:]\s*"?#[0-9a-fA-F]{3,8}')
SVG_ID = re.compile(r'\bid="([^"]+)"')


class ManualError(Exception):
    """Something in the manual's sources is wrong; the message names the file."""


@dataclass
class Chapter:
    nummer: int
    slug: str
    tag: str
    tittel: str
    aksent: str
    bruk: str
    ferdig: str
    body: str
    meta: dict = field(default_factory=dict)


def parse_chapter(path: Path) -> Chapter:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.match(r"---\n(.*?)\n---\n(.*)\Z", text, re.S)
    if not m:
        raise ManualError(f"{path.name}: no frontmatter block")
    meta: dict = {}
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ManualError(f"{path.name}: frontmatter line without a colon: {line!r}")
        meta[key.strip()] = value.strip()
    missing = [k for k in REQUIRED if not meta.get(k)]
    if missing:
        raise ManualError(f"{path.name}: frontmatter lacks {', '.join(missing)}")
    if not meta["nummer"].isdigit():
        raise ManualError(f"{path.name}: nummer {meta['nummer']!r} is not a number")
    if meta["aksent"] not in ACCENTS:
        raise ManualError(f"{path.name}: aksent {meta['aksent']!r} is not one of {', '.join(ACCENTS)}")
    number = re.match(r"(\d\d)-", path.name)
    if not number or int(meta["nummer"]) != int(number.group(1)):
        raise ManualError(f"{path.name}: nummer {meta['nummer']} does not match the file name")
    return Chapter(int(meta["nummer"]), path.stem, meta["tag"], meta["tittel"], meta["aksent"],
                   meta["bruk"], meta["ferdig"], m.group(2).strip("\n"), meta)


def inline(text: str) -> str:
    """Escape HTML, then apply `code`, **bold** and [text](url). Code spans are protected."""
    out = []
    for part in re.split(r"(`[^`]+`)", text):
        if len(part) > 1 and part.startswith("`") and part.endswith("`"):
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        p = html.escape(part, quote=False)
        p = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", p)
        p = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                   lambda m: f'<a href="{m.group(2).replace(chr(34), "%22")}">{m.group(1)}</a>', p)
        out.append(p)
    return "".join(out)


def load_figure(figures: Path, name: str, where: str) -> str:
    path = figures / name
    if not path.is_file():
        raise ManualError(f"{where}: figure {name} does not exist in {figures.name}/")
    svg = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    if not svg.startswith("<svg"):
        raise ManualError(f"{name}: a figure file must start with <svg")
    opening = svg.split(">", 1)[0]
    if 'role="img"' not in opening or "aria-label=" not in opening:
        raise ManualError(f'{name}: the <svg> needs role="img" and an aria-label')
    if "viewBox=" not in opening:
        raise ManualError(f"{name}: the <svg> needs a viewBox")
    if HEX_COLOUR.search(svg):
        raise ManualError(f"{name}: a hex colour in the drawing; use the tokens (var(--cyan), …) so the dark theme works")
    return svg


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def render_table(rows: list[str], where: str) -> str:
    if len(rows) < 2 or not re.fullmatch(r"\|?[\s:|-]+\|?", rows[1]):
        raise ManualError(f"{where}: a table needs a header row and a --- separator row")
    head = _cells(rows[0])
    body_rows = [_cells(r) for r in rows[2:]]
    for r in body_rows:
        if len(r) != len(head):
            raise ManualError(f"{where}: a table row has {len(r)} cells, the header has {len(head)}")
    th = "".join(f"<th>{inline(c)}</th>" for c in head)
    trs = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body_rows)
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


def render_body(body: str, figures: Path, where: str) -> tuple[str, int]:
    out: list[str] = []
    para: list[str] = []
    keys = 0
    lines = body.split("\n")
    i = 0

    def flush() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            flush()
            i += 1
            code: list[str] = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            if i >= len(lines):
                raise ManualError(f"{where}: unclosed code fence")
            out.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
            i += 1
            continue
        fig = FIGURE_LINE.match(line)
        if fig:
            flush()
            out.append(f'<div class="scroll">{load_figure(figures, fig.group(1), where)}</div>')
        elif line.startswith("### "):
            flush()
            out.append(f"<h3>{inline(line[4:].strip())}</h3>")
        elif line.startswith("#"):
            raise ManualError(f"{where}: only ### headings are allowed in a chapter (the title is in the frontmatter)")
        elif line.startswith("|"):
            flush()
            rows: list[str] = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(render_table(rows, where))
            continue
        elif line.startswith(">"):
            flush()
            quote: list[str] = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].strip())
                i += 1
            keys += 1
            out.append(f'<div class="key">{inline(" ".join(quote))}</div>')
            continue
        elif line.startswith("- ") or re.match(r"\d+\. ", line):
            flush()
            ordered = not line.startswith("- ")
            pat = r"\d+\. " if ordered else r"- "
            items: list[str] = []
            while i < len(lines) and re.match(pat, lines[i]):
                items.append(re.sub(pat, "", lines[i], count=1))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        elif not line.strip():
            flush()
        else:
            para.append(line.strip())
        i += 1
    flush()
    if keys > 1:
        raise ManualError(f"{where}: {keys} blockquotes; a card has at most one .key (one insight)")
    return "\n".join(out), keys
