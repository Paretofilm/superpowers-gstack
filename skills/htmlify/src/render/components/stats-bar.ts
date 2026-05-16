import { esc } from "../../helpers/render.ts";

export interface StatItem {
  label: string;
  value: string | number;
  delta?: string;
  trend?: "up" | "down" | "flat";
}

export interface StatsData {
  items: StatItem[];
}

export function renderStatsBar(data: StatsData): string {
  if (!data || !data.items || data.items.length === 0) return "";
  const cells = data.items
    .map((it) => {
      const trendClass = it.trend ? ` stat-trend-${esc(it.trend)}` : "";
      const delta = it.delta
        ? `<span class="stat-delta${trendClass}">${esc(it.delta)}</span>`
        : "";
      return `<div class="stat">
  <div class="stat-value">${esc(String(it.value))}</div>
  <div class="stat-label">${esc(it.label)}</div>
  ${delta}
</div>`;
    })
    .join("\n");
  return `<div class="stats-bar">${cells}</div>`;
}
