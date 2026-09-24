import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../services/api";
import type { EntityDetail, EntityRelationships, TreeNode } from "../types/api";
import { Markdown } from "../components/Markdown";
import { RelationshipList } from "../components/RelationshipList";
import { TypeBadge } from "../components/TypeBadge";
import { ErrorBox, Spinner, ghostButtonCls, inputCls } from "../components/ui";

function filterTree(nodes: TreeNode[], q: string): TreeNode[] {
  if (!q) return nodes;
  const lq = q.toLowerCase();
  return nodes.flatMap((n) => {
    const kids = filterTree(n.children, q);
    return n.title.toLowerCase().includes(lq) || kids.length ? [{ ...n, children: kids.length ? kids : n.children }] : [];
  });
}

function TreeItem({ node, depth, selected, onSelect, expanded, toggle }: {
  node: TreeNode; depth: number; selected: string | null; onSelect: (id: string) => void;
  expanded: Set<string>; toggle: (id: string) => void;
}) {
  const isOpen = expanded.has(node.id);
  const hasKids = node.children.length > 0;
  const selectable = node.type !== "group" && (node.type !== "package" || node.has_document);
  return (
    <li>
      <div className={`flex items-center gap-1 rounded px-1 py-0.5 ${selected === node.id ? "bg-blue-100 dark:bg-blue-950" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`}
        style={{ paddingLeft: depth * 12 + 4 }}>
        <button className="w-4 text-xs text-slate-400" onClick={() => hasKids && toggle(node.id)} aria-label={isOpen ? "Collapse" : "Expand"}>
          {hasKids ? (isOpen ? "▾" : "▸") : ""}
        </button>
        <button className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-sm"
          onClick={() => { if (selectable) onSelect(node.id); if (hasKids && !isOpen) toggle(node.id); }}>
          <TypeBadge type={node.type === "group" ? "document" : node.type} />
          <span className="truncate font-mono text-xs">{node.title}</span>
        </button>
      </div>
      {isOpen && hasKids && (
        <ul>{node.children.map((c) => <TreeItem key={c.id} node={c} depth={depth + 1} selected={selected} onSelect={onSelect} expanded={expanded} toggle={toggle} />)}</ul>
      )}
    </li>
  );
}

export function ExplorerPage() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("id");
  const navigate = useNavigate();
  const [tree, setTree] = useState<TreeNode[] | null>(null);
  const [filter, setFilter] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [rels, setRels] = useState<EntityRelationships | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.tree().then((t) => { setTree(t); setExpanded(new Set(t.slice(0, 1).map((n) => n.id))); }).catch(setError);
  }, []);

  useEffect(() => {
    if (!selected) return;
    setDetail(null); setRels(null);
    Promise.all([api.entity(selected), api.relationships(selected)])
      .then(([d, r]) => {
        setDetail(d); setRels(r);
        // Reveal the selection in the tree.
        setExpanded((prev) => new Set([...prev, ...(d.entity.package ? [d.entity.package] : []), ...(d.owner ? [d.owner.id] : []), d.entity.id]));
      })
      .catch(setError);
  }, [selected]);

  const visible = useMemo(() => filterTree(tree ?? [], filter), [tree, filter]);
  const toggle = (id: string) => setExpanded((prev) => {
    const n = new Set(prev);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });
  const select = (id: string) => setParams({ id });
  const e = detail?.entity;

  return (
    <div className="grid h-full min-h-0 grid-cols-1 md:grid-cols-[280px_1fr_320px]">
      <aside className="flex min-h-0 flex-col border-r border-slate-200 dark:border-slate-800" aria-label="Packages, classes and methods">
        <div className="p-2"><input className={`${inputCls} w-full`} placeholder="Filter…" value={filter} onChange={(ev) => {
          setFilter(ev.target.value);
          if (ev.target.value && tree) setExpanded(new Set(tree.flatMap((p) => [p.id, ...p.children.map((c) => c.id)])));
        }} /></div>
        <div className="min-h-0 flex-1 overflow-auto px-1 pb-4">
          {!tree && !error && <div className="p-2"><Spinner /></div>}
          <ul data-testid="explorer-tree">{visible.map((n) => <TreeItem key={n.id} node={n} depth={0} selected={selected} onSelect={select} expanded={expanded} toggle={toggle} />)}</ul>
        </div>
      </aside>

      <section className="min-h-0 overflow-auto p-4 md:p-6">
        <ErrorBox error={error} />
        {!selected && <p className="text-sm text-slate-500">Select a package, class or method on the left.</p>}
        {selected && !detail && !error && <Spinner />}
        {detail && e && (
          <div className="space-y-4">
            <div>
              <div className="flex items-center gap-2"><TypeBadge type={e.type} /><h1 className="font-mono text-lg font-semibold">{e.title}</h1></div>
              <p className="font-mono text-xs text-slate-500">{e.id}</p>
              {detail.signature && <pre className="mt-2 overflow-x-auto rounded bg-slate-100 p-2 font-mono text-xs dark:bg-slate-900">{detail.signature}</pre>}
              <p className="mt-2 text-xs text-slate-500">
                Source: <span className="font-mono">{e.source_file ?? "—"}{e.source_line ? `:${e.source_line}` : ""}</span>
                {" · "}OKF: <span className="font-mono">{e.document ?? "—"}</span>
              </p>
              <div className="mt-2 flex gap-2">
                <button className={ghostButtonCls} onClick={() => navigate(`/graph?id=${encodeURIComponent(e.id)}`)}>Graph</button>
                {detail.flow_available && <button className={ghostButtonCls} onClick={() => navigate(`/flow?id=${encodeURIComponent(e.id)}`)}>Flow</button>}
              </div>
            </div>
            {detail.content ? <Markdown className="border-t border-slate-200 pt-4 dark:border-slate-800" linkTargets={detail.link_targets}>{detail.content}</Markdown>
              : <p className="text-sm text-slate-500">No document content.</p>}
          </div>
        )}
      </section>

      <aside className="min-h-0 overflow-auto border-l border-slate-200 p-4 dark:border-slate-800" aria-label="Relationships">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Knowledge / Relations</h2>
        {rels ? <RelationshipList rels={rels} /> : <p className="text-sm text-slate-500">—</p>}
      </aside>
    </div>
  );
}
