import { esc } from "../../helpers/render.ts";

export interface DiffCardData {
  title?: string;
  before: { label?: string; content: string };
  after: { label?: string; content: string };
  language?: string;  // for future syntax highlighting
}

export function renderDiffCard(data: DiffCardData): string {
  if (!data || !data.before || !data.after) return "";
  const title = data.title
    ? `<h3 class="diff-title">${esc(data.title)}</h3>`
    : "";
  const beforeLabel = esc(data.before.label ?? "Before");
  const afterLabel = esc(data.after.label ?? "After");
  return `<div class="diff-card">
  ${title}
  <div class="diff-grid">
    <div class="diff-pane diff-before">
      <div class="diff-pane-label">${beforeLabel}</div>
      <pre><code>${esc(data.before.content)}</code></pre>
    </div>
    <div class="diff-pane diff-after">
      <div class="diff-pane-label">${afterLabel}</div>
      <pre><code>${esc(data.after.content)}</code></pre>
    </div>
  </div>
</div>`;
}
