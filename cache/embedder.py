"""
Mock embedder: bag-of-words TF vectors + cosine similarity.
In production, replace embed() with an embedding API call — the store,
policies, tuner, and load test are unchanged.
"""

import math
import re

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "in", "on",
    "for", "and", "or", "me", "my", "your", "you", "i", "we", "it", "this",
    "that", "what", "how", "please", "can", "could", "do", "does", "explain",
    "tell", "about", "give", "describe",
}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


def embed(text: str) -> dict[str, float]:
    tokens = _tokenize(text)
    if not tokens:
        return {}
    counts: dict[str, float] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = len(tokens)
    return {t: c / total for t, c in counts.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a.get(t, 0.0) * v for t, v in b.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0
