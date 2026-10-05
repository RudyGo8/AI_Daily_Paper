"""RSS 抓取模块：从 RSS/Atom feed 下载并解析为 NewsItem 列表。

HTTP 下载使用 requests，解析使用 feedparser（均为硬依赖）。
"""

from __future__ import annotations

import feedparser
import requests
import logging

from src.models.schemas import NewsItem
from src.utils.date_utils import strict_datetime


class RSSFetcher:
    """RSS 抓取器，负责下载和解析单个 RSS 源。"""
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    def fetch(self, url: str, source_name: str) -> list[NewsItem]:
        return self._parse_with_feedparser(self._download_text(url), source_name)

    def _download_text(self, url: str) -> str:
        response = requests.get(
            url,
            timeout=self.timeout,
            headers={"User-Agent": "ai-daily-paper/0.1"},
        )
        response.raise_for_status()
        return response.text

    def _parse_with_feedparser(self, payload: str, source_name: str) -> list[NewsItem]:
        parsed = feedparser.parse(payload)
        entries = getattr(parsed, "entries", [])
        if not entries and not getattr(parsed, "version", ""):
            raise ValueError("Response is not a valid RSS/Atom feed")
        items: list[NewsItem] = []
        invalid_dates = 0
        for entry in entries:
            title = self._safe_get(entry, "title")
            link = self._safe_get(entry, "link")
            summary = self._safe_get(entry, "summary") or self._safe_get(
                entry,
                "description",
            )
            published = (
                self._safe_get(entry, "published")
                or self._safe_get(entry, "updated")
                or self._safe_get(entry, "pubDate")
            )
            content = ""
            content_candidates = entry.get("content", [])
            if isinstance(content_candidates, list) and content_candidates:
                first_content = content_candidates[0]
                if isinstance(first_content, dict):
                    content = str(first_content.get("value", ""))
            if not title or not link:
                continue
            timestamp = strict_datetime(published)
            if timestamp is None:
                invalid_dates += 1
                continue

            items.append(
                NewsItem(
                    source=source_name,
                    title=title.strip(),
                    link=link.strip(),
                    published_at=timestamp,
                    summary=summary.strip(),
                    content=content.strip(),
                )
            )
        if invalid_dates:
            logging.getLogger(__name__).warning("Skipped %s RSS items without valid dates source=%s", invalid_dates, source_name)
        return items

    @staticmethod
    def _safe_get(obj: object, key: str) -> str:
        if isinstance(obj, dict):
            value = obj.get(key, "")
            return str(value or "")
        value = getattr(obj, key, "")
        return str(value or "")
