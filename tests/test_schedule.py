from pathlib import Path

import pytest

from src.config import load_yaml
from src.schedule import resolve_topic


def test_workflow_crons_match_topic_schedule_and_beijing_hours():
    root = Path(__file__).resolve().parents[1]
    config = load_yaml(root / "configs/topics.yaml")
    workflow = load_yaml(root / ".github/workflows/information-hub.yml")
    event = workflow.get("on", workflow.get(True))  # PyYAML YAML 1.1 treats on as boolean.
    crons = {row["cron"] for row in event["schedule"]}
    assert crons == {row["cron_utc"] for row in config["topics"].values()}
    for cron in crons:
        assert resolve_topic(config, cron) in config["topics"]
        minute, hour, *_ = cron.split()
        beijing = int(hour) * 60 + int(minute) + 8 * 60
        assert 8 * 60 <= beijing <= 17 * 60
    with pytest.raises(ValueError):
        resolve_topic(config, "bad")


def test_workflow_serializes_only_same_scheduled_topic():
    root = Path(__file__).resolve().parents[1]
    workflow = load_yaml(root / ".github/workflows/information-hub.yml")
    group = workflow["concurrency"]["group"]
    assert "github.event.schedule" in group
    assert "github.event.inputs.topic" in group
