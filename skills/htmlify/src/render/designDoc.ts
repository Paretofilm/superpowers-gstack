import type { DesignDocFM, Plan } from "../schemas.ts";
import { renderHero, renderFooter, htmlShell } from "../helpers/render.ts";
import { tokenize } from "../helpers/markdown.ts";
import { renderPlannedSections, type SectionSpec } from "../helpers/planWiring.ts";
import { renderFeedbackPanel } from "./components/feedback-panel.ts";

interface RenderInput {
  frontmatter: DesignDocFM;
  body: string;
  mdPath: string;
  cssHref: string;
  plan?: Plan | null;  // v2: rich layout plan (null/undefined = v1 template)
}

const SECTION_CARDS: SectionSpec[] = [
  { heading: "Problem Statement", collapsible: true },
  { heading: "What Makes This Cool", collapsible: true },
  { heading: "Constraints", collapsible: true },
  { heading: "Premises", collapsible: true },
  { heading: "Cross-Model Perspective", collapsible: true },
  { heading: "Approaches Considered", collapsible: true },
  { heading: "Recommended Approach", variant: "accent" },
  { heading: "Engineering Decisions", collapsible: true },
  { heading: "Layout Mapping", collapsible: true },
  { heading: "Frontmatter Schemas", collapsible: true },
  { heading: "Failure Modes & Exit Code Taxonomy", collapsible: true },
  { heading: "Failure Modes", collapsible: true },
  { heading: "Idempotency / Overwrite Policy", collapsible: true },
  { heading: "Output Path", collapsible: true },
  { heading: "Open Questions", collapsible: true },
  { heading: "Success Criteria", collapsible: true },
  { heading: "Success Criteria (V1 ship-readiness)", collapsible: true },
  { heading: "Distribution Plan", collapsible: true },
  { heading: "Dependencies", collapsible: true },
  { heading: "NOT in scope", collapsible: true },
  { heading: "NOT in scope (deferred)", collapsible: true },
  { heading: "What already exists", collapsible: true },
  { heading: "Worktree parallelization strategy", collapsible: true },
  { heading: "The Assignment", variant: "accent" },
  { heading: "Next Steps", variant: "accent" },
  { heading: "What I noticed about how you think", variant: "muted", collapsible: true },
  { heading: "GSTACK REVIEW REPORT", variant: "muted", collapsible: true },
];

export function renderDesignDoc(input: RenderInput): string {
  const { frontmatter, body, mdPath, cssHref, plan } = input;
  const tokens = tokenize(body);

  const meta: Array<{ label: string; value: string }> = [];
  if (frontmatter.mode) meta.push({ label: "Mode", value: frontmatter.mode });
  if (frontmatter.branch) meta.push({ label: "Branch", value: frontmatter.branch });
  if (frontmatter.created) {
    meta.push({ label: "Created", value: frontmatter.created.slice(0, 10) });
  }
  if (frontmatter.generator) meta.push({ label: "Generator", value: `/${frontmatter.generator}` });
  if (frontmatter.slug) meta.push({ label: "Project", value: frontmatter.slug });

  const hero = renderHero({
    title: frontmatter.title,
    status: frontmatter.status,
    meta,
    supersedesPath: frontmatter.supersedes ?? null,
  });

  const cards = renderPlannedSections({
    tokens,
    canonical: SECTION_CARDS,
    plan,
  });

  const feedback = plan?.feedback_panel
    ? renderFeedbackPanel(plan.feedback_panel)
    : "";

  const footer = renderFooter({
    mdPath,
    generator: frontmatter.generator ?? null,
  });

  return htmlShell({
    title: frontmatter.title,
    cssHref,
    bodyClass: "companion design-doc",
    body: `${hero}\n<main>${cards}</main>\n${feedback}\n${footer}`,
  });
}
