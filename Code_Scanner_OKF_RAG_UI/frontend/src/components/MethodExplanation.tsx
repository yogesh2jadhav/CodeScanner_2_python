import { useMemo, useState } from "react";
import type { EvidenceItem, MethodExplanationResponse, SourceRef, SourceView } from "../types/api";
import { EntityLink } from "./EntityLink";
import { SourceCode } from "./SourceCode";
import { Notice, ghostButtonCls } from "./ui";

const CERTAINTY: Record<string, string> = {
  observed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  derived: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200",
  unknown: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200",
};
const CALL_STATUS: Record<string, string> = {
  body_inspected: "body inspected", signature_only: "signature only", unresolved: "unresolved", external: "external",
};

/** Evidence content is "N| code" lines; turn it into a SourceView for the viewer. */
function evidenceToSource(item: EvidenceItem): SourceView | null {
  const rows = item.content.split("\n").map((l) => l.match(/^\s*(\d+)\| ?(.*)$/));
  if (!rows.length || rows.some((r) => !r)) return null;
  const start = Number(rows[0]![1]);
  return {
    file: item.file ?? "", start_line: start, decl_line: start, end_line: Number(rows[rows.length - 1]![1]),
    code: rows.map((r) => r![2]).join("\n"), comments: [], conditions: [], notes: [], truncated: false,
  };
}

