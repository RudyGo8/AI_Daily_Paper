from __future__ import annotations

import re
from collections import Counter

from src.models.schemas import NewsItem

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-\+]{1,}|[\u4e00-\u9fff]{2,}")


class KeywordExtractor:
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

