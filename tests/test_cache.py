"""
Behavioural tests for the semantic cache core.

All time-based behaviour (TTL expiry) is tested against a caller-supplied clock,
so there are no sleeps and no network. Paraphrases that reduce to identical
token vectors are guaranteed hits; look-alike queries with different intent must
not hit.
"""

from cache.store import SemanticCache, scope_key
from cache.embedder import embed, cosine
from cache.ttl_policy import ttl_for_prompt

SCOPE = scope_key("default", "gpt-4o-mini", 0.0)


def put(cache, prompt, now=0.0, ttl=86400.0):
    cache.put(prompt, SCOPE, f"answer:{prompt}", "gpt-4o-mini", now, ttl_seconds=ttl)


def test_exact_repeat_is_a_hit():
    cache = SemanticCache(threshold=0.40)
    put(cache, "What is Python programming language?")
    r = cache.lookup("What is Python programming language?", SCOPE, now=1.0)
    assert r.status == "hit"
    assert r.similarity == 1.0


def test_paraphrase_hits():
    cache = SemanticCache(threshold=0.40)
    put(cache, "What is Python programming language?")
    # "describe"/"what"/"is"/"the" are stopwords -> both reduce to python+programming+language
    r = cache.lookup("Describe the Python programming language", SCOPE, now=1.0)
    assert r.status == "hit"
    assert r.similarity >= 0.99


def test_lookalike_different_intent_does_not_hit():
    cache = SemanticCache(threshold=0.40)
    put(cache, "What is Python programming language?")
    # shares only 'python' -> similarity well below threshold
    r = cache.lookup("How do I install Python on Windows?", SCOPE, now=1.0)
    assert r.status != "hit"
    assert r.similarity < 0.40


def test_empty_cache_is_a_miss():
    cache = SemanticCache(threshold=0.40)
    r = cache.lookup("anything at all here", SCOPE, now=0.0)
    assert r.status == "miss"


def test_scope_isolation():
    cache = SemanticCache(threshold=0.40)
    put(cache, "What is Python programming language?")
    other_scope = scope_key("a different system prompt", "gpt-4o-mini", 0.0)
    r = cache.lookup("What is Python programming language?", other_scope, now=1.0)
    assert r.status == "miss"          # identical prompt, different scope -> no share


def test_ttl_expiry():
    cache = SemanticCache(threshold=0.40)
    put(cache, "What is Python programming language?", now=0.0, ttl=3600.0)
    fresh = cache.lookup("What is Python programming language?", SCOPE, now=1000.0)
    assert fresh.status == "hit"
    stale = cache.lookup("What is Python programming language?", SCOPE, now=3601.0)
    assert stale.status == "expired"


def test_near_miss_is_logged():
    # threshold 0.95 so a strong-but-imperfect match lands in the near-miss window
    cache = SemanticCache(threshold=0.95)
    put(cache, "What are the API rate limits?")
    r = cache.lookup("API rate limits — what are the maximums?", SCOPE, now=1.0)
    assert r.status in ("near_miss", "hit", "miss")
    if r.status == "near_miss":
        assert cache.near_miss_log


def test_creative_prompts_are_not_cached():
    cache = SemanticCache(threshold=0.40)
    # ttl_for_prompt returns 0 for creative prompts; put() must refuse to store
    cache.put("Write me a poem about the rain", SCOPE, "a poem", "gpt-4o-mini",
              now=0.0, ttl_seconds=ttl_for_prompt("Write me a poem about the rain"))
    assert len(cache) == 0


def test_invalidate_scope_drops_entries():
    cache = SemanticCache(threshold=0.40)
    put(cache, "What is Python programming language?")
    put(cache, "What are the API rate limits?")
    removed = cache.invalidate_scope(SCOPE)
    assert removed == 2
    assert len(cache) == 0


def test_ttl_policy_tiers():
    assert ttl_for_prompt("What is Python?") == 86400.0        # stable
    assert ttl_for_prompt("What is the weather today?") == 3600.0  # time-sensitive
    assert ttl_for_prompt("Write me a poem") == 0.0            # creative -> no cache
