"""\u5173\u952e\u8bcd\u63d0\u53d6\u6a21\u5757\uff1a\u57fa\u4e8e\u8bcd\u9891\u7edf\u8ba1\u4ece\u65b0\u95fb\u6807\u9898\u548c\u6458\u8981\u4e2d\u63d0\u53d6\u5173\u952e\u8bcd\u3002"""

from __future__ import annotations

import re
from collections import Counter

from src.models.schemas import NewsItem

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-\+]{1,}|[\u4e00-\u9fff]{2,}")


class KeywordExtractor:
    """\u57fa\u4e8e\u8bcd\u9891\u7684\u7b80\u5355\u5173\u952e\u8bcd\u63d0\u53d6\u5668\uff0c\u6309\u51fa\u73b0\u9891\u6b21\u6392\u5e8f\u8fd4\u56de top-N\u3002"""
    def __init__(self, max_keywords: int = 6, stopwords: set[str] | None = None) -> None:
        self.max_keywords = max_keywords
        self.stopwords = stopwords or {
            "with",
            "from",
            "that",
            "this",
            "will",
            "have",
            "about",
            "today",
            "daily",
            "news",
            "the",
            "and",
            "for",
            "了",
            "以及",
            "我们",
            "你们",
            "这个",
            "那个",
        }

    def extract(self, text: str) -> list[str]:
        counts = Counter()
        for token in TOKEN_RE.findall((text or "").lower()):
            if token in self.stopwords:
                continue
            counts[token] += 1
        return [word for word, _ in counts.most_common(self.max_keywords)]

    def extract_for_items(self, items: list[NewsItem]) -> list[NewsItem]:
        for item in items:
            item.keywords = self.extract(f"{item.title} {item.summary}")
        return items

