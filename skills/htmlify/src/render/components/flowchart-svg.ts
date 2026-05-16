import dagre from "dagre";
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
}

// Render a flowchart as inline SVG using dagre for layout. Self-contained:
// no client-side JS, no external SVG renderer. Static, accessible.
//
// Constants tuned to look good with the design system (Charter typography,
// copper accent, hairline borders).
const NODE_WIDTH = 160;
const NODE_HEIGHT = 50;
const PAD = 30;
const STROKE = "rgba(26, 22, 18, 0.4)";
const STROKE_EMPHASIS = "#b06a3b";  // copper
const TEXT = "#1a1612";
const TEXT_FILL_NORMAL = "#fdfaf6";
const TEXT_FILL_EMPHASIS = "#f4ede3";
const FONT = "ui-sans-serif, system-ui, sans-serif";

export function renderFlowchart(data: FlowchartData): string {
  if (!data || !data.nodes || data.nodes.length === 0) return "";

  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: data.orientation ?? "TB",
    nodesep: 30,
    ranksep: 40,
    marginx: PAD,
    marginy: PAD,
  });
  g.setDefaultEdgeLabel(() => ({}));

  const nodeMap = new Map(data.nodes.map((n) => [n.id, n]));

  for (const node of data.nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of data.edges ?? []) {
    if (nodeMap.has(edge.from) && nodeMap.has(edge.to)) {
      g.setEdge(edge.from, edge.to, { label: edge.label ?? "" });
    }
  }

  dagre.layout(g);

  const graphData = g.graph() as { width: number; height: number };
  const width = Math.max(NODE_WIDTH + PAD * 2, graphData.width ?? 0);
  const height = Math.max(NODE_HEIGHT + PAD * 2, graphData.height ?? 0);

  const nodeShapes: string[] = [];
  for (const id of g.nodes()) {
    const layout = g.node(id) as { x: number; y: number };
    const node = nodeMap.get(id)!;
    const x = layout.x - NODE_WIDTH / 2;
    const y = layout.y - NODE_HEIGHT / 2;
    const stroke = node.emphasis ? STROKE_EMPHASIS : STROKE;
    const fill = node.emphasis ? TEXT_FILL_EMPHASIS : TEXT_FILL_NORMAL;
    const strokeWidth = node.emphasis ? 1.5 : 1;
    const rx = node.shape === "round" ? 18 : 4;
    nodeShapes.push(
      `<g class="flowchart-node${node.emphasis ? " flowchart-node-emphasis" : ""}">
        <rect x="${x}" y="${y}" width="${NODE_WIDTH}" height="${NODE_HEIGHT}" rx="${rx}" ry="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/>
        <text x="${layout.x}" y="${layout.y}" text-anchor="middle" dominant-baseline="middle" fill="${TEXT}" font-family="${FONT}" font-size="13">${esc(node.label)}</text>
      </g>`
    );
  }

  const edgePaths: string[] = [];
  for (const edgeObj of g.edges()) {
    const e = g.edge(edgeObj) as { points: Array<{ x: number; y: number }>; label?: string };
    if (!e || !e.points || e.points.length === 0) continue;
    const points = e.points;
    const path = `M ${points[0].x} ${points[0].y} ${points
      .slice(1)
      .map((p) => `L ${p.x} ${p.y}`)
      .join(" ")}`;
    // arrow head
    const last = points[points.length - 1];
    const prev = points[points.length - 2];
    const angle = Math.atan2(last.y - prev.y, last.x - prev.x);
    const arrowSize = 8;
    const ax1 = last.x - arrowSize * Math.cos(angle - Math.PI / 6);
    const ay1 = last.y - arrowSize * Math.sin(angle - Math.PI / 6);
    const ax2 = last.x - arrowSize * Math.cos(angle + Math.PI / 6);
    const ay2 = last.y - arrowSize * Math.sin(angle + Math.PI / 6);
    const labelEl = e.label
      ? (() => {
          // Place label at midpoint
          const mid = points[Math.floor(points.length / 2)];
          return `<text x="${mid.x}" y="${mid.y - 6}" text-anchor="middle" fill="${TEXT}" font-family="${FONT}" font-size="11" class="flowchart-edge-label">${esc(e.label)}</text>`;
        })()
      : "";
    edgePaths.push(
      `<g class="flowchart-edge">
        <path d="${path}" fill="none" stroke="${STROKE}" stroke-width="1"/>
        <polygon points="${last.x},${last.y} ${ax1},${ay1} ${ax2},${ay2}" fill="${STROKE}"/>
        ${labelEl}
      </g>`
    );
  }

  return `<div class="flowchart">
  <svg viewBox="0 0 ${width} ${height}" width="100%" preserveAspectRatio="xMinYMin meet" aria-label="Flowchart diagram" role="img" xmlns="http://www.w3.org/2000/svg">
    ${edgePaths.join("\n")}
    ${nodeShapes.join("\n")}
  </svg>
</div>`;
}
