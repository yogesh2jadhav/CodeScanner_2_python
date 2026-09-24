import pytest

from codeknowledge.graph.builder import GraphBuilder
from codeknowledge.graph.networkx_store import NetworkXGraphStore
from codeknowledge.llm.provider import MockLLMProvider
from codeknowledge.models.query import QueryCategory as C
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.query.classifier import QueryClassifier
from codeknowledge.query.context_builder import ContextBuilder
from codeknowledge.query.planner import QueryPlanner, StepType
from codeknowledge.retrieval.symbol import SymbolIndex
from tests.conftest import SAMPLE_OKF

P = "com.example.claim"


@pytest.fixture(scope="module")
def repo():
    return OKFRepository.from_directory(SAMPLE_OKF)


@pytest.fixture(scope="module")
def clf(repo):
    return QueryClassifier(SymbolIndex(repo))


@pytest.mark.parametrize("q,cat", [
    ("Who calls processClaim?", C.CALLERS),
    ("What calls CasingService.processClaims?", C.CALLERS),
    ("Where is validate called?", C.CALLERS),
    ("What does ClaimService do?", C.FUNCTIONAL_EXPLANATION),
    ("Explain CasingService.processClaims", C.FUNCTIONAL_EXPLANATION),
    ("How does claim processing flow?", C.FLOW),
    ("What happens when processClaims runs?", C.FLOW),
    ("What classes depend on ClaimService?", C.DEPENDENCIES),
    ("What are the dependencies of CasingService?", C.DEPENDENCIES),
    ("What does processClaim call?", C.CALLEES),
    ("What does ClaimService.processClaim eventually call?", C.CALLEES),
    ("What is the impact of changing ClaimDataDTO?", C.IMPACT_ANALYSIS),
    ("What is the path from ClaimService.process to getClaimData?", C.PATH),
    ("What are the business rules in processClaims?", C.BUSINESS_RULE),
    ("Under what conditions is a claim eligible?", C.BUSINESS_RULE),
    ("Describe the architecture of the system", C.ARCHITECTURE),
    ("Where is discharge date calculated?", C.SEMANTIC_SEARCH),
    ("How is discharge date calculated?", C.FUNCTIONAL_EXPLANATION),
    ("ClaimService", C.CLASS_LOOKUP),
    ("CasingService.processClaims()", C.METHOD_LOOKUP),
    ("hello there", C.GENERAL),
])
def test_classification(clf, q, cat):
    assert clf.classify(q).category == cat


def test_classification_symbols_and_direction(clf):
    r = clf.classify("What classes depend on ClaimService?")
    assert r.symbols == [f"{P}.ClaimService"] and r.direction == "in" and r.method == "rules"
    r = clf.classify("What does CasingService depend on?")
    assert r.direction == "out"
    assert clf.classify("What does A eventually call?").transitive


def test_low_confidence_uses_llm(repo):
    llm = MockLLMProvider(response="ARCHITECTURE")
    r = QueryClassifier(SymbolIndex(repo), llm, threshold=0.6).classify("hello there")
    assert r.category == C.ARCHITECTURE and r.method == "llm" and len(llm.calls) == 1


def test_high_confidence_skips_llm(repo):
    llm = MockLLMProvider(response="GENERAL")
    QueryClassifier(SymbolIndex(repo), llm).classify("Who calls processClaim?")
    assert llm.calls == []


def test_llm_classification_failure_is_tolerated(repo):
    r = QueryClassifier(SymbolIndex(repo), MockLLMProvider(fail=True)).classify("hello there")
    assert r.category == C.GENERAL and r.method == "rules"


def test_structural_question_without_symbol_is_low_confidence(clf):
    assert clf.classify("who calls the frobnicator?").confidence < 0.6


# --- planner ---

def test_plan_callers_no_llm(clf):
    q = "Who calls CasingService.processClaims?"
    plan = QueryPlanner(3).plan(clf.classify(q), q)
    types = [s.type for s in plan.steps]
    assert types[:2] == [StepType.SYMBOL_LOOKUP, StepType.GRAPH_REVERSE]
    assert not plan.requires_llm and plan.graph_depth == 1
    assert plan.describe()[0] == "1. Exact symbol lookup"


def test_plan_semantic_explanation(clf):
    q = "How is discharge date calculated?"
    plan = QueryPlanner(3).plan(clf.classify(q), q)
    types = [s.type for s in plan.steps]
    assert types == [StepType.SEMANTIC_SEARCH, StepType.IDENTIFY_TARGET, StepType.GRAPH_EXPAND, StepType.FLOW,
                     StepType.BUILD_CONTEXT, StepType.LLM]
    assert plan.requires_llm and plan.prompt_kind == "functional"


def test_plan_transitive_depth_and_explanation(clf):
    q = "Explain who calls processClaims"
    plan = QueryPlanner(4).plan(clf.classify(q), q)
    assert plan.requires_llm  # explanation explicitly requested
    q = "What does processClaim eventually call?"
    assert QueryPlanner(4).plan(clf.classify(q), q).graph_depth == 4


def test_plan_business_rule_has_rules_step(clf):
    q = "What are the business rules in processClaims?"
    plan = QueryPlanner(3).plan(clf.classify(q), q)
    assert plan.has(StepType.FLOW) and plan.has(StepType.RULES) and plan.prompt_kind == "business_rule"


# --- context builder ---

def test_context_builder_bounds_and_dedupe(repo):
    cb = ContextBuilder(repo, max_documents=3, max_tokens=100000)
    cb.add_entity(f"{P}.ClaimService", 0.4, "semantic", "semantic")
    cb.add_entity(f"{P}.ClaimService", 1.0, "target", "target")  # duplicate, higher priority wins
    cb.add_entity(f"{P}.CasingService", 0.9, "semantic", "semantic")
    cb.add_entity(f"{P}.ClaimValidator", 0.5, "graph", "graph")
    cb.add_entity(f"{P}.ClaimDataDTO", 0.1, "semantic", "semantic")
    cb.add_relationship(f"{P}.ClaimService", f"{P}.CasingService", "DEPENDS_ON")
    cb.add_relationship(f"{P}.ClaimService", f"{P}.CasingService", "DEPENDS_ON")
    ctx = cb.build("q", "GENERAL", f"{P}.ClaimService")
    ids = [e.id for e in ctx.entities]
    assert ids == [f"{P}.ClaimService", f"{P}.ClaimValidator", f"{P}.CasingService"]  # priority then score
    assert ctx.truncated and len(ctx.relationships) == 1
    assert ctx.evidence[0].reason == "target" and ctx.evidence[0].document == "classes/ClaimService.md"


def test_context_builder_token_budget(repo):
    cb = ContextBuilder(repo, max_documents=50, max_tokens=400)
    for d in repo.documents:
        cb.add_entity(d.id, 0.5, "semantic", "s")
    ctx = cb.build("q", "GENERAL", None)
    assert ctx.estimated_tokens() <= 400 or not ctx.source_documents
    assert ctx.truncated


def test_context_includes_flow(repo):
    from codeknowledge.flow.builder import FlowBuilder

    graph = GraphBuilder(NetworkXGraphStore()).build(repo)
    cb = ContextBuilder(repo, 20, 6000)
    cb.add_flow(FlowBuilder(repo, graph).build(f"{P}.CasingService.processClaims"))
    ctx = cb.build("q", "FLOW", f"{P}.CasingService.processClaims")
    assert "availability: explicit" in ctx.flow[0]
    assert f"{P}.CasingService.applyDefaultDischarge" in {e.id for e in ctx.entities}
    assert '"entities"' in ctx.to_prompt_json()
