import urllib.request
import xml.etree.ElementTree as ET
import sqlite3
import json
import os
import re
from datetime import date as date_cls
from email.utils import parsedate_to_datetime
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
    "Replit": "https://blog.replit.com/feed.xml",
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
        return "Summary unavailable.", "Analogy unavailable."

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
            return parsed.get("summary", ""), parsed.get("analogy", "")
    except Exception as e:
        print(f"AI error: {e}")
        return "Summary unavailable.", "Analogy unavailable."

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
    if not ANTHROPIC_API_KEY or not original_analogy:
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
            return result["content"][0]["text"].strip()
    except Exception as e:
        print(f"Voice analogy error: {e}")
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

def fetch_jobs():
    today = date_cls.today().isoformat()
    for company, slug in ASHBY_SLUGS.items():
        cursor.execute("DELETE FROM jobs WHERE company = ?", (company,))
        conn.commit()
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
        with urllib.request.urlopen(url) as response:
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
                entry_id = get_text("guid") or link

                if not title or not link:
                    continue

                existing = cursor.execute(
                    "SELECT id, analogy FROM blog_posts WHERE id = ?", (entry_id,)
                ).fetchone()

                if existing is None:
                    print(f"  Getting AI summary for: {title}")
                    summary, analogy = get_ai_summary(title, content)
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
                elif existing[1] is None or existing[1] == '':
                    print(f"  Backfilling analogy for: {title}")
                    _, analogy = get_ai_summary(title, content)
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
conn.close()
print("Done!")
