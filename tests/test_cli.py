import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest


@pytest.mark.parametrize("topic", ["qingdao_policy", "all"])
def test_cli_utf8_output_even_when_windows_encoding_is_ascii(tmp_path, topic):
    root = Path(__file__).resolve().parents[1]
    configs = tmp_path / "configs"
    configs.mkdir()
    for name in ("topics.yaml", "categories.yaml", "prompt_templates.yaml"):
        shutil.copyfile(root / "configs" / name, configs / name)
    (configs / "sources.yaml").write_text("sources: []\n", encoding="utf-8")
    env = dict(os.environ, CONFIG_DIR=str(configs), LOAD_DOTENV="false", HISTORY_ENABLED="false",
               PYTHONIOENCODING="ascii", FEISHU_ENABLED="false")
    result = subprocess.run([sys.executable, "-B", "-m", "src.main", "--topic", topic, "--dry-run"],
                            cwd=root, env=env, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    report = json.loads(result.stdout.decode("utf-8"))
    assert report["topic"] == topic
    reports = report["reports"] if topic == "all" else [report]
    if topic == "all":
        assert {r["topic"] for r in reports} == {"ai", "agent", "github", "python", "news", "qingdao_policy", "industry", "custom"}
        assert len(reports) == 8
        assert all(r["feishu_result"]["sent"] is False for r in reports)
        assert all(r["history_saved"] is False for r in reports)
    policy = next(r for r in reports if r["topic"] == "qingdao_policy")
    assert "🏙" in policy["feishu_result"]["preview"]["card"]["header"]["title"]["content"]
