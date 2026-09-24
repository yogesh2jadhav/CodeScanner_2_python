import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

interface EntityPanelState {
  entityId: string | null;
  open: (id: string) => void;
  close: () => void;
}

const Ctx = createContext<EntityPanelState | null>(null);

/** One global entity drawer: any entity mention anywhere in the UI can open it. */
export function EntityPanelProvider({ children }: { children: ReactNode }) {
  const [entityId, setEntityId] = useState<string | null>(null);
  const open = useCallback((id: string) => setEntityId(id), []);
  const close = useCallback(() => setEntityId(null), []);
  const value = useMemo(() => ({ entityId, open, close }), [entityId, open, close]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useEntityPanel(): EntityPanelState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useEntityPanel must be used inside EntityPanelProvider");
  return v;
}
