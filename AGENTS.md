# AGENTS.md

## 项目概述

AI Daily Paper V2：按 Topic 从 RSS、GitHub、明确配置的静态网页采集资讯，过去 24 小时筛选、清洗、领域过滤、合并、历史去重、评分排序后，仅对 Top K 调用 LLM（OpenAI 兼容协议，默认 DashScope 千问），生成中文摘要、标题和导读，以同一个飞书群机器人 interactive card 推送。GitHub Actions 多时段运行（`.github/workflows/information-hub.yml`，北京时间 08:00～17:00）。

## 技术栈

- Python 3.11+，uv 管理依赖
- requests / feedparser / BeautifulSoup / PyYAML（均为硬依赖，无可选降级路径）

## 常用命令

```powershell
uv sync --extra dev                                   # 安装依赖与 pytest
uv run python -m src.main --topic ai --dry-run --top-k 10 # 本地预览（不推送，不写历史）
uv run python -m src.main --topic github --dry-run      # GitHub 领域预览
uv run python -m src.main --topic ai --date 2026-08-17 --dry-run # 指定自然日调试
uv run python -B -m pytest -q -p no:cacheprovider    # 测试
```

## 目录结构

```text
configs/
  sources.yaml            # RSS / GitHub / Webpage 源与多 Topic 绑定，兼容 name + url
  topics.yaml             # 领域、窗口、Top K、评分权重、关键词、公司名单、Cron
  categories.yaml         # 分类关键词
  prompt_templates.yaml   # LLM 提示词模板（summarize / title / digest）
src/
  main.py                 # 单 Topic Pipeline：筛选→合并→历史过滤→评分→排序→Top K→LLM→飞书
  topics.py               # Topic 校验与关键词匹配
  schedule.py             # 根据触发 Cron 解析 Topic，不依赖实际启动时间
  config.py               # 配置加载（.env + 环境变量，Settings 为全局唯一入口）
  fetchers/               # rss_fetcher / github_fetcher / webpage_fetcher / source_manager
  processors/             # cleaner / deduplicator / classifier / keyword_extractor / hot_scorer / ranker
  storage/                # 原子本地 JSON 历史 / GitHub 专用 data branch 状态
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
- **先排名再 LLM**：不得在评分排序前截取 Top K；卡片保留全局排名，不按分类重新排序
- **时间不能编造**：缺失/非法发布日期跳过；`--date` 用指定时区自然日，其余默认滚动 24h
- **历史只在成功推送后写入**：dry-run 仅读历史；飞书确认成功业务码后保存；CI 使用 `information-hub-data` 分支，每 Topic 一个 JSON，禁止写默认分支
- **离线测试不加载密钥**：测试 fixture 设置 `LOAD_DOTENV=false`，网络由 mock 隔离
