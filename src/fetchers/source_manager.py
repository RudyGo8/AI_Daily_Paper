"""Topic-aware source selection and isolated fetcher dispatch."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from src.models.schemas import NewsItem
from src.utils.date_utils import is_same_day, strict_datetime

LOGGER = logging.getLogger(__name__)


@dataclass
class RSSSource:
    name: str
    url: str = ""
    source_type: str = "rss"
    topics: list[str] = field(default_factory=lambda: ["ai"])
    source_weight: float = 3
    options: dict[str, Any] = field(default_factory=dict)


class SourceManager:
    def __init__(self, sources: list[RSSSource]) -> None:
        self.sources = sources
        self.failed_sources: list[str] = []

    @classmethod
    def from_config(cls, config: dict[str, Any], topic: str | None = None) -> "SourceManager":
        sources = []
        for row in config.get("sources", []):
            try:
                if row.get("enabled", True) is False:
                    continue
                name, url = str(row.get("name", "")).strip(), str(row.get("url", "")).strip()
                kind = str(row.get("type", "rss"))
                topics = row.get("topic", ["ai"])
                topics = [topics] if isinstance(topics, str) else list(topics)
                if topic and topic not in topics:
                    continue
                weight = float(row.get("source_weight", 3))
                if not name or (kind in {"rss", "webpage"} and not url) or not math.isfinite(weight) or weight < 0:
                    raise ValueError("missing name/url or invalid weight")
                sources.append(RSSSource(name, url, kind, topics, weight, dict(row)))
            except (ValueError, TypeError, AttributeError) as exc:
                LOGGER.warning("Skipping invalid source configuration: %s", exc)
        return cls(sources)

    def fetch_all(self, fetcher: Any = None, *, github_fetcher: Any = None,
                  webpage_fetcher: Any = None, topic: str = "", since: datetime | None = None,
                  now: datetime | None = None) -> list[NewsItem]:
        all_items = []
        self.failed_sources = []
        for source in self.sources:
            try:
                if source.source_type == "rss":
                    items = fetcher.fetch(source.url, source.name)
                elif source.source_type in {"github", "webpage"}:
                    handler = github_fetcher if source.source_type == "github" else webpage_fetcher
                    if handler is None:
                        raise ValueError(f"Fetcher unavailable: {source.source_type}")
                    items = handler.fetch_source(source, topic, since=since, now=now)
                else:
                    raise ValueError(f"Unsupported source type: {source.source_type}")
                valid = 0
                for item in items:
                    try:
                        if not isinstance(item, NewsItem):
                            raise TypeError("not a NewsItem")
                        if any(not isinstance(getattr(item, field), str)
                               for field in ("title", "link", "summary", "content")):
                            raise TypeError("invalid text field")
                        if not item.title.strip() or not item.link.strip() or not isinstance(item.metadata, dict):
                            raise ValueError("missing title/link or invalid metadata")
                        parsed_link = urlsplit(item.link)
                        if parsed_link.scheme not in {"http", "https"} or not parsed_link.hostname:
                            raise ValueError("invalid article URL")
                        _ = parsed_link.port  # Validate malformed ports before history normalization.
                        for field in ("merged_titles", "merged_links", "merged_sources"):
                            values = getattr(item, field)
                            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                                raise TypeError("invalid merged field")
                        item.topic = topic
                        item.source_type = source.source_type
                        item.source_weight = source.source_weight
                        item.metadata["source_weights"] = {source.name: source.source_weight}
                    except (ValueError, TypeError, AttributeError):
                        LOGGER.warning("Skipping malformed item from source=%s", source.name)
                        continue
                    all_items.append(item)
                    valid += 1
                LOGGER.info("Fetched %s items from source=%s", valid, source.name)
            except Exception as exc:
                self.failed_sources.append(source.name)
                LOGGER.warning("Failed fetching source=%s error_type=%s", source.name, type(exc).__name__)
        return all_items


def filter_items_by_window(items: list[NewsItem], end: datetime, window_hours: float) -> list[NewsItem]:
    start = end - timedelta(hours=window_hours)
    valid = []
    for item in items:
        published = strict_datetime(item.published_at)
        if published is None:
            LOGGER.warning("Skipping item with invalid publication date source=%s", item.source)
            continue
        if start < published <= end:
            item.published_at = published
            valid.append(item)
    return sorted(valid, key=lambda i: i.published_at, reverse=True)


def filter_items_by_date(items: list[NewsItem], target_date: date, timezone_name: str = "UTC") -> list[NewsItem]:
    valid = []
    for item in items:
        published = strict_datetime(item.published_at)
        if published and is_same_day(published, target_date, timezone_name):
            item.published_at = published
            valid.append(item)
    return sorted(valid, key=lambda i: i.published_at, reverse=True)
