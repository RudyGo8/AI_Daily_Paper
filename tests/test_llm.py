from __future__ import annotations

from src.llm.llm_client import LLMClient, LLMConfig
from src.llm.summarizer import NewsSummarizer
from src.models.schemas import NewsItem
from src.utils.date_utils import parse_datetime


def test_llm_client_fallback_without_api_key() -> None:
    client = LLMClient(LLMConfig(api_key=""))
    text = client.complete(prompt="Summarize today's AI market movement.")
    assert text.startswith("[fallback]")
    assert "Summarize" in text


def test_summarizer_sets_ai_summary() -> None:
    client = LLMClient(LLMConfig(api_key=""))
    summarizer = NewsSummarizer(client)
    item = NewsItem(
        source="Example",
        title="Example title",
        link="https://example.com",
        published_at=parse_datetime("2026-04-23T08:00:00+00:00"),
        summary="This is a detailed summary for testing.",
    )
    out = summarizer.summarize_items([item])
    assert "Example title" in out[0].ai_summary
    assert "核心内容" in out[0].ai_summary
