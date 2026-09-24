import pytest

from codeknowledge.config.settings import VectorSettings
from codeknowledge.graph.builder import GraphBuilder
from codeknowledge.graph.networkx_store import NetworkXGraphStore
from codeknowledge.models.query import SearchRequest
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.retrieval.embeddings import EmbeddingUnavailableError, HashEmbeddingProvider, OllamaEmbeddingProvider
from codeknowledge.retrieval.hybrid import HybridRetriever
from codeknowledge.retrieval.representation import build_metadata, build_retrieval_text
from codeknowledge.retrieval.reranker import Reranker
from codeknowledge.retrieval.semantic import SemanticIndex
from codeknowledge.retrieval.symbol import SymbolIndex, extract_symbols
from tests.conftest import SAMPLE_OKF

P = "com.example.claim"


@pytest.fixture(scope="module")
def repo():
    return OKFRepository.from_directory(SAMPLE_OKF)


@pytest.fixture(scope="module")
def symbols(repo):
    return SymbolIndex(repo)


@pytest.fixture(scope="module")
def semantic(repo, tmp_path_factory):
    idx = SemanticIndex(VectorSettings(persist_directory=str(tmp_path_factory.mktemp("vec"))), HashEmbeddingProvider())
    idx.rebuild(repo)
    return idx


# --- symbol search ---------------------------------------------------------

def test_exact_fqn(symbols):
    [h, *_] = symbols.search(f"{P}.CasingService.processClaims")
    assert h.entity_id == f"{P}.CasingService.processClaims" and h.score == 1.0


def test_class_method_notation_and_parens(symbols):
    assert symbols.search("CasingService.processClaims()")[0].entity_id == f"{P}.CasingService.processClaims"
    assert symbols.search("CasingService#processClaims")[0].entity_id == f"{P}.CasingService.processClaims"


def test_distinguishes_similar_names(symbols):
    assert symbols.search("processClaim")[0].entity_id == f"{P}.ClaimService.processClaim"
    assert symbols.search("processClaims")[0].entity_id == f"{P}.CasingService.processClaims"


def test_class_name_case_insensitive(symbols):
    assert symbols.search("claimservice")[0].entity_id == f"{P}.ClaimService"


def test_package_and_source_file(symbols):
    assert symbols.search(P)[0].entity_id == P
    assert symbols.search("CasingService.java")[0].entity_id == f"{P}.CasingService"


def test_fuzzy_prefix_ranks_below_exact(symbols):
    hits = symbols.search("Claim")
    assert hits and all(h.score < 0.9 for h in hits)


def test_extract_symbols():
    assert extract_symbols("Who calls CasingService.processClaims()?") == ["CasingService.processClaims"]
    assert extract_symbols("what does `save` do") == ["save"]
    assert extract_symbols("how is the discharge date calculated") == []


def test_resolve_question(symbols):
    ids = [h.entity_id for h in symbols.resolve_question("Who calls processClaim?")]
    assert ids[0] == f"{P}.ClaimService.processClaim"
    # plain words fall back to exact name matches only
    assert [h.entity_id for h in symbols.resolve_question("who calls isEligible")] == [f"{P}.ClaimValidator.isEligible"]


# --- representation / semantic --------------------------------------------

def test_retrieval_representation(repo):
    doc = repo.get(f"{P}.CasingService.processClaims")
    text = build_retrieval_text(doc, repo.relationships())
    assert text.startswith("Title: CasingService.processClaims\nType: method")
    assert "Package: com.example.claim" in text and "CALLS:" in text and "CALLED_BY: processClaim" in text
    meta = build_metadata(doc)
    assert meta["entity_type"] == "method" and meta["class_name"] == "CasingService"
    assert None not in meta.values()


def test_semantic_index_and_search(semantic, repo):
    assert semantic.count() == len(repo.documents)
    assert semantic.indexed_bundle_hash() == repo.bundle_hash
    ids = [h.entity_id for h in semantic.search("where is discharge date set to maximum service date", 5)]
    assert f"{P}.CasingService.applyDefaultDischarge" in ids


def test_semantic_filters(semantic):
    hits = semantic.search("claim", 10, entity_type="interface")
    assert hits and all(h.metadata["entity_type"] == "interface" for h in hits)
    hits = semantic.search("claim", 5, entity_type="method", package=P)
    assert all(h.metadata["entity_type"] == "method" for h in hits)


def test_ollama_embedding_unavailable():
    with pytest.raises(EmbeddingUnavailableError):
        OllamaEmbeddingProvider("http://127.0.0.1:9", "x", timeout=0.5).embed(["hi"])


# --- reranker / hybrid ------------------------------------------------------

def test_reranker_fusion():
    rr = Reranker()
    rr.add("a", 0.9, "symbol", "method_name")
    rr.add("b", 0.95, "semantic")
    rr.add("a", 0.5, "semantic")
    ranked = rr.ranked()
    assert ranked[0].entity_id == "a" and set(ranked[0].match_types) == {"symbol", "semantic"}


def test_hybrid_search(repo, symbols, semantic):
    graph = GraphBuilder(NetworkXGraphStore()).build(repo)
    hr = HybridRetriever(repo, symbols, semantic, graph, 10)
    res = hr.search(SearchRequest(query="ClaimService.processClaim"))
    assert res.hits[0].entity.id == f"{P}.ClaimService.processClaim"
    assert "symbol" in res.hits[0].match_types
    assert any("graph" in h.match_types for h in res.hits)  # expansion added neighbours
    assert "symbol_search" in res.timings_ms


def test_hybrid_filters(repo, symbols, semantic):
    hr = HybridRetriever(repo, symbols, semantic, None, 10)
    res = hr.search(SearchRequest(query="claim", entity_type="interface"))
    assert res.hits and all(h.entity.type.value == "interface" for h in res.hits)


def test_hybrid_degrades_without_vector_store(repo, symbols):
    class Broken:
        def search(self, *a, **k):
            from codeknowledge.retrieval.semantic import SemanticUnavailableError
            raise SemanticUnavailableError("down")

    hr = HybridRetriever(repo, symbols, Broken(), None, 5)
    res = hr.search(SearchRequest(query="CasingService"))
    assert res.hits[0].entity.id == f"{P}.CasingService"
    assert res.warnings and "unavailable" in res.warnings[0]
