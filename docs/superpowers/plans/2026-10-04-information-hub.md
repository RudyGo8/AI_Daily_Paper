# Information Hub V2 Implementation Plan

**Goal:** Implement P0, verify it, then complete P1 and P2 in the existing batch pipeline.
**Architecture:** Topic/source YAML selects one topic per run. All fetchers return NewsItem; rolling-window filtering, merging, scoring and ranking precede LLM calls. JSON history is committed only after successful delivery; CI stores per-topic state on a dedicated data branch.
**Tech Stack:** Python 3.11+, requests, feedparser, BeautifulSoup, PyYAML, pytest, GitHub Actions.
**Spec:** `AI_Daily_Paper_V2_Codex_Task.md`; user authorized all phases and autonomous verification.

## Constraints
- Keep current dependencies, legacy source configuration, CLI date/max-items and LLM fallback.
- No service, database server, browser automation, or new framework.
- Dry-run always builds a card and never sends or changes delivery history.
- Unknown dates are logged and skipped rather than presented as newly published.
- Schedule routing uses the triggering cron, independently of runner start time.
- Fewer than ten eligible items produces the actual count, without filling with old news.

## Tasks
- [x] P0 configuration/model: add `src/topics.py`, `configs/topics.yaml`; extend Settings, NewsItem and DailyArticle with defaulted fields. Test legacy sources, topic validation, window boundaries.
- [x] P0 scoring/ranking: add `hot_scorer.py`, `ranker.py`; fix same-link merge, retain source weights/titles, count distinct sources. Test authority, freshness, relevance, independent-source boost and Top K ties.
- [x] P0 fetching/pipeline: add GitHub search, repository/release metadata and bounded star-history enrichment; route SourceManager by type; update main and topic cards/prompts. Mock HTTP and verify only ranked Top K reaches LLM and dry-run cannot post.
- [x] P0 scheduling: replace old workflow with one multi-cron workflow and a tested Python cron resolver; validate UTC-to-Beijing mapping. Full pytest and live ai/agent/github dry-runs passed with configured LLM (no sends); later smoke tests disable dotenv to validate fallback.
- [x] P1 sources: configure Python, important news and industry filters/company watchlist; verify real feeds and run topic dry-runs.
- [x] P2 pages: add selector-based webpage/repository subscriptions; configure and validate Qingdao official pages. Test relative links, local dates, full article text, bad rows and isolated failures.
- [x] P2 history: add atomic local JSON store and GitHub data-branch load/save; version-aware per-topic keys, retention, failure isolation and dry-run/read-only behavior. Test delivery failure vs success and repository updates.
- [x] Documentation/review: update README, env template and AGENTS; full offline tests, all-topic smoke checks, compile and git diff checks passed. Independent review findings fixed and scoped re-review passed.

## Validation result (2026-10-05)
- 127 offline tests passed; compileall and git diff --check passed.
- Final live dry-runs: news/ai/agent/github/python/industry/custom produced Top 10; qingdao_policy found 25 dated candidates with zero in the last 24h and produced Top 0.
- Three initial P0 live runs used the configured LLM successfully for all 30 selected item summaries. Final all-topic run disabled dotenv and verified fallback, no sends and no history writes.
- Final live run isolated a ReadTimeout from The Decoder and an unavailable astral-sh/uv repository endpoint. Other sources completed and their topics produced cards.
- Qingdao HRSS HTML bodies parse; some SJW documents are attachment-only and attachment text is not extracted. Video-platform collection remains outside the implemented RSS/GitHub/static-page adapters.
- GitHub state load/create/save/concurrency is covered by mocked API tests; no real remote write, branch deployment or Feishu message was performed.
- Work remains in the user's current checkout for review; no git commit/push was requested or performed.

## Validation commands
```powershell
uv run python -B -m pytest -q -p no:cacheprovider
uv run python -m src.main --topic ai --top-k 10 --dry-run
uv run python -m src.main --topic agent --top-k 10 --dry-run
uv run python -m src.main --topic github --top-k 10 --dry-run
git diff --check
```
