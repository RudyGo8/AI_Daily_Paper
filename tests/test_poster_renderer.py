from __future__ import annotations

from datetime import date
from pathlib import Path

try:
    from PIL import Image, Image as PILImage
except ImportError:  # pragma: no cover - optional dependency path
    Image = None
    PILImage = None

from src.models.schemas import DailyArticle, NewsItem
from src.renderers.poster_renderer import PosterRenderer
from src.utils.date_utils import parse_datetime


def test_poster_renderer_generates_png() -> None:
    if Image is None:
        return

    item = NewsItem(
        source="Example Source",
        title="OpenAI releases a new agentic model",
        link="https://example.com/openai-agent",
        published_at=parse_datetime("2026-04-24T08:00:00+00:00"),
        summary="A new model improves terminal automation and research execution.",
        ai_summary="OpenAI 发布新一代智能体模型，重点提升终端自动化与研究执行能力。",
        category="模型发布",
        keywords=["openai", "agent", "model"],
        merged_sources=["Example Source", "Another Source"],
        merged_links=["https://example.com/openai-agent", "https://another.example.com/openai-agent"],
        cluster_size=2,
    )

    article = DailyArticle(
        target_date=date(2026, 4, 24),
        title="AI Daily Brief",
        digest="今日聚焦模型、产品与工具更新。",
        intro="Intro",
        closing="Closing",
        markdown_content="# test",
        html_content="<p>test</p>",
        categories={"模型发布": [item]},
        total_items=1,
    )

    output_path = Path("poster.png")
    original_save = PILImage.Image.save
    save_calls: list[str] = []

    def fake_save(self, fp, format=None, **kwargs):  # type: ignore[no-untyped-def]
        save_calls.append(str(fp))

    PILImage.Image.save = fake_save
    try:
        generated = PosterRenderer().generate_poster(article, output_path)
    finally:
        PILImage.Image.save = original_save

    assert generated == output_path
    assert save_calls == [str(output_path)]
