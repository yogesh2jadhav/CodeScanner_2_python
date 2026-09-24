import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import type { SearchHit } from "../types/api";
import { TypeBadge } from "./TypeBadge";
import { inputCls } from "./ui";

interface Props {
  value: string;
  onPick: (id: string) => void;
  placeholder?: string;
  entityType?: string;
}

/** Symbol-search autocomplete returning an entity id. */
export function EntityPicker({ value, onPick, placeholder = "Class or method, e.g. ClaimService.processClaim", entityType }: Props) {
  const [text, setText] = useState(value);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => setText(value), [value]);

  useEffect(() => {
    clearTimeout(timer.current);
    if (!open || text.trim().length < 2) {
      setHits([]);
      return;
    }
    timer.current = setTimeout(() => {
      api.search({ query: text, top_k: 8, mode: "symbol", entity_type: entityType ?? null })
        .then((r) => setHits(r.hits))
        .catch(() => setHits([]));
    }, 200);
    return () => clearTimeout(timer.current);
  }, [text, open, entityType]);

  const pick = (id: string) => {
    setText(id);
    setOpen(false);
    onPick(id);
  };

  return (
    <div className="relative w-full">
      <input
        className={`${inputCls} w-full font-mono`}
        value={text}
        placeholder={placeholder}
        aria-label="Entity"
        onChange={(e) => { setText(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "Enter") pick(hits[0]?.entity.id ?? text.trim());
        }}
      />
      {open && hits.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-md border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-900">
          {hits.map((h) => (
            <li key={h.entity.id}>
              <button type="button" onMouseDown={() => pick(h.entity.id)}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800">
                <TypeBadge type={h.entity.type} />
                <span className="truncate font-mono">{h.entity.title}</span>
                <span className="ml-auto truncate text-xs text-slate-400">{h.entity.package}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
