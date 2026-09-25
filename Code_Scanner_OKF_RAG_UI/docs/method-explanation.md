# Evidence-Grounded Method Explanation

"Explain this method" produces a step-by-step explanation. Every code-specific statement in it is tied to lines
that were actually sent to the local model, and the server checks those citations before the UI shows anything.
The baseline and the gap analysis are in [method-explanation-baseline.md](method-explanation-baseline.md).

## Responsibility boundary

| Component | Does | Does not |
|---|---|---|
| **Java2OKF** | Canonical IDs, signatures, source locations, calls with call-site lines, resolution markers | Method bodies, comments, LLM work (unchanged by this feature) |
| **CodeScanner** | Reads method bodies from `source.root_dir`, assembles and budgets evidence, prompts Ollama, validates, caches, renders | Parse Java into a second graph |
| **Ollama model** | Explains the supplied evidence as JSON | Decide symbols, line numbers, call targets or call status |

## Pipeline

```text
Explain tab / POST /api/methods/{id}/explain / Ask "Explain X"
  -> MethodEvidenceBuilder        deterministic: metadata, body (line-numbered), class, fields/constants,
                                  calls (status + call-site lines), callee bodies (depth, cycle-safe),
                                  callers (optional), SQL literals (optional)
  -> EvidenceBudgetManager        priority order, output-token reserve; never truncates the selected body
                                  (an oversized body is split into ordered segments)
  -> cache lookup                 key = bundle + method + options + budget + model + prompt version
                                  + evidence fingerprint (so edited source misses the cache)
  -> MethodExplanationPromptBuilder   versioned template, delimited evidence blocks
  -> Ollama /api/chat, format=<JSON schema>, think=false, num_ctx
  -> ExplanationResponseValidator schema, citations, call statuses (one bounded repair on bad JSON)
  -> MethodExplanationResponse    explanation + evidence + deterministic facts + warnings + model/timings
```

Code: `src/codeknowledge/explain/` (`models`, `evidence`, `budget`, `prompt`, `validator`, `render`, `service`),
`api/routes_methods.py`. UI: `frontend/src/components/ExplainPanel.tsx` and `MethodExplanation.tsx`.

## Evidence

| Kind | Source | Priority (kept first) |
|---|---|---|
| `method_source` | method body with Javadoc and annotations, `N| code` lines | 0 (mandatory) |
| `method_metadata` | OKF: declaration, return type, visibility, location | 1 (mandatory) |
| `class_metadata` | OKF: declaring type | 2 |
| `call` | OKF `## Calls`: target, status `resolved`/`unresolved`/`ambiguous`/`external`, all call-site lines | 3 |
| `field`, `sql_literal` | source: class fields/constants used in the body; SQL-looking string literals | 4 |
| `callee_source` | source: body of a resolved callee (depth ≤ `max_callee_depth`; non-accessors before getters/setters) | 4 + depth |
| `callee_signature` | callee with no body (interface or abstract method, or source missing): signature only, status `unavailable` | 5 + depth |
| `caller` | optional, at most 5 | 7 |

Evidence IDs (`E1`, `E2`, …) are deterministic for the same bundle, source and options. Segments of an oversized
body are numbered `E2.1`, `E2.2`, and so on.

## Validation policy

- Output that is not valid JSON for the schema gets **one** repair attempt (`max_repair_attempts`). If it is still
  invalid, the response contains the evidence and deterministic facts plus a warning. Raw model output is never
  shown.
- A `source_ref` must name an evidence block and a line range inside it; otherwise it is removed.
- Line mentions in prose (`L120`, `lines 120-130`) that are outside all evidence become `[unverified line]`.
- Items left without a valid citation are kept but flagged `grounded=false` (shown as **unverified**).
- A call's `evidence_status` is always recomputed from the evidence. A call is `body_inspected` only if that callee's
  body was supplied, `signature_only`, `unresolved` or `external` otherwise. Calls to targets absent from the
  evidence are removed. A call without a citation gets its OKF call-site lines attached.
