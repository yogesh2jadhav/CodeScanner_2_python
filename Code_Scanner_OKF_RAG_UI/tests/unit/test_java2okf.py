"""Java2OKF bundle format (see java2okf docs/okf-output.md)."""
import pytest

from codeknowledge.flow.builder import FlowBuilder
from codeknowledge.graph.builder import GraphBuilder
from codeknowledge.graph.networkx_store import NetworkXGraphStore
from codeknowledge.graph.traversal import GraphTraversal
from codeknowledge.models.entities import EntityType
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.okf.validator import OKFValidator
from codeknowledge.retrieval.symbol import SymbolIndex
from tests.conftest import FIXTURES

J2O = FIXTURES / "java2okf-sample"
PLACE = "java-method:com.example.OrderService.placeOrder(com.example.Customer,double)"
SAVE = "java-method:com.example.OrderRepository.save(com.example.Order)"


@pytest.fixture(scope="module")
def repo():
    return OKFRepository.from_directory(J2O)


@pytest.fixture(scope="module")
def graph(repo):
    return GraphBuilder(NetworkXGraphStore()).build(repo)


def test_bundle_validates_without_errors_or_warnings():
    r = OKFValidator(J2O).validate()
    assert r.passed and not r.warnings, r.render(verbose=True)
    assert r.documents == 31 and r.duplicate_ids == 0 and r.unresolved_relationships == 0
    assert r.external_references > 40


def test_method_document_fields(repo):
    d = repo.get(PLACE)
    assert d.type == EntityType.METHOD
    assert d.display_name() == "OrderService.placeOrder(Customer, double)"
    assert (d.package, d.class_name, d.method_name) == ("com.example", "OrderService", "placeOrder")
    assert d.source_file == "src/main/java/com/example/OrderService.java"
    assert (d.source_line, d.end_line) == (17, 24)
    assert d.signature == "public Order placeOrder(Customer customer, double amount)"
    assert "returns Order" in d.summary


def test_types_and_nested_enum(repo):
    assert repo.get("java-class:com.example.OrderService").type == EntityType.CLASS
    enum = repo.get("java-enum:com.example.Order.Status")
    assert enum.type == EntityType.ENUM and enum.class_name == "Order.Status"
    ctor = repo.get("java-constructor:com.example.Order(java.lang.String,com.example.Customer,double)")
    assert ctor.type == EntityType.METHOD and ctor.display_name() == "Order(String, Customer, double)"


def test_navigation_documents_have_no_relationships(repo):
    nav = [d for d in repo.documents if d.navigation]
    assert {d.path for d in nav} >= {"index.md", "log.md", "classes/index.md"}
    ids = {d.id for d in nav}
    assert not [r for r in repo.relationships() if r.source in ids or r.target in ids]
    assert all(not d.navigation for d in repo.content_documents)


def test_calls_with_lines_and_external_markers(repo):
    calls = {(r.target, r.status, r.line) for r in repo.relationships() if r.source == PLACE and r.type.value == "CALLS"}
    assert (SAVE, "resolved", 22) in calls
    assert ("java.lang.IllegalArgumentException(java.lang.String)", "external", 19) in calls
    # class-level "Called By" aggregates are not turned into vague class CALLS edges
    assert not any(t.startswith("java-class:") for t, _, _ in calls)


def test_sections_map_to_relationships(repo):
    rels = {(r.source, r.target, r.type.value) for r in repo.relationships()}
    assert ("java-class:com.example.OrderService", PLACE, "CONTAINS") in rels  # Declared By / Methods
    assert ("java-package:com.example", "java-class:com.example.OrderService", "CONTAINS") in rels  # Package
    assert (PLACE, "java-class:com.example.Customer", "USES") in rels  # Parameters / Uses
    assert ("java-class:com.example.OrderService", "java-class:com.example.OrderRepository", "DEPENDS_ON") in rels


def test_primitive_field_types_are_not_relationships(repo):
    targets = {r.target for r in repo.relationships() if r.source == "java-class:com.example.OrderService"}
    assert "sequence" not in targets and "int" not in targets


def test_overloads_are_distinct(tmp_path):
    for sig, h in (("run(int)", "a1"), ("run(java.lang.String)", "b2")):
        (tmp_path / f"m-{h}.md").write_text(
            f'---\ntype: JavaMethod\nid: "java-method:p.A.{sig}"\ntitle: run\n'
            f"generated:\n  by: java2okf/1.0.0\njava:\n  declaringClass: p.A\n  signature: \"{sig}\"\n---\n# run\n")
    repo = OKFRepository.from_directory(tmp_path)
    assert not repo.duplicates
    assert set(repo.lookup("A.run")) == {"java-method:p.A.run(int)", "java-method:p.A.run(java.lang.String)"}
    assert OKFValidator(tmp_path).validate().duplicate_ids == 0


def test_symbol_search_on_java2okf_ids(repo):
    s = SymbolIndex(repo)
    assert s.search("OrderService.placeOrder")[0].entity_id == PLACE
    assert s.search("com.example.OrderService.placeOrder(com.example.Customer,double)")[0].entity_id == PLACE
    assert s.search("OrderService")[0].entity_id == "java-class:com.example.OrderService"
    assert s.search("OrderService.java")[0].entity_id == "java-class:com.example.OrderService"


def test_external_nodes_are_leaves(graph):
    node = graph.get_node("java.lang.String")
    assert node["type"] == "external" and node["status"] == "external"
    # Walking dependents of Customer must not hop through java.lang.String to unrelated classes.
    t = GraphTraversal(graph)
    deps = t.dependents("java-class:com.example.Customer", depth=3).ids()
    assert "java.lang.String" not in deps
    # Subgraph expansion stops at external nodes: every node must be reachable from a
    # non-external node one level closer to the root.
    sg = graph.subgraph("java-class:com.example.Customer", depth=3)
    depth = {n["id"]: n["depth"] for n in sg.nodes}
    status = {n["id"]: n.get("status") for n in sg.nodes}
    for nid, d in depth.items():
        if d == 0:
            continue
        parents = {e.source if e.target == nid else e.target for e in sg.edges if nid in (e.source, e.target)}
        assert any(depth.get(p) == d - 1 and status.get(p) != "external" for p in parents), nid
    # no path may pass through an external node
    for e in graph.edges("java.lang.String", "in"):
        for f in graph.edges("java.lang.String", "in"):
            if e.source != f.source:
                path = graph.shortest_path(e.source, f.source, {"DEPENDS_ON", "USES"}, directed=False)
                assert path is None or "java.lang.String" not in path


def test_call_chains_skip_externals_by_default(graph):
    chains = GraphTraversal(graph).reachable_call_chains(PLACE, 5)
    assert all(not c[-1].startswith("java.") for c in chains)
    assert [PLACE, SAVE] in [c[:2] for c in chains]


def test_call_sequence_flow_is_ordered_by_line(repo, graph):
    flow = FlowBuilder(repo, graph).build(PLACE)
    assert flow.availability == "call_sequence" and "source-line order" in flow.notes[0]
    calls = [n.label for n in flow.nodes if n.kind == "call"]
    assert calls == ["IllegalArgumentException()", "Order(String, Customer, double)", "OrderService.nextId()",
                     "OrderRepository.save(Order)"]
    ext = next(n for n in flow.nodes if n.label == "IllegalArgumentException()")
    assert ext.status == "external" and ext.entity_id is None
