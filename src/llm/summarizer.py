from __future__ import annotations

import re

from src.llm.llm_client import LLMClient
from src.models.schemas import NewsItem

SPACE_RE = re.compile(r"\s+")


class NewsSummarizer:
    def __init__(self, llm_client: LLMClient, prompt_template: str = "") -> None:
        self.llm_client = llm_client
        self.prompt_template = prompt_template or (
            "请将以下资讯总结为2-3句中文，突出事实与影响。"
        )

    def summarize_item(self, item: NewsItem) -> str:
        prompt = (
            f"{self.prompt_template}\n\n"
            f"标题：{item.title}\n"
            f"来源：{item.source}\n"
            f"内容：{item.summary or item.content}\n"
            "输出："
        )
        result = self.llm_client.complete(prompt=prompt).strip()
        if not result or self.llm_client.is_fallback_response(result):
            return self._fallback_summary(item)
        return result

    def summarize_items(self, items: list[NewsItem]) -> list[NewsItem]:
        for item in items:
            item.ai_summary = self.summarize_item(item)
        return items

    @staticmethod
    def _fallback_summary(item: NewsItem) -> str:
        base = item.summary or item.content or item.title
        base = SPACE_RE.sub(" ", base).strip().rstrip(".")
        if len(base) > 150:
            base = base[:147].rstrip() + "..."
        return f"{item.source} 发布动态：{item.title}。核心内容：{base}"
