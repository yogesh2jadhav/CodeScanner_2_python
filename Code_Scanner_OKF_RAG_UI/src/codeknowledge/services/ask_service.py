"""Question answering pipeline: classify -> plan -> retrieve -> graph/flow -> context -> (LLM) -> answer.

Deterministic facts are always computed from the graph/flow and returned even
when the LLM is disabled or unavailable; LLM output is attached separately as a
labelled interpretation.
"""
from __future__ import annotations

import re
import time

from codeknowledge.flow.analyzer import extract_rules
from codeknowledge.flow.path import Flow
from codeknowledge.graph.traversal import TraversalResult
from codeknowledge.llm.prompts import SYSTEM_PROMPT, build_prompt
from codeknowledge.llm.provider import LLMProvider, LLMUnavailableError
from codeknowledge.models.answers import AskRequest, AskResponse, Fact, RelationshipView, SourceView
from codeknowledge.models.entities import EntityType
from codeknowledge.models.query import QueryCategory as C
from codeknowledge.models.query import SearchRequest
from codeknowledge.query.classifier import QueryClassifier
from codeknowledge.query.context_builder import ContextBuilder, SourceCode
from codeknowledge.query.planner import QueryPlanner, StepType
from codeknowledge.retrieval.hybrid import entity_summary
from codeknowledge.services.cache_service import AnswerCache, cache_key
from codeknowledge.services.indexing_service import KnowledgeBase
from codeknowledge.source.reader import extract_comments, extract_conditions
from codeknowledge.utils.ids import new_request_id
from codeknowledge.utils.logging import get_logger, request_id_var
from codeknowledge.utils.timing import Timings, timed

logger = get_logger("AskService")

_FROM_TO_RE = re.compile(r"\bfrom\s+`?([\w.$#()]+)`?\s+to\s+`?([\w.$#()]+)`?", re.IGNORECASE)
_BETWEEN_RE = re.compile(r"\bbetween\s+`?([\w.$#()]+)`?\s+and\s+`?([\w.$#()]+)`?", re.IGNORECASE)
MAX_FLOW_METHODS = 3
CLOSE_MATCH_MIN = 0.55  # fuzzy symbol score needed to use a close match as the target
WALKTHROUGH_CATEGORIES = {C.FUNCTIONAL_EXPLANATION, C.FLOW, C.BUSINESS_RULE, C.GENERAL, C.METHOD_LOOKUP,
                          C.SEMANTIC_SEARCH}
FLOW_BONUS = 0.08
CALLS_BONUS = 0.04
MAX_LISTED = 25
ARROW = " → "


def _join_markdown(lines: list[str]) -> str:
    """Consecutive list items stay in one list; every other line becomes its own paragraph."""
    out: list[str] = []
    for i, line in enumerate(lines):
        if i and not (line.startswith("- ") and lines[i - 1].startswith("- ")):
            out.append("")
        out.append(line)
    return "\n".join(out).strip()


