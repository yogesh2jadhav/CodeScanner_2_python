export type EntityType =
  | "package" | "module" | "class" | "interface" | "enum" | "method" | "field" | "document" | "external" | "unresolved";

export interface EntitySummary {
  id: string;
  title: string;
  type: EntityType;
  package?: string | null;
  class_name?: string | null;
  method_name?: string | null;
  document?: string | null;
  source_file?: string | null;
  source_line?: number | null;
  summary?: string | null;
  status: string;
}

export interface SearchHit {
  entity: EntitySummary;
  score: number;
  match_types: string[];
  matched_on?: string | null;
}

export type SearchMode = "hybrid" | "symbol" | "semantic";

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  hits: SearchHit[];
  warnings: string[];
  timings_ms: Record<string, number>;
}

export interface FlowNode {
  id: string;
  kind: "start" | "call" | "condition" | "loop" | "statement" | "return" | "throw" | "merge" | "end";
  label: string;
  entity_id?: string | null;
  status: string;
}

export interface FlowEdge {
  source: string;
  target: string;
  label?: string | null;
}

export interface Flow {
  root: string;
  title: string;
  availability: "explicit" | "call_sequence" | "unavailable";
  nodes: FlowNode[];
  edges: FlowEdge[];
  notes: string[];
  call_chains: string[][];
  outline: string[];
}

export interface FlowResponse extends Flow {
  text: string;
  rules: { entity_id: string; condition: string; then: string[]; otherwise: string[] }[];
}

export interface Evidence {
  entity_id: string;
  title: string;
  type: string;
  document?: string | null;
  source?: string | null;
  source_line?: number | null;
  reason?: string | null;
  cited: boolean;
}

export interface Fact {
  claim: string;
  kind: "fact";
  evidence: string[];
}

export interface RelationshipView {
  source: string;
  target: string;
  type: string;
  status: string;
}

export interface AskResponse {
  request_id: string;
  question: string;
  category: string;
  confidence: number;
  classification_method: string;
  plan: string[];
  target?: string | null;
  answer: string;
  facts: Fact[];
  interpretation?: string | null;
  evidence: Evidence[];
  related_entities: EntitySummary[];
  relationships: RelationshipView[];
  paths: string[][];
  flow?: Flow | null;
  llm_used: boolean;
  llm_model?: string | null;
  llm_error?: string | null;
  warnings: string[];
  timings_ms: Record<string, number>;
  cached: boolean;
  knowledge_base_version?: string | null;
}

export interface GraphNode {
  id: string;
  label: string;
  type?: string;
  status?: string;
  package?: string | null;
  depth?: number;
  document?: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  status?: string;
  origin?: string;
}

export interface SubGraphResponse {
  root: string;
  depth: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  hidden_external: number;
  truncated: boolean;
}

export interface EntityDetail {
  entity: EntitySummary;
  content: string | null;
  signature: string | null;
  metadata: Record<string, unknown>;
  flow_available: boolean;
  owner: EntitySummary | null;
  members: EntitySummary[];
  link_targets: Record<string, string>;
}

export interface RelationshipEntry extends GraphEdge {
  other: EntitySummary;
}

export interface EntityRelationships {
  entity_id: string;
  outgoing: RelationshipEntry[];
  incoming: RelationshipEntry[];
}

export interface TreeNode {
  id: string;
  title: string;
  type: string;
  has_document?: boolean;
  children: TreeNode[];
}

export interface StatusResponse {
  knowledge_base: {
    ready: boolean;
    error: string | null;
    documents: number;
    graph_nodes: number;
    graph_edges: number;
    unresolved_relationships: number;
    vector_documents: number;
    vector_status: string;
    bundle_hash: string | null;
  };
  llm: { provider: string | null; model: string | null; available: boolean };
  embedding: { provider: string; model: string };
}
