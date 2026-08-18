import type { Plan } from "../schemas.ts";
import { esc, renderHero, renderFooter, htmlShell } from "../helpers/render.ts";
import { renderFullBody } from "../helpers/markdown.ts";
import { renderFeedbackPanel } from "./components/feedback-panel.ts";
import * as path from "node:path";

interface RenderInput {
  frontmatter: Record<string, unknown>;
  body: string;
  mdPath: string;
  cssHref: string;
  plan?: Plan | null;
}

// Generic fallback when frontmatter is missing or type unknown.
// Renders full body via marked() + DOMPurify. Banner warns the view is
// best-effort and lacks pedagogical scaffolding.

export function renderGeneric(input: RenderInput): string {
  const { frontmatter, body, mdPath, cssHref, plan } = input;
  const title = (frontmatter.title as string) ?? path.basename(mdPath, ".md");
  const status = frontmatter.status as string | undefined;

  const hero = renderHero({
    title,
    status,
  });

  const banner = `<p class="fallback-banner">This artifact predates the schema or has no recognized <code>type:</code> — pedagogical view is best-effort. <a href="${esc(mdPath)}">View source MD →</a></p>`;

  const main = `<main class="card">${renderFullBody(body)}</main>`;

  // A plan reached the generic renderer. It used to be accepted and dropped in
  // silence (#52): exit 0, valid HTML, no feedback panel — a review that looked
  // finished while the user was never shown the form. The panel is the one part
  // that carries independently, so render it; warn about the rest rather than
  // pretending the plan was honoured.
  const feedback = plan?.feedback_panel ? renderFeedbackPanel(plan.feedback_panel) : "";
  if (plan) {
    const ignored: string[] = [];
    if (plan.sections?.length) ignored.push(`${plan.sections.length} section treatment(s)`);
    if (plan.pullquotes?.length) ignored.push(`${plan.pullquotes.length} pullquote(s)`);
    if (ignored.length) {
      process.stderr.write(
        `Warning: artifact classified as generic (no recognized \`type:\` frontmatter) — ` +
        `${ignored.join(" and ")} in the plan cannot be applied. ` +
        `Add \`type: design-doc\` to the frontmatter to use them.` +
        (plan.feedback_panel ? " The feedback panel was rendered.\n" : "\n")
      );
    }
  }

  const footer = renderFooter({ mdPath });

  return htmlShell({
    title,
    cssHref,
    bodyClass: "companion generic",
    body: `${hero}\n${banner}\n${main}\n${feedback}\n${footer}`,
  });
}
