import { esc } from "../../helpers/render.ts";
import { marked } from "marked";
import DOMPurify from "isomorphic-dompurify";

export type CalloutLevel = "info" | "warn" | "insight" | "danger";

export interface CalloutData {
  level?: CalloutLevel;
  title?: string;
  body: string;  // MD or plain text
}

const LEVEL_LABEL: Record<CalloutLevel, string> = {
  info: "Note",
  warn: "Warning",
  insight: "Insight",
  danger: "Critical",
};

export function renderCallout(data: CalloutData): string {
  if (!data || !data.body) return "";
  const level: CalloutLevel = data.level ?? "info";
  const title = data.title
    ? esc(data.title)
    : LEVEL_LABEL[level] ?? "Note";
  const bodyHtml = DOMPurify.sanitize(marked.parse(data.body, { async: false }) as string);
  return `<aside class="callout callout-${esc(level)}">
  <h3 class="callout-title">${title}</h3>
  <div class="callout-body">${bodyHtml}</div>
</aside>`;
}
