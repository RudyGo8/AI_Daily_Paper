# AI Daily Paper V2

多领域定时信息播报：RSS、GitHub 和明确配置的官方网页统一采集，经过时间筛选、合并、热度排序后，仅对 Top K 调用 LLM，生成中文摘要并推送至同一个飞书群机器人。

**GitHub Actions 是正式运行环境，不需要额外服务器。** 不使用常驻服务、数据库服务器、消息队列或 Agent 框架。

## 每日播报

| 北京时间 | Topic | 领域 |
|---|---|---|
| 08:00 | `news` | 科技 / 社会重要新闻 |
| 09:00 | `ai` | AI / 大模型 |
| 10:00 | `agent` | Agent / Vibe Coding |
| 11:00 | `github` | GitHub 热门项目 |
| 12:00 | `python` | Python / 开源技术 |
| 14:00 | `qingdao_policy` | 青岛政策 / 人才政策 |
| 15:30 | `industry` | 行业 / 公司动态 |
| 17:00 | `custom` | 自定义订阅 |

每个 Topic 独立执行、独立排序，默认统计运行时刻之前的 **24 小时**，最多 10 条。合格资讯不足 10 条时展示实际数量；没有新资讯时生成空卡片，不使用过期内容填榜。

GitHub Actions 的调度可能延迟，以上是计划时间，不保证准点送达。Workflow 根据 `github.event.schedule` 路由 Topic，延迟不会导致播错领域。UTC Cron 与 `configs/topics.yaml` 中的 `cron_utc` 一致，由测试检查。

## 安装与运行

Python 3.11+，使用 uv：

```powershell
uv sync --extra dev
Copy-Item .env.example .env
uv run python -m src.main --topic ai --top-k 10 --dry-run
uv run python -m src.main --topic agent --window-hours 24 --dry-run
uv run python -m src.main --topic github --dry-run
```

`--dry-run` 完整抓取、处理、调用配置好的 LLM 并输出飞书 payload，**不发送消息、不保存历史、不写 GitHub data branch**。即使 `FEISHU_ENABLED=false`，dry-run 也会输出预览。

关闭本地 `.env` 加载即可验证无密钥兜底：

```powershell
$env:LOAD_DOTENV = 'false'
uv run python -m src.main --topic news --dry-run
```

恢复本地配置加载：`Remove-Item Env:LOAD_DOTENV`。

正式推送需要 `FEISHU_ENABLED=true` 与有效 Webhook：

```powershell
uv run python -m src.main --topic ai
```

保留 `--date YYYY-MM-DD` 作为调试模式，筛选指定时区的自然日；它优先于滚动窗口参数。`--max-items` 是 `--top-k` 的旧参数别名，两者同时指定时 `--top-k` 优先。默认 Topic 为 `ai`。Top K 与窗口必须为正数，未知 Topic 会给出明确错误。

历史日期无法从 GitHub 当前仓库状态还原当日完整榜单；要回放 RSS/网页并忽略已推送记录，可设置 `HISTORY_ENABLED=false`。

## Pipeline

```text
Load Topic / Sources
  → Fetch: RSS / GitHub / Webpage
  → Rolling Window Filter（或 --date 自然日）
  → Clean / Topic Filter / Deduplicate-Merge
  → History Filter
  → Classify / Keywords
  → Hot Score / Rank / Top K
  → LLM Summary / Title / Digest
  → Feishu Card
  → 成功后保存历史及 Star 快照
```

LLM 只处理排名后的条目。单源、单条目或 LLM 失败会隔离或兜底；日期缺失、无法解析的条目跳过并记录日志，不把抓取时间伪装成发布时间。飞书必须返回明确的成功业务码，才会报告已发送并保存历史；正式发送失败时 CLI 返回非零退出码。

## 配置领域与信息源

`configs/topics.yaml` 配置显示名、emoji、`top_k`、`window_hours`、领域关键词、重大事件关键词、正文排除词、标题排除词、公司观察名单和评分权重。`agent` 等领域要求关键词匹配，避免泛 AI 内容占据榜单。`industry.watch_companies` 可修改关注公司。新增 Topic 时，常规手动运行只需配置；新增定时任务还需同步 Workflow Cron。

`configs/sources.yaml` 每个源可绑定多个 Topic：

