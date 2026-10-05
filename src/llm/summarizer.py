"""AI 摘要模块：调用 LLM 为每条新闻生成 2-3 句中文摘要。

当 LLM 不可用时，降级为模板拼接（来源 + 标题 + 原文摘要）。
"""

from __future__ import annotations

from src.llm.llm_client import LLMClient
from src.models.schemas import NewsItem


class NewsSummarizer:
    """调用 LLM 对新闻条目进行摘要。"""
    def __init__(self, llm_client: LLMClient, prompt_template: str = "") -> None:
        self.llm_client = llm_client
        self.prompt_template = prompt_template or (
            "请将以下资讯总结为约150字的中文摘要，突出事实与影响。"
        )

    def summarize_item(self, item: NewsItem) -> str:
        prompt = (
            f"{self.prompt_template}\n\n"
            f"标题：{item.title}\n来源：{item.source}\n"
            f"内容：{(item.content or item.summary)[:4000]}\n"
            "输出："
        )
        result = self.llm_client.complete(prompt=prompt).strip()
        if not result or self.llm_client.is_fallback_response(result):
            item.metadata["llm_fallback"] = True
            return self._fallback_summary(item)
        item.metadata["llm_fallback"] = False
        return result

    def summarize_items(self, items: list[NewsItem]) -> list[NewsItem]:
        for item in items:
            item.ai_summary = self.summarize_item(item)
        return items

    @staticmethod
    def _fallback_summary(item: NewsItem) -> str:
        material = " ".join((item.summary or item.content or item.title).split())
        return f"【模型摘要未生成】{item.title}。{material[:100]}（请以原文为准）"
