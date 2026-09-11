import * as fs from "node:fs";
import * as path from "node:path";
import { pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";
import { EXIT, die } from "./helpers/exit-codes.ts";

export const OUTPUT_DIR = ".superpowers-html";

export interface WriteOpts {
  noClobber?: boolean;
  forceRebuild?: boolean;
}

export interface WriteResult {
  outPath: string;
  written: boolean;
  reason: "wrote" | "skipped-newer" | "skipped-no-clobber";
}

export function companionPathFor(mdPath: string): string {
  const dir = path.dirname(path.resolve(mdPath));
  const base = path.basename(mdPath, ".md");
  return path.join(dir, OUTPUT_DIR, `${base}.html`);
}

export function ensureGitignore(outDir: string): void {
  // Walk up from outDir to find a git repo root (where .git/ lives).
  // If found, append `.superpowers-html/` to .gitignore unless already present.
  // If no git repo found, silently skip.
  let dir = path.resolve(outDir);
  while (dir !== path.dirname(dir)) {
    const gitDir = path.join(dir, ".git");
    if (fs.existsSync(gitDir)) {
      const giPath = path.join(dir, ".gitignore");
      let existing = "";
      try {
        existing = fs.readFileSync(giPath, "utf8");
      } catch {
        // file does not exist yet — that's fine
      }
      const lines = existing.split("\n").map((l) => l.trim());
      if (lines.includes(`${OUTPUT_DIR}/`) || lines.includes(OUTPUT_DIR)) {
        return; // already present
      }
      const prefix = existing.length > 0 && !existing.endsWith("\n") ? "\n" : "";
      try {
        fs.appendFileSync(giPath, `${prefix}${OUTPUT_DIR}/\n`);
      } catch {
        // non-fatal: gitignore append failed (read-only fs etc.) — just warn
        process.stderr.write(
          `Warning: could not append to ${giPath}; add '${OUTPUT_DIR}/' manually.\n`
        );
      }
      return;
    }
    dir = path.dirname(dir);
  }
  // No git repo found — skip silently
}

export function writeCompanion(
  mdPath: string,
  html: string,
  opts: WriteOpts = {}
): WriteResult {
  const outPath = companionPathFor(mdPath);
  const outDir = path.dirname(outPath);

  try {
    fs.mkdirSync(outDir, { recursive: true });
  } catch (err: any) {
    die(EXIT.IO, `Cannot create output directory ${outDir}: ${err?.message ?? err}`);
  }

  if (opts.noClobber && !opts.forceRebuild && fs.existsSync(outPath)) {
    try {
      const mdStat = fs.statSync(mdPath);
      const htmlStat = fs.statSync(outPath);
      if (htmlStat.mtimeMs >= mdStat.mtimeMs) {
        return { outPath, written: false, reason: "skipped-newer" };
      }
    } catch {
      // proceed to write if stat failed
    }
  }

  try {
    fs.writeFileSync(outPath, html);
  } catch (err: any) {
    die(EXIT.IO, `Cannot write ${outPath}: ${err?.message ?? err}`);
  }

  ensureGitignore(outDir);

  return { outPath, written: true, reason: "wrote" };
}

// Open the HTML companion in the user's default browser. Earlier versions took
// over Safari (closed every window, then opened the file); that was replaced in
// 3.0.0 — the Artifact tool is the preferred preview surface, and a local render
// should never close windows it did not open.
//
// macOS-only by design. On other platforms, just print the path.
export function openInBrowser(filePath: string): void {
  if (process.platform !== "darwin") {
    process.stdout.write(
      `open: not supported on ${process.platform}. HTML at ${filePath}\n`
    );
    return;
  }
  let url: string;
  try {
    url = pathToFileURL(path.resolve(filePath)).href;
  } catch (err: any) {
    die(EXIT.IO, `Cannot convert path to URL: ${filePath} — ${err?.message ?? err}`);
  }
  try {
    execFileSync("/usr/bin/open", [url], { stdio: "ignore" });
  } catch (err: any) {
    process.stderr.write(`Warning: could not open ${url}: ${err?.message ?? err}\n`);
    process.stdout.write(`HTML at ${filePath}\n`);
  }
}
