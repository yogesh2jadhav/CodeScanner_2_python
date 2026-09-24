import { useEntityPanel } from "./EntityPanelContext";
import { TypeBadge } from "./TypeBadge";

interface Props {
  id: string;
  label?: string;
  type?: string | null;
  status?: string;
  showType?: boolean;
  className?: string;
}

/** Clickable reference to a knowledge entity; opens the entity panel. */
export function EntityLink({ id, label, type, status, showType = false, className = "" }: Props) {
  const { open } = useEntityPanel();
  const unresolved = status === "unresolved" || type === "unresolved";
  return (
    <button
      type="button"
      onClick={() => open(id)}
      title={unresolved ? `${id} (unresolved reference)` : id}
      className={`inline-flex max-w-full items-center gap-1.5 text-left font-mono text-[0.85em] text-blue-700 hover:underline dark:text-blue-300 ${
        unresolved ? "text-red-600 decoration-dashed dark:text-red-400" : ""
      } ${className}`}
    >
      {showType && <TypeBadge type={type} />}
      <span className="truncate">{label ?? id}</span>
    </button>
  );
}
