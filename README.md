# AI Daily Paper Generator

An independent Python pipeline that fetches daily AI news from RSS, cleans and classifies content, summarizes and rewrites it with an LLM, and renders archiveable Markdown and HTML daily reports.

## Features

- Fetch news from one or more RSS feeds.
- Filter by target date.
- Clean and deduplicate content.
- Classify into categories.
- Extract keywords.
- Generate summary/title/digest/article style with a unified LLM client.
- Render Markdown and HTML daily reports.
- Optionally generate a simple cover image.
- Includes retry, logging, scheduler entrypoint, and tests.

## Quick Start

1. Install dependencies:

```bash
uv sync
```

or

```bash
pip install -r requirements.txt
```

2. Prepare environment:

```bash
cp .env.example .env
```

3. Run pipeline:

```bash
python -m src.main --date 2026-04-23 --dry-run
```

4. Run tests:

```bash
python -B -m pytest -q -p no:cacheprovider
```

## Project Structure

See `AGENTS.md` for the full architecture guidelines used in this implementation.
