import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../services/api";
import type { SubGraphResponse } from "../types/api";
import { EntityLink } from "../components/EntityLink";
import { useEntityPanel } from "../components/EntityPanelContext";
import { EntityPicker } from "../components/EntityPicker";
import { GraphView } from "../components/GraphView";
import { TypeBadge } from "../components/TypeBadge";
import { ErrorBox, Spinner, inputCls } from "../components/ui";
import { EDGE_COLORS } from "../utils/entityStyle";

export const FILTERS = [
  { key: "calls", label: "Calls", type: "CALLS" },
  { key: "dependencies", label: "Dependencies", type: "DEPENDS_ON" },
  { key: "inheritance", label: "Inheritance", type: "EXTENDS" },
  { key: "implements", label: "Implements", type: "IMPLEMENTS" },
  { key: "uses", label: "Uses", type: "USES" },
  { key: "overrides", label: "Overrides", type: "OVERRIDES" },
  { key: "contains", label: "Contains", type: "CONTAINS" },
];

export function GraphPage() {
  const [params, setParams] = useSearchParams();
  const root = params.get("id") ?? "";
  const [depth, setDepth] = useState(2);
  const [direction, setDirection] = useState<"both" | "in" | "out">("both");
  const [filters, setFilters] = useState<string[]>(["calls", "dependencies", "inheritance", "implements", "uses"]);
  const [data, setData] = useState<SubGraphResponse | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [showExternal, setShowExternal] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const { open } = useEntityPanel();

  useEffect(() => {
    if (!root) return;
    setBusy(true); setError(null);
    api.subgraph(root, depth, filters, direction, showExternal)
      .then((d) => { setData(d); setSelected(root); })
      .catch((e) => { setError(e); setData(null); })
      .finally(() => setBusy(false));
  }, [root, depth, filters, direction, showExternal]);

  const sel = useMemo(() => data?.nodes.find((n) => n.id === selected), [data, selected]);
  const selEdges = useMemo(() => data?.edges.filter((e) => e.source === selected || e.target === selected) ?? [], [data, selected]);
  const toggle = (k: string) => setFilters((f) => (f.includes(k) ? f.filter((x) => x !== k) : [...f, k]));

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-end gap-3 border-b border-slate-200 p-3 dark:border-slate-800">
        <div className="w-full max-w-md"><EntityPicker value={root} onPick={(id) => setParams({ id })} /></div>
        <label className="flex items-center gap-2 text-xs text-slate-500">Depth
          <input aria-label="Depth" type="range" min={1} max={5} value={depth} onChange={(e) => setDepth(Number(e.target.value))} />
          <span className="w-3 font-mono">{depth}</span>
        </label>
        <select aria-label="Direction" className={`${inputCls} py-1 text-xs`} value={direction} onChange={(e) => setDirection(e.target.value as typeof direction)}>
          <option value="both">Both directions</option><option value="out">Outgoing</option><option value="in">Incoming</option>
        </select>
        <fieldset className="flex flex-wrap gap-3 text-xs" aria-label="Relationship filters">
          {FILTERS.map((f) => (
            <label key={f.key} className="flex items-center gap-1">
              <input type="checkbox" checked={filters.includes(f.key)} onChange={() => toggle(f.key)} />
              <span style={{ color: EDGE_COLORS[f.type] }} className="font-medium">{f.label}</span>
            </label>
          ))}
        </fieldset>
        <label className="flex items-center gap-1 text-xs text-slate-500">
          <input type="checkbox" checked={showExternal} onChange={(e) => setShowExternal(e.target.checked)} />
          Show external (JDK / libraries)
        </label>
      </div>
      <div className="relative grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[1fr_300px]">
        <div className="relative min-h-[400px]">
          {!root && <p className="p-6 text-sm text-slate-500">Pick an entity to explore its relationship graph.</p>}
          {busy && <div className="absolute left-4 top-4 z-10"><Spinner /></div>}
          <div className="p-3"><ErrorBox error={error} /></div>
          {data && data.nodes.length > 0 && (
            <div className="absolute inset-0">
              <GraphView nodes={data.nodes} edges={data.edges} rootId={data.root} selectedId={selected}
                onSelect={setSelected} onOpen={(id) => setParams({ id })} />
            </div>
          )}
        </div>
        <aside className="min-h-0 overflow-auto border-l border-slate-200 p-4 text-sm dark:border-slate-800">
          {data && <p className="mb-3 text-xs text-slate-500">{data.nodes.length} nodes · {data.edges.length} edges · click to select, double-click to re-center</p>}
          {data && data.hidden_external > 0 && <p className="mb-2 text-xs text-slate-500">{data.hidden_external} external (JDK/library) nodes hidden.</p>}
          {data?.truncated && <p className="mb-2 text-xs text-amber-600">Graph truncated to the closest {data.nodes.length} nodes; lower the depth or add filters.</p>}
          {sel && (
            <div className="space-y-3">
              <div className="flex items-center gap-2"><TypeBadge type={sel.type} /><span className="font-mono font-semibold">{sel.label}</span></div>
              <p className="break-all font-mono text-xs text-slate-500">{sel.id}</p>
              <button className="text-xs text-blue-600 hover:underline" onClick={() => open(sel.id)}>Open details →</button>
              <ul className="space-y-1">
                {selEdges.map((e) => {
                  const other = e.source === sel.id ? e.target : e.source;
                  const node = data?.nodes.find((n) => n.id === other);
                  return (
                    <li key={`${e.source}-${e.target}-${e.type}`} className="flex items-center gap-2 text-xs">
                      <span className="w-24 shrink-0 font-semibold" style={{ color: EDGE_COLORS[e.type] }}>
                        {e.source === sel.id ? `${e.type} →` : `← ${e.type}`}
                      </span>
                      <EntityLink id={other} label={node?.label ?? other} status={node?.status} />
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
