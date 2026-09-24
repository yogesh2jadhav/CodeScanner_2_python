import logging

from fastapi.testclient import TestClient

from codeknowledge.api.app import create_app
from codeknowledge.config.settings import load_settings
from codeknowledge.utils.logging import request_id_var, setup_logging


def test_health_endpoint(settings):
    client = TestClient(create_app(settings))
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": "0.1.0"}


def test_openapi_docs_available(settings):
    client = TestClient(create_app(settings))
    assert client.get("/docs").status_code == 200
    assert "/api/health" in client.get("/openapi.json").json()["paths"]


def test_config_loads_yaml(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text("llm:\n  model: foo:1b\nretrieval:\n  graph_max_depth: 5\n")
    s = load_settings(cfg, env={})
    assert s.llm.model == "foo:1b"
    assert s.retrieval.graph_max_depth == 5
    assert s.vector.collection_name == "codeknowledge"  # default retained


def test_config_env_overrides(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text("llm:\n  model: foo:1b\n")
    env = {
        "CODEKNOWLEDGE_LLM_MODEL": "bar:7b",
        "CODEKNOWLEDGE_LLM_BASE_URL": "http://x:1",
        "CODEKNOWLEDGE_OKF_SOURCE_DIR": "/okf",
        "CODEKNOWLEDGE_VECTOR_PERSIST_DIRECTORY": "/vec",
        "CODEKNOWLEDGE_RETRIEVAL_GRAPH_MAX_DEPTH": "7",
        "CODEKNOWLEDGE_CACHE_ENABLED": "false",
    }
    s = load_settings(cfg, env=env)
    assert s.llm.model == "bar:7b"
    assert s.llm.base_url == "http://x:1"
    assert s.okf.source_dir == "/okf"
    assert s.vector.persist_directory == "/vec"
    assert s.retrieval.graph_max_depth == 7
    assert s.cache.enabled is False


def test_config_missing_file_uses_defaults(tmp_path):
    s = load_settings(tmp_path / "nope.yaml", env={})
    assert s.application.version == "0.1.0"


def test_repo_config_file_is_valid():
    s = load_settings("config/config.yaml", env={})
    assert s.embedding.model == "nomic-embed-text"


def test_logging_initialization(tmp_path):
    log_file = tmp_path / "logs" / "app.log"
    setup_logging("DEBUG", str(log_file), None)
    token = request_id_var.set("abc123")
    try:
        logging.getLogger("TestComponent").info("hello")
    finally:
        request_id_var.reset(token)
    for h in logging.getLogger().handlers:
        h.flush()
    text = log_file.read_text()
    assert "TestComponent" in text and "request_id=abc123" in text and "hello" in text


def test_logging_from_yaml(tmp_path):
    log_file = tmp_path / "y.log"
    setup_logging("INFO", str(log_file), "config/logging.yaml")
    logging.getLogger("Y").info("from yaml")
    for h in logging.getLogger().handlers:
        h.flush()
    assert "from yaml" in log_file.read_text()
