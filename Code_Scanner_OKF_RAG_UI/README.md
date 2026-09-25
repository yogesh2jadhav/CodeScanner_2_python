# Code_Scanner_OKF_RAG_UI — CodeKnowledgeAI

OKF + Graph + RAG for understanding large Java codebases.

## 1. What the project does

CodeKnowledgeAI reads the OKF Markdown knowledge base produced by `Java2OKF` and answers developer questions about
classes, methods, callers/callees, dependencies, inheritance, execution flow, business-rule-like conditions and
change impact. It gives evidence for every answer.

It is **not** "RAG over Markdown":

- **OKF is canonical.** The vector index and relationship graph are derived and can be rebuilt at any time.
- **Semantic search** finds concepts. **Exact symbol search** finds identifiers. **Graph traversal** finds relationships.
  **Flow analysis** reconstructs logic.
- The **LLM only explains** evidence that the analyzers found. It never discovers relationships.
- **Deterministic facts** (from the graph/flow) are kept separate from **AI interpretation** (from the LLM, labelled as such).
- Search, exact lookup, graph, explorer and flow all keep working when the LLM or the vector DB is down.

## 2. Architecture

```text
                         OKF Bundle (canonical Markdown + YAML frontmatter)
                             |
              +--------------+--------------+
              |                             |
              v                             v
     Semantic Index (Chroma)        Relationship Graph (NetworkX)   + Exact Symbol Index
              |                             |
              +--------------+--------------+
                             |
                     Query Classifier  (rules first, LLM only when unsure)
                             |
                       Query Planner   (explicit, inspectable steps)
                             |
              +--------------+--------------+
              v              v              v
          Semantic        Graph          Flow
           Search       Traversal      Analysis
              +--------------+--------------+
                             |
                      Context Builder  (bounded, deduplicated, prioritised)
                             |
                        LLM Provider   (Ollama; optional)
                             |
                  Evidence-backed Answer  (facts + interpretation + evidence)
                             |
              +--------------+--------------+
              v              v              v
             Ask         Explorer        Graph / Flow / Search
```

Code layout (`src/codeknowledge/`):

| Package | Responsibility |
|---|---|
| `okf/` | `parser` (frontmatter, links, relationship sections), `loader` (discovery + ingestion report), `repository` (id/link resolution), `validator` |
| `graph/` | `GraphStore` abstraction, `NetworkXGraphStore`, `GraphBuilder`, `GraphTraversal` (callers, callees, impact, inheritance, chains) |
| `retrieval/` | `embeddings` (Ollama / hash), `representation`, `semantic` (Chroma), `symbol` (exact), `hybrid`, `reranker` |
| `flow/` | `FlowBuilder` (explicit control flow from OKF), `analyzer` (IF/THEN/ELSE rule skeletons) |
| `query/` | `classifier`, `planner`, `context_builder` |
| `llm/` | `LLMProvider`, `OllamaProvider`, `MockLLMProvider`, prompts |
| `services/` | `KnowledgeBase` (indexing), ask, explorer, graph, flow, answer cache |
| `api/` | FastAPI app and routes |
| `cli.py` | `python -m codeknowledge …` |

## 3. Prerequisites

