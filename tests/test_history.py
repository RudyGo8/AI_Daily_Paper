import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from src.models.schemas import NewsItem


NOW = datetime(2026, 10, 4, 4, tzinfo=timezone.utc)


def history_store(path, **kwargs):
    from src.storage.history import HistoryStore
    return HistoryStore(path, now=NOW, **kwargs)


def item(**kwargs):
    fields = dict(source="A", title="Model 2 Released", link="https://example.com/story",
                  published_at=NOW, summary="The new model supports longer contexts.")
    fields.update(kwargs)
    return NewsItem(**fields)


def test_first_load_and_mark_do_not_create_directories(tmp_path):
    path = tmp_path / "missing" / "history.json"
    store = history_store(path)
    store.load()
    assert store.state == {"version": 1, "sent": {}, "stars": {}}
    assert not store.is_seen(item(), "ai")
    store.mark_sent([item()], "ai")
    assert store.is_seen(item(), "ai")
    assert not path.parent.exists()


def test_save_roundtrip_and_topic_isolation(tmp_path):
    path = tmp_path / "state" / "history.json"
    store = history_store(path)
    store.mark_sent([item()], "ai")
    store.state["stars"] = {"org/repo": {"stars": 123, "at": NOW.isoformat()}}
    store.save()
    restored = history_store(path)
    restored.load()
    assert restored.is_seen(item(), "ai")
    assert not restored.is_seen(item(), "agent")
    assert restored.state["stars"]["org/repo"]["stars"] == 123
    assert list(path.parent.iterdir()) == [path]


def test_content_changes_are_new_versions_but_whitespace_is_not(tmp_path):
    store = history_store(tmp_path / "state.json")
    original = item(content="Supports 64k context")
    store.mark_sent([original], "ai")
    assert store.is_seen(replace(original, summary=" The new model supports\nlonger contexts. "), "ai")
    assert not store.is_seen(replace(original, summary="Now supports local deployment."), "ai")
    assert not store.is_seen(replace(original, content="Supports 128k context"), "ai")
    assert not store.is_seen(replace(original, title="Model 3 Released", merged_titles=["Model 3 Released"]), "ai")


def test_all_merged_urls_and_titles_match_when_primary_changes(tmp_path):
    store = history_store(tmp_path / "state.json")
    original = item(merged_links=["https://example.com/story?utm_source=rss#section", "https://other.com/report/"],
                    merged_titles=["Model 2 Released", "Official Model 2 launch"])
    store.mark_sent([original], "ai")
    moved = item(title="Official Model 2 launch", link="http://OTHER.com/report", merged_links=["http://OTHER.com/report"])
    assert store.is_seen(moved, "ai")
    assert store.is_seen(item(link="https://example.com/story?utm_campaign=daily"), "ai")
    assert not store.is_seen(item(link="https://example.com/story?id=2"), "ai")


def test_article_stays_seen_when_collector_changes_from_rss_to_webpage(tmp_path):
    store = history_store(tmp_path / "state.json")
    store.mark_sent([item()], "ai")
    assert store.is_seen(item(source_type="webpage"), "ai")


@pytest.mark.parametrize("field,value", [("release_tag", "v2"), ("release_at", "2026-10-04T05:00:00Z"),
                                        ("pushed_at", "2026-10-04T05:00:00Z")])
def test_github_release_and_push_versions_can_reappear(tmp_path, field, value):
    store = history_store(tmp_path / "state.json")
    original = item(source_type="github", link="https://github.com/org/repo", metadata={
        "release_tag": "v1", "release_at": "2026-10-03T00:00:00Z", "pushed_at": "2026-10-04T01:00:00Z"})
    store.mark_sent([original], "github")
    changed = replace(original, metadata={**original.metadata, field: value})
    assert not store.is_seen(changed, "github")
    cosmetic = replace(original, summary="description edit", metadata={**original.metadata,
        "stars": 9999, "updated_at": "2026-10-04T06:00:00Z"})
    assert store.is_seen(cosmetic, "github")


def test_github_repository_url_case_is_normalized(tmp_path):
    store = history_store(tmp_path / "state.json")
    store.mark_sent([item(source_type="github", link="https://github.com/Org/Repo")], "github")
    assert store.is_seen(item(source_type="github", link="https://github.com/org/repo"), "github")


def test_retention_expires_sent_versions_and_star_snapshots(tmp_path):
    from src.storage.history import HistoryStore
    path = tmp_path / "state.json"
    old = HistoryStore(path, now=NOW - timedelta(days=31))
    old.mark_sent([item()], "ai")
    old.state["stars"]["org/repo"] = {"stars": 1, "at": (NOW - timedelta(days=31)).isoformat()}
    old.save()
    current = history_store(path)
    current.load()
    assert not current.is_seen(item(), "ai")
    assert current.state["sent"] == {}
    assert current.state["stars"] == {}


def test_retention_boundary_is_inclusive_and_loading_does_not_rewrite(tmp_path):
    from src.storage.history import HistoryStore
    path = tmp_path / "state.json"
    old = HistoryStore(path, now=NOW - timedelta(days=30))
    old.mark_sent([item()], "ai")
    old.save()
    raw = path.read_bytes()
    current = history_store(path)
    current.load()
    assert current.is_seen(item(), "ai")
    assert path.read_bytes() == raw


@pytest.mark.parametrize("raw", ["not-json", '[]', '{"version": 2, "sent": {}, "stars": {}}',
                                '{"version": 1, "sent": {"key": "bad-date"}, "stars": {}}',
                                '{"version": 1, "sent": {}, "stars": {"org/repo": {"stars": -1, "at": "2026-10-04T00:00:00Z"}}}'])
def test_corrupt_history_raises_without_overwriting(tmp_path, raw):
    path = tmp_path / "state.json"
    path.write_text(raw, encoding="utf-8")
    store = history_store(path)
    with pytest.raises(ValueError, match="history"):
        store.load()
    with pytest.raises(ValueError, match="history"):
        store.save()
    assert path.read_text(encoding="utf-8") == raw


def test_set_state_validates_and_does_not_alias_input(tmp_path):
    store = history_store(tmp_path / "state.json")
    state = {"version": 1, "sent": {}, "stars": {}}
    store.set_state(state)
    state["sent"]["bad"] = "invalid"
    assert store.state["sent"] == {}
    with pytest.raises(ValueError):
        store.set_state(state)
    assert store.state["sent"] == {}


def test_failed_atomic_replace_preserves_existing_file_and_cleans_temp(tmp_path, monkeypatch):
    store = history_store(tmp_path / "state.json")
    store.save()
    initial = store.path.read_bytes()
    store.mark_sent([item()], "ai")
    def fail_replace(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr("src.storage.history.os.replace", fail_replace)
    with pytest.raises(OSError):
        store.save()
    assert store.path.read_bytes() == initial
    assert list(tmp_path.iterdir()) == [store.path]
    assert json.loads(initial) == {"version": 1, "sent": {}, "stars": {}}
