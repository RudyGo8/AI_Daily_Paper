# AI Daily Feishu Publisher

从 RSS 抓取每日 AI 资讯，清洗、去重、分类后调用千问生成中文摘要，并推送为飞书群机器人卡片。

## 功能

- 多 RSS 源抓取
- 按日期筛选资讯
- 文本清洗、相似新闻合并和去重
- 规则分类与关键词提取
- 使用 DashScope 千问生成中文摘要、标题和 digest
- 推送飞书 interactive card
- 支持 dry-run 预览卡片 payload

## 安装

使用 `uv`（`--extra dev` 同时安装 pytest 等测试依赖）：

```powershell
uv sync --extra dev
```

## 配置

复制并填写 `.env`：

```powershell
Copy-Item .env.example .env
```

核心配置：

```env
LLM_PROVIDER=dashscope
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=your_api_key
LLM_MODEL=qwen3.6-flash

FEISHU_ENABLED=true
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
FEISHU_MESSAGE_TITLE=AI 日报
```

配置优先级：**环境变量 > `.env` > 代码默认值**。本地由 `.env` 提供；CI 上不存在 `.env`，全部来自仓库 Secrets。

## 运行

预览飞书卡片，不实际推送：

```powershell
uv run python -m src.main --date 2026-05-31 --dry-run --max-items 6
```

正式推送：

```powershell
uv run python -m src.main --date 2026-05-31 --max-items 6
```

## 测试

```powershell
uv run python -B -m pytest -q -p no:cacheprovider
```

## GitHub Actions 定时部署

`.github/workflows/daily-report.yml` 每天 UTC 22:01（北京时间 06:01）自动运行，也可在 Actions 页面手动触发（支持指定日期、dry-run、条数上限）。

需要在仓库 Settings → Secrets and variables → Actions 配置：

| Secret | 说明 |
|---|---|
| `LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_MODEL` | LLM 接入参数（OpenAI 兼容，默认 DashScope） |
| `LLM_API_KEY` | DashScope（百炼）API key |
| `FEISHU_WEBHOOK_URL` | 飞书群机器人 webhook |
| `FEISHU_MESSAGE_TITLE` | 卡片标题前缀 |

CI 环境没有 `.env`，以上 Secret 经 workflow 的 `env:` 块注入为环境变量，是线上唯一的配置来源。

## 结构

```text
configs/
  sources.yaml
  categories.yaml
  prompt_templates.yaml
src/
  main.py
  config.py
  fetchers/
  processors/
  llm/
  publishers/
  models/
  utils/
tests/
.github/workflows/daily-report.yml   # 每日定时推送
```
