import base64
import json
from unittest.mock import Mock

import pytest
import requests


EMPTY = {"version": 1, "sent": {}, "stars": {}}


def response(status, body=None):
    result = Mock(status_code=status)
    result.json.return_value = body
    return result


def content(state, sha="file-sha"):
    return {"type": "file", "encoding": "base64", "sha": sha,
            "content": base64.b64encode(json.dumps(state).encode()).decode()}


def setup_store(monkeypatch, replies, topic="ai"):
    from src.storage.github_state import GitHubStateStore
    calls = []
    replies = iter(replies)
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr("src.storage.github_state.requests.request", request)
    return GitHubStateStore("owner/repo", "secret-token", "data", topic), calls


def test_first_run_load_missing_branch_is_read_only(monkeypatch):
    store, calls = setup_store(monkeypatch, [response(404), response(200, {"default_branch": "main"}), response(404)])
    assert store.load() is None
    assert all(call[0] == "GET" for call in calls)
    assert calls[0][1].endswith("/contents/history/ai.json")
    assert calls[0][2]["params"] == {"ref": "data"}


def test_load_missing_file_on_existing_branch_is_read_only(monkeypatch):
    store, calls = setup_store(monkeypatch, [response(404), response(200, {"default_branch": "main"}),
                                           response(200, {"object": {"sha": "data-sha"}})])
    assert store.load() is None
    assert all(call[0] == "GET" for call in calls)


def test_repository_404_is_not_treated_as_empty_history(monkeypatch):
    store, calls = setup_store(monkeypatch, [response(404), response(404)])
    with pytest.raises(RuntimeError, match="HTTP 404"):
        store.load()
    assert all(call[0] == "GET" for call in calls)


def test_load_decodes_and_validates_state(monkeypatch):
    state = {**EMPTY, "stars": {"org/repo": {"stars": 5, "at": "2026-10-04T00:00:00Z"}}}
    store, _ = setup_store(monkeypatch, [response(200, content(state))])
    assert store.load() == state


def test_save_creates_branch_from_default_head_then_topic_file(monkeypatch):
    store, calls = setup_store(monkeypatch, [response(404), response(200, {"default_branch": "main"}),
        response(200, {"object": {"sha": "main-sha"}}), response(201), response(404), response(201)])
    store.save(EMPTY)
    post = next(c for c in calls if c[0] == "POST")
    assert post[2]["json"] == {"ref": "refs/heads/data", "sha": "main-sha"}
    put = next(c for c in calls if c[0] == "PUT")
    assert put[1].endswith("/contents/history/ai.json")
    assert put[2]["json"]["branch"] == "data"
    assert "sha" not in put[2]["json"]
    assert json.loads(base64.b64decode(put[2]["json"]["content"])) == EMPTY
    assert all(c[2]["timeout"] == 15 for c in calls)


def test_two_branch_creators_recheck_after_422(monkeypatch):
    store, calls = setup_store(monkeypatch, [response(404), response(200, {"default_branch": "main"}),
        response(200, {"object": {"sha": "main-sha"}}), response(422),
        response(200, {"object": {"sha": "data-sha"}}), response(404), response(201)])
    store.save(EMPTY)
    assert sum(c[0] == "POST" for c in calls) == 1
    assert calls[-1][0] == "PUT"


def test_sha_conflict_refreshes_and_merges_concurrent_history(monkeypatch):
    ours = {"version": 1, "sent": {"ours": "2026-10-04T02:00:00Z"}, "stars": {}}
    theirs = {"version": 1, "sent": {"theirs": "2026-10-04T01:00:00Z"}, "stars": {}}
    store, calls = setup_store(monkeypatch, [response(200), response(200, {"default_branch": "main"}), response(200, content(EMPTY, "old")),
        response(409), response(200, content(theirs, "new")), response(200)])
    store.save(ours)
    puts = [c for c in calls if c[0] == "PUT"]
    assert [c[2]["json"]["sha"] for c in puts] == ["old", "new"]
    saved = json.loads(base64.b64decode(puts[-1][2]["json"]["content"]))
    assert saved["sent"] == {"ours": "2026-10-04T02:00:00Z", "theirs": "2026-10-04T01:00:00Z"}


def test_content_creation_race_422_refreshes_sha(monkeypatch):
    store, calls = setup_store(monkeypatch, [response(200), response(200, {"default_branch": "main"}), response(404), response(422),
                                           response(200, content(EMPTY, "created")), response(200)])
    store.save(EMPTY)
    assert calls[-1][2]["json"]["sha"] == "created"


