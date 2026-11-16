#!/usr/bin/env bash
# AI Daily Paper 一键运行：首次自动生成 .env，按分支分流预览或正式推送。
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

topic="ai"
target_date=""
top_k=""
window_hours=""
force_dry_run=0
assume_yes=0

usage() {
  cat <<'EOF'
用法: ./run.sh [选项]

  --topic NAME        主题键（configs/topics.yaml），或 all（默认 ai）
  --date YYYY-MM-DD   按指定时区自然日调试
  --top-k N           覆盖该主题的 Top K
  --window-hours H    覆盖滚动窗口小时数
  --dry-run           强制预览（不发送、不写历史）
  -y, --yes           正式推送时跳过确认
  -h, --help          显示本帮助

分流规则：master / main 分支正式推送（需确认），其余分支强制预览。
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --topic) topic="${2:?缺少 --topic 的值}"; shift 2 ;;
    --date) target_date="${2:?缺少 --date 的值}"; shift 2 ;;
    --top-k) top_k="${2:?缺少 --top-k 的值}"; shift 2 ;;
    --window-hours) window_hours="${2:?缺少 --window-hours 的值}"; shift 2 ;;
    --dry-run) force_dry_run=1; shift ;;
    -y|--yes) assume_yes=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $1" >&2; usage >&2; exit 2 ;;
  esac
done

command -v uv >/dev/null 2>&1 || {
  echo "未找到 uv，请先安装：https://docs.astral.sh/uv/" >&2
  exit 1
}

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已根据 .env.example 生成 .env；正式推送前请填写 LLM_API_KEY 与 FEISHU_WEBHOOK_URL。"
fi

echo "版本: $(tr -d '[:space:]' < VERSION)"
uv sync --extra dev --frozen --quiet

args=(--topic "$topic")
[[ -n "$target_date" ]] && args+=(--date "$target_date")
[[ -n "$top_k" ]] && args+=(--top-k "$top_k")
[[ -n "$window_hours" ]] && args+=(--window-hours "$window_hours")

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"

if [[ "$force_dry_run" == "1" ]]; then
  args+=(--dry-run)
  echo "模式: 预览（--dry-run）"
elif [[ "$branch" == "master" || "$branch" == "main" ]]; then
  # 用应用自身的配置加载判断，避免与环境变量优先级不一致。
  readiness="$(uv run --frozen python - <<'PY'
from src.config import load_settings

settings = load_settings()
print("yes" if settings.feishu_enabled else "no", "yes" if settings.llm_api_key else "no")
PY
)"
  feishu_ready="${readiness%% *}"
  llm_ready="${readiness##* }"

  if [[ "$feishu_ready" != "yes" ]]; then
    echo "正式推送需要 FEISHU_ENABLED=true，当前配置未启用；改用 --dry-run 可仅预览。" >&2
    exit 1
  fi
  if [[ "$llm_ready" != "yes" ]]; then
    echo "警告: LLM_API_KEY 为空，摘要将退化为模板兜底。" >&2
  fi
  if [[ "$assume_yes" != "1" ]]; then
    if [[ ! -t 0 ]]; then
      echo "非交互环境无法确认推送，请加 --yes 或 --dry-run。" >&2
      exit 1
    fi
    read -r -p "即将正式推送到飞书群（topic=$topic），继续？[y/N] " answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "已取消。"; exit 0; }
  fi
  echo "模式: 正式推送（分支 $branch）"
else
  args+=(--dry-run)
  echo "模式: 预览（分支 ${branch:-未知} 非 master/main）"
fi

exec uv run --frozen python -m src.main "${args[@]}"
