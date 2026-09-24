import { typeStyle } from "../utils/entityStyle";

export function TypeBadge({ type }: { type: string | undefined | null }) {
  const s = typeStyle(type);
  return (
    <span className={`inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${s.chip}`}>
      {s.label}
    </span>
  );
}
