from src.config import load_settings


def test_can_disable_dotenv_for_offline_smoke_tests(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("LLM_API_KEY=should-not-load\nFEISHU_ENABLED=true\n", encoding="utf-8")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("FEISHU_ENABLED", raising=False)
    monkeypatch.setenv("LOAD_DOTENV", "false")
    settings = load_settings(tmp_path)
    assert settings.llm_api_key == ""
    assert not settings.feishu_enabled
