import type {
  AskResponse, EntityDetail, EntityRelationships, ExplainOptions, FlowResponse, MethodExplanationResponse,
  SearchMode, SearchResponse, SourceResponse,
  StatusResponse, SubGraphResponse, TreeNode,
} from "../types/api";

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string, public requestId?: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    let requestId: string | undefined = res.headers.get("X-Request-ID") ?? undefined;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      requestId = body.request_id ?? requestId;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail || `HTTP ${res.status}`, requestId);
  }
  return res.json() as Promise<T>;
}

// Entity ids contain dots but never slashes; encode each char that could break the path.
const id = (value: string) => encodeURIComponent(value);

export const api = {
  status: () => request<StatusResponse>("/api/status"),
  rebuild: (vectors = true) => request<unknown>("/api/index/rebuild", { method: "POST", body: JSON.stringify({ vectors }) }),
  search: (body: { query: string; top_k?: number; mode?: SearchMode; entity_type?: string | null; package?: string | null }) =>
    request<SearchResponse>("/api/search", { method: "POST", body: JSON.stringify(body) }),
  ask: (question: string, useLlm = true) =>
    request<AskResponse>("/api/ask", { method: "POST", body: JSON.stringify({ question, use_llm: useLlm }) }),
  tree: () => request<TreeNode[]>("/api/explorer/tree"),
  entity: (entityId: string) => request<EntityDetail>(`/api/entities/${id(entityId)}`),
  relationships: (entityId: string) => request<EntityRelationships>(`/api/entities/${id(entityId)}/relationships`),
  subgraph: (entityId: string, depth: number, types: string[], direction = "both", includeExternal = false) => {
    const q = new URLSearchParams({ depth: String(depth), direction });
    if (includeExternal) q.set("include_external", "true");
    if (types.length) q.set("types", types.join(","));
    return request<SubGraphResponse>(`/api/graph/subgraph/${id(entityId)}?${q}`);
  },
  source: (entityId: string) => request<SourceResponse>(`/api/entities/${id(entityId)}/source`),
  explainMethod: (methodId: string, options: ExplainOptions = {}, signal?: AbortSignal) =>
    request<MethodExplanationResponse>(`/api/methods/${id(methodId)}/explain`, {
      method: "POST", body: JSON.stringify(options), signal,
    }),
  flow: (entityId: string) => request<FlowResponse>(`/api/flow/${id(entityId)}`),
};
