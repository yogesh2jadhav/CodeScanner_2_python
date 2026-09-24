"""OKF -> Loader -> Graph -> Vector Index -> Query -> Context."""
from codeknowledge.config.settings import VectorSettings
from codeknowledge.graph.builder import GraphBuilder
from codeknowledge.graph.networkx_store import NetworkXGraphStore
from codeknowledge.okf.loader import OKFLoader
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.query.classifier import QueryClassifier
from codeknowledge.query.context_builder import ContextBuilder
from codeknowledge.query.planner import QueryPlanner, StepType
from codeknowledge.retrieval.embeddings import HashEmbeddingProvider
from codeknowledge.retrieval.hybrid import HybridRetriever
from codeknowledge.models.query import SearchRequest
from codeknowledge.retrieval.semantic import SemanticIndex
from codeknowledge.retrieval.symbol import SymbolIndex
from codeknowledge.graph.traversal import GraphTraversal
from tests.conftest import SAMPLE_OKF

P = "com.example.claim"


def test_full_pipeline(tmp_path):
    load = OKFLoader(SAMPLE_OKF).load()
    assert load.report.errors == 0
    repo = OKFRepository(load)
    graph = GraphBuilder(NetworkXGraphStore()).build(repo)
    semantic = SemanticIndex(VectorSettings(persist_directory=str(tmp_path)), HashEmbeddingProvider())
    assert semantic.rebuild(repo) == 24
    symbols = SymbolIndex(repo)

    q = "Who calls CasingService.processClaims?"
    cls = QueryClassifier(symbols).classify(q)
    plan = QueryPlanner(3).plan(cls, q)
    assert plan.has(StepType.GRAPH_REVERSE) and not plan.requires_llm

    retriever = HybridRetriever(repo, symbols, semantic, graph, 10)
    hits = retriever.search(SearchRequest(query=q)).hits
    assert hits[0].entity.id == f"{P}.CasingService.processClaims"

    res = GraphTraversal(graph).callers(cls.symbols[0])
    cb = ContextBuilder(repo, 20, 6000)
    cb.add_entity(cls.symbols[0], 1.0, "target", "target")
    for e in res.edges:
        cb.add_relationship(e.source, e.target, e.type)
        cb.add_entity(e.source, 0.9, "graph", "caller")
    for h in hits:
        cb.add_entity(h.entity.id, h.score, "semantic", "search")
    ctx = cb.build(q, cls.category.value, cls.symbols[0])
    assert ctx.entities[0].id == f"{P}.CasingService.processClaims"
    assert ctx.entities[1].id == f"{P}.ClaimService.processClaim"
    assert ctx.relationships[0].type == "CALLS"
    assert all(e.document for e in ctx.evidence)
