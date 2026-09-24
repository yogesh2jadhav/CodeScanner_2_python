import type { ReactNode } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { EntityPanel } from "../components/EntityPanel";
import { EntityPanelProvider } from "../components/EntityPanelContext";

export function renderWithProviders(ui: ReactNode, route = "/") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <EntityPanelProvider>
        {ui}
        <EntityPanel />
      </EntityPanelProvider>
    </MemoryRouter>,
  );
}

type Handler = (url: string, init?: RequestInit) => unknown;

/** Route-based fetch mock: first matching (method, substring) wins. */
export function mockApi(routes: Record<string, Handler | unknown>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    for (const [key, value] of Object.entries(routes)) {
      const [m, path] = key.includes(" ") ? key.split(" ", 2) : ["GET", key];
      if (m === method && url.includes(path)) {
        const body = typeof value === "function" ? (value as Handler)(url, init) : value;
        return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
      }
    }
    return new Response(JSON.stringify({ detail: `No mock for ${method} ${url}` }), { status: 404 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export const entity = (id: string, type = "class", extra: Record<string, unknown> = {}) => ({
  id, title: id.split(".").pop(), type, package: "demo", document: `${id.split(".").pop()}.md`,
  source_file: `src/demo/${id.split(".").pop()}.java`, source_line: 1, summary: `Summary of ${id}`, status: "resolved", ...extra,
});

export const entityDetail = (id: string) => ({
  entity: entity(id), content: `# ${id}\n\nSee [B](B.md) and <script>alert(1)</script>`, signature: null,
  metadata: {}, flow_available: true, owner: null, members: [], link_targets: { "B.md": "demo.B" },
});

export const relationships = (id: string) => ({
  entity_id: id,
  outgoing: [{ source: id, target: "demo.B", type: "CALLS", status: "resolved", other: entity("demo.B") }],
  incoming: [],
});
