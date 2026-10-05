from datetime import datetime, timedelta, timezone

from src.main import run_pipeline
from src.models.schemas import NewsItem


def test_pipeline_ranks_before_llm_and_dry_run_always_previews(monkeypatch, tmp_path):
    now = datetime(2026, 10, 4, 4, tzinfo=timezone.utc)
    rows = [NewsItem("A", "MCP low", "https://a", now, "MCP tool", source_weight=1),
            NewsItem("B", "MCP high", "https://b", now - timedelta(hours=1), "MCP tool", source_weight=5)]
    monkeypatch.setenv("FEISHU_ENABLED", "false")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("HISTORY_DIR", str(tmp_path))
    monkeypatch.setattr("src.main.SourceManager.fetch_all", lambda *a, **k: rows)
    selected = []
    def summarize(self, items):
        selected.extend(i.title for i in items)
        for i in items:
            i.ai_summary = "摘要"
        return items
    monkeypatch.setattr("src.main.NewsSummarizer.summarize_items", summarize)
    monkeypatch.setattr("requests.post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not post")))
    result = run_pipeline(topic="agent", top_k=1, dry_run=True, now=now)
    assert selected == ["MCP high"]
    assert result["total_processed_items"] == 1
    assert result["feishu_result"]["preview"]["msg_type"] == "interactive"
    assert not list(tmp_path.glob("*.json"))


def test_no_sources_produces_clear_empty_preview(monkeypatch, tmp_path):
    from pathlib import Path
    from src.config import load_settings
    settings = load_settings()
    original = __import__("src.main", fromlist=["load_yaml"]).load_yaml
    monkeypatch.setattr("src.main.load_yaml", lambda path: {"sources": []} if path == settings.sources_file else original(path))
    monkeypatch.setenv("LOAD_DOTENV", "false")
    monkeypatch.setenv("HISTORY_DIR", str(tmp_path))
    result = run_pipeline(topic="custom", dry_run=True)
    assert result["sources"] == result["total_processed_items"] == 0
    assert result["feishu_result"]["preview"]["card"]["header"]["title"]["content"].find("Top 0") >= 0


def _delivery_setup(monkeypatch):
    now = datetime(2026, 10, 4, 4, tzinfo=timezone.utc)
    def fetched(*args, **kwargs):
        return [NewsItem("A", "MCP announcement", "https://example.com/event", now, "MCP launch")]
    monkeypatch.setattr("src.main.SourceManager.fetch_all", fetched)
    monkeypatch.setenv("FEISHU_ENABLED", "true")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/mock-only")
    return now


def test_history_saved_only_after_success_and_filters_next_run(monkeypatch):
    now = _delivery_setup(monkeypatch)
    monkeypatch.setattr("src.main.FeishuBotPublisher.publish", lambda *a, **k: {"sent": True})
    first = run_pipeline(topic="agent", dry_run=False, now=now)
    assert first["total_processed_items"] == 1
    assert first["history_saved"] is True
    second = run_pipeline(topic="agent", dry_run=True, now=now)
    assert second["total_processed_items"] == 0
    assert second["statistics"]["history_filtered"] == 1


def test_failed_delivery_preserves_eligible_items_and_does_not_save(monkeypatch):
    now = _delivery_setup(monkeypatch)
    def fail(*args, **kwargs):
        raise RuntimeError("delivery failure")
    monkeypatch.setattr("src.main.FeishuBotPublisher.publish", fail)
    report = run_pipeline(topic="agent", dry_run=False, now=now)
    assert report["feishu_result"]["sent"] is False
    assert report["history_saved"] is False
    preview = run_pipeline(topic="agent", dry_run=True, now=now)
    assert preview["total_processed_items"] == 1


def test_dry_run_reads_remote_history_but_never_writes(monkeypatch):
    now = _delivery_setup(monkeypatch)
    monkeypatch.setenv("HISTORY_BACKEND", "github")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    calls = []
    class Remote:
        def __init__(self, *args, **kwargs):
            pass
        def load(self):
            calls.append("load")
            return {"version": 1, "sent": {}, "stars": {}}
        def save(self, state):
            raise AssertionError("dry-run must not write GitHub state")
    monkeypatch.setattr("src.main.GitHubStateStore", Remote)
    result = run_pipeline(topic="agent", dry_run=True, now=now)
    assert calls == ["load"]
    assert result["feishu_result"]["sent"] is False
    assert result["history_saved"] is False


def test_corrupt_history_is_preserved_even_after_delivery(monkeypatch, tmp_path):
    now = _delivery_setup(monkeypatch)
    folder = tmp_path / "history"
    folder.mkdir()
    path = folder / "agent.json"
    path.write_text("corrupt", encoding="utf-8")
    monkeypatch.setattr("src.main.FeishuBotPublisher.publish", lambda *a, **k: {"sent": True})
    result = run_pipeline(topic="agent", dry_run=False, now=now)
    assert result["history_saved"] is False
    assert result["history_error"]
    assert path.read_text(encoding="utf-8") == "corrupt"


def test_date_mode_fetches_details_at_local_midnight(monkeypatch):
    from datetime import date
    captured = {}
    def fetch(*args, **kwargs):
        captured.update(kwargs)
        return []
    monkeypatch.setattr("src.main.SourceManager.fetch_all", fetch)
    report = run_pipeline(date(2026, 10, 4), topic="qingdao_policy", window_hours=48, dry_run=True)
    midnight = datetime(2026, 10, 3, 16, tzinfo=timezone.utc)
    assert captured["since"] < midnight
    assert captured["now"] < midnight + timedelta(days=1)
    assert report["window_start"] == midnight.isoformat()
    assert "指定日期" in report["feishu_result"]["preview"]["card"]["elements"][1]["elements"][0]["content"]
