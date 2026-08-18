import { describe, test, expect } from "bun:test";
import {
  renderFlowchart, wrapLabel, estimateTextWidth, effectiveFontPx,
  type FlowchartData,
} from "../src/render/components/flowchart-svg.ts";

// Regression tests for #53. The agent that authors a plan never sees the rendered
// output, so the quality gate cannot live in SKILL.md prose — it has to be in the
// tool. Measured before the fix: an 8-node TB chain rendered node text at ~6px,
// with labels spilling outside their boxes, exit 0, nothing on stderr.

function chain(n: number, label = (i: number) => `Step ${i}`): FlowchartData {
  return {
    nodes: Array.from({ length: n }, (_, i) => ({ id: `n${i}`, label: label(i) })),
    edges: Array.from({ length: n - 1 }, (_, i) => ({ from: `n${i}`, to: `n${i + 1}` })),
    orientation: "TB",
  };
}

function captureStderr(fn: () => void): string {
  const seen: string[] = [];
  const orig = process.stderr.write;
  (process.stderr as any).write = (c: any) => { seen.push(String(c)); return true; };
  try { fn(); } finally { (process.stderr as any).write = orig; }
  return seen.join("");
}

describe("label wrapping — text outside a node must be impossible, not unlikely", () => {
  const BOX = 165 - 24;   // NODE_WIDTH minus horizontal padding

  test("a long label wraps instead of overflowing", () => {
    const lines = wrapLabel("PreviewDiscoverer + fabrikk-bro xcrun swiftc emit-library", BOX, 15.5);
    expect(lines.length).toBeGreaterThan(1);
    for (const ln of lines) expect(estimateTextWidth(ln, 15.5)).toBeLessThanOrEqual(BOX);
  });

  test("a single unsplittable word is clipped, never allowed to overflow", () => {
    const lines = wrapLabel("Supercalifragilisticexpialidociousextravaganza", BOX, 15.5);
    expect(lines).toHaveLength(1);
    expect(estimateTextWidth(lines[0], 15.5)).toBeLessThanOrEqual(BOX);
    expect(lines[0]).toContain("…");
  });

  test("a short label is left exactly as written", () => {
    expect(wrapLabel("Build", BOX, 15.5)).toEqual(["Build"]);
  });

  test("wrapping is bounded — a wall of text cannot grow the node forever", () => {
    const lines = wrapLabel("word ".repeat(60).trim(), BOX, 15.5);
    expect(lines.length).toBeLessThanOrEqual(3);
  });
});

describe("readability gate — stop downscaling below the readable floor", () => {
  test("effective font tracks the height clamp", () => {
    expect(effectiveFontPx(200)).toBeCloseTo(15.5, 1);   // under the clamp, untouched
    expect(effectiveFontPx(900)).toBeLessThan(11);        // the #53 case
  });

  test("a long chain renders unclamped and says so", () => {
    let html = "";
    const err = captureStderr(() => { html = renderFlowchart(chain(8)); });
    expect(html).toContain("flowchart-unclamped");
    expect(err).toContain("readable floor");
  });

  test("a small diagram is untouched and silent", () => {
    let html = "";
    const err = captureStderr(() => { html = renderFlowchart(chain(3)); });
    expect(html).not.toContain("flowchart-unclamped");
    expect(err).toBe("");
  });

  test("node labels are emitted as tspans, so multi-line is real", () => {
    const html = renderFlowchart({
      nodes: [{ id: "a", label: "A very long node label that must wrap onto lines" }],
      edges: [],
    });
    expect(html).toContain("<tspan");
  });
});
