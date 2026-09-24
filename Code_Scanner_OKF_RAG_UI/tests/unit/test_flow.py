import pytest

from codeknowledge.flow.analyzer import extract_rules
from codeknowledge.flow.builder import FlowBuilder
from codeknowledge.graph.builder import GraphBuilder
from codeknowledge.graph.networkx_store import NetworkXGraphStore
from codeknowledge.okf.repository import OKFRepository
from tests.conftest import ABC_OKF, SAMPLE_OKF

P = "com.example.claim"


@pytest.fixture(scope="module")
def fb():
    repo = OKFRepository.from_directory(SAMPLE_OKF)
    return FlowBuilder(repo, GraphBuilder(NetworkXGraphStore()).build(repo))


def edges(flow):
    by = {n.id: n for n in flow.nodes}
    return {(by[e.source].label, by[e.target].label, e.label) for e in flow.edges}


def test_explicit_flow_with_loop_and_branch(fb):
    flow = fb.build(f"{P}.CasingService.processClaims")
    assert flow.availability == "explicit"
    kinds = [n.kind for n in flow.nodes]
    assert kinds.count("condition") == 1 and kinds.count("loop") == 1 and "return" in kinds
    e = edges(flow)
    assert ("checkConfiguration()", "CasingService.applyConfiguredDischarge()", "yes") in e
    assert ("checkConfiguration()", "CasingService.applyDefaultDischarge()", "no") in e
    assert ("CasingService.getClaimData()", "CasingService.calculateServiceDate()", "next") in e
    calls = {n.entity_id for n in flow.nodes if n.kind == "call"}
    assert f"{P}.ClaimRepository.save" in calls and None not in calls
    text = flow.render_text()
    assert text.splitlines() == [
        "CasingService.processClaims()",
        "  LOOP for (ClaimDataDTO claim : claims)",
        "    CALL CasingService.getClaimData()",
        "    CALL CasingService.calculateServiceDate()",
        "    IF checkConfiguration()",
        "      CALL CasingService.applyConfiguredDischarge()",
        "    ELSE",
        "      CALL CasingService.applyDefaultDischarge()",
        "    END IF",
        "    CALL ClaimRepository.save()",
        "  END LOOP",
        "  RETURN void",
    ]


def test_explicit_flow_throw_is_terminal(fb):
    flow = fb.build(f"{P}.ClaimValidator.validate")
    throw = next(n for n in flow.nodes if n.kind == "throw")
    assert not [e for e in flow.edges if e.source == throw.id]


def test_sequential_flow(fb):
    flow = fb.build(f"{P}.ClaimService.processClaim")
    labels = [n.label for n in flow.nodes if n.kind == "call"]
    assert labels == ["JdbcClaimRepository.findById()", "ClaimValidator.validate()",
                      "CasingService.processClaims()", "BaseService.log()"]


def test_call_sequence_fallback_is_labelled(tmp_path):
    (tmp_path / "A.md").write_text("---\nid: A\ntype: method\ncalls: [B, C]\n---\n")
    (tmp_path / "B.md").write_text("---\nid: B\ntype: method\n---\n")
    (tmp_path / "C.md").write_text("---\nid: C\ntype: method\n---\n")
    repo = OKFRepository.from_directory(tmp_path)
    flow = FlowBuilder(repo, GraphBuilder(NetworkXGraphStore()).build(repo)).build("A")
    assert flow.availability == "call_sequence"
    assert "not available" in flow.notes[0]
    assert not any(n.kind == "condition" for n in flow.nodes)  # never invented


def test_unavailable_flow(fb):
    flow = fb.build(f"{P}.CasingService.checkConfiguration")
    assert flow.availability == "unavailable" and flow.nodes == []


def test_unknown_entity(fb):
    assert fb.build("does.not.Exist") is None


def test_abc_call_chains():
    repo = OKFRepository.from_directory(ABC_OKF)
    flow = FlowBuilder(repo, GraphBuilder(NetworkXGraphStore()).build(repo)).build("demo.A")
    assert flow.call_chains == [["demo.A", "demo.B", "demo.C"]]
    assert flow.availability == "call_sequence"


def test_unresolved_call_in_flow(tmp_path):
    (tmp_path / "A.md").write_text("---\nid: A\ntype: method\nflow:\n  - call: Ghost.run\n  - weird: 1\n  - plain text step\n---\n")
    repo = OKFRepository.from_directory(tmp_path)
    flow = FlowBuilder(repo).build("A")
    call = next(n for n in flow.nodes if n.kind == "call")
    assert call.status == "unresolved" and call.entity_id is None
    assert any("unrecognised" in n for n in flow.notes)
    assert any(n.kind == "statement" and n.label == "plain text step" for n in flow.nodes)


def test_business_rule_extraction(fb):
    [rule] = extract_rules(fb.build(f"{P}.CasingService.processClaims"))
    assert rule.condition == "checkConfiguration()"
    assert rule.then == ["CasingService.applyConfiguredDischarge()"]
    assert rule.otherwise == ["CasingService.applyDefaultDischarge()"]
    [rule] = extract_rules(fb.build(f"{P}.ClaimValidator.validate"))
    assert rule.then == ["return true"] and rule.otherwise == ["throw InvalidClaimException"]
