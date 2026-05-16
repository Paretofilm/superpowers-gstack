import dagre from "dagre";
import { marked } from "marked";
import DOMPurify from "isomorphic-dompurify";
import { esc } from "../../helpers/render.ts";

export interface FlowchartNode {
  id: string;
  label: string;
  shape?: "rect" | "round" | "ellipse";
  emphasis?: boolean;
}

export interface FlowchartEdge {
  from: string;
  to: string;
  label?: string;
}

export interface FlowchartData {
  nodes: FlowchartNode[];
  edges: FlowchartEdge[];
  orientation?: "TB" | "LR" | "BT" | "RL";
  /** Optional markdown rendered alongside the diagram (right column when
      horizontal, below when too narrow). Use for legend/budget/context that
      would otherwise leave the card half-empty. */
  notes?: string;
}

// ============================================================
// Constants
// ============================================================

// All viewBox sizing scales together — increasing one without the others
// breaks the visual ratio. Bumped 25% over the original v2.1 sizes.
const NODE_WIDTH = 165;
const NODE_HEIGHT_TB = 50;
const NODE_HEIGHT_LR = 72;
const PAD = 20;
const NODE_FONT_PX = 15.5;
const EDGE_FONT_PX = 13;
const ARROW_SIZE = 9;
const EDGE_LABEL_OFFSET = 14;
const FONT = `-apple-system, "SF Pro Text", ui-sans-serif, system-ui, sans-serif`;
const FONT_MONO = `ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace`;

// Layout policy thresholds. Documented here so the reasoning lives next to
// the numbers and survives future tweaks.
const AUTO_LR_MAX_NODES = 4;        // chains ≤4 → LR; longer would crowd edge labels
const TB_BALANCED_NODES = 5;         // exactly-5 chains → TB single column, 50/50 with notes
const SPLIT_TARGET_LEFT_MAX = 5;     // split column tries to keep ≤5 on the left
// Note: the 5-node balanced visual reduction is *purely a CSS concern*
// (max-height on the svg-wrap shrinks rendered boxes ~25%). Scaling node
// viewBox coordinates compounded with CSS reduction and ended up halving
// boxes — keep viewBox coordinates consistent and let CSS drive size.

// ============================================================
// Helpers
// ============================================================

// True when every node has at most one predecessor and one successor — i.e.
// the graph is a linear pipeline rather than a tree or DAG.
function isLinearChain(
  nodes: FlowchartNode[],
  edges: FlowchartEdge[]
): boolean {
  if (nodes.length < 2) return false;
  const inDeg = new Map<string, number>();
  const outDeg = new Map<string, number>();
  for (const n of nodes) {
    inDeg.set(n.id, 0);
    outDeg.set(n.id, 0);
  }
  for (const e of edges) {
    if (!inDeg.has(e.to) || !outDeg.has(e.from)) continue;
    inDeg.set(e.to, (inDeg.get(e.to) ?? 0) + 1);
    outDeg.set(e.from, (outDeg.get(e.from) ?? 0) + 1);
  }
  for (const n of nodes) {
    if ((inDeg.get(n.id) ?? 0) > 1) return false;
    if ((outDeg.get(n.id) ?? 0) > 1) return false;
  }
  return true;
}

// Returns the nodes in chain-traversal order: start (in-degree 0) → next → … .
// Falls back to the input array if no clear start can be detected.
function chainOrder(
  nodes: FlowchartNode[],
  edges: FlowchartEdge[]
): FlowchartNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const succ = new Map<string, string>();
  const hasPred = new Set<string>();
  for (const e of edges) {
    if (byId.has(e.from) && byId.has(e.to)) {
      succ.set(e.from, e.to);
      hasPred.add(e.to);
    }
  }
  let start: string | undefined;
  for (const n of nodes) {
    if (!hasPred.has(n.id)) {
      start = n.id;
      break;
    }
  }
  if (!start) return nodes;

  const order: FlowchartNode[] = [];
  const seen = new Set<string>();
  let cur: string | undefined = start;
  while (cur && !seen.has(cur)) {
    seen.add(cur);
    const node = byId.get(cur);
    if (node) order.push(node);
    cur = succ.get(cur);
  }
  // Append any disconnected nodes at the end so we don't silently drop them.
  for (const n of nodes) {
    if (!seen.has(n.id)) order.push(n);
  }
  return order;
}

// Decide how to break a long chain across two sub-columns. The left column
// holds up to SPLIT_TARGET_LEFT_MAX; if that would leave fewer than 3 nodes
// on the right (which looks lopsided), rebalance toward ceil(n/2).
function computeSplit(n: number): { left: number; right: number } {
  const idealLeft = SPLIT_TARGET_LEFT_MAX;
  const right = n - idealLeft;
  if (right < 3) {
    const left = Math.ceil(n / 2);
    return { left, right: n - left };
  }
  return { left: idealLeft, right };
}

