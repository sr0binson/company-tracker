import urllib.request
import xml.etree.ElementTree as ET
import sqlite3
import json
import os
import re
import time
from datetime import date as date_cls
from email.utils import parsedate_to_datetime
from html import unescape
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

def sanitize_input(text):
    """Strip suspicious patterns from RSS feed content before DB storage.
    Applied to raw feed fields before AI calls (prompt injection) and before
    every DB insert (stored XSS / defence in depth)."""
    if not text:
        return text
    # Remove script tags and their content
    text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
    # Remove javascript: pseudo-URLs
    text = re.sub(r'javascript\s*:', '', text, flags=re.IGNORECASE)
    # Remove on* event attributes (onclick="...", onload='...', onmouseover=foo)
    text = re.sub(r'\bon\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|\S+)', '', text, flags=re.IGNORECASE)
    # Remove prompt injection phrases
    for pattern in (
        r'ignore\s+(?:all\s+)?previous\s+instructions?',
        r'\byou\s+are\s+now\b',
        r'\bdisregard\b',
        r'new\s+instructions?\s*:',
    ):
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return text.strip()

def normalize_date(date_str):
    """Return an ISO 8601 string so SQLite ORDER BY updated DESC sorts correctly.
    Handles RFC 2822 (RSS pubDate) and passes through anything already ISO-like."""
    if not date_str:
        return ""
    try:
        return parsedate_to_datetime(date_str).isoformat()
    except Exception:
        return date_str

FEEDS = {
    "PostHog": "https://posthog.com/rss.xml",
    "Linear": "https://linear.app/rss/changelog.xml",
    "Zapier": "https://zapier.com/blog/feeds/latest/",
    "Replit": "https://replit.com/blog/feed.xml",
}

