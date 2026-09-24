import { useMemo } from "react";
import {
  Background, Controls, MarkerType, MiniMap, Position, ReactFlow, ReactFlowProvider,
  type Edge, type Node, type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphEdge, GraphNode } from "../types/api";
import { EDGE_COLORS, typeStyle } from "../utils/entityStyle";
import { layoutGraph } from "../utils/layout";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  rootId?: string;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  onOpen?: (id: string) => void;
  direction?: "TB" | "LR";
  height?: number | string;
}

const W = 190;
const H = 44;

export function GraphView({ nodes, edges, rootId, selectedId, onSelect, onOpen, direction = "LR", height = "100%" }: Props) {
  const { rfNodes, rfEdges } = useMemo(() => {
    const pos = layoutGraph(nodes.map((n) => ({ id: n.id, width: W, height: H })), edges, direction);
    const rfNodes: Node[] = nodes.map((n) => {
      const s = typeStyle(n.type);
      const isRoot = n.id === rootId;
      const isSel = n.id === selectedId;
      return {
        id: n.id,
        position: pos[n.id],
        // Handles must follow the layout direction or edges loop around nodes.
        sourcePosition: direction === "LR" ? Position.Right : Position.Bottom,
        targetPosition: direction === "LR" ? Position.Left : Position.Top,
        data: { label: (
          <div className="flex flex-col leading-tight" title={n.id}>
            <span className="truncate text-[11px] font-semibold">{n.label}</span>
            <span className="text-[9px] uppercase opacity-70">{n.type}{n.status === "unresolved" ? " · unresolved" : ""}</span>
          </div>
        ) },
        style: {
          width: W,
          border: `${isSel || isRoot ? 2 : 1}px ${n.status === "unresolved" ? "dashed" : "solid"} ${s.node}`,
          borderRadius: 8,
          background: isRoot ? `${s.node}22` : "var(--ck-node-bg, #fff)",
          boxShadow: isSel ? `0 0 0 3px ${s.node}44` : undefined,
          padding: "4px 8px",
          textAlign: "left",
        },
      };
    });
    const rfEdges: Edge[] = edges.map((e, i) => {
      const color = EDGE_COLORS[e.type] ?? "#94a3b8";
      return {
        id: `${e.source}->${e.target}:${e.type}:${i}`,
        source: e.source,
        target: e.target,
        label: e.type,
        labelStyle: { fontSize: 9, fill: color, fontWeight: 600 },
        labelBgStyle: { fillOpacity: 0.85 },
        style: { stroke: color, strokeDasharray: e.status === "unresolved" ? "4 3" : undefined },
        markerEnd: { type: MarkerType.ArrowClosed, color },
      };
    });
    return { rfNodes, rfEdges };
  }, [nodes, edges, rootId, selectedId, direction]);

  const onClick: NodeMouseHandler = (_, node) => onSelect?.(node.id);
  const onDbl: NodeMouseHandler = (_, node) => onOpen?.(node.id);

  return (
    <div style={{ height }} className="ck-graph w-full [--ck-node-bg:#fff] dark:[--ck-node-bg:#0f172a]" data-testid="graph-view">
      <ReactFlowProvider>
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          onNodeClick={onClick}
          onNodeDoubleClick={onDbl}
          fitView
          colorMode="system"
          minZoom={0.1}
          nodesConnectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} size={1} />
          <Controls showInteractive={false} />
          <MiniMap pannable zoomable nodeColor={(n) => typeStyle(nodes.find((x) => x.id === n.id)?.type).node} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
