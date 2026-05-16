import type { HandoffFM } from "../schemas.ts";
import { esc, renderHero, renderFooter, renderCard, htmlShell, statusBadge } from "../helpers/render.ts";
import { tokenize, extractSection, renderTokens, renderFullBody } from "../helpers/markdown.ts";

interface RenderInput {
  frontmatter: HandoffFM;
  body: string;
  mdPath: string;
  cssHref: string;
}

const PROSE_SECTIONS = [
  "What I was doing",
  "Key decisions made this session",
  "Files modified this session",
  "Plan progress",
  "Open questions / blockers",
];

export function renderHandoff(input: RenderInput): string {
  const { frontmatter, body, mdPath, cssHref } = input;

  const meta: Array<{ label: string; value: string }> = [];
  if (frontmatter.active_task) meta.push({ label: "Active task", value: frontmatter.active_task });
  if (frontmatter.branch) meta.push({ label: "Branch", value: frontmatter.branch });
  if (frontmatter.session_end) meta.push({ label: "Session end", value: frontmatter.session_end });
  if (frontmatter.commit_at_handoff) meta.push({ label: "Commit", value: frontmatter.commit_at_handoff });

  const hero = renderHero({
    title: frontmatter.next_step,
    status: frontmatter.status,
    meta,
  });

  const completed = frontmatter.completed ?? [];
  const remaining = frontmatter.remaining ?? [];
  const tasksBlock = (completed.length > 0 || remaining.length > 0)
    ? `<div class="tasks-progress">
        <div>
          <h3>Completed (${completed.length})</h3>
          ${completed.map((t) => `<span class="task-chip done">${esc(t)}</span>`).join("\n") || `<p class="card-muted">None</p>`}
        </div>
        <div>
          <h3>Remaining (${remaining.length})</h3>
          ${remaining.map((t) => `<span class="task-chip">${esc(t)}</span>`).join("\n") || `<p class="card-muted">None</p>`}
        </div>
      </div>`
    : "";

  const env = frontmatter.env ?? {};
  const envLines = Object.entries(env)
    .filter(([, v]) => v && v !== "n/a")
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n");
  const envBlock = envLines
    ? renderCard({
        heading: "Environment",
        body: `<pre><code>${esc(envLines)}</code></pre>`,
      })
    : "";

  const inFlight = frontmatter.files_in_flight ?? [];
  const inFlightBlock = inFlight.length > 0
    ? renderCard({
        heading: "Files in flight",
        body: `<ul>${inFlight.map((f) => `<li><code>${esc(f)}</code></li>`).join("")}</ul>`,
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

  const tasksCard = tasksBlock
    ? renderCard({
        heading: "Tasks",
        body: tasksBlock,
        variant: "accent",
      })
    : "";

  const footer = renderFooter({ mdPath });

  return htmlShell({
    title: `Handoff — ${frontmatter.active_task ?? frontmatter.next_step.slice(0, 40)}`,
    cssHref,
    bodyClass: "companion handoff",
    body: `${hero}\n<main>${tasksCard}${envBlock}${inFlightBlock}${proseCards}</main>\n${footer}`,
  });
}
