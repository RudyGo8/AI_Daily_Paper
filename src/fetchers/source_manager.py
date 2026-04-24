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
    name: str
    url: str


class SourceManager:
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
