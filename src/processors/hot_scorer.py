"""Explainable rules for topic importance; no LLM or network calls."""
from __future__ import annotations

import math
from datetime import datetime

from src.models.schemas import NewsItem
from src.topics import TopicConfig, keyword_matches
from src.utils.date_utils import strict_datetime


class HotScorer:
    def __init__(self, topic: TopicConfig, now: datetime) -> None:
        self.topic = topic
        self.now = now

    def _text(self, item: NewsItem) -> str:
        return " ".join([item.title, *item.merged_titles, item.summary, item.content])

    def matches(self, item: NewsItem) -> bool:
        text = self._text(item)
        if keyword_matches(item.title, self.topic.exclude_title_keywords):
            return False
        if keyword_matches(text, self.topic.exclude_keywords):
            return False
        return len(keyword_matches(text, self.topic.keywords + self.topic.watch_companies)) >= self.topic.min_keyword_matches

    def score_all(self, items: list[NewsItem]) -> list[NewsItem]:
        for item in items:
            text = self._text(item)
            hours = max(0, (self.now - item.published_at).total_seconds() / 3600)
            freshness = 4 if hours <= 3 else 3 if hours <= 6 else 2 if hours <= 12 else 1
            matches = keyword_matches(text, self.topic.keywords + self.topic.watch_companies)
            significant = keyword_matches(text, self.topic.important_keywords)
            popularity = min(3, len(significant))
            if item.source_type == "github" or "stars" in item.metadata:
                popularity = self._github_popularity(item)
            raw = {
                "source": item.source_weight,
                "freshness": freshness,
                "popularity": popularity,
                "cross_source": min(3, max(0, len(set(item.merged_sources)) - 1)),
                "topic": min(5, len(matches)),
            }
            item.score_reasons = []
            for component, value in raw.items():
                score = round(value * self.topic.score_weights.get(component, 1), 3)
                setattr(item, component + "_score", score)
                item.score_reasons.append(f"{component}={score:g}")
            item.hot_score = round(sum(getattr(item, c + "_score") for c in raw), 3)
        return items

    def _github_popularity(self, item: NewsItem) -> float:
        data = item.metadata
        stars, forks = max(0, float(data.get("stars", 0))), max(0, float(data.get("forks", 0)))
        score = min(2, math.log10(1 + stars) * .5) + min(1, math.log10(1 + forks) * .3)
        if "star_growth" in data:
            daily = max(0, float(data["star_growth"])) / max(1 / 24, float(data.get("star_growth_days", 1)))
            score += min(6, math.log10(1 + daily) * 2.5)
        for key, bonus, days in [("created_at", 1, 30), ("release_at", 2, 7)]:
            timestamp = strict_datetime(data.get(key))
            if timestamp and 0 <= (self.now - timestamp).total_seconds() <= days * 86400:
                score += bonus
        return score
