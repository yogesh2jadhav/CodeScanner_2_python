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

export interface SourceComment { start_line: number; end_line: number; kind: string; text: string }
export interface SourceCondition { line: number; kind: string; expression: string }

export interface SourceView {
  entity_id?: string;
  file: string;
  start_line: number;
  decl_line: number;
  end_line: number;
  code: string;
  comments: SourceComment[];
  conditions: SourceCondition[];
  notes: string[];
  truncated: boolean;
}

export interface SourceResponse extends Partial<SourceView> {
  available: boolean;
  reason?: string;
}

export interface SourceRef { evidence_id: string; start_line: number; end_line: number }
export type Certainty = "observed" | "derived" | "unknown";

export interface EvidenceItem {
  evidence_id: string;
  kind: string;
  title: string;
  entity_id?: string | null;
  file?: string | null;
  start_line?: number | null;
  end_line?: number | null;
  status: string;
  depth: number;
  priority: number;
  content: string;
  lines: number[];
}

export interface Grounded { source_refs: SourceRef[]; grounded: boolean }
export interface ExplanationStep extends Grounded { step_number: number; title: string; description: string; certainty: Certainty }
export interface BranchItem extends Grounded { condition: string; when_true: string; when_false?: string | null }
export interface DescribedItem extends Grounded { description: string }
export interface CallExplanation extends Grounded {
  callee: string;
  evidence_status: "body_inspected" | "signature_only" | "unresolved" | "external";
  summary: string;
}

export interface LLMExplanation {
  summary: string;
  purpose_is_inferred: boolean;
  inputs_outputs: { name: string; role: "input" | "output" | "exception" | "side_effect"; description: string }[];
  execution_steps: ExplanationStep[];
  branches: BranchItem[];
  data_transformations: DescribedItem[];
  calls: CallExplanation[];
  side_effects: DescribedItem[];
  exceptions: DescribedItem[];
  uncertainties: string[];
}

export interface MethodExplanationResponse {
  request_id: string;
  method_id: string;
  method_signature: string;
  method_title: string;
  explanation: LLMExplanation | null;
  evidence: EvidenceItem[];
  facts: { comments: SourceComment[]; conditions: SourceCondition[]; calls: { target: string; entity_id?: string | null; status: string; lines: number[] }[] };
  warnings: string[];
  validation: { valid: boolean; repair_attempts: number; invalid_refs_removed: number; ungrounded_items: number; corrected_call_statuses: number; errors: string[] } | null;
  model: { provider: string; model: string; prompt_version: string; num_ctx?: number | null } | null;
  cached: boolean;
  timings_ms: Record<string, number>;
  estimated_prompt_tokens: number;
  markdown: string;
}

export interface ExplainOptions {
  detail?: "detailed" | "summary";
  max_callee_depth?: number;
  include_caller_context?: boolean;
  force_refresh?: boolean;
  use_llm?: boolean;
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
  source?: SourceView | null;
  method_explanation?: MethodExplanationResponse | null;
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
  source?: { enabled: boolean };
}
