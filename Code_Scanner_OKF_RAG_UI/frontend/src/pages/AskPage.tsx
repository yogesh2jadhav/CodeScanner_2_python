import { useMemo, useState } from "react";
import { api } from "../services/api";
import type { AskResponse } from "../types/api";
import { EntityLink } from "../components/EntityLink";
import { useEntityPanel } from "../components/EntityPanelContext";
import { FlowDiagram } from "../components/FlowDiagram";
import { Markdown } from "../components/Markdown";
import { SourceCode } from "../components/SourceCode";
import { MethodExplanationView } from "../components/MethodExplanation";
import { Card, ErrorBox, Notice, Spinner, buttonCls } from "../components/ui";
import { linkifyMarkdown, type LinkTarget } from "../utils/linkify";
import { shortName } from "../utils/entityStyle";

// Templates, not demo questions: clicking one fills the box so the user can put in
// a real class/method name before sending.
const EXAMPLES = [
  "Explain ClassName.methodName",
  "What are the business rules in ClassName.methodName?",
  "Who calls ClassName.methodName?",
  "What does ClassName.methodName eventually call?",
  "What is the impact of changing ClassName?",
  "Where is <concept, e.g. discharge date> calculated?",
];

function linkTargets(r: AskResponse): LinkTarget[] {
  const targets = new Map<string, LinkTarget>();
  const add = (id: string, ...names: (string | null | undefined)[]) => {
    const t = targets.get(id) ?? { id, names: [] };
    names.forEach((n) => n && !t.names.includes(n) && t.names.push(n));
    targets.set(id, t);
  };
  // Also match names without their parameter list: an answer may say
  // "OrderService.placeOrder" for "OrderService.placeOrder(Customer, double)".
  const bare = (t: string) => t.replace(/\(.*\)$/, "");
  r.evidence.forEach((e) => add(e.entity_id, e.title, bare(e.title)));
  r.related_entities.forEach((e) => add(e.id, e.title, bare(e.title)));
  r.paths.flat().forEach((id) => add(id));
  return [...targets.values()];
}

