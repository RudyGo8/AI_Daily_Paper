"""Validated topic configuration and keyword matching."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any


def keyword_matches(text: str, keywords: list[str]) -> list[str]:
    text = text.casefold()
    return [word for word in keywords if re.search(
        (r"(?<![a-z0-9])" + re.escape(word.casefold()) + r"(?![a-z0-9])")
        if word.isascii() else re.escape(word.casefold()), text)]


@dataclass
class TopicConfig:
    name: str
    display_name: str
    top_k: int = 10
    window_hours: float = 24
    emoji: str = "📰"
    keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    exclude_title_keywords: list[str] = field(default_factory=list)
    important_keywords: list[str] = field(default_factory=list)
    watch_companies: list[str] = field(default_factory=list)
    min_keyword_matches: int = 0
    score_weights: dict[str, float] = field(default_factory=dict)
    summarize_prompt: str = ""

    @classmethod
    def from_config(cls, name: str, config: dict[str, Any]) -> "TopicConfig":
        top_k = int(config.get("top_k", 10))
        hours = float(config.get("window_hours", 24))
        minimum = int(config.get("min_keyword_matches", 0))
        if top_k <= 0 or not math.isfinite(hours) or hours <= 0 or minimum < 0:
            raise ValueError(f"Invalid limits for topic={name}")
        weights = {key: float(value) for key, value in config.get("score_weights", {}).items()}
        if any(not math.isfinite(value) or value < 0 for value in weights.values()):
            raise ValueError(f"Invalid score weights for topic={name}")
        lists = {}
        for key in ("keywords", "exclude_keywords", "exclude_title_keywords", "important_keywords", "watch_companies"):
            value = config.get(key, [])
            if not isinstance(value, list):
                raise ValueError(f"topic={name} {key} must be a list")
            lists[key] = [str(word).strip() for word in value if str(word).strip()]
        return cls(name, str(config.get("display_name", name)), top_k, hours,
                   str(config.get("emoji", "📰")), **lists, min_keyword_matches=minimum,
                   score_weights=weights, summarize_prompt=str(config.get("summarize_prompt", "")))


def load_topic(config: dict[str, Any], name: str) -> TopicConfig:
    topics = config.get("topics", {})
    if name not in topics:
        raise ValueError(f"Unknown topic: {name}. Available: {', '.join(topics)}")
    return TopicConfig.from_config(name, topics[name])
