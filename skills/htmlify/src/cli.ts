import * as path from "node:path";
import * as fs from "node:fs";
import { fileURLToPath } from "node:url";
import { readArtifact } from "./readArtifact.ts";
import { classify } from "./classifyArtifact.ts";
import { renderDesignDoc } from "./render/designDoc.ts";
import { renderHandoff } from "./render/handoff.ts";
import { renderPlan } from "./render/plan.ts";
import { renderGeneric } from "./render/generic.ts";
import { writeCompanion, openInBrowser, companionPathFor, OUTPUT_DIR } from "./output.ts";
import { writeDashboard } from "./renderDashboard.ts";
import { readPlan } from "./readPlan.ts";
import type { Plan } from "./schemas.ts";
import { EXIT, die } from "./helpers/exit-codes.ts";

const HELP = `htmlify — generate HTML companions for superpowers-gstack MD artifacts

USAGE
  htmlify <file.md> [--plan <plan.json>] [--open] [--no-clobber] [--force-rebuild]
  htmlify dashboard <dir>
  htmlify --help

OPTIONS
  --plan <file>     Load v2 rendering plan (JSON) for rich, content-aware layout
                    (comparison-matrix, flowchart-svg, pullquote, feedback-panel,
                    etc.). Without --plan: v1 template rendering (default).
  --open            After render, open the HTML in the default browser (macOS).
  --no-clobber      Skip render if HTML is newer than MD.
  --force-rebuild   Render regardless of mtime (overrides --no-clobber).

DASHBOARD
  htmlify dashboard <dir>
    Generates an aggregated index page at <dir>/.superpowers-html/index.html
    listing all artifact MDs in <dir>, sorted by mtime desc.

EXIT CODES
  0  success
  1  usage error
  2  schema validation failure
  3  MD parse error
  4  I/O error
  5  setup error (run: cd skills/htmlify && bun install)`;

const REPO_ROOT_HINT = path.resolve(fileURLToPath(import.meta.url), "..", "..");
// CSS lives at skills/htmlify/styles/companion.css. Companion HTML lives at
// <dir>/.superpowers-html/<name>.html. Relative path from HTML to CSS:
// from .superpowers-html/ → ../../../skills/htmlify/styles/companion.css? No.
// Better: copy CSS to the .superpowers-html/ dir alongside the HTML.
// We'll handle CSS as inline import URL pointing to a local copy.

function ensureCssAt(htmlPath: string): string {
  const outDir = path.dirname(htmlPath);
  const cssTarget = path.join(outDir, "companion.css");
  const cssSource = path.join(REPO_ROOT_HINT, "styles", "companion.css");
  try {
    fs.mkdirSync(outDir, { recursive: true });
    // Always copy (overwrite) so CSS stays in sync if it changes.
    const css = fs.readFileSync(cssSource, "utf8");
    fs.writeFileSync(cssTarget, css);
  } catch (err: any) {
    process.stderr.write(
      `Warning: could not copy CSS to ${cssTarget}: ${err?.message ?? err}\n`
    );
  }
  return "companion.css";
}

interface ParsedArgs {
  command: "render" | "dashboard" | "help";
  positional: string[];
  flags: {
    open: boolean;
    noClobber: boolean;
    forceRebuild: boolean;
    planPath: string | null;
  };
}

function parseArgs(argv: string[]): ParsedArgs {
  const positional: string[] = [];
  const flags = {
    open: false,
    noClobber: false,
    forceRebuild: false,
    planPath: null as string | null,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--open") flags.open = true;
    else if (a === "--no-clobber") flags.noClobber = true;
    else if (a === "--force-rebuild") flags.forceRebuild = true;
    else if (a === "--plan") {
      const next = argv[i + 1];
      if (!next || next.startsWith("--")) {
        die(EXIT.USAGE, `--plan requires a path argument\n\n${HELP}`);
      }
      flags.planPath = next;
      i++;
    } else if (a === "--help" || a === "-h") {
      return { command: "help", positional, flags };
    } else if (a.startsWith("--")) {
      die(EXIT.USAGE, `Unknown flag: ${a}\n\n${HELP}`);
    } else {
      positional.push(a);
    }
  }
  if (positional.length === 0) return { command: "help", positional, flags };
  if (positional[0] === "dashboard") {
    return { command: "dashboard", positional: positional.slice(1), flags };
  }
  return { command: "render", positional, flags };
}

