import { useState } from "react";
import { api } from "../services/api";
import type { SearchMode, SearchResponse } from "../types/api";
import { EntityLink } from "../components/EntityLink";
import { TypeBadge } from "../components/TypeBadge";
import { ErrorBox, Notice, Spinner, buttonCls, inputCls } from "../components/ui";

const TYPES = ["", "class", "interface", "enum", "method", "field", "package", "document"];

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [type, setType] = useState("");
  const [pkg, setPkg] = useState("");
  const [topK, setTopK] = useState(20);
  const [res, setRes] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const run = async () => {
    if (!query.trim()) return;
    setBusy(true); setError(null);
    try {
      setRes(await api.search({ query, mode, top_k: topK, entity_type: type || null, package: pkg.trim() || null }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 md:p-6">
      <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); run(); }}>
        <label className="flex min-w-64 flex-1 flex-col gap-1 text-xs text-slate-500">Query
          <input aria-label="Search query" className={inputCls} value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Symbol (ClaimService.processClaim) or concept (discharge date)" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">Mode
          <select aria-label="Mode" className={inputCls} value={mode} onChange={(e) => setMode(e.target.value as SearchMode)}>
            <option value="hybrid">Hybrid</option>
            <option value="symbol">Exact symbol</option>
            <option value="semantic">Semantic</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">Type
          <select aria-label="Entity type" className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
            {TYPES.map((t) => <option key={t} value={t}>{t || "Any"}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">Package
          <input aria-label="Package" className={`${inputCls} w-48 font-mono`} value={pkg} onChange={(e) => setPkg(e.target.value)} placeholder="com.example" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">Top K
          <input aria-label="Top K" type="number" min={1} max={100} className={`${inputCls} w-20`} value={topK}
            onChange={(e) => setTopK(Math.max(1, Math.min(100, Number(e.target.value) || 10)))} />
        </label>
        <button className={buttonCls} disabled={busy || !query.trim()}>Search</button>
      </form>
      <ErrorBox error={error} />
      {busy && <Spinner />}
      {res?.warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
      {res && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          <table className="w-full text-sm" data-testid="search-results">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-800/50">
              <tr><th className="px-3 py-2">Entity</th><th className="px-3 py-2">Type</th><th className="px-3 py-2">Package</th>
                <th className="px-3 py-2">Match</th><th className="px-3 py-2 text-right">Score</th><th className="px-3 py-2">Source</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {res.hits.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-slate-500">No results.</td></tr>}
              {res.hits.map((h) => (
                <tr key={h.entity.id} className="align-top">
                  <td className="px-3 py-2">
                    <EntityLink id={h.entity.id} label={h.entity.title} status={h.entity.status} />
                    {h.entity.summary && <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{h.entity.summary}</p>}
                  </td>
                  <td className="px-3 py-2"><TypeBadge type={h.entity.type} /></td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">{h.entity.package}</td>
                  <td className="px-3 py-2 text-xs"><span className="font-medium">{h.match_types.join(" + ")}</span>
                    {h.matched_on && <div className="text-slate-400">{h.matched_on}</div>}</td>
                  <td className="px-3 py-2 text-right font-mono text-xs">{h.score.toFixed(2)}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">
                    {h.entity.source_file ? `${h.entity.source_file.split("/").pop()}${h.entity.source_line ? `:${h.entity.source_line}` : ""}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="border-t border-slate-100 px-3 py-1.5 font-mono text-[11px] text-slate-400 dark:border-slate-800">
            {Object.entries(res.timings_ms).map(([k, v]) => `${k}=${v}ms`).join(" · ")}
          </p>
        </div>
      )}
    </div>
  );
}
