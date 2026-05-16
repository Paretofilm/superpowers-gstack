import { esc } from "../../helpers/render.ts";

export interface ComparisonItem {
  title: string;
  summary?: string;
  pros?: string[];
  cons?: string[];
  effort?: string;
  risk?: string;
  highlighted?: boolean;  // visual emphasis (the recommended one)
}

export interface ComparisonMatrixData {
  items: ComparisonItem[];
}

function bulletList(items: string[] | undefined, className: string): string {
  if (!items || items.length === 0) return "";
  const lis = items.map((t) => `<li>${esc(t)}</li>`).join("");
  return `<ul class="${className}">${lis}</ul>`;
}

function metaRow(label: string, value: string | undefined): string {
  if (!value) return "";
  return `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`;
}

export function renderComparisonMatrix(data: ComparisonMatrixData): string {
  if (!data || !data.items || data.items.length === 0) return "";
  const cards = data.items
    .map((it) => {
      const highlightClass = it.highlighted ? " comparison-card-highlighted" : "";
      const summary = it.summary
        ? `<p class="comparison-summary">${esc(it.summary)}</p>`
        : "";
      const pros = bulletList(it.pros, "comparison-pros");
      const cons = bulletList(it.cons, "comparison-cons");
      const meta = (it.effort || it.risk)
        ? `<dl class="comparison-meta">${metaRow("Effort", it.effort)}${metaRow("Risk", it.risk)}</dl>`
        : "";
      const badge = it.highlighted
        ? `<span class="comparison-badge">Recommended</span>`
        : "";
      return `<article class="comparison-card${highlightClass}">
  <header>
    <h3>${esc(it.title)}</h3>
    ${badge}
  </header>
  ${summary}
  ${pros ? `<h4>Pros</h4>${pros}` : ""}
  ${cons ? `<h4>Cons</h4>${cons}` : ""}
  ${meta}
</article>`;
    })
    .join("\n");
  return `<div class="comparison-matrix">${cards}</div>`;
}