conn = sqlite3.connect("releases.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT,
        title TEXT,
        department TEXT,
        location TEXT,
        url TEXT,
        date_found TEXT,
        UNIQUE(company, title, url)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT,
        job_id TEXT,
        title TEXT,
        department TEXT,
        location TEXT,
        team TEXT,
        snapshot_date TEXT,
        UNIQUE(company, job_id, snapshot_date)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS hiring_deltas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT,
        snapshot_date TEXT,
        open_roles INTEGER,
        delta INTEGER,
        note TEXT,
        UNIQUE(company, snapshot_date)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS hiring_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        summary_date TEXT,
        summary TEXT,
        UNIQUE(summary_date)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS blog_posts (
        id TEXT PRIMARY KEY,
        company TEXT,
        title TEXT,
        updated TEXT,
        link TEXT,
        summary TEXT,
        analogy TEXT,
        analogy_90s TEXT,
        analogy_genz TEXT,
        analogy_medieval TEXT,
        analogy_aifluff TEXT,
        analogy_plain TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS reddit_sentiment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT,
        summary TEXT,
        fetched_date TEXT,
        sources_json TEXT,
        raw_titles_json TEXT,
        UNIQUE(company, fetched_date)
    )
""")

for _col in ("sources_json", "raw_titles_json",
             "summary_90s", "summary_genz", "summary_medieval", "summary_aifluff"):
    try:
        cursor.execute(f"ALTER TABLE reddit_sentiment ADD COLUMN {_col} TEXT")
    except Exception:
        pass

# Add voice columns to existing databases that predate this schema
for col in ("analogy", "analogy_90s", "analogy_genz", "analogy_medieval", "analogy_aifluff", "analogy_plain"):
    try:
        cursor.execute(f"ALTER TABLE blog_posts ADD COLUMN {col} TEXT")
    except Exception:
        pass

conn.commit()

# Migrate existing blog_posts rows that have RFC 2822 dates to ISO 8601
for row_id, raw_date in cursor.execute("SELECT id, updated FROM blog_posts WHERE updated LIKE '%,%'").fetchall():
    cursor.execute("UPDATE blog_posts SET updated = ? WHERE id = ?", (normalize_date(raw_date), row_id))
conn.commit()

def get_ai_summary(title, content):
    if not ANTHROPIC_API_KEY:
        return "", ""

    if not content or len(content.strip()) < 20:
        return title, ""

    prompt = f"""You are summarizing a software release or blog post for a general audience.

Title: {title}
Content: {content[:2000]}

If you have very little information, write one short sentence based on the title alone. Do not ask for more content.

Respond ONLY with valid JSON, no markdown, no backticks, exactly this format:
{{"summary": "1-3 sentence plain English summary of what changed", "analogy": "one corny everyday analogy that describes the change in simple terms"}}"""

    data = json.dumps({
        "model": "claude-haiku-4-5",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
            text = result["content"][0]["text"]
            text = text.strip().replace("```json", "").replace("```", "").strip()
            parsed = json.loads(text)
            summary = parsed.get("summary", "")
            if re.search(r'no blog post content|no content was provided', summary, re.IGNORECASE):
                summary = ""
            return summary, parsed.get("analogy", "")
    except Exception as e:
        print(f"AI error: {e}")
        return "", ""

VOICE_PROMPTS = {
    "analogy_90s":      "Rewrite this analogy in late 90s R&B and hip hop slang. Use phrases like 'all that and a bag of chips', 'da bomb', 'feel me', 'no doubt', 'word', 'straight up', 'mad [adjective]', 'on the real', 'that joint is', 'for real for real'. One sentence, no quotes.",
    "analogy_genz":     "Rewrite this analogy in Gen Z slang — lowkey, slay, no cap, vibe check. One sentence, no quotes.",
    "analogy_medieval": "Rewrite this analogy as if proclaimed by a medieval town crier. One sentence, no quotes.",
    "analogy_aifluff":  "Rewrite this analogy as hollow AI corporate marketing speak — synergies, paradigms, leverage. One sentence, no quotes.",
    "analogy_plain":    "Rewrite this analogy as a plain, clear one or two sentence explanation a normal person would understand. No slang, no jargon, no style — just simple everyday language. No quotes.",
}

# NOTE: each new post triggers 5 extra API calls (one per voice) on top of the
# main summary call. Budget ~6 Haiku calls per new post at fetch time.
def get_voice_analogy(original_analogy, voice_instruction):
    if not ANTHROPIC_API_KEY or not original_analogy or original_analogy == "Analogy unavailable.":
        return ""

    prompt = f"{voice_instruction}\n\nOriginal: {original_analogy}"

    data = json.dumps({
        "model": "claude-haiku-4-5",
        "max_tokens": 120,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
            return re.sub(r'^#+\s*', '', result["content"][0]["text"].strip())
    except Exception as e:
        print(f"Voice analogy error: {e}")
        return ""

PULSE_VOICE_PROMPTS = {
    "summary_90s": (
        "Rewrite this community sentiment summary in late 90s R&B and hip hop slang. "
        "Use phrases like 'all that and a bag of chips', 'da bomb', 'feel me', 'no doubt', "
        "'word', 'straight up', 'mad [adjective]', 'on the real', 'for real for real'. "
        "3-4 sentences. No quotes. No em dashes."
    ),
    "summary_genz": (
        "Rewrite this community sentiment summary in Gen Z slang — lowkey, slay, no cap, "
        "understood the assignment, it's giving, rent free, bussin, based. "
        "3-4 sentences. No quotes. No em dashes."
    ),
    "summary_medieval": (
        "Rewrite this community sentiment summary as if proclaimed by a medieval town crier "
        "addressing the townspeople in the square. "
        "3-4 sentences. No quotes. No em dashes."
    ),
    "summary_aifluff": (
        "Rewrite this community sentiment summary as hollow AI corporate marketing speak — "
        "synergies, paradigms, leverage, ecosystem, disruptive, transformative, value proposition, "
        "best-in-class. 3-4 sentences. No quotes. No em dashes."
    ),
}

def get_pulse_voice_summary(plain_summary, voice_instruction):
    if not ANTHROPIC_API_KEY or not plain_summary or plain_summary == "Sentiment summary unavailable.":
        return ""

    prompt = f"{voice_instruction}\n\nOriginal summary:\n{plain_summary}"

    data = json.dumps({
        "model": "claude-haiku-4-5",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                result = json.loads(response.read())
                return re.sub(r'^#+\s*', '', result["content"][0]["text"].strip())
        except Exception as e:
            print(f"  Pulse voice error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(2)
    return ""

# Backfill base analogy for existing posts that predate this feature
_backfill = cursor.execute("""
    SELECT id, title, summary FROM blog_posts
    WHERE (analogy IS NULL OR analogy = '')
      AND summary IS NOT NULL AND summary != ''
""").fetchall()
if _backfill:
    print(f"Backfilling analogies for {len(_backfill)} posts...")
    for _row_id, _title, _summary in _backfill:
        _, _analogy = get_ai_summary(_title, _summary or _title)
        _voices = {col: get_voice_analogy(_analogy, instr) for col, instr in VOICE_PROMPTS.items()}
        cursor.execute("""
            UPDATE blog_posts
               SET analogy = ?, analogy_90s = ?, analogy_genz = ?,
                   analogy_medieval = ?, analogy_aifluff = ?, analogy_plain = ?
             WHERE id = ?
        """, (_analogy, _voices["analogy_90s"], _voices["analogy_genz"],
              _voices["analogy_medieval"], _voices["analogy_aifluff"], _voices["analogy_plain"], _row_id))
    conn.commit()
    print("Analogy backfill complete.")

# Backfill voice columns for posts that have a base analogy but are missing voice variants
_voice_backfill = cursor.execute("""
    SELECT id, analogy FROM blog_posts
    WHERE analogy IS NOT NULL AND analogy != ''
      AND (analogy_plain IS NULL OR analogy_plain = '')
""").fetchall()
if _voice_backfill:
    print(f"Backfilling voice analogies for {len(_voice_backfill)} posts...")
    for _row_id, _analogy in _voice_backfill:
        _voices = {col: get_voice_analogy(_analogy, instr) for col, instr in VOICE_PROMPTS.items()}
        cursor.execute("""
            UPDATE blog_posts
               SET analogy_90s = ?, analogy_genz = ?, analogy_medieval = ?, analogy_aifluff = ?, analogy_plain = ?
             WHERE id = ?
        """, (_voices["analogy_90s"], _voices["analogy_genz"],
              _voices["analogy_medieval"], _voices["analogy_aifluff"], _voices["analogy_plain"], _row_id))
    conn.commit()
    print("Voice backfill complete.")

REDDIT_SUBREDDITS = {
    "PostHog": "posthog",
    "Zapier":  "zapier",
    "Replit":  "replit",
    "Linear":  "linear",
}

_REDDIT_RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RSS reader)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}
_NS_ATOM = {"atom": "http://www.w3.org/2005/Atom"}

def _strip_html(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    for ent, ch in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&quot;','"'),('&#39;',"'"),('&nbsp;',' ')]:
        text = text.replace(ent, ch)
    return re.sub(r'\s+', ' ', text).strip()

def fetch_reddit_posts(subreddit):
    """Top posts from a subreddit via the public Atom RSS feed (no auth required).
    Fetches both week-top and month-top to get up to ~50 unique posts for small subreddits."""
    seen  = set()
    posts = []
    feeds = [
        f"https://www.reddit.com/r/{subreddit}/top.rss?t=week&limit=50",
        f"https://www.reddit.com/r/{subreddit}/top.rss?t=month&limit=50",
    ]
    for url in feeds:
        try:
            req = urllib.request.Request(url, headers=_REDDIT_RSS_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
            root = ET.fromstring(raw.decode("utf-8", errors="replace"))
            for entry in root.findall("atom:entry", _NS_ATOM):
                title_el   = entry.find("atom:title",   _NS_ATOM)
                content_el = entry.find("atom:content", _NS_ATOM)
                link_el    = entry.find("atom:link",    _NS_ATOM)
                title = sanitize_input((title_el.text or "").strip()) if title_el is not None else ""
                body  = _strip_html(content_el.text or "")            if content_el is not None else ""
                link  = link_el.get("href", "")                       if link_el is not None else ""
                if title and title not in seen:
                    seen.add(title)
                    posts.append({"title": title, "body": sanitize_input(body[:400]), "url": link})
            time.sleep(1)
        except Exception as e:
            print(f"    Reddit RSS error ({url}): {e}")
    return posts

_POSTHOG_STRAPI = "https://better-animal-d658c56969.strapiapp.com/api"

def fetch_posthog_questions(limit=50):
    """Recent questions from posthog.com/questions via their public Strapi API."""
    url = (f"{_POSTHOG_STRAPI}/questions"
           f"?fields[0]=subject&fields[1]=permalink&fields[2]=activeAt"
           f"&pagination[limit]={limit}&sort=activeAt:desc")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    posts = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        subject   = sanitize_input(attrs.get("subject", "").strip())
        permalink = attrs.get("permalink", "")
        if subject and permalink:
            posts.append({"title": subject, "body": "", "url": f"https://posthog.com/questions/{permalink}"})
    return posts

_ZAPIER_COMMUNITY_CATS = [
    "https://community.zapier.com/get-help-50",
    "https://community.zapier.com/troubleshooting-99",
    "https://community.zapier.com/how-do-i-3",
    "https://community.zapier.com/general-discussion-13",
]

def fetch_zapier_community(limit=50):
    """Recent posts from community.zapier.com via HTML scraping (entity-encoded JSON)."""
    posts = []
    seen  = set()
    for cat_url in _ZAPIER_COMMUNITY_CATS:
        req = urllib.request.Request(cat_url, headers={"User-Agent": "Mozilla/5.0 (compatible)"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"    Zapier category error ({cat_url}): {e}")
            continue
        pairs = re.findall(
            r'&quot;topicUrl&quot;:\{&quot;destination&quot;:&quot;((?:[^&]|&(?!quot;))+)&quot;\}'
            r'.{0,300}?&quot;title&quot;:&quot;((?:[^&]|&(?!quot;))+)&quot;,&quot;content&quot;:',
            html, re.DOTALL
        )
        for raw_url, raw_title in pairs:
            title = sanitize_input(unescape(raw_title).strip())
            url   = unescape(raw_url).replace("\\/", "/")
            if not title or title in seen:
                continue
            if title.lower().startswith("about the"):
                continue
            seen.add(title)
            posts.append({"title": title, "body": "", "url": url})
            if len(posts) >= limit:
                return posts
        time.sleep(1)
    return posts

def get_community_pulse_summary(company, all_posts):
    if not ANTHROPIC_API_KEY:
        return "Sentiment summary unavailable."

    lines = []
    for post in all_posts:
        lines.append(f"- {post['title']}")
        if post.get("body"):
            lines.append(f"  {post['body'][:300]}")

    content = "\n".join(lines)[:3500]

    prompt = f"""These are recent posts from {company}'s community forums and social channels:

{content}

Write 3-4 sentences summarizing community sentiment about {company}. Cover what users love, what frustrates them, any bugs or pain points, and overall tone. Be specific and direct. No headers, no bullet points, no markdown, no em dashes."""

    data = json.dumps({
        "model": "claude-haiku-4-5",
        "max_tokens": 250,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read())
            return re.sub(r'^#+\s*', '', result["content"][0]["text"].strip())
    except Exception as e:
        print(f"  Community pulse AI error: {e}")
        return "Sentiment summary unavailable."

def fetch_reddit_sentiment():
    today = date_cls.today().isoformat()
    for company, subreddit in REDDIT_SUBREDDITS.items():
        # Skip only if we already have a fully-populated row (with voice summaries) for today
        existing = cursor.execute(
            "SELECT id FROM reddit_sentiment WHERE company = ? AND fetched_date = ? "
            "AND sources_json IS NOT NULL AND summary_90s IS NOT NULL AND summary_90s != '' "
            "AND summary != 'Sentiment summary unavailable.'",
            (company, today)
        ).fetchone()
        if existing:
            print(f"  {company}: Community Pulse already fetched today, skipping.")
            continue

        print(f"Fetching community data for {company}...")
        sources   = []
        all_posts = []

        # Reddit (all companies)
        try:
            reddit_posts = fetch_reddit_posts(subreddit)
            print(f"  r/{subreddit}: {len(reddit_posts)} posts")
            if reddit_posts:
                sources.append({"name": f"r/{subreddit}",
                                "url":  f"https://www.reddit.com/r/{subreddit}/",
                                "count": len(reddit_posts)})
                all_posts.extend(reddit_posts)
            time.sleep(2)
        except Exception as e:
            print(f"  Reddit error: {e}")

        # PostHog questions (PostHog only)
        if company == "PostHog":
            try:
                ph_posts = fetch_posthog_questions(limit=50)
                print(f"  posthog.com/questions: {len(ph_posts)} posts")
                if ph_posts:
                    sources.append({"name": "posthog.com/questions",
                                    "url":  "https://posthog.com/questions",
                                    "count": len(ph_posts)})
                    all_posts.extend(ph_posts)
            except Exception as e:
                print(f"  PostHog questions error: {e}")

        # Zapier community (Zapier only)
        elif company == "Zapier":
            try:
                zap_posts = fetch_zapier_community(limit=50)
                print(f"  community.zapier.com: {len(zap_posts)} posts")
                if zap_posts:
                    sources.append({"name": "community.zapier.com",
                                    "url":  "https://community.zapier.com",
                                    "count": len(zap_posts)})
                    all_posts.extend(zap_posts)
            except Exception as e:
                print(f"  Zapier community error: {e}")

        if not all_posts:
            print(f"  No posts found for {company}, skipping.")
            continue

        summary    = get_community_pulse_summary(company, all_posts)
        raw_titles = [p["title"] for p in all_posts]

        print(f"  Generating voice summaries for {company}...")
        voices = {col: get_pulse_voice_summary(summary, instr)
                  for col, instr in PULSE_VOICE_PROMPTS.items()}

        # Replace any incomplete row from today with the fully-populated one
        cursor.execute("DELETE FROM reddit_sentiment WHERE company = ? AND fetched_date = ?",
                       (company, today))
        cursor.execute(
            """INSERT INTO reddit_sentiment
               (company, summary, fetched_date, sources_json, raw_titles_json,
                summary_90s, summary_genz, summary_medieval, summary_aifluff)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (company, summary, today, json.dumps(sources), json.dumps(raw_titles),
             voices["summary_90s"], voices["summary_genz"],
             voices["summary_medieval"], voices["summary_aifluff"])
        )
        conn.commit()
        print(f"  {company}: stored ({len(all_posts)} posts, {len(sources)} sources, 5 voices).")

