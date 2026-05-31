"""AI daily Feishu card pipeline."""

from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any

from src.config import load_settings, load_yaml
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.source_manager import SourceManager, filter_items_by_date
from src.llm.llm_client import LLMConfig, LLMClient
from src.llm.summarizer import NewsSummarizer
from src.llm.title_generator import TitleGenerator
from src.logger import setup_logger
from src.models.schemas import DailyArticle, NewsItem
from src.processors.classifier import TopicClassifier
from src.processors.cleaner import ContentCleaner
from src.processors.deduplicator import NewsDeduplicator
from src.processors.keyword_extractor import KeywordExtractor
from src.publishers.feishu_bot import FeishuBotPublisher
from src.utils.date_utils import parse_target_date


def _group_by_category(
    items: list[NewsItem],
    categories_config: dict[str, Any],
) -> dict[str, list[NewsItem]]:
    category_map = categories_config.get("categories", categories_config)
    ordered = {name: [] for name in category_map.keys()}

    for item in items:
        label = item.category or "行业事件"
        ordered.setdefault(label, []).append(item)

    return {category: grouped for category, grouped in ordered.items() if grouped}


def _build_empty_article(target_date: date) -> DailyArticle:
    return DailyArticle(
        target_date=target_date,
        title=f"AI 日报（{target_date.isoformat()}）",
        digest="今日暂无符合条件的 AI 资讯。",
        categories={},
        total_items=0,
    )


def run_pipeline(
    target_date: date,
    dry_run: bool = True,
    max_items: int | None = None,
) -> dict[str, Any]:
    settings = load_settings()
    logger = setup_logger(settings.log_level)

    sources_config = load_yaml(settings.sources_file)
    categories_config = load_yaml(settings.categories_file)
    prompt_config = load_yaml(settings.prompt_templates_file).get("prompts", {})

    source_manager = SourceManager.from_config(sources_config)
    fetcher = RSSFetcher(timeout=settings.rss_timeout)
    raw_items = source_manager.fetch_all(fetcher)

    items = filter_items_by_date(raw_items, target_date, settings.timezone)
    cleaner = ContentCleaner()
    items = [cleaner.clean_item(item) for item in items]

    deduplicator = NewsDeduplicator(
        similarity_threshold=settings.dedup_similarity_threshold
    )
    items = deduplicator.deduplicate(items)

    limit = max_items if max_items is not None else settings.max_items_per_day
    if limit > 0:
        items = items[:limit]

    if not items:
        article = _build_empty_article(target_date)
    else:
        classifier = TopicClassifier(categories_config)
        classifier.classify_all(items)

        extractor = KeywordExtractor(max_keywords=6)
        extractor.extract_for_items(items)

        llm_client = LLMClient(
            LLMConfig(
                provider=settings.llm_provider,
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                timeout=settings.llm_timeout,
            )
        )

        summarizer = NewsSummarizer(
            llm_client=llm_client,
            prompt_template=str(prompt_config.get("summarize", "")),
        )
        summarizer.summarize_items(items)

        title_gen = TitleGenerator(
            llm_client=llm_client,
            title_prompt_template=str(prompt_config.get("title", "")),
            digest_prompt_template=str(prompt_config.get("digest", "")),
        )
        article = DailyArticle(
            target_date=target_date,
            title=title_gen.generate_title(target_date=target_date, items=items),
            digest=title_gen.generate_digest(items=items),
            categories=_group_by_category(items, categories_config),
            total_items=len(items),
        )

    feishu_result = {"enabled": False, "sent": False}
    if settings.feishu_enabled:
        feishu_result = FeishuBotPublisher(
            webhook_url=settings.feishu_webhook_url,
            message_title=settings.feishu_message_title,
            dry_run=dry_run,
        ).publish(article)
        feishu_result["enabled"] = True

    report = {
        "target_date": target_date.isoformat(),
        "total_raw_items": len(raw_items),
        "total_processed_items": article.total_items,
        "feishu_result": feishu_result,
    }
    logger.info("Pipeline finished: %s", json.dumps(report, ensure_ascii=False))
    return report


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI daily Feishu card publisher")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the Feishu card preview without sending it",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Maximum number of items to include after dedup",
    )
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    report = run_pipeline(
        target_date=parse_target_date(args.date),
        dry_run=args.dry_run,
        max_items=args.max_items,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
