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

推荐使用 `uv`：

```powershell
uv sync
```

或使用 `pip`：

```powershell
pip install -r requirements.txt
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

## 运行

预览飞书卡片，不实际推送：

```powershell
.\.venv\Scripts\python.exe -m src.main --date 2026-05-31 --dry-run --max-items 6
```

正式推送：

```powershell
.\.venv\Scripts\python.exe -m src.main --date 2026-05-31 --max-items 6
```

## 测试

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

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
```
