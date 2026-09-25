import pytest
from fastapi.testclient import TestClient

from codeknowledge.api.app import create_app
from codeknowledge.llm.provider import MockLLMProvider
from tests.conftest import make_settings

P = "com.example.claim"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("api")
    app = create_app(make_settings(tmp), llm=MockLLMProvider())
    with TestClient(app) as c:
        c.post("/api/index/rebuild")  # builds the vector index with hash embeddings
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.json() == {"status": "ok", "version": "0.1.0"}
    assert r.headers["X-Request-ID"]


def test_status(client):
    s = client.get("/api/status").json()
    assert s["knowledge_base"]["ready"] and s["knowledge_base"]["documents"] == 24
    assert s["knowledge_base"]["vector_status"] == "ok"
    assert s["llm"]["provider"] == "mock"


def test_rebuild(client):
    r = client.post("/api/index/rebuild", json={"vectors": False}).json()
    assert r["status"] == "ok" and r["index"]["graph_nodes"] == 24


def test_search(client):
    r = client.post("/api/search", json={"query": "CasingService.processClaims", "top_k": 5}).json()
    assert r["hits"][0]["entity"]["id"] == f"{P}.CasingService.processClaims"
    assert r["hits"][0]["entity"]["document"] == "methods/CasingService.processClaims.md"
    r = client.post("/api/search", json={"query": "claim", "mode": "semantic", "entity_type": "interface"}).json()
    assert r["hits"] and {h["entity"]["type"] for h in r["hits"]} == {"interface"}
    r = client.post("/api/search", json={"query": "claim", "mode": "symbol", "package": P}).json()
    assert all(h["entity"]["package"] == P for h in r["hits"])


def test_search_validation(client):
    assert client.post("/api/search", json={"query": ""}).status_code == 422
    assert client.post("/api/search", json={"query": "x", "top_k": 0}).status_code == 422


def test_ask(client):
    r = client.post("/api/ask", json={"question": "Who calls CasingService.processClaims?"}, headers={"X-Request-ID": "req-1"})
    body = r.json()
    assert r.headers["X-Request-ID"] == "req-1" and body["request_id"] == "req-1"
    assert body["category"] == "CALLERS" and body["evidence"]


def test_ask_with_llm(client):
    body = client.post("/api/ask", json={"question": "What does ClaimService do?", "use_cache": False}).json()
    assert body["llm_used"] and body["interpretation"]


def test_entity(client):
    body = client.get(f"/api/entities/{P}.CasingService").json()
    assert body["entity"]["title"] == "CasingService" and "discharge date" in body["content"]
    assert body["owner"]["id"] == P
    assert body["link_targets"]["../methods/CasingService.processClaims.md"] == f"{P}.CasingService.processClaims"
    assert {m["id"] for m in body["members"]} >= {f"{P}.CasingService.processClaims"}
    m = client.get(f"/api/entities/{P}.CasingService.processClaims").json()
    assert m["flow_available"] and m["signature"].startswith("public void processClaims")
    assert "flow" not in m["metadata"]


def test_entity_relationships(client):
    body = client.get(f"/api/entities/{P}.ClaimService/relationships").json()
    out = {(e["type"], e["target"]) for e in body["outgoing"]}
    assert ("EXTENDS", f"{P}.BaseService") in out
    assert body["incoming"][0]["other"]["id"] == P  # contained by package


def test_entity_not_found(client):
    r = client.get("/api/entities/no.such.Thing")
    assert r.status_code == 404 and "no.such.Thing" in r.json()["detail"]


def test_explorer_tree(client):
    tree = client.get("/api/explorer/tree").json()
    assert tree[0]["id"] == P
    titles = [c["title"] for c in tree[0]["children"]]
    assert titles[:2] == ["ClaimProcessor", "ClaimRepository"]  # interfaces first
    casing = next(c for c in tree[0]["children"] if c["title"] == "CasingService")
    assert "processClaims" in [m["title"] for m in casing["children"]]


def test_graph_node(client):
    body = client.get(f"/api/graph/node/{P}.ClaimService").json()
    assert body["node"]["type"] == "class" and body["degree"]["out"] > 3
    assert client.get("/api/graph/node/nope").status_code == 404


def test_graph_neighbors(client):
    body = client.get(f"/api/graph/neighbors/{P}.ClaimService", params={"types": "inheritance,implements"}).json()
    assert {e["type"] for e in body["edges"]} == {"EXTENDS", "IMPLEMENTS"}
    body = client.get(f"/api/graph/neighbors/{P}.CasingService.processClaims", params={"direction": "in", "types": "calls"}).json()
    assert [e["source"] for e in body["edges"]] == [f"{P}.ClaimService.processClaim"]


def test_graph_path(client):
    body = client.get("/api/graph/path", params={"from": f"{P}.ClaimService.process", "to": f"{P}.CasingService.getClaimData",
                                                 "types": "calls"}).json()
    assert body["found"] and len(body["path"]) == 4 and len(body["edges"]) == 3
    body = client.get("/api/graph/path", params={"from": f"{P}.CasingService.getClaimData", "to": f"{P}.ClaimService.process",
                                                 "types": "calls"}).json()
    assert not body["found"]