type LayoutMode =
  | "lr-stacked" // ≤4-node chain: LR pipeline, full card width, notes below
  | "tb-balanced" // exactly-5 chain: TB single column, 50/50 with notes, scaled
  | "tb-split" // 6+-node chain: two TB sub-columns joined by curve, 2/3+1/3
  | "tb-regular" // trees/DAGs: regular TB with side notes
  | "lr-regular"; // caller pinned LR/RL explicitly: regular dagre LR

interface LayoutDecision {
  orientation: "TB" | "LR" | "BT" | "RL";
  mode: LayoutMode;
  isHorizontal: boolean;
  split?: { left: number; right: number };
}

function decideLayout(data: FlowchartData): LayoutDecision {
  const n = data.nodes.length;
  const isChain = isLinearChain(data.nodes, data.edges ?? []);
  const hasNotes = !!data.notes;

  // Caller pinned orientation — respect it, no fancy splits.
  if (data.orientation) {
    const o = data.orientation;
    const isHorizontal = o === "LR" || o === "RL";
    return {
      orientation: o,
      mode: isHorizontal ? "lr-regular" : "tb-regular",
      isHorizontal,
    };
  }

  if (isChain && n <= AUTO_LR_MAX_NODES) {
    return { orientation: "LR", mode: "lr-stacked", isHorizontal: true };
  }

  if (isChain && n === TB_BALANCED_NODES && hasNotes) {
    return { orientation: "TB", mode: "tb-balanced", isHorizontal: false };
  }

  if (isChain && n >= TB_BALANCED_NODES + 1) {
    return {
      orientation: "TB",
      mode: "tb-split",
      isHorizontal: false,
      split: computeSplit(n),
    };
  }

  // Trees, DAGs, single-node, or 5-node chain without notes
  return { orientation: "TB", mode: "tb-regular", isHorizontal: false };
}

// ============================================================
// SVG primitive emitters (shared between dagre and split paths)
// ============================================================

function emitNode(
  node: FlowchartNode,
  x: number,
  y: number,
  nw: number,
  nh: number
): string {
  const rx = node.shape === "round" ? nh / 2 : 12;
  const cls = `flowchart-node${node.emphasis ? " flowchart-node-emphasis" : ""}`;
  return `<g class="${cls}">
        <rect x="${x}" y="${y}" width="${nw}" height="${nh}" rx="${rx}" ry="${rx}"/>
        <text x="${x + nw / 2}" y="${y + nh / 2}" text-anchor="middle" dominant-baseline="central" font-family="${FONT}" font-size="${NODE_FONT_PX}" font-weight="500">${esc(node.label)}</text>
      </g>`;
}

function emitArrowHead(x: number, y: number, angle: number): string {
  const sz = ARROW_SIZE;
  const ax1 = x - sz * Math.cos(angle - Math.PI / 6);
  const ay1 = y - sz * Math.sin(angle - Math.PI / 6);
  const ax2 = x - sz * Math.cos(angle + Math.PI / 6);
  const ay2 = y - sz * Math.sin(angle + Math.PI / 6);
  return `<polygon points="${x},${y} ${ax1},${ay1} ${ax2},${ay2}"/>`;
}

function emitEdgeLabel(x: number, y: number, label: string): string {
  return `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="central" font-family="${FONT_MONO}" font-size="${EDGE_FONT_PX}" class="flowchart-edge-label">${esc(label)}</text>`;
}

// ============================================================
// Split-chain renderer (hand-laid-out, no dagre)
// ============================================================

