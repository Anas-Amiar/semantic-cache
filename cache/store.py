"""
The semantic cache store.

Key properties:
  - Scope isolation: entries are keyed by scope (hash of system prompt +
    model + temperature).  Identical user prompts under different scopes
    NEVER share entries — no cross-contamination between use cases.
  - Similarity lookup: nearest neighbor by cosine within the scope; hit if
    similarity >= threshold, near-miss logged if within 0.10 below it.
  - TTL expiry against a caller-supplied clock (simulated in the load test).
"""

import hashlib
import uuid

from cache.models import CacheEntry, LookupResult
from cache.embedder import embed, cosine

DEFAULT_THRESHOLD = 0.60
NEAR_MISS_WINDOW = 0.10


def scope_key(system_prompt: str, model: str, temperature: float) -> str:
    raw = f"{system_prompt}|{model}|{temperature}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class SemanticCache:
    def __init__(self, threshold: float = DEFAULT_THRESHOLD) -> None:
        self.threshold = threshold
        self._entries: list[CacheEntry] = []
        self._vectors: dict[str, dict[str, float]] = {}
        self.near_miss_log: list[dict] = []

    def lookup(self, prompt: str, scope: str, now: float) -> LookupResult:
        q_vec = embed(prompt)
        best_sim, best_entry = 0.0, None

        for e in self._entries:
            if e.scope_key != scope:
                continue
            sim = cosine(q_vec, self._vectors[e.entry_id])
            if sim > best_sim:
                best_sim, best_entry = sim, e

        if best_entry is None:
            return LookupResult(status="miss", similarity=0.0)

        if now - best_entry.created_at > best_entry.ttl_seconds:
            return LookupResult(status="expired", similarity=best_sim, entry=best_entry)

        if best_sim >= self.threshold:
            best_entry.hit_count += 1
            return LookupResult(status="hit", similarity=best_sim, entry=best_entry)

        if best_sim >= self.threshold - NEAR_MISS_WINDOW:
            self.near_miss_log.append({
                "prompt": prompt, "similarity": round(best_sim, 4),
                "would_have_matched": best_entry.prompt,
            })
            return LookupResult(status="near_miss", similarity=best_sim, entry=best_entry)

        return LookupResult(status="miss", similarity=best_sim)

    def put(self, prompt: str, scope: str, response: str, model: str,
            now: float, ttl_seconds: float, intent: str | None = None) -> None:
        if ttl_seconds <= 0:
            return  # policy says: do not cache
        entry = CacheEntry(
            entry_id=uuid.uuid4().hex[:12], prompt=prompt, scope_key=scope,
            response=response, model=model, created_at=now,
            ttl_seconds=ttl_seconds, intent=intent,
        )
        self._entries.append(entry)
        self._vectors[entry.entry_id] = embed(prompt)

    def invalidate_scope(self, scope: str) -> int:
        """When a system prompt or model changes, drop every entry in its scope."""
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.scope_key != scope]
        return before - len(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
