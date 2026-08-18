# AGENTS.md

## 项目概述

AI Daily Paper：从 RSS 源抓取每日 AI 资讯，经清洗、去重、分类后调用 LLM（OpenAI 兼容协议，默认 DashScope 千问）生成中文摘要、标题与 digest，最终以飞书群机器人 interactive card 推送。GitHub Actions 每日定时运行（`.github/workflows/daily-report.yml`，UTC 22:01 / 北京时间 06:01）。

## 技术栈

- Python 3.11+，uv 管理依赖
- requests / feedparser / BeautifulSoup / PyYAML（均为硬依赖，无可选降级路径）

## 常用命令

```powershell
uv sync                                              # 安装依赖
uv run python -m src.main --dry-run --max-items 6    # 本地预览（不推送飞书）
uv run python -m src.main --date 2026-08-17          # 指定日期正式运行
uv run python -B -m pytest -q -p no:cacheprovider    # 测试
```

## 目录结构

```text
configs/
  sources.yaml            # RSS 源列表（name + url）
  categories.yaml         # 分类关键词
  prompt_templates.yaml   # LLM 提示词模板（summarize / title / digest）
src/
  main.py                 # Pipeline 入口：抓取→筛选→清洗→去重→分类→关键词→LLM摘要→飞书推送
  config.py               # 配置加载（.env + 环境变量，Settings 为全局唯一入口）
  fetchers/               # RSS 抓取（rss_fetcher）与多源管理（source_manager）
  processors/             # 清洗 cleaner / 去重 deduplicator / 分类 classifier / 关键词 keyword_extractor
  llm/                    # LLM 客户端 llm_client / 摘要 summarizer / 标题生成 title_generator
  publishers/             # 飞书机器人推送 feishu_bot
  models/schemas.py       # NewsItem / DailyArticle 数据结构
  utils/                  # 日期工具 date_utils / 重试装饰器 retry
tests/                    # pytest（网络层全部 mock，可离线跑）
```

## 关键约定

- **LLM 失败不中断流水线**：`LLMClient.complete` 无 key 或调用失败时返回 `[fallback]` 前缀文本；上层用 `is_fallback_response()` 判断后走模板兜底（summarizer / title_generator 各有自己的 fallback）
- **单源失败不中断整轮**：`SourceManager.fetch_all` 对每个源 try/except，失败只记日志
- **飞书推送支持 dry-run**：`--dry-run` 输出卡片 payload 预览，不实际发送
- **配置与代码分离**：源、分类、提示词全部在 `configs/*.yaml`；密钥走环境变量 / GitHub secrets，代码中无业务硬编码
- **去重是合并不是丢弃**：重复条目合并来源/链接/标题到 `merged_*` 字段，保留信息量更大的一方作为主体
