"""日志配置模块。"""

from __future__ import annotations

import logging


def setup_logger(level: str = "INFO") -> logging.Logger:
    """配置统一的日志格式并返回 ai_daily_paper 根 logger。"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("ai_daily_paper")
