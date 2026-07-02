"""
Load test with a simulated clock: replays the labeled traffic pool many times
(with repeats, like real usage) and reports the headline numbers — hit rate,
latency percentiles, and cost savings vs. no cache.
"""

import random
import statistics

from cache.models import CacheStats
from cache.store import SemanticCache
from cache.proxy import cached_completion, LLM_COST_USD


def run_load_test(traffic: list[dict], n_requests: int = 300,
                  threshold: float = 0.60, seed: int = 42) -> CacheStats:
    rng = random.Random(seed)
    cache = SemanticCache(threshold=threshold)

    outcomes = []
    now = 0.0
    for _ in range(n_requests):
        item = rng.choice(traffic)   # repeats naturally, like production traffic
        outcomes.append(cached_completion(
            cache, item["prompt"], now, intent=item["intent"], rng=rng))
        now += rng.uniform(1, 30)    # simulated seconds between requests

    hits = [o for o in outcomes if o.status == "hit"]
    latencies = sorted(o.latency_ms for o in outcomes)
    total_cost = sum(o.cost_usd for o in outcomes)
    baseline = n_requests * LLM_COST_USD

    return CacheStats(
        total_requests=n_requests,
        hits=len(hits), misses=n_requests - len(hits),
        hit_rate_pct=round(100 * len(hits) / n_requests, 1),
        total_cost_usd=round(total_cost, 4),
        baseline_cost_usd=round(baseline, 4),
        savings_pct=round(100 * (baseline - total_cost) / baseline, 1),
        p50_latency_ms=round(statistics.median(latencies), 1),
        p95_latency_ms=round(latencies[int(0.95 * len(latencies))], 1),
        near_misses=len(cache.near_miss_log),
    )


if __name__ == "__main__":
    from data.traffic import TRAFFIC

    stats = run_load_test(TRAFFIC, n_requests=300)
    print("=== Semantic cache load test (300 requests, simulated clock) ===")
    print(f"Hit rate:        {stats.hit_rate_pct}%  ({stats.hits} hits / {stats.misses} misses)")
    print(f"Cost:            ${stats.total_cost_usd}  vs baseline ${stats.baseline_cost_usd}")
    print(f"Savings:         {stats.savings_pct}%")
    print(f"Latency P50:     {stats.p50_latency_ms} ms   (uncached calls ~700-1400 ms)")
    print(f"Latency P95:     {stats.p95_latency_ms} ms")
    print(f"Near-misses:     {stats.near_misses}  (logged for threshold tuning)")