def test_conflict_retries_are_bounded(monkeypatch):
    store, calls = setup_store(monkeypatch, [response(200), response(200, {"default_branch": "main"})] + [r for _ in range(3)
        for r in (response(200, content(EMPTY)), response(409))])
    with pytest.raises(RuntimeError, match="conflict"):
        store.save(EMPTY)
    assert sum(c[0] == "PUT" for c in calls) == 3


@pytest.mark.parametrize("state", [{"version": 2, "sent": {}, "stars": {}}, {"version": 1, "sent": [], "stars": {}}])
def test_corrupt_remote_history_cannot_be_overwritten(monkeypatch, state):
    store, calls = setup_store(monkeypatch, [response(200), response(200, {"default_branch": "main"}), response(200, content(state))])
    with pytest.raises(ValueError, match="history"):
        store.save(EMPTY)
    assert all(c[0] == "GET" for c in calls)


def test_topics_write_separate_paths(monkeypatch):
    store, calls = setup_store(monkeypatch, [response(200), response(200, {"default_branch": "main"}), response(404), response(201)], topic="python")
    store.save(EMPTY)
    assert calls[-1][1].endswith("/contents/history/python.json")


@pytest.mark.parametrize("reply", [response(403, {"message": "secret-token private-body"}),
                                  requests.RequestException("secret-token https://private/url body")])
def test_errors_do_not_expose_tokens_urls_or_bodies(monkeypatch, reply):
    store, _ = setup_store(monkeypatch, [reply])
    with pytest.raises(RuntimeError) as caught:
        store.load()
    assert "secret-token" not in str(caught.value)
    assert "https://" not in str(caught.value)
    assert "body" not in str(caught.value)


def test_save_preserves_updates_between_load_and_first_write(monkeypatch):
    loaded = {"version": 1, "sent": {"expired": "2026-09-01T00:00:00Z", "a": "2026-10-04T00:00:00Z"}, "stars": {}}
    concurrent = {**loaded, "sent": {**loaded["sent"], "b": "2026-10-04T01:00:00Z"}}
    desired = {"version": 1, "sent": {"a": "2026-10-04T00:00:00Z", "c": "2026-10-04T02:00:00Z"}, "stars": {}}
    store, calls = setup_store(monkeypatch, [response(200, content(loaded)), response(200),
        response(200, {"default_branch": "main"}), response(200, content(concurrent, "latest")), response(200)])
    state = store.load()
    state["sent"]["b"] = "2026-10-04T01:00:00Z"  # Mutating load's return must not mutate its baseline.
    store.save(desired)
    saved = json.loads(base64.b64decode(calls[-1][2]["json"]["content"]))
    assert saved["sent"] == {"a": "2026-10-04T00:00:00Z", "b": "2026-10-04T01:00:00Z", "c": "2026-10-04T02:00:00Z"}
    assert calls[-1][2]["json"]["sha"] == "latest"


def test_default_branch_cannot_be_used_for_history_writes(monkeypatch):
    store, calls = setup_store(monkeypatch, [response(200), response(200, {"default_branch": "data"})])
    with pytest.raises(ValueError, match="default branch"):
        store.save(EMPTY)
    assert all(c[0] == "GET" for c in calls)


@pytest.mark.parametrize("bad_content", [None, [], {}, b"e30="])
def test_invalid_content_types_raise_sanitized_errors(monkeypatch, bad_content):
    malformed = {**content(EMPTY), "content": bad_content}
    store, _ = setup_store(monkeypatch, [response(200, malformed)])
    with pytest.raises(ValueError, match="history"):
        store.load()


def test_concurrent_newer_star_snapshot_wins_without_restoring_expired_records(monkeypatch):
    loaded = {"version": 1, "sent": {}, "stars": {
        "expired/repo": {"stars": 1, "at": "2026-09-01T00:00:00Z"},
        "org/repo": {"stars": 10, "at": "2026-10-04T00:00:00Z"}}}
    concurrent = {**loaded, "stars": {**loaded["stars"], "org/repo": {"stars": 12, "at": "2026-10-04T02:00:00Z"}}}
    desired = {"version": 1, "sent": {}, "stars": {"org/repo": {"stars": 11, "at": "2026-10-04T01:00:00Z"}}}
    store, calls = setup_store(monkeypatch, [response(200, content(loaded)), response(200),
        response(200, {"default_branch": "main"}), response(200, content(concurrent)), response(200)])
    store.load()
    store.save(desired)
    saved = json.loads(base64.b64decode(calls[-1][2]["json"]["content"]))
    assert saved["stars"] == {"org/repo": {"stars": 12, "at": "2026-10-04T02:00:00Z"}}
