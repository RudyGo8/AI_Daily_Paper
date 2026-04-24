from __future__ import annotations

import re
from datetime import timedelta
from difflib import SequenceMatcher

from src.models.schemas import NewsItem

PUNCT_RE = re.compile(r"[^\w\u4e00-\u9fff]+", flags=re.UNICODE)
TOKEN_RE = re.compile(r"[a-z]+(?:[\.-]?\d+)*|\d+(?:\.\d+)?|[\u4e00-\u9fff]{2,}", flags=re.IGNORECASE)
GENERIC_TOKENS = {
    "the",
    "a",
    "an",
    "and",
    "of",
    "to",
    "for",
    "in",
    "on",
    "with",
    "new",
    "ai",
    "model",
    "models",
    "releases",
    "release",
    "launches",
    "launch",
    "introduces",
    "introducing",
    "unveils",
    "brings",
    "claims",
    "says",
    "tutorial",
    "coding",
    "framework",
    "agents",
    "agent",
    "intelligence",
}

ORGANIZATION_TOKENS = {
    "openai",
    "google",
    "deepmind",
    "microsoft",
    "meta",
    "anthropic",
    "huggingface",
    "nvidia",
    "mend",
    "sierra",
    "fragment",
    "era",
    "decoder",
    "techcrunch",
}


def _normalize_title(title: str) -> str:
    lowered = title.lower().strip()
    return PUNCT_RE.sub("", lowered)


def _normalize_link(link: str) -> str:
    normalized = link.strip().lower().rstrip("/")
    normalized = normalized.replace("https://", "").replace("http://", "")
    return normalized


def _tokenize_text(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw_token in TOKEN_RE.findall(text.lower()):
        token = raw_token.replace(".", "").replace("-", "")
        if len(token) <= 1 or token in GENERIC_TOKENS:
            continue
        tokens.add(token)
    return tokens


def _extract_model_tokens(text: str) -> set[str]:
    model_tokens: set[str] = set()
    for raw_token in TOKEN_RE.findall(text.lower()):
        token = raw_token.replace(".", "").replace("-", "")
        if any(char.isdigit() for char in token) and any(char.isalpha() for char in token):
            model_tokens.add(token)
    return model_tokens


class NewsDeduplicator:
    def __init__(self, similarity_threshold: float = 0.88) -> None:
        self.similarity_threshold = similarity_threshold

    def deduplicate(self, items: list[NewsItem]) -> list[NewsItem]:
        ordered_items = sorted(
            items,
            key=lambda item: (item.published_at, len(item.summary), len(item.content)),
            reverse=True,
        )
        unique: list[NewsItem] = []
        seen_links: set[str] = set()

        for item in ordered_items:
            normalized_link = _normalize_link(item.link)
            if normalized_link and normalized_link in seen_links:
                continue

            merged = False
            for index, saved in enumerate(unique):
                if self._is_duplicate(item, saved):
                    unique[index] = self._merge(saved, item)
                    merged = True
                    break

            if not merged:
                if normalized_link:
                    seen_links.add(normalized_link)
                unique.append(item)

        return unique

    def _is_duplicate(self, left: NewsItem, right: NewsItem) -> bool:
        if _normalize_link(left.link) == _normalize_link(right.link):
            return True

        title_similarity = SequenceMatcher(
            None,
            _normalize_title(left.title),
            _normalize_title(right.title),
        ).ratio()
        if title_similarity >= self.similarity_threshold:
            return True

        if abs(left.published_at - right.published_at) > timedelta(hours=72):
            return False

        left_title_tokens = _tokenize_text(left.title)
        right_title_tokens = _tokenize_text(right.title)
        left_body_tokens = _tokenize_text(f"{left.title} {left.summary}")
        right_body_tokens = _tokenize_text(f"{right.title} {right.summary}")
        left_model_tokens = _extract_model_tokens(left.title)
        right_model_tokens = _extract_model_tokens(right.title)

        title_overlap = self._overlap_ratio(left_title_tokens, right_title_tokens)
        body_overlap = self._overlap_ratio(left_body_tokens, right_body_tokens)
        model_overlap = left_model_tokens & right_model_tokens
        org_overlap = (left_body_tokens & right_body_tokens) & ORGANIZATION_TOKENS

        if title_overlap >= 0.75 or body_overlap >= 0.72:
            return True
        if len(model_overlap) >= 1 and (len(org_overlap) >= 1 or title_overlap >= 0.30):
            return True
        if len(left_title_tokens & right_title_tokens) >= 3 and body_overlap >= 0.45:
            return True

        return False

    @staticmethod
    def _overlap_ratio(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    @staticmethod
    def _merge(left: NewsItem, right: NewsItem) -> NewsItem:
        primary = left
        secondary = right
        primary_score = len(left.summary or left.content) + len(left.merged_sources) * 10
        secondary_score = len(right.summary or right.content) + len(right.merged_sources) * 10
        if secondary_score > primary_score:
            primary, secondary = right, left

        merged_sources = list(dict.fromkeys(primary.merged_sources + secondary.merged_sources))
        merged_links = list(dict.fromkeys(primary.merged_links + secondary.merged_links))
        merged_titles = list(dict.fromkeys(primary.merged_titles + secondary.merged_titles))

        primary.merged_sources = merged_sources
        primary.merged_links = merged_links
        primary.merged_titles = merged_titles
        primary.cluster_size = len(merged_links) or len(merged_titles) or len(merged_sources)

        if not primary.content and secondary.content:
            primary.content = secondary.content
        if len(secondary.summary or "") > len(primary.summary or ""):
            primary.summary = secondary.summary
        if not primary.ai_summary and secondary.ai_summary:
            primary.ai_summary = secondary.ai_summary
        return primary
