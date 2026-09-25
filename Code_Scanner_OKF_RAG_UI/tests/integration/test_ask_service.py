"""question -> context -> prompt -> mock answer -> evidence (no live LLM)."""
import pytest

from codeknowledge.llm.provider import MockLLMProvider
from codeknowledge.models.answers import AskRequest
from codeknowledge.services.ask_service import AskService
from codeknowledge.services.cache_service import AnswerCache
from tests.conftest import ABC_OKF, make_kb

P = "com.example.claim"


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    return make_kb(tmp_path_factory.mktemp("kb"))


@pytest.fixture
def llm():
    return MockLLMProvider()


@pytest.fixture
def svc(kb, llm):
    return AskService(kb, llm, None)


def ev_ids(resp):
    return {e.entity_id for e in resp.evidence}


def test_callers_deterministic_no_llm(svc, llm):
    r = svc.ask(AskRequest(question="Who calls CasingService.processClaims?"))
    assert r.category == "CALLERS" and r.target == f"{P}.CasingService.processClaims"
    assert "ClaimService.processClaim" in r.answer
    assert not r.llm_used and llm.calls == []
    assert {f"{P}.CasingService.processClaims", f"{P}.ClaimService.processClaim"} <= ev_ids(r)
    assert r.facts and all(f.kind == "fact" for f in r.facts)
    assert r.plan[0] == "1. Exact symbol lookup"


def test_dependents(svc):
    r = svc.ask(AskRequest(question="What classes depend on ClaimValidator?"))
    assert r.category == "DEPENDENCIES"
    assert "ClaimService" in r.answer


def test_impact(svc):
    r = svc.ask(AskRequest(question="What is the impact of changing ClaimDataDTO?"))
    assert r.category == "IMPACT_ANALYSIS" and "CasingService.processClaims" in r.answer


def test_path(svc):
    r = svc.ask(AskRequest(question="What is the path from ClaimService.process to CasingService.getClaimData?"))
    assert r.paths == [[f"{P}.ClaimService.process", f"{P}.ClaimService.processClaim",
                        f"{P}.CasingService.processClaims", f"{P}.CasingService.getClaimData"]]
    assert "ClaimService.process → ClaimService.processClaim → CasingService.processClaims → CasingService.getClaimData" in r.answer


def test_semantic_question_uses_llm_with_evidence(svc, llm):
    r = svc.ask(AskRequest(question="How is discharge date calculated?"))
    assert r.category == "FUNCTIONAL_EXPLANATION"
    assert r.llm_used and r.interpretation.startswith("**Interpretation (mock)")
    prompt, system = llm.calls[0]
    assert "Use ONLY the supplied context" in system
    assert '"entities"' in prompt and "How is discharge date calculated?" in prompt
    assert r.evidence and all(e.document for e in r.evidence)
    assert any(e.cited for e in r.evidence)
    # the target was found via search and its flow was built
    assert r.target is not None


def test_flow_question(svc):
    r = svc.ask(AskRequest(question="Explain the flow of CasingService.processClaims"))
    assert r.category == "FLOW" and r.flow and r.flow.availability == "explicit"
    assert "checkConfiguration()" in r.answer


def test_business_rules(svc):
    r = svc.ask(AskRequest(question="What are the business rules in processClaims?", use_llm=False))
    assert r.category == "BUSINESS_RULE"
    assert any(f.claim.startswith("IF checkConfiguration()") for f in r.facts)
    assert not r.llm_used and r.warnings


def test_lookup(svc):
    r = svc.ask(AskRequest(question="ClaimService"))
    assert r.category == "CLASS_LOOKUP"
    assert "Source: src/main/java/com/example/claim/ClaimService.java:14" in r.answer
    assert "EXTENDS: BaseService" in r.answer


def test_architecture(svc):
    r = svc.ask(AskRequest(question="Describe the architecture of the system"))
    assert r.category == "ARCHITECTURE" and "com.example.claim" in r.answer and r.llm_used


def test_unknown_target(svc):
    r = svc.ask(AskRequest(question="Who calls the frobnicator?", use_llm=False))
    # Either nothing is found, or the guess is flagged explicitly.
    assert r.target is None or any("No exact symbol" in w for w in r.warnings)
    assert r.target is not None or "could not identify" in r.answer.lower()


def test_llm_unavailable_still_returns_facts(kb):
    svc = AskService(kb, MockLLMProvider(fail=True), None)
    r = svc.ask(AskRequest(question="Explain the flow of CasingService.processClaims"))
    assert not r.llm_used and r.llm_error and "unavailable" in r.llm_error
    assert r.flow is not None and r.facts is not None and r.evidence


def test_cache_hit_and_invalidation(kb, tmp_path):
    from tests.conftest import make_settings

    cache = AnswerCache(make_settings(tmp_path))
    llm = MockLLMProvider()
    svc = AskService(kb, llm, cache)
    q = AskRequest(question="How is discharge date calculated?")
    first = svc.ask(q)
    second = svc.ask(q)
    assert not first.cached and second.cached and len(llm.calls) == 1
    assert second.answer == first.answer
    third = svc.ask(AskRequest(question=q.question, use_cache=False))
    assert not third.cached and len(llm.calls) == 2


def test_request_id_propagates(svc):
    r = svc.ask(AskRequest(question="Who calls processClaim?"), request_id="abc123")
    assert r.request_id == "abc123"


