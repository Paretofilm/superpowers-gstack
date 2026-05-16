import { esc } from "../../helpers/render.ts";
import { marked } from "marked";
import DOMPurify from "isomorphic-dompurify";

export interface TwoColumnData {
  left: { heading?: string; body: string };
  right: { heading?: string; body: string };
}

function sanitizedMd(md: string): string {
  return DOMPurify.sanitize(marked.parse(md ?? "", { async: false }) as string);
}

export function renderTwoColumn(data: TwoColumnData): string {
  if (!data || !data.left || !data.right) return "";
  const leftHeading = data.left.heading
    ? `<h3 class="col-heading">${esc(data.left.heading)}</h3>`
    : "";
  const rightHeading = data.right.heading
    ? `<h3 class="col-heading">${esc(data.right.heading)}</h3>`
    : "";
  return `<div class="two-column">
  <div class="col">
    ${leftHeading}
    ${sanitizedMd(data.left.body)}
  </div>
  <div class="col">
    ${rightHeading}
    ${sanitizedMd(data.right.body)}
  </div>
</div>`;
}
