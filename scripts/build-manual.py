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
HEX_COLOUR = re.compile(r"(?<!url\()(?<![\w&])#[0-9a-fA-F]{3,8}\b")
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
    for element in ("style", "script"):
        if re.search(rf"<{element}\b", svg, re.I):
            raise ManualError(f"{name}: a <{element}> element in a figure; it would act on the whole page. Use the tokens in attributes")
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
        elif line.startswith("- ") or re.match(r"\d+\. ", line) and (not para or line.startswith("1. ")):
            flush()
            ordered = not line.startswith("- ")
            pat = r"\d+\. " if ordered else r"- "
            start = int(line.split(".", 1)[0]) if ordered else 1
            items: list[str] = []
            while i < len(lines) and re.match(pat, lines[i]):
                items.append(re.sub(pat, "", lines[i], count=1))
                i += 1
            if i < len(lines) and lines[i][:1] in (" ", "\t") and lines[i].strip():
                raise ManualError(f"{where}: list items are one line each; {lines[i].strip()[:40]!r} continues the item above")
            tag = "ol" if ordered else "ul"
            attr = f' start="{start}"' if start != 1 else ""
            out.append(f"<{tag}{attr}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
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


THEME_SCRIPT = """<script>
(function(){
  var root=document.documentElement,btn=document.getElementById('tg');
  try{var s=localStorage.getItem('manual-tema');if(s)root.setAttribute('data-theme',s);}catch(e){}
  btn.addEventListener('click',function(){
    var cur=root.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
    var next=cur==='dark'?'light':'dark';root.setAttribute('data-theme',next);
    try{localStorage.setItem('manual-tema',next);}catch(e){}
  });
})();
</script>"""


def render_chapter(ch: Chapter, figures: Path) -> str:
    body_html, _ = render_body(ch.body, figures, f"{ch.slug}.md")
    return f"""<section class="glass" id="k{ch.nummer}">
  <span class="tag t-{ch.aksent}">{html.escape(ch.tag)}</span>
  <h2>{ch.nummer}&nbsp; {html.escape(ch.tittel)}</h2>
  <div class="grid g2 bruk">
    <div class="chip"><span class="ic">🎯</span><div><b>Bruk denne når</b><span>{inline(ch.bruk)}</span></div></div>
    <div class="chip"><span class="ic">🏁</span><div><b>Du er ferdig når</b><span>{inline(ch.ferdig)}</span></div></div>
  </div>
{body_html}
</section>"""


def render_page(chapters: list[Chapter], figures: Path, css: str, manual_css: str) -> str:
    cards = "\n\n".join(render_chapter(c, figures) for c in chapters)
    toc = "".join(f'<li><a href="#k{c.nummer}"><b>{c.nummer}</b> {html.escape(c.tittel)}</a></li>' for c in chapters)
    updated = chapters[0].meta.get("oppdatert", "")
    stamp = f" · oppdatert {html.escape(updated)}" if updated else ""
    return f"""<!doctype html>
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Manual for superpowers-gstack</title>
<style>
{css.rstrip(chr(10))}
</style>
<style>
{manual_css.rstrip(chr(10))}
</style>
</head>
<body>
<div class="wrap">

<div class="top">
  <div>
    <span class="tag t-violet">Manual{stamp}</span>
    <h1>Superpowers + gstack</h1>
    <p class="sub">Slik bygger du apper med Claude Code uten å miste tråden.</p>
  </div>
  <button class="toggle" id="tg" aria-label="Bytt mellom lyst og mørkt">◐ Tema</button>
</div>

<div class="layout">
<nav aria-label="Innhold">
<section class="glass" id="innhold">
  <span class="tag t-violet">Innhold</span>
  <ol class="toc">{toc}</ol>
</section>
</nav>

<main>
{cards}
</main>
</div>

<footer>Bygget fra <code>docs/manual/</code> med <code>python3 scripts/build-manual.py</code></footer>
</div>
{THEME_SCRIPT}
</body>
</html>
"""


def build(manual_dir: Path = MANUAL_DIR, css_path: Path = EXPLAINER_CSS) -> str:
    files = sorted(manual_dir.glob("[0-9][0-9]-*.md"))
    if not files:
        raise ManualError(f"{manual_dir}: no chapters (NN-name.md)")
    chapters = [parse_chapter(f) for f in files]
    numbers = [c.nummer for c in chapters]
    if numbers != list(range(len(numbers))):
        raise ManualError(f"chapter numbers must run 0..{len(numbers) - 1} with no gaps or repeats, got {numbers}")
    css_file = manual_dir / "manual.css"
    if not css_file.is_file():
        raise ManualError(f"{manual_dir.name}/manual.css is missing")
    page = render_page(chapters, manual_dir / "figurer", css_path.read_text(encoding="utf-8"),
                       css_file.read_text(encoding="utf-8"))
    dup = sorted(k for k, n in Counter(SVG_ID.findall(page)).items() if n > 1)
    if dup:
        raise ManualError(f"duplicate id {', '.join(dup)} in the page; marker ids must be unique across figures")
    return page


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build docs/manual/manual.html from the chapters and figures.")
    ap.add_argument("--check", action="store_true", help="exit 1 if manual.html is not what a build gives now")
    ap.add_argument("--dir", type=Path, default=MANUAL_DIR, help="the manual directory (default docs/manual)")
    args = ap.parse_args(argv)
    try:
        page = build(args.dir)
    except ManualError as exc:
        print(f"build-manual: {exc}", file=sys.stderr)
        return 1
    target = args.dir / "manual.html"
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != page:
            print("build-manual: manual.html is not what a build gives now; run `python3 scripts/build-manual.py`",
                  file=sys.stderr)
            return 1
        print("manual.html is current")
        return 0
    target.write_text(page, encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