function Answer({ r }: { r: AskResponse }) {
  const { open } = useEntityPanel();
  const targets = useMemo(() => linkTargets(r), [r]);
  const [showPlan, setShowPlan] = useState(false);
  const titleOf = (id: string) => r.evidence.find((e) => e.entity_id === id)?.title ?? shortName(id);

  return (
    <article className="space-y-3" data-testid="answer">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded bg-slate-900 px-2 py-0.5 font-semibold text-white dark:bg-slate-100 dark:text-slate-900">{r.category}</span>
        <span className="text-slate-500">confidence {(r.confidence * 100).toFixed(0)}% · {r.classification_method}</span>
        {r.cached && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">cached</span>}
        <button className="text-blue-600 hover:underline" onClick={() => setShowPlan(!showPlan)}>{showPlan ? "hide plan" : "show plan"}</button>
        <span className="ml-auto font-mono text-slate-400">request_id={r.request_id}</span>
      </div>
      {showPlan && <ol className="rounded-md bg-slate-50 p-3 font-mono text-xs dark:bg-slate-900">{r.plan.map((p) => <li key={p}>{p}</li>)}</ol>}

      {r.paths.length > 0 && (
        <div className="space-y-1">
          {r.paths.map((p) => (
            <div key={p.join(">")} className="flex flex-wrap items-center gap-1 rounded-md bg-blue-50 px-3 py-2 dark:bg-blue-950/40" data-testid="path">
              {p.map((id, i) => (
                <span key={id} className="flex items-center gap-1">
                  {i > 0 && <span className="text-slate-400">→</span>}
                  <EntityLink id={id} label={titleOf(id)} />
                </span>
              ))}
            </div>
          ))}
        </div>
      )}

      <Card title="Verified facts (from OKF graph & flow)">
        <Markdown>{linkifyMarkdown(r.answer, targets)}</Markdown>
      </Card>

      {r.method_explanation && (
        <Card title={<>Method explanation <span className="normal-case text-slate-400">— evidence-grounded, citations verified</span></>}
          className="border-violet-200 dark:border-violet-900">
          <MethodExplanationView data={r.method_explanation} />
        </Card>
      )}
      {r.interpretation && !r.method_explanation && (
        <Card title={<>AI interpretation <span className="normal-case text-slate-400">— {r.llm_model}; verify against evidence</span></>}
          className="border-violet-200 dark:border-violet-900">
          <Markdown>{linkifyMarkdown(r.interpretation, targets)}</Markdown>
        </Card>
      )}
      {r.llm_error && <Notice tone="warn">Natural-language explanation unavailable: {r.llm_error}</Notice>}
      {r.warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}

      {r.source && (
        <details className="rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          <summary className="cursor-pointer px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Source code ({r.source.end_line - r.source.start_line + 1} lines, {r.source.comments.length} comments)
          </summary>
          <div className="px-4 pb-4"><SourceCode source={r.source} /></div>
        </details>
      )}

      {r.flow && r.flow.nodes.length > 0 && (
        <Card title={`Flow preview — ${r.flow.title} (${r.flow.availability})`}>
          <FlowDiagram flow={r.flow} height={360} onNodeClick={(n) => n.entity_id && open(n.entity_id)} />
        </Card>
      )}

      <Card title={`Evidence (${r.evidence.length})`}>
        <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-800" data-testid="evidence">
          {r.evidence.map((e) => (
            <li key={e.entity_id} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 py-1.5">
              <EntityLink id={e.entity_id} label={e.title} type={e.type} showType />
              {e.cited && <span className="rounded bg-violet-100 px-1 text-[10px] font-semibold text-violet-800 dark:bg-violet-900 dark:text-violet-200">cited</span>}
              <span className="font-mono text-xs text-slate-500">{e.document}</span>
              {e.source && <span className="font-mono text-xs text-slate-400">{e.source}{e.source_line ? `:${e.source_line}` : ""}</span>}
              <span className="ml-auto text-xs text-slate-400">{e.reason}</span>
            </li>
          ))}
        </ul>
      </Card>

      {r.related_entities.length > 0 && (
        <div className="flex flex-wrap gap-2 text-sm">
          <span className="text-xs font-semibold uppercase text-slate-500">Related:</span>
          {r.related_entities.map((e) => <EntityLink key={e.id} id={e.id} label={e.title} type={e.type} status={e.status} />)}
        </div>
      )}
      <p className="font-mono text-[11px] text-slate-400">
        {Object.entries(r.timings_ms).map(([k, v]) => `${k}=${v < 1000 ? `${v}ms` : `${(v / 1000).toFixed(2)}s`}`).join(" · ")}
      </p>
    </article>
  );
}

interface Turn { question: string; response?: AskResponse; error?: unknown }

export function AskPage() {
  const [question, setQuestion] = useState("");
  const [useLlm, setUseLlm] = useState(true);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);

  const submit = async (q = question) => {
    const text = q.trim();
    if (!text || busy) return;
    setBusy(true);
    setQuestion("");
    setTurns((t) => [{ question: text }, ...t]);
    try {
      const response = await api.ask(text, useLlm);
      setTurns((t) => [{ question: text, response }, ...t.slice(1)]);
    } catch (error) {
      setTurns((t) => [{ question: text, error }, ...t.slice(1)]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-6">
      <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="space-y-2">
        <textarea
          aria-label="Question"
          className="w-full resize-y rounded-lg border border-slate-300 bg-white p-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900"
          rows={3}
          placeholder="Ask about classes, methods, callers, flows, business rules…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit(); } }}
        />
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className={buttonCls} disabled={busy || !question.trim()}>Ask</button>
          <label className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
            <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} /> Use LLM explanation
          </label>
          <span className="text-xs text-slate-400">⌘/Ctrl + Enter to send</span>
        </div>
        {turns.length === 0 && (
          <div className="flex flex-wrap gap-2 pt-2">
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" onClick={() => setQuestion(ex)}
                className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
                {ex}
              </button>
            ))}
          </div>
        )}
      </form>

      {turns.map((t, i) => (
        <section key={`${t.question}-${turns.length - i}`} className="space-y-3 border-t border-slate-200 pt-4 dark:border-slate-800">
          <h2 className="text-base font-semibold">{t.question}</h2>
          {!t.response && !t.error && <Spinner label="Retrieving evidence and generating answer…" />}
          <ErrorBox error={t.error} />
          {t.response && <Answer r={t.response} />}
        </section>
      ))}
    </div>
  );
}
