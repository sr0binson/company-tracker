# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A single-page company tracker that monitors GitHub releases and blog/changelog feeds for PostHog, Zapier, Replit, and Linear. It generates AI summaries using the Anthropic API and produces a static `index.html`.

## Running the pipeline

```bash
# 1. Fetch releases + blog posts, generate AI summaries, store in SQLite
python3 fetch_feeds.py

# 2. Regenerate index.html from the database
python3 generate_html.py
```

Run both scripts together to do a full refresh. `fetch_feeds.py` is idempotent — it skips already-fetched entries.

## Environment

Copy `.env` and add your key:
```
ANTHROPIC_API_KEY=...
```

`releases.db` and `.env` are gitignored.

## Architecture

The pipeline is two stages:

**`fetch_feeds.py`** — fetches Atom/RSS feeds (GitHub releases + company blogs), calls `claude-haiku-4-5` via raw `urllib` to generate a plain-English summary and a corny analogy per release, and stores everything in `releases.db` (two tables: `releases` and `blog_posts`).

**`generate_html.py`** — reads from `releases.db` and builds `index.html` as one big Python string. All CSS, JS, and HTML are inline in this file. The JS embedded in the HTML handles:
- Paper stack UI (release cards with toss/rise/warp animations)
- Blog card slideshow with prev/next navigation
- Per-company custom cursors: PostHog → hedgehog with paw prints, Linear → glowing cursor, Zapier → bolt cursor with trail, Replit → logo cursor

Company list and brand colors are hardcoded at the top of each script. To add a new company, add it to `FEEDS`/`BLOG_FEEDS` in `fetch_feeds.py`, `company_colors` in `generate_html.py`, and the render loop (`for company in [...]`).

**GitHub Actions** (`.github/workflows/fetch.yml`) runs both scripts daily at 9am UTC and auto-commits the regenerated `index.html`.

## Design spec

`PROMPTS.md` contains the full design specification and future ideas (e.g. analogy voice selector). Refer to it when making UI changes.

## Prompt logging
When the human sends a chat message asking you to build, change, or fix something:
- Append one entry to prompts.md with format: `### YYYY-MM-DD — <one line summary of what was asked>`
- Log ONLY the human's actual requests, not bash commands, file reads, ls, cat, or your own actions
- Do NOT log meta-commands like "run this", "show me", "cat", "ls", "push", etc.

## Auto-push after completing work
After successfully completing any build/change task (running generate_html.py with no errors):
1. Run: git add .
2. Run: git commit -m "<short description of what changed>"
3. Run: git push
Do this automatically without being asked.
