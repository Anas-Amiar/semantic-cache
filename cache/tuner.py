"""
The similarity threshold tuner — the core interview talking point.

Sweeps thresholds over the labeled traffic and reports, per threshold:
  hit rate       — how often a repeated/paraphrased query hits the cache
  wrong-hit rate — how often a hit served an answer for a DIFFERENT intent
                   (measured against the traffic's ground-truth intent labels)

Low thresholds maximize savings but serve wrong answers; high thresholds are
safe but barely cache anything.  The sweep makes that tradeoff visible with
data instead of guesswork.
"""

from cache.store import SemanticCache, scope_key
from cache.proxy import cached_completion


def sweep(traffic: list[dict], thresholds: list[float]) -> list[dict]:
    results = []
    for th in thresholds:
        cache = SemanticCache(threshold=th)
        hits = wrong_hits = 0
        now = 0.0
        for item in traffic:
            scope = scope_key("default", "gpt-4o-mini", 0.0)
            lookup = cache.lookup(item["prompt"], scope, now)
            if lookup.status == "hit":
                hits += 1
                if lookup.entry.intent != item["intent"]:
                    wrong_hits += 1
            cached_completion(cache, item["prompt"], now, intent=item["intent"])
            now += 10.0
        total = len(traffic)
        results.append({
            "threshold": th,
            "hit_rate_pct": round(100 * hits / total, 1),
            "wrong_hit_rate_pct": round(100 * wrong_hits / hits, 1) if hits else 0.0,
            "hits": hits, "wrong_hits": wrong_hits,
        })
    return results


if __name__ == "__main__":
    from data.traffic import TRAFFIC

    print("=== Similarity threshold sweep ===")
    print(f"{'threshold':>9} | {'hit rate':>8} | {'wrong-hit rate':>14}")
    for r in sweep(TRAFFIC, [0.25, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]):
        print(f"{r['threshold']:>9} | {r['hit_rate_pct']:>7}% | {r['wrong_hit_rate_pct']:>13}%"
              f"   ({r['hits']} hits, {r['wrong_hits']} wrong)")
