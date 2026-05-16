import type { DesignDocFM } from "../schemas.ts";
import { esc, renderHero, renderFooter, renderCard, htmlShell } from "../helpers/render.ts";
import { tokenize, extractSection, renderTokens } from "../helpers/markdown.ts";

interface RenderInput {
  frontmatter: DesignDocFM;
  body: string;
  mdPath: string;
  cssHref: string;
}

const SECTION_CARDS: Array<{
  heading: string;
  variant?: "default" | "accent" | "muted";
  collapsible?: boolean;
}> = [
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
  const { frontmatter, body, mdPath, cssHref } = input;
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

  const cards = SECTION_CARDS
    .map((c) => {
      const section = extractSection(tokens, c.heading);
      if (section === null) return null;
      if (section.length === 0) return null;
      const inner = renderTokens(section);
      return renderCard({
        heading: c.heading,
        body: inner,
        variant: c.variant,
        collapsible: c.collapsible,
      });
    })
    .filter((x) => x !== null)
    .join("\n");

  const footer = renderFooter({
    mdPath,
    generator: frontmatter.generator ?? null,
  });

  return htmlShell({
    title: frontmatter.title,
    cssHref,
    bodyClass: "companion design-doc",
    body: `${hero}\n<main>${cards}</main>\n${footer}`,
  });
}
