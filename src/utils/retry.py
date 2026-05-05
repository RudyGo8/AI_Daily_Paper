"""重试装饰器：在指定异常发生时自动重试函数调用。"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar


F = TypeVar("F", bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """装饰器工厂：返回一个在异常时自动重试的装饰器。"""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                attempt += 1
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt >= max_attempts:
                        raise
                    logging.getLogger(__name__).warning(
                        "Retrying %s after error: %s (attempt %s/%s)",
                        func.__name__,
                        exc,
                        attempt,
                        max_attempts,
                    )
                    time.sleep(delay_seconds)

        return wrapper  # type: ignore[return-value]

    return decorator

