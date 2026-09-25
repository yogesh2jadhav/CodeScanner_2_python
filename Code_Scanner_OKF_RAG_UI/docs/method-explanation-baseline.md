# Method Explanation — Phase 0 Baseline

Reconnaissance for `Plan_CodeScanner_Method_Explanation.md`, written before any code change.
**Status:** implemented. Gaps G1–G9 are addressed; see [method-explanation.md](method-explanation.md).

## 1. Repositories

| Project | Role | State at baseline |
|---|---|---|
| `java2okf` (Java, `CodeScanner_1_java/java2okf`) | Static analysis → OKF v0.2 Markdown bundle | Unchanged. No JVM on the dev Mac, so it cannot be run here; the Windows machine runs it. |
| `Code_Scanner_OKF_RAG_UI` (Python package `codeknowledge` + React `frontend/`) | Ingests OKF, retrieval, graph, flow, LLM, UI | Commit `67a01e8`; **196 backend tests, 16 frontend tests passing** (`pytest`, `npm test`); live suite `pytest -m llm` passes against local Ollama (`qwen3:8b`, `nomic-embed-text`). |

## 2. What Java2OKF does and does not emit (verified)

Verified from `docs/knowledge-model.md`, `docs/okf-output.md`, the generators and generated sample output.

**Emitted per method/constructor:** canonical ID with erased signature
(`java-method:com.x.A.m(com.x.B,int)`), declaring type, declaration text (`## Signature`), return type, parameters
(table), throws, annotations, visibility, `java.lines: first-last` (declaration line through closing brace, Javadoc
excluded), `## Calls` / `## Called By` with call-site lines (`— line 21` or `— lines 12, 15`), `## Uses`,
`## Instantiates`, `## References`, `## Overrides` / `## Overridden By`, and resolution markers:
`(external)`, `(implicit)`, `(no document)`, `UNRESOLVED`, `AMBIGUOUS`.

**Not emitted:** method body text, comments or Javadoc, statement structure, branches or loops, assignments, return
expressions, call-site argument expressions, or string/SQL literals.

Conclusion: the explanation must read the body from the original source. `codeknowledge.source.reader.SourceReader`
already does this safely (it resolves under `source.root_dir` only and re-locates declarations when the file has
drifted). **No Java2OKF change is required.** A possible later, optional and backward-compatible enhancement is
emitting Javadoc text, which would make the bundle self-contained.

## 3. Current request path (Ask → answer)

```text
AskPage.submit ─► api.ask ─► POST /api/ask (routes_ask) ─► AskService.ask
  ├─ AnswerCache.get(key = question + bundle hash + model + retrieval cfg + use_llm)
  ├─ QueryClassifier (regex rules, LLM only if low confidence) ─► QueryPlanner (StepType list)
  ├─ HybridRetriever.search (SymbolIndex exact/fuzzy + SemanticIndex/Chroma + graph expansion + Reranker)
  ├─ target = exact symbols │ close matches │ best search hit
  ├─ GraphTraversal (callers/callees/dependencies/impact/paths)
  ├─ _source_for ─► SourceReader.snippet ─► extract_comments / extract_conditions   (method targets only)
  ├─ FlowBuilder (explicit flow │ call_sequence by line │ unavailable) ─► extract_rules
  ├─ ContextBuilder.build (entities/relationships/flow/facts/source_code; char/4 token estimate)
  ├─ prompts.build_prompt(kind="code_walkthrough"|…) + SYSTEM_PROMPT
  ├─ OllamaProvider.generate (/api/chat, think=false, num_ctx) ─► free-text Markdown
  └─ AskResponse (answer facts + interpretation + evidence[cited by substring] + source + flow + timings)
AskPage ─► Markdown (react-markdown, no raw HTML) + linkify(entity names) + SourceCode viewer
```

Other relevant endpoints: `GET /api/entities/{id}`, `/relationships`, `/source`, `GET /api/flow/{id}`,
`/api/graph/*`, `POST /api/search`, `POST /api/index/rebuild`.

## 4. Reusable modules

