"""
The drop-in proxy: cached_completion() is what an application calls instead
of the LLM API.  On a hit the cached response returns in ~2ms (simulated);
on a miss the request goes to the (mock) provider — simulated 900ms latency
and $0.002 cost — and the response is cached under the request's scope with
a policy-assigned TTL.

The clock is caller-supplied so the load test can simulate hours of traffic
in milliseconds of real time.
"""

import random

from cache.models import RequestOutcome
from cache.store import SemanticCache, scope_key
from cache.ttl_policy import ttl_for_prompt

LLM_LATENCY_MS = (700, 1400)     # simulated provider latency range
LLM_COST_USD = 0.002             # simulated cost per uncached call
HIT_LATENCY_MS = (1.0, 4.0)      # cache lookup is near-instant


def _mock_llm(prompt: str, model: str) -> str:
    return f"[{model}] Answer to: {prompt[:60]}"


def cached_completion(cache: SemanticCache, prompt: str, now: float,
                      system_prompt: str = "default", model: str = "gpt-4o-mini",
                      temperature: float = 0.0, intent: str | None = None,
                      rng: random.Random | None = None) -> RequestOutcome:
    rng = rng or random.Random(hash(prompt) & 0xFFFF)
    scope = scope_key(system_prompt, model, temperature)

    result = cache.lookup(prompt, scope, now)
    if result.status == "hit":
        return RequestOutcome(
            prompt=prompt, status="hit",
            latency_ms=round(rng.uniform(*HIT_LATENCY_MS), 2),
            cost_usd=0.0, similarity=round(result.similarity, 4),
        )

    # miss / expired / near_miss → call the provider and cache the result
    response = _mock_llm(prompt, model)
    cache.put(prompt, scope, response, model, now,
              ttl_seconds=ttl_for_prompt(prompt), intent=intent)
    return RequestOutcome(
        prompt=prompt, status="miss",
        latency_ms=round(rng.uniform(*LLM_LATENCY_MS), 2),
        cost_usd=LLM_COST_USD, similarity=round(result.similarity, 4),
    )
