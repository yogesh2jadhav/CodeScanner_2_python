import { useEffect, useMemo, useRef } from "react";
import type { SourceView } from "../types/api";

/**
 * Read-only, line-numbered source listing. Comment lines are tinted and lines with
 * a detected condition are marked, so the code matches the explanation's line refs.
 */
export function SourceCode({ source, maxHeight = 480, highlight }: {
  source: SourceView; maxHeight?: number; highlight?: [number, number] | null;
}) {
  const hlRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    hlRef.current?.scrollIntoView?.({ block: "center" });
  }, [highlight]);
  const { commentLines, conditionLines } = useMemo(() => {
    const commentLines = new Set<number>();
    source.comments.forEach((c) => { for (let l = c.start_line; l <= c.end_line; l++) commentLines.add(l); });
    return { commentLines, conditionLines: new Set(source.conditions.map((c) => c.line)) };
  }, [source]);
  const lines = source.code.split("\n");
  const width = String(source.start_line + lines.length).length;
  return (
    <div className="space-y-1">
      <p className="font-mono text-[11px] text-slate-500">
        {source.file} · lines {source.start_line}–{source.end_line}
        {source.truncated ? " (truncated)" : ""}
      </p>
      {source.notes.map((n) => <p key={n} className="text-[11px] text-amber-600">{n}</p>)}
      <pre data-testid="source-code" style={{ maxHeight }}
        className="overflow-auto rounded-md bg-slate-50 py-2 font-mono text-[11.5px] leading-[1.45] dark:bg-slate-900">
        {lines.map((text, i) => {
          const n = source.start_line + i;
          const inHl = !!highlight && n >= highlight[0] && n <= highlight[1];
          const cls = inHl ? "bg-blue-100 dark:bg-blue-900/50"
            : commentLines.has(n) ? "text-emerald-700 dark:text-emerald-400"
            : conditionLines.has(n) ? "bg-amber-100/70 dark:bg-amber-900/30" : "";
          return (
            <div key={n} ref={inHl && n === highlight![0] ? hlRef : undefined}
              data-highlighted={inHl || undefined} className={`flex px-2 ${cls}`}>
              <span className="mr-3 select-none text-right text-slate-400" style={{ minWidth: `${width}ch` }}>{n}</span>
              <span className="whitespace-pre">{text || " "}</span>
            </div>
          );
        })}
      </pre>
    </div>
  );
}
