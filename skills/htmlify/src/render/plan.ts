import type { PlanFM, Plan } from "../schemas.ts";
import { esc, renderHero, renderFooter, renderCard, htmlShell, statusBadge } from "../helpers/render.ts";
import { tokenize, extractSection, renderTokens } from "../helpers/markdown.ts";
import { renderPlannedSections, type SectionSpec } from "../helpers/planWiring.ts";
import { renderFeedbackPanel } from "./components/feedback-panel.ts";

interface RenderInput {
  frontmatter: PlanFM;
  body: string;
  mdPath: string;
  cssHref: string;
  plan?: Plan | null;  // v2 render plan (not to be confused with PlanFM frontmatter type)
}

const PROSE_SECTIONS: SectionSpec[] = [
  { heading: "Overview", collapsible: true },
  { heading: "Architecture", collapsible: true },
  { heading: "Approach", collapsible: true },
  { heading: "Dependencies", collapsible: true },
  { heading: "NOT in scope", collapsible: true },
  { heading: "Open Questions", collapsible: true },
  { heading: "Success Criteria", collapsible: true },
];

export function renderPlan(input: RenderInput): string {
  const { frontmatter, body, mdPath, cssHref, plan } = input;
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
  const proseCards = renderPlannedSections({
    tokens,
    canonical: PROSE_SECTIONS,
    plan,
    defaultCollapsible: true,
  });

  const feedback = plan?.feedback_panel
    ? renderFeedbackPanel(plan.feedback_panel)
    : "";

  const footer = renderFooter({ mdPath });

  return htmlShell({
    title: frontmatter.title,
    cssHref,
    bodyClass: "companion plan",
    body: `${hero}\n<main>${phasesBlock}${proseCards}</main>\n${feedback}\n${footer}`,
  });
}
