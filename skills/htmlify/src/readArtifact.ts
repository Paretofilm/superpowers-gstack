import * as fs from "node:fs";
import matter from "gray-matter";
import { EXIT, die } from "./helpers/exit-codes.ts";

export interface RawArtifact {
  frontmatter: Record<string, unknown>;
  body: string;
  filePath: string;
}

export function readArtifact(filePath: string): RawArtifact {
  let raw: string;
  try {
    raw = fs.readFileSync(filePath, "utf8");
  } catch (err: any) {
    if (err && err.code === "ENOENT") {
      die(EXIT.IO, `File not found: ${filePath}`);
    }
    if (err && err.code === "EACCES") {
      die(EXIT.IO, `Permission denied: ${filePath}`);
    }
    die(EXIT.IO, `Read failed: ${filePath} — ${err?.message ?? err}`);
  }

  let parsed: matter.GrayMatterFile<string>;
  try {
    parsed = matter(raw);
  } catch (err: any) {
    die(
      EXIT.PARSE,
      `Malformed YAML frontmatter in ${filePath}: ${err?.message ?? err}`
    );
  }

  return {
    frontmatter: normalizeDates(parsed.data ?? {}) as Record<string, unknown>,
    body: parsed.content,
    filePath,
  };
}

// YAML parsers convert ISO-8601 timestamps to Date objects. Our schemas
// expect strings (the frontmatter contract is text-based). Walk the parsed
// object and coerce Dates back to ISO strings.
function normalizeDates(value: unknown): unknown {
  if (value instanceof Date) return value.toISOString();
  if (Array.isArray(value)) return value.map(normalizeDates);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = normalizeDates(v);
    }
    return out;
  }
  return value;
}
