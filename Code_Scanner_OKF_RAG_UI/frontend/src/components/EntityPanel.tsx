import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import type { EntityDetail, EntityRelationships, FlowResponse, SourceResponse, SourceView } from "../types/api";
import { useEntityPanel } from "./EntityPanelContext";
import { EntityLink } from "./EntityLink";
import { ExplainPanel } from "./ExplainPanel";
import { FlowDiagram } from "./FlowDiagram";
import { Markdown } from "./Markdown";
import { RelationshipList } from "./RelationshipList";
import { SourceCode } from "./SourceCode";
import { TypeBadge } from "./TypeBadge";
import { ErrorBox, Notice, Spinner, ghostButtonCls } from "./ui";

type Tab = "overview" | "explain" | "source" | "document" | "relationships" | "flow";

/** Slide-over with Class / Method / Source / Relationships / Flow for any entity. */
export function EntityPanel() {
  const { entityId, close, open } = useEntityPanel();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [rels, setRels] = useState<EntityRelationships | null>(null);
  const [flow, setFlow] = useState<FlowResponse | null>(null);
  const [source, setSource] = useState<SourceResponse | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!entityId) return;
    let cancelled = false;
    setDetail(null); setRels(null); setFlow(null); setSource(null); setError(null); setTab("overview");
    Promise.all([api.entity(entityId), api.relationships(entityId)])
      .then(([d, r]) => { if (!cancelled) { setDetail(d); setRels(r); } })
      .catch((e) => { if (!cancelled) setError(e); });
    return () => { cancelled = true; };
  }, [entityId]);

  useEffect(() => {
    if (tab === "flow" && entityId && !flow) api.flow(entityId).then(setFlow).catch(setError);
    if (tab === "source" && entityId && !source) api.source(entityId).then(setSource).catch(setError);
  }, [tab, entityId, flow, source]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  if (!entityId) return null;
  const e = detail?.entity;
  const go = (path: string) => { navigate(`${path}?id=${encodeURIComponent(entityId)}`); close(); };

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-label="Entity details">
      <div className="absolute inset-0 bg-slate-900/30" onClick={close} />
      <aside className="relative flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl dark:bg-slate-950">
        <header className="border-b border-slate-200 px-5 py-3 dark:border-slate-800">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <TypeBadge type={e?.type} />
                <h2 className="truncate font-mono text-base font-semibold">{e?.title ?? entityId}</h2>
              </div>
              <p className="mt-0.5 truncate font-mono text-xs text-slate-500">{entityId}</p>
            </div>
            <button onClick={close} className="rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Close">✕</button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className={ghostButtonCls} onClick={() => go("/explorer")}>Open in Explorer</button>
            <button className={ghostButtonCls} onClick={() => go("/graph")}>Open in Graph</button>
            <button className={ghostButtonCls} onClick={() => go("/flow")}>Open in Flow</button>
          </div>
          <nav className="mt-3 flex gap-1 text-sm" role="tablist">
            {(["overview", ...(e?.type === "method" ? ["explain"] : []), "source", "document", "relationships", "flow"] as Tab[]).map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                className={`rounded-md px-3 py-1 capitalize ${tab === t ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"}`}>
                {t}
              </button>
            ))}
          </nav>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <ErrorBox error={error} />
          {!detail && !error && <Spinner />}
          {detail && tab === "overview" && (
            <dl className="grid grid-cols-[110px_1fr] gap-x-3 gap-y-2 text-sm">
              {detail.owner && (<><dt className="text-slate-500">{detail.entity.type === "method" ? "Class" : "Package"}</dt>
                <dd><EntityLink id={detail.owner.id} label={detail.owner.title} type={detail.owner.type} showType /></dd></>)}
              {e?.method_name && (<><dt className="text-slate-500">Method</dt><dd className="font-mono">{e.method_name}</dd></>)}
              {detail.signature && (<><dt className="text-slate-500">Signature</dt><dd className="font-mono text-xs">{detail.signature}</dd></>)}
              {e?.package && (<><dt className="text-slate-500">Package</dt><dd className="font-mono text-xs">{e.package}</dd></>)}
              <dt className="text-slate-500">Source</dt>
              <dd className="font-mono text-xs">{e?.source_file ? `${e.source_file}${e.source_line ? `:${e.source_line}` : ""}` : "—"}</dd>
              <dt className="text-slate-500">OKF document</dt><dd className="font-mono text-xs">{e?.document ?? "—"}</dd>
              {e?.status === "unresolved" && (<><dt className="text-slate-500">Status</dt><dd className="text-red-600">unresolved reference (no OKF document)</dd></>)}
              {e?.summary && (<><dt className="text-slate-500">Summary</dt><dd>{e.summary}</dd></>)}
              {detail.members.length > 0 && (<><dt className="text-slate-500">Members</dt>
                <dd className="flex flex-col gap-0.5">{detail.members.map((m) =>
                  <EntityLink key={m.id} id={m.id} label={m.method_name ?? m.title} type={m.type} showType />)}</dd></>)}
            </dl>
          )}
          {detail && tab === "document" && (detail.content ? <Markdown linkTargets={detail.link_targets}>{detail.content}</Markdown> : <p className="text-sm text-slate-500">No document content.</p>)}
          {rels && tab === "relationships" && <RelationshipList rels={rels} />}
          {tab === "explain" && e?.type === "method" && <ExplainPanel key={entityId} methodId={entityId} />}
          {tab === "source" && !source && !error && <Spinner />}
          {tab === "source" && source && (source.available
            ? <SourceCode source={source as SourceView} maxHeight={640} />
            : <Notice>{source.reason}</Notice>)}
          {tab === "flow" && !flow && !error && <Spinner />}
          {tab === "flow" && flow && (
            <div className="space-y-3">
              <Notice tone={flow.availability === "explicit" ? "info" : "warn"}>
                Flow availability: <b>{flow.availability}</b>{flow.notes.length ? ` — ${flow.notes.join(" ")}` : ""}
              </Notice>
              {flow.nodes.length > 0 && <FlowDiagram flow={flow} height={420} onNodeClick={(n) => n.entity_id && open(n.entity_id)} />}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
