// Shared wiring between v2 render plans and the per-type renderers.
// Goal: given a list of canonical prose section headings and an optional plan,
// produce the rendered HTML blocks, with plan overrides applied and pullquotes
// inserted after their target sections.
//
// Used by designDoc / handoff / plan renderers so that plan.sections behave
// consistently across artifact types.

import type { Plan, PlanSection } from "../schemas.ts";
import { extractSection, renderTokens, type Token } from "./markdown.ts";
import { esc, renderCard } from "./render.ts";
import { renderTreatment } from "../render/components/index.ts";
import { renderPullquote } from "../render/components/pullquote.ts";

export interface SectionSpec {
  heading: string;
  variant?: "default" | "accent" | "muted";
  collapsible?: boolean;
}

export function normalizeHeading(h: string): string {
  return h.trim().toLowerCase();
}

export function planSectionMap(
  plan: Plan | null | undefined
): Map<string, PlanSection> {
  const map = new Map<string, PlanSection>();
  if (!plan) return map;
  for (const s of plan.sections ?? []) {
    map.set(normalizeHeading(s.heading), s);
  }
  return map;
}

export function pullquotesAfter(
  heading: string,
  plan: Plan | null | undefined
): string {
  if (!plan?.pullquotes) return "";
  const norm = normalizeHeading(heading);
  return plan.pullquotes
    .filter(
      (pq) => pq.after_section && normalizeHeading(pq.after_section) === norm
    )
    .map((pq) => renderPullquote({ text: pq.text, attribution: pq.attribution }))
    .join("\n");
}

// Render a single section, consulting the plan first. If the plan specifies a
// non-section-card treatment, the component output replaces the default body.
// Empty/null component output falls through to default card rendering.
// Component renderers may throw if plan-LLM produces wrong-shape data (zod
// only validates that data is an object, not that it matches the treatment).
// Catch + warn + fall back so a single malformed section can't crash the CLI.
export function renderSectionWithPlan(
  spec: SectionSpec,
  body: string,
  planSection: PlanSection | undefined
): string {
  if (planSection && planSection.treatment !== "section-card") {
    try {
      const out = renderTreatment(planSection.treatment, planSection.data ?? {});
      if (out !== null && out !== "") {
        return `<section class="card card-${spec.variant ?? "default"} card-component">
  <h2>${esc(spec.heading)}</h2>
  ${out}
</section>`;
      }
    } catch (err: any) {
      process.stderr.write(
        `Warning: treatment '${planSection.treatment}' for section '${spec.heading}' threw: ${err?.message ?? err}\n` +
          `Falling back to default card rendering for this section.\n`
      );
    }
  }
  return renderCard({
    heading: spec.heading,
    body,
    variant: spec.variant,
    collapsible: spec.collapsible,
  });
}

// Iterate canonical sections + plan-introduced sections, producing rendered
// blocks (with pullquotes interleaved).
export function renderPlannedSections(opts: {
  tokens: Token[];
  canonical: SectionSpec[];
  plan: Plan | null | undefined;
  defaultCollapsible?: boolean;
}): string {
  const { tokens, canonical, plan } = opts;
  const map = planSectionMap(plan);
  const rendered = new Set<string>();
  const blocks: string[] = [];

  for (const c of canonical) {
    const norm = normalizeHeading(c.heading);
    const section = extractSection(tokens, c.heading);
    const planSection = map.get(norm);

    if (section === null && !planSection) continue;
    if (section !== null && section.length === 0 && !planSection) continue;

    const inner = section !== null ? renderTokens(section) : "";
    blocks.push(renderSectionWithPlan(c, inner, planSection));
    const pq = pullquotesAfter(c.heading, plan);
    if (pq) blocks.push(pq);
    rendered.add(norm);
  }

  if (plan?.sections) {
    for (const s of plan.sections) {
      const norm = normalizeHeading(s.heading);
      if (rendered.has(norm)) continue;
      const section = extractSection(tokens, s.heading);
      const inner = section !== null ? renderTokens(section) : "";
      blocks.push(
        renderSectionWithPlan(
          { heading: s.heading, collapsible: opts.defaultCollapsible ?? false },
          inner,
          s
        )
      );
      const pq = pullquotesAfter(s.heading, plan);
      if (pq) blocks.push(pq);
      rendered.add(norm);
    }
  }

  return blocks.join("\n");
}
