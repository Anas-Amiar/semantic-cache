"""
TTL tier classifier: prompts that reference time or current events get short
TTLs (or no caching at all); stable/factual prompts get long TTLs.
"""

import re

TIME_SENSITIVE = re.compile(
    r"\b(today|tomorrow|yesterday|now|current|currently|latest|this (week|month|year)|"
    r"news|weather|stock|price of|score)\b", re.IGNORECASE)

CREATIVE = re.compile(
    r"\b(write|compose|poem|story|creative|brainstorm|imagine|joke)\b", re.IGNORECASE)


def ttl_for_prompt(prompt: str) -> float:
    """Returns TTL in seconds. 0 means: do not cache."""
    if TIME_SENSITIVE.search(prompt):
        return 3600.0            # 1 hour — answer changes with the world
    if CREATIVE.search(prompt):
        return 0.0               # creative output shouldn't be replayed
    return 86400.0               # 24h — stable factual content


if __name__ == "__main__":
    for p in ["What is Python?", "What's the weather today?", "Write me a poem about rain"]:
        print(f"{ttl_for_prompt(p):>8.0f}s  {p}")
