// Component dispatch: maps treatment names from a render plan to component
// renderers. Each renderer is a pure function from data → HTML.
//
// Unknown treatments fall back to null (caller decides; usually treated as
// "skip with stderr warning + fall through to default section-card render").

import type { ComponentTreatment } from "../../schemas.ts";
import { renderComparisonMatrix, type ComparisonMatrixData } from "./comparison-matrix.ts";
import { renderFlowchart, type FlowchartData } from "./flowchart-svg.ts";
import { renderPullquote, type PullquoteData } from "./pullquote.ts";
import { renderCallout, type CalloutData } from "./callout-box.ts";
import { renderStatsBar, type StatsData } from "./stats-bar.ts";
import { renderTwoColumn, type TwoColumnData } from "./two-column.ts";
import { renderExpandable, type ExpandableData } from "./expandable.ts";
import { renderDiffCard, type DiffCardData } from "./diff-card.ts";
import { renderFeedbackPanel, type FeedbackPanelData } from "./feedback-panel.ts";

export {
  renderComparisonMatrix,
  renderFlowchart,
  renderPullquote,
  renderCallout,
  renderStatsBar,
  renderTwoColumn,
  renderExpandable,
  renderDiffCard,
  renderFeedbackPanel,
};

export type {
  ComparisonMatrixData,
  FlowchartData,
  PullquoteData,
  CalloutData,
  StatsData,
  TwoColumnData,
  ExpandableData,
  DiffCardData,
  FeedbackPanelData,
};

// Dispatches a treatment + data to the matching renderer.
// Returns null for unknown treatments (caller can decide fallback).
// `section-card` is intentionally not handled here — that's the renderer's
// default path and uses extractSection + renderTokens directly.
export function renderTreatment(
  treatment: ComponentTreatment,
  data: unknown
): string | null {
  switch (treatment) {
    case "comparison-matrix":
      return renderComparisonMatrix(data as ComparisonMatrixData);
    case "flowchart-svg":
      return renderFlowchart(data as FlowchartData);
    case "pullquote":
      return renderPullquote(data as PullquoteData);
    case "callout-box":
      return renderCallout(data as CalloutData);
    case "stats-bar":
      return renderStatsBar(data as StatsData);
    case "two-column":
      return renderTwoColumn(data as TwoColumnData);
    case "expandable":
      return renderExpandable(data as ExpandableData);
    case "diff-card":
      return renderDiffCard(data as DiffCardData);
    case "section-card":
      // Handled by the default section-card path in each renderer.
      return null;
    default:
      return null;
  }
}
