from __future__ import annotations

import logging
from typing import Any

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
except ImportError:  # pragma: no cover - optional dependency path
    BlockingScheduler = None

LOGGER = logging.getLogger(__name__)


def run_daily_scheduler(
    job_func: Any,
    hour: int = 8,
    minute: int = 30,
    timezone: str = "Asia/Shanghai",
) -> None:
    if BlockingScheduler is None:
        raise RuntimeError("APScheduler is not installed.")

    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(job_func, "cron", hour=hour, minute=minute)
    LOGGER.info("Scheduler started: daily at %02d:%02d (%s)", hour, minute, timezone)
    scheduler.start()