def test_graph_subgraph(client):
    body = client.get(f"/api/graph/subgraph/{P}.CasingService", params={"depth": 1}).json()
    assert body["root"] == f"{P}.CasingService" and len(body["nodes"]) > 5
    assert client.get(f"/api/graph/subgraph/{P}.CasingService", params={"depth": 99}).status_code == 422


def test_flow(client):
    body = client.get(f"/api/flow/{P}.CasingService.processClaims").json()
    assert body["availability"] == "explicit" and body["rules"][0]["condition"] == "checkConfiguration()"
    assert "LOOP" in body["text"]
    assert client.get("/api/flow/nope").status_code == 404


def test_openapi_lists_all_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/api/health", "/api/index/rebuild", "/api/search", "/api/ask", "/api/entities/{entity_id}",
              "/api/entities/{entity_id}/relationships", "/api/graph/node/{node_id}", "/api/graph/neighbors/{node_id}",
              "/api/graph/path", "/api/graph/subgraph/{node_id}", "/api/flow/{entity_id}"]:
        assert p in paths, p


# ------------------------------------------------------------- degradation

def test_missing_okf_dir_returns_503(tmp_path):
    app = create_app(make_settings(tmp_path, tmp_path / "missing"), llm=MockLLMProvider())
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200
        r = c.post("/api/search", json={"query": "x"})
        assert r.status_code == 503
        assert "OKF source directory does not exist." in r.json()["detail"]
        assert "Configure okf.source_dir." in r.json()["detail"]


def test_vector_store_unavailable_graph_still_works(tmp_path):
    settings = make_settings(tmp_path)
    settings.embedding.provider = "does-not-exist"
    app = create_app(settings, llm=MockLLMProvider())
    with TestClient(app) as c:
        s = c.get("/api/status").json()["knowledge_base"]
        assert s["ready"] and s["vector_status"] == "unavailable"
        assert c.get(f"/api/graph/node/{P}.ClaimService").status_code == 200
        assert c.get(f"/api/entities/{P}.ClaimService").status_code == 200
        r = c.post("/api/search", json={"query": "ClaimService"}).json()
        assert r["hits"][0]["entity"]["id"] == f"{P}.ClaimService"
        assert r["warnings"]


def test_llm_unavailable_other_features_work(tmp_path):
    app = create_app(make_settings(tmp_path), llm=MockLLMProvider(fail=True))
    with TestClient(app) as c:
        body = c.post("/api/ask", json={"question": "What does ClaimService do?"}).json()
        assert body["llm_error"] and body["evidence"] and not body["llm_used"]
        assert c.get(f"/api/flow/{P}.CasingService.processClaims").status_code == 200


def test_java2okf_bundle_graph_hides_external_by_default(tmp_path):
    from tests.conftest import FIXTURES

    app = create_app(make_settings(tmp_path, FIXTURES / "java2okf-sample"), llm=MockLLMProvider())
    with TestClient(app) as c:
        cls = "java-class:com.example.OrderService"
        body = c.get(f"/api/graph/subgraph/{cls}", params={"depth": 1}).json()
        assert body["hidden_external"] > 0
        assert all(n.get("status") != "external" for n in body["nodes"])
        body = c.get(f"/api/graph/subgraph/{cls}", params={"depth": 1, "include_external": True}).json()
        assert any(n.get("status") == "external" for n in body["nodes"])
        body = c.get(f"/api/graph/subgraph/{cls}", params={"depth": 2, "max_nodes": 3}).json()
        assert len(body["nodes"]) == 3 and body["truncated"]
        ent = c.get(f"/api/entities/{cls}").json()
        assert ent["entity"]["title"] == "OrderService" and ent["signature"] == "public class OrderService"
        rels = c.get(f"/api/entities/{cls}/relationships").json()
        assert any(e["status"] == "external" and e["other"]["type"] == "external" for e in rels["outgoing"])
        flow = c.get("/api/flow/java-method:com.example.OrderService.placeOrder(com.example.Customer,double)").json()
        assert flow["availability"] == "call_sequence" and "line 22" in flow["text"]


def test_entity_source_endpoint(tmp_path):
    from tests.conftest import FIXTURES

    settings = make_settings(tmp_path, FIXTURES / "java2okf-sample")
    m = "java-method:com.example.OrderService.placeOrder(com.example.Customer,double)"
    with TestClient(create_app(settings, llm=MockLLMProvider())) as c:
        assert c.get(f"/api/entities/{m}/source").json()["available"] is False
    settings.source.root_dir = str(FIXTURES / "java2okf-source")
    with TestClient(create_app(settings, llm=MockLLMProvider())) as c:
        body = c.get(f"/api/entities/{m}/source").json()
        assert body["available"] and body["start_line"] == 17 and body["end_line"] == 24
        assert body["conditions"][0]["expression"] == "amount <= 0"
        assert c.get("/api/status").json()["source"]["enabled"] is True


def test_explorer_tree_members_have_children_lists(client):
    tree = client.get("/api/explorer/tree").json()

    def walk(nodes):
        for n in nodes:
            assert isinstance(n.get("children"), list), n
            walk(n["children"])
    walk(tree)
