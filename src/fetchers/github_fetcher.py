"""Bounded GitHub REST search, release and star-growth collection."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from src.fetchers.source_manager import RSSSource
from src.models.schemas import NewsItem
from src.utils.date_utils import strict_datetime

LOGGER = logging.getLogger(__name__)


class GitHubFetcher:
    def __init__(self, token: str = "", timeout: int = 20,
                 snapshots: dict[str, Any] | None = None) -> None:
        self.timeout = timeout
        self.snapshots = snapshots or {}
        self.observed: dict[str, Any] = {}
        self.headers = {"Accept": "application/vnd.github+json", "User-Agent": "ai-daily-paper/2"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str, **params: Any) -> Any:
        response = requests.get("https://api.github.com/" + path.lstrip("/"),
                                headers=self.headers, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def fetch_source(self, source: RSSSource, topic: str, *, since: datetime | None = None,
                     now: datetime | None = None) -> list[NewsItem]:
        now = now or datetime.now(timezone.utc)
        since = since or now - timedelta(hours=24)
        options = source.options
        repos = options.get("repositories", [])
        records: dict[str, Any] = {}
        successful_requests = 0
        attempted_requests = 0
        for repo in repos:
            attempted_requests += 1
            try:
                record = self._get(f"repos/{repo}")
                if not isinstance(record, dict) or not isinstance(record.get("full_name"), str):
                    raise ValueError("Invalid GitHub repository response")
                records[repo] = record
                successful_requests += 1
            except (requests.RequestException, ValueError):
                LOGGER.warning("GitHub repository unavailable: %s", repo)
        queries = options.get("queries", [])
        if isinstance(queries, dict):
            queries = queries.get(topic, [])
        for query in queries:
            attempted_requests += 1
            try:
                result = self._get("search/repositories", q=f"{query} pushed:>={since.date().isoformat()} archived:false fork:false",
                                   sort="updated", order="desc", per_page=min(100, int(options.get("per_page", 30))))
                if not isinstance(result, dict) or not isinstance(result.get("items"), list):
                    raise ValueError("Invalid GitHub search response")
                successful_requests += 1
                for record in result.get("items", []):
                    if not isinstance(record, dict) or not isinstance(record.get("full_name"), str):
                        LOGGER.warning("Skipping malformed GitHub record")
                        continue
                    if record["full_name"].strip():
                        records[record["full_name"]] = record
            except (requests.RequestException, ValueError, TypeError, AttributeError):
                LOGGER.warning("GitHub search unavailable for topic=%s", topic)
        if attempted_requests and not successful_requests:
            raise RuntimeError("All GitHub collection requests failed")
        items = []
        for record in records.values():
            try:
                item = self._to_item(record, source, topic)
                if item:
                    items.append(item)
            except (ValueError, TypeError, KeyError, OverflowError):
                LOGGER.warning("Skipping malformed GitHub record")
        # Enrich recent candidates instead of privileging only old, high-star repositories.
        items.sort(key=lambda item: item.published_at, reverse=True)
        for item in items[:max(0, int(options.get("enrich_limit", 20)))]:
            self._enrich(item, now)
        for item in items:
            name = item.title
            if "star_growth" not in item.metadata and name in self.snapshots:
                try:
                    previous = self.snapshots[name]
                    if not isinstance(previous, dict):
                        raise TypeError("invalid snapshot")
                    timestamp = strict_datetime(previous.get("at"))
                    previous_stars = int(previous["stars"])
                    if previous_stars < 0:
                        raise ValueError("negative snapshot stars")
                    if timestamp and timestamp < now:
                        item.metadata["star_growth"] = max(0, item.metadata["stars"] - previous_stars)
                        item.metadata["star_growth_days"] = max(1 / 24, (now - timestamp).total_seconds() / 86400)
                        item.metadata["star_growth_method"] = "snapshot_net_change"
                except (ValueError, TypeError, KeyError, OverflowError):
                    LOGGER.warning("Ignoring malformed GitHub star snapshot")
            self.observed[name] = {"stars": item.metadata["stars"], "at": now.isoformat()}
        return items

    @staticmethod
    def _to_item(record: dict[str, Any], source: RSSSource, topic: str) -> NewsItem | None:
        if not isinstance(record, dict):
            raise TypeError("invalid repository record")
        published = strict_datetime(record.get("pushed_at"))
        if not published:
            return None
        if any(not isinstance(record.get(key), str) or not record[key].strip()
               for key in ("html_url", "full_name")):
            raise ValueError("missing repository name/url")
        description = record.get("description")
        language = record.get("language")
        topics = record.get("topics", [])
        if description is not None and not isinstance(description, str):
            raise TypeError("invalid description")
        if language is not None and not isinstance(language, str):
            raise TypeError("invalid language")
        if not isinstance(topics, list) or any(not isinstance(value, str) for value in topics):
            raise TypeError("invalid repository topics")
        description = description or ""
        metadata = {"stars": int(record.get("stargazers_count", 0)),
                    "forks": int(record.get("forks_count", 0)),
                    "created_at": record.get("created_at"), "updated_at": record.get("updated_at"),
                    "pushed_at": record.get("pushed_at"), "language": language,
                    "repository_topics": topics}
        content = f"{description}\n语言：{metadata['language'] or '未标注'}；标签：{' '.join(metadata['repository_topics'])}"
        return NewsItem(source.name, record["full_name"], record["html_url"], published,
                        description, content, topic=topic, source_type="github", metadata=metadata)

    def _enrich(self, item: NewsItem, now: datetime) -> None:
        try:
            release = self._get(f"repos/{item.title}/releases/latest")
            released = strict_datetime(release.get("published_at"))
            if released and released <= now:
                item.metadata.update(release_at=released.isoformat(), release_tag=release.get("tag_name", ""))
                item.published_at = max(item.published_at, released)
                item.content += "\n最新 Release：" + str(release.get("tag_name", "")) + "\n" + str(release.get("body") or "")[:3000]
        except (requests.RequestException, ValueError, AttributeError):
            pass  # No release is normal; HTTP failure must not discard a repository.
        try:
            weeks = self._get(f"repos/{item.title}/stargazers/history", per_page=2)
            if not isinstance(weeks, list):
                return
            cutoff = now - timedelta(days=7)
            growth = 0
            available = False
            for week in weeks:
                start = datetime.fromtimestamp(int(week["week"]), timezone.utc)
                for index, count in enumerate(week.get("days", [])):
                    day = start + timedelta(days=index)
                    if cutoff <= day <= now:
                        growth += max(0, int(count))
                        available = True
            if available:
                item.metadata.update(star_growth=growth, star_growth_days=7,
                                     star_growth_method="calendar_history_approximate")
        except (requests.RequestException, ValueError, TypeError, KeyError, OverflowError):
            pass  # Missing growth remains missing, never fabricate a growth signal.
