import { useRef, useState } from "react";
import { ApiError, api } from "../services/api";
import type { MethodExplanationResponse } from "../types/api";
import { MethodExplanationView } from "./MethodExplanation";
import { ErrorBox, Spinner, buttonCls, ghostButtonCls, inputCls } from "./ui";

/** Explain Method workflow for one method/constructor entity. */
export function ExplainPanel({ methodId }: { methodId: string }) {
  const [depth, setDepth] = useState(1);
  const [detail, setDetail] = useState<"detailed" | "summary">("detailed");
  const [callers, setCallers] = useState(false);
  const [data, setData] = useState<MethodExplanationResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const ctrl = useRef<AbortController | null>(null);

  const run = async (opts: { force?: boolean; evidenceOnly?: boolean } = {}) => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setBusy(true); setError(null);
    try {
      setData(await api.explainMethod(methodId, {
        detail, max_callee_depth: depth, include_caller_context: callers,
        force_refresh: !!opts.force, use_llm: !opts.evidenceOnly,
      }, c.signal));
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) setError(e);
    } finally {
      if (ctrl.current === c) setBusy(false);
    }
  };

  const errMsg = error instanceof ApiError
    ? `${error.message}${error.requestId ? `\n(request_id=${error.requestId})` : ""}` : error;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2 text-xs">
        <label className="flex flex-col gap-1 text-slate-500">Detail
          <select aria-label="Detail" className={`${inputCls} py-1 text-xs`} value={detail}
            onChange={(e) => setDetail(e.target.value as "detailed" | "summary")}>
            <option value="detailed">Detailed</option><option value="summary">Summary</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-slate-500">Callee depth
          <select aria-label="Callee depth" className={`${inputCls} py-1 text-xs`} value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}>
            {[0, 1, 2].map((d) => <option key={d} value={d}>{d === 0 ? "0 (this method only)" : d}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-1 pb-2 text-slate-600 dark:text-slate-300">
          <input type="checkbox" checked={callers} onChange={(e) => setCallers(e.target.checked)} /> Include callers
        </label>
        <button type="button" className={buttonCls} disabled={busy} onClick={() => run()}>Explain method</button>
        <button type="button" className={ghostButtonCls} disabled={busy} onClick={() => run({ evidenceOnly: true })}>Evidence only</button>
        {busy && <button type="button" className={ghostButtonCls} onClick={() => { ctrl.current?.abort(); setBusy(false); }}>Cancel</button>}
        {data && !busy && <button type="button" className={ghostButtonCls} onClick={() => run({ force: true })}>Regenerate</button>}
      </div>
      {busy && <Spinner label="Collecting evidence and asking the local model (this can take minutes on CPU)…" />}
      {error != null && (
        <div className="space-y-2">
          <ErrorBox error={errMsg} />
          <button type="button" className={ghostButtonCls} onClick={() => run()}>Retry</button>
        </div>
      )}
      {!busy && !error && !data && <p className="text-sm text-slate-500">Explains this method step by step from its source code, with every statement linked to the lines it is based on.</p>}
      {data && <MethodExplanationView data={data} />}
    </div>
  );
}
