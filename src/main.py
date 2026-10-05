"""One topic per batch: fetch, merge, score, rank, summarize and publish."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from src.config import load_settings, load_yaml
from src.fetchers.github_fetcher import GitHubFetcher
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.webpage_fetcher import WebpageFetcher
from src.fetchers.source_manager import SourceManager, filter_items_by_date, filter_items_by_window
from src.llm.llm_client import LLMConfig, LLMClient
from src.llm.summarizer import NewsSummarizer
from src.llm.title_generator import TitleGenerator
from src.logger import setup_logger
from src.models.schemas import DailyArticle
from src.processors.classifier import TopicClassifier
from src.processors.cleaner import ContentCleaner
from src.processors.deduplicator import NewsDeduplicator
from src.processors.hot_scorer import HotScorer
from src.processors.keyword_extractor import KeywordExtractor
from src.processors.ranker import rank
from src.publishers.feishu_bot import FeishuBotPublisher
from src.topics import load_topic
from src.storage.history import HistoryStore
from src.storage.github_state import GitHubStateStore
from src.utils.date_utils import get_timezone


def run_pipeline(target_date: date | None = None, dry_run: bool = True,
                 max_items: int | None = None, *, topic: str = "ai", top_k: int | None = None,
                 window_hours: float | None = None, now: datetime | None = None) -> dict[str, Any]:
    settings = load_settings()
    logger = setup_logger(settings.log_level)
    topic_config = load_topic(load_yaml(settings.topics_file), topic)
    if top_k is not None or max_items is not None:
        topic_config.top_k = top_k if top_k is not None else max_items
    if window_hours is not None:
        topic_config.window_hours = window_hours
    if topic_config.top_k <= 0 or not 0 < topic_config.window_hours < float("inf"):
        raise ValueError("top_k and window_hours must be positive finite values")
    generated_at = (now or datetime.now(timezone.utc)).astimezone(get_timezone(settings.timezone))
    end = generated_at.astimezone(timezone.utc)
    if target_date is not None:
        end = datetime.combine(target_date + timedelta(days=1), time.min,
                               get_timezone(settings.timezone)).astimezone(timezone.utc)
        topic_config.window_hours = 24
    report_date = target_date or generated_at.date()
    since = end - timedelta(hours=topic_config.window_hours)
    history = HistoryStore(settings.history_dir / f"{topic}.json", settings.history_retention_days, generated_at)
    remote = None
    history_ready = False
    history_error = ""
    if settings.history_enabled:
        try:
            if settings.history_backend == "github":
                remote = GitHubStateStore(settings.github_repository, settings.github_state_token,
                                          settings.history_branch, topic, settings.github_timeout)
                state = remote.load()
                if state is not None:
                    history.set_state(state)
            elif settings.history_backend == "local":
                history.load()
            else:
                raise ValueError("HISTORY_BACKEND must be local or github")
            history_ready = True
        except (ValueError, RuntimeError, OSError) as exc:
            history_error = type(exc).__name__
            logger.warning("topic=%s history load failed error_type=%s; history writes disabled", topic, history_error)
    source_manager = SourceManager.from_config(load_yaml(settings.sources_file), topic)
    logger.info("topic=%s sources=%s window_start=%s window_end=%s", topic, len(source_manager.sources), since.isoformat(), end.isoformat())
    if not source_manager.sources:
        logger.warning("topic=%s has no configured sources", topic)
    github = GitHubFetcher(settings.github_token, settings.github_timeout, snapshots=history.state["stars"])
    fetch_since = since - timedelta(microseconds=1) if target_date else since
    fetch_end = end - timedelta(microseconds=1) if target_date else end
    raw_items = source_manager.fetch_all(RSSFetcher(settings.rss_timeout), github_fetcher=github,
                                        webpage_fetcher=WebpageFetcher(settings.rss_timeout),
                                        topic=topic, since=fetch_since, now=fetch_end)
    items = (filter_items_by_date(raw_items, target_date, settings.timezone) if target_date else
             filter_items_by_window(raw_items, end, topic_config.window_hours))
    stats = {"raw": len(raw_items), "within_window": len(items)}
    cleaner = ContentCleaner()
    cleaned = []
    for item in items:
        try:
            cleaned.append(cleaner.clean_item(item))
        except (ValueError, TypeError, AttributeError):
            logger.warning("Skipping malformed content source=%s", item.source)
    scorer = HotScorer(topic_config, end)
    # Filter topic relevance before merging so irrelevant content cannot lift a matching event.
    items = [item for item in cleaned if scorer.matches(item)]
    stats["topic_matched"] = len(items)
    items = NewsDeduplicator(settings.dedup_similarity_threshold).deduplicate(items)
    stats["after_dedup"] = len(items)
    stats["history_filtered"] = 0
    if history_ready:
        unseen = [item for item in items if not history.is_seen(item, topic)]
        stats["history_filtered"] = len(items) - len(unseen)
        items = unseen
    categories = load_yaml(settings.categories_file)
    TopicClassifier(categories).classify_all(items)
    KeywordExtractor(max_keywords=6).extract_for_items(items)
    scorer.score_all(items)
    items = rank(items, topic, topic_config.top_k)
    stats["top_k"] = len(items)
    for item in items:
        logger.info("topic=%s selected=%s hot_score=%s reasons=%s", topic, item.title,
                    item.hot_score, ", ".join(item.score_reasons))
    prompts = load_yaml(settings.prompt_templates_file).get("prompts", {})
    llm = LLMClient(LLMConfig(provider=settings.llm_provider, base_url=settings.llm_base_url,
                             api_key=settings.llm_api_key, model=settings.llm_model, timeout=settings.llm_timeout))
    title = f"{topic_config.display_name}重点速览"
    digest = "本时段暂无符合条件的新资讯。"
    if items:
        summary_prompt = f"{prompts.get('summarize', '')}\n领域：{topic_config.display_name}\n{topic_config.summarize_prompt}"
        NewsSummarizer(llm, summary_prompt).summarize_items(items)
        generator = TitleGenerator(llm, str(prompts.get("title", "")) + f"\n领域：{topic_config.display_name}",
                                   str(prompts.get("digest", "")) + f"\n领域：{topic_config.display_name}",
                                   display_name=topic_config.display_name)
        title = generator.generate_title(report_date, items)
        digest = generator.generate_digest(items)
    stats["llm_fallback"] = sum(bool(i.metadata.get("llm_fallback")) for i in items)
    stats["llm_success"] = len(items) - stats["llm_fallback"]
    article = DailyArticle(report_date, title, digest, {}, len(items), topic=topic,
                           display_name=topic_config.display_name, emoji=topic_config.emoji,
                           generated_at=generated_at, window_hours=topic_config.window_hours,
                           ranked_items=items, statistics=stats, date_mode=target_date is not None)
    feishu_result: dict[str, Any] = {"enabled": settings.feishu_enabled, "sent": False}
    if dry_run or settings.feishu_enabled:
        publisher = FeishuBotPublisher(settings.feishu_webhook_url, settings.feishu_message_title,
                                       dry_run=dry_run)
        try:
            feishu_result = publisher.publish(article)
        except (RuntimeError, OSError, ValueError) as exc:
            feishu_result = {"sent": False, "error_type": type(exc).__name__}
            logger.error("topic=%s Feishu delivery failed error_type=%s", topic, type(exc).__name__)
        feishu_result["enabled"] = settings.feishu_enabled
    history_saved = False
    if history_ready and not dry_run and feishu_result.get("sent"):
        try:
            history.mark_sent(items, topic)
            history.state["stars"].update(github.observed)
            if remote is not None:
                remote.save(history.state)
            else:
                history.save()
            history_saved = True
        except (ValueError, RuntimeError, OSError) as exc:
            history_error = type(exc).__name__
            logger.warning("topic=%s history save failed error_type=%s", topic, history_error)
    report = {"topic": topic, "display_name": topic_config.display_name,
              "target_date": report_date.isoformat(), "window_start": since.isoformat(),
              "window_end": end.isoformat(), "date_mode": target_date is not None,
              "sources": len(source_manager.sources), "failed_sources": source_manager.failed_sources,
              "total_raw_items": len(raw_items), "total_processed_items": len(items),
              "statistics": stats, "feishu_result": feishu_result,
              "history_saved": history_saved, "history_error": history_error}
    logger.info("topic=%s raw=%s within_window=%s after_dedup=%s top_k=%s llm_success=%s llm_fallback=%s feishu_sent=%s",
                topic, stats["raw"], stats["within_window"], stats["after_dedup"], stats["top_k"],
                stats["llm_success"], stats["llm_fallback"], feishu_result["sent"])
    return report


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Multi-topic Feishu information hub")
    parser.add_argument("--topic", default="ai", help="Topic key from topics.yaml (default: ai)")
    parser.add_argument("--top-k", type=int, default=None, help="Number of ranked items")
    parser.add_argument("--window-hours", type=float, default=None, help="Rolling window length")
    parser.add_argument("--date", default=None, help="Debug a natural day: YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Build card without sending or saving history")
    parser.add_argument("--max-items", type=int, default=None, help="Legacy alias for --top-k")
    return parser


def main() -> None:
    # Windows terminals/pipes may default to GBK; card JSON includes emoji.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = _build_arg_parser()
    args = parser.parse_args()
    try:
        target_date = date.fromisoformat(args.date) if args.date else None
        report = run_pipeline(target_date, args.dry_run, args.max_items, topic=args.topic,
                              top_k=args.top_k, window_hours=args.window_hours)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["feishu_result"]["enabled"] and not args.dry_run and not report["feishu_result"]["sent"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