| Need in plan | Existing module to reuse |
|---|---|
| Method identity/lookup, overloads | `OKFRepository.get/lookup/resolve`, `SymbolIndex` |
| Source span with line numbers, root-bounded | `SourceReader.snippet`, `SourceSnippet.numbered()` |
| Comments/conditions | `extract_comments`, `extract_conditions` |
| Calls with status + line | `OKFRepository.relationships()` (`Relationship.status`, `.line`), graph edges |
| Callees/cycles | `GraphStore.edges`, visited-set pattern from `GraphTraversal` |
| Local LLM | `LLMProvider` / `OllamaProvider` / `MockLLMProvider` |
| Cache | `AnswerCache` (file-based, TTL, version check), `cache_key` |
| Correlation ID, timings | `request_id_var`, HTTP middleware, `timed()` / `Timings` |
| UI | `EntityPanel` (tabs), `SourceCode`, `Markdown`, `EntityLink`, `api.ts`, `types/api.ts` |

## 5. Current method-explanation behaviour and gaps

Current behaviour: "Explain X" in Ask. When X resolves to a method and `source.root_dir` is set, the answer shows the
source location, verbatim comments and conditions, and a free-text LLM walkthrough.

| # | Gap vs plan | Where |
|---|---|---|
| G1 | Explanation depends on natural-language classification and target resolution. There is no explicit "explain this method ID" entry point, and this was the cause of the user-reported failure. | `AskService` |
| G2 | LLM output is free Markdown: no schema, no citation validation. Line references are never checked. | `prompts.py`, `AskService` |
| G3 | Only the selected method's body is included; callee bodies are never provided (no depth control). | `AskService._source_for` |
| G4 | Method body is cut at `source.max_lines` (800) with a note, and the token budget is not reconciled with `num_ctx`. The plan forbids silent truncation and asks for segmentation. | `SourceReader`, `ContextBuilder` |
| G5 | No prompt-injection guard: the system prompt does not say that evidence is untrusted data. | `prompts.py` |
| G6 | The cache key lacks prompt version, explanation options and source-file fingerprint, so edited source can return a stale answer. | `cache_service.cache_key` |
| G7 | Call-site parsing captures `— line N` but not `— lines N, M`, so multi-site calls lose their lines. | `okf/parser.py` |
| G8 | No Explain action in the entity panel; no structured rendering of steps and citations. | frontend |
| G9 | No synthetic benchmark fixture or checklist for explanation quality. | tests |

## 6. Proposed changes (Phases 1–7)

New package `codeknowledge/explain/` (orchestration kept out of `AskService`):

| File | Component |
|---|---|
| `explain/models.py` | Evidence item, explain options, structured explanation schema (Pydantic) |
| `explain/evidence.py` | `MethodEvidenceBuilder`: deterministic evidence (method, class, source span, fields, calls with status/lines, callee bodies to depth N, cycle-safe) |
| `explain/budget.py` | `EvidenceBudgetManager`: priority order, output-token reserve, never truncates the selected body (segments or warns instead) |
| `explain/prompt.py` | `MethodExplanationPromptBuilder`: versioned templates (`method-explanation-v1`, `method-summary-v1`) and delimited evidence blocks |
| `explain/validator.py` | `ExplanationResponseValidator`: schema check, citation-in-evidence check, unknown-entity check, one bounded repair |
| `explain/service.py` | `MethodExplanationService`: orchestration, cache, timings, logging |
| `api/routes_methods.py` | `POST /api/methods/{method_id}/explain` |

Changes to existing files: `config/settings.py` + `config/config.yaml` (`method_explanation:` section),
`llm/provider.py` + `llm/ollama.py` (`generate_json` using Ollama structured output `format`), `okf/parser.py`
(multi-line call sites, G7), `services/cache_service.py` (key builder reuse), `api/app.py` (wiring),
`services/ask_service.py` (for method targets, "Explain X" delegates to the new service, fixing G1 in Ask as well),
frontend (`EntityPanel` Explain action, `MethodExplanation` view, `api.ts`, `types/api.ts`), README.

Tests: `tests/fixtures/explain-java/` (synthetic Java source, no proprietary code),
`tests/fixtures/explain-okf/` (a Java2OKF-format bundle for it, hand-written to `docs/okf-output.md` because Java
is not available here; `scripts/regen_explain_fixture.sh` regenerates it with Java2OKF where Java exists),
`tests/fixtures/explain-checklist.yaml`, plus unit tests for evidence, budget, prompt and validator, and API and
frontend tests.

## 7. Facts not obtainable from current OKF

Method bodies, comments, control structure, argument expressions and SQL text all come from source via
`source.root_dir`. When source is unavailable, the explanation service returns metadata-only evidence with an
"Insufficient evidence: method body not available" warning, and never infers behaviour from names.
