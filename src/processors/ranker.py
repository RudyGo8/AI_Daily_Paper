"""Deterministic ranking after scoring, before expensive summarization."""
from src.models.schemas import NewsItem


def rank(items: list[NewsItem], topic: str, top_k: int) -> list[NewsItem]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    candidates = [item for item in items if not item.topic or item.topic == topic]
    return sorted(candidates, key=lambda i: (i.hot_score, i.published_at, i.cluster_size), reverse=True)[:top_k]
