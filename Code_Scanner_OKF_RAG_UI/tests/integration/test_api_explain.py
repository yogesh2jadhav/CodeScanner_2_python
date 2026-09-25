"""POST /api/methods/{id}/explain and Ask routing, with fake models."""
import json

import pytest
from fastapi.testclient import TestClient

from codeknowledge.api.app import create_app
from codeknowledge.llm.provider import LLMModelMissingError, LLMTimeoutError, MockLLMProvider
from tests.conftest import BUILD_VISITS, EXPLAIN_JAVA, EXPLAIN_OKF, make_settings
from tests.unit.test_explain_llm import GOOD

URL = f"/api/methods/{BUILD_VISITS}/explain"


def client(tmp_path, llm, **overrides):
    s = make_settings(tmp_path, EXPLAIN_OKF)
    s.source.root_dir = str(EXPLAIN_JAVA)
    for k, v in overrides.items():
        setattr(s.method_explanation, k, v)
    return TestClient(create_app(s, llm=llm))


def test_success(tmp_path):
    with client(tmp_path, MockLLMProvider(json_responses=[json.dumps(GOOD)])) as c:
        r = c.post(URL, json={"max_callee_depth": 1}, headers={"X-Request-ID": "abc"})
        body = r.json()
        assert r.status_code == 200 and body["request_id"] == "abc"
        assert body["method_signature"].startswith("public List<Visit> buildVisits")
        assert body["explanation"]["execution_steps"][0]["source_refs"][0] == {"evidence_id": "E2", "start_line": 30, "end_line": 32}
        assert body["model"]["prompt_version"] == "method-explanation-v1"
        assert body["validation"]["valid"] and body["markdown"]
        assert any(e["kind"] == "method_source" for e in body["evidence"])
        # second call is served from cache; force_refresh bypasses it
        assert c.post(URL, json={"max_callee_depth": 1}).json()["cached"] is True
        assert c.post(URL, json={"max_callee_depth": 1, "force_refresh": True}).json()["cached"] is False


def test_evidence_only(tmp_path):
    llm = MockLLMProvider()
    with client(tmp_path, llm) as c:
        body = c.post(URL, json={"use_llm": False}).json()
        assert body["explanation"] is None and body["facts"]["conditions"] and not llm.json_calls


def test_not_found_invalid_and_disabled(tmp_path):
    with client(tmp_path, MockLLMProvider()) as c:
        r = c.post("/api/methods/java-method:no.Such.m()/explain")
        assert r.status_code == 404 and r.json()["request_id"]
        assert c.post(URL, json={"max_callee_depth": 9}).status_code == 422
        assert c.post(URL, json={"detail": "novel"}).status_code == 422
        # control characters never reach the service (router 404 or validator 422)
        assert c.post("/api/methods/a%0Ab/explain").status_code in (404, 422)
    with client(tmp_path / "d", MockLLMProvider(), enabled=False) as c:
        assert c.post(URL).status_code == 404


@pytest.mark.parametrize("error,status", [
    (LLMTimeoutError("Ollama did not answer within 600s"), 504),
    (LLMModelMissingError("Model 'x' is not installed in Ollama. Run: ollama pull x"), 503),
])
def test_llm_failures_are_controlled(tmp_path, error, status):
    with client(tmp_path, MockLLMProvider(error=error)) as c:
        r = c.post(URL)
        assert r.status_code == status
        assert "Traceback" not in r.text and r.json()["request_id"]
        assert str(error) in r.json()["detail"]


def test_malformed_model_output_is_partial_not_error(tmp_path):
    with client(tmp_path, MockLLMProvider(json_responses=["nonsense"])) as c:
        body = c.post(URL).json()
        assert body["explanation"] is None and body["validation"]["repair_attempts"] == 1
        assert body["evidence"] and "nonsense" not in json.dumps(body)


def test_ask_explain_routes_to_method_workflow(tmp_path):
    llm = MockLLMProvider(json_responses=[json.dumps(GOOD)])
    with client(tmp_path, llm) as c:
        body = c.post("/api/ask", json={"question": "Explain VisitProcessor.buildVisits", "use_cache": False}).json()
        assert body["category"] == "FUNCTIONAL_EXPLANATION"
        assert body["method_explanation"]["method_id"] == BUILD_VISITS
        assert body["interpretation"].startswith("## VisitProcessor.buildVisits")
        assert llm.json_calls and not llm.calls  # structured path only


def test_openapi_documents_endpoint(tmp_path):
    with client(tmp_path, MockLLMProvider()) as c:
        assert "/api/methods/{method_id}/explain" in c.get("/openapi.json").json()["paths"]
