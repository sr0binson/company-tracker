# Company Tracker — Project Notes
**Status: PAUSED as of June 27, 2026**
Live site: sr0binson.github.io/company-tracker
Repo: github.com/sr0binson/company-tracker

---

## What This Project Does
Tracks product releases, changelogs, and blog posts for 4 companies:
PostHog, Zapier, Replit, Linear.

Fetches RSS feeds daily, stores data in SQLite, generates a styled HTML page,
and deploys automatically via GitHub Actions.

---

## Tech Stack
- Python 3.14.3 — fetch_feeds.py, validate.py, autofix.py, generate_html.py
- SQLite — releases.db (main data), logs.db (errors), companies.db (metadata)
- GitHub Actions — fetch.yml runs daily at 9am UTC
- Anthropic Claude Haiku — pre-generates 5 voice analogies per post
- GitHub Pages — hosts the live site (repo must stay PUBLIC)

---

## Pipeline Order
fetch_feeds.py → validate.py → autofix.py → generate_html.py → git commit

---

## What Was Completed
- Self-healing pipeline: alert.py emails errors, autofix.py fixes bad data
- Voice selector: 5 tones (90s R&B, Gen Z, Medieval, AI fluff, Plain)
- Custom cursors per company, paper stack releases UI, favicon
- validate.py checks for dead URLs, empty fields, bad summaries
- Mozilla/5.0 User-Agent fix for Linear/Cloudflare bot blocking
- PostHog analytics script removed (CSP + privacy)
- README added, workflow disabled

---

## To Re-Enable the Project
1. Run: cd ~/company-tracker && git pull
2. Go to GitHub → Actions → fetch.yml → "..." → Enable workflow
3. Trigger a manual run to confirm pipeline is healthy
4. Check logs.db for any errors that built up while paused:
   sqlite3 logs.db "SELECT * FROM errors WHERE fixed = 0;"

---

## Open Items (pick up here when ready)
1. companies.db populate script — never completed
2. GitHub Actions failure email — verify in Settings → Notifications → Actions
3. Mobile CSS — hiring summary card text cutoff, needs desktop check first
4. Reddit 403/429 on Replit/Linear community pulse — transient, monitor
5. Consider swapping Replit Reddit feed for a changelog/blog RSS instead

---

## Key Rules
- Always git pull before any local work
- Repo must stay PUBLIC for GitHub Pages to work
- Linear 503/525 = Cloudflare bot blocking, not dead pages
- Empty strings pass IS NOT NULL — always use AND column != '' guards
- errors.details stores the URL (not a separate url column)
- errors.fixed: 0=open, 1=fixed, -1=unfixable/recheck

---

## GitHub Secrets (do not lose these)
ALERT_EMAIL, GMAIL_USER, GMAIL_APP_PASSWORD
(stored in repo Settings → Secrets → Actions)
