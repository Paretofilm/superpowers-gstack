import * as path from "node:path";
import { z } from "zod";
import { DesignDoc, Handoff, Plan, KNOWN_TYPES, type KnownType } from "./schemas.ts";
import { EXIT, die } from "./helpers/exit-codes.ts";
import { closestMatch } from "./helpers/levenshtein.ts";
import type { RawArtifact } from "./readArtifact.ts";

export type Classified =
  | { kind: "design-doc"; frontmatter: z.infer<typeof DesignDoc> }
  | { kind: "handoff"; frontmatter: z.infer<typeof Handoff> }
  | { kind: "plan"; frontmatter: z.infer<typeof Plan> }
  | { kind: "generic"; frontmatter: Record<string, unknown>; reason: string };

// Detect whether a frontmatter object looks like a legacy handoff (no `type:`
// field, but has session_end + next_step + filename === handoff.md).
function looksLikeLegacyHandoff(fm: Record<string, unknown>, filePath: string): boolean {
  if (fm.type) return false;
  const base = path.basename(filePath).toLowerCase();
  if (base !== "handoff.md") return false;
  return typeof fm.session_end === "string" && typeof fm.next_step === "string";
}

function schemaFail(kind: KnownType, err: z.ZodError, filePath: string): never {
  const issues = err.issues
    .map((i) => `  - ${i.path.join(".") || "<root>"}: ${i.message}`)
    .join("\n");
  die(
    EXIT.SCHEMA,
    `Schema validation failed for type '${kind}' in ${filePath}:\n${issues}`
  );
}

export function classify(artifact: RawArtifact): Classified {
  const { frontmatter, filePath } = artifact;

  // Legacy handoff: no `type:` but matches handoff filename + fields
  if (looksLikeLegacyHandoff(frontmatter, filePath)) {
    const r = Handoff.safeParse(frontmatter);
    if (!r.success) schemaFail("handoff", r.error, filePath);
    return { kind: "handoff", frontmatter: r.data };
  }

  const rawType = frontmatter.type;

  // No `type:` and not legacy handoff → generic
  if (typeof rawType !== "string") {
    return {
      kind: "generic",
      frontmatter,
      reason: "no `type:` field in frontmatter",
    };
  }

  // Known type → dispatch to schema
  if ((KNOWN_TYPES as readonly string[]).includes(rawType)) {
    const t = rawType as KnownType;
    if (t === "design-doc") {
      const r = DesignDoc.safeParse(frontmatter);
      if (!r.success) schemaFail(t, r.error, filePath);
      return { kind: "design-doc", frontmatter: r.data };
    }
    if (t === "handoff") {
      const r = Handoff.safeParse(frontmatter);
      if (!r.success) schemaFail(t, r.error, filePath);
      return { kind: "handoff", frontmatter: r.data };
    }
    if (t === "plan") {
      const r = Plan.safeParse(frontmatter);
      if (!r.success) schemaFail(t, r.error, filePath);
      return { kind: "plan", frontmatter: r.data };
    }
  }

  // Unknown type — typo detection (D12)
  const suggestion = closestMatch(rawType, KNOWN_TYPES as unknown as string[]);
  if (suggestion) {
    process.stderr.write(
      `Warning: unknown type '${rawType}' in ${filePath}. Did you mean '${suggestion}'?\n`
    );
  } else {
    process.stderr.write(
      `Warning: unknown type '${rawType}' in ${filePath}. Rendering as generic.\n`
    );
  }
  return {
    kind: "generic",
    frontmatter,
    reason: `unknown type '${rawType}'`,
  };
}
