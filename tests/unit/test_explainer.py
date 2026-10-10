"""htmlify explain mode (3.10.0): the reminder hook, explain-check's file rules, and the
shipped example page.

The layout half of explain-check needs a real browser and is not run here; it was
verified by hand against the example, a reference page and a page with planted defects
(see the CHANGELOG entry).
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "scripts" / "explainer-nudge.py"
HTMLIFY = REPO / "skills" / "htmlify"
EXAMPLE = HTMLIFY / "examples" / "explainer-example.html"
CSS = HTMLIFY / "styles" / "explainer.css"


def load_check():
    loader = importlib.machinery.SourceFileLoader("explain_check", str(HTMLIFY / "bin" / "explain-check"))
    spec = importlib.util.spec_from_loader("explain_check", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


check = load_check()


# ── the reminder hook ────────────────────────────────────────────────────────

def project(tmp_path: Path, target: str | None = None) -> Path:
    root = tmp_path / "proj"
    (root / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (root / "docs" / "superpowers" / "plans").mkdir(parents=True)
    if target is not None:
        (root / ".gstack").mkdir()
        (root / ".gstack" / "explainer").write_text(target + "\n")
    return root


def hook(tmp_path: Path, file_path, session="s1", cwd=None, raw=None):
    payload = raw if raw is not None else json.dumps({
        "session_id": session, "cwd": str(cwd or tmp_path), "tool_name": "Write",
        "tool_input": {"file_path": str(file_path)}})
    env = dict(os.environ, TMPDIR=str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir(exist_ok=True)
    p = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True,
                       text=True, env=env, timeout=10)
    assert p.returncode == 0 and p.stderr == "", p.stderr
    if not p.stdout.strip():
        return None
    out = json.loads(p.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    return out["hookSpecificOutput"]["additionalContext"]


def touch(p: Path, text="x", later=0.0):
    p.write_text(text)
    t = time.time() + later
    os.utime(p, (t, t))


def test_a_new_spec_gets_one_reminder_per_draft(tmp_path):
    root = project(tmp_path)
    spec = root / "docs/superpowers/specs/2026-10-10-x-design.md"
    touch(spec)
    msg = hook(tmp_path, spec, cwd=root)
    assert "/superpowers-gstack:htmlify explain docs/superpowers/specs/2026-10-10-x-design.md" in msg
    assert "the spec" in msg and "has no explainer page yet" in msg and "local" in msg
    touch(spec, "edited in self-review")
    assert hook(tmp_path, spec) is None, "no explainer written since the reminder: stay quiet"


def test_an_up_to_date_explainer_silences_it_and_a_stale_one_earns_one_more(tmp_path):
    root = project(tmp_path)
    spec = root / "docs/superpowers/specs/a-design.md"
    touch(spec)
    assert hook(tmp_path, spec)
    html = spec.with_suffix(".html")
    touch(html, "<html>", later=5)
    assert hook(tmp_path, spec) is None, "explainer newer than the spec"
    touch(spec, "changed again", later=10)
    msg = hook(tmp_path, spec)
    assert msg and "is newer than its explainer page" in msg
    assert hook(tmp_path, spec) is None


def test_plans_are_covered_and_progress_and_other_files_are_not(tmp_path):
    root = project(tmp_path)
    plan = root / "docs/superpowers/plans/2026-10-10-x.md"
    touch(plan)
    assert "the plan" in hook(tmp_path, plan)
    for other in ("docs/superpowers/plans/progress.md", "docs/superpowers/specs/.hidden.md",
                  "docs/superpowers/specs/notes.txt", "docs/superpowers/handoff.md",
                  "docs/superpowers/vibe/2026-10-10-x/SPEC.md", "specs/a.md", "README.md"):
        f = root / other
        f.parent.mkdir(parents=True, exist_ok=True)
        touch(f)
        assert hook(tmp_path, f) is None, other


def test_artifact_target_reminds_once_per_document_per_session(tmp_path):
    root = project(tmp_path, target="artifact")
    spec = root / "docs/superpowers/specs/a-design.md"
    touch(spec)
    msg = hook(tmp_path, spec)
    assert "as an Artifact page" in msg and "artifact" in msg
    touch(spec, "edit", later=5)
    assert hook(tmp_path, spec) is None
    assert hook(tmp_path, spec, session="s2"), "a new session is reminded again"


def test_relative_paths_resolve_against_cwd_and_bad_input_is_silent(tmp_path):
    root = project(tmp_path)
    spec = root / "docs/superpowers/specs/a-design.md"
    touch(spec)
    assert hook(tmp_path, "docs/superpowers/specs/a-design.md", cwd=root)
    assert hook(tmp_path, None, raw="not json") is None
    assert hook(tmp_path, None, raw=json.dumps({"tool_input": {}})) is None
    missing = root / "docs/superpowers/specs/gone-design.md"
    assert hook(tmp_path, missing) is None


def test_state_is_private_and_week_old_sessions_are_dropped(tmp_path):
    root = project(tmp_path)
    spec = root / "docs/superpowers/specs/a-design.md"
    touch(spec)
    state_dir = tmp_path / "tmp" / "superpowers-gstack-explainer"
    state_dir.mkdir(parents=True)
    old = state_dir / "old-session.json"
    old.write_text("{}")
    week = time.time() - 8 * 86400
    os.utime(old, (week, week))
    assert hook(tmp_path, spec, session="fresh")
    assert not old.exists()
    mine = state_dir / "fresh.json"
    assert mine.is_file() and (mine.stat().st_mode & 0o077) == 0, "readable by the user only"


def test_the_pin_is_found_above_a_docs_folder_in_a_subproject(tmp_path):
    repo = tmp_path / "proj"
    (repo / ".git").mkdir(parents=True)
    (repo / ".gstack").mkdir()
    (repo / ".gstack" / "explainer").write_text("artifact\n")
    spec = repo / "app" / "docs/superpowers/specs/a-design.md"
    spec.parent.mkdir(parents=True)
    touch(spec)
    assert "as an Artifact page" in hook(tmp_path, spec)
    # ... but never from above the repository root
    outer = tmp_path / ".gstack"
    outer.mkdir()
    (outer / "explainer").write_text("artifact\n")
    (repo / ".gstack" / "explainer").unlink()
    spec2 = repo / "docs/superpowers/specs/b-design.md"
    spec2.parent.mkdir(parents=True)
    touch(spec2)
    assert "(`.gstack/explainer`: local)" in hook(tmp_path, spec2)


def test_an_invalid_pin_falls_back_to_local(tmp_path):
    root = project(tmp_path, target="sometimes")
    spec = root / "docs/superpowers/specs/a-design.md"
    touch(spec)
    assert "(`.gstack/explainer`: local)" in hook(tmp_path, spec)


def test_the_plugin_registers_the_hook_on_writes():
    hooks = json.loads((REPO / "hooks" / "hooks.json").read_text())["hooks"]["PostToolUse"]
    cmds = [(h["matcher"], c["command"]) for h in hooks for c in h["hooks"]]
    assert ("Write|Edit|MultiEdit", "${CLAUDE_PLUGIN_ROOT}/scripts/explainer-nudge.py") in cmds
    assert os.access(HOOK, os.X_OK)


# ── explain-check: the file rules ────────────────────────────────────────────

def page(body: str, css: str | None = None) -> str:
    style = CSS.read_text() if css is None else css
    return f"<!doctype html><html><head><style>{style}</style></head><body>{body}</body></html>"


CARD = ('<section class="glass"><span class="tag t-cyan">Del 1</span><h2>Tittel</h2>'
        '<svg viewBox="0 0 10 10" role="img" aria-label="tegning"></svg>'
        '<div class="key">💡 Én innsikt.</div></section>')


def kinds(html: str):
    f, w = check.rule_findings(html)
    return [x["kind"] for x in f], [x["detail"] for x in w]


def test_a_well_formed_card_is_clean():
    assert kinds(page(CARD)) == ([], [])


def test_the_style_must_be_explainer_css_with_comments_and_whitespace_free():
    css = CSS.read_text()
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert kinds(page(CARD, "\n".join(l.strip() for l in stripped.splitlines())))[0] == []
    assert kinds(page(CARD, css.replace("--cyan:#0891b2", "--cyan:#00ffff")))[0] == ["style-drift"]
    assert kinds("<html><body>" + CARD + "</body></html>")[0] == ["style-missing"]


def test_companion_css_and_linked_stylesheets_are_refused():
    html = page(CARD).replace("</head>", '<link rel="stylesheet" href="companion.css"></head>')
    assert set(kinds(html)[0]) == {"companion", "external-style"}


def test_every_card_starts_with_its_badge_and_has_at_most_one_insight():
    no_badge = CARD.replace('<span class="tag t-cyan">Del 1</span>', "")
    assert kinds(page(no_badge))[0] == ["no-badge"]
    text_first = CARD.replace('<section class="glass">', '<section class="glass">Løs tekst ')
    assert kinds(page(text_first))[0] == ["no-badge"]
    two = CARD.replace("</section>", '<div class="key">💡 En til.</div></section>')
    assert kinds(page(two))[0] == ["two-insights"]


def test_every_svg_is_labelled():
    assert kinds(page(CARD.replace(' aria-label="tegning"', "")))[0] == ["svg-label"]
    assert kinds(page(CARD.replace(' role="img"', "")))[0] == ["svg-label"]


def test_internal_identifiers_outside_code_are_warnings():
    body = CARD.replace("<h2>Tittel</h2>",
                        "<h2>Steg T3.2 og FR-12 i a1b2c3d</h2><p>kaller fetch_invoices og parseRow</p>"
                        "<p>på iPhone og macOS</p><p><code>bibliotek varsel_send --dag</code></p>"
                        '<p class="mono">deadBeef42</p>')
    findings, warnings = kinds(page(body))
    assert findings == []
    joined = " ".join(warnings)
    for word in ("T3.2", "FR-12", "a1b2c3d", "fetch_invoices", "parseRow"):
        assert word in joined, word
    for word in ("iPhone", "macOS", "varsel_send", "deadBeef42"):
        assert word not in joined, word


# ── the shipped example ──────────────────────────────────────────────────────

def test_the_example_passes_the_rules_with_no_warnings():
    assert kinds(EXAMPLE.read_text()) == ([], [])


def test_the_example_carries_every_part_the_skill_names():
    html = EXAMPLE.read_text()
    assert 'id="tg"' in html and "data-theme" in html, "theme button"
    assert html.count('<section class="glass">') >= 8
    for cls in ("big", "bars", "chip", "key", "who", "done", "scroll", "g2", "g3"):
        assert f'class="{cls}' in html or f' {cls}"' in html or f'"{cls} ' in html, cls
    assert html.count('role="img"') >= 5


def test_the_example_holds_no_kvitteriai_content():
    """The style came from a real project's page; its content must not have."""
    html = EXAMPLE.read_text().lower()
    for word in ("kvitteri", "fakturahenting", "amazonaws", "aws", "openai", "chatgpt", "starlink",
                 "fyndiq", "biltema", "pareto", "skunkworks", "bankrad", "hentet.json"):
        assert word not in html, word
