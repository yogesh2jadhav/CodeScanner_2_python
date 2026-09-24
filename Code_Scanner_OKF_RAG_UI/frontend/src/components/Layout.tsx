import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../services/api";
import type { StatusResponse } from "../types/api";
import { EntityPanel } from "./EntityPanel";

const NAV = [
  { to: "/ask", label: "Ask" },
  { to: "/search", label: "Search" },
  { to: "/explorer", label: "Explorer" },
  { to: "/graph", label: "Graph" },
  { to: "/flow", label: "Flow" },
];

function Dot({ ok, warn }: { ok: boolean; warn?: boolean }) {
  return <span className={`inline-block h-2 w-2 rounded-full ${ok ? (warn ? "bg-amber-500" : "bg-emerald-500") : "bg-red-500"}`} />;
}

function StatusBar() {
  const [s, setS] = useState<StatusResponse | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    api.status().then(setS).catch(() => setErr(true));
  }, []);
  if (err) return <span className="flex items-center gap-1.5 text-xs text-red-600"><Dot ok={false} />Backend unreachable</span>;
  if (!s) return null;
  const kb = s.knowledge_base;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
      <span className="flex items-center gap-1.5" title={kb.error ?? ""}>
        <Dot ok={kb.ready} />{kb.ready ? `${kb.documents} docs · ${kb.graph_edges} relations` : "OKF not loaded"}
      </span>
      <span className="flex items-center gap-1.5" title={`Embedding: ${s.embedding.model}`}>
        <Dot ok={kb.vector_status !== "unavailable" && kb.vector_status !== "empty"} warn={kb.vector_status === "stale"} />
        vectors: {kb.vector_status}
      </span>
      <span className="flex items-center gap-1.5">
        <Dot ok={s.llm.available} />LLM: {s.llm.model ?? "none"}{s.llm.available ? "" : " (offline)"}
      </span>
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-slate-200 bg-white px-4 py-2 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center gap-2">
          <img src="/favicon.svg" alt="" className="h-6 w-6" />
          <span className="font-semibold tracking-tight">CodeKnowledgeAI</span>
        </div>
        <nav className="flex gap-1">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to}
              className={({ isActive }) => `rounded-md px-3 py-1.5 text-sm font-medium ${isActive
                ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto"><StatusBar /></div>
      </header>
      <main className="min-h-0 flex-1 overflow-auto">{children}</main>
      <EntityPanel />
    </div>
  );
}
