"""定时调度模块：基于 APScheduler 实现每日定时触发 Pipeline。

默认每天早上 8:30（Asia/Shanghai）执行，使用阻塞式调度器保持进程运行。
"""

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
    """启动阻塞式每日定时任务，在指定时间执行 job_func。"""
    if BlockingScheduler is None:
        raise RuntimeError("APScheduler is not installed.")

    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(job_func, "cron", hour=hour, minute=minute)
    LOGGER.info("Scheduler started: daily at %02d:%02d (%s)", hour, minute, timezone)
    scheduler.start()

