from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import requests

from src.fetchers.source_manager import RSSSource
from src.fetchers.webpage_fetcher import WebpageFetcher


def response(html, url="https://official.example/list/"):
    result = requests.Response()
    result.status_code = 200
    result.url = url
    result._content = html.encode("utf-8")
    result.encoding = "utf-8"
    return result


def source(**options):
    return RSSSource("Official", "https://official.example/list/", "webpage",
                     ["qingdao_policy"], 5, {
                         "selectors": {"item": "li", "link": "a", "title": ".title",
                                       "date": "time", "summary": ".summary"},
                         **options,
                     })


def row(title="Policy", date="2026-10-04", href="../policy.html", summary="Listing summary"):
    return (f'<li><a href="{href}"><span class="title">{title}</span></a>'
            f'<time>{date}</time><p class="summary">{summary}</p></li>')


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_listing_extracts_real_dates_relative_links_and_topic(get):
    get.return_value = response(row())
    items = WebpageFetcher(timeout=7).fetch_source(source(), "qingdao_policy")
    assert len(items) == 1
    item = items[0]
    assert item.title == "Policy"
    assert item.link == "https://official.example/policy.html"
    assert item.published_at == datetime(2026, 10, 3, 16, tzinfo=timezone.utc)
    assert item.summary == "Listing summary"
    assert (item.topic, item.source_type, item.source_weight) == ("qingdao_policy", "webpage", 5)
    assert get.call_args.kwargs["timeout"] == 7


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_bad_rows_do_not_hide_later_healthy_rows(get):
    get.return_value = response(row(date="not-a-date") + row(title="", date="2026-10-04")
                                  + row(href="javascript:alert(1)") + row("Healthy"))
    items = WebpageFetcher().fetch_source(source(), "qingdao_policy")
    assert [item.title for item in items] == ["Healthy"]


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_url_date_is_opt_in_and_listing_date_takes_precedence(get):
    get.return_value = response(row("Real date", "2026-04-15", "/202605/t20260509_123.shtml")
                                  + row("No date", "", "/202605/t20260509_456.shtml"))
    assert len(WebpageFetcher().fetch_source(source(), "custom")) == 1
    items = WebpageFetcher().fetch_source(source(date_from_url=r"t(\d{8})_"), "custom")
    assert [item.published_at for item in items] == [
        datetime(2026, 4, 14, 16, tzinfo=timezone.utc),
        datetime(2026, 5, 8, 16, tzinfo=timezone.utc),
    ]


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_detail_requests_are_bounded_and_only_fetch_known_dates_in_window(get):
    listing = row("Old", "2026-10-01", "/old") + row("Current", "2026-10-04", "/current")
    listing += row("Second", "2026-10-04", "/second") + row("Unknown", "", "/unknown")
    detail = '<main><p>Eligible graduates receive a housing allowance.</p><p>Apply before October 20.</p></main>'
    get.side_effect = [response(listing), response(detail)]
    items = WebpageFetcher().fetch_source(source(detail_selectors={"content": "main"},
                                               max_detail_items=1), "qingdao_policy",
                                          since=datetime(2026, 10, 3, 12, tzinfo=timezone.utc),
                                          now=datetime(2026, 10, 4, 12, tzinfo=timezone.utc))
    assert [item.title for item in items] == ["Old", "Current", "Second"]
    assert items[0].content == ""
    assert "housing allowance" in items[1].content
    assert "October 20" in items[1].content
    assert items[2].content == ""
    assert [call.args[0] for call in get.call_args_list] == [source().url, "https://official.example/current"]


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_detail_failure_preserves_dated_listing_row(get):
    get.side_effect = [response(row()), requests.Timeout("detail timed out")]
    items = WebpageFetcher().fetch_source(source(detail_selectors={"content": "main"}), "custom")
    assert len(items) == 1
    assert items[0].summary == "Listing summary"


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_detail_date_can_rescue_unknown_listing_date(get):
    get.side_effect = [response(row(date="")), response('<time datetime="2026-10-04T10:30:00+08:00"></time><main>Full policy</main>')]
    items = WebpageFetcher().fetch_source(source(detail_selectors={"content": "main", "date": "time"}), "custom")
    assert items[0].published_at == datetime(2026, 10, 4, 2, 30, tzinfo=timezone.utc)
    assert items[0].content == "Full policy"


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_date_regex_date_format_and_site_timezone_are_explicit(get):
    get.return_value = response(row(date="Published: Oct 2, 2026"))
    items = WebpageFetcher().fetch_source(source(date_regex=r"([A-Z][a-z]{2} \d{1,2}, \d{4})",
                                               date_format="%b %d, %Y", timezone="America/New_York"), "ai")
    assert items[0].published_at == datetime(2026, 10, 2, 4, tzinfo=timezone.utc)


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_missing_site_selectors_are_rejected_before_request(get):
    with pytest.raises(ValueError, match="selectors"):
        WebpageFetcher().fetch_source(RSSSource("Missing", "https://official.example"), "custom")
    get.assert_not_called()


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_listing_http_error_propagates_for_source_manager_isolation(get):
    get.side_effect = requests.HTTPError("Unavailable")
    with pytest.raises(requests.HTTPError):
        WebpageFetcher().fetch_source(source(), "custom")


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_max_items_caps_valid_results_instead_of_malformed_rows(get):
    get.return_value = response(row(date="invalid") + row("First") + row("Second"))
    assert [item.title for item in WebpageFetcher().fetch_source(source(max_items=1), "custom")] == ["First"]


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_html_charset_preserves_chinese_policy_content(get):
    result = response("")
    result._content = ('<meta charset="gb2312">' + row(title="人才补贴")).encode("gb2312")
    result.encoding = "utf-8"  # Some government responses announce the wrong HTTP charset.
    get.return_value = result
    assert WebpageFetcher().fetch_source(source(), "custom")[0].title == "人才补贴"


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_http_links_can_be_explicitly_upgraded_for_official_site(get):
    get.side_effect = [response(row(href="http://official.example/policy")), response('<main>Full policy</main>')]
    item = WebpageFetcher().fetch_source(source(prefer_https=True, detail_selectors={"content": "main"}), "custom")[0]
    assert item.link == "https://official.example/policy"
    assert item.content == "Full policy"


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_detail_page_date_wins_over_url_fallback(get):
    get.side_effect = [response(row(date="", href="/202605/t20260509_123.shtml")),
                       response('<time>2026-04-15</time><main>Full policy</main>')]
    item = WebpageFetcher().fetch_source(source(date_from_url=r"t(\d{8})_",
                                              detail_selectors={"date": "time", "content": "main"}), "custom")[0]
    assert item.published_at == datetime(2026, 4, 14, 16, tzinfo=timezone.utc)


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_window_bounds_control_details_but_preserve_dated_listing_rows(get):
    listing = row("Start", "2026-10-03T12:00:00Z", "/start")
    listing += row("End", "2026-10-04T12:00:00Z", "/end")
    listing += row("Future", "2026-10-04T12:00:01Z", "/future")
    get.side_effect = [response(listing), response('<main>End of window</main>')]
    items = WebpageFetcher().fetch_source(source(detail_selectors={"content": "main"}), "custom",
                                          since=datetime(2026, 10, 3, 12, tzinfo=timezone.utc),
                                          now=datetime(2026, 10, 4, 12, tzinfo=timezone.utc))
    assert [item.title for item in items] == ["Start", "End", "Future"]
    assert [item.content for item in items] == ["", "End of window", ""]
    assert [call.args[0] for call in get.call_args_list] == [source().url, "https://official.example/end"]


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_detail_date_outside_window_is_returned_for_central_filter(get):
    get.side_effect = [response(row()), response('<time>2026-10-01</time><main>Original policy text</main>')]
    items = WebpageFetcher().fetch_source(source(detail_selectors={"content": "main", "date": "time"}), "custom",
                                          since=datetime(2026, 10, 3, 12, tzinfo=timezone.utc),
                                          now=datetime(2026, 10, 4, 12, tzinfo=timezone.utc))
    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 9, 30, 16, tzinfo=timezone.utc)
    assert items[0].content == "Original policy text"


