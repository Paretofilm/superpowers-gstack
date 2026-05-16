import { esc, renderHero, renderFooter, htmlShell } from "../helpers/render.ts";
import { renderFullBody } from "../helpers/markdown.ts";
import * as path from "node:path";

interface RenderInput {
  frontmatter: Record<string, unknown>;
  body: string;
  mdPath: string;
  cssHref: string;
}

// Generic fallback when frontmatter is missing or type unknown.
// Renders full body via marked() + DOMPurify. Banner warns the view is
// best-effort and lacks pedagogical scaffolding.

export function renderGeneric(input: RenderInput): string {
  const { frontmatter, body, mdPath, cssHref } = input;
  const title = (frontmatter.title as string) ?? path.basename(mdPath, ".md");
  const status = frontmatter.status as string | undefined;

  const hero = renderHero({
    title,
    status,
  });

  const banner = `<p class="fallback-banner">This artifact predates the schema or has no recognized <code>type:</code> — pedagogical view is best-effort. <a href="${esc(mdPath)}">View source MD →</a></p>`;

  const main = `<main class="card">${renderFullBody(body)}</main>`;

  const footer = renderFooter({ mdPath });

  return htmlShell({
    title,
    cssHref,
    bodyClass: "companion generic",
    body: `${hero}\n${banner}\n${main}\n${footer}`,
  });
}
