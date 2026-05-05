"""RSS 抓取模块：从 RSS/Atom feed 下载并解析为 NewsItem 列表。

支持双重解析策略：
  1. feedparser 库（优先，处理各种 RSS/Atom 变体）
  2. xml.etree.ElementTree（纯标准库 fallback，仅解析标准 RSS 2.0）

HTTP 下载同样双轨：requests（优先）→ urllib（fallback）。
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

try:
    import feedparser
except ImportError:  # pragma: no cover - optional dependency path
    feedparser = None

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency path
    requests = None

from src.models.schemas import NewsItem
from src.utils.date_utils import parse_datetime

LOGGER = logging.getLogger(__name__)


class RSSFetcher:
    """RSS 抓取器，负责下载和解析单个 RSS 源。"""
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    def fetch(self, url: str, source_name: str) -> list[NewsItem]:
        raw_text = self._download_text(url)
        if feedparser is not None:
            return self._parse_with_feedparser(raw_text, source_name)
        return self._parse_with_xml(raw_text, source_name)

    def _download_text(self, url: str) -> str:
        if requests is not None:
            response = requests.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": "ai-daily-paper/0.1"},
            )
            response.raise_for_status()
            return response.text

        request = Request(url, headers={"User-Agent": "ai-daily-paper/0.1"})
        with urlopen(request, timeout=self.timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def _parse_with_feedparser(self, payload: str, source_name: str) -> list[NewsItem]:
        parsed = feedparser.parse(payload)
        entries = getattr(parsed, "entries", [])
        items: list[NewsItem] = []
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
            content_candidates = self._safe_get(entry, "content")
            if isinstance(content_candidates, list) and content_candidates:
                first_content = content_candidates[0]
                if isinstance(first_content, dict):
                    content = str(first_content.get("value", ""))
            author = self._safe_get(entry, "author")

            if not title or not link:
                continue

            items.append(
                NewsItem(
                    source=source_name,
                    title=title.strip(),
                    link=link.strip(),
                    published_at=parse_datetime(published),
                    summary=summary.strip(),
                    content=content.strip(),
                    author=author.strip(),
                )
            )
        return items

    def _parse_with_xml(self, payload: str, source_name: str) -> list[NewsItem]:
        items: list[NewsItem] = []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            LOGGER.warning("Failed to parse RSS XML: %s", exc)
            return items

        for node in root.findall(".//item"):
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            description = (node.findtext("description") or "").strip()
            pub_date = (node.findtext("pubDate") or "").strip()
            author = (node.findtext("author") or "").strip()
            if not title or not link:
                continue
            items.append(
                NewsItem(
                    source=source_name,
                    title=title,
                    link=link,
                    published_at=parse_datetime(pub_date),
                    summary=description,
                    content=description,
                    author=author,
                )
            )

        return items

    @staticmethod
    def _safe_get(obj: object, key: str) -> str:
        if isinstance(obj, dict):
            value = obj.get(key, "")
            return str(value or "")
        value = getattr(obj, key, "")
        return str(value or "")