```yaml
sources:
  - name: Official Blog
    type: rss
    topic: [ai, agent]
    url: https://example.com/feed.xml
    source_weight: 5
```

旧的 `name + url` 源仍兼容，默认 `type=rss`、`topic=[ai]`、权重 3。`enabled: false` 可停用来源。旧配置中实测不可用的 RSS 已保留并停用；Anthropic 改用官方静态新闻列表。

已配置 Python Insider、Real Python、Astral、Hacker News、中国新闻网、BBC、IT之家和现有 AI 媒体。`custom` 默认提供 Real Python、Astral、Hacker News、uv 仓库作为可运行示例，可直接更换为自己的 RSS、网页或指定仓库。

### GitHub Fetcher

优先使用 REST Search API，按领域分别配置 `queries`；支持 `repositories: [owner/repository]` 指定仓库。搜索近期代码更新的项目，获取 Stars、Forks、创建时间、代码推送时间；对 `enrich_limit` 限定数量的近期候选补充 Release 和 Star 历史，控制 API 请求数量。

增长数据优先使用官方 Star 历史接口的近七天日统计；这些是日历统计，不能当作精确滚动 24 小时增量。接口不可用时，若有上次成功运行的快照，则计算两次快照之间的净增长；没有真实增长数据时不添加增长加分。总 Stars/Forks 使用有上限的对数分数，防止老项目仅凭积累值长期霸榜。

候选只覆盖配置的搜索词与 API 返回范围，补充数据也有数量上限，因此它是可解释的热度榜，而非完整 GitHub Trending 的复刻。可用 `GH_API_TOKEN` 提升本地请求额度；CI 默认使用 `GITHUB_TOKEN`。

### Webpage Fetcher

仅支持明确配置的静态 HTML 列表，使用 requests + BeautifulSoup；不使用浏览器。选择器示例：

```yaml
- name: Official Policy
  type: webpage
  topic: [qingdao_policy]
  url: https://example.gov.cn/notices/
  source_weight: 5
  timezone: Asia/Shanghai
  date_regex: '(\d{4}-\d{2}-\d{2})'
  max_items: 30
  max_detail_items: 10
  selectors:
    item: '.notices li'
    link: 'a'
    title: 'a'
    date: 'time'
  detail_selectors:
    content: '.article-body'
    date: '.published'
```

支持相对链接、显式日期格式、站点时区、可选 URL 日期回退和 `prefer_https`。详情抓取有数量上限，已知过期条目不抓正文。正文抓取失败时保留有日期的列表条目；网页真实日期优先于 URL 中的日期。

已适配青岛人社通知公告与青岛住建规范性文件。政策更新频率较低，24 小时窗口内可能没有新条目；可用 `--window-hours 168` 手动查看近一周。部分住建文件只有 Word 附件，当前不会解析附件，摘要应明确材料不足，并提供原文链接。微信视频号、小红书尚无采集适配；目前使用公开 RSS、GitHub 和静态网站来源。

## 热度评分与飞书卡片

```text
hot_score = source_score + freshness_score + popularity_score
          + cross_source_score + topic_score
```

来源权重来自 YAML；新鲜度按 3/6/12/24 小时区间递减；重大关键词和 GitHub 公开指标反映热度；多源加分按独立来源数计算；领域关键词提供相关度。各分项乘以 Topic 配置的权重，政策领域更加重视官方性和相关度。

排序为 `hot_score DESC → published_at DESC → cluster_size DESC`。相似资讯合并来源、链接、标题并保留较丰富内容，最高来源权重和 GitHub 指标不会因合并丢失。不同 GitHub 仓库不做模糊合并。

飞书按排名展示编号、摘要、合并来源及原文链接；卡片显示领域、实际条数、生成时间和数量统计。分数及原因只进入日志，不显示在卡片中。

## 跨天历史

本地使用 `data/history/<topic>.json`，原子写入，默认保留 30 天。历史按 Topic 隔离，使用规范化 URL 与版本指纹识别已推送内容：

- RSS/网页：标题、摘要与正文变化可作为新版本；URL 跟踪参数被移除。
- GitHub：Release 标签/时间或代码推送时间变化可再次播报；单纯 Stars、元数据更新时间变化不会视为新版本。
- 历史只在非 dry-run 且飞书确认成功后写入。推送失败不会吞掉待推送内容。

