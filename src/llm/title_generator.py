"""Generate a topic title and digest with factual template fallbacks."""

from __future__ import annotations

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
        display_name: str = "AI",
    ) -> None:
        self.llm_client = llm_client
        self.display_name = display_name
        self.title_prompt_template = title_prompt_template or (
            "请生成一个中文飞书简报标题，概括本时段资讯重点。"
        )
        self.digest_prompt_template = digest_prompt_template or (
            "请生成一个不超过120字的中文导读，用于飞书简报。"
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
            return f"{self.display_name}重点速览（{target_date.isoformat()}）"
        return title[:80]

    def generate_digest(self, items: list[NewsItem]) -> str:
        seed = "；".join(item.ai_summary or item.summary for item in items[:4])
        prompt = f"{self.digest_prompt_template}\n素材：{seed}"
        digest = self.llm_client.complete(prompt=prompt, max_tokens=140).strip()
        digest = digest.replace("\n", " ")
        if not digest or self.llm_client.is_fallback_response(digest):
            return f"本时段筛选 {len(items)} 条{self.display_name}动态，请结合原文查看。"
        return digest[:120]
