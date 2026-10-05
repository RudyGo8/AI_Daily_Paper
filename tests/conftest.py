from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def offline_settings(monkeypatch, tmp_path):
    """Tests never read local secrets or persist real delivery state."""
    monkeypatch.setenv("LOAD_DOTENV", "false")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("FEISHU_ENABLED", "false")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "")
    monkeypatch.setenv("HISTORY_BACKEND", "local")
    monkeypatch.setenv("HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("GH_API_TOKEN", "")

