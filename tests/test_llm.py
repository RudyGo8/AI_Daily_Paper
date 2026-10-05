from __future__ import annotations

from src.llm.llm_client import LLMClient, LLMConfig
from src.llm.summarizer import NewsSummarizer
from src.models.schemas import NewsItem
from src.utils.date_utils import parse_datetime
import pytest


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
    assert "模型摘要未生成" in out[0].ai_summary
    assert "Example" in out[0].ai_summary


@pytest.mark.parametrize("content", [None, 7, [], [{"text": None}], "  "])
def test_null_or_nontext_llm_content_is_fallback(monkeypatch, content):
    client = LLMClient(LLMConfig(api_key="mock"))
    monkeypatch.setattr(client, "_call_openai_compatible", lambda **kwargs: {"choices": [{"message": {"content": content}}]})
    item = NewsItem("Test", "MCP release", "https://example.com/test",
                    parse_datetime("2026-10-04T08:00:00Z"), "MCP update")
    result = NewsSummarizer(client).summarize_item(item)
    assert "模型摘要未生成" in result
    assert item.metadata["llm_fallback"] is True


def test_valid_text_blocks_are_joined_without_nontext_values():
    value = {"choices": [{"message": {"content": [{"text": "正文"}, {"text": None}, {"image_url": "ignored"}, {"text": "补充"}]}}]}
    assert LLMClient._extract_content(value) == "正文补充"
