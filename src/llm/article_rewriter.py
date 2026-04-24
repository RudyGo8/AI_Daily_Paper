from __future__ import annotations

from collections import Counter
from datetime import date

from src.llm.llm_client import LLMClient
from src.models.schemas import NewsItem


class ArticleRewriter:
    def __init__(
        self,
        llm_client: LLMClient,
        intro_prompt_template: str = "",
        closing_prompt_template: str = "",
    ) -> None:
        self.llm_client = llm_client
        self.intro_prompt_template = intro_prompt_template or (
            "请写一段简洁的中文公众号导语，概览今天 AI 行业重点。"
        )
        self.closing_prompt_template = closing_prompt_template or (
            "请写一段简洁的中文收尾，提醒读者关注明日更新。"
        )

    def rewrite_intro(self, target_date: date, items: list[NewsItem]) -> str:
        highlights = "；".join(item.title for item in items[:5])
        prompt = (
            f"{self.intro_prompt_template}\n"
            f"日期：{target_date.isoformat()}\n"
            f"今日重点：{highlights}"
        )
        result = self.llm_client.complete(prompt=prompt, max_tokens=220).strip()
        if not result or self.llm_client.is_fallback_response(result):
            return self._fallback_intro(target_date, items)
        return result

    def rewrite_closing(self, target_date: date) -> str:
        prompt = (
            f"{self.closing_prompt_template}\n"
            f"日期：{target_date.isoformat()}\n"
            "风格：专业、克制、友好。"
        )
        result = self.llm_client.complete(prompt=prompt, max_tokens=180).strip()
        if not result or self.llm_client.is_fallback_response(result):
            return self._fallback_closing(target_date)
        return result

    @staticmethod
    def _fallback_intro(target_date: date, items: list[NewsItem]) -> str:
        category_counts = Counter(item.category or "行业事件" for item in items)
        top_categories = "、".join(
            category for category, _ in category_counts.most_common(2)
        )
        highlights = "；".join(item.title for item in items[:2])
        return (
            f"{target_date.isoformat()} 的 AI 日报共筛选出 {len(items)} 条重点动态，"
            f"主要涉及 {top_categories or 'AI 行业动态'}。"
            f"今日最值得关注的是：{highlights}。"
        )

    @staticmethod
    def _fallback_closing(target_date: date) -> str:
        return (
            f"以上就是 {target_date.isoformat()} 的 AI 资讯速览。"
            "如果你希望持续跟踪模型、产品和行业变化，欢迎继续关注下一期更新。"
        )