function renderSplitChainSvg(
  ordered: FlowchartNode[],
  edges: FlowchartEdge[],
  split: { left: number; right: number }
): { width: number; height: number; body: string } {
  const NW = NODE_WIDTH;
  const NH = NODE_HEIGHT_TB;
  const ranksep = 55; // matches dagre TB — labels need room between boxes
  const colGap = 125; // horizontal room between the two sub-columns
  const yPad = 90; // extra top/bottom room for the connector curve's bends

  // Edge-label lookup keyed by `from->to` so we can render labels even though
  // we're not using dagre's edge iteration here.
  const labelOf = new Map<string, string>();
  for (const e of edges) {
    if (e.label) labelOf.set(`${e.from}->${e.to}`, e.label);
  }

  const leftX = PAD;
  const rightX = PAD + NW + colGap;
  const totalWidth = PAD + NW + colGap + NW + PAD;
  const leftColH = split.left * NH + (split.left - 1) * ranksep;
  const rightColH = split.right * NH + (split.right - 1) * ranksep;
  const colsHeight = Math.max(leftColH, rightColH);
  const totalHeight = yPad + colsHeight + yPad;

  const shapes: string[] = [];
  const paths: string[] = [];

  // Helper: vertical arrow between two adjacent boxes in a single column,
  // with the label hung to the right of the arrow (off the arrow path).
  function intraColumnArrow(colX: number, topY: number, bottomY: number, label?: string) {
    const midX = colX + NW / 2;
    paths.push(
      `<g class="flowchart-edge">
        <path d="M ${midX} ${topY} L ${midX} ${bottomY}" fill="none"/>
        ${emitArrowHead(midX, bottomY, Math.PI / 2)}
        ${label ? emitEdgeLabel(midX + 28, (topY + bottomY) / 2, label) : ""}
      </g>`
    );
  }

  // Left column
  for (let i = 0; i < split.left; i++) {
    const node = ordered[i];
    const y = yPad + i * (NH + ranksep);
    shapes.push(emitNode(node, leftX, y, NW, NH));
    if (i < split.left - 1) {
      const fromBottom = y + NH;
      const toTop = y + NH + ranksep;
      const label = labelOf.get(`${node.id}->${ordered[i + 1].id}`);
      intraColumnArrow(leftX, fromBottom, toTop, label);
    }
  }

  // Right column
  for (let i = 0; i < split.right; i++) {
    const idx = split.left + i;
    const node = ordered[idx];
    const y = yPad + i * (NH + ranksep);
    shapes.push(emitNode(node, rightX, y, NW, NH));
    if (i < split.right - 1) {
      const fromBottom = y + NH;
      const toTop = y + NH + ranksep;
      const label = labelOf.get(`${node.id}->${ordered[idx + 1].id}`);
      intraColumnArrow(rightX, fromBottom, toTop, label);
    }
  }

  // Connector path: bottom of last-left → straight down → tight bend right →
  // straight up at midX → tight bend right → straight down into top of
  // first-right. Built as L + C + L + C + L so the vertical segments stay
  // truly straight (no Bezier wobble); the bends happen only at the corners.
  const lastLeftBottomY = yPad + (split.left - 1) * (NH + ranksep) + NH;
  const startX = leftX + NW / 2;
  const startY = lastLeftBottomY;
  const endX = rightX + NW / 2;
  const endY = yPad; // top of first-right
  const midX = (startX + endX) / 2;
  const dOut = 25;  // straight segment leaving the bottom of left column
  const dIn = 25;   // straight segment entering the top of right column
  const bend = 50;  // bow depth for each corner (controls tightness)
  const bottomTurnY = startY + dOut;   // where bottom-bend begins/ends
  const topTurnY = endY - dIn;         // where top-bend begins/ends

  // Cubic-Bezier control points are placed BELOW the bottom endpoints (for
  // the bottom bend) and ABOVE the top endpoints (for the top bend) so that
  // each curve enters/exits its endpoints in a purely vertical direction.
  const pathD =
    `M ${startX} ${startY} ` +
    `L ${startX} ${bottomTurnY} ` +
    `C ${startX} ${bottomTurnY + bend}, ${midX} ${bottomTurnY + bend}, ${midX} ${bottomTurnY} ` +
    `L ${midX} ${topTurnY} ` +
    `C ${midX} ${topTurnY - bend}, ${endX} ${topTurnY - bend}, ${endX} ${topTurnY} ` +
    `L ${endX} ${endY}`;

  const connectorLabel = labelOf.get(
    `${ordered[split.left - 1].id}->${ordered[split.left].id}`
  );

  paths.push(
    `<g class="flowchart-edge flowchart-edge-connector">
      <path d="${pathD}" fill="none"/>
      ${emitArrowHead(endX, endY, Math.PI / 2)}
      ${
        connectorLabel
          ? emitEdgeLabel(midX, (bottomTurnY + topTurnY) / 2, connectorLabel)
          : ""
      }
    </g>`
  );

  return {
    width: totalWidth,
    height: totalHeight,
    body: paths.join("\n") + "\n" + shapes.join("\n"),
  };
}

// ============================================================
// dagre-driven renderer (for everything else)
// ============================================================

