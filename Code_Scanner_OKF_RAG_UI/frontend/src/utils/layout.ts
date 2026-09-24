import dagre from "@dagrejs/dagre";

export interface Sized {
  id: string;
  width: number;
  height: number;
}

/** Layered (dagre) layout: call graphs and flows read naturally top-to-bottom. */
export function layoutGraph(nodes: Sized[], edges: { source: string; target: string }[], direction: "TB" | "LR" = "TB") {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 36, ranksep: 64, marginx: 16, marginy: 16 });
  nodes.forEach((n) => g.setNode(n.id, { width: n.width, height: n.height }));
  edges.forEach((e) => {
    if (g.hasNode(e.source) && g.hasNode(e.target)) g.setEdge(e.source, e.target);
  });
  dagre.layout(g);
  const positions: Record<string, { x: number; y: number }> = {};
  nodes.forEach((n) => {
    const p = g.node(n.id);
    positions[n.id] = { x: (p?.x ?? 0) - n.width / 2, y: (p?.y ?? 0) - n.height / 2 };
  });
  return positions;
}
