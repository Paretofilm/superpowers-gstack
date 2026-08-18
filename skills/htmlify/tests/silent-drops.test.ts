import { describe, test, expect } from "bun:test";
import { renderGeneric } from "../src/render/generic.ts";
import { renderPlannedSections } from "../src/helpers/planWiring.ts";
import { tokenize } from "../src/helpers/markdown.ts";

// Regression tests for #52 — two defects that both failed in the "looks finished"
// direction: exit 0, valid HTML, no stderr, content silently missing. In a review
// flow where the feedback panel IS the mechanism for user input, a silently dropped
// panel means the review looks complete while the user was never shown the form.

describe("#52 bug 2 — body H2s outside the plan must not vanish", () => {
  const body = [
    "## Planned One", "in plan",
    "## Unlisted Two", "not in the plan but in the document",
    "## Unlisted Three", "also not in the plan",
  ].join("\n\n");

  test("headings absent from both canonical and plan are still rendered", () => {
    const html = renderPlannedSections({
      tokens: tokenize(body),
      canonical: [],
      plan: { sections: [{ heading: "Planned One", treatment: "section-card" }] } as any,
    });
    expect(html).toContain("Planned One");
    // Before the fix these two were dropped with no warning and exit 0.
    expect(html).toContain("Unlisted Two");
    expect(html).toContain("Unlisted Three");
  });

  test("a heading is never rendered twice when it appears in the plan", () => {
    const html = renderPlannedSections({
      tokens: tokenize("## Only One\n\nbody"),
      canonical: [],
      plan: { sections: [{ heading: "Only One", treatment: "section-card" }] } as any,
    });
    expect(html.split("Only One").length - 1).toBe(1);
  });

  test("no plan at all still renders the document's own headings", () => {
    const html = renderPlannedSections({ tokens: tokenize(body), canonical: [], plan: null });
    expect(html).toContain("Unlisted Two");
  });
});

describe("#52 bug 1 — a plan reaching the generic renderer must not be silent", () => {
  const base = { frontmatter: {}, body: "## X\n\nbody", mdPath: "a.md", cssHref: "c.css" };

  test("the feedback panel renders even without recognized frontmatter", () => {
    const html = renderGeneric({
      ...base,
      plan: {
        feedback_panel: {
          enabled: true,
          premises: ["Premise under review"],
          approaches: [],
          custom_questions: [],
        },
      } as any,
    });
    // The panel is the piece whose absence broke the review flow.
    expect(html).toContain("Premise under review");
  });

  test("plan features generic cannot honour are reported, not dropped in silence", () => {
    const seen: string[] = [];
    const orig = process.stderr.write;
    (process.stderr as any).write = (c: any) => { seen.push(String(c)); return true; };
    try {
      renderGeneric({ ...base, plan: { sections: [{ heading: "X", treatment: "section-card" }] } as any });
    } finally {
      (process.stderr as any).write = orig;
    }
    const msg = seen.join("");
    expect(msg).toContain("generic");
    expect(msg).toContain("section treatment");
  });

  test("no plan means no warning — silence is correct when nothing was dropped", () => {
    const seen: string[] = [];
    const orig = process.stderr.write;
    (process.stderr as any).write = (c: any) => { seen.push(String(c)); return true; };
    try {
      renderGeneric({ ...base, plan: null });
    } finally {
      (process.stderr as any).write = orig;
    }
    expect(seen.join("")).toBe("");
  });
});
