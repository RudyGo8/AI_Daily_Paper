from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class NewsItem:
    source: str
    title: str
    link: str
    published_at: datetime
    summary: str
    content: str = ""
    author: str = ""
    category: str = ""
    keywords: list[str] = field(default_factory=list)
    ai_summary: str = ""
    merged_sources: list[str] = field(default_factory=list)
    merged_links: list[str] = field(default_factory=list)
    merged_titles: list[str] = field(default_factory=list)
    cluster_size: int = 1

    def __post_init__(self) -> None:
        if not self.merged_sources and self.source:
            self.merged_sources = [self.source]
        if not self.merged_links and self.link:
            self.merged_links = [self.link]
        if not self.merged_titles and self.title:
            self.merged_titles = [self.title]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["published_at"] = self.published_at.isoformat()
        return payload


@dataclass
class DailyArticle:
    target_date: date
    title: str
    digest: str
    intro: str
    closing: str
    markdown_content: str
    html_content: str
    categories: dict[str, list[NewsItem]]
    total_items: int
    cover_image_path: str | None = None
    image_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_date": self.target_date.isoformat(),
            "title": self.title,
            "digest": self.digest,
            "intro": self.intro,
            "closing": self.closing,
            "total_items": self.total_items,
            "cover_image_path": self.cover_image_path,
            "image_paths": self.image_paths,
            "categories": {
                category: [item.to_dict() for item in items]
                for category, items in self.categories.items()
            },
        }
