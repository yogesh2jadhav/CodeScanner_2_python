"""Hybrid retrieval: exact symbol search + semantic search + graph expansion."""
from __future__ import annotations

from codeknowledge.graph.store import GraphStore
from codeknowledge.models.entities import EntitySummary
from codeknowledge.models.query import SearchHit, SearchRequest, SearchResponse
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.retrieval.embeddings import EmbeddingUnavailableError
from codeknowledge.retrieval.reranker import GRAPH_DECAY, Reranker
from codeknowledge.retrieval.semantic import SemanticIndex, SemanticUnavailableError
from codeknowledge.retrieval.symbol import SymbolIndex
from codeknowledge.utils.logging import get_logger
from codeknowledge.utils.timing import Timings, timed

logger = get_logger("HybridRetriever")

EXPANSION_SEEDS = 3
EXPANSION_TYPES = {"CALLS", "EXTENDS", "IMPLEMENTS", "DEPENDS_ON", "USES"}


def entity_summary(repo: OKFRepository, graph: GraphStore | None, entity_id: str) -> EntitySummary:
    doc = repo.get(entity_id)
    if doc:
        return EntitySummary.from_document(doc)
    node = (graph.get_node(entity_id) if graph else None) or {}
    return EntitySummary(
        id=entity_id,
        title=node.get("label", entity_id),
        type=node.get("type", "unresolved"),
        package=node.get("package"),
        status=node.get("status", "unresolved"),
    )


class HybridRetriever:
    def __init__(self, repo: OKFRepository, symbols: SymbolIndex, semantic: SemanticIndex | None,
                 graph: GraphStore | None, default_top_k: int):
        self.repo = repo
        self.symbols = symbols
        self.semantic = semantic
        self.graph = graph
        self.default_top_k = default_top_k

    def search(self, req: SearchRequest, timings: Timings | None = None) -> SearchResponse:
        timings = timings if timings is not None else Timings()
        top_k = req.top_k or self.default_top_k
        rr = Reranker()
        warnings: list[str] = []
        pool = top_k * 3  # over-fetch so post-filtering by type/package still fills top_k

        if req.mode in ("hybrid", "symbol"):
            with timed(logger, "symbol_search", timings):
                hits = self.symbols.search(req.query, pool)
                if req.mode == "hybrid":
                    # Also resolve identifiers embedded in a natural-language query.
                    hits += [h for h in self.symbols.resolve_question(req.query)]
                for h in hits:
                    rr.add(h.entity_id, h.score, "symbol", h.kind)

        if req.mode in ("hybrid", "semantic"):
            if self.semantic is None:
                warnings.append("Semantic search is not configured.")
            else:
                try:
                    with timed(logger, "semantic_search", timings):
                        for h in self.semantic.search(req.query, pool, req.entity_type, req.package):
                            rr.add(h.entity_id, max(h.score, 0.0), "semantic", "semantic similarity")
                except (SemanticUnavailableError, EmbeddingUnavailableError) as exc:
                    # Graceful degradation: symbol + graph results are still returned.
                    logger.warning("Semantic search unavailable: %s", exc)
                    warnings.append(f"Semantic search unavailable: {exc}")

        if req.expand_graph and self.graph is not None and req.mode == "hybrid":
            with timed(logger, "graph_expansion", timings):
                for seed in rr.ranked()[:EXPANSION_SEEDS]:
                    for e in self.graph.edges(seed.entity_id, "both", EXPANSION_TYPES):
                        other = e.target if e.source == seed.entity_id else e.source
                        arrow = "->" if e.source == seed.entity_id else "<-"
                        rr.add(other, seed.score * GRAPH_DECAY, "graph", f"{e.type} {arrow} {seed.entity_id}")

        results: list[SearchHit] = []
        for c in rr.ranked():
            ent = entity_summary(self.repo, self.graph, c.entity_id)
            if req.entity_type and ent.type.value != req.entity_type:
                continue
            if req.package and ent.package != req.package:
                continue
            results.append(SearchHit(entity=ent, score=c.score, match_types=c.match_types, matched_on=c.matched_on))
            if len(results) >= top_k:
                break
        return SearchResponse(query=req.query, mode=req.mode, hits=results, warnings=warnings, timings_ms=dict(timings))
