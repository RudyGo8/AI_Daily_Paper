from datetime import datetime, timezone
from unittest.mock import Mock
import pytest

from src.fetchers.github_fetcher import GitHubFetcher
from src.fetchers.source_manager import SourceManager


def test_search_preserves_metadata_and_isolates_bad_records(monkeypatch):
    response = Mock()
    response.json.return_value = {"items": [
        {"full_name": "org/mcp", "html_url": "https://github.com/org/mcp", "description": "MCP tool",
         "pushed_at": "2026-10-04T02:00:00Z", "updated_at": "2026-10-04T03:00:00Z",
         "created_at": "2026-10-01T00:00:00Z", "stargazers_count": 100, "forks_count": 10},
        {"full_name": "bad"}]}
    calls = []
    def get(url, **kwargs):
        calls.append(kwargs)
        return response
    monkeypatch.setattr("src.fetchers.github_fetcher.requests.get", get)
    source = SourceManager.from_config({"sources": [{"name": "GitHub", "type": "github",
        "topic": "github", "queries": ["topic:mcp"], "enrich_limit": 0}]}).sources[0]
    now = datetime(2026, 10, 4, 4, tzinfo=timezone.utc)
    items = GitHubFetcher(token="test").fetch_source(source, "github", now=now)
    assert len(items) == 1
    assert items[0].source_type == "github"
    assert items[0].published_at.hour == 2  # actual code push, not metadata update
    assert items[0].metadata["stars"] == 100
    assert "star_growth" not in items[0].metadata
    assert calls[0]["headers"]["Authorization"] == "Bearer test"


def test_all_api_failures_are_reported_as_a_failed_source(monkeypatch):
    import requests
    manager = SourceManager.from_config({"sources": [{"name": "GitHub", "type": "github",
        "topic": "github", "queries": ["topic:mcp"], "enrich_limit": 0}]})
    def fail(*args, **kwargs):
        raise requests.HTTPError("rate limited")
    monkeypatch.setattr(GitHubFetcher, "_get", fail)
    assert manager.fetch_all(github_fetcher=GitHubFetcher(), topic="github") == []
    assert manager.failed_sources == ["GitHub"]


@pytest.mark.parametrize("body", [None, [], {}, {"items": None}])
def test_malformed_success_body_is_reported_failed(monkeypatch, body):
    manager = SourceManager.from_config({"sources": [{"name": "GitHub", "type": "github",
        "topic": "github", "queries": ["topic:mcp"], "enrich_limit": 0}]})
    monkeypatch.setattr(GitHubFetcher, "_get", lambda *a, **k: body)
    assert manager.fetch_all(github_fetcher=GitHubFetcher(), topic="github") == []
    assert manager.failed_sources == ["GitHub"]