class AskService:
    def __init__(self, kb: KnowledgeBase, llm: LLMProvider | None, cache: AnswerCache | None = None):
        self.kb = kb
        self.llm = llm
        self.cache = cache
        self.settings = kb.settings

    # ----------------------------------------------------------------- helpers
    def label(self, eid: str) -> str:
        doc = self.kb.repo.get(eid)
        if doc:
            return doc.display_name()
        node = self.kb.graph.get_node(eid) if self.kb.graph else None
        return (node or {}).get("label", eid)

    def chain_text(self, ids: list[str]) -> str:
        return ARROW.join(self.label(i) for i in ids)

    def _resolve_one(self, token: str) -> str | None:
        hits = self.kb.symbols.search(token, top_k=1, fuzzy=False)
        return hits[0].entity_id if hits else None

    def _path_endpoints(self, question: str, symbols: list[str]) -> tuple[str, str] | None:
        for rx in (_FROM_TO_RE, _BETWEEN_RE):
            m = rx.search(question)
            if m:
                a, b = self._resolve_one(m.group(1)), self._resolve_one(m.group(2))
                if a and b:
                    return a, b
        return (symbols[0], symbols[1]) if len(symbols) >= 2 else None

    def _retrieval_config(self) -> dict:
        r = self.settings.retrieval
        return {"retrieval": r.model_dump(), "embedding": self.settings.embedding.model,
                "vector_top_k": self.settings.vector.top_k}

    # -------------------------------------------------------------------- main
    def ask(self, req: AskRequest, request_id: str | None = None) -> AskResponse:
        self.kb.require_ready()
        request_id = request_id or new_request_id()
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        timings = Timings()
        try:
            return self._ask(req, request_id, timings, start)
        finally:
            request_id_var.reset(token)

    def _ask(self, req: AskRequest, request_id: str, timings: Timings, start: float) -> AskResponse:
        kb = self.kb
        question = req.question.strip()
        logger.info("QUERY_RECEIVED length=%d use_llm=%s", len(question), req.use_llm)

        model = self.llm.model if self.llm else "none"
        key = cache_key(question, kb.repo.bundle_hash, model, self._retrieval_config(), req.use_llm)
        if self.cache and req.use_cache:
            hit = self.cache.get(key, kb.repo.bundle_hash)
            if hit:
                resp = AskResponse.model_validate(hit["response"])
                resp.request_id, resp.cached = request_id, True
                resp.timings_ms = {"total": round((time.perf_counter() - start) * 1000, 2)}
                logger.info("ANSWER_RETURNED cached=true")
                return resp

        classifier = QueryClassifier(kb.symbols, self.llm if req.use_llm else None,
                                     self.settings.retrieval.classifier_confidence_threshold)
        with timed(logger, "classify", timings):
            cls = classifier.classify(question)
        plan = QueryPlanner(self.settings.retrieval.graph_max_depth).plan(cls, question)
        cat = plan.category
        warnings: list[str] = []
        ctxb = ContextBuilder(kb.repo, self.settings.retrieval.max_context_documents,
                              self.settings.retrieval.max_context_tokens)

        # ---- target identification: exact symbols first, semantic search otherwise
        targets = list(cls.symbols)
        search_hits = []
        needs_search = plan.has(StepType.SEMANTIC_SEARCH) or cat in (
            C.FUNCTIONAL_EXPLANATION, C.BUSINESS_RULE, C.FLOW, C.GENERAL, C.SEMANTIC_SEARCH, C.ARCHITECTURE)
        if needs_search:
            logger.info("SEARCH_STARTED")
            sr = kb.retriever.search(SearchRequest(query=question, top_k=self.settings.retrieval.semantic_top_k,
                                                   expand_graph=False), timings)
            warnings.extend(sr.warnings)
            search_hits = sr.hits
            logger.info("SEARCH_COMPLETED hits=%d", len(search_hits))
            for h in search_hits:
                ctxb.add_entity(h.entity.id, h.score, "semantic" if "semantic" in h.match_types else "symbol",
                                f"{'/'.join(h.match_types)} match")
            if not targets and search_hits:
                prefer_methods = cat in (C.FLOW, C.BUSINESS_RULE, C.FUNCTIONAL_EXPLANATION)
                ranked = [h for h in search_hits if h.entity.status == "resolved"]
                if prefer_methods:
                    # Among close semantic matches, a method with explicit flow or outgoing calls
                    # explains more than a leaf method, so it gets a small boost.
                    def informative(h) -> float:
                        doc = kb.repo.get(h.entity.id)
                        bonus = FLOW_BONUS if doc and doc.metadata.get("flow") else 0.0
                        if kb.graph.edges(h.entity.id, "out", {"CALLS"}):
                            bonus += CALLS_BONUS
                        return h.score + bonus

                    methods = sorted((h for h in ranked if h.entity.type == EntityType.METHOD), key=lambda h: -informative(h))
                    ranked = methods + [h for h in ranked if h.entity.type != EntityType.METHOD]
                targets = [h.entity.id for h in ranked[:2]]

        # A code-like name that matched nothing exactly (typo, partial name): try close matches
        # before falling back to semantic guesses.
        if not cls.symbols:
            close = [h for h in kb.symbols.close_matches(question) if h.score >= CLOSE_MATCH_MIN]
            if close:
                targets = [close[0].entity_id] + [t for t in targets if t != close[0].entity_id]
        primary = targets[0] if targets else None
        facts: list[Fact] = []
        paths: list[list[str]] = []
        flow: Flow | None = None
        lines: list[str] = []
        if primary and not cls.symbols:
            # Be explicit when the target is a best guess from search rather than a named symbol.
            note = f"No exact symbol was named; using the closest search match: {self.label(primary)}."
            warnings.append(note)
            lines.append(f"_{note}_")
        for t in targets:
            ctxb.add_entity(t, 1.0, "target", "target entity")

        # ---- graph expansion
        logger.info("GRAPH_EXPANSION category=%s target=%s depth=%d", cat.value, primary, plan.graph_depth)
        with timed(logger, "graph_expansion", timings):
            if primary is None and cat not in (C.ARCHITECTURE, C.GENERAL, C.SEMANTIC_SEARCH):
                lines.append("I could not identify a code entity for this question in the knowledge base. "
                             "Try naming a class or method (e.g. `ClassName.methodName`).")
                candidates = kb.symbols.close_matches(question) or []
                if candidates:
                    lines.append("Did you mean:")
                    lines.extend(f"- {self.label(h.entity_id)}" for h in candidates)
                    for h in candidates:
                        ctxb.add_entity(h.entity_id, h.score, "symbol", "close name match")
            elif cat in (C.CALLERS, C.CALLEES, C.DEPENDENCIES, C.IMPACT_ANALYSIS):
                lines += self._traversal_answer(cat, cls.direction, primary, plan.graph_depth, cls.transitive,
                                                ctxb, facts, paths)
            elif cat == C.PATH:
                lines += self._path_answer(question, targets, ctxb, facts, paths)
            elif cat in (C.CLASS_LOOKUP, C.METHOD_LOOKUP):
                lines += self._lookup_answer(primary, ctxb, facts)
            elif cat == C.ARCHITECTURE:
                lines += self._architecture_answer(targets, ctxb, facts)
            elif cat == C.SEMANTIC_SEARCH:
                lines += self._search_answer(search_hits)
            elif primary:
                lines += self._neighbourhood(primary, ctxb, facts)

        # ---- real source code + developer comments (when source.root_dir is configured)
        source_view: SourceView | None = None
        if primary and cat not in (C.CALLERS, C.CALLEES, C.DEPENDENCIES, C.IMPACT_ANALYSIS, C.PATH, C.ARCHITECTURE):
            with timed(logger, "source_read", timings):
                source_view = self._source_for(primary, ctxb, facts, lines, cat)

        # ---- flow / rules
        if primary and plan.has(StepType.FLOW):
            with timed(logger, "flow_build", timings):
                flow = self._flow_for(primary, ctxb, facts, lines, quiet_if_unavailable=source_view is not None)
            if flow and plan.has(StepType.RULES):
                rules = extract_rules(flow)
                ctxb.rules = [r.model_dump() for r in rules]
                for r in rules:
                    claim = f"IF {r.condition} THEN {', '.join(r.then) or '(nothing)'} ELSE {', '.join(r.otherwise) or '(nothing)'}"
                    facts.append(Fact(claim=claim, evidence=[r.entity_id]))
                if not rules and not (source_view and source_view.conditions):
                    lines.append("No explicit conditional logic is recorded for this entity in the OKF bundle.")

        ctxb.facts = [f.claim for f in facts]
        with timed(logger, "context_build", timings):
            ctx = ctxb.build(question, cat.value, primary)
        logger.info("CONTEXT_BUILT entities=%d relationships=%d est_tokens=%d truncated=%s",
                    len(ctx.entities), len(ctx.relationships), ctx.estimated_tokens(), ctx.truncated)

        # ---- LLM explanation (optional)
        interpretation, llm_error, llm_used = None, None, False
        if plan.requires_llm and req.use_llm and self.llm is not None:
            if not ctx.entities:
                llm_error = "No evidence found; LLM not called to avoid an unsupported answer."
            else:
                logger.info("LLM_STARTED provider=%s model=%s", self.llm.name, self.llm.model)
                try:
                    with timed(logger, "llm", timings):
                        # With the real code available, explain it block by block instead of
                        # reasoning from call lists alone.
                        kind = "code_walkthrough" if (source_view and cat in WALKTHROUGH_CATEGORIES) else plan.prompt_kind
                        interpretation = self.llm.generate(build_prompt(question, ctx, kind), SYSTEM_PROMPT)
                    llm_used = True
                    logger.info("LLM_COMPLETED chars=%d", len(interpretation))
                except LLMUnavailableError as exc:
                    llm_error = f"LLM unavailable: {exc}"
                    logger.warning("LLM_FAILED %s", exc)
        elif plan.requires_llm and not req.use_llm:
            warnings.append("LLM disabled for this request; returning deterministic facts only.")

        evidence = ctx.evidence
        if interpretation:
            low = interpretation.lower()
            for ev in evidence:
                ev.cited = ev.entity_id.lower() in low or ev.title.lower() in low

        answer = _join_markdown(lines) or "No deterministic facts were found for this question."
        timings["total"] = round((time.perf_counter() - start) * 1000, 2)
        resp = AskResponse(
            request_id=request_id, question=question, category=cat.value, confidence=cls.confidence,
            classification_method=cls.method, plan=plan.describe(), target=primary, answer=answer, facts=facts,
            interpretation=interpretation, evidence=evidence,
            related_entities=[entity_summary(kb.repo, kb.graph, e.id) for e in ctx.entities if e.id != primary][:MAX_LISTED],
            relationships=ctxb.relationships[:200], paths=paths, flow=flow, source=source_view, llm_used=llm_used,
            llm_model=self.llm.model if (self.llm and llm_used) else None, llm_error=llm_error,
            warnings=warnings, timings_ms=dict(timings), knowledge_base_version=kb.repo.bundle_hash[:12],
        )
        logger.info("ANSWER_RETURNED category=%s facts=%d evidence=%d llm_used=%s timings=%s",
                    cat.value, len(facts), len(evidence), llm_used, dict(timings))
        if self.cache and req.use_cache and not llm_error:
            self.cache.put(key, question, kb.repo.bundle_hash, resp.model_dump(mode="json"))
        return resp

    # -------------------------------------------------------- answer builders
    def _record_traversal(self, res: TraversalResult, ctxb: ContextBuilder) -> None:
        for e in res.edges:
            ctxb.add_relationship(e.source, e.target, e.type, e.attrs.get("status", "resolved"))
        for nid, depth in res.nodes.items():
            if nid != res.root:
                ctxb.add_entity(nid, 1.0 / (1 + depth), "graph", f"graph depth {depth}")

    def _traversal_answer(self, cat, direction, primary, depth, transitive, ctxb, facts, paths) -> list[str]:
        t = self.kb.traversal
        name = self.label(primary)
        if cat == C.CALLERS:
            res, verb, empty = t.callers(primary, depth), "is called by", "No callers of {} were found in the OKF graph."
        elif cat == C.CALLEES:
            res, verb, empty = t.callees(primary, depth), "calls", "{} does not call any known entity."
        elif cat == C.IMPACT_ANALYSIS:
            res, verb, empty = t.impact(primary, depth), "may impact", "Nothing depends on {} in the OKF graph."
        elif direction == "in":
            res, verb, empty = t.dependents(primary, depth), "is depended on by", "Nothing depends on {} in the OKF graph."
        else:
            res, verb, empty = t.dependencies(primary, depth), "depends on", "{} has no recorded dependencies."
        self._record_traversal(res, ctxb)

        if cat == C.CALLEES and transitive:
            chains = [c for c in t.reachable_call_chains(primary, depth) if len(c) > 1]
            if chains:
                paths.extend(chains)
                out = [f"Call chains starting at {name}:"]
                for c in chains[:MAX_LISTED]:
                    text = self.chain_text(c)
                    out.append(f"- {text}")
                    facts.append(Fact(claim=text, evidence=c))
                    for n in c:
                        ctxb.add_entity(n, 1.0, "path", "on call chain")
                return out

        ids = res.ids()
        if not ids:
            return [empty.format(name)]
        out = [f"{name} {verb}:"]
        for nid in ids[:MAX_LISTED * 2]:
            rel_edges = [e for e in res.edges if nid in (e.source, e.target)]
            rtypes = sorted({e.type for e in rel_edges})
            status = " (unresolved)" if (self.kb.graph.get_node(nid) or {}).get("status") == "unresolved" else ""
            depth_note = f", depth {res.nodes[nid]}" if res.nodes[nid] > 1 else ""
            out.append(f"- {self.label(nid)} ({', '.join(rtypes)}{depth_note}){status}")
            facts.append(Fact(claim=f"{name} {verb} {self.label(nid)} via {', '.join(rtypes)}", evidence=[primary, nid]))
        if len(ids) > MAX_LISTED * 2:
            out.append(f"- … and {len(ids) - MAX_LISTED * 2} more")
        return out

    def _path_answer(self, question, targets, ctxb, facts, paths) -> list[str]:
        ends = self._path_endpoints(question, targets)
        if not ends:
            return ["A path question needs two entities (e.g. 'path from A to C')."]
        a, b = ends
        path = self.kb.traversal.call_paths(a, b)
        if not path:
            return [f"No directed relationship path from {self.label(a)} to {self.label(b)} was found."]
        paths.append(path)
        for x, y in zip(path, path[1:]):
            types = sorted({e.type for e in self.kb.graph.edges(x, "out") if e.target == y})
            ctxb.add_relationship(x, y, "/".join(types))
        for n in path:
            ctxb.add_entity(n, 1.0, "path", "on path")
        text = self.chain_text(path)
        facts.append(Fact(claim=text, evidence=path))
        return [f"Path from {self.label(a)} to {self.label(b)}:", text]

    def _neighbourhood(self, eid, ctxb, facts) -> list[str]:
        edges = self.kb.graph.edges(eid, "both")
        for e in edges:
            ctxb.add_relationship(e.source, e.target, e.type, e.attrs.get("status", "resolved"))
            other = e.target if e.source == eid else e.source
            ctxb.add_entity(other, 0.6, "graph", f"{e.type} neighbour")
            if e.type != "CONTAINS":
                facts.append(Fact(claim=f"{self.label(e.source)} {e.type} {self.label(e.target)}", evidence=[e.source, e.target]))
        return []

    def _lookup_answer(self, eid, ctxb, facts) -> list[str]:
        doc = self.kb.repo.get(eid)
        out = []
        if doc:
            out.append(f"{doc.display_name()} ({doc.type.value})" + (f" in package {doc.package}" if doc.package else ""))
            if doc.signature:
                out.append(f"Signature: {doc.signature}")
            if doc.source_file:
                out.append(f"Source: {doc.source_file}" + (f":{doc.source_line}" if doc.source_line else ""))
            if doc.summary:
                out.append(f"Summary: {doc.summary}")
        self._neighbourhood(eid, ctxb, facts)
        by_type: dict[str, list[str]] = {}
        for e in self.kb.graph.edges(eid, "out"):
            by_type.setdefault(e.type, []).append(self.label(e.target))
        for e in self.kb.graph.edges(eid, "in"):
            by_type.setdefault(f"{e.type} (incoming)", []).append(self.label(e.source))
        for rtype, names in sorted(by_type.items()):
            out.append(f"- {rtype}: {', '.join(sorted(names)[:MAX_LISTED])}")
        return out

    def _architecture_answer(self, targets, ctxb, facts) -> list[str]:
        g = self.kb.graph
        packages = sorted(n["id"] for n in g.nodes() if n.get("type") == EntityType.PACKAGE.value)
        out = [f"Packages ({len(packages)}):"]
        for p in packages[:MAX_LISTED]:
            members = [e.target for e in g.edges(p, "out", {"CONTAINS"})]
            out.append(f"- {p}: {len(members)} types")
            for m in members:
                ctxb.add_entity(m, 0.5, "graph", f"member of {p}")
                ctxb.add_relationship(p, m, "CONTAINS")
                for e in g.edges(m, "out", {"EXTENDS", "IMPLEMENTS", "DEPENDS_ON"}):
                    ctxb.add_relationship(e.source, e.target, e.type)
                    facts.append(Fact(claim=f"{self.label(e.source)} {e.type} {self.label(e.target)}",
                                      evidence=[e.source, e.target]))
        for t in targets:
            self._neighbourhood(t, ctxb, facts)
        return out

    def _search_answer(self, hits) -> list[str]:
        if not hits:
            return ["No matching entities found."]
        out = ["Most relevant entities:"]
        for h in hits[:10]:
            loc = f" — {h.entity.source_file}:{h.entity.source_line}" if h.entity.source_file else ""
            out.append(f"- {h.entity.title} ({h.entity.type.value}, score {h.score:.2f}){loc}")
        return out

    def _source_for(self, primary, ctxb, facts, lines, cat) -> SourceView | None:
        """Attach the method's code; comments and conditions become deterministic facts."""
        doc = self.kb.repo.get(primary)
        if doc is None or doc.type != EntityType.METHOD:
            return None
        if not self.kb.source.enabled:
            if cat in WALKTHROUGH_CATEGORIES:
                # Without source the answer can only use structure; say so instead of looking thin.
                lines.append("_The OKF bundle has no method code or comments. Set `source.root_dir` in "
                             "config/config.yaml to the Java project folder to get a step-by-step explanation "
                             "based on the real code and its comments._")
            return None
        snippet = self.kb.source.snippet(doc)
        if snippet is None:
            lines.append(f"_Source for {doc.display_name()} not found under source.root_dir "
                         f"({doc.source_file})._")
            return None
        comments = extract_comments(snippet)
        conditions = extract_conditions(snippet)
        view = SourceView(
            entity_id=primary, file=snippet.file, start_line=snippet.start_line, decl_line=snippet.decl_line,
            end_line=snippet.end_line, code=snippet.text, truncated=snippet.truncated, notes=snippet.notes,
            comments=[{"start_line": c.start_line, "end_line": c.end_line, "kind": c.kind, "text": c.text}
                      for c in comments],
            conditions=[{"line": c.line, "kind": c.kind, "expression": c.expression} for c in conditions])
        ctxb.source_code.append(SourceCode(
            entity_id=primary, file=snippet.file, start_line=snippet.start_line, end_line=snippet.end_line,
            code=snippet.numbered(),
            comments=[f"L{c.start_line}-L{c.end_line}: {c.text}" for c in comments],
            conditions=[f"L{c.line} {c.kind}: {c.expression}" for c in conditions]))

        name = doc.display_name()
        lines.append(f"Source: {snippet.file} lines {snippet.start_line}-{snippet.end_line}")
        lines.extend(f"_Note: {n}_" for n in snippet.notes)
        if comments:
            lines.append(f"Developer comments in {name} (verbatim from source):")
            for c in comments:
                loc = f"L{c.start_line}" + (f"-L{c.end_line}" if c.end_line != c.start_line else "")
                lines.append(f"- **{loc}**: " + " ".join(c.text.split()))
        else:
            lines.append(f"{name} has no comments in its source.")
        if conditions:
            lines.append("Conditions and branches in the code:")
            for c in conditions:
                lines.append(f"- **L{c.line}** {c.kind}: `{c.expression}`")
                if cat == C.BUSINESS_RULE:
                    facts.append(Fact(claim=f"L{c.line} {c.kind}: {c.expression}", evidence=[primary]))
        return view

    def _flow_for(self, primary, ctxb, facts, lines, quiet_if_unavailable: bool = False) -> Flow | None:
        fb = self.kb.flows
        doc = self.kb.repo.get(primary)
        candidates = [primary]
        if doc and doc.type in (EntityType.CLASS, EntityType.INTERFACE):
            # For a class, show flows of its methods that have explicit flow metadata.
            members = [e.target for e in self.kb.graph.edges(primary, "out", {"CONTAINS"})]
            with_flow = [m for m in members if (self.kb.repo.get(m) and self.kb.repo.get(m).metadata.get("flow"))]
            candidates = with_flow[:MAX_FLOW_METHODS] or [primary]
        first: Flow | None = None
        for c in candidates:
            f = fb.build(c, self.settings.retrieval.graph_max_depth)
            if f is None:
                continue
            first = first or f
            ctxb.add_flow(f)
            if quiet_if_unavailable and f.availability == "unavailable":
                continue  # the source code section already shows what the method does
            lines.append(f"Flow of {f.title} (availability: {f.availability}):")
            if f.nodes:
                lines.append("```text\n" + f.render_text() + "\n```")
            lines.extend(f"_Note: {n}_" for n in f.notes)
            for ch in f.call_chains[:5]:
                facts.append(Fact(claim=self.chain_text(ch), evidence=ch))
        return first
