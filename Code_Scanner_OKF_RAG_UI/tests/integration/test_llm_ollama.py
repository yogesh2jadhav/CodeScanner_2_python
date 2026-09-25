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


def test_ollama_method_explanation_quality_gates(cfg, tmp_path):
    """Release gates from the plan (section 13) on the synthetic fixture, with the configured local model."""
    import yaml

    from codeknowledge.explain.models import ExplainOptions
    from codeknowledge.explain.service import MethodExplanationService
    from scripts.eval_explanation import score
    from tests.conftest import BUILD_VISITS, FIXTURES, make_explain_kb

    kb = make_explain_kb(tmp_path)
    llm = OllamaProvider(cfg.llm.base_url, cfg.llm.model, cfg.llm.temperature, cfg.llm.timeout_seconds, cfg.llm.num_ctx)
    r = MethodExplanationService(kb, llm, None).explain(BUILD_VISITS, ExplainOptions())
    assert r.explanation is not None and r.validation.valid
    result = score(r, yaml.safe_load((FIXTURES / "explain-checklist.yaml").read_text()))
    assert result["citation_precision"] == 1.0  # no fabricated line references survive
    assert result["traps_failed"] == []  # misleading comment / prompt injection not repeated as fact
    assert result["coverage"] >= 0.75
    save_all = [c for c in r.explanation.calls if "saveAll" in c.callee]
    assert all(c.evidence_status == "signature_only" for c in save_all)  # no body claims without source
