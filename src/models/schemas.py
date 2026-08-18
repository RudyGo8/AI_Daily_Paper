"""数据模型：定义整个 Pipeline 中流通的核心数据结构。

NewsItem — 单条新闻，贯穿抓取→清洗→去重→分类→摘要全流程。
DailyArticle — 最终生成的日报文章，包含渲染内容和发布所需的所有字段。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class NewsItem:
    """单条 AI 资讯，从 RSS 抓取后逐步填充各字段。"""
    source: str
    title: str
    link: str
    published_at: datetime
    summary: str
    content: str = ""
    category: str = ""
    keywords: list[str] = field(default_factory=list)
    ai_summary: str = ""
    merged_sources: list[str] = field(default_factory=list)
    merged_links: list[str] = field(default_factory=list)
    cluster_size: int = 1

    def __post_init__(self) -> None:
        if not self.merged_sources and self.source:
            self.merged_sources = [self.source]
        if not self.merged_links and self.link:
            self.merged_links = [self.link]


@dataclass
class DailyArticle:
    """最终生成的日报文章，包含所有渲染和发布所需数据。"""
    target_date: date
    title: str
    digest: str
    categories: dict[str, list[NewsItem]]
    total_items: int
