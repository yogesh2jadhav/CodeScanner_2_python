import json
import time

from codeknowledge.services.cache_service import AnswerCache, cache_key


def test_cache_key_components():
    base = cache_key("Who calls X?", "h1", "m", {"k": 1}, True)
    assert base == cache_key("  who   calls x? ", "h1", "m", {"k": 1}, True)  # normalised question
    assert base != cache_key("Who calls X?", "h2", "m", {"k": 1}, True)  # OKF version
    assert base != cache_key("Who calls X?", "h1", "m2", {"k": 1}, True)  # model
    assert base != cache_key("Who calls X?", "h1", "m", {"k": 2}, True)  # retrieval config
    assert base != cache_key("Who calls X?", "h1", "m", {"k": 1}, False)


def test_cache_roundtrip_ttl_and_version(settings):
    c = AnswerCache(settings)
    c.put("k", "q", "v1", {"answer": "a"})
    entry = c.get("k", "v1")
    assert entry["response"] == {"answer": "a"} and entry["question"] == "q" and entry["knowledge_base_version"] == "v1"
    assert c.get("k", "v2") is None  # version mismatch invalidates (and deletes)
    c.put("k", "q", "v1", {"answer": "a"})
    p = c.dir / "k.json"
    data = json.loads(p.read_text())
    data["timestamp"] = time.time() - settings.cache.ttl_seconds - 1
    p.write_text(json.dumps(data))
    assert c.get("k", "v1") is None  # expired


def test_cache_purge(settings):
    c = AnswerCache(settings)
    c.put("a", "q", "v1", {})
    c.put("b", "q", "v2", {})
    (c.dir / "bad.json").write_text("{not json")
    assert c.purge(keep_version="v2") == 2
    assert c.get("b", "v2") is not None


def test_cache_disabled(settings):
    settings.cache.enabled = False
    c = AnswerCache(settings)
    c.put("k", "q", "v", {})
    assert c.get("k", "v") is None