ASHBY_SLUGS = {
    "PostHog": "posthog",
    "Linear": "linear",
    "Zapier": "zapier",
    "Replit": "replit",
}

def _str_field(val):
    if not val:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, dict):
        return (val.get("name") or val.get("title") or "").strip()
    return str(val).strip()

def _title_to_slug(title):
    """Normalise a job title to a URL slug for matching against posthog.com/careers/slug."""
    s = title.lower()
    s = re.sub(r'[—–]+', '-', s)        # em/en-dash → hyphen
    s = re.sub(r'[^a-z0-9]+', '-', s)   # everything else non-alphanumeric → hyphen
    s = re.sub(r'-+', '-', s)            # collapse runs
    return s.strip('-')

def _fetch_posthog_sitemap_urls():
    """Return a dict of {slug: full_url} from posthog.com/sitemap/sitemap-0.xml."""
    sitemap_url = "https://posthog.com/sitemap/sitemap-0.xml"
    req = urllib.request.Request(sitemap_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml = resp.read().decode("utf-8", errors="replace")
    urls = re.findall(r'<loc>(https://posthog\.com/careers/[^<]+)</loc>', xml)
    return {u.split("/careers/")[1]: u for u in urls}

def fetch_jobs():
    cursor.execute("DELETE FROM jobs")
    conn.commit()
    print("Jobs table cleared.")
    today = date_cls.today().isoformat()

    # Pre-fetch PostHog sitemap slug → URL map so we can use canonical career page URLs
    print("Fetching PostHog careers sitemap...")
    try:
        posthog_slug_map = _fetch_posthog_sitemap_urls()
        print(f"  Found {len(posthog_slug_map)} PostHog career URLs in sitemap.")
    except Exception as e:
        print(f"  Could not fetch PostHog sitemap ({e}), will fall back to Ashby URLs.")
        posthog_slug_map = {}

    for company, slug in ASHBY_SLUGS.items():
        print(f"Fetching jobs for {company}...")
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            jobs = data.get("jobs", [])
            count = 0
            for job in jobs:
                title = _str_field(job.get("title"))
                if not title:
                    continue
                department = (
                    _str_field(job.get("department")) or
                    _str_field(job.get("teamName")) or
                    _str_field(job.get("team"))
                )
                location = (
                    _str_field(job.get("locationName")) or
                    _str_field(job.get("location")) or
                    _str_field(job.get("primaryLocation"))
                )
                if company == "PostHog":
                    # Match Ashby title → posthog.com/careers/slug via sitemap
                    title_slug = _title_to_slug(title)
                    job_url = posthog_slug_map.get(title_slug,
                              f"https://posthog.com/careers#{job.get('id', '')}")
                else:
                    job_url = (
                        job.get("jobUrl") or job.get("hostedUrl") or
                        job.get("applyUrl") or job.get("url") or ""
                    )
                cursor.execute("""
                    INSERT OR IGNORE INTO jobs (company, title, department, location, url, date_found)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (company, title, department, location, job_url, today))
                count += 1
            conn.commit()
            print(f"  {company}: {count} jobs found.")
        except Exception as e:
            print(f"  Error fetching jobs for {company}: {e}")

# Fix existing entries where AI returned a complaint instead of a summary
_complaint_rows = cursor.execute("""
    SELECT id, title FROM blog_posts
    WHERE summary IS NOT NULL
      AND (
          LOWER(summary) LIKE "%i don't have%" OR
          LOWER(summary) LIKE "%i do not have%" OR
          LOWER(summary) LIKE "%i cannot%" OR
          LOWER(summary) LIKE "%i can't%" OR
          LOWER(summary) LIKE "%not enough%" OR
          LOWER(summary) LIKE "%please provide%" OR
          LOWER(summary) LIKE "%unable to%" OR
          LOWER(summary) LIKE "%i'm sorry%" OR
          LOWER(summary) LIKE "%i am sorry%" OR
          LOWER(summary) LIKE "%no content%" OR
          LOWER(summary) LIKE "%no information%"
      )
""").fetchall()
if _complaint_rows:
    print(f"Clearing {len(_complaint_rows)} complaint summaries...")
    for _row_id, _title in _complaint_rows:
        cursor.execute("""
            UPDATE blog_posts
               SET summary = ?, analogy = '',
                   analogy_90s = '', analogy_genz = '',
                   analogy_medieval = '', analogy_aifluff = '', analogy_plain = ''
             WHERE id = ?
        """, (_title, _row_id))
    conn.commit()
    print("Complaint summary cleanup done.")

# Fetch blog/changelog posts
for company, url in FEEDS.items():
    print(f"Fetching feed for {company}...")
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req) as response:
            tree = ET.parse(response)
            root = tree.getroot()

            ns_atom = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns_atom)

            if not entries:
                entries = root.findall(".//item")

            count = 0
            for entry in entries:
                if count >= 5:
                    break

                def get_text(tag):
                    found = entry.find(tag)
                    if found is not None and found.text:
                        return found.text.strip()
                    return ""

                # Sanitize raw feed fields before passing to AI (blocks prompt injection)
                title = sanitize_input(get_text("title"))
                link = get_text("link")
                updated = normalize_date(get_text("pubDate"))
                content = sanitize_input(get_text("description"))
                if not content:
                    # Fall back to content:encoded (used by Linear and similar feeds)
                    _encoded = entry.find("{http://purl.org/rss/1.0/modules/content/}encoded")
                    if _encoded is not None and _encoded.text:
                        _raw = re.sub(r'<[^>]+>', ' ', _encoded.text)
                        content = sanitize_input(re.sub(r'\s+', ' ', _raw).strip())
                entry_id = get_text("guid") or link

                if not title or not link:
                    continue

                existing = cursor.execute(
                    "SELECT id, analogy, analogy_plain FROM blog_posts WHERE id = ?", (entry_id,)
                ).fetchone()

                if existing is None:
                    print(f"  Getting AI summary for: {title}")
                    summary, analogy = get_ai_summary(title, content)
                    if not summary:
                        analogy = None
                    voices = {col: get_voice_analogy(analogy, instr) for col, instr in VOICE_PROMPTS.items()}
                    cursor.execute("""
                        INSERT OR IGNORE INTO blog_posts
                            (id, company, title, updated, link, summary, analogy,
                             analogy_90s, analogy_genz, analogy_medieval, analogy_aifluff, analogy_plain)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (entry_id, company,
                          sanitize_input(title), updated, link,
                          sanitize_input(summary), sanitize_input(analogy),
                          sanitize_input(voices["analogy_90s"]),
                          sanitize_input(voices["analogy_genz"]),
                          sanitize_input(voices["analogy_medieval"]),
                          sanitize_input(voices["analogy_aifluff"]),
                          sanitize_input(voices["analogy_plain"])))
                elif existing[1] is None or existing[1] == '' or existing[2] is None or existing[2] == '':
                    print(f"  Backfilling analogy for: {title}")
                    _, analogy = get_ai_summary(title, content)
                    if not analogy:
                        analogy = None
                    voices = {col: get_voice_analogy(analogy, instr) for col, instr in VOICE_PROMPTS.items()}
                    cursor.execute("""
                        UPDATE blog_posts SET analogy = ?,
                            analogy_90s = ?, analogy_genz = ?,
                            analogy_medieval = ?, analogy_aifluff = ?, analogy_plain = ?
                        WHERE id = ?
                    """, (sanitize_input(analogy),
                          sanitize_input(voices["analogy_90s"]),
                          sanitize_input(voices["analogy_genz"]),
                          sanitize_input(voices["analogy_medieval"]),
                          sanitize_input(voices["analogy_aifluff"]),
                          sanitize_input(voices["analogy_plain"]),
                          entry_id))

                count += 1

    except Exception as e:
        print(f"Error fetching {company}: {e}")

conn.commit()
fetch_jobs()

# ── daily job snapshot (copy from already-populated jobs table) ───────────────
_today = date_cls.today().isoformat()
_snap_rows = cursor.execute("SELECT company, title, department, location FROM jobs").fetchall()
for _company, _title, _dept, _loc in _snap_rows:
    _job_id = re.sub(r'\s+', '-', _title.lower())
    cursor.execute("""
        INSERT OR IGNORE INTO job_snapshots (company, job_id, title, department, location, team, snapshot_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (_company, _job_id, _title, _dept or "", _loc or "", "", _today))
conn.commit()
print(f"Job snapshots recorded for {_today}: {len(_snap_rows)} rows.")

def calculate_hiring_deltas(cursor, today):
    companies = ["PostHog", "Linear", "Zapier", "Replit"]
    for company in companies:
        today_count = cursor.execute("""
            SELECT COUNT(*) FROM job_snapshots
            WHERE company = ? AND snapshot_date = ?
        """, (company, today)).fetchone()[0]

        prev = cursor.execute("""
            SELECT snapshot_date, COUNT(*) as cnt FROM job_snapshots
            WHERE company = ? AND snapshot_date < ?
            GROUP BY snapshot_date
            ORDER BY snapshot_date DESC
            LIMIT 1
        """, (company, today)).fetchone()

        if prev:
            delta = today_count - prev[1]
            if delta > 0:
                note = f"+{delta} roles since {prev[0]}"
            elif delta < 0:
                note = f"{delta} roles since {prev[0]}"
            else:
                note = f"No change since {prev[0]}"
        else:
            delta = 0
            note = "First snapshot"

        cursor.execute("""
            INSERT OR IGNORE INTO hiring_deltas (company, snapshot_date, open_roles, delta, note)
            VALUES (?, ?, ?, ?, ?)
        """, (company, today, today_count, delta, note))

def generate_weekly_hiring_summary(cursor, today):
    from datetime import timedelta
    if date_cls.fromisoformat(today).weekday() != 0:
        return

    existing = cursor.execute("""
        SELECT id FROM hiring_summaries WHERE summary_date = ?
    """, (today,)).fetchone()
    if existing:
        return

    week_ago = (date_cls.fromisoformat(today) - timedelta(days=7)).isoformat()
    deltas = cursor.execute("""
        SELECT company, snapshot_date, open_roles, delta, note
        FROM hiring_deltas
        WHERE snapshot_date >= ?
        ORDER BY company, snapshot_date
    """, (week_ago,)).fetchall()

    if not deltas:
        return

    data_text = "\n".join([
        f"{company} on {snap_date}: {open_roles} open roles ({note})"
        for company, snap_date, open_roles, delta, note in deltas
    ])

    prompt = f"""Here is hiring data for 4 tech companies over the past week:

{data_text}

Write a 3-4 sentence plain English summary of what this hiring data suggests about each company. \
Be specific about numbers. Note any interesting patterns or signals. \
Do not use buzzwords or hype. Be direct and factual.
Do not use em dashes."""

    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps({
                "model": "claude-haiku-4-5",
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}]
            }).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        summary = data["content"][0]["text"]
        cursor.execute("""
            INSERT OR IGNORE INTO hiring_summaries (summary_date, summary)
            VALUES (?, ?)
        """, (today, summary))
        print(f"Weekly hiring summary generated for {today}")
    except Exception as e:
        print(f"Error generating hiring summary: {e}")

calculate_hiring_deltas(cursor, _today)
generate_weekly_hiring_summary(cursor, _today)
fetch_reddit_sentiment()

conn.commit()

print("\nVerification — first 3 PostHog job URLs:")
for row in cursor.execute(
    "SELECT title, url FROM jobs WHERE company='PostHog' ORDER BY title LIMIT 3"
).fetchall():
    print(f"  {row[0]} | {row[1]}")
conn.close()
print("Done!")
