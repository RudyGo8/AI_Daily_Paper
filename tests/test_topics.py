from datetime import datetime, timedelta, timezone

import pytest

from src.fetchers.source_manager import SourceManager, filter_items_by_window
from src.models.schemas import NewsItem
from src.topics import load_topic


def test_legacy_and_multi_topic_source_selection():
    config = {"sources": [{"name": "legacy", "url": "https://old"},
        {"name": "shared", "type": "rss", "topic": ["ai", "agent"], "url": "https://shared"},
        {"name": "GitHub", "type": "github", "topic": "github"}]}
    assert [s.name for s in SourceManager.from_config(config, "ai").sources] == ["legacy", "shared"]
    assert [s.name for s in SourceManager.from_config(config, "agent").sources] == ["shared"]
    assert len(SourceManager.from_config(config, "github").sources) == 1


def test_window_excludes_old_future_and_invalid_dates():
    now = datetime(2026, 10, 4, 2, tzinfo=timezone.utc)
    rows = [NewsItem("A", str(h), "https://a", now - timedelta(hours=h), "")
            for h in [0, 23, 24, 25, -1]]
    rows.append(NewsItem("A", "bad", "https://bad", None, ""))
    assert [r.title for r in filter_items_by_window(rows, now, 24)] == ["0", "23"]


@pytest.mark.parametrize("values", [{"top_k": 0}, {"window_hours": -1}, {"top_k": "bad"}])
def test_invalid_topic_values_raise_clear_error(values):
    with pytest.raises(ValueError):
        load_topic({"topics": {"ai": values}}, "ai")


def test_malformed_url_item_does_not_break_history_or_discard_healthy_items():
    class Fetcher:
        def fetch(self, *args):
            now = datetime.now(timezone.utc)
            return [NewsItem("Test", "bad", "https://host:broken/a", now, ""),
                    NewsItem("Test", "unsafe", "javascript:alert(1)", now, ""),
                    NewsItem("Test", "good", "https://example.com/good", now, "")]
    manager = SourceManager.from_config({"sources": [{"name": "Test", "url": "https://example.com/rss"}]})
    assert [i.title for i in manager.fetch_all(Fetcher())] == ["good"]
