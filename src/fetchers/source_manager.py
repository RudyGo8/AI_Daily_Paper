"""RSS 源管理模块：管理和遍历所有 RSS 数据源。

SourceManager 从 sources.yaml 加载源列表，批量调用 RSSFetcher 抓取。
filter_items_by_date 按目标日期筛选抓取结果，确保只处理指定日期的新闻。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.models.schemas import NewsItem
from src.utils.date_utils import is_same_day

LOGGER = logging.getLogger(__name__)


@dataclass
class RSSSource:
    """单个 RSS 源：名称 + 订阅地址。"""
    name: str
    url: str


class SourceManager:
    """管理 RSS 源列表，批量抓取并汇总。"""
    def __init__(self, sources: list[RSSSource]) -> None:
        self.sources = sources

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "SourceManager":
        raw_sources = config.get("sources", [])
        sources: list[RSSSource] = []
        for source in raw_sources:
            name = str(source.get("name", "")).strip()
            url = str(source.get("url", "")).strip()
            if not name or not url:
                continue
            sources.append(RSSSource(name=name, url=url))
        return cls(sources=sources)

    def fetch_all(self, fetcher: Any) -> list[NewsItem]:
        all_items: list[NewsItem] = []
        for source in self.sources:
            try:
                items = fetcher.fetch(source.url, source.name)
                LOGGER.info(
                    "Fetched %s items from source=%s",
                    len(items),
                    source.name,
                )
                all_items.extend(items)
            except Exception as exc:
                LOGGER.exception("Failed fetching source=%s error=%s", source.name, exc)
        return all_items


def filter_items_by_date(
    items: list[NewsItem],
    target_date: date,
    timezone_name: str = "UTC",
) -> list[NewsItem]:
    filtered = [
        item
        for item in items
        if is_same_day(item.published_at, target_date, timezone_name)
    ]
    return sorted(filtered, key=lambda item: item.published_at, reverse=True)
