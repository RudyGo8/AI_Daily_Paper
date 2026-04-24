from __future__ import annotations

from datetime import date

from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.source_manager import SourceManager, filter_items_by_date


def test_rss_fetcher_parse_items_without_network() -> None:
    sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Model release from ExampleLab</title>
          <link>https://example.com/model-release</link>
          <description>A major model update is announced.</description>
          <pubDate>Thu, 23 Apr 2026 10:00:00 +0000</pubDate>
        </item>
        <item>
          <title>Research update from Example University</title>
          <link>https://example.com/research-update</link>
          <description>New benchmark result was published.</description>
          <pubDate>Thu, 23 Apr 2026 12:00:00 +0000</pubDate>
        </item>
      </channel>
    </rss>
    """

    fetcher = RSSFetcher(timeout=3)
    fetcher._download_text = lambda url: sample_rss  # type: ignore[method-assign]

    items = fetcher.fetch("https://example.com/feed.xml", "Example Source")
    assert len(items) == 2
    assert items[0].source == "Example Source"
    assert "Model release" in items[0].title


def test_source_manager_fetch_and_filter() -> None:
    class DummyFetcher:
        def fetch(self, url: str, source_name: str):
            sample = RSSFetcher()
            sample._download_text = lambda _: f"""<rss><channel><item>
                <title>{source_name}</title>
                <link>{url}</link>
                <description>desc</description>
                <pubDate>Thu, 23 Apr 2026 12:00:00 +0000</pubDate>
            </item></channel></rss>"""  # type: ignore[method-assign]
            return sample.fetch(url, source_name)

    manager = SourceManager.from_config(
        {
            "sources": [
                {"name": "A", "url": "https://a.test/rss"},
                {"name": "B", "url": "https://b.test/rss"},
            ]
        }
    )
    items = manager.fetch_all(DummyFetcher())
    assert len(items) == 2

    filtered = filter_items_by_date(items, date(2026, 4, 23))
    assert len(filtered) == 2

