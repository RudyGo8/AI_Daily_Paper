from __future__ import annotations

import json
from urllib.request import Request, urlopen

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency path
    requests = None

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
                        "content": f"共 {article.total_items} 条重点动态",
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

    def _build_category_sections(
        self,
        article: DailyArticle,
        max_categories: int = 4,
        max_items_per_category: int = 2,
    ) -> list[dict]:
        sections: list[dict] = []
        added_categories = 0

        for category, items in article.categories.items():
            if not items:
                continue
            if added_categories >= max_categories:
                break

            lines = [f"**{self._escape(category)}**"]
            for item in items[:max_items_per_category]:
                title = self._shorten(item.title, 72)
                title_link = f"[{self._escape(title)}]({item.link})"
                summary = self._shorten(item.ai_summary or item.summary, 110)
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
            added_categories += 1

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
        return clean[: limit - 1].rstrip() + "…"

    @staticmethod
    def _escape(text: str) -> str:
        return (text or "").replace("\\", "\\\\")

    @retry(max_attempts=3, delay_seconds=1.0)
    def _post_json(self, payload: dict) -> dict:
        if requests is not None:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            return response.json()

        request = Request(
            self.webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.request_timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
