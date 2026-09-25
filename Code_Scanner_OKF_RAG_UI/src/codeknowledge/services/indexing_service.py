"""KnowledgeBase: loads OKF and owns all derived indexes.

Why one container: the repository, graph, symbol index and vector index must all
describe the same OKF bundle version. Loading/rebuilding them together (keyed by
bundle hash) prevents mixing a new graph with a stale vector index silently.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from codeknowledge.config.settings import Settings
from codeknowledge.flow.builder import FlowBuilder
from codeknowledge.graph.builder import GraphBuilder
from codeknowledge.graph.networkx_store import NetworkXGraphStore
from codeknowledge.graph.store import GraphStore
from codeknowledge.graph.traversal import GraphTraversal
from codeknowledge.okf.loader import OKFSourceMissingError
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.retrieval.embeddings import EmbeddingUnavailableError, create_embedding_provider
from codeknowledge.retrieval.hybrid import HybridRetriever
from codeknowledge.retrieval.semantic import SemanticIndex, SemanticUnavailableError
from codeknowledge.retrieval.symbol import SymbolIndex
from codeknowledge.source.reader import SourceReader
from codeknowledge.utils.logging import get_logger
from codeknowledge.utils.timing import Timings, timed

logger = get_logger("IndexingService")


class KnowledgeBaseNotReadyError(RuntimeError):
    pass


def create_graph_store(settings: Settings) -> GraphStore:
    if settings.graph.provider == "networkx":
        return NetworkXGraphStore()
    raise ValueError(f"Unknown graph provider: {settings.graph.provider} (supported: networkx)")


@dataclass
class IndexStatus:
    ready: bool = False
    error: str | None = None
    documents: int = 0
    graph_nodes: int = 0
    graph_edges: int = 0
    unresolved_relationships: int = 0
    external_relationships: int = 0
    vector_documents: int = 0
    vector_status: str = "unknown"  # ok | stale | empty | unavailable
    vector_run: dict = field(default_factory=dict)
    bundle_hash: str | None = None
    ingestion: dict = field(default_factory=dict)
    timings_ms: dict = field(default_factory=dict)


class KnowledgeBase:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock = threading.RLock()
        self.status = IndexStatus()
        self.repo: OKFRepository | None = None
        self.graph: GraphStore | None = None
        self.symbols: SymbolIndex | None = None
        self.semantic: SemanticIndex | None = None
        self.retriever: HybridRetriever | None = None
        self.traversal: GraphTraversal | None = None
        self.flows: FlowBuilder | None = None
        self.source = SourceReader(settings.source.root_dir, settings.source.max_lines)
        if settings.source.root_dir and not self.source.enabled:
            logger.warning("source.root_dir does not exist: %s (source-based explanations disabled)",
                           settings.source.root_dir)

    # ------------------------------------------------------------------ loading
    def load(self, rebuild: bool = False, rebuild_vectors: bool | None = None, progress=None,
             full_vectors: bool = False) -> IndexStatus:
        """Load OKF and indexes. Graph is rebuilt when the bundle changed; the vector
        index is only rebuilt when asked (embedding a large bundle is slow)."""
        timings = Timings()
        with self.lock:
            status = IndexStatus()
            try:
                with timed(logger, "okf_load", timings):
                    repo = OKFRepository.from_directory(self.settings.okf.source_dir)
            except OKFSourceMissingError as exc:
                status.error = str(exc)
                self.status = status
                logger.error("%s", exc)
                return status

            graph = create_graph_store(self.settings)
            persisted = None if rebuild else graph.load(self.settings.graph.persist_directory)
            if persisted and persisted.get("bundle_hash") == repo.bundle_hash:
                logger.info("Loaded persisted graph (bundle unchanged)")
            else:
                with timed(logger, "graph_build", timings):
                    GraphBuilder(graph).build(repo)
                    graph.save(self.settings.graph.persist_directory, {"bundle_hash": repo.bundle_hash})

            with timed(logger, "symbol_index", timings):
                symbols = SymbolIndex(repo)

            semantic = None
            try:
                semantic = SemanticIndex(self.settings.vector, create_embedding_provider(self.settings.embedding))
                indexed = semantic.indexed_bundle_hash()
                do_vectors = rebuild if rebuild_vectors is None else rebuild_vectors
                if do_vectors:
                    with timed(logger, "vector_index", timings):
                        run = semantic.rebuild(repo, progress, full=full_vectors, source=self.source)
                    status.vector_run = {"embedded": run.embedded, "unchanged": run.unchanged, "removed": run.removed}
                    status.vector_status = "ok"
                elif semantic.count() == 0:
                    status.vector_status = "empty"
                elif indexed != repo.bundle_hash:
                    status.vector_status = "stale"
                    logger.warning("Vector index is stale (OKF changed); run rebuild to refresh")
                else:
                    status.vector_status = "ok"
                status.vector_documents = semantic.count()
            except (SemanticUnavailableError, EmbeddingUnavailableError, ValueError) as exc:
                # Vector store problems must not take down graph/explorer features.
                if isinstance(exc, EmbeddingUnavailableError):
                    # Expected operational condition (Ollama down): one clear line, no traceback.
                    logger.error("Semantic index unavailable: %s", exc)
                else:
                    logger.exception("Semantic index unavailable")
                status.vector_status = "unavailable"
                status.error = f"Semantic index unavailable: {exc}"
                semantic = None

            self.repo, self.graph, self.symbols, self.semantic = repo, graph, symbols, semantic
            self.retriever = HybridRetriever(repo, symbols, semantic, graph, self.settings.retrieval.semantic_top_k)
            self.traversal = GraphTraversal(graph)
            self.flows = FlowBuilder(repo, graph)

            stats = graph.stats()
            rels = repo.relationships()
            status.ready = True
            status.documents = len(repo.documents)
            status.graph_nodes, status.graph_edges = stats["nodes"], stats["edges"]
            status.unresolved_relationships = sum(1 for r in rels if r.status == "unresolved")
            status.external_relationships = sum(1 for r in rels if r.status == "external")
            status.bundle_hash = repo.bundle_hash
            r = repo.report
            status.ingestion = {"discovered": r.discovered, "valid": r.valid, "warnings": r.warnings,
                                "errors": r.errors, "links": r.links}
            status.timings_ms = dict(timings)
            self.status = status
            logger.info("Knowledge base ready documents=%d nodes=%d edges=%d vector=%s",
                        status.documents, status.graph_nodes, status.graph_edges, status.vector_status)
            return status

    def require_ready(self) -> None:
        if not self.status.ready or self.repo is None:
            raise KnowledgeBaseNotReadyError(self.status.error or "Knowledge base is not loaded")
