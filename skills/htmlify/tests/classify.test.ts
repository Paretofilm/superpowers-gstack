import { describe, test, expect, beforeEach, afterEach } from "bun:test";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import { readArtifact } from "../src/readArtifact.ts";
import { classify } from "../src/classifyArtifact.ts";

let TMP: string;

beforeEach(() => {
  TMP = fs.mkdtempSync(path.join(os.tmpdir(), "htmlify-classify-"));
});
afterEach(() => {
  fs.rmSync(TMP, { recursive: true, force: true });
});

function write(name: string, content: string): string {
  const p = path.join(TMP, name);
  fs.writeFileSync(p, content);
  return p;
}

describe("classify", () => {
  test("type: design-doc with required title → design-doc", () => {
    const p = write(
      "doc.md",
      `---
type: design-doc
title: "Hello"
status: DRAFT
---

# Hello
`
    );
    const r = classify(readArtifact(p));
    expect(r.kind).toBe("design-doc");
    if (r.kind === "design-doc") {
      expect(r.frontmatter.title).toBe("Hello");
    }
  });

  test("type: handoff with required fields → handoff", () => {
    const p = write(
      "h.md",
      `---
type: handoff
session_end: 2026-05-15T16:30:00+02:00
next_step: Do X
completed: [a-1]
remaining: [a-2]
---
`
    );
    const r = classify(readArtifact(p));
    expect(r.kind).toBe("handoff");
  });

  test("legacy handoff (filename + fields, no type:) → handoff", () => {
    const p = write(
      "handoff.md",
      `---
session_end: 2026-05-15T16:30:00+02:00
next_step: Do X
---
`
    );
    const r = classify(readArtifact(p));
    expect(r.kind).toBe("handoff");
  });

  test("legacy-style fields but wrong filename → generic (no type:)", () => {
    const p = write(
      "something.md",
      `---
session_end: 2026-05-15T16:30:00+02:00
next_step: Do X
---
`
    );
    const r = classify(readArtifact(p));
    expect(r.kind).toBe("generic");
  });

  test("type: plan with phases → plan", () => {
    const p = write(
      "plan.md",
      `---
type: plan
title: My plan
phases:
  - id: p1
    name: Setup
    status: pending
---
`
    );
    const r = classify(readArtifact(p));
    expect(r.kind).toBe("plan");
  });

  test("no frontmatter → generic", () => {
    const p = write("plain.md", `# Hello\n\nNo frontmatter here.`);
    const r = classify(readArtifact(p));
    expect(r.kind).toBe("generic");
  });

  test("unknown type → generic with warning", () => {
    const p = write(
      "u.md",
      `---
type: review
title: x
---
`
    );
    const r = classify(readArtifact(p));
    expect(r.kind).toBe("generic");
  });

  test("typo on type → generic + stderr warning suggests correction", () => {
    const p = write(
      "t.md",
      `---
type: design_doc
title: x
---
`
    );
    // Capture stderr
    const orig = process.stderr.write.bind(process.stderr);
    let captured = "";
    (process.stderr as any).write = (chunk: any) => {
      captured += chunk;
      return true;
    };
    try {
      const r = classify(readArtifact(p));
      expect(r.kind).toBe("generic");
    } finally {
      (process.stderr as any).write = orig;
    }
    expect(captured).toContain("design_doc");
    expect(captured).toContain("design-doc");
  });

  test("DesignDoc missing required title → exit 2", () => {
    const p = write(
      "bad.md",
      `---
type: design-doc
---
`
    );
    // classify calls die() on schema fail. die() calls process.exit().
    // Spy on exit to assert without actually exiting the test runner.
    const origExit = process.exit;
    let exitCode: number | null = null;
    (process.exit as any) = (c: number) => {
      exitCode = c;
      throw new Error("EXIT_INTERCEPT");
    };
    const origStderr = process.stderr.write.bind(process.stderr);
    let captured = "";
    (process.stderr as any).write = (chunk: any) => {
      captured += chunk;
      return true;
    };
    try {
      try {
        classify(readArtifact(p));
      } catch (e: any) {
        if (e.message !== "EXIT_INTERCEPT") throw e;
      }
    } finally {
      (process.exit as any) = origExit;
      (process.stderr as any).write = origStderr;
    }
    expect(exitCode).toBe(2);
    expect(captured).toContain("Schema validation failed");
  });
});