export function MethodExplanationView({ data }: { data: MethodExplanationResponse }) {
  const evidence = useMemo(() => new Map(data.evidence.map((e) => [e.evidence_id, e])), [data.evidence]);
  const [open, setOpen] = useState<SourceRef | null>(null);
  const [copied, setCopied] = useState(false);
  const x = data.explanation;

  /** Only refs to existing evidence and in-range lines are clickable (the server validated them too). */
  const RefChips = ({ refs }: { refs: SourceRef[] }) => (
    <span className="ml-1 inline-flex flex-wrap gap-1 align-middle">
      {refs.filter((r) => evidence.has(r.evidence_id)).map((r) => {
        const it = evidence.get(r.evidence_id)!;
        const file = (it.file ?? "").split("/").pop();
        const label = r.start_line === r.end_line ? `${file}:${r.start_line}` : `${file}:${r.start_line}-${r.end_line}`;
        return (
          <button key={`${r.evidence_id}:${r.start_line}:${r.end_line}`} type="button" onClick={() => setOpen(r)}
            aria-label={`Show source ${label}`}
            className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-blue-700 hover:bg-blue-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 dark:bg-slate-800 dark:text-blue-300">
            {label}
          </button>
        );
      })}
    </span>
  );
  const Unverified = ({ grounded }: { grounded: boolean }) =>
    grounded ? null : <span className="ml-1 rounded bg-amber-100 px-1 text-[10px] font-semibold text-amber-800" title="No verified source reference">unverified</span>;

  const openItem = open ? evidence.get(open.evidence_id) : null;
  const openSource = openItem ? evidenceToSource(openItem) : null;
  const calleeLink = (callee: string) => {
    const ev = data.evidence.find((e) => e.entity_id === callee || e.title.includes(callee));
    return ev?.entity_id ? <EntityLink id={ev.entity_id} label={callee.split(":").pop()} /> : <code className="text-xs">{callee}</code>;
  };

  return (
    <div className="space-y-4 text-sm" data-testid="method-explanation">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <span className="font-mono">{data.method_signature}</span>
        {data.model && <span>· {data.model.model} · {data.model.prompt_version}</span>}
        {data.cached && <span className="rounded bg-amber-100 px-1.5 text-amber-800">cached</span>}
        {data.markdown && (
          <button type="button" className={`${ghostButtonCls} ml-auto`} onClick={() => {
            navigator.clipboard?.writeText(data.markdown).then(() => setCopied(true)).catch(() => setCopied(false));
          }}>{copied ? "Copied" : "Copy Markdown"}</button>
        )}
      </div>

      {data.warnings.length > 0 && (
        <div role="status" aria-label="Warnings" className="space-y-1">
          {data.warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
        </div>
      )}

      {x ? (
        <>
          <section>
            <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">Summary</h4>
            <p>{x.summary}{x.purpose_is_inferred && <span className="ml-1 text-xs text-slate-500">(purpose inferred from code)</span>}</p>
          </section>
          {x.inputs_outputs.length > 0 && (
            <section>
              <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">Inputs and outputs</h4>
              <ul className="space-y-0.5">{x.inputs_outputs.map((io) => (
                <li key={`${io.role}:${io.name}`}><span className="text-[10px] uppercase text-slate-500">{io.role}</span> <code className="text-xs">{io.name}</code> — {io.description}</li>
              ))}</ul>
            </section>
          )}
          <section>
            <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">Execution flow</h4>
            <ol className="space-y-2" data-testid="execution-steps">{x.execution_steps.map((s) => (
              <li key={s.step_number} className="rounded-md border border-slate-200 p-2 dark:border-slate-800">
                <div className="flex flex-wrap items-center gap-1">
                  <span className="font-semibold">{s.step_number}. {s.title}</span>
                  <span className={`rounded px-1 text-[10px] ${CERTAINTY[s.certainty]}`}>{s.certainty}</span>
                  <Unverified grounded={s.grounded} /><RefChips refs={s.source_refs} />
                </div>
                <p className="mt-1 text-slate-700 dark:text-slate-300">{s.description}</p>
              </li>
            ))}</ol>
          </section>
          {x.branches.length > 0 && (
            <section>
              <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">Branches and conditions</h4>
              <ul className="space-y-1">{x.branches.map((b, i) => (
                <li key={i}><b>IF</b> <code className="text-xs">{b.condition}</code> <b>THEN</b> {b.when_true}
                  {b.when_false && <> <b>ELSE</b> {b.when_false}</>}<Unverified grounded={b.grounded} /><RefChips refs={b.source_refs} /></li>
              ))}</ul>
            </section>
          )}
          {([["Data transformations", x.data_transformations], ["Side effects", x.side_effects],
            ["Exceptions and failure paths", x.exceptions]] as const).map(([title, items]) => items.length > 0 && (
            <section key={title}>
              <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">{title}</h4>
              <ul className="list-disc space-y-0.5 pl-5">{items.map((it, i) => (
                <li key={i}>{it.description}<Unverified grounded={it.grounded} /><RefChips refs={it.source_refs} /></li>
              ))}</ul>
            </section>
          ))}
          {x.calls.length > 0 && (
            <section>
              <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">Calls</h4>
              <ul className="space-y-1" data-testid="calls">{x.calls.map((c, i) => (
                <li key={i} className="flex flex-wrap items-center gap-1">
                  {calleeLink(c.callee)}
                  <span className="rounded bg-slate-100 px-1 text-[10px] dark:bg-slate-800">{CALL_STATUS[c.evidence_status]}</span>
                  <span>{c.summary}</span><RefChips refs={c.source_refs} />
                </li>
              ))}</ul>
            </section>
          )}
          {x.uncertainties.length > 0 && (
            <section aria-label="Uncertainties">
              <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">Uncertainties</h4>
              <ul className="list-disc pl-5 text-slate-600 dark:text-slate-400">{x.uncertainties.map((u) => <li key={u}>{u}</li>)}</ul>
            </section>
          )}
        </>
      ) : (
        <section>
          <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">Deterministic facts (no model output)</h4>
          <ul className="list-disc space-y-0.5 pl-5">
            {data.facts.comments.map((c) => <li key={`c${c.start_line}`}>L{c.start_line}: {c.text}</li>)}
            {data.facts.conditions.map((c) => <li key={`k${c.line}${c.kind}`}>L{c.line} {c.kind}: <code className="text-xs">{c.expression}</code></li>)}
          </ul>
        </section>
      )}

      {openItem && open && (
        <section aria-label="Cited source" className="rounded-md border border-blue-200 p-2 dark:border-blue-900">
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="font-semibold">{openItem.evidence_id} · {openItem.title}</span>
            <button type="button" className="text-slate-500 hover:underline" onClick={() => setOpen(null)}>close</button>
          </div>
          {openSource
            ? <SourceCode source={openSource} maxHeight={320} highlight={[open.start_line, open.end_line]} />
            : <pre className="whitespace-pre-wrap text-xs">{openItem.content}</pre>}
        </section>
      )}

      <details>
        <summary className="cursor-pointer text-xs font-semibold uppercase text-slate-500">Evidence ({data.evidence.length})</summary>
        <ul className="mt-1 space-y-0.5 text-xs" data-testid="explain-evidence">{data.evidence.map((e) => (
          <li key={e.evidence_id} className="flex flex-wrap gap-2">
            <span className="font-mono text-slate-400">{e.evidence_id}</span>
            <span className="text-slate-500">{e.kind}</span>
            {e.entity_id ? <EntityLink id={e.entity_id} label={e.title} status={e.status} /> : <span>{e.title}</span>}
            {e.status !== "resolved" && <span className="text-amber-700">{e.status}</span>}
          </li>
        ))}</ul>
      </details>
      <p className="font-mono text-[10px] text-slate-400">
        request_id={data.request_id} · {Object.entries(data.timings_ms).map(([k, v]) => `${k}=${v < 1000 ? `${v}ms` : `${(v / 1000).toFixed(1)}s`}`).join(" · ")}
        {data.estimated_prompt_tokens ? ` · ~${data.estimated_prompt_tokens} prompt tokens` : ""}
      </p>
    </div>
  );
}