function renderDagreSvg(
  data: FlowchartData,
  decision: LayoutDecision
): { width: number; height: number; body: string } {
  const isH = decision.isHorizontal;
  const nw = NODE_WIDTH;
  const nh = isH ? NODE_HEIGHT_LR : NODE_HEIGHT_TB;

  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: decision.orientation,
    nodesep: isH ? 38 : 30,
    // ranksep — generous in both directions so edge labels never collide
    // with adjacent boxes. Horizontal labels run beside arrows; vertical
    // labels hang to the right of the arrow.
    ranksep: isH ? 70 : 55,
    marginx: PAD,
    marginy: PAD,
  });
  g.setDefaultEdgeLabel(() => ({}));

  const byId = new Map(data.nodes.map((n) => [n.id, n]));
  for (const node of data.nodes) g.setNode(node.id, { width: nw, height: nh });
  for (const edge of data.edges ?? []) {
    if (byId.has(edge.from) && byId.has(edge.to)) {
      g.setEdge(edge.from, edge.to, { label: edge.label ?? "" });
    }
  }
  dagre.layout(g);

  const graphData = g.graph() as { width: number; height: number };
  const width = Math.max(nw + PAD * 2, graphData.width ?? 0);
  const height = Math.max(nh + PAD * 2, graphData.height ?? 0);

  const shapes: string[] = [];
  for (const id of g.nodes()) {
    const layout = g.node(id) as { x: number; y: number };
    const node = byId.get(id)!;
    shapes.push(emitNode(node, layout.x - nw / 2, layout.y - nh / 2, nw, nh));
  }

  const paths: string[] = [];
  for (const edgeObj of g.edges()) {
    const e = g.edge(edgeObj) as {
      points: Array<{ x: number; y: number }>;
      label?: string;
    };
    if (!e || !e.points || e.points.length === 0) continue;
    const points = e.points;
    const path = `M ${points[0].x} ${points[0].y} ${points
      .slice(1)
      .map((p) => `L ${p.x} ${p.y}`)
      .join(" ")}`;
    const last = points[points.length - 1];
    const prev = points[points.length - 2];
    const angle = Math.atan2(last.y - prev.y, last.x - prev.x);

    let labelEl = "";
    if (e.label) {
      const mid = points[Math.floor(points.length / 2)];
      const segPrev =
        points[Math.max(0, Math.floor(points.length / 2) - 1)];
      const segAngle = Math.atan2(mid.y - segPrev.y, mid.x - segPrev.x);
      const off = EDGE_LABEL_OFFSET;
      const lx = mid.x + Math.cos(segAngle - Math.PI / 2) * off;
      const ly = mid.y + Math.sin(segAngle - Math.PI / 2) * off;
      labelEl = emitEdgeLabel(lx, ly, e.label);
    }

    paths.push(
      `<g class="flowchart-edge">
        <path d="${path}" fill="none"/>
        ${emitArrowHead(last.x, last.y, angle)}
        ${labelEl}
      </g>`
    );
  }

  return {
    width,
    height,
    body: paths.join("\n") + "\n" + shapes.join("\n"),
  };
}

// ============================================================
// Public entry
// ============================================================

export function renderFlowchart(data: FlowchartData): string {
  if (!data || !data.nodes || data.nodes.length === 0) return "";

  const decision = decideLayout(data);

  let svgWidth: number;
  let svgHeight: number;
  let svgBody: string;

  if (decision.mode === "tb-split" && decision.split) {
    const ordered = chainOrder(data.nodes, data.edges ?? []);
    const out = renderSplitChainSvg(ordered, data.edges ?? [], decision.split);
    svgWidth = out.width;
    svgHeight = out.height;
    svgBody = out.body;
  } else {
    const out = renderDagreSvg(data, decision);
    svgWidth = out.width;
    svgHeight = out.height;
    svgBody = out.body;
  }

  const notesHtml = data.notes
    ? `<aside class="flowchart-notes">${DOMPurify.sanitize(
        marked.parse(data.notes, { async: false }) as string
      )}</aside>`
    : "";

  // CSS class drives the wrapper layout (stacked vs side-by-side, balanced
  // 50/50 vs split 2/3+1/3).
  let layoutClass = "";
  if (data.notes) {
    switch (decision.mode) {
      case "lr-stacked":
      case "lr-regular":
        layoutClass = " flowchart-stacked";
        break;
      case "tb-balanced":
        layoutClass = " flowchart-side flowchart-side-balanced";
        break;
      case "tb-split":
        layoutClass = " flowchart-side flowchart-side-split";
        break;
      default:
        layoutClass = " flowchart-side";
    }
  }

  return `<div class="flowchart${layoutClass}">
  <div class="flowchart-svg-wrap">
    <svg viewBox="0 0 ${svgWidth} ${svgHeight}" width="${svgWidth}" height="${svgHeight}" preserveAspectRatio="xMidYMid meet" aria-label="Flowchart diagram" role="img" xmlns="http://www.w3.org/2000/svg">
      ${svgBody}
    </svg>
  </div>
  ${notesHtml}
</div>`;
}
