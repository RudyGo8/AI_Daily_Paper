"""Resolve a triggering cron from configuration, never the runner's wall clock."""
from __future__ import annotations

import argparse

from src.config import load_settings, load_yaml


def resolve_topic(config: dict, cron: str) -> str:
    for name, row in config.get("topics", {}).items():
        if row.get("cron_utc") == cron:
            return name
    raise ValueError(f"No topic configured for cron={cron!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cron", required=True)
    args = parser.parse_args()
    try:
        print(resolve_topic(load_yaml(load_settings().topics_file), args.cron))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
