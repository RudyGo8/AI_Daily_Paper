from __future__ import annotations

from datetime import date
from unittest.mock import Mock

import pytest

from src.models.schemas import DailyArticle, NewsItem
from src.publishers.feishu_bot import FeishuBotPublisher
from src.utils.date_utils import parse_datetime


def _build_article() -> DailyArticle:
    item = NewsItem(
        source="OpenAI News",
        title="OpenAI releases new agentic model",
        link="https://example.com/openai-agent",
        published_at=parse_datetime("2026-04-24T08:00:00+00:00"),
        summary="A new model improves autonomous coding and research performance.",
        ai_summary="OpenAI 发布新的智能体模型，重点提升自主编码和研究能力。",
        category="模型发布",
        merged_sources=["OpenAI News", "TechCrunch AI"],
        merged_links=[
            "https://example.com/openai-agent",
            "https://example.com/openai-agent-report",
        ],
        cluster_size=2,
    )
    return DailyArticle(
        target_date=date(2026, 4, 24),
        title="AI Daily Brief",
        digest="今日聚焦模型、产品与工具更新。",
        categories={"模型发布": [item]},
        total_items=1,
    )


def test_feishu_publisher_builds_interactive_card() -> None:
    article = _build_article()
    publisher = FeishuBotPublisher(
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/demo",
        message_title="AI 日报",
        dry_run=True,
    )

    payload = publisher.build_card_payload(article)

    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "AI 日报 | 2026-04-24"
    body = payload["card"]["elements"][0]["content"]
    assert "AI Daily Brief" in body
    assert "今日聚焦模型、产品与工具更新。" in body

    section_text = payload["card"]["elements"][-1]["text"]["content"]
    assert "**模型发布**" in section_text
    assert "OpenAI News / TechCrunch AI" in section_text


def test_feishu_publisher_dry_run_returns_card_preview() -> None:
    article = _build_article()
    publisher = FeishuBotPublisher(
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/demo",
        dry_run=True,
    )

    result = publisher.publish(article)

    assert result["dry_run"] is True
    assert result["sent"] is False
    assert result["preview"]["msg_type"] == "interactive"
    assert "AI Daily Brief" in result["preview"]["card"]["elements"][0]["content"]


def test_topic_card_keeps_rank_order_and_hides_scores():
    article = _build_article()
    article.topic, article.display_name, article.emoji = "agent", "Agent / Vibe Coding", "🧠"
    first = article.categories["模型发布"][0]
    first.hot_score = 999
    article.ranked_items = [first]
    payload = FeishuBotPublisher("", dry_run=True).build_card_payload(article)
    assert "Top 1" in payload["card"]["header"]["title"]["content"]
    text = payload["card"]["elements"][-1]["text"]["content"]
    assert "1. OpenAI releases" in text
    assert "hot_score" not in str(payload)
    assert "999" not in str(payload)


def test_feishu_business_error_is_not_reported_sent(monkeypatch):
    response = Mock()
    response.json.return_value = {"code": 19024, "msg": "failure"}
    monkeypatch.setattr("src.publishers.feishu_bot.requests.post", lambda *a, **k: response)
    monkeypatch.setattr("src.utils.retry.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="rejected"):
        FeishuBotPublisher("https://example.com/webhook").publish(_build_article())


@pytest.mark.parametrize("ack", [{}, {"StatusCode": 1}, {"code": "bad"}, []])
def test_invalid_feishu_acknowledgement_is_not_success(monkeypatch, ack):
    response = Mock()
    response.json.return_value = ack
    monkeypatch.setattr("src.publishers.feishu_bot.requests.post", lambda *a, **k: response)
    monkeypatch.setattr("src.utils.retry.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError):
        FeishuBotPublisher("https://example.com/webhook").publish(_build_article())


def test_feishu_network_error_does_not_expose_webhook(monkeypatch):
    import requests
    webhook = "https://example.com/hook/private-token"
    def fail(*args, **kwargs):
        raise requests.ConnectionError(webhook)
    monkeypatch.setattr("src.publishers.feishu_bot.requests.post", fail)
    monkeypatch.setattr("src.utils.retry.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError) as error:
        FeishuBotPublisher(webhook).publish(_build_article())
    assert "private-token" not in str(error.value)