def test_timings_recorded(svc):
    r = svc.ask(AskRequest(question="How is discharge date calculated?"))
    for k in ("classify", "symbol_search", "semantic_search", "graph_expansion", "context_build", "llm", "total"):
        assert k in r.timings_ms, k


# ---------------------------------------------------------------- A -> B -> C

@pytest.fixture(scope="module")
def abc(tmp_path_factory):
    return AskService(make_kb(tmp_path_factory.mktemp("abc"), ABC_OKF), MockLLMProvider(), None)


def test_abc_who_does_a_call(abc):
    r = abc.ask(AskRequest(question="Who does A call?"))
    assert r.category == "CALLEES" and "- B" in r.answer


def test_abc_what_calls_c(abc):
    r = abc.ask(AskRequest(question="What calls C?"))
    assert r.category == "CALLERS" and "- B" in r.answer


def test_abc_path(abc):
    r = abc.ask(AskRequest(question="What is the path from A to C?"))
    assert r.paths == [["demo.A", "demo.B", "demo.C"]] and "A → B → C" in r.answer


def test_abc_final_acceptance(abc):
    r = abc.ask(AskRequest(question="What does A eventually call?"))
    assert r.category == "CALLEES"
    assert "A → B → C" in r.answer
    assert r.paths == [["demo.A", "demo.B", "demo.C"]]
    evidence = {e.entity_id: e for e in r.evidence}
    assert {"demo.A", "demo.B", "demo.C"} <= set(evidence)
    assert all(evidence[i].document for i in ("demo.A", "demo.B", "demo.C"))  # clickable (document known)
    assert not r.llm_used


# ------------------------------------------------ real source (source.root_dir)

@pytest.fixture(scope="module")
def j2o_with_source(tmp_path_factory):
    from tests.conftest import FIXTURES, make_settings
    from codeknowledge.services.indexing_service import KnowledgeBase

    s = make_settings(tmp_path_factory.mktemp("src"), FIXTURES / "java2okf-sample")
    s.source.root_dir = str(FIXTURES / "java2okf-source")
    kb = KnowledgeBase(s)
    kb.load(rebuild=True, rebuild_vectors=True)
    return kb


def test_explain_method_uses_real_source(j2o_with_source):
    llm = MockLLMProvider()
    r = AskService(j2o_with_source, llm, None).ask(AskRequest(question="Explain OrderService.placeOrder"))
    assert r.category == "FUNCTIONAL_EXPLANATION"
    assert r.source and r.source.file == "src/main/java/com/example/OrderService.java"
    assert (r.source.decl_line, r.source.end_line) == (17, 24)
    assert "throw new IllegalArgumentException" in r.source.code
    assert r.source.conditions[0] == {"line": 18, "kind": "if", "expression": "amount <= 0"}
    assert "Source: src/main/java/com/example/OrderService.java lines 17-24" in r.answer
    assert "**L18** if: `amount <= 0`" in r.answer
    prompt, _ = llm.calls[0]
    assert "### Step-by-step" in prompt and "source_code" in prompt
    assert "18|         if (amount <= 0) {" in prompt


def test_business_rules_from_source(j2o_with_source):
    r = AskService(j2o_with_source, MockLLMProvider(), None).ask(
        AskRequest(question="What are the business rules in OrderService.placeOrder?", use_llm=False))
    assert r.category == "BUSINESS_RULE"
    assert any(f.claim == "L18 if: amount <= 0" for f in r.facts)
    assert "No explicit conditional logic" not in r.answer


def test_structural_questions_do_not_attach_source(j2o_with_source):
    r = AskService(j2o_with_source, MockLLMProvider(), None).ask(
        AskRequest(question="Who calls OrderRepository.save?"))
    assert r.source is None


def test_method_named_with_its_class_targets_the_method(j2o_with_source):
    r = AskService(j2o_with_source, MockLLMProvider(), None).ask(
        AskRequest(question="Explain the method placeOrder in OrderService", use_llm=False))
    assert r.target == "java-method:com.example.OrderService.placeOrder(com.example.Customer,double)"
    assert r.source is not None


def test_close_match_for_misspelled_method(j2o_with_source):
    r = AskService(j2o_with_source, MockLLMProvider(), None).ask(
        AskRequest(question="Explain placeOrdr", use_llm=False))
    assert r.target == "java-method:com.example.OrderService.placeOrder(com.example.Customer,double)"


def test_missing_source_root_is_explained(tmp_path):
    from tests.conftest import FIXTURES, make_kb

    kb = make_kb(tmp_path, FIXTURES / "java2okf-sample")
    r = AskService(kb, MockLLMProvider(), None).ask(AskRequest(question="Explain OrderService.placeOrder", use_llm=False))
    assert r.source is None and "Set `source.root_dir`" in r.answer


def test_stale_vector_entries_are_ignored_and_reported(tmp_path):
    from codeknowledge.models.query import SearchRequest
    from codeknowledge.retrieval.semantic import SemanticHit
    from tests.conftest import make_kb

    kb = make_kb(tmp_path)

    class StaleSemantic:
        def search(self, *a, **k):
            return [SemanticHit("java-method:old.Id.gone", 0.99, {}),
                    SemanticHit("com.example.claim.ClaimService", 0.5, {})]

    kb.retriever.semantic = StaleSemantic()
    res = kb.retriever.search(SearchRequest(query="something vague", expand_graph=False))
    assert [h.entity.id for h in res.hits] == ["com.example.claim.ClaimService"]
    assert any("not in the current OKF bundle" in w for w in res.warnings)
