export const TYPE_STYLES: Record<string, { chip: string; node: string; label: string }> = {
  package: { chip: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200", node: "#64748b", label: "pkg" },
  module: { chip: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200", node: "#64748b", label: "mod" },
  class: { chip: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200", node: "#2563eb", label: "class" },
  interface: { chip: "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-200", node: "#7c3aed", label: "iface" },
  enum: { chip: "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200", node: "#0d9488", label: "enum" },
  method: { chip: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200", node: "#059669", label: "method" },
  field: { chip: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200", node: "#d97706", label: "field" },
  document: { chip: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200", node: "#6b7280", label: "doc" },
  external: { chip: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300", node: "#a1a1aa", label: "external" },
  unresolved: { chip: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200", node: "#dc2626", label: "unresolved" },
};

export function typeStyle(type: string | undefined | null) {
  return TYPE_STYLES[type ?? "document"] ?? TYPE_STYLES.document;
}

export const EDGE_COLORS: Record<string, string> = {
  CALLS: "#2563eb",
  DEPENDS_ON: "#d97706",
  EXTENDS: "#7c3aed",
  IMPLEMENTS: "#a855f7",
  USES: "#0d9488",
  CONTAINS: "#94a3b8",
  BELONGS_TO: "#94a3b8",
  REFERENCES: "#cbd5e1",
  OVERRIDES: "#db2777",
};

export function shortName(id: string): string {
  const parts = id.split(".");
  return parts[parts.length - 1] || id;
}
