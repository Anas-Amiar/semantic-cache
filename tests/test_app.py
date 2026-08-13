"""
HTTP-layer tests: a paraphrase of a prior request is served from cache, stats
reflect the savings, and scope invalidation clears entries.
"""

from fastapi.testclient import TestClient

from cache.app import app, cache, _stats

client = TestClient(app)


def setup_function():
    # fresh cache + counters for each test
    cache._entries.clear()
    cache._vectors.clear()
    cache.near_miss_log.clear()
    _stats.update(total=0, hits=0, misses=0, cost_usd=0.0)


def test_first_request_is_a_miss_then_paraphrase_hits():
    first = client.post("/v1/complete", json={"prompt": "What is Python programming language?"})
    assert first.status_code == 200
    assert first.json()["cache"] == "miss"
    assert first.json()["cost_usd"] > 0

    second = client.post("/v1/complete", json={"prompt": "Describe the Python programming language"})
    body = second.json()
    assert body["cache"] == "hit"
    assert body["cost_usd"] == 0.0
    assert body["saved_usd"] > 0
    assert body["response"] == first.json()["response"]   # same cached answer served


def test_stats_reflect_savings():
    client.post("/v1/complete", json={"prompt": "What are the API rate limits?"})
    client.post("/v1/complete", json={"prompt": "API rate limits — what are the maximums?"})
    s = client.get("/stats").json()
    assert s["total_requests"] == 2
    assert s["hits"] == 1
    assert s["misses"] == 1
    assert s["savings_pct"] == 50.0


def test_lookalike_does_not_falsely_hit():
    client.post("/v1/complete", json={"prompt": "What is Python programming language?"})
    r = client.post("/v1/complete", json={"prompt": "How do I install Python on Windows?"})
    assert r.json()["cache"] == "miss"


def test_invalidate_clears_scope():
    client.post("/v1/complete", json={"prompt": "What are the API rate limits?"})
    assert client.get("/health").json()["entries"] == 1
    inv = client.post("/invalidate", json={}).json()
    assert inv["invalidated"] == 1
    assert client.get("/health").json()["entries"] == 0


def test_root_and_health():
    assert client.get("/").status_code == 200
    assert client.get("/health").json()["status"] == "ok"
