"""
HTTP layer for the semantic cache — turns the store into a runnable drop-in
proxy an app can point at instead of the LLM provider.

    uvicorn cache.app:app --reload

Runs on the mock embedder + mock provider by default, so it needs **no secrets**
and is safe to deploy as a public demo. Swap embed() (embedder.py) and _mock_llm
(proxy.py) for real API calls to make it live.

Endpoints:
    POST /v1/complete   cached completion; returns the response + whether it was a
                        cache hit, the match similarity, latency, cost, and $ saved
    GET  /stats         running hit rate, cost, baseline cost, and savings %
    POST /invalidate    drop every cached entry in a scope (system prompt/model change)
    GET  /health        liveness + number of cached entries
"""

import os
import random
import time

from pydantic import BaseModel
from fastapi import FastAPI

from cache.store import SemanticCache, scope_key
from cache.ttl_policy import ttl_for_prompt
from cache.proxy import _mock_llm, LLM_COST_USD, LLM_LATENCY_MS, HIT_LATENCY_MS

# The threshold tuner (see README) found 0.40 to be the sweet spot on this
# traffic: maximal hit rate at a 0% wrong-hit rate. Override with CACHE_THRESHOLD.
THRESHOLD = float(os.getenv("CACHE_THRESHOLD", "0.40"))

app = FastAPI(
    title="Semantic Cache",
    version="1.0.0",
    description="Semantic caching middleware for LLM APIs: matches requests by meaning, "
                "serves cached answers, and tracks the hit-rate / wrong-hit tradeoff.",
)

cache = SemanticCache(threshold=THRESHOLD)
_rng = random.Random(0)

_stats = {"total": 0, "hits": 0, "misses": 0, "cost_usd": 0.0}


class CompleteRequest(BaseModel):
    prompt: str
    system_prompt: str = "default"
    model: str = "gpt-4o-mini"
    temperature: float = 0.0


@app.get("/")
def root() -> dict:
    return {
        "service": "semantic-cache",
        "threshold": THRESHOLD,
        "docs": "/docs",
        "try": "POST /v1/complete with {\"prompt\": \"What is Python?\"}, then POST a paraphrase",
        "stats": "/stats",
    }


@app.post("/v1/complete")
def complete(req: CompleteRequest) -> dict:
    now = time.time()
    scope = scope_key(req.system_prompt, req.model, req.temperature)
    result = cache.lookup(req.prompt, scope, now)

    _stats["total"] += 1
    if result.status == "hit" and result.entry is not None:
        _stats["hits"] += 1
        return {
            "response": result.entry.response,
            "cache": "hit",
            "similarity": round(result.similarity, 4),
            "latency_ms": round(_rng.uniform(*HIT_LATENCY_MS), 2),
            "cost_usd": 0.0,
            "saved_usd": LLM_COST_USD,
        }

    # miss / expired / near_miss -> call the provider and cache the fresh answer
    response = _mock_llm(req.prompt, req.model)
    cache.put(req.prompt, scope, response, req.model, now,
              ttl_seconds=ttl_for_prompt(req.prompt))
    _stats["misses"] += 1
    _stats["cost_usd"] += LLM_COST_USD
    return {
        "response": response,
        "cache": "miss",
        "similarity": round(result.similarity, 4),
        "latency_ms": round(_rng.uniform(*LLM_LATENCY_MS), 2),
        "cost_usd": LLM_COST_USD,
        "saved_usd": 0.0,
    }


@app.get("/stats")
def stats() -> dict:
    total = _stats["total"]
    baseline = total * LLM_COST_USD          # cost if every request hit the provider
    actual = _stats["cost_usd"]
    return {
        "total_requests": total,
        "hits": _stats["hits"],
        "misses": _stats["misses"],
        "hit_rate_pct": round(100 * _stats["hits"] / total, 1) if total else 0.0,
        "cost_usd": round(actual, 4),
        "baseline_cost_usd": round(baseline, 4),
        "savings_pct": round(100 * (baseline - actual) / baseline, 1) if baseline else 0.0,
        "entries_cached": len(cache),
        "near_misses": len(cache.near_miss_log),
    }


class InvalidateRequest(BaseModel):
    system_prompt: str = "default"
    model: str = "gpt-4o-mini"
    temperature: float = 0.0


@app.post("/invalidate")
def invalidate(req: InvalidateRequest) -> dict:
    scope = scope_key(req.system_prompt, req.model, req.temperature)
    removed = cache.invalidate_scope(scope)
    return {"invalidated": removed, "remaining": len(cache)}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "threshold": THRESHOLD, "entries": len(cache)}
