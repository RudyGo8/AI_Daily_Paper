from __future__ import annotations

from datetime import date

from src.models.schemas import NewsItem


class MarkdownRenderer:
    def render(
        self,
        target_date: date,
        title: str,
        digest: str,
        intro: str,
        categorized_items: dict[str, list[NewsItem]],
        closing: str,
    ) -> str:
        lines: list[str] = []
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"> 日期：{target_date.isoformat()}")
        lines.append(f"> 摘要：{digest}")
        lines.append("")
        lines.append(intro.strip())
        lines.append("")

        for category, items in categorized_items.items():
            if not items:
                continue
            lines.append(f"## {category}")
            lines.append("")
            for idx, item in enumerate(items, start=1):
                summary = item.ai_summary or item.summary
                keywords = "、".join(item.keywords[:5]) if item.keywords else "暂无"
                extra_sources = [source for source in item.merged_sources if source != item.source]
                lines.append(f"### {idx}. {item.title}")
                lines.append(f"- 来源：{item.source}")
                if extra_sources:
                    lines.append(f"- 补充来源：{'、'.join(extra_sources)}")
                lines.append(f"- 时间：{item.published_at.isoformat()}")
                lines.append(f"- 关键词：{keywords}")
                lines.append(f"- 链接：{item.link}")
                if len(item.merged_links) > 1:
                    lines.append(f"- 聚合条数：{item.cluster_size}")
                lines.append("")
                lines.append(summary.strip())
                lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(closing.strip())
        lines.append("")
        return "\n".join(lines)
