"""内容清洗模块：去除 HTML 标签、解码实体、规范化空白字符。

使用 BeautifulSoup 作为主解析器，当库不可用时回退到正则表达式。
"""

from __future__ import annotations

import html
import re

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - optional dependency path
    BeautifulSoup = None

from src.models.schemas import NewsItem

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


class ContentCleaner:
    """清洗 RSS 条目中的 HTML 标记和转义字符，输出纯文本。"""
    def __init__(self, max_summary_chars: int = 1000) -> None:
        self.max_summary_chars = max_summary_chars

    def clean_text(self, text: str) -> str:
        raw = text or ""
        if BeautifulSoup is not None:
            parsed = BeautifulSoup(raw, "html.parser")
            raw = parsed.get_text(" ", strip=True)
        else:
            raw = TAG_RE.sub(" ", raw)

        raw = html.unescape(raw)
        raw = SPACE_RE.sub(" ", raw).strip()
        return raw

    def clean_item(self, item: NewsItem) -> NewsItem:
        item.title = self.clean_text(item.title)
        item.summary = self.clean_text(item.summary)[: self.max_summary_chars]
        item.content = self.clean_text(item.content)
        return item

