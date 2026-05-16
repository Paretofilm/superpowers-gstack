import { describe, test, expect } from "bun:test";
import { renderDesignDoc } from "../src/render/designDoc.ts";
import type { DesignDocFM, Plan } from "../src/schemas.ts";

const CSS = "../styles/companion.css";

const fm: DesignDocFM = {
  type: "design-doc",
  title: "Plan wiring",
  status: "DRAFT",
  mode: "builder",
};

describe("renderDesignDoc — plan wiring", () => {
  test("plan-driven comparison-matrix replaces default card body", () => {
    const plan: Plan = {
      version: 1,
      sections: [
        {
          heading: "Approaches Considered",
          treatment: "comparison-matrix",
          data: {
            items: [
              { title: "A", pros: ["fast"], cons: ["risky"] },
              { title: "B", pros: ["safe"], cons: ["slow"], highlighted: true },
            ],
          },
        },
      ],
      pullquotes: [],
    };
    const html = renderDesignDoc({
      frontmatter: fm,
      body: "## Approaches Considered\n- A: see plan\n- B: see plan",
      mdPath: "x.md",
      cssHref: CSS,
      plan,
    });
    expect(html).toContain("comparison-matrix");
    expect(html).toContain("Approaches Considered");
    expect(html).toContain("Recommended");
    // MD body bullets should NOT appear when treatment overrides
    expect(html).not.toContain("<li>A: see plan</li>");
  });

  test("pullquote after_section is placed below the matching section", () => {
    const plan: Plan = {
      version: 1,
      sections: [],
      pullquotes: [
        {
          text: "Less is more.",
          attribution: "Mies",
          after_section: "Problem Statement",
        },
      ],
    };
    const html = renderDesignDoc({
      frontmatter: fm,
      body: "## Problem Statement\nReal.\n\n## Premises\n- P1",
      mdPath: "x.md",
      cssHref: CSS,
      plan,
    });
    const idxSection = html.indexOf("Problem Statement");
    const idxQuote = html.indexOf("Less is more.");
    const idxPremises = html.indexOf("Premises");
    expect(idxQuote).toBeGreaterThan(idxSection);
    expect(idxQuote).toBeLessThan(idxPremises);
  });

  test("plan section with treatment=section-card uses default rendering", () => {
    const plan: Plan = {
      version: 1,
      sections: [
        { heading: "Problem Statement", treatment: "section-card" },
      ],
      pullquotes: [],
    };
    const html = renderDesignDoc({
      frontmatter: fm,
      body: "## Problem Statement\nDefault please.",
      mdPath: "x.md",
      cssHref: CSS,
      plan,
    });
    expect(html).toContain("Default please.");
    expect(html).not.toContain("card-component");
  });

  test("plan introduces a new heading not in SECTION_CARDS", () => {
    const plan: Plan = {
      version: 1,
      sections: [
        {
          heading: "Custom Visualisation",
          treatment: "callout-box",
          data: { level: "insight", body: "**bold thought**" },
        },
      ],
      pullquotes: [],
    };
    const html = renderDesignDoc({
      frontmatter: fm,
      body: "## Problem Statement\nx",
      mdPath: "x.md",
      cssHref: CSS,
      plan,
    });
    expect(html).toContain("Custom Visualisation");
    expect(html).toContain("callout-insight");
    expect(html).toContain("<strong>bold thought</strong>");
  });

  test("no plan → behaves identically to v1 (default cards)", () => {
    const html = renderDesignDoc({
      frontmatter: fm,
      body: "## Problem Statement\nClassic.",
      mdPath: "x.md",
      cssHref: CSS,
    });
    expect(html).toContain("Problem Statement");
    expect(html).toContain("Classic.");
    expect(html).not.toContain("card-component");
  });

  test("plan heading is case/whitespace-tolerant", () => {
    const plan: Plan = {
      version: 1,
      sections: [
        {
          heading: "  problem STATEMENT  ",
          treatment: "callout-box",
          data: { body: "matched" },
        },
      ],
      pullquotes: [],
    };
    const html = renderDesignDoc({
      frontmatter: fm,
      body: "## Problem Statement\nmd body",
      mdPath: "x.md",
      cssHref: CSS,
      plan,
    });
    expect(html).toContain("callout");
    expect(html).toContain("matched");
  });

  test("malformed plan data falls back to default card render", () => {
    const plan: Plan = {
      version: 1,
      sections: [
        {
          heading: "Approaches Considered",
          treatment: "comparison-matrix",
          // wrong shape — items should be an array of objects
          data: { items: "this is not an array" } as any,
        },
      ],
      pullquotes: [],
    };
    // Should not throw, should fall back to default card with the MD body.
    const html = renderDesignDoc({
      frontmatter: fm,
      body: "## Approaches Considered\n- A: see plan\n- B: see plan",
      mdPath: "x.md",
      cssHref: CSS,
      plan,
    });
    expect(html).toContain("Approaches Considered");
    // Default card rendering preserves MD body
    expect(html).toContain("A: see plan");
    expect(html).not.toContain("card-component");
  });

  test("flowchart-svg treatment renders inline SVG", () => {
    const plan: Plan = {
      version: 1,
      sections: [
        {
          heading: "Engineering Decisions",
          treatment: "flowchart-svg",
          data: {
            nodes: [
              { id: "a", label: "Step 1" },
              { id: "b", label: "Step 2", emphasis: true },
            ],
            edges: [{ from: "a", to: "b" }],
          },
        },
      ],
      pullquotes: [],
    };
    const html = renderDesignDoc({
      frontmatter: fm,
      body: "## Engineering Decisions\nsee diagram",
      mdPath: "x.md",
      cssHref: CSS,
      plan,
    });
    expect(html).toContain("<svg");
    expect(html).toContain("Step 1");
    expect(html).toContain("Step 2");
  });
});
