import { esc } from "../../helpers/render.ts";
import { marked } from "marked";
import DOMPurify from "isomorphic-dompurify";

export interface ExpandableData {
  summary: string;
  body: string;  // MD or HTML
  open?: boolean;
}

export function renderExpandable(data: ExpandableData): string {
  if (!data || !data.summary) return "";
  const isOpen = data.open ? " open" : "";
  const bodyHtml = DOMPurify.sanitize(
    marked.parse(data.body ?? "", { async: false }) as string
  );
  return `<details class="expandable"${isOpen}>
  <summary>${esc(data.summary)}</summary>
  <div class="expandable-body">${bodyHtml}</div>
</details>`;
}
