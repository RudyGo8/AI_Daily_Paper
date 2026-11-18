# 项目架构与规则

`CLAUDE.md` 与 `AGENTS.md` 内容逐字节一致。只写本项目的架构边界与专属规则；通用代码质量、完成标准、文档规范见全局 `CLAUDE.md`。

## 定位

定时批处理流水线，不是服务：按 Topic 从 RSS、GitHub、明确配置的静态网页采集资讯，过去 24 小时窗口内筛选、清洗、领域过滤、合并、历史去重、评分排序，仅对 Top K 调用 LLM 生成中文摘要 / 标题 / 导读，以同一个飞书群机器人 interactive card 推送。正式运行在 GitHub Actions，每天一次（北京时间 10:00），一次依次播报全部 Topic 组；无常驻进程、无数据库、无消息队列、无 Agent 框架。

## 架构地图

```text
schedule.py（Cron→Topic 组）/ CLI --topic
      │  同一 cron 的 Topic 共用一次采集截止时间；--topic all 执行全部 Topic
      ▼
fetchers/source_manager ── rss | github | webpage（单源失败只记日志）
      ▼
processors/cleaner → classifier（领域匹配）→ deduplicator（合并）
      ▼
storage/history（已推送过滤，只读）
      ▼
keyword_extractor → hot_scorer → ranker（Top K 在此产生）
      ▼
llm/summarizer + title_generator（仅入选条目）
      ▼
publishers/feishu_bot → 成功业务码 → storage/history 写入
```

## 模块边界

| 模块 | 负责 | 禁止 |
|---|---|---|
| `src/main.py` | 编排、CLI、`--topic all` 循环、退出码 | 内联阈值 / 关键词等业务规则 |
| `src/topics.py`、`src/schedule.py` | Topic 校验、关键词匹配、Cron→Topic 组 | 依赖进程实际启动时间 |
| `src/fetchers/` | 网络采集、单源隔离、字段归一 | 评分、调 LLM、推送、写历史 |
| `src/processors/` | 无网络、无磁盘副作用的纯处理 | 发请求、写文件 |
| `src/storage/` | 历史读写、远端条件更新 | 业务语义判断 |
| `src/llm/` | LLM 调用、模板兜底 | 决定哪些条目入选 |
| `src/publishers/` | 卡片组装、HTTP 推送 | 写历史 |
| `configs/*.yaml` | 源、Topic、分类、提示词 | 密钥、代码 |

## 数据与状态

无数据库；状态是两份 JSON 历史，按 Topic 一文件，默认保留 30 天。

| 环境 | 后端 | 位置 |
|---|---|---|
| 本地 / dry-run | `HISTORY_BACKEND=local` | `data/history/<topic>.json`，原子写入 |
| GitHub Actions | `HISTORY_BACKEND=github` | `information-hub-data` 分支 `history/<topic>.json` |

- 历史只在飞书确认成功业务码后写入；dry-run 只读不写。
- 版本指纹区分"已推送内容"与"新版本"：RSS / 网页看标题、摘要、正文；GitHub 看 Release 标签 / 时间或代码推送时间，纯 Stars 变化不算新版本。
- 远端保存使用 SHA 条件更新与有限次冲突重试，保留并发新增记录。
- 历史损坏时保留原文件并跳过该轮写入，资讯流程继续。

## 鉴权与密钥

| 凭据 | 来源 | 边界 |
|---|---|---|
| `LLM_API_KEY` | 本地 `.env` / Actions Secrets | 仅 LLM 客户端读取 |
| `FEISHU_WEBHOOK_URL` | 同上 | 仅 publishers 读取 |
| `GITHUB_TOKEN` / `GH_API_TOKEN` | CI 自动注入 / 可选提升额度 | 历史读写、GitHub 采集 |
| `GITHUB_REPOSITORY` | CI 自动注入 | 缺省则禁用远端历史 |

- 密钥只走环境变量或 Secrets，不落 YAML、不落代码、不入日志。
- 远端历史只能写 `information-hub-data`；`src/storage/github_state.py` 拒绝写入默认分支，Workflow 仅声明 `contents: write`。
- `.env` 被 `.gitignore` 忽略，入库模板为 `.env.example`；CI 用 `LOAD_DOTENV=false` 保证不读本地文件。

## 流程不变量

- **先排名再 LLM**：评分排序前不得截取 Top K。
- **失败隔离**：单源、单条目、单 Topic 失败都不中断其余部分；LLM 无 key 或调用失败返回 `[fallback]` 前缀，由上层模板兜底。
- **时间不编造**：缺失或非法发布日期直接跳过，不把抓取时间当发布时间。
- **去重是合并不是丢弃**：重复条目合并来源、链接、标题到 `merged_*` 字段，主体取信息量更大的一方；不同 GitHub 仓库不做模糊合并。
- **配置与代码分离**：新增源、Topic、分类、提示词只改 `configs/*.yaml`，代码中无业务硬编码。
