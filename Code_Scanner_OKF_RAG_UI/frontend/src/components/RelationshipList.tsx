import type { EntityRelationships, RelationshipEntry } from "../types/api";
import { EntityLink } from "./EntityLink";

function group(entries: RelationshipEntry[]) {
  const m = new Map<string, RelationshipEntry[]>();
  for (const e of entries) m.set(e.type, [...(m.get(e.type) ?? []), e]);
  return [...m.entries()].sort(([a], [b]) => a.localeCompare(b));
}

const INCOMING_LABEL: Record<string, string> = {
  CALLS: "Called by",
  CONTAINS: "Contained in",
  EXTENDS: "Extended by",
  IMPLEMENTS: "Implemented by",
  DEPENDS_ON: "Depended on by",
  USES: "Used by",
  REFERENCES: "Referenced by",
};

export function RelationshipList({ rels }: { rels: EntityRelationships }) {
  const sections = [
    ...group(rels.outgoing).map(([t, es]) => ({ title: t, es })),
    ...group(rels.incoming).map(([t, es]) => ({ title: INCOMING_LABEL[t] ?? `${t} (incoming)`, es })),
  ];
  if (!sections.length) return <p className="text-sm text-slate-500">No relationships recorded.</p>;
  return (
    <div className="space-y-3">
      {sections.map((s) => (
        <div key={s.title}>
          <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{s.title} ({s.es.length})</h4>
          <ul className="space-y-0.5">
            {s.es.map((e) => (
              <li key={`${e.source}-${e.target}-${e.type}`} className="flex items-center gap-2">
                <EntityLink id={e.other.id} label={e.other.title} type={e.other.type} status={e.other.status} showType />
                {e.status === "unresolved" && <span className="text-[10px] font-semibold text-red-600">unresolved</span>}
                {e.status === "external" && <span className="text-[10px] font-semibold text-zinc-500">external</span>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
