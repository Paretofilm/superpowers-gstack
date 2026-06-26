from test_smoke import load
report = load("report")

ENV = {"platform": "ios", "udid": "ABC-123", "bundle_id": "com.x.app"}
LOG = [{"step": 1, "action": "tap", "intent": "tap continue", "coord": "(195,400)", "result": "success",
        "produced_by_steps": [1]}]
FINDINGS = [{"severity": "P2", "text": "knapp avkuttet", "screenshot": "shot_001.png"}]


def test_markdown_contains_sections():
    md = report.build_markdown("utforsk onboarding", ENV, LOG, FINDINGS, "fullført")
    assert "utforsk onboarding" in md
    assert "ABC-123" in md
    assert "knapp avkuttet" in md
    assert "shot_001.png" in md
    assert "fullført" in md


def test_text_summary_has_no_inline_images():
    s = report.text_summary(FINDINGS, "/p/report.md", "/p/shots")
    assert "![" not in s              # ingen inline-bilde-markdown
    assert "/p/report.md" in s        # filsti ja
    assert "knapp avkuttet" in s


def test_text_summary_neutralizes_inline_image_in_finding_text():
    adversarial = [{"severity": "P1", "text": "see ![shot](x.png) here", "screenshot": "s.png"}]
    s = report.text_summary(adversarial, "/p/report.md", "/p/shots")
    assert "![" not in s
    assert "see !\\[shot](x.png) here" in s


def test_text_summary_coerces_non_string_fields():
    """Regression: Gemini may emit screenshot as int instead of string."""
    findings = [{"severity": "P1", "text": "broken layout", "screenshot": 2}]
    s = report.text_summary(findings, "/p/report.md", "/p/shots")
    assert "broken layout" in s
    assert "2" in s
    # Ensure no crash and proper formatting
    assert s.startswith("Visuell utforsking ferdig")


def test_build_markdown_coerces_non_string_fields():
    """Regression: handle int/None values in finding dict gracefully."""
    findings = [
        {"severity": "P0", "text": "crash on launch", "screenshot": 1},
        {"severity": None, "text": 123, "screenshot": None},
    ]
    md = report.build_markdown("test mission", {"platform": "ios", "udid": "x", "bundle_id": "y"}, [], findings, "failed")
    assert "crash on launch" in md
    assert "1" in md
    assert "123" in md  # int coerced to str
