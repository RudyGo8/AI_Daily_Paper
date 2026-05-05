"""文件操作工具函数。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_dir(path: Path) -> None:
    """确保目录存在，不存在则递归创建。"""
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding=encoding)


def write_json(path: Path, data: Any, indent: int = 2) -> None:
    ensure_dir(path.parent)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=indent),
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

