import { describe, test, expect } from "bun:test";
import {
  renderComparisonMatrix,
  renderFlowchart,
  renderPullquote,
  renderCallout,
  renderStatsBar,
  renderTwoColumn,
  renderExpandable,
  renderDiffCard,
  renderTreatment,
} from "../src/render/components/index.ts";

describe("renderPullquote", () => {
  test("renders text and attribution", () => {
    const html = renderPullquote({ text: "Less is more.", attribution: "Mies" });
    expect(html).toContain("Less is more.");
    expect(html).toContain("— Mies");
    expect(html).toContain('class="pullquote"');
  });

  test("renders without attribution", () => {
    const html = renderPullquote({ text: "Hello world" });
    expect(html).toContain("Hello world");
    expect(html).not.toContain("pullquote-attribution");
  });

  test("escapes HTML in text and attribution", () => {
    const html = renderPullquote({
      text: "<script>x</script>",
      attribution: "<b>bad</b>",
    });
    expect(html).not.toContain("<script>x</script>");
    expect(html).not.toContain("<b>bad</b>");
    expect(html).toContain("&lt;script&gt;");
  });

  test("empty text returns empty string", () => {
    expect(renderPullquote({ text: "" })).toBe("");
  });
});

describe("renderCallout", () => {
  test("renders info variant by default with markdown body", () => {
    const html = renderCallout({ body: "**bold** text" });
    expect(html).toContain("callout-info");
    expect(html).toContain("<strong>bold</strong>");
    expect(html).toContain("Note");
  });

  test("renders warn level with custom title", () => {
    const html = renderCallout({ level: "warn", title: "Heads up", body: "x" });
    expect(html).toContain("callout-warn");
    expect(html).toContain("Heads up");
  });

  test("strips script tags via DOMPurify", () => {
    const html = renderCallout({ body: "ok <script>alert(1)</script>" });
    expect(html).not.toContain("<script>");
  });

  test("danger level renders with critical title default", () => {
    const html = renderCallout({ level: "danger", body: "x" });
    expect(html).toContain("callout-danger");
    expect(html).toContain("Critical");
  });

  test("empty body returns empty string", () => {
    expect(renderCallout({ body: "" })).toBe("");
  });
});

describe("renderStatsBar", () => {
  test("renders items with label, value, delta, trend", () => {
    const html = renderStatsBar({
      items: [
        { label: "Tests", value: 87, delta: "+13", trend: "up" },
        { label: "Lines", value: "725", delta: "0", trend: "flat" },
      ],
    });
    expect(html).toContain("Tests");
    expect(html).toContain("87");
    expect(html).toContain("+13");
    expect(html).toContain("stat-trend-up");
    expect(html).toContain("stat-trend-flat");
  });

  test("delta omitted when not provided", () => {
    const html = renderStatsBar({ items: [{ label: "x", value: 1 }] });
    expect(html).not.toContain("stat-delta");
  });

  test("escapes HTML in labels and values", () => {
    const html = renderStatsBar({
      items: [{ label: "<b>x</b>", value: "<i>y</i>" }],
    });
    expect(html).not.toContain("<b>x</b>");
    expect(html).toContain("&lt;b&gt;");
  });

  test("empty items returns empty string", () => {
    expect(renderStatsBar({ items: [] })).toBe("");
  });
});

describe("renderTwoColumn", () => {
  test("renders both columns with headings and markdown body", () => {
    const html = renderTwoColumn({
      left: { heading: "Before", body: "**old**" },
      right: { heading: "After", body: "**new**" },
    });
    expect(html).toContain("Before");
    expect(html).toContain("After");
    expect(html).toContain("<strong>old</strong>");
    expect(html).toContain("<strong>new</strong>");
    expect(html).toContain('class="two-column"');
  });

  test("renders without headings", () => {
    const html = renderTwoColumn({
      left: { body: "a" },
      right: { body: "b" },
    });
    expect(html).not.toContain("col-heading");
  });

  test("strips scripts in column bodies", () => {
    const html = renderTwoColumn({
      left: { body: "<script>x</script>" },
      right: { body: "ok" },
    });
    expect(html).not.toContain("<script>");
  });

  test("missing left or right returns empty string", () => {
    // @ts-expect-error testing runtime guard
    expect(renderTwoColumn({ left: { body: "x" } })).toBe("");
  });
});

describe("renderExpandable", () => {
  test("renders summary + body with details element", () => {
    const html = renderExpandable({ summary: "Click me", body: "hidden" });
    expect(html).toContain("<details");
    expect(html).toContain("<summary>Click me</summary>");
    expect(html).toContain("hidden");
  });

  test("open=true adds open attribute", () => {
    const html = renderExpandable({ summary: "x", body: "y", open: true });
    expect(html).toContain('<details class="expandable" open>');
  });

  test("escapes summary; sanitizes body", () => {
    const html = renderExpandable({
      summary: "<script>x</script>",
      body: "ok <script>bad()</script>",
    });
    expect(html).not.toContain("<script>x</script>");
    expect(html).not.toContain("<script>bad()</script>");
    expect(html).toContain("&lt;script&gt;");
  });

  test("missing summary returns empty string", () => {
    expect(renderExpandable({ summary: "", body: "x" })).toBe("");
  });
});

