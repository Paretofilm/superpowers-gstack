import { describe, test, expect, beforeEach, afterEach } from "bun:test";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import { readPlan } from "../src/readPlan.ts";
import { PlanSchema } from "../src/schemas.ts";

let TMP: string;

beforeEach(() => {
  TMP = fs.mkdtempSync(path.join(os.tmpdir(), "htmlify-plan-"));
});
afterEach(() => {
  fs.rmSync(TMP, { recursive: true, force: true });
});

function writeJson(name: string, obj: unknown): string {
  const p = path.join(TMP, name);
  fs.writeFileSync(p, JSON.stringify(obj));
  return p;
}

describe("PlanSchema", () => {
  test("minimal valid plan parses", () => {
    const r = PlanSchema.safeParse({ version: 1 });
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.sections).toEqual([]);
      expect(r.data.pullquotes).toEqual([]);
    }
  });

  test("rejects missing version", () => {
    const r = PlanSchema.safeParse({});
    expect(r.success).toBe(false);
  });

  test("rejects wrong version", () => {
    const r = PlanSchema.safeParse({ version: 2 });
    expect(r.success).toBe(false);
  });

  test("accepts known treatments", () => {
    const r = PlanSchema.safeParse({
      version: 1,
      sections: [
        { heading: "Approaches", treatment: "comparison-matrix" },
        { heading: "Architecture", treatment: "flowchart-svg" },
        { heading: "Notes", treatment: "callout-box" },
      ],
    });
    expect(r.success).toBe(true);
  });

  test("rejects unknown treatment", () => {
    const r = PlanSchema.safeParse({
      version: 1,
      sections: [{ heading: "X", treatment: "magic-render" }],
    });
    expect(r.success).toBe(false);
  });

  test("passthrough preserves unknown fields", () => {
    const r = PlanSchema.safeParse({
      version: 1,
      mystery_field: "preserved",
    });
    expect(r.success).toBe(true);
    if (r.success) {
      expect((r.data as any).mystery_field).toBe("preserved");
    }
  });

  test("pullquote with attribution and placement", () => {
    const r = PlanSchema.safeParse({
      version: 1,
      pullquotes: [
        { text: "Move fast", attribution: "Anon", after_section: "Problem Statement" },
      ],
    });
    expect(r.success).toBe(true);
  });

  test("feedback_panel with premises, approaches, custom_questions", () => {
    const r = PlanSchema.safeParse({
      version: 1,
      feedback_panel: {
        premises: ["P1", "P2"],
        approaches: ["A", "B"],
        custom_questions: [
          { id: "q1", label: "Need more detail?", type: "checkbox" },
          { id: "q2", label: "Pick a tone", type: "radio", options: ["formal", "casual"] },
        ],
      },
    });
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.feedback_panel?.enabled).toBe(true);  // default
      expect(r.data.feedback_panel?.premises).toEqual(["P1", "P2"]);
    }
  });
});

describe("readPlan", () => {
  test("loads valid plan from disk", () => {
    const p = writeJson("plan.json", {
      version: 1,
      sections: [{ heading: "X", treatment: "section-card" }],
    });
    const result = readPlan(p);
    expect(result).not.toBeNull();
    expect(result?.sections.length).toBe(1);
  });

  test("returns null + stderr warning on missing file", () => {
    const orig = process.stderr.write.bind(process.stderr);
    let captured = "";
    (process.stderr as any).write = (chunk: any) => {
      captured += chunk;
      return true;
    };
    try {
      const result = readPlan(path.join(TMP, "nonexistent.json"));
      expect(result).toBeNull();
    } finally {
      (process.stderr as any).write = orig;
    }
    expect(captured).toContain("could not read plan");
    expect(captured).toContain("Falling back to template rendering");
  });

  test("returns null + warning on malformed JSON", () => {
    const p = path.join(TMP, "bad.json");
    fs.writeFileSync(p, "{not valid json");
    const orig = process.stderr.write.bind(process.stderr);
    let captured = "";
    (process.stderr as any).write = (chunk: any) => {
      captured += chunk;
      return true;
    };
    try {
      const result = readPlan(p);
      expect(result).toBeNull();
    } finally {
      (process.stderr as any).write = orig;
    }
    expect(captured).toContain("not valid JSON");
  });

  test("returns null + warning on schema mismatch", () => {
    const p = writeJson("wrong.json", { version: 99 });
    const orig = process.stderr.write.bind(process.stderr);
    let captured = "";
    (process.stderr as any).write = (chunk: any) => {
      captured += chunk;
      return true;
    };
    try {
      const result = readPlan(p);
      expect(result).toBeNull();
    } finally {
      (process.stderr as any).write = orig;
    }
    expect(captured).toContain("schema validation");
  });

  test("graceful degradation: no crash, just stderr + null", () => {
    // Invalid in every way
    const p = writeJson("crap.json", { version: 1, sections: "not an array" });
    const result = readPlan(p);
    expect(result).toBeNull();
  });
});
