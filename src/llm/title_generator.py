"""标题生成模块：调用 LLM 生成日报的微信公众号标题和摘要语。

LLM 不可用时，降级为类别统计 + 日期组合的模板标题。
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from src.llm.llm_client import LLMClient
from src.models.schemas import NewsItem


class TitleGenerator:
    """使用 LLM 生成日报标题和摘要。"""
    def __init__(
        self,
        llm_client: LLMClient,
        title_prompt_template: str = "",
        digest_prompt_template: str = "",
    ) -> None:
        self.llm_client = llm_client
        self.title_prompt_template = title_prompt_template or (
            "请生成一个中文公众号标题，概括今日 AI 资讯重点。"
        )
        self.digest_prompt_template = digest_prompt_template or (
            "请生成一个不超过120字的中文摘要，用于公众号 digest。"
        )

    def generate_title(self, target_date: date, items: list[NewsItem]) -> str:
        headline_seed = "；".join(item.title for item in items[:6]) or "AI 行业动态"
        prompt = (
            f"{self.title_prompt_template}\n"
            f"日期：{target_date.isoformat()}\n"
            f"候选信息：{headline_seed}"
        )
        title = self.llm_client.complete(prompt=prompt, max_tokens=80).strip()
        title = title.replace("\n", " ")
        if not title or self.llm_client.is_fallback_response(title):
            return self._fallback_title(target_date, items)
        return title[:80]

    def generate_digest(self, items: list[NewsItem]) -> str:
        seed = "；".join(item.ai_summary or item.summary for item in items[:4])
        prompt = f"{self.digest_prompt_template}\n素材：{seed}"
        digest = self.llm_client.complete(prompt=prompt, max_tokens=140).strip()
        digest = digest.replace("\n", " ")
        if not digest or self.llm_client.is_fallback_response(digest):
            return self._fallback_digest(items)
        return digest[:120]

    @staticmethod
    def _fallback_title(target_date: date, items: list[NewsItem]) -> str:
        categories = Counter(item.category or "行业事件" for item in items)
        top_categories = "、".join(
            category for category, _ in categories.most_common(2)
        ) or "AI 行业"
        return f"AI 资讯日报：{top_categories}重点速览（{target_date.isoformat()}）"

    @staticmethod
    def _fallback_digest(items: list[NewsItem]) -> str:
        highlights = []
        for item in items[:2]:
            snippet = (item.ai_summary or item.summary or item.title).strip()
            highlights.append(snippet[:36].rstrip("，。 ;") + "...")
        digest = f"今日聚焦 {len(items)} 条 AI 动态：" + "；".join(highlights)
        return digest[:120]
