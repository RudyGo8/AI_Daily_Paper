# AI Daily Paper

按 Topic 从 RSS、GitHub、静态网页采集资讯，去重排序后仅对 Top K 调用 LLM 生成中文摘要，以飞书群机器人卡片推送。

## 技术栈

| 项 | 选型 |
|---|---|
| 语言 / 依赖 | Python 3.11+，uv 管理 |
| 采集 | requests / feedparser / BeautifulSoup / PyYAML（均为硬依赖） |
| LLM | OpenAI 兼容协议，默认 DashScope `qwen3.6-flash` |
| 推送 | 飞书群机器人 interactive card |
| 运行环境 | GitHub Actions（`.github/workflows/`），无常驻服务、无数据库、无 HTTP 端口 |

## 文档职责

| 文件 | 职责 |
|---|---|
| `README.md` | 项目门面：简介、技术栈、运行入口、目录概览 |
| `SKILL.md` | 可重复执行的实操命令与排查步骤 |
| `CLAUDE.md` / `AGENTS.md` | 架构地图、模块边界、数据与鉴权规则（两份逐字节一致） |
| `CHANGELOG.md` | 用户与运维可见的版本变化 |
| `prd.md` | 业务目标与验收口径，仅人工维护 |
| `VERSION` | 唯一版本号来源，`pyproject.toml` 动态读取 |

## 运行入口

本项目无 HTTP 端口，入口只有 CLI 与 Actions。`run.sh` 按分支分流：`master` / `main` 正式推送，其余分支强制预览。

| 场景 | 入口 | 发送飞书 | 写历史 |
|---|---|---|---|
| 本地预览 | `./run.sh --topic ai`（非主分支自动加 `--dry-run`） | 否 | 否 |
| 全量预览 | `./run.sh --topic all --dry-run` | 否 | 否 |
| 本地正式推送 | `./run.sh --topic ai`（`master` / `main`，需确认） | 是 | 是 |
| 指定自然日调试 | `./run.sh --topic ai --date 2026-08-17` | 否 | 否 |
| 测试 | `uv run python -B -m pytest -q -p no:cacheprovider` | 否 | 否 |
| 定时 / 手动播报 | GitHub Actions `.github/workflows/information-hub.yml` | 由 `dry_run` 决定 | 由 `dry_run` 决定 |

## 目录职责

| 路径 | 职责 |
|---|---|
| `configs/` | 源、Topic、分类、提示词；业务配置全部在 YAML |
| `src/main.py` | Pipeline 编排、CLI、退出码 |
| `src/fetchers/` | RSS / GitHub / 网页采集与多源调度 |
| `src/processors/` | 清洗、合并、分类、关键词、评分、排序 |
| `src/storage/` | 本地 JSON 历史与 GitHub data branch 状态 |
| `src/llm/` | LLM 客户端、摘要、标题与导读 |
| `src/publishers/` | 飞书卡片构建与推送 |
| `tests/` | 离线 pytest，网络层全部 mock |
| `.github/workflows/` | 唯一正式 Workflow |