@patch("src.fetchers.webpage_fetcher.requests.get")
def test_policy_pipeline_reports_25_raw_items_and_zero_in_window(get, monkeypatch):
    from src.fetchers.source_manager import SourceManager
    from src.main import run_pipeline

    listing = "".join(row(f"Policy {i}", "2026-09-30", f"/policy-{i}") for i in range(25))
    get.return_value = response(listing)
    policy_source = source(detail_selectors={"content": "main", "date": "time"})
    end = datetime(2026, 10, 5, 6, tzinfo=timezone.utc)
    items = WebpageFetcher().fetch_source(policy_source, "qingdao_policy",
                                          since=datetime(2026, 10, 4, 6, tzinfo=timezone.utc), now=end)
    assert len(items) == 25
    assert all(item.content == "" for item in items)
    monkeypatch.setattr("src.main.SourceManager.from_config", lambda *args, **kwargs: SourceManager([policy_source]))
    monkeypatch.setenv("HISTORY_ENABLED", "false")
    result = run_pipeline(topic="qingdao_policy", dry_run=True, now=end)
    assert result["statistics"]["raw"] == 25
    assert result["statistics"]["within_window"] == 0
    assert result["total_processed_items"] == 0
    assert len(get.call_args_list) == 2  # Only the two listing downloads; no dated old details.
