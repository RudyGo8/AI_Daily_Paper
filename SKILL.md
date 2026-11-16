# SKILL

可重复执行的实操命令。业务口径见 `prd.md`，架构边界见 `CLAUDE.md`。

## 锚点

- [环境准备](#环境准备)
- [本地预览](#本地预览)
- [正式推送](#正式推送)
- [测试](#测试)
- [GitHub Actions](#github-actions)
- [历史与 data branch](#历史与-data-branch)
- [Topic 与 Cron](#topic-与-cron)
- [常见排查](#常见排查)

本项目无数据库、无迁移、无 HTTP 端口，也没有打包发布产物；发布 = 合并到默认分支后由 Actions 运行。

## 环境准备

```bash
./run.sh                      # 首次运行：自动复制 .env.example → .env，再 uv sync
uv sync --extra dev           # 手动等价：主依赖 + pytest
cp .env.example .env          # 手动等价：生成配置文件
```

要求 Python 3.11+ 与 uv。`.env` 被 `.gitignore` 忽略；真实环境变量优先于 `.env`，`LOAD_DOTENV=false` 可完全禁用它。

## 本地预览

`run.sh` 按当前分支分流：`master` / `main` 默认正式推送（需确认），其余分支强制 `--dry-run`。

```bash
./run.sh --topic ai                      # 非主分支自动预览
./run.sh --topic all --dry-run           # 一次预览全部 Topic
./run.sh --topic github --date 2026-08-17 --dry-run
./run.sh --topic qingdao_policy --window-hours 168 --dry-run
./run.sh --topic ai --top-k 5 --dry-run
```

直接调用模块（绕过 run.sh）：

```bash
uv run python -m src.main --topic ai --dry-run --top-k 10
uv run python -m src.main --topic all --dry-run
HISTORY_ENABLED=false uv run python -m src.main --topic ai --dry-run   # 忽略已推送历史
```

dry-run 只输出飞书卡片 payload：不发送、不写历史、不触达 data branch。

## 正式推送

```bash
git switch master            # 或 main
./run.sh --topic ai          # 交互确认后发送
./run.sh --topic all --yes   # 跳过确认，批量发送全部 Topic
```

前置条件：`.env` 中 `FEISHU_ENABLED=true`、`FEISHU_WEBHOOK_URL` 有效、`LLM_API_KEY` 有效。非 `master` / `main` 分支会拒绝正式推送并回落到预览；推送未确认成功时 CLI 返回非零退出码。

## 测试

```bash
uv run python -B -m pytest -q -p no:cacheprovider                       # 全量
uv run python -B -m pytest -q -p no:cacheprovider tests/test_history.py # 单文件
uv run python -B -m pytest -q -p no:cacheprovider -k history            # 按关键词
uv run python -B -m pytest -q -p no:cacheprovider tests/test_cli.py -x -vv
```

网络层全部 mock，可离线运行；测试 fixture 设置 `LOAD_DOTENV=false`，不读取本地密钥。

## GitHub Actions

```bash
gh workflow run information-hub.yml -f topic=all -f dry_run=true   # 手动预览全部 Topic
gh workflow run information-hub.yml -f topic=ai -f dry_run=false   # 手动正式推送单 Topic
gh run list --workflow information-hub.yml --limit 5
gh run watch <run-id>
gh run view <run-id> --log | grep -iE "feishu|error|fallback"
```

Secrets 需配置 `LLM_API_KEY`、`FEISHU_WEBHOOK_URL`，可选 `LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_MODEL` / `GH_API_TOKEN`。Workflow 声明 `contents: write` 用于写历史分支。

## 历史与 data branch

本地历史：`data/history/<topic>.json`，按 Topic 隔离，默认保留 30 天。CI 历史：`information-hub-data` 分支 `history/<topic>.json`。

```bash
python3 -m json.tool data/history/ai.json | head -40          # 查看本地历史
git fetch origin information-hub-data                          # 拉取远端历史
git show origin/information-hub-data:history/ai.json | head -40
git log origin/information-hub-data -5 --oneline
```

远端历史写入被拒绝时，检查分支保护规则与 `contents: write` 权限；`src/storage/github_state.py` 会主动拒绝写默认分支，属于预期保护。历史文件损坏时保留原文件并跳过该轮写入，可手工修复后重跑。

## Topic 与 Cron

```bash
uv run python -m src.schedule --cron "0 0 * * *"    # 该批次的 Topic 组（逗号分隔）
```

`configs/topics.yaml` 的 `cron_utc` 决定 Topic 属于哪一批：一天两档（北京时间 08:00 / 17:00），同一 cron 的 Topic 在同一次 Actions 中依次播报，共用一个采集截止时间。Topic 显示名、`top_k`、`window_hours`、关键词、权重都在该文件；源与绑定的 Topic 在 `configs/sources.yaml`。新增 Topic 会自动加入 `--topic all`；要让它参与定时播报，需把 `cron_utc` 设为某一批的 cron，并同步 `.github/workflows/information-hub.yml` 的 `schedule` 与 `options`（测试会校验两边一致）。

## 常见排查

| 现象 | 处理 |
|---|---|
| 卡片显示暂无新资讯 | 窗口内无新条目或已全部推送；用 `--window-hours 168` 或 `HISTORY_ENABLED=false` 复查 |
| 摘要出现 `[fallback]` | `LLM_API_KEY` 缺失或调用失败，流水线已降级为模板输出 |
| 推送后 CLI 非零退出 | 飞书未返回成功业务码；核对 Webhook 与机器人配置 |
| 改了 `.env` 不生效 | 同名环境变量优先；确认 `LOAD_DOTENV` 未被设为 `false` |
| 时区 / 日期串位 | `TIMEZONE` 默认 `Asia/Shanghai`；`--date` 按该时区自然日筛选 |
| Actions 没有按点运行 | Cron 有调度延迟属正常；Topic 由 `github.event.schedule` 路由，不会播错领域 |
