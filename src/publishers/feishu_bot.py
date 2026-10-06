"""Publish the daily AI brief as a Feishu interactive card."""

from __future__ import annotations

import requests

from src.models.schemas import DailyArticle, NewsItem
from src.utils.retry import retry


class FeishuBotPublisher:
    def __init__(
        self,
        webhook_url: str,
        message_title: str = "AI 日报",
        request_timeout: int = 20,
        dry_run: bool = False,
    ) -> None:
        self.webhook_url = webhook_url.strip()
        self.message_title = message_title.strip() or "AI 日报"
        self.request_timeout = request_timeout
        self.dry_run = dry_run

    def publish(self, article: DailyArticle) -> dict:
        payload = self.build_card_payload(article)

        if self.dry_run or not self.webhook_url:
            return {
                "dry_run": True,
                "sent": False,
                "preview": payload,
            }

        response = self._post_json(payload)
        return {
            "dry_run": False,
            "sent": True,
            "response": response,
        }

    def build_card_payload(self, article: DailyArticle) -> dict:
        header_title = f"{self.message_title} | {article.target_date.isoformat()}"
        if article.topic:
            stamp = article.generated_at.strftime("%Y-%m-%d %H:%M") if article.generated_at else article.target_date.isoformat()
            header_title = f"{article.emoji} {article.display_name} Top {article.total_items} | 截至 {stamp}"
        statistics = article.statistics
        count_note = f"共 {article.total_items} 条重点动态"
        if article.topic:
            period = f"指定日期 {article.target_date.isoformat()}" if article.date_mode else f"过去 {article.window_hours:g} 小时"
            count_note = (f"{period}共抓取 {statistics.get('raw', 0)} 条，"
                          f"时间筛选后 {statistics.get('within_window', 0)} 条，"
                          f"领域匹配后 {statistics.get('topic_matched', 0)} 条，"
                          f"合并去重后 {statistics.get('after_dedup', 0)} 条")
            if statistics.get("history_filtered"):
                count_note += f"，过滤已推送 {statistics['history_filtered']} 条"
            count_note += f"，最终推荐 {article.total_items} 条"
        elements: list[dict] = [
            {
                "tag": "markdown",
                "content": (
                    f"**{self._escape(article.title)}**\n"
                    f"{self._escape(article.digest.strip() or '今日暂无摘要。')}"
                ),
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": count_note,
                    }
                ],
            },
        ]

        sections = self._build_category_sections(article)
        if sections:
            elements.append({"tag": "hr"})
            elements.extend(sections)
        else:
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "今日暂无可推送的重点动态。",
                    },
                }
            )

        return {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True,
                    "enable_forward": True,
                },
                "header": {
                    "template": "blue",
                    "title": {
                        "tag": "plain_text",
                        "content": header_title,
                    },
                },
                "elements": elements,
            },
        }

    def _build_category_sections(self, article: DailyArticle) -> list[dict]:
        sections: list[dict] = []
        categories = article.categories
        if article.topic:
            # Group only the scored Top K, keeping first appearance and rank within each group.
            categories = {}
            for item in article.ranked_items:
                categories.setdefault(item.category or "其他动态", []).append(item)

        for category, items in categories.items():
            if not items:
                continue

            lines = [f"**{self._escape(category)}**"]
            for item in items:
                title = self._shorten(item.title, 72)
                title_link = f"[{self._escape(title)}]({item.link})"
                summary = self._shorten(item.ai_summary or item.summary, 150)
                source_note = self._source_note(item)
                extra = f" 来源：{self._escape(source_note)}" if source_note else ""
                lines.append(f"- {title_link}")
                lines.append(f"  {self._escape(summary)}{extra}")

            sections.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "\n".join(lines),
                    },
                }
            )

        return sections

    @staticmethod
    def _source_note(item: NewsItem) -> str:
        sources = item.merged_sources or [item.source]
        if len(sources) <= 1:
            return sources[0] if sources else ""
        return " / ".join(sources[:3])

    @staticmethod
    def _shorten(text: str, limit: int) -> str:
        clean = " ".join((text or "").split())
        if len(clean) <= limit:
            return clean
        truncated = clean[:limit]
        last_period = max(
            truncated.rfind("。"),
            truncated.rfind("；"),
            truncated.rfind("，"),
        )
        if last_period >= limit // 2:
            return clean[: last_period + 1] + "…"
        return clean[: limit - 1].rstrip() + "…"

    @staticmethod
    def _escape(text: str) -> str:
        return (text or "").replace("\\", "\\\\")

    @retry(max_attempts=3, delay_seconds=1.0)
    def _post_json(self, payload: dict) -> dict:
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=self.request_timeout)
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError("Feishu request failed") from None
        if not isinstance(result, dict) or result.get("code", result.get("StatusCode")) != 0:
            raise RuntimeError("Feishu rejected the card payload")
        return result
