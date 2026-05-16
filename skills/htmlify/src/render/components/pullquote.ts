import { esc } from "../../helpers/render.ts";

export interface PullquoteData {
  text: string;
  attribution?: string;
}

export function renderPullquote(data: PullquoteData): string {
  if (!data || !data.text) return "";
  const attribution = data.attribution
    ? `<cite class="pullquote-attribution">— ${esc(data.attribution)}</cite>`
    : "";
  return `<blockquote class="pullquote">
  <p>${esc(data.text)}</p>
  ${attribution}
</blockquote>`;
}