- Python 3.12+
- Node.js 20+ (tested with 22)
- [Ollama](https://ollama.com) (optional at runtime, needed for semantic embeddings and LLM explanations)
- Git

## 4. Installation

```bash
cd Code_Scanner_OKF_RAG_UI
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt        # installs the package in editable mode too
```

```bash
cd frontend
npm install
cd ..
```

```bash
ollama pull nomic-embed-text
ollama pull qwen3:8b
```

## 5. Configuration

Configuration lives in `config/config.yaml`. Environment variables override it using the pattern
`CODEKNOWLEDGE_<SECTION>_<KEY>`. Use `CODEKNOWLEDGE_CONFIG` to point at another YAML file. See `.env.example`.

| Key | Default | Env override | Purpose |
|---|---|---|---|
| `okf.source_dir` | `./data/okf` | `CODEKNOWLEDGE_OKF_SOURCE_DIR` | OKF bundle root |
| `okf.required_metadata` | `[id, type]` | – | Frontmatter keys the validator requires |
| `vector.persist_directory` | `./data/indexes/vector` | `CODEKNOWLEDGE_VECTOR_PERSIST_DIRECTORY` | Chroma storage |
| `vector.collection_name` | `codeknowledge` | `CODEKNOWLEDGE_VECTOR_COLLECTION_NAME` | Chroma collection |
| `graph.persist_directory` | `./data/indexes/graph` | `CODEKNOWLEDGE_GRAPH_PERSIST_DIRECTORY` | Persisted graph (`graph.json`) |
| `llm.provider` | `ollama` | `CODEKNOWLEDGE_LLM_PROVIDER` | `ollama` or `mock` |
| `llm.base_url` | `http://localhost:11434` | `CODEKNOWLEDGE_LLM_BASE_URL` | Ollama URL |
| `llm.model` | `qwen3:8b` | `CODEKNOWLEDGE_LLM_MODEL` | Chat model |
| `llm.temperature` / `llm.timeout_seconds` | `0.1` / `600` | `CODEKNOWLEDGE_LLM_TEMPERATURE` / `…_TIMEOUT_SECONDS` | Generation settings |
| `llm.num_ctx` | `16384` | `CODEKNOWLEDGE_LLM_NUM_CTX` | Ollama context window (long methods need it) |
| `source.root_dir` | none | `CODEKNOWLEDGE_SOURCE_ROOT_DIR` | Java project root, used to show and explain real code and comments |
| `method_explanation.*` | see docs | `CODEKNOWLEDGE_METHOD_EXPLANATION_*` | Explain Method workflow (depth, budget, validation, cache); see [docs/method-explanation.md](docs/method-explanation.md) |
| `embedding.timeout_seconds` / `batch_size` | `300` / `16` | `CODEKNOWLEDGE_EMBEDDING_*` | Per-request timeout; timed-out batches are split and retried |
| `embedding.provider` | `ollama` | `CODEKNOWLEDGE_EMBEDDING_PROVIDER` | `ollama` or `hash` (offline/test) |
| `embedding.model` | `nomic-embed-text` | `CODEKNOWLEDGE_EMBEDDING_MODEL` | Embedding model |
| `retrieval.semantic_top_k` | `10` | `CODEKNOWLEDGE_RETRIEVAL_SEMANTIC_TOP_K` | Default search size |
| `retrieval.graph_max_depth` | `3` | `CODEKNOWLEDGE_RETRIEVAL_GRAPH_MAX_DEPTH` | Depth for transitive/impact questions |
| `retrieval.max_context_documents` | `20` | `…_MAX_CONTEXT_DOCUMENTS` | Max entities sent to the LLM |
| `retrieval.max_context_tokens` | `12000` | `…_MAX_CONTEXT_TOKENS` | Approximate LLM context budget |
| `retrieval.classifier_confidence_threshold` | `0.6` | `…_CLASSIFIER_CONFIDENCE_THRESHOLD` | Below this, the LLM classifies |
| `cache.enabled` / `directory` / `ttl_seconds` | `true` / `./data/cache` / `86400` | `CODEKNOWLEDGE_CACHE_*` | Answer cache |
| `logging.level` / `file` / `config_file` | `INFO` / `./logs/codeknowledge.log` / `./config/logging.yaml` | `CODEKNOWLEDGE_LOGGING_*` | Logging |
| `application.cors_origins` | `localhost:5173` | `CODEKNOWLEDGE_APPLICATION_CORS_ORIGINS` (comma-separated) | Allowed browser origins |

## 6. How to provide OKF data

Point the app at the Java2OKF output folder, the directory that contains `index.md`, `classes/`, `methods/` and so
on. Pick one of these:

- Set `okf.source_dir` in `config/config.yaml`. This is recommended because every command and the server then use
  the same bundle. Single quotes keep Windows paths intact:
  `source_dir: 'C:\Users\me\java2okf\output'`.
- Set `CODEKNOWLEDGE_OKF_SOURCE_DIR` in the shell that runs the scripts and the server.
- Copy or symlink the bundle into `data/okf/`.

`--input` on `validate`, `ingest` or `rebuild` applies to that one command only. Every command prints the `OKF source`
it used.

### Java2OKF bundles (native format)

The app follows java2okf `docs/okf-output.md`:

| Java2OKF | How it is used |
|---|---|
| `id: java-method:com.x.OrderService.placeOrder(com.x.Customer,double)` | Canonical id. The parameter list is kept so overloads stay distinct. Search also matches `OrderService.placeOrder`, `placeOrder`, the qualified name, etc. |
| `type: JavaClass / JavaInterface / JavaEnum / JavaRecord / JavaAnnotation / JavaMethod / JavaConstructor / JavaPackage` | Entity type |
| `type: Index / Log` | Navigation pages: browsable, but they create no relationships and need no `id` |
| `resource`, `java.lines: 17-24` | Source file and start/end line |
| `java.declaringClass`, `java.qualifiedName`, `java.package`, `java.signature`, `## Signature` / `## Declaration` code | Class/method names, display name such as `OrderService.placeOrder(Customer, double)`, and signature |
| `## Calls`, `## Called By` (method docs), `## Initializer Calls` | `CALLS`, with the source line from "— line N" |
| `## Declared By`, `## Methods`, `## Constructors`, `## Nested Types`, `## Package`, `## Classes`/`Interfaces`/`Enums`/`Records` | `CONTAINS` |
| `## Inheritance`/`Extends`, `## Subtypes` | `EXTENDS` |
| `## Implements`, `## Extended / Implemented By` | `IMPLEMENTS` |
| `## Overrides`, `## Overridden By` | `OVERRIDES` |
| `## Uses`, `## Used By`, `## Parameters`, `## Returns`, `## Throws`, `## Instantiates`, `## Fields`, `## Annotations` | `USES` |
| `## Dependencies`, `## Dependents`, `## Imports` | `DEPENDS_ON` |
| `## References`, `## Referenced By` | `REFERENCES` |
| `` `java.util.List` (external) ``, `(implicit)` | **External** reference (JDK/library): kept as a leaf node, not counted as a problem |
| `` `x.save(..)` — UNRESOLVED ``, `AMBIGUOUS`, `(no document)` | **Unresolved**: kept and shown with `status: unresolved` |

Class documents' aggregated `## Called By` sections are skipped, because method documents record the same calls
more precisely.

External nodes such as `java.lang.String` are **leaves**. Traversal, paths and graph expansion never pass through
them. Without that, one shared JDK type would link every class in the project together. The Graph screen hides
them by default; use "Show external" to see them. Java2OKF records no control flow, so the Flow view shows a
method's calls in **source-line order** (`call_sequence`) and states that conditions and loops are unknown.

### Source code and developer comments (`source.root_dir`)

Java2OKF records structure (calls, types, line ranges) but not method bodies or comments. To get explanations
that follow the code, point the app at the Java project that Java2OKF analysed:

```yaml
source:
  root_dir: 'C:\Users\me\projects\my-java-app'   # Java2OKF project.sourceRoot
```

With it, "Explain X.method" and "What are the business rules in X.method?":

- read the method from `resource` + `java.lines`, including the Javadoc and annotations above it. If the file
  changed since generation, the declaration is re-located nearby and a note is shown.
- show the **developer comments verbatim with line numbers**, and every condition (`if`, `.filter(...)`, loops,
  `catch`), without needing the LLM.
- ask the LLM for a **step-by-step walkthrough**: one item per code block, restating the comment where there is
  one and writing an explanation in the same style where there isn't, then IF/THEN/ELSE business rules with line
  references.

Source is only read, never executed, and never outside `root_dir`. The Explorer and the entity panel ("source"
tab) show the code too.

For long methods the prompt is large. `llm.num_ctx` (default 16384) stops Ollama from silently truncating it, and
`llm.timeout_seconds` (default 600) allows for slow CPU-only machines.

A copy of the Java2OKF sample output is kept in `tests/fixtures/java2okf-sample/`. It is 31 documents and validates
with 0 errors and 0 warnings.

### Hand-written / generic OKF

Other generators, or hand-written docs, can use the same concepts with plain keys:

```markdown
---
id: com.example.claim.CasingService.processClaims   # aliases: identifier, fqn, qualified_name
type: method                  # class|java_class|interface|enum|method|constructor|field|package|module
title: CasingService.processClaims
package: com.example.claim
class_name: CasingService
method_name: processClaims
signature: public void processClaims(List<ClaimDataDTO> claims)
source_file: src/main/java/com/example/claim/CasingService.java   # aliases: source, source_path, file, resource
source_line: 42                                                    # aliases: line, start_line
summary: Assigns the discharge date for each claim.
relationships:                # mapping or list of {type, target}; also accepted as top-level keys
  calls: [com.example.claim.CasingService.getClaimData]
  uses: [com.example.claim.ClaimDataDTO]
  # extends, implements, depends_on, called_by, implemented_by, contains, overrides, references …
flow:                         # optional explicit control flow (enables IF/ELSE and loop diagrams)
  - call: getClaimData
  - if: checkConfiguration()
    then: [{call: applyConfiguredDischarge}]
    else: [{call: applyDefaultDischarge}]
  - loop: "for (Claim c : claims)"
    body: [{call: save}]
  - return: void              # also: throw, statement
---
# CasingService.processClaims

## Calls
- [getClaimData](CasingService.getClaimData.md)   <!-- section headings type the links below them -->
```

- Relationship targets can be fully qualified, `Class.method`, or unqualified names. They are resolved against the
  source entity's own class/package first, then by a unique name suffix.
- Targets that cannot be resolved are **kept** as `status: unresolved` nodes and edges. They are never dropped.
- Links in other body text become `REFERENCES` edges. `CONTAINS` edges (package → class → method) are also derived
  from `package`/`class_name`.
- If there is no `flow:` block, the flow view shows only the known calls, labelled `call_sequence`. With no calls
  either, it shows `unavailable`. Control flow is never invented.

The golden sample for this format is in `tests/fixtures/sample-okf/`. It has 6 classes, 2 interfaces, 15 methods,
inheritance, 13 calls and 2 conditional flows.

Validate a bundle:

```bash
python scripts/validate_okf.py --input ./data/okf -v     # exit code 0 = pass, 1 = errors
```

Rules checked: frontmatter exists, required metadata (not for Index/Log pages), malformed YAML, duplicate IDs, links
resolve, referenced files exist, links escaping the root, plus unresolved relationships (warning) and orphan
documents (warning). External references are counted but are not warnings. The summary lists the most frequent
unresolved targets. `-v` prints the first 200 issues, errors first.

### Explain a method (evidence-grounded)

Open a method and go to its **Explain** tab, call `POST /api/methods/{method_id}/explain`, or ask
"Explain `Class.method`". The answer is a structured, step-by-step explanation in which every statement cites lines
that the server has verified against the evidence sent to the model:
- the method body
- callee bodies, to a configurable depth
- calls, with their resolution status

The model's output is constrained to a JSON schema and validated. Invented line numbers are removed, and a call is
never described as "inspected" unless its body was supplied. See **[docs/method-explanation.md](docs/method-explanation.md)**
for the pipeline, API, configuration (`method_explanation:`), validation policy, tests and benchmark.

## 7. How to build indexes

```bash
python scripts/rebuild_indexes.py                 # graph + vectors (needs Ollama embeddings)
python scripts/rebuild_indexes.py --skip-vectors  # graph only
```

Or call `POST /api/index/rebuild`. At startup the app loads the persisted graph if the OKF bundle hash is unchanged,
and rebuilds it otherwise. The vector index is rebuilt only on request, because embedding a large bundle is slow. If
it is out of date, `/api/status` reports `vector_status: stale`.

## 8. How to run the backend

```bash
source .venv/bin/activate
uvicorn codeknowledge.api.app:app --reload --port 8000
# without an editable install:  uvicorn --app-dir src codeknowledge.api.app:app --reload --port 8000
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

## 9. How to run the frontend

```bash
cd frontend
npm run dev          # http://localhost:5173 (proxies /api to http://localhost:8000; override with VITE_API_PROXY_TARGET)
npm run build        # production build to frontend/dist
```

The UI has five screens:

- **Ask**: chat with verified facts, AI interpretation, clickable path, evidence, flow preview and timings.
- **Search**: hybrid, symbol or semantic search with type and package filters.
- **Explorer**: packages, classes and methods, the document, and its relations.
- **Graph**: React Flow view with zoom, pan, selection, relationship labels, a depth slider and filters for Calls,
  Dependencies, Inheritance, Implements, Uses and Contains.
- **Flow**: execution flow with branches and loops. Click a call node to follow it.

Any entity mention opens the **entity panel**, with Class, Method, Source, Document, Relationships and Flow.

## 10. How to run tests

```bash
pytest                                  # backend unit + integration + API + e2e (no live LLM needed)
pytest --cov=codeknowledge              # coverage (~94%)
pytest -m llm                           # optional live suite: requires Ollama with the configured models
cd frontend && npm test                 # Vitest + React Testing Library
cd frontend && npm run typecheck
```

CI does not need an LLM. `MockLLMProvider` covers the question → context → prompt → answer → evidence chain, and
tests check facts and evidence rather than LLM wording. The final acceptance test is in
`tests/integration/test_ask_service.py::test_abc_final_acceptance`: given `A → B → C`, "What does A eventually call?"
answers `A → B → C` with clickable evidence for A, B and C.

## 11. How to use the CLI

```bash
python -m codeknowledge validate [--input DIR] [-v]
python -m codeknowledge ingest   [--input DIR] [-v]
python -m codeknowledge rebuild  [--input DIR] [--skip-vectors]
python -m codeknowledge search "ClaimService" [--mode hybrid|symbol|semantic] [--type method] [--package p] [--json]
python -m codeknowledge ask "How is discharge date calculated?" [--no-llm] [--no-cache] [--json]
```

`ask` prints the category, plan, deterministic answer, AI interpretation, evidence and per-stage latency, for example
`symbol_search=0.02ms, semantic_search=32ms, graph_expansion=0.05ms, context_build=0.8ms, llm=10.4s`.

## 12. API documentation

Full OpenAPI docs are at `/docs`.

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | `{"status":"ok","version":"0.1.0"}` |
| GET | `/api/status` | Index, vector and LLM status |
| POST | `/api/index/rebuild` | Body `{"vectors": true}`; purges stale cache entries |
| POST | `/api/search` | `{"query", "top_k", "mode", "entity_type", "package", "expand_graph"}` |
| POST | `/api/methods/{method_id}/explain` | Evidence-grounded method explanation (see docs/method-explanation.md) |
| POST | `/api/ask` | `{"question", "use_llm", "use_cache"}`; returns facts, interpretation, evidence, plan, paths, flow, timings, `request_id` |
| GET | `/api/entities/{id}` | Entity, document content, owner, members, resolved cross-links |
| GET | `/api/entities/{id}/relationships` | Incoming and outgoing edges (with `status`) |
| GET | `/api/explorer/tree` | Package → type → member tree |
| GET | `/api/graph/node/{id}` | Node and degree |
| GET | `/api/graph/neighbors/{id}` | `?direction=in\|out\|both&types=calls,inheritance&include_external=false` |
| GET | `/api/graph/path` | `?from=…&to=…&types=…&directed=true` |
| GET | `/api/graph/subgraph/{id}` | `?depth=0..6&types=…&direction=…&include_external=false&max_nodes=300` |
| GET | `/api/flow/{id}` | Flow nodes/edges, outline text, rule skeletons, call chains |

Every response carries an `X-Request-ID` header. You can send your own. Each `/api/ask` logs `QUERY_RECEIVED`,
`QUERY_CLASSIFIED`, `SEARCH_STARTED`, `SEARCH_COMPLETED`, `GRAPH_EXPANSION`, `CONTEXT_BUILT`, `LLM_STARTED`,
`LLM_COMPLETED` and `ANSWER_RETURNED`, all tagged with the same `request_id`. Timings are included.

## 13. Troubleshooting

| Symptom | Fix |
|---|---|
| `rebuild` prints `Documents: 0` / "No OKF documents found" | The command used the default `./data/okf`. Set `okf.source_dir` (see section 6) so every command uses the same bundle |
| `OKF source directory does not exist. Configure okf.source_dir.` (HTTP 503) | Put the bundle in `data/okf/` or set `CODEKNOWLEDGE_OKF_SOURCE_DIR`, then restart or call `/api/index/rebuild` |
| `vectors: empty` / `stale` in the UI header | `python scripts/rebuild_indexes.py` |
| `Semantic search unavailable` warning | Ollama is not running, or `nomic-embed-text` is not pulled. Symbol and graph search still work |
| "LLM unavailable" in answers | `ollama serve` and `ollama pull qwen3:8b`, or set `CODEKNOWLEDGE_LLM_MODEL`. Facts and evidence are still returned |
| Many `unresolved` relationships | Run `validate`. The summary shows the most frequent targets. Targets must match an `id` or a unique `Class.member` suffix; Java2OKF `UNRESOLVED`/`AMBIGUOUS` items stay unresolved by design |
| Frontend shows "Backend unreachable" | Start uvicorn on port 8000, or set `VITE_API_PROXY_TARGET` |
| Stale answers | Answers are cached per (question, OKF hash, model, retrieval config) for `cache.ttl_seconds`. Use `--no-cache` or `use_cache:false` |

Logs are written to `logs/codeknowledge.log`, including stack traces for errors.

## 14. Architecture decisions

- **NetworkX behind a `GraphStore` interface.** There is no infrastructure for v1. A `Neo4jGraphStore` can replace it
  without touching services.
- **Deterministic-first classification.** Regex rules are instant, testable and work offline. The LLM is asked only
  below the confidence threshold.
- **Explicit query plans.** Each answer shows the plan it ran, which makes poor answers easier to debug.
- **Structured, bounded context.** Entities, relationships, flow, rules and facts go to the LLM as JSON with
  document/token budgets, deduplication and priority (target > path > graph > semantic). Raw Markdown is never dumped.
- **Retrieval representation.** Embeddings index a compact header (title/type/names/package/summary/relationships)
  plus trimmed content, not boilerplate-heavy raw Markdown.
- **Hybrid scoring.** Symbol hits rank above fuzzy and semantic hits, with a bonus when both agree. Graph expansion
  adds neighbours at a decayed score. Every hit reports why it matched.
- **Unresolved references are kept, not dropped.** Missing targets become visible `unresolved` nodes.
- **Flow is never invented.** Explicit OKF flow gives a real control-flow graph. Calls alone give a labelled
  `call_sequence`. Otherwise the flow is `unavailable`.
- **The bundle hash is the knowledge-base version.** It keys graph persistence, vector staleness and cache
  invalidation.
- **Sanitised rendering.** OKF and LLM Markdown are rendered with react-markdown without raw HTML, and URLs are
  filtered. Entity references are linkified on the client from the evidence set, so links never depend on the LLM
  emitting correct syntax.
- **Security.** Java code and Markdown content are never executed. APIs expose only OKF-relative document paths and
  the source paths already stated in OKF. Secrets are not logged, and questions are logged by length only.

## 15. Limitations

- The graph is in-memory (NetworkX). Very large bundles (hundreds of thousands of nodes) may need the future Neo4j
  store.
- Control-flow detail depends on the OKF `flow:` metadata. Without it, only unordered call sets are available.
- Rule classification is English-only. Unusual phrasings fall back to the LLM classifier, or to `GENERAL`.
- Token budgeting uses a ~4 chars/token heuristic, not a real tokenizer.
- Rebuilding the vector index re-embeds the whole bundle. Incremental indexing is not implemented.
- Only one LLM provider is active at a time (Ollama). An OpenAI-compatible provider is a planned extension.
- The answer cache is file-based and per-process. It is not intended for multi-node deployments.
- No Docker setup yet. v1 runs locally without Docker, by design.
