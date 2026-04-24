from __future__ import annotations

from src.models.schemas import NewsItem
from src.processors.deduplicator import NewsDeduplicator
from src.utils.date_utils import parse_datetime


def _news_item(source: str, title: str, link: str, summary: str, published_at: str) -> NewsItem:
    return NewsItem(
        source=source,
        title=title,
        link=link,
        published_at=parse_datetime(published_at),
        summary=summary,
    )


def test_deduplicator_clusters_same_event_across_sources() -> None:
    items = [
        _news_item(
            "MarkTechPost",
            "OpenAI Releases GPT-5.5, a Fully Retrained Agentic Model That Scores 82.7% on Terminal-Bench 2.0",
            "https://example.com/marktechpost-gpt55",
            "OpenAI introduces GPT-5.5 with stronger agentic coding and research performance.",
            "2026-04-23T22:11:30+00:00",
        ),
        _news_item(
            "TechCrunch AI",
            "OpenAI releases GPT-5.5, bringing company one step closer to an AI super app",
            "https://example.com/techcrunch-gpt55",
            "The new GPT-5.5 release pushes OpenAI deeper into autonomous assistants and super app ambitions.",
            "2026-04-23T18:29:29+00:00",
        ),
        _news_item(
            "The Decoder",
            "OpenAI unveils GPT-5.5, claims a new class of intelligence at double the API price",
            "https://example.com/the-decoder-gpt55",
            "GPT-5.5 is framed as an agentic model with higher pricing and stronger autonomous tool use.",
            "2026-04-23T19:01:07+00:00",
        ),
    ]

    deduplicated = NewsDeduplicator().deduplicate(items)

    assert len(deduplicated) == 1
    assert deduplicated[0].cluster_size == 3
    assert set(deduplicated[0].merged_sources) == {
        "MarkTechPost",
        "TechCrunch AI",
        "The Decoder",
    }
    assert len(deduplicated[0].merged_links) == 3