CI 使用 **`information-hub-data` 专用分支** 保存每个 Topic 的 JSON，不依赖 Runner 本地磁盘或不可变 Cache。不写默认代码分支。首次成功推送后才创建 data branch；dry-run 只读历史。保存使用 SHA 条件更新和有上限的冲突重试，保留并发新增记录。

损坏历史会保留原文件并禁用该轮历史写入；历史加载/保存故障单独记录，资讯流程继续。若发送成功后历史保存失败，下一次可能再次推送，日志会明确显示该错误。相似事件与内容版本使用规则判断，并不保证语义层面的完全去重；主来源切换且正文不同可能作为新版本。

## GitHub Actions 部署

唯一正式 Workflow：`.github/workflows/information-hub.yml`。旧 `daily-report.yml` 已替换，避免重复推送。手动触发默认 `dry_run=true`，支持输入 Topic、日期、Top K 和窗口。

将代码和配置提交到仓库默认分支后，配置仓库 Secrets：

| Secret | 说明 |
|---|---|
| `LLM_API_KEY` | OpenAI 兼容 API 的密钥；默认 DashScope |
| `LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_MODEL` | 可选；空值使用默认 DashScope 配置 |
| `FEISHU_WEBHOOK_URL` | 同一个飞书群机器人 Webhook |
| `FEISHU_MESSAGE_TITLE` | 旧版卡片标题前缀；V2 使用领域名 |
| `GH_API_TOKEN` | 可选 GitHub 采集 token；缺省使用 Workflow 的 `GITHUB_TOKEN` |

Workflow 已声明 `contents: write`，用于专用历史分支。若组织权限策略或分支规则阻止写入，历史会报错并保留推送结果，需要调整对应权限。统一并发组串行运行 Workflow，避免同一 Topic 的手动和定时运行同时更新状态。

## 环境变量

环境变量优先于 `.env`；`LOAD_DOTENV=false` 禁止读取本地文件。密钥从环境变量/Secrets 获取，不放入 YAML。

| 变量 | 默认值 / 用途 |
|---|---|
| `TIMEZONE` | `Asia/Shanghai`，日期和卡片时区 |
| `CONFIG_DIR` | `configs` |
| `LOG_LEVEL` | `INFO` |
| `RSS_TIMEOUT` / `GITHUB_TIMEOUT` | 20 / 15 秒 |
| `DEDUP_SIMILARITY_THRESHOLD` | `0.88` |
| `LLM_PROVIDER` | `dashscope` |
| `LLM_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL` / `LLM_TIMEOUT` | `qwen3.6-flash` / 60 秒 |
| `FEISHU_ENABLED` | `false`，正式运行须启用 |
| `HISTORY_ENABLED` | `true` |
| `HISTORY_BACKEND` | 本地 `local`；CI `github` |
| `HISTORY_DIR` / `HISTORY_RETENTION_DAYS` | `data/history` / 30 天 |
| `HISTORY_BRANCH` | `information-hub-data` |
| `GITHUB_REPOSITORY` / `GITHUB_TOKEN` | CI 自动注入，用于历史读写 |

`MAX_ITEMS_PER_DAY` 保留为旧环境配置字段；V2 的默认条数由 `topics.yaml.top_k` 决定。

## 测试

```powershell
uv run python -B -m pytest -q -p no:cacheprovider
```

网络层全部 mock，可离线运行。覆盖来源兼容、窗口边界、领域过滤、独立来源合并、评分排序、GitHub 异常隔离、静态网页解析、飞书业务响应、仅 Top K 调用 LLM、dry-run 无写入、跨天版本去重、原子保存及远端 SHA 冲突。测试默认不读取本地 `.env`。

## 目录

```text
configs/               sources.yaml / topics.yaml / categories.yaml / prompt_templates.yaml
src/main.py            Topic Pipeline 与 CLI
src/topics.py          领域配置校验与关键词匹配
src/schedule.py        Cron → Topic
src/fetchers/          RSS / GitHub / Webpage / SourceManager
src/processors/        清洗、合并、分类、关键词、热度评分、排序
src/llm/               LLM 客户端、摘要、标题和导读
src/storage/           本地 JSON 历史与 GitHub data branch
src/publishers/         飞书 interactive card
tests/                 离线 pytest
.github/workflows/     information-hub.yml
```
