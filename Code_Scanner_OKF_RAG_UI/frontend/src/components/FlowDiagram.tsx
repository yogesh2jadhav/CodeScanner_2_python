import { useMemo } from "react";
import { Background, Controls, MarkerType, ReactFlow, ReactFlowProvider, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Flow, FlowNode } from "../types/api";
import { layoutGraph } from "../utils/layout";

const KIND_STYLE: Record<FlowNode["kind"], { bg: string; border: string; radius: number | string }> = {
  start: { bg: "#dbeafe", border: "#2563eb", radius: 999 },
  end: { bg: "#e2e8f0", border: "#64748b", radius: 999 },
  call: { bg: "#ecfdf5", border: "#059669", radius: 6 },
  condition: { bg: "#fef3c7", border: "#d97706", radius: 2 },
  loop: { bg: "#ede9fe", border: "#7c3aed", radius: 6 },
  statement: { bg: "#f8fafc", border: "#94a3b8", radius: 4 },
  return: { bg: "#f1f5f9", border: "#475569", radius: 4 },
  throw: { bg: "#fee2e2", border: "#dc2626", radius: 4 },
  merge: { bg: "#cbd5e1", border: "#94a3b8", radius: 999 },
};

interface Props {
  flow: Flow;
  onNodeClick?: (node: FlowNode) => void;
  height?: number | string;
}

export function FlowDiagram({ flow, onNodeClick, height = 480 }: Props) {
  const { nodes, edges } = useMemo(() => {
    const size = (n: FlowNode) => (n.kind === "merge" ? { width: 14, height: 14 } : { width: 220, height: n.kind === "condition" ? 52 : 40 });
    const pos = layoutGraph(flow.nodes.map((n) => ({ id: n.id, ...size(n) })), flow.edges, "TB");
    const nodes: Node[] = flow.nodes.map((n) => {
      const s = KIND_STYLE[n.kind];
      const clickable = !!n.entity_id && n.kind === "call";
      return {
        id: n.id,
        position: pos[n.id],
        data: {
          label: n.kind === "merge" ? "" : (
            <div className="leading-tight" title={n.entity_id ?? n.label}>
              <div className="text-[9px] font-semibold uppercase tracking-wide opacity-60">
                {n.kind === "condition" ? "if" : n.kind}
                {n.status === "unresolved" ? " · unresolved" : ""}
              </div>
              <div className={`text-[11px] font-medium ${clickable ? "text-blue-700 underline" : ""}`}>{n.label}</div>
            </div>
          ),
        },
        style: {
          ...size(n),
          background: s.bg,
          color: "#0f172a",
          border: `1.5px ${n.status === "unresolved" ? "dashed" : "solid"} ${s.border}`,
          borderRadius: s.radius,
          padding: n.kind === "merge" ? 0 : "4px 8px",
          cursor: clickable ? "pointer" : "default",
        },
      };
    });
    const edges: Edge[] = flow.edges.map((e, i) => ({
      id: `${e.source}-${e.target}-${i}`,
      source: e.source,
      target: e.target,
      label: e.label && e.label !== "next" ? e.label : undefined,
      labelStyle: { fontSize: 10, fontWeight: 700, fill: e.label === "yes" ? "#059669" : e.label === "no" ? "#dc2626" : "#475569" },
      markerEnd: { type: MarkerType.ArrowClosed },
      animated: e.label === "repeat",
    }));
    return { nodes, edges };
  }, [flow]);

  return (
    <div style={{ height }} className="w-full rounded-md border border-slate-200 dark:border-slate-800" data-testid="flow-diagram">
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          colorMode="system"
          nodesConnectable={false}
          proOptions={{ hideAttribution: true }}
          onNodeClick={(_, n) => {
            const fn = flow.nodes.find((x) => x.id === n.id);
            if (fn) onNodeClick?.(fn);
          }}
        >
          <Background gap={16} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