describe("renderComparisonMatrix", () => {
  test("renders multiple items with pros/cons/meta", () => {
    const html = renderComparisonMatrix({
      items: [
        {
          title: "Option A",
          summary: "Fast",
          pros: ["Cheap", "Fast"],
          cons: ["Risky"],
          effort: "1 day",
          risk: "low",
        },
        {
          title: "Option B",
          pros: ["Safe"],
          cons: ["Slow"],
          highlighted: true,
        },
      ],
    });
    expect(html).toContain("Option A");
    expect(html).toContain("Option B");
    expect(html).toContain("Cheap");
    expect(html).toContain("Risky");
    expect(html).toContain("1 day");
    expect(html).toContain("comparison-card-highlighted");
    expect(html).toContain("Recommended");
  });

  test("optional fields omitted gracefully", () => {
    const html = renderComparisonMatrix({
      items: [{ title: "Only title" }],
    });
    expect(html).toContain("Only title");
    expect(html).not.toContain("<h4>Pros</h4>");
    expect(html).not.toContain("comparison-meta");
  });

  test("escapes HTML in titles, pros, summary", () => {
    const html = renderComparisonMatrix({
      items: [
        {
          title: "<script>x</script>",
          summary: "<b>y</b>",
          pros: ["<i>p</i>"],
        },
      ],
    });
    expect(html).not.toContain("<script>x</script>");
    expect(html).not.toContain("<b>y</b>");
    expect(html).not.toContain("<i>p</i>");
  });

  test("empty items returns empty string", () => {
    expect(renderComparisonMatrix({ items: [] })).toBe("");
  });
});

describe("renderDiffCard", () => {
  test("renders before/after with default labels", () => {
    const html = renderDiffCard({
      before: { content: "old code" },
      after: { content: "new code" },
    });
    expect(html).toContain("Before");
    expect(html).toContain("After");
    expect(html).toContain("old code");
    expect(html).toContain("new code");
    expect(html).toContain("diff-card");
  });

  test("custom labels and title", () => {
    const html = renderDiffCard({
      title: "Refactor",
      before: { label: "Was", content: "x" },
      after: { label: "Is", content: "y" },
    });
    expect(html).toContain("Refactor");
    expect(html).toContain("Was");
    expect(html).toContain("Is");
  });

  test("escapes HTML in content", () => {
    const html = renderDiffCard({
      before: { content: "<script>x</script>" },
      after: { content: "<b>y</b>" },
    });
    expect(html).not.toContain("<script>x</script>");
    expect(html).not.toContain("<b>y</b>");
    expect(html).toContain("&lt;script&gt;");
  });

  test("missing before or after returns empty string", () => {
    // @ts-expect-error testing runtime guard
    expect(renderDiffCard({ before: { content: "x" } })).toBe("");
  });
});

describe("renderFlowchart", () => {
  test("renders SVG with nodes and edges", () => {
    const html = renderFlowchart({
      nodes: [
        { id: "a", label: "Start" },
        { id: "b", label: "End", emphasis: true },
      ],
      edges: [{ from: "a", to: "b", label: "go" }],
    });
    expect(html).toContain("<svg");
    expect(html).toContain("Start");
    expect(html).toContain("End");
    expect(html).toContain("go");
    expect(html).toContain('class="flowchart"');
    expect(html).toContain("flowchart-node-emphasis");
  });

  test("ignores edges referencing unknown nodes", () => {
    const html = renderFlowchart({
      nodes: [{ id: "a", label: "A" }],
      edges: [
        { from: "a", to: "missing" },
        { from: "ghost", to: "a" },
      ],
    });
    expect(html).toContain("<svg");
    expect(html).toContain("A");
    // No arrow path should be rendered
    expect(html).not.toContain("<polygon");
  });

  test("escapes labels", () => {
    const html = renderFlowchart({
      nodes: [{ id: "a", label: "<script>x</script>" }],
      edges: [],
    });
    expect(html).not.toContain("<script>x</script>");
    expect(html).toContain("&lt;script&gt;");
  });

  test("empty nodes returns empty string", () => {
    expect(renderFlowchart({ nodes: [], edges: [] })).toBe("");
  });
});

describe("renderTreatment dispatch", () => {
  test("dispatches each known treatment to the right renderer", () => {
    const pq = renderTreatment("pullquote", { text: "hi" });
    expect(pq).toContain("pullquote");

    const cb = renderTreatment("callout-box", { body: "hi" });
    expect(cb).toContain("callout");

    const sb = renderTreatment("stats-bar", { items: [{ label: "x", value: 1 }] });
    expect(sb).toContain("stats-bar");

    const tc = renderTreatment("two-column", {
      left: { body: "a" },
      right: { body: "b" },
    });
    expect(tc).toContain("two-column");

    const exp = renderTreatment("expandable", { summary: "s", body: "b" });
    expect(exp).toContain("expandable");

    const dc = renderTreatment("diff-card", {
      before: { content: "a" },
      after: { content: "b" },
    });
    expect(dc).toContain("diff-card");

    const cm = renderTreatment("comparison-matrix", { items: [{ title: "x" }] });
    expect(cm).toContain("comparison-matrix");

    const fc = renderTreatment("flowchart-svg", {
      nodes: [{ id: "a", label: "x" }],
      edges: [],
    });
    expect(fc).toContain("<svg");
  });

  test("section-card returns null (default path)", () => {
    expect(renderTreatment("section-card", {})).toBeNull();
  });
});
