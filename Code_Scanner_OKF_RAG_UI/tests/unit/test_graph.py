import pytest

from codeknowledge.graph.builder import GraphBuilder
from codeknowledge.graph.networkx_store import NetworkXGraphStore
from codeknowledge.graph.traversal import GraphTraversal
from codeknowledge.okf.repository import OKFRepository
from tests.conftest import ABC_OKF, SAMPLE_OKF

P = "com.example.claim"


@pytest.fixture(scope="module")
def store():
    return GraphBuilder(NetworkXGraphStore()).build(OKFRepository.from_directory(SAMPLE_OKF))


@pytest.fixture(scope="module")
def trav(store):
    return GraphTraversal(store)


def test_graph_creation_nodes_and_types(store):
    assert store.get_node(f"{P}.ClaimService")["type"] == "class"
    assert store.get_node(f"{P}.ClaimProcessor")["type"] == "interface"
    assert store.get_node(f"{P}.CasingService.processClaims")["type"] == "method"
    assert store.get_node(P)["type"] == "package"
    assert store.get_node(f"{P}.ClaimService")["document"] == "classes/ClaimService.md"
    s = store.stats()
    assert s["nodes"] == 24 and s["edges"] > 40


def test_graph_edges_by_type(store):
    out = {(e.target, e.type) for e in store.edges(f"{P}.ClaimService", "out")}
    assert (f"{P}.BaseService", "EXTENDS") in out
    assert (f"{P}.ClaimProcessor", "IMPLEMENTS") in out
    assert (f"{P}.CasingService", "DEPENDS_ON") in out
    assert (f"{P}.ClaimService.processClaim", "CONTAINS") in out


def test_callers_and_callees(trav):
    callees = trav.callees(f"{P}.ClaimService.processClaim").ids()
    assert f"{P}.CasingService.processClaims" in callees and f"{P}.ClaimValidator.validate" in callees
    callers = trav.callers(f"{P}.CasingService.processClaims").ids()
    assert callers == [f"{P}.ClaimService.processClaim"]


def test_transitive_callers_with_depth(trav):
    deep = trav.callers(f"{P}.CasingService.processClaims", depth=2).ids()
    assert f"{P}.ClaimService.process" in deep


def test_class_level_callers_include_method_callers(trav):
    callers = trav.callers(f"{P}.CasingService").ids()
    assert f"{P}.ClaimService.processClaim" in callers


def test_impact_analysis(trav):
    impacted = trav.impact(f"{P}.ClaimDataDTO", depth=2).ids()
    assert f"{P}.CasingService.processClaims" in impacted
    assert f"{P}.ClaimService.processClaim" in impacted


def test_inheritance(trav):
    assert trav.supertypes(f"{P}.ClaimService").ids() == [f"{P}.BaseService", f"{P}.ClaimProcessor"]
    assert trav.subtypes(f"{P}.ClaimRepository").ids() == [f"{P}.JdbcClaimRepository"]


def test_path(store):
    path = store.shortest_path(f"{P}.ClaimService.process", f"{P}.CasingService.getClaimData", {"CALLS"})
    assert path == [f"{P}.ClaimService.process", f"{P}.ClaimService.processClaim",
                    f"{P}.CasingService.processClaims", f"{P}.CasingService.getClaimData"]
    assert store.shortest_path(f"{P}.CasingService.getClaimData", f"{P}.ClaimService.process", {"CALLS"}) is None
    assert store.shortest_path("nope", P) is None


def test_subgraph_depth_and_filters(store):
    sg = store.subgraph(f"{P}.CasingService.processClaims", depth=1, rel_types={"CALLS"})
    ids = {n["id"] for n in sg.nodes}
    assert f"{P}.CasingService.getClaimData" in ids and f"{P}.ClaimService.processClaim" in ids
    assert all(e.type == "CALLS" for e in sg.edges)
    assert f"{P}.ClaimService.process" not in ids  # depth 2
    assert store.subgraph("missing", 2).nodes == []


def test_abc_chain():
    store = GraphBuilder(NetworkXGraphStore()).build(OKFRepository.from_directory(ABC_OKF))
    t = GraphTraversal(store)
    assert t.callees("demo.A").ids() == ["demo.B"]
    assert t.callers("demo.C").ids() == ["demo.B"]
    assert t.call_paths("demo.A", "demo.C") == ["demo.A", "demo.B", "demo.C"]
    assert t.reachable_call_chains("demo.A", 5) == [["demo.A", "demo.B", "demo.C"]]


def test_unresolved_nodes(tmp_path):
    (tmp_path / "A.md").write_text("---\nid: p.A\ntype: class\ncalls: [p.Ghost]\n---\n")
    store = GraphBuilder(NetworkXGraphStore()).build(OKFRepository.from_directory(tmp_path))
    ghost = store.get_node("p.Ghost")
    assert ghost["status"] == "unresolved" and ghost["type"] == "unresolved"
    [edge] = store.edges("p.A", "out")
    assert edge.attrs["status"] == "unresolved"


def test_cycle_safe_chains(tmp_path):
    (tmp_path / "A.md").write_text("---\nid: A\ntype: class\ncalls: [B]\n---\n")
    (tmp_path / "B.md").write_text("---\nid: B\ntype: class\ncalls: [A]\n---\n")
    store = GraphBuilder(NetworkXGraphStore()).build(OKFRepository.from_directory(tmp_path))
    assert GraphTraversal(store).reachable_call_chains("A", 10) == [["A", "B"]]


def test_persistence_roundtrip(store, tmp_path):
    store.save(str(tmp_path), {"bundle_hash": "h1"})
    loaded = NetworkXGraphStore()
    assert loaded.load(str(tmp_path)) == {"bundle_hash": "h1"}
    assert loaded.stats() == store.stats()
    assert {e.type for e in loaded.edges(f"{P}.ClaimService", "out")} == {e.type for e in store.edges(f"{P}.ClaimService", "out")}
    assert NetworkXGraphStore().load(str(tmp_path / "none")) is None
