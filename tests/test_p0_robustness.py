from datetime import datetime, timedelta, timezone

import pytest

from src.fetchers.github_fetcher import GitHubFetcher
from src.fetchers.source_manager import RSSSource, SourceManager, filter_items_by_window
from src.models.schemas import NewsItem
from src.processors.deduplicator import NewsDeduplicator
from src.processors.hot_scorer import HotScorer
from src.topics import TopicConfig


NOW = datetime(2026, 10, 4, 4, tzinfo=timezone.utc)


def news(title="good", **kwargs):
    return NewsItem("Source", title, "https://example.com/" + title, NOW, "summary", **kwargs)


@pytest.mark.parametrize("field,value", [
    ("title", 123), ("title", "   "), ("link", ["https://example.com"]),
    ("summary", None), ("content", {}), ("metadata", None),
    ("merged_titles", [123]),
])
def test_source_skips_bad_item_and_preserves_next_item(field, value, caplog):
    bad, good = news("bad"), news()
    setattr(bad, field, value)

    class Fetcher:
        def fetch(self, *args):
            return [bad, good]

    manager = SourceManager([RSSSource("Source", "https://example.com/feed")])
    assert manager.fetch_all(Fetcher(), topic="ai") == [good]
    assert manager.failed_sources == []
    assert "Skipping malformed item" in caplog.text
    assert good.metadata["source_weights"] == {"Source": 3}


def test_invalid_publication_date_is_skipped_downstream(caplog):
    bad, good = news("bad"), news()
    bad.published_at = "invalid"

    class Fetcher:
        def fetch(self, *args):
            return [bad, good]

    manager = SourceManager([RSSSource("Source", "https://example.com/feed")])
    fetched = manager.fetch_all(Fetcher())
    assert filter_items_by_window(fetched, NOW, 24) == [good]
    assert "invalid publication date" in caplog.text


def repository(name="org/good", **kwargs):
    return {"full_name": name, "html_url": "https://github.com/" + name,
            "pushed_at": NOW.isoformat(), "stargazers_count": 100,
            "forks_count": 5, "description": "MCP tool", "language": "Python",
            "topics": ["mcp"], **kwargs}


@pytest.mark.parametrize("snapshot", [
    {"at": (NOW - timedelta(days=1)).isoformat(), "stars": "bad"},
    {"at": (NOW - timedelta(days=1)).isoformat()},
    {"at": (NOW - timedelta(days=1)).isoformat(), "stars": -1},
    None,
])
def test_bad_snapshot_does_not_discard_repositories(monkeypatch, snapshot):
    fetcher = GitHubFetcher(snapshots={"org/good": snapshot})
    monkeypatch.setattr(fetcher, "_get", lambda *a, **k: {"items": [repository()]})
    source = RSSSource("GitHub", source_type="github",
                       options={"queries": ["topic:mcp"], "enrich_limit": 0})
    items = fetcher.fetch_source(source, "github", now=NOW)
    assert [item.title for item in items] == ["org/good"]
    assert "star_growth" not in items[0].metadata
    assert fetcher.observed["org/good"]["stars"] == 100


@pytest.mark.parametrize("bad_record", [
    None, repository("org/bad", topics="mcp"),
    repository("org/bad", topics=[123]),
    repository("org/bad", language={"name": "Python"}),
    repository("org/bad", description={"text": "MCP"}),
    repository("org/bad", full_name=["org/bad"]),
])
def test_bad_github_record_does_not_hide_later_valid_record(monkeypatch, bad_record):
    fetcher = GitHubFetcher()
    monkeypatch.setattr(fetcher, "_get", lambda *a, **k: {"items": [bad_record, repository()]})
    source = RSSSource("GitHub", source_type="github",
                       options={"queries": ["topic:mcp"], "enrich_limit": 0})
    items = fetcher.fetch_source(source, "github", now=NOW)
    assert [item.title for item in items] == ["org/good"]
    assert "Python" in items[0].content
    assert items[0].metadata["repository_topics"] == ["mcp"]


def test_bad_explicit_repository_does_not_abort_other_repositories(monkeypatch):
    fetcher = GitHubFetcher()
    monkeypatch.setattr(fetcher, "_get", lambda path, **k: None if path.endswith("bad") else repository())
    source = RSSSource("GitHub", source_type="github",
                       options={"repositories": ["org/bad", "org/good"], "enrich_limit": 0})
    assert [item.title for item in fetcher.fetch_source(source, "github", now=NOW)] == ["org/good"]


def test_same_repository_merge_retains_github_signals_with_richer_rss_primary():
    github = NewsItem("GitHub", "org/repo", "https://github.com/org/repo", NOW,
                      "short", source_type="github", source_weight=4,
                      metadata={"stars": 100, "star_growth": 10, "star_growth_days": 1,
                                "release_at": NOW.isoformat(), "source_weights": {"GitHub": 4}})
    rss = NewsItem("Blog", "Project release explained", github.link, NOW,
                   "MCP detailed release report " * 20, source_weight=5,
                   metadata={"custom": "keep", "source_weights": {"Blog": 5}})
    merged, = NewsDeduplicator().deduplicate([github, rss])
    assert merged.title == rss.title
    assert merged.source_type == "github"
    assert merged.metadata["stars"] == 100
    assert merged.metadata["star_growth"] == 10
    assert merged.metadata["release_at"] == NOW.isoformat()
    assert merged.metadata["custom"] == "keep"
    assert merged.metadata["source_weights"] == {"GitHub": 4, "Blog": 5}
    assert set(merged.merged_sources) == {"GitHub", "Blog"}


def test_fractional_snapshot_interval_uses_daily_growth_rate():
    topic = TopicConfig.from_config("github", {})
    hourly = news("hourly", metadata={"stars": 100, "forks": 5,
                                      "star_growth": 10, "star_growth_days": 1 / 24})
    daily = news("daily", metadata={"stars": 100, "forks": 5,
                                    "star_growth": 240, "star_growth_days": 1})
    HotScorer(topic, NOW).score_all([hourly, daily])
    assert hourly.popularity_score == daily.popularity_score
