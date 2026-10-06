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


def test_topic_card_links_titles_under_categories_and_hides_scores():
    article = _build_article()
    article.topic, article.display_name, article.emoji = "agent", "Agent / Vibe Coding", "🧠"
    first = article.categories["模型发布"][0]
    first.hot_score = 999
    article.ranked_items = [first]
    payload = FeishuBotPublisher("", dry_run=True).build_card_payload(article)
    assert "Top 1" in payload["card"]["header"]["title"]["content"]
    assert "截至" in payload["card"]["header"]["title"]["content"]
    text = payload["card"]["elements"][-1]["text"]["content"]
    assert "**模型发布**" in text
    assert "- [OpenAI releases new agentic model](https://example.com/openai-agent)" in text
    assert "OpenAI 发布新的智能体模型，重点提升自主编码和研究能力。 来源：OpenAI News / TechCrunch AI" in text
    assert "阅读全文" not in text
    assert "hot_score" not in str(payload)
    assert "999" not in str(payload)


def test_topic_card_groups_only_selected_items_in_rank_order():
    from dataclasses import replace

    article = _build_article()
    first = article.categories["模型发布"][0]
    tool = replace(first, title="MCP toolkit", link="https://example.com/tool", category="工具框架")
    second = replace(first, title="Another model", link="https://example.com/model")
    unselected = replace(first, title="Unselected story", link="https://example.com/unselected")
    article.topic = "ai"
    article.ranked_items = [first, tool, second]
    article.categories = {"模型发布": [unselected]}
    article.total_items = 3

    payload = FeishuBotPublisher("", dry_run=True).build_card_payload(article)
    sections = [element["text"]["content"] for element in payload["card"]["elements"] if element.get("tag") == "div"]
    assert len(sections) == 2
    assert sections[0].startswith("**模型发布**\n")
    assert sections[0].index("OpenAI releases") < sections[0].index("Another model")
    assert sections[1].startswith("**工具框架**\n")
    assert "MCP toolkit" in sections[1]
    assert "Unselected story" not in str(payload)


def test_fallback_card_keeps_original_title_link():
    article = _build_article()
    item = article.categories["模型发布"][0]
    item.ai_summary = "【模型摘要未生成】原文事实摘要。"
    payload = FeishuBotPublisher("", dry_run=True).build_card_payload(article)
    text = payload["card"]["elements"][-1]["text"]["content"]
    assert "[OpenAI releases new agentic model](https://example.com/openai-agent)" in text
    assert "【模型摘要未生成】" in text


def test_topic_card_does_not_render_stale_categories_when_selection_is_empty():
    article = _build_article()
    article.topic = "ai"
    article.ranked_items = []
    article.total_items = 0
    payload = FeishuBotPublisher("", dry_run=True).build_card_payload(article)
    assert "今日暂无可推送的重点动态。" in str(payload)
    assert "openai-agent" not in str(payload)


def test_topic_card_distinguishes_topic_filter_from_deduplication():
    article = _build_article()
    article.topic, article.display_name, article.emoji = "python", "Python / 开源技术", "🐍"
    article.ranked_items = article.categories["模型发布"]
    article.statistics = {"raw": 335, "within_window": 85, "topic_matched": 64,
                          "after_dedup": 60, "history_filtered": 2}
    payload = FeishuBotPublisher("", dry_run=True).build_card_payload(article)
    note = payload["card"]["elements"][1]["elements"][0]["content"]
    assert "时间筛选后 85 条，领域匹配后 64 条，合并去重后 60 条" in note
    assert "过滤已推送 2 条，最终推荐 1 条" in note


@pytest.mark.parametrize("one_category", [True, False])
def test_topic_card_displays_every_selected_item(one_category):
    from dataclasses import replace

    article = _build_article()
    first = article.categories["模型发布"][0]
    article.topic = "ai"
    article.ranked_items = [replace(first, title=f"Selected item {index}",
                                    link=f"https://example.com/item/{index}",
                                    category="模型发布" if one_category else f"Category {index}")
                            for index in range(100)]
    article.total_items = 100
    payload = FeishuBotPublisher("", dry_run=True).build_card_payload(article)
    sections = [e["text"]["content"] for e in payload["card"]["elements"] if e.get("tag") == "div"]
    assert sum(section.count("https://example.com/item/") for section in sections) == 100
    assert "[Selected item 99](https://example.com/item/99)" in sections[-1]


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
