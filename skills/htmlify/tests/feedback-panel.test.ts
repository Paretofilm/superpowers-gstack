import { describe, test, expect } from "bun:test";
import { renderFeedbackPanel } from "../src/render/components/feedback-panel.ts";
import { renderDesignDoc } from "../src/render/designDoc.ts";
import type { DesignDocFM, Plan } from "../src/schemas.ts";

const CSS = "../styles/companion.css";

describe("renderFeedbackPanel", () => {
  test("renders premises checkboxes, approach radios, comment textarea", () => {
    const html = renderFeedbackPanel({
      enabled: true,
      premises: ["P1", "P2"],
      approaches: ["A1", "A2"],
      custom_questions: [],
    });
    expect(html).toContain('class="feedback-panel"');
    expect(html).toContain("Premises that need more thought");
    expect(html).toContain('value="P1"');
    expect(html).toContain('value="P2"');
    expect(html).toContain('type="checkbox"');
    expect(html).toContain('type="radio"');
    expect(html).toContain("I'd actually pick this approach");
    expect(html).toContain('<textarea');
    expect(html).toContain("Comment (always included)");
    expect(html).toContain("Copy feedback as prompt");
  });

  test("custom questions: checkbox/radio/text", () => {
    const html = renderFeedbackPanel({
      enabled: true,
      premises: [],
      approaches: [],
      custom_questions: [
        { id: "q1", label: "Try this?", type: "checkbox", options: ["yes", "no"] },
        { id: "q2", label: "Pick one", type: "radio", options: ["a", "b"] },
        { id: "q3", label: "Free form", type: "text" },
      ],
    });
    expect(html).toContain("Try this?");
    expect(html).toContain("Pick one");
    expect(html).toContain("Free form");
    expect(html).toContain('data-fb-question="q1"');
    expect(html).toContain('data-fb-question="q2"');
    expect(html).toContain('data-fb-question="q3"');
    expect(html).toContain('id="fb-q-q3"');
  });

  test("enabled=false returns empty", () => {
    expect(
      renderFeedbackPanel({
        enabled: false,
        premises: ["P1"],
        approaches: [],
        custom_questions: [],
      })
    ).toBe("");
  });

  test("escapes HTML in premise / approach IDs", () => {
    const html = renderFeedbackPanel({
      enabled: true,
      premises: ["<script>x</script>"],
      approaches: ["<b>y</b>"],
      custom_questions: [],
    });
    expect(html).not.toContain("<script>x</script>");
    expect(html).not.toContain("<b>y</b>");
    expect(html).toContain("&lt;script&gt;");
  });

  test("contains inline clipboard script with gather() function", () => {
    const html = renderFeedbackPanel({
      enabled: true,
      premises: ["P1"],
      approaches: [],
      custom_questions: [],
    });
    expect(html).toContain("<script>");
    expect(html).toContain("navigator.clipboard");
    expect(html).toContain("JSON.stringify");
    expect(html).toContain("fb-fallback");
  });

  test("includes fallback <pre> for clipboard-unavailable browsers", () => {
    const html = renderFeedbackPanel({
      enabled: true,
      premises: [],
      approaches: [],
      custom_questions: [],
    });
    expect(html).toContain('class="fb-fallback"');
    expect(html).toContain("hidden");
  });

  test("renders even when all fields empty (still has comment)", () => {
    const html = renderFeedbackPanel({
      enabled: true,
      premises: [],
      approaches: [],
      custom_questions: [],
    });
    expect(html).toContain("feedback-panel");
    expect(html).toContain("<textarea");
    // No premise/approach fieldsets
    expect(html).not.toContain("Premises that need more thought");
    expect(html).not.toContain("I'd actually pick this approach");
  });
});

describe("renderDesignDoc — feedback panel integration", () => {
  const fm: DesignDocFM = {
    type: "design-doc",
    title: "FB test",
    status: "DRAFT",
    mode: "builder",
  };

  test("feedback panel appears below <main>", () => {
    const plan: Plan = {
      version: 1,
      sections: [],
      pullquotes: [],
      feedback_panel: {
        enabled: true,
        premises: ["P1"],
        approaches: ["A1"],
        custom_questions: [],
      },
    };
    const html = renderDesignDoc({
      frontmatter: fm,
      body: "## Problem Statement\nx",
      mdPath: "x.md",
      cssHref: CSS,
      plan,
    });
    const idxMainClose = html.indexOf("</main>");
    const idxPanel = html.indexOf('class="feedback-panel"');
    const idxFooter = html.indexOf("companion-footer");
    expect(idxPanel).toBeGreaterThan(idxMainClose);
    expect(idxPanel).toBeLessThan(idxFooter);
  });

  test("absent feedback_panel produces no panel", () => {
    const html = renderDesignDoc({
      frontmatter: fm,
      body: "## Problem Statement\nx",
      mdPath: "x.md",
      cssHref: CSS,
      plan: { version: 1, sections: [], pullquotes: [] },
    });
    expect(html).not.toContain("feedback-panel");
  });
});
