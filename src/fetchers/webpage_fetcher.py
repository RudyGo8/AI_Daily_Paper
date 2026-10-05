"""Selector-based fetching for explicitly configured official webpages."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Tag

from src.fetchers.source_manager import RSSSource
from src.models.schemas import NewsItem
from src.utils.date_utils import strict_datetime

LOGGER = logging.getLogger(__name__)


class WebpageFetcher:
    """Read selectors and date/detail limits from RSSSource.options.

    selectors requires item/link/title; date/summary are optional. Detail content
    and publication date selectors live in detail_selectors. Undated rows are
    excluded unless a configured detail date or explicit URL regex supplies one.
    Window bounds limit detail requests; the pipeline centrally filters dated rows.
    """

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    def fetch_source(self, source: RSSSource, topic: str, *, since: datetime | None = None,
                     now: datetime | None = None) -> list[NewsItem]:
        options = source.options
        selectors = options.get("selectors", {})
        if not isinstance(selectors, dict) or not all(selectors.get(key) for key in ("item", "link", "title")):
            raise ValueError("Webpage selectors must specify item, link and title")
        if not self._http_url(source.url):
            raise ValueError("Webpage source requires an HTTP/HTTPS URL")
        detail_selectors = options.get("detail_selectors", {})
        if not isinstance(detail_selectors, dict):
            raise ValueError("detail_selectors must be a mapping")
        max_items = max(0, int(options.get("max_items", 50)))
        max_details = min(max_items, max(0, int(options.get("max_detail_items", 10))))
        if max_items == 0:
            return []
        since = strict_datetime(since) if since is not None else None
        now = strict_datetime(now) if now is not None else None
        soup, base_url = self._download(source.url)
        items: list[NewsItem] = []
        detail_count = 0
        for row in soup.select(selectors["item"]):
            if len(items) >= max_items:
                break
            try:
                link_node = self._select(row, selectors["link"])
                title = self._text(self._select(row, selectors["title"]))
                href = str(link_node.get("href", "")).strip() if link_node else ""
                link = urljoin(base_url, href)
                if not title or not href or not self._http_url(link):
                    continue
                if options.get("prefer_https") and link.startswith("http://"):
                    link = "https://" + link[len("http://"):]
                summary = self._text(self._select(row, selectors.get("summary")))
                published = self._date(self._date_text(self._select(row, selectors.get("date"))), options)
                if published is None and options.get("date_from_url"):
                    expression = options["date_from_url"]
                    if expression is True:
                        expression = r"(?:t|/)(\d{8})(?:_|/|\.)"
                    match = re.search(str(expression), urlsplit(link).path)
                    if match:
                        raw = match.group(1) if match.lastindex else match.group(0)
                        published = self._date(raw, options, from_url=True)
                content = ""
                # An undated row only merits a detail request when a configured date can rescue it.
                fetch_detail = (self._in_window(published, since, now) if published is not None
                                else bool(detail_selectors.get("date")))
                if detail_selectors and detail_count < max_details and fetch_detail:
                    detail_count += 1
                    try:
                        detail, _ = self._download(link)
                        if detail_selectors.get("content"):
                            content = "\n".join(self._text(node) for node in detail.select(detail_selectors["content"]))
                        detail_date = self._date(self._date_text(self._select(detail, detail_selectors.get("date"))), options)
                        if detail_date is not None:
                            published = detail_date
                    except Exception as exc:
                        LOGGER.warning("Webpage detail failed source=%s error_type=%s", source.name, type(exc).__name__)
                if published is None:
                    LOGGER.debug("Skipping undated webpage row source=%s", source.name)
                    continue
                items.append(NewsItem(source=source.name, title=title, link=link,
                                      published_at=published, summary=summary, content=content,
                                      source_type="webpage", topic=topic, source_weight=source.source_weight))
            except Exception as exc:
                LOGGER.warning("Skipping malformed webpage row source=%s error_type=%s", source.name, type(exc).__name__)
        return items

    def _download(self, url: str) -> tuple[BeautifulSoup, str]:
        response = requests.get(url, timeout=self.timeout, headers={"User-Agent": "ai-daily-paper/0.1"})
        response.raise_for_status()
        # Let HTML charset declarations guide decoding; several official sites mislabel HTTP encoding.
        return BeautifulSoup(response.content, "html.parser"), response.url or url

    @staticmethod
    def _select(node: Tag | BeautifulSoup, selector: str | None) -> Tag | None:
        if not selector:
            return None
        return node if selector == ":scope" else node.select_one(selector)

    @staticmethod
    def _text(node: Tag | None) -> str:
        if node is None:
            return ""
        for unwanted in node.select("script, style"):
            unwanted.decompose()
        return node.get_text(" ", strip=True)

    @classmethod
    def _date_text(cls, node: Tag | None) -> str:
        if node is None:
            return ""
        return str(node.get("datetime") or node.get("content") or cls._text(node))

    @staticmethod
    def _date(raw: str, options: dict, *, from_url: bool = False) -> datetime | None:
        raw = raw.strip()
        if not raw:
            return None
        if not from_url and options.get("date_regex"):
            match = re.search(options["date_regex"], raw)
            if match is None:
                return None
            raw = match.group(1) if match.lastindex else match.group(0)
        timezone_name = options.get("timezone", "Asia/Shanghai")
        date_format = "%Y%m%d" if from_url and re.fullmatch(r"\d{8}", raw) else options.get("date_format")
        if date_format:
            try:
                return strict_datetime(datetime.strptime(raw, date_format), timezone_name)
            except ValueError:
                return None
        raw = raw.strip("[]() ").replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
        return strict_datetime(raw, timezone_name)

    @staticmethod
    def _http_url(url: str) -> bool:
        parsed = urlsplit(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _in_window(published: datetime, since: datetime | None, now: datetime | None) -> bool:
        return (since is None or published > since) and (now is None or published <= now)
