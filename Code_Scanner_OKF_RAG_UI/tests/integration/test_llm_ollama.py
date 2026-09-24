"""Optional live-LLM suite: pytest -m llm (requires Ollama with the configured models)."""
import pytest

from codeknowledge.config.settings import load_settings
from codeknowledge.llm.ollama import OllamaProvider
from codeknowledge.models.answers import AskRequest
from codeknowledge.retrieval.embeddings import OllamaEmbeddingProvider
from codeknowledge.services.ask_service import AskService
from codeknowledge.services.indexing_service import KnowledgeBase
from tests.conftest import make_settings

pytestmark = pytest.mark.llm


@pytest.fixture(scope="module")
def cfg():
    return load_settings("config/config.yaml")


def test_ollama_embeddings(cfg):
    vecs = OllamaEmbeddingProvider(cfg.embedding.base_url, cfg.embedding.model, 60).embed(["hello", "world"])
    assert len(vecs) == 2 and len(vecs[0]) > 100


def test_ollama_answer_is_evidence_based(cfg, tmp_path):
    s = make_settings(tmp_path)
    s.embedding = cfg.embedding
    kb = KnowledgeBase(s)
    kb.load(rebuild=True, rebuild_vectors=True)
    llm = OllamaProvider(cfg.llm.base_url, cfg.llm.model, cfg.llm.temperature, cfg.llm.timeout_seconds)
    r = AskService(kb, llm, None).ask(AskRequest(question="How is discharge date calculated?"))
    assert r.llm_used, r.llm_error
    assert r.interpretation and len(r.interpretation) > 50
    assert any(e.cited for e in r.evidence)
    # Facts are the analyzer's, not the LLM's
    assert r.flow is not None
