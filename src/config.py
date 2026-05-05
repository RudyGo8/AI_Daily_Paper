"""配置加载模块：从 .env 文件和环境变量中读取所有项目配置。

Settings 数据类是全局配置的唯一入口，通过 load_settings() 创建。
支持 .env 文件自动加载、YAML 配置文件读取、布尔值字符串转换。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - handled by runtime error path
    yaml = None


def _str_to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        row = line.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, value = row.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _require_yaml() -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML is required. Install dependencies first.")
    return yaml


def load_yaml(path: Path) -> dict[str, Any]:
    """安全加载 YAML 配置文件，返回字典。文件不存在时抛出异常。"""
    yaml_module = _require_yaml()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    content = yaml_module.safe_load(path.read_text(encoding="utf-8"))
    return content or {}


@dataclass
class Settings:
    """项目的全局配置，所有字段从环境变量或默认值初始化。"""
    project_root: Path
    env: str
    log_level: str
    timezone: str

    config_dir: Path
    sources_file: Path
    categories_file: Path
    prompt_templates_file: Path

    data_dir: Path
    data_raw_dir: Path
    data_processed_dir: Path
    data_output_dir: Path
    docs_dir: Path
    docs_articles_dir: Path
    docs_images_dir: Path

    rss_timeout: int
    dedup_similarity_threshold: float
    max_items_per_day: int

    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout: int

    feishu_enabled: bool
    feishu_webhook_url: str
    feishu_message_title: str

    generate_cover_image: bool
    generate_article_images: bool


def load_settings(project_root: Path | None = None) -> Settings:
    """加载所有配置，返回 Settings 实例。自动加载项目根目录的 .env 文件。"""
    root = (project_root or Path(__file__).resolve().parent.parent).resolve()
    _load_dotenv(root / ".env")

    env = os.getenv("ENV", "dev")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    timezone_value = os.getenv("TIMEZONE", "Asia/Shanghai")

    config_dir = root / os.getenv("CONFIG_DIR", "configs")
    data_dir = root / os.getenv("DATA_DIR", "data")
    docs_dir = root / os.getenv("DOCS_DIR", "docs")

    return Settings(
        project_root=root,
        env=env,
        log_level=log_level,
        timezone=timezone_value,
        config_dir=config_dir,
        sources_file=config_dir / "sources.yaml",
        categories_file=config_dir / "categories.yaml",
        prompt_templates_file=config_dir / "prompt_templates.yaml",
        data_dir=data_dir,
        data_raw_dir=data_dir / "raw",
        data_processed_dir=data_dir / "processed",
        data_output_dir=data_dir / "output",
        docs_dir=docs_dir,
        docs_articles_dir=docs_dir / "articles",
        docs_images_dir=docs_dir / "images",
        rss_timeout=int(os.getenv("RSS_TIMEOUT", "20")),
        dedup_similarity_threshold=float(
            os.getenv("DEDUP_SIMILARITY_THRESHOLD", "0.88")
        ),
        max_items_per_day=int(os.getenv("MAX_ITEMS_PER_DAY", "50")),
        llm_provider=os.getenv("LLM_PROVIDER"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL"),
        llm_timeout=int(os.getenv("LLM_TIMEOUT", "60")),
        feishu_enabled=_str_to_bool(os.getenv("FEISHU_ENABLED"), default=False),
        feishu_webhook_url=os.getenv("FEISHU_WEBHOOK_URL", ""),
        feishu_message_title=os.getenv("FEISHU_MESSAGE_TITLE", "AI 日报"),
        generate_cover_image=_str_to_bool(
            os.getenv("GENERATE_COVER_IMAGE"),
            default=False,
        ),
        generate_article_images=_str_to_bool(
            os.getenv("GENERATE_ARTICLE_IMAGES"),
            default=False,
        ),
    )
