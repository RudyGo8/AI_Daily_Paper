import json
import sys

import pytest

import src.main as pipeline


def test_all_topics_attempts_remaining_cards_after_failed_delivery(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["main", "--topic", "all"])
    monkeypatch.setenv("FEISHU_ENABLED", "true")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/mock-only")
    monkeypatch.setenv("HISTORY_DIR", str(tmp_path))
    monkeypatch.setattr("src.main.SourceManager.fetch_all", lambda *a, **k: [])

    def deliver(self, payload):
        if "AI / 大模型" in payload["card"]["header"]["title"]["content"]:
            raise RuntimeError("mock delivery failure")
        return {"code": 0}

    monkeypatch.setattr("src.main.FeishuBotPublisher._post_json", deliver)
    with pytest.raises(SystemExit) as error:
        pipeline.main()
    assert error.value.code == 1
    report = json.loads(capsys.readouterr().out)
    assert report["topic"] == "all"
    results = {r["topic"]: r for r in report["reports"]}
    assert set(results) == {"ai", "agent", "github", "python", "news", "qingdao_policy", "industry", "custom"}
    assert results["ai"]["feishu_result"]["sent"] is False
    assert all(r["feishu_result"]["sent"] for key, r in results.items() if key != "ai")
    assert not (tmp_path / "ai.json").exists()
    assert (tmp_path / "custom.json").exists()


def test_all_topics_isolates_unexpected_topic_failure(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main", "--topic", "all", "--dry-run"])
    monkeypatch.setattr("src.main.SourceManager.fetch_all", lambda *a, **k: [])
    original = pipeline.run_pipeline

    def run(*args, **kwargs):
        if kwargs["topic"] == "ai":
            raise RuntimeError("private failure text must not be logged")
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline, "run_pipeline", run)
    with pytest.raises(SystemExit) as error:
        pipeline.main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert len(report["reports"]) == 8
    assert report["reports"][0]["topic"] == "ai"
    assert report["reports"][0]["error_type"] == "RuntimeError"
    assert report["reports"][-1]["topic"] == "custom"
    assert "private failure text" not in captured.out + captured.err
