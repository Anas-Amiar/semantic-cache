# Semantic Caching Layer for LLM APIs

[![CI](https://github.com/Anas-Amiar/semantic-cache/actions/workflows/ci.yml/badge.svg)](https://github.com/Anas-Amiar/semantic-cache/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **▶ Live demo:** [https://semantic-cache-dzv2.onrender.com/docs](https://semantic-cache-dzv2.onrender.com/docs) — a running instance on Render's free tier. The first request after a while takes ~50s to wake the service, then it's fast.

A caching middleware that sits between an application and any LLM provider, detects
semantically similar requests that were already answered ("What is Python?" ≈ "Describe the
Python programming language"), and serves cached responses instantly.

Ships as a real HTTP service (FastAPI) **and** a pure, unit-tested core. Runs on a mock
embedder + mock provider by default, so it needs **no API keys** — clone it and the proxy
(or the one-click deploy) is live immediately.

**Mock-mode load test (300 requests, realistic repeat traffic, simulated clock): 89.7% hit
rate, 89.7% cost savings, P50 latency 2.6ms vs ~1000ms uncached.** Reproducible on your
machine with `python3 -m cache.loadtest` — no keys, no network.

And the number that matters more — the threshold tradeoff, measured with ground-truth
intent labels:

| Similarity threshold | Hit rate | Wrong-hit rate |
|---|---|---|
| 0.25 | 56.2% | **22.2% — serving wrong answers** |
| 0.30 | 50.0% | 12.5% |
| **0.40** | **50.0%** | **0.0% — the sweet spot** |
| 0.60 | 31.2% | 0.0% |
| 0.90 | 12.5% | 0.0% — safe but barely caching |

## Why this exists

Every company running LLMs at scale pays repeatedly for the same answers: users phrase the
same question a hundred different ways, and each phrasing is a fresh API call. Exact-match
caching catches none of this. A semantic cache embeds each prompt and matches on meaning —
but the similarity threshold is a genuine engineering tradeoff (too loose = wrong answers
served from cache; too strict = no savings), and this project measures that tradeoff with
data instead of guessing.

## How it works

```
cache/
  models.py      Typed shapes: CacheEntry, LookupResult, RequestOutcome, CacheStats
  embedder.py    Bag-of-words TF vectors + cosine (mock; swap embed() for a real API)
  store.py       The semantic cache: scope isolation, similarity lookup, TTL expiry,
                 scope invalidation, near-miss logging
  ttl_policy.py  TTL tiers by prompt content: time-sensitive -> 1h, stable -> 24h,
                 creative -> never cached
  proxy.py       cached_completion() — the drop-in call an app makes instead of the LLM.
                 Hits return in ~2ms; misses go to the (mock) provider at ~900ms/$0.002
  tuner.py       Threshold sweep with ground-truth intent labels: hit rate vs. wrong-hit
                 rate per threshold — the core tradeoff, quantified
  loadtest.py    300-request load test on a SIMULATED clock (runs in milliseconds):
                 hit rate, latency percentiles, cost savings
  app.py         FastAPI HTTP layer: POST /v1/complete, GET /stats, POST /invalidate,
                 GET /health — the drop-in proxy an app points at instead of the LLM
data/traffic.py  Labeled traffic: paraphrase groups that SHOULD share a cache entry, plus
                 look-alike queries (same vocabulary, different intent) that must NOT
tests/           Deterministic pytest suite (paraphrase hits, look-alike misses, TTL,
                 scope isolation/invalidation) — no network
reports/         (gitignored)
```

### Key design properties

- **Scope isolation**: the cache key includes a hash of (system prompt, model, temperature).
  Two identical user prompts under different system prompts never share an entry — no
  cross-contamination between use cases.
- **TTL by content**: "what's the weather today" gets 1 hour; "what is Python" gets 24;
  "write me a poem" is never cached (replaying creative output is a bug, not a feature).
- **Near-miss log**: queries that fell just under the threshold are recorded — that's the
  data you use to tune the threshold and to find normalization opportunities.
- **Scope invalidation**: when a feature's system prompt changes, one call drops every
  entry in that scope.

## Quickstart

```bash
git clone https://github.com/Anas-Amiar/semantic-cache.git
cd semantic-cache
pip install -r requirements.txt

python3 -m cache.ttl_policy   # TTL tiers per prompt type
python3 -m cache.tuner        # the threshold sweep (the tradeoff table)
python3 -m cache.loadtest     # 300-request load test: hit rate, latency, savings
```

Mock mode throughout: bag-of-words embeddings, simulated provider latency/cost, and a
simulated clock (the load test replays hours of traffic in milliseconds). Swapping in
production pieces: `embed()` → embedding API; `_mock_llm()` → real provider call; the
store → Redis+RedisVL or Qdrant. The policies, tuner, and metrics are unchanged.

## Run the API

```bash
uvicorn cache.app:app --reload    # http://localhost:8000  (interactive docs at /docs)
```

```bash
# ask once -> miss (goes to the provider), then ask a paraphrase -> cache hit at $0
curl -s -X POST localhost:8000/v1/complete -H 'content-type: application/json' \
  -d '{"prompt":"What is Python programming language?"}'
curl -s -X POST localhost:8000/v1/complete -H 'content-type: application/json' \
  -d '{"prompt":"Describe the Python programming language"}'
# -> {"cache":"hit","similarity":1.0,"cost_usd":0.0,"saved_usd":0.002, ...}
```

A look-alike query with different intent ("How do I install Python on Windows?") lands
below the threshold and is correctly served as a miss, not a wrong cache hit. `GET /stats`
returns the running hit rate and savings; `POST /invalidate` drops a scope's entries.
The match threshold defaults to **0.40** (the tuner's sweet spot) — override with the
`CACHE_THRESHOLD` env var.

## Deploy your own

Runs on the mock embedder + provider with no secrets, so a public demo is one click:

- **Render** — New → Blueprint → point at this repo (`render.yaml` included, free tier).
- **Docker** — `docker build -t semantic-cache . && docker run -p 8000:8000 semantic-cache`

## Testing

```bash
pip install -r requirements-dev.txt
pytest -q        # 15 tests, deterministic, no network
```

The core takes a caller-supplied clock, so TTL expiry is asserted by advancing a fake
clock; paraphrase hits and look-alike misses are asserted against the labeled traffic.
CI runs the suite on Python 3.10–3.12.

## Architecture decisions

**Why measure wrong-hit rate with intent labels instead of just reporting hit rate?**
Hit rate alone is a vanity metric — you can get 100% by setting the threshold to zero and
serving garbage. The real question is "at what threshold do hits start being wrong?", and
answering it requires ground truth. The labeled traffic makes the tradeoff measurable:
at 0.25 the cache serves a refund-policy answer to a cancellation question (22% wrong);
at 0.40 wrong hits disappear while keeping half the traffic cached.

**Why scope isolation in the cache key?**
The same user prompt under a different system prompt is a different request. A support-bot
and a marketing-bot both asking "summarize this" must not share answers. Hashing
(system prompt, model, temperature) into the key prevents an entire class of subtle,
hard-to-debug contamination bugs.

**Why a simulated clock?**
TTL expiry is time-based logic, and testing it against the wall clock means slow, flaky
tests. Passing `now` explicitly makes TTL behavior instantly testable and lets the load
test replay realistic inter-arrival times without actually waiting.

## What's deliberately out of scope for v1

- Real Redis/Qdrant backend (in-memory store isolates the same interface)
- Streaming support (buffer-while-streaming on misses)
- Adaptive per-request-type thresholds learned from feedback
- Prometheus/Grafana dashboards (stats are computed; export is plumbing)