function relPath(from: string, to: string): string {
  return path.relative(path.dirname(from), to) || path.basename(to);
}

function renderOne(mdPath: string, flags: ParsedArgs["flags"]): void {
  const abs = path.resolve(mdPath);
  if (!fs.existsSync(abs)) {
    die(EXIT.IO, `File not found: ${mdPath}`);
  }
  const artifact = readArtifact(abs);
  const classified = classify(artifact);

  // Load plan if --plan was passed. On any failure, falls back to null,
  // which triggers v1 template rendering (graceful degradation per design E2).
  let plan: Plan | null = null;
  if (flags.planPath) {
    plan = readPlan(flags.planPath);
  }

  const outPath = companionPathFor(abs);
  const cssHref = ensureCssAt(outPath);
  const mdHref = relPath(outPath, abs);

  let html: string;
  switch (classified.kind) {
    case "design-doc":
      html = renderDesignDoc({
        frontmatter: classified.frontmatter,
        body: artifact.body,
        mdPath: mdHref,
        cssHref,
        plan,
      });
      break;
    case "handoff":
      html = renderHandoff({
        frontmatter: classified.frontmatter,
        body: artifact.body,
        mdPath: mdHref,
        cssHref,
        plan,
      });
      break;
    case "plan":
      html = renderPlan({
        frontmatter: classified.frontmatter,
        body: artifact.body,
        mdPath: mdHref,
        cssHref,
        plan,
      });
      break;
    case "generic":
      html = renderGeneric({
        frontmatter: classified.frontmatter,
        body: artifact.body,
        mdPath: mdHref,
        cssHref,
        plan,
      });
      break;
  }

  const result = writeCompanion(abs, html, {
    noClobber: flags.noClobber,
    forceRebuild: flags.forceRebuild,
  });

  if (result.written) {
    process.stdout.write(`${result.outPath}\n`);
  } else {
    process.stdout.write(`${result.outPath} (skipped: ${result.reason})\n`);
  }

  if (flags.open) {
    openInBrowser(result.outPath);
  }
}

function runDashboard(dir: string): void {
  if (!fs.existsSync(dir)) {
    die(EXIT.IO, `Directory not found: ${dir}`);
  }
  if (!fs.statSync(dir).isDirectory()) {
    die(EXIT.USAGE, `Not a directory: ${dir}`);
  }
  // CSS placed in <dir>/.superpowers-html/companion.css
  const outDir = path.join(path.resolve(dir), OUTPUT_DIR);
  fs.mkdirSync(outDir, { recursive: true });
  try {
    const cssSource = path.join(REPO_ROOT_HINT, "styles", "companion.css");
    fs.writeFileSync(path.join(outDir, "companion.css"), fs.readFileSync(cssSource, "utf8"));
  } catch (err: any) {
    process.stderr.write(`Warning: could not copy CSS: ${err?.message ?? err}\n`);
  }
  const indexPath = writeDashboard(dir, "companion.css");
  if (indexPath) {
    process.stdout.write(`${indexPath}\n`);
  }
}

export function main(argv: string[]): void {
  const parsed = parseArgs(argv);
  if (parsed.command === "help") {
    process.stdout.write(`${HELP}\n`);
    process.exit(EXIT.SUCCESS);
  }
  if (parsed.command === "dashboard") {
    if (parsed.positional.length === 0) {
      die(EXIT.USAGE, "dashboard: missing <dir> argument\n\n" + HELP);
    }
    runDashboard(parsed.positional[0]);
    process.exit(EXIT.SUCCESS);
  }
  // command === "render"
  if (parsed.positional.length === 0) {
    die(EXIT.USAGE, "render: missing <file.md> argument\n\n" + HELP);
  }
  for (const md of parsed.positional) {
    renderOne(md, parsed.flags);
  }
  process.exit(EXIT.SUCCESS);
}

if (import.meta.main) {
  main(process.argv.slice(2));
}
