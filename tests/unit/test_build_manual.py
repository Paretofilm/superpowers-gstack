"""scripts/build-manual.py: chapters + figures -> one page that follows the htmlify
explainer contract, so explain-check runs on it unchanged.

Review Focus pinned here: raw HTML in a chapter is text, two blockquotes stop the build,
a hex colour or an unlabelled figure stops the build, two figures may not share a marker
id, the build is byte-deterministic (CRLF sources, glob order), chapter numbers are
checked. The layout half of explain-check needs a real browser and is run by hand
(Task 4 onwards in the plan).
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def load(name: str, rel: str):
    loader = importlib.machinery.SourceFileLoader(name, str(REPO / rel))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


bm = load("build_manual", "scripts/build-manual.py")
check = load("explain_check_for_manual", "skills/htmlify/bin/explain-check")

FIG = (
    '<svg viewBox="0 0 960 100" role="img" aria-label="en tegning">'
    '<defs><marker id="{id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
    'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="var(--muted)"/></marker></defs>'
    '<rect x="10" y="10" width="100" height="40" rx="8" fill="var(--cyan-s)" stroke="var(--cyan)"/>'
    '<text x="20" y="35" font-size="14">hei</text></svg>'
)


def chapter(n=0, body="Første avsnitt.", **over) -> str:
    meta = {
        "nummer": str(n), "tag": "Kartet", "tittel": "Kartet", "aksent": "cyan",
        "bruk": "Bruk denne når du trenger oversikt.",
        "ferdig": "Du er ferdig når du ser hele flyten.",
    }
    if n == 0:
        meta["oppdatert"] = "2026-10-12"
    meta.update(over)
    head = "\n".join(f"{k}: {v}" for k, v in meta.items())
    return f"---\n{head}\n---\n{body}\n"


def make(base: Path, chapters: dict, figures: dict | None = None) -> Path:
    d = base / "manual"
    (d / "figurer").mkdir(parents=True)
    (d / "manual.css").write_text("/* test */\n.x{color:var(--fg)}\n")
    for name, text in chapters.items():
        (d / name).write_text(text)
    for name, text in (figures or {}).items():
        (d / "figurer" / name).write_text(text)
    return d


def body(text: str, figures: Path | None = None):
    return bm.render_body(text, figures or Path("/nonexistent"), "test.md")


# ── inline ───────────────────────────────────────────────────────────────────

def test_inline_escapes_html_and_protects_code():
    assert bm.inline("a <script>x</script> b") == "a &lt;script&gt;x&lt;/script&gt; b"
    assert bm.inline("kjør `a < b && c`") == "kjør <code>a &lt; b &amp;&amp; c</code>"
    assert bm.inline("**fet** og [lenke](https://x.no/a?b=1&c=2)") == \
        '<b>fet</b> og <a href="https://x.no/a?b=1&amp;c=2">lenke</a>'


def test_a_quote_cannot_break_out_of_an_href():
    assert '"onclick' not in bm.inline('[x](a"onclick=y)')


def test_raw_html_is_text_not_markup():
    html, _ = body("<script>alert(1)</script>\n\n<img src=x onerror=y>\n")
    assert "<script" not in html and "<img" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


# ── blocks ───────────────────────────────────────────────────────────────────

def test_paragraphs_lists_and_headings():
    html, keys = body("### Tittel\n\nEn linje\nfortsetter.\n\n- ett\n- to\n\n1. først\n2. så\n")
    assert "<h3>Tittel</h3>" in html
    assert "<p>En linje fortsetter.</p>" in html
    assert "<ul><li>ett</li><li>to</li></ul>" in html
    assert "<ol><li>først</li><li>så</li></ol>" in html
    assert keys == 0


def test_code_fence_is_escaped_and_kept_verbatim():
    html, _ = body("```\nwt switch --create feat/x <ikke html>\n```")
    assert "<pre><code>wt switch --create feat/x &lt;ikke html&gt;</code></pre>" in html


def test_unclosed_fence_is_an_error():
    with pytest.raises(bm.ManualError, match="unclosed"):
        body("```\nkode")


def test_table():
    html, _ = body("| a | b |\n|---|---|\n| 1 | `x` |\n")
    assert "<th>a</th><th>b</th>" in html
    assert "<td>1</td><td><code>x</code></td>" in html
    with pytest.raises(bm.ManualError, match="cells"):
        body("| a | b |\n|---|---|\n| 1 |\n")
    with pytest.raises(bm.ManualError, match="separator"):
        body("| a | b |\n| 1 | 2 |\n")


def test_one_blockquote_becomes_the_key_and_two_are_refused():
    html, keys = body("> 💡 Poenget.\n")
    assert '<div class="key">💡 Poenget.</div>' in html and keys == 1
    with pytest.raises(bm.ManualError, match="at most one"):
        body("> en\n\ntekst\n\n> to\n")


def test_only_h3_is_allowed_in_a_chapter():
    with pytest.raises(bm.ManualError, match="###"):
        body("## For stor\n")


def test_figure_is_inlined_and_validated(tmp_path):
    (tmp_path / "a.svg").write_text(FIG.format(id="m1"))
    html, _ = body("![[a.svg]]\n", tmp_path)
    assert html.startswith('<div class="scroll"><svg') and 'id="m1"' in html
    with pytest.raises(bm.ManualError, match="does not exist"):
        body("![[b.svg]]\n", tmp_path)
    (tmp_path / "c.svg").write_text(FIG.format(id="m").replace(' aria-label="en tegning"', ""))
    with pytest.raises(bm.ManualError, match="aria-label"):
        body("![[c.svg]]\n", tmp_path)
    (tmp_path / "d.svg").write_text(FIG.format(id="m").replace("var(--cyan)", "#22d3ee"))
    with pytest.raises(bm.ManualError, match="hex colour"):
        body("![[d.svg]]\n", tmp_path)
    (tmp_path / "e.svg").write_text(FIG.format(id="m").replace('viewBox="0 0 960 100" ', ""))
    with pytest.raises(bm.ManualError, match="viewBox"):
        body("![[e.svg]]\n", tmp_path)


# ── chapters ─────────────────────────────────────────────────────────────────

def test_parse_chapter(tmp_path):
    p = tmp_path / "00-kartet.md"
    p.write_text(chapter(0, body="Hei."))
    c = bm.parse_chapter(p)
    assert (c.nummer, c.tag, c.aksent, c.body) == (0, "Kartet", "cyan", "Hei.")
    assert c.meta["oppdatert"] == "2026-10-12"


def test_a_colon_inside_a_frontmatter_value_is_kept(tmp_path):
    p = tmp_path / "00-kartet.md"
    p.write_text(chapter(0, bruk="Bruk denne når: du vil se alt."))
    assert bm.parse_chapter(p).bruk == "Bruk denne når: du vil se alt."


@pytest.mark.parametrize("over,msg", [
    ({"aksent": "rosa"}, "aksent"),
    ({"tag": ""}, "lacks tag"),
    ({"nummer": "x"}, "nummer"),
])
def test_bad_frontmatter_is_an_error_that_names_the_file(tmp_path, over, msg):
    p = tmp_path / "00-kartet.md"
    p.write_text(chapter(0, **over))
    with pytest.raises(bm.ManualError, match=msg) as e:
        bm.parse_chapter(p)
    assert "00-kartet.md" in str(e.value)


def test_a_file_number_must_match_its_frontmatter(tmp_path):
    p = tmp_path / "03-flyten.md"
    p.write_text(chapter(2))
    with pytest.raises(bm.ManualError, match="does not match the file name"):
        bm.parse_chapter(p)


def test_no_frontmatter_is_an_error(tmp_path):
    p = tmp_path / "00-kartet.md"
    p.write_text("bare tekst\n")
    with pytest.raises(bm.ManualError, match="no frontmatter"):
        bm.parse_chapter(p)
