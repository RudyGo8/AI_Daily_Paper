from __future__ import annotations

import re
from typing import Any

from src.models.schemas import NewsItem


class TopicClassifier:
    CATEGORY_PRIORITY = [
        "融资并购",
        "研究进展",
        "产品动态",
        "工具框架",
        "模型发布",
        "行业事件",
    ]

    BUILTIN_RULES: dict[str, list[tuple[str, int]]] = {
        "模型发布": [
            (r"\b(model|weights?|checkpoint|llm|gpt-\w+|reasoning model)\b", 6),
            (r"(基座模型|开源模型|模型发布|模型升级)", 6),
        ],
        "产品动态": [
            (r"\b(chatgpt|copilot|workspace|assistant|feature|launch|product|app)\b", 7),
            (r"(上线|发布|推出|更新|功能|产品)", 5),
            (r"\b(clinician|team|enterprise|workflow)\b", 4),
        ],
        "研究进展": [
            (r"\b(research|paper|benchmark|study|university|scientists?)\b", 7),
            (r"(研究|论文|基准|实验|科学家)", 6),
        ],
        "工具框架": [
            (r"\b(agent|sdk|framework|library|api|tooling|platform|open source)\b", 6),
            (r"(工具|框架|开发|接口|工作流|智能体)", 5),
        ],
        "融资并购": [
            (r"\b(funding|funded|raise|raised|series [a-z]|acquisition|acquire|merger|investment)\b", 9),
            (r"(融资|收购|并购|投资)", 8),
        ],
        "行业事件": [
            (r"\b(policy|regulation|market|partnership|government|safety|compliance)\b", 5),
            (r"(监管|政策|市场|合作|行业)", 5),
        ],
    }

    def __init__(
        self,
        categories_config: dict[str, Any],
        default_category: str = "行业事件",
    ) -> None:
        self.default_category = default_category
        self.category_keywords = categories_config.get("categories", categories_config)

    def classify(self, item: NewsItem) -> str:
        title_text = item.title.lower()
        body_text = f"{item.title} {item.summary}".lower()
        scores = {category: 0 for category in self.CATEGORY_PRIORITY}

        for category, keywords in self.category_keywords.items():
            for keyword in keywords:
                token = str(keyword).lower()
                if token and token in body_text:
                    scores[category] = scores.get(category, 0) + 2
                if token and token in title_text:
                    scores[category] = scores.get(category, 0) + 3

        for category, rules in self.BUILTIN_RULES.items():
            for pattern, weight in rules:
                if re.search(pattern, title_text):
                    scores[category] = scores.get(category, 0) + weight + 2
                elif re.search(pattern, body_text):
                    scores[category] = scores.get(category, 0) + weight

        best_category = self.default_category
        best_score = -1
        for category in self.CATEGORY_PRIORITY:
            score = scores.get(category, 0)
            if score > best_score:
                best_category = category
                best_score = score

        return best_category if best_score > 0 else self.default_category

    def classify_all(self, items: list[NewsItem]) -> list[NewsItem]:
        for item in items:
            item.category = self.classify(item)
        return items