- The JSON schema sent to the model requires at least one citation for branches, transformations, side effects,
  exceptions and calls. Server-side parsing is lenient, so one missing citation cannot discard a whole answer.

Prompt-injection guard: the system prompt declares that evidence is untrusted data, and delimiter-like text
(`<<<`, `>>>`) inside evidence is neutralised so source content cannot close an evidence block.

## API

```bash
curl -X POST "http://localhost:8000/api/methods/java-method:com.acme.visits.VisitProcessor.buildVisits(java.util.List,boolean)/explain" \
     -H "Content-Type: application/json" \
     -d '{"detail": "detailed", "max_callee_depth": 1, "include_caller_context": false, "force_refresh": false}'
```

Body fields (all optional): `detail` (`detailed` | `summary`), `max_callee_depth` (0–3),
`include_caller_context`, `include_related_config`, `include_sql_evidence`, `force_refresh`, `use_llm`
(`false` returns evidence and deterministic facts without calling the model).

| Status | When |
|---|---|
| 200 | Explanation, or a partial response with warnings (invalid model output, missing source, size limit) |
| 404 | Unknown method ID, not a method, or feature disabled |
| 422 | Invalid options or ID |
| 503 | Ollama unreachable or model not installed (`ollama pull <model>`) |
| 504 | Ollama timed out (`llm.timeout_seconds`) |

Error bodies are `{"detail": …, "request_id": …}`, with no stack traces. Every log line of a request carries the
same `request_id` (`EXPLAIN_REQUEST`, `EVIDENCE_READY`, `EXPLAIN_CACHE hit|miss`, `LLM_STARTED`,
`EXPLAIN_REPAIR`, `EXPLAIN_DONE`). Source and prompts are not logged unless
`method_explanation.debug_prompt_logging: true`, which logs a truncated prompt at DEBUG.

## UI

Open any method (Search, Explorer relations, Graph, a link in an answer), then go to the **Explain** tab. It is shown
only for methods and constructors. Choose Detail and Callee depth, then click **Explain method**. Cancel, Retry,
Regenerate (bypasses the cache) and **Evidence only** are available.

The result shows:
- summary, inputs and outputs
- numbered steps with certainty badges (`observed`, `derived`, `unknown`) and **unverified** flags
- branches, transformations, side effects and exceptions
- calls, linked to their entity panel, with their evidence status
- uncertainties and warnings
- the evidence list

Clicking a citation chip (e.g. `VisitProcessor.java:30-32`) opens that evidence with the lines highlighted.
**Copy Markdown** copies the rendered explanation. In Ask, "Explain `Class.method`" uses the same workflow.

## Configuration

`config/config.yaml` → `method_explanation:`. Environment overrides follow `CODEKNOWLEDGE_METHOD_EXPLANATION_<KEY>`.
Restart the backend after changes.

| Key | Default | Notes |
|---|---|---|
| `enabled` | `true` | |
| `default_detail` | `detailed` | |
| `max_callee_depth` | `1` | `0` = the selected method only |
| `max_callees_per_method` | `8` | callee bodies included per method (non-accessors first) |
| `max_evidence_documents` | `30` | |
| `max_source_lines_per_method` | `2500` | larger bodies are refused with a size-limit warning |
| `max_context_tokens` | `12000` | effective budget = min(this, `llm.num_ctx` − `output_token_reserve`) |
| `output_token_reserve` | `2500` | |
| `chars_per_token` | `3.5` | conservative estimate; no tokenizer dependency |
| `include_caller_context` / `include_related_config` / `include_sql_evidence` | `false` / `true` / `true` | |
| `validate_citations` | `true` | |
| `max_repair_attempts` | `1` | |
| `cache_enabled` | `true` | uses `cache.directory` and `cache.ttl_seconds` |
| `prompt_version` | `method-explanation-v1` | part of the cache key |
| `debug_prompt_logging` | `false` | |

Also required: `source.root_dir` (the Java project that Java2OKF analysed), `llm.num_ctx` (default 16384) and
`llm.timeout_seconds` (default 600).

