import type { PlanFM } from "../schemas.ts";
import { esc, renderHero, renderFooter, renderCard, htmlShell, statusBadge } from "../helpers/render.ts";
import { tokenize, extractSection, renderTokens } from "../helpers/markdown.ts";

interface RenderInput {
  frontmatter: PlanFM;
  body: string;
  mdPath: string;
  cssHref: string;
}

const PROSE_SECTIONS = [
  "Overview",
  "Architecture",
  "Approach",
  "Dependencies",
  "NOT in scope",
  "Open Questions",
  "Success Criteria",
];

export function renderPlan(input: RenderInput): string {
  const { frontmatter, body, mdPath, cssHref } = input;
  const phases = frontmatter.phases ?? [];
  const doneCount = phases.filter((p) => p.status === "done").length;
  const totalCount = phases.length;

  const meta: Array<{ label: string; value: string }> = [];
  if (frontmatter.branch) meta.push({ label: "Branch", value: frontmatter.branch });
  if (frontmatter.created) meta.push({ label: "Created", value: frontmatter.created.slice(0, 10) });
  if (totalCount > 0) meta.push({ label: "Progress", value: `${doneCount} / ${totalCount} phases done` });
  if (frontmatter.slug) meta.push({ label: "Project", value: frontmatter.slug });

  const hero = renderHero({
    title: frontmatter.title,
    status: frontmatter.status,
    meta,
    supersedesPath: frontmatter.supersedes ?? null,
  });

  const phasesBlock = phases.length > 0
    ? renderCard({
        heading: "Phases",
        variant: "accent",
        body: phases
          .map((p) => {
            const taskList = (p.tasks && p.tasks.length > 0)
              ? `<ul>${p.tasks.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`
              : "";
            return `<div class="phase">
              <div>
                <span class="phase-name">${esc(p.name)}</span>
                <span class="phase-progress">(${esc(p.id)})</span>
              </div>
              ${statusBadge(p.status)}
              ${taskList}
            </div>`;
          })
          .join("\n"),
      })
    : "";

  const tokens = tokenize(body);
  const proseCards = PROSE_SECTIONS
    .map((h) => {
      const section = extractSection(tokens, h);
      if (!section || section.length === 0) return null;
      return renderCard({
        heading: h,
        body: renderTokens(section),
        collapsible: true,
      });
    })
    .filter((x) => x !== null)
    .join("\n");

  const footer = renderFooter({ mdPath });

  return htmlShell({
    title: frontmatter.title,
    cssHref,
    bodyClass: "companion plan",
    body: `${hero}\n<main>${phasesBlock}${proseCards}</main>\n${footer}`,
  });
}
