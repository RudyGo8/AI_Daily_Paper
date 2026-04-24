from __future__ import annotations

from datetime import date

from src.models.schemas import NewsItem
from src.renderers.html_renderer import HtmlRenderer
from src.renderers.markdown_renderer import MarkdownRenderer
from src.utils.date_utils import parse_datetime


def _sample_item() -> NewsItem:
    return NewsItem(
        source="Example Source",
        title="AI Product Update",
        link="https://example.com/news",
        published_at=parse_datetime("2026-04-23T11:00:00+00:00"),
        summary="A product update summary.",
        ai_summary="An AI-focused summary for daily report readers.",
        keywords=["ai", "product", "update"],
        category="product",
    )


def test_markdown_renderer_contains_sections() -> None:
    renderer = MarkdownRenderer()
    item = _sample_item()
    item.merged_sources = ["Example Source", "Second Source"]
    item.merged_links = ["https://example.com/news", "https://second.example.com/news"]
    item.cluster_size = 2
    content = renderer.render(
        target_date=date(2026, 4, 23),
        title="AI Daily Title",
        digest="Digest text",
        intro="Intro text",
        categorized_items={"product": [item]},
        closing="Closing text",
    )
    assert "# AI Daily Title" in content
    assert "## product" in content
    assert item.link in content
    assert "补充来源" in content
    assert "聚合条数" in content


def test_html_renderer_wraps_html() -> None:
    html_renderer = HtmlRenderer()
    html = html_renderer.render("# Title\n\nBody paragraph", "Title")
    assert "<html" in html.lower()
    assert "Body paragraph" in html
    assert html.count("<h1") == 1


def test_html_renderer_accepts_markdown_content_alias() -> None:
    html_renderer = HtmlRenderer()
    html = html_renderer.render(markdown_content="# Alias Title\n\nAlias body", title="Alias")
    assert "Alias body" in html