## Tests

| Area | File |
|---|---|
| Evidence builder, budget (12.1, 12.2) | `tests/unit/test_explain_evidence.py` |
| Prompt, validator, service, cache, segments (12.3, 12.4) | `tests/unit/test_explain_llm.py` |
| API and Ask routing (12.4) | `tests/integration/test_api_explain.py` |
| Frontend (12.5) | `frontend/src/test/ExplainMethod.test.tsx` |
| Synthetic fixture (12.6) | `tests/fixtures/explain-java/`, `tests/fixtures/explain-okf/`, `tests/fixtures/explain-checklist.yaml` |

The fixture contains sequential stages, null checks and if/else, a stream with filter/group/min, a helper with its
body available (`groupByClaim`), a misleadingly named helper (`validate`), an interface method with no body
(`saveAll`), an UNRESOLVED call (`audit.record`), external JDK calls, DTO mutation, try/catch, a field update, a
SQL constant, a call cycle (`pingA`↔`pingB`), a misleading comment and a prompt-injection comment.

Java is not installed on the development Mac, so `tests/fixtures/explain-okf` was produced by
`scripts/make_explain_fixture.py` to the Java2OKF spec. Its call-site lines were checked against the source. Where
Java is available, run `scripts/regen_explain_fixture.sh` and diff the result against the committed copy.

Score any saved response against a checklist:

```bash
python scripts/eval_explanation.py --response explain.json --checklist tests/fixtures/explain-checklist.yaml
```

## Benchmark (real Ollama)

Method `VisitProcessor.buildVisits` (49 source lines) from the synthetic fixture, default options (depth 1),
about 3,700 estimated prompt tokens. Hardware: Apple M5, 24 GB, Ollama 0.34.4. Model: `qwen3:8b`
(`num_ctx` 16384, temperature 0.1, `think=false`), prompt `method-explanation-v1`, 2026-09-25.

| Run | Checklist coverage | Citation precision | Citations | Unverified items | Traps failed | LLM time |
|---|---|---|---|---|---|---|
| Without schema-required citations | 8/9 (89%) | 100% | 15 | 8 | none | 113 s |
| Schema-required citations (run 1) | 8/9 | 100% | 39 | 0 | none | 219 s |
| Schema-required citations (run 2) | 8/9 | 100% | 37 | 0 | none | 237 s |
| **Final prompt (covers the return statement)** | **9/9 (100%)** | **100%** | **34** | **0** | **none** | **214 s** |

Deterministic stages (evidence build, budget, prompt build, validation) take under 10 ms together; practically all
the time is model inference. Both schema-required runs produced the same six-step structure (repeatability).
Traps held in every run:
- the "sends reminder emails" comment was not presented as fact;
- the prompt-injection comment was ignored;
- `validate(...)` was explained as a converter;
- `saveAll` stayed `signature_only` and `audit.record` stayed `unresolved`.

Requiring citations roughly doubles the output, and therefore the latency; that is the accuracy/latency trade-off.
On CPU-only machines, expect several minutes per method. Use `detail: summary` or `max_callee_depth: 0` for faster
answers. These figures apply only to this model, prompt version and hardware.

Reproduce with `pytest -m llm tests/integration/test_llm_ollama.py::test_ollama_method_explanation_quality_gates`,
or save a response and run `scripts/eval_explanation.py`.

## Limitations

- Static analysis cannot determine runtime behaviour under reflection, dynamic dispatch (the callee is the declared
  target), dependency injection, library internals, configuration, database state or dynamically built SQL. The
  model is told to mark these as unknown.
- Callee bodies come only from `source.root_dir`. JDK and library bodies are never included.
- Token counts are estimates (`chars_per_token`). If the model's real context is smaller than `llm.num_ctx`, raise
  `output_token_reserve` or lower `max_context_tokens`.
- A segmented explanation (very large methods) uses the first part's summary; each part is explained in order but
  without full cross-part context.
- Quality depends on the model. The benchmark numbers apply only to the model, prompt version and hardware listed.
