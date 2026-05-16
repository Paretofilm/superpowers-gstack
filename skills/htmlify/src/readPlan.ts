import * as fs from "node:fs";
import { PlanSchema, type Plan } from "./schemas.ts";
import { EXIT, die } from "./helpers/exit-codes.ts";

// Load and validate a rendering plan from disk.
// On any error, returns null + writes warning to stderr — the caller falls
// back to v1 template rendering (graceful degradation per design E2).
export function readPlan(planPath: string): Plan | null {
  let raw: string;
  try {
    raw = fs.readFileSync(planPath, "utf8");
  } catch (err: any) {
    process.stderr.write(
      `Warning: could not read plan ${planPath}: ${err?.message ?? err}\n` +
        `Falling back to template rendering.\n`
    );
    return null;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err: any) {
    process.stderr.write(
      `Warning: plan ${planPath} is not valid JSON: ${err?.message ?? err}\n` +
        `Falling back to template rendering.\n`
    );
    return null;
  }

  const result = PlanSchema.safeParse(parsed);
  if (!result.success) {
    const issues = result.error.issues
      .map((i) => `  - ${i.path.join(".") || "<root>"}: ${i.message}`)
      .join("\n");
    process.stderr.write(
      `Warning: plan ${planPath} failed schema validation:\n${issues}\n` +
        `Falling back to template rendering.\n`
    );
    return null;
  }

  return result.data;
}
