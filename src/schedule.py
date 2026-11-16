"""Resolve the triggering cron to its topic group, never the runner's wall clock."""
from __future__ import annotations

import argparse

from src.config import load_settings, load_yaml


def resolve_topics(config: dict, cron: str) -> list[str]:
    """Return every topic that shares this cron, in configuration order."""
    topics = [name for name, row in config.get("topics", {}).items() if row.get("cron_utc") == cron]
    if not topics:
        raise ValueError(f"No topic configured for cron={cron!r}")
    return topics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cron", required=True)
    args = parser.parse_args()
    try:
        print(",".join(resolve_topics(load_yaml(load_settings().topics_file), args.cron)))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
