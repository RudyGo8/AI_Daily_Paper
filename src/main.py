"""
AI 日报自动生成系统 — 主 Pipeline 入口。

流程概览：
  RSS 源获取 → 日期过滤 → 内容清洗 → 去重合并 → 分类 → 关键词提取
  → AI 摘要 → AI 写标题/导语/收尾 → Markdown/HTML 渲染 → 飞书推送

使用方式:
  python -m src.main                  # 处理当天资讯
  python -m src.main --date 2026-05-04  # 处理指定日期
  python -m src.main --dry-run        # 调试模式（不真正推送飞书）
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from src.config import load_settings, load_yaml
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.source_manager import SourceManager, filter_items_by_date
from src.llm.article_rewriter import ArticleRewriter
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
from src.renderers.html_renderer import HtmlRenderer
from src.renderers.image_renderer import ImageRenderer
from src.renderers.markdown_renderer import MarkdownRenderer
from src.renderers.poster_renderer import PosterRenderer
from src.utils.date_utils import parse_target_date
from src.utils.file_utils import ensure_dir, write_json, write_text


def _group_by_category(
    items: list[NewsItem],
    categories_config: dict[str, Any],
) -> dict[str, list[NewsItem]]:
    """将已分类的新闻条目按类别分组，保持 categories.yaml 中定义的顺序。"""
    category_map = categories_config.get("categories", categories_config)
    ordered = {name: [] for name in category_map.keys()}

    for item in items:
        label = item.category or "行业事件"
        ordered.setdefault(label, []).append(item)

    # Put unknown categories at the end while preserving known order.
    return {k: v for k, v in ordered.items() if v}


def _build_empty_article(target_date: date) -> DailyArticle:
    """当今日无符合条件的新闻时，生成一篇空日报占位文章。"""
    markdown_content = (
        f"# AI 资讯日报（{target_date.isoformat()}）\n\n"
        "今日暂无符合条件的 AI 资讯，建议检查 RSS 源可用性或放宽筛选条件。\n"
    )
    html_content = (
        "<html><body><h1>AI 资讯日报</h1><p>今日暂无符合条件的 AI 资讯。</p></body></html>"
    )
    return DailyArticle(
        target_date=target_date,
        title=f"AI 资讯日报（{target_date.isoformat()}）",
        digest="今日暂无符合条件的 AI 资讯。",
        intro="今日暂无符合条件的资讯，我们会持续跟踪并在明天更新。",
        closing="欢迎持续关注，我们会在下一期带来最新 AI 动态。",
        markdown_content=markdown_content,
        html_content=html_content,
        categories={},
        total_items=0,
    )


def run_pipeline(
    target_date: date,
    dry_run: bool = True,
    max_items: int | None = None,
) -> dict[str, Any]:
    """执行完整的日报生成流水线，返回处理报告。

    各阶段按序执行：抓取 → 清洗 → 去重 → 分类 → AI 处理 → 渲染 → 发布。
    """
    settings = load_settings()
    logger = setup_logger(settings.log_level)

    for directory in (
        settings.data_raw_dir,
        settings.data_processed_dir,
        settings.data_output_dir,
        settings.docs_articles_dir,
        settings.docs_images_dir,
    ):
        ensure_dir(directory)

    sources_config = load_yaml(settings.sources_file)
    categories_config = load_yaml(settings.categories_file)
    prompt_config = load_yaml(settings.prompt_templates_file).get("prompts", {})

    source_manager = SourceManager.from_config(sources_config)
    fetcher = RSSFetcher(timeout=settings.rss_timeout)
    raw_items = source_manager.fetch_all(fetcher)

    raw_output = settings.data_raw_dir / f"raw_{target_date.isoformat()}.json"
    write_json(raw_output, [item.to_dict() for item in raw_items])
    logger.info("Saved raw RSS items: %s", raw_output.as_posix())

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

        categorized = _group_by_category(items, categories_config)
        rewriter = ArticleRewriter(
            llm_client=llm_client,
            intro_prompt_template=str(prompt_config.get("rewrite_intro", "")),
            closing_prompt_template=str(prompt_config.get("rewrite_closing", "")),
        )
        intro = rewriter.rewrite_intro(target_date=target_date, items=items)
        closing = rewriter.rewrite_closing(target_date=target_date)

        title_gen = TitleGenerator(
            llm_client=llm_client,
            title_prompt_template=str(prompt_config.get("title", "")),
            digest_prompt_template=str(prompt_config.get("digest", "")),
        )
        title = title_gen.generate_title(target_date=target_date, items=items)
        digest = title_gen.generate_digest(items=items)

        markdown_renderer = MarkdownRenderer()
        markdown_content = markdown_renderer.render(
            target_date=target_date,
            title=title,
            digest=digest,
            intro=intro,
            categorized_items=categorized,
            closing=closing,
        )
        html_renderer = HtmlRenderer()
        html_content = html_renderer.render(markdown_text=markdown_content, title=title)

        article = DailyArticle(
            target_date=target_date,
            title=title,
            digest=digest,
            intro=intro,
            closing=closing,
            markdown_content=markdown_content,
            html_content=html_content,
            categories=categorized,
            total_items=len(items),
        )

    cover_image_path: str | None = None
    poster_image_path: str | None = None
    if settings.generate_cover_image:
        cover_path = settings.docs_images_dir / f"cover_{target_date.isoformat()}.png"
        generated = ImageRenderer().generate_cover(article.title, cover_path)
        if generated is not None:
            cover_image_path = generated.as_posix()
            article.cover_image_path = cover_image_path

    if settings.generate_article_images:
        poster_path = settings.docs_images_dir / f"poster_{target_date.isoformat()}.png"
        generated = PosterRenderer().generate_poster(article, poster_path)
        if generated is not None:
            poster_image_path = generated.as_posix()
            article.image_paths.append(poster_image_path)

    output_dir = settings.data_output_dir / target_date.isoformat()
    ensure_dir(output_dir)
    markdown_path = output_dir / "article.md"
    html_path = output_dir / "article.html"
    json_path = output_dir / "article.json"
    write_text(markdown_path, article.markdown_content)
    write_text(html_path, article.html_content)
    write_json(json_path, article.to_dict())

    if poster_image_path:
        output_poster_path = output_dir / "poster.png"
        output_poster_path.write_bytes(Path(poster_image_path).read_bytes())

    docs_markdown_path = settings.docs_articles_dir / f"{target_date.isoformat()}.md"
    docs_html_path = settings.docs_articles_dir / f"{target_date.isoformat()}.html"
    write_text(docs_markdown_path, article.markdown_content)
    write_text(docs_html_path, article.html_content)

    # GitHub Pages: 输出 JSON 数据 + Vue 前端渲染
    gh_pages_dir = settings.docs_dir / "ai-daily"
    write_json(gh_pages_dir / "data.json", article.to_dict())
    logger.info("GitHub Pages updated: %s", (gh_pages_dir / "data.json").as_posix())

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
        "markdown_path": markdown_path.as_posix(),
        "html_path": html_path.as_posix(),
        "json_path": json_path.as_posix(),
        "feishu_result": feishu_result,
    }
    logger.info("Pipeline finished: %s", json.dumps(report, ensure_ascii=False))
    return report


def _build_arg_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="AI Daily Paper Generator")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Enable dry-run mode for external API calls",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Maximum number of items to include after dedup",
    )
    return parser


def main() -> None:
    """CLI 入口：解析参数后触发 run_pipeline 并打印 JSON 报告。"""
    args = _build_arg_parser().parse_args()
    target = parse_target_date(args.date)
    report = run_pipeline(
        target_date=target,
        dry_run=args.dry_run,
        max_items=args.max_items,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
