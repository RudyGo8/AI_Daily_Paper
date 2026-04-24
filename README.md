# AI Daily Paper Generator

一个独立运行的 Python 自动化日报项目：从 RSS 抓取 AI 资讯，完成清洗、事件级去重、分类、LLM 摘要与改写，最终输出可归档的 Markdown / HTML 日报，并可选推送到飞书群机器人卡片。

## Features

- 支持多 RSS 源抓取与按日期过滤
- 支持文本清洗、相似新闻聚合、事件级去重
- 支持分类、关键词提取、标题与 digest 生成
- 支持输出 `article.json`、`article.md`、`article.html`
- 支持飞书群机器人卡片推送
- 可选生成封面图与长图海报
- 包含日志、失败重试、调度入口和测试

## Quick Start

### 1. 安装依赖

推荐使用 `uv`：

```powershell
uv sync
```

或者使用 `pip`：

```powershell
pip install -r requirements.txt
```

### 2. 准备环境变量

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

按需填写 `.env`，最常用的是：

```env
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=your_api_key
LLM_MODEL=qwen-plus

FEISHU_ENABLED=true
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
FEISHU_MESSAGE_TITLE=AI 日报

GENERATE_COVER_IMAGE=false
GENERATE_ARTICLE_IMAGES=false
```

说明：

- `FEISHU_ENABLED=true` 时，流程结束后会发送飞书卡片
- `GENERATE_ARTICLE_IMAGES=false` 时，不生成长图海报
- 当前飞书推送为卡片版，不会再把本地图片路径当文本发出去

### 3. 运行日报流程

先做本地 dry-run：

```powershell
python -m src.main --date 2026-04-24 --dry-run --max-items 12
```

确认正常后再正式发送：

```powershell
python -m src.main --date 2026-04-24 --max-items 12
```

### 4. 运行测试

```powershell
python -B -m pytest -q -p no:cacheprovider
```

## Outputs

默认会生成以下文件：

- `data/raw/raw_YYYY-MM-DD.json`
- `data/output/YYYY-MM-DD/article.json`
- `data/output/YYYY-MM-DD/article.md`
- `data/output/YYYY-MM-DD/article.html`
- `docs/articles/YYYY-MM-DD.md`
- `docs/articles/YYYY-MM-DD.html`

如果开启图片生成，还会额外输出：

- `docs/images/cover_YYYY-MM-DD.png`
- `docs/images/poster_YYYY-MM-DD.png`

## Feishu Card

当前飞书推送使用群机器人卡片消息，内容包括：

- 日报标题
- digest 摘要
- 重点栏目
- 每条新闻的聚合来源
- 原文点击链接

如果你只想保留飞书卡片，不要海报，请确保：

```env
FEISHU_ENABLED=true
GENERATE_ARTICLE_IMAGES=false
```

## GitHub Actions 定时执行

项目已经内置 GitHub Actions 工作流：

- 文件路径：`.github/workflows/daily-report.yml`
- 触发方式：
  - 每天定时执行
  - 手动点击 `Run workflow`

默认定时为北京时间每天 `08:30`，对应 GitHub Actions 的 UTC `00:30`。

### 需要配置的 GitHub Secrets

在仓库 `Settings -> Secrets and variables -> Actions` 里添加：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `FEISHU_WEBHOOK_URL`

可选添加：

- `FEISHU_MESSAGE_TITLE`

### 工作流行为

工作流会自动执行：

1. 拉取代码
2. 安装 Python 与 `uv`
3. 安装依赖
4. 运行日报生成流程
5. 上传 `data/output/` 为构建产物

### 手动触发

你也可以在 GitHub Actions 页面手动触发，并传入：

- `target_date`：指定日期，例如 `2026-04-24`
- `dry_run`：是否只预览不真正调用飞书
- `max_items`：限制日报条数

## Project Structure

核心目录如下：

```text
src/
├── main.py
├── config.py
├── fetchers/
├── processors/
├── llm/
├── renderers/
└── publishers/
```

如果你要看完整架构说明，可以继续参考 `AGENTS.md`。
