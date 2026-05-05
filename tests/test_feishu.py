from __future__ import annotations

from datetime import date

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
        intro="Intro",
        closing="Closing",
        markdown_content="# test",
        html_content="<p>test</p>",
        categories={"模型发布": [item]},
        total_items=1,
        image_paths=["F:/demo/poster.png"],
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
    assert "F:/demo/poster.png" not in section_text


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
