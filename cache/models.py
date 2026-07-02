from pydantic import BaseModel
from typing import Optional, Literal


class CacheEntry(BaseModel):
    entry_id: str
    prompt: str                 # original prompt text (kept for debugging/audit)
    scope_key: str              # hash of system prompt + model + temperature —
                                # different scopes NEVER share entries
    response: str
    model: str
    created_at: float           # simulated clock seconds
    ttl_seconds: float
    hit_count: int = 0
    intent: Optional[str] = None  # ground-truth label, used by the threshold tuner


class LookupResult(BaseModel):
    status: Literal["hit", "miss", "expired", "near_miss"]
    similarity: float
    entry: Optional[CacheEntry] = None


class RequestOutcome(BaseModel):
    prompt: str
    status: str                 # hit / miss
    latency_ms: float           # simulated
    cost_usd: float
    similarity: float


class CacheStats(BaseModel):
    total_requests: int
    hits: int
    misses: int
    hit_rate_pct: float
    total_cost_usd: float
    baseline_cost_usd: float    # what it would cost with no cache
    savings_pct: float
    p50_latency_ms: float
    p95_latency_ms: float
    near_misses: int
