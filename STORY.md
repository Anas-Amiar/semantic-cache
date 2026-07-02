# Semantic Caching Layer for LLM APIs — the pitch

*A 2-minute walkthrough for presenting this project in an interview.*

## The 30-second version

"Companies running LLMs at scale pay repeatedly for the same answers, because users phrase
the same question a hundred ways and exact-match caching catches none of it. I built a
semantic cache: every prompt is embedded, and incoming requests that are semantically close
to an already-answered one get the cached response in ~2 milliseconds instead of a ~1-second,
paid API call. In a 300-request load test it hit 89.7% cache hit rate and cut costs 89.7%.
But the number I'm most proud of is the tradeoff curve: I labeled the test traffic with
ground-truth intents so I could measure not just hit rate but *wrong-hit* rate — at a loose
threshold the cache serves wrong answers 22% of the time; at 0.40 wrong hits disappear
while keeping half the traffic cached. That's the engineering decision, quantified."

## The problem, in plain terms

A support bot gets asked "What's your refund policy?", "Can I get a refund?", "refund
policy for annual plans?" — a hundred phrasings, one answer, a hundred API calls. Multiply
by every common question and you're burning real money and adding a second of latency to
answers you already computed. Exact-match caching is useless here because no two phrasings
are byte-identical.

## The idea

Cache on meaning, not text. Embed every prompt; on each request, find the nearest cached
neighbor; if similarity clears a threshold, serve the cached response. But the threshold is
a genuine tradeoff — too loose and you serve the *wrong* cached answer (worse than no
cache), too strict and you save nothing — so build the instrumentation to measure that
tradeoff with data.

## How I built it (in order, and why that order)

1. **The store with scope isolation** (`cache/store.py`) — entries are keyed by a hash of
   (system prompt, model, temperature). Identical user prompts under different system
   prompts never share entries. Built first because contamination between use cases is the
   bug that kills semantic caches in production, and it has to be impossible by construction.

2. **The TTL policy** (`cache/ttl_policy.py`) — content-based tiers: time-sensitive prompts
   ("weather today") get 1 hour, stable facts get 24, creative prompts ("write me a poem")
   are never cached — replaying creative output is a bug, not a feature.

3. **The labeled traffic** (`data/traffic.py`) — paraphrase groups that SHOULD share a
   cache entry, plus deliberate traps: queries sharing vocabulary but not intent
   ("refund my subscription" vs "cancel my subscription"). The labels are what make
   wrong-hit rate measurable instead of anecdotal.

4. **The proxy** (`cache/proxy.py`) — `cached_completion()`, the drop-in call. Simulated
   provider latency (~900ms) and cost ($0.002) on misses; ~2ms on hits. The clock is
   caller-supplied, so TTL logic is testable and the load test runs in milliseconds.

5. **The threshold tuner** (`cache/tuner.py`) — sweeps thresholds over the labeled traffic
   and reports hit rate AND wrong-hit rate per threshold. This is the core deliverable:
   the tradeoff curve that turns "pick 0.95 and hope" into a data-driven decision.

6. **The load test** (`cache/loadtest.py`) — 300 requests with realistic repetition,
   simulated clock: hit rate, latency percentiles, cost savings.

## The result

- **89.7% hit rate and 89.7% cost savings** on the load test; P50 latency 2.6ms vs ~1s uncached
- The tradeoff curve: 0.25 → 56% hits but 22% wrong; **0.40 → 50% hits, 0% wrong**;
  0.90 → 12% hits (safe but pointless)
- Near-misses logged for tuning; creative prompts correctly never cached; scope isolation
  verified (same prompt, different system prompt → separate entries)

## What I'd highlight if asked "what was the hardest design decision?"

Refusing to report hit rate without wrong-hit rate. Hit rate alone is a vanity metric —
you can get 100% by setting the threshold to zero and serving garbage. The uncomfortable
truth about semantic caching is that its failure mode is *silently serving a wrong answer*,
which is strictly worse than a cache miss. Labeling the traffic with ground-truth intents
made that failure measurable, and the sweep found the operating point where savings stay
high and wrong hits go to zero. Building the instrumentation to see your own failure mode —
that's the actual engineering here.

## What I'd build next

- Real embeddings (the "refund vs cancel" distinction gets much sharper) and a Redis/RedisVL
  backend for sub-millisecond lookups at scale
- The FastAPI drop-in proxy mirroring the OpenAI API contract (change base URL, get caching)
- Streaming: buffer-while-streaming on misses, cache only complete successful responses
- Adaptive thresholds per request type, learned from the near-miss log + user feedback

## Companion projects

Same mission as [LLM Cost Autopilot](https://github.com/Anas-Amiar/Project-2-llm-cost-autopilot)
— cut LLM spend without hurting quality — attacked from the opposite side: the Autopilot
routes requests to cheaper models; the cache eliminates repeat requests entirely. A
production stack would run both: cache first, route on miss.
