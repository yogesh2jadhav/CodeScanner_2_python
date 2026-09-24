import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../services/api";
import type { FlowResponse } from "../types/api";
import { EntityLink } from "../components/EntityLink";
import { useEntityPanel } from "../components/EntityPanelContext";
import { EntityPicker } from "../components/EntityPicker";
import { FlowDiagram } from "../components/FlowDiagram";
import { Card, ErrorBox, Notice, Spinner } from "../components/ui";
import { shortName } from "../utils/entityStyle";

export function FlowPage() {
  const [params, setParams] = useSearchParams();
  const id = params.get("id") ?? "";
  const [flow, setFlow] = useState<FlowResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const { open } = useEntityPanel();

  useEffect(() => {
    if (!id) return;
    setBusy(true); setError(null);
    api.flow(id).then(setFlow).catch((e) => { setError(e); setFlow(null); }).finally(() => setBusy(false));
  }, [id]);

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-6">
      <div className="max-w-xl"><EntityPicker value={id} onPick={(v) => setParams({ id: v })} entityType="method"
        placeholder="Method, e.g. CasingService.processClaims" /></div>
      <ErrorBox error={error} />
      {busy && <Spinner />}
      {!id && <p className="text-sm text-slate-500">Pick a method to display its execution flow. Click a call node to follow it.</p>}
      {flow && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-mono text-lg font-semibold">{flow.title}()</h1>
            <span className={`rounded px-2 py-0.5 text-xs font-semibold ${flow.availability === "explicit" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
              {flow.availability}
            </span>
            <button className="text-xs text-blue-600 hover:underline" onClick={() => open(flow.root)}>details</button>
          </div>
          {flow.notes.map((n) => <Notice key={n} tone="warn">{n}</Notice>)}
          {flow.nodes.length > 0 ? (
            <FlowDiagram flow={flow} height={560} onNodeClick={(n) => n.entity_id && n.kind === "call" && setParams({ id: n.entity_id })} />
          ) : (
            <Notice>Flow is unavailable for this entity in the OKF bundle; nothing is inferred.</Notice>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            {flow.text && <Card title="Outline"><pre className="overflow-x-auto font-mono text-xs">{flow.text}</pre></Card>}
            {flow.rules.length > 0 && (
              <Card title="Conditional rules (from flow)">
                <ul className="space-y-2 text-sm">
                  {flow.rules.map((r) => (
                    <li key={r.condition} className="font-mono text-xs">
                      <div><b>IF</b> {r.condition}</div>
                      <div><b>THEN</b> {r.then.join(", ") || "—"}</div>
                      <div><b>ELSE</b> {r.otherwise.join(", ") || "—"}</div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            {flow.call_chains.length > 0 && (
              <Card title="Call chains">
                <ul className="space-y-1">
                  {flow.call_chains.slice(0, 20).map((c) => (
                    <li key={c.join(">")} className="flex flex-wrap items-center gap-1 text-xs">
                      {c.map((cid, i) => (
                        <span key={cid} className="flex items-center gap-1">{i > 0 && "→"}<EntityLink id={cid} label={shortName(cid)} /></span>
                      ))}
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  );
}
