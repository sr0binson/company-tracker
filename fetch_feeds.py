import urllib.request
import xml.etree.ElementTree as ET
import sqlite3
import json
import os
import re
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
    "PostHog": "https://github.com/PostHog/posthog/releases.atom",
    "Zapier": "https://github.com/zapier/zapier-platform/releases.atom",
    "Replit": "https://github.com/replit/desktop/releases.atom",
    "Linear": "https://github.com/linear/linear/releases.atom",
}

BLOG_FEEDS = {
    "PostHog": "https://posthog.com/rss.xml",
    "Zapier": "https://zapier.com/blog/feeds/latest/",
    "Replit": "https://blog.replit.com/feed.xml",
    "Linear": "https://linear.app/rss/changelog.xml",
}

conn = sqlite3.connect("releases.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS releases (
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
for col in ("analogy_90s", "analogy_genz", "analogy_medieval", "analogy_aifluff", "analogy_plain"):
    try:
        cursor.execute(f"ALTER TABLE releases ADD COLUMN {col} TEXT")
    except Exception:
        pass

cursor.execute("""
    CREATE TABLE IF NOT EXISTS blog_posts (
        id TEXT PRIMARY KEY,
        company TEXT,
        title TEXT,
        updated TEXT,
        link TEXT,
        summary TEXT
    )
""")

conn.commit()

# Migrate existing blog_posts rows that have RFC 2822 dates to ISO 8601
for row_id, raw_date in cursor.execute("SELECT id, updated FROM blog_posts WHERE updated LIKE '%,%'").fetchall():
    cursor.execute("UPDATE blog_posts SET updated = ? WHERE id = ?", (normalize_date(raw_date), row_id))
conn.commit()

def get_ai_summary(title, content):
    if not ANTHROPIC_API_KEY:
        return "Summary unavailable.", "Analogy unavailable."
    
    prompt = f"""You are summarizing a software release for a general audience.

Release title: {title}
Release notes: {content[:2000]}

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

# NOTE: each new release triggers 5 extra API calls (one per voice) on top of the
# main summary call. Budget ~6 Haiku calls per new release at fetch time.
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

def get_blog_summary(title, content):
    if not ANTHROPIC_API_KEY:
        return "Summary unavailable."
    
    prompt = f"""Summarize this blog post in 2 sentences for a general audience.

Title: {title}
Content: {content[:1500]}

Respond ONLY with valid JSON, no markdown, no backticks, exactly this format:
{{"summary": "2 sentence plain English summary"}}"""

    data = json.dumps({
        "model": "claude-haiku-4-5",
        "max_tokens": 150,
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
            return parsed.get("summary", "")
    except Exception as e:
        print(f"AI error: {e}")
        return "Summary unavailable."

# Backfill voice analogies for existing releases that predate this feature
_backfill = cursor.execute("""
    SELECT id, analogy FROM releases
    WHERE analogy IS NOT NULL AND analogy != ''
      AND (analogy_plain IS NULL OR analogy_plain = '')
""").fetchall()
if _backfill:
    print(f"Backfilling voice analogies for {len(_backfill)} releases...")
    for _row_id, _analogy in _backfill:
        _voices = {col: get_voice_analogy(_analogy, instr) for col, instr in VOICE_PROMPTS.items()}
        cursor.execute("""
            UPDATE releases
               SET analogy_90s = ?, analogy_genz = ?, analogy_medieval = ?, analogy_aifluff = ?, analogy_plain = ?
             WHERE id = ?
        """, (_voices["analogy_90s"], _voices["analogy_genz"],
              _voices["analogy_medieval"], _voices["analogy_aifluff"], _voices["analogy_plain"], _row_id))
    conn.commit()
    print("Backfill complete.")

# Fetch GitHub releases
for company, url in FEEDS.items():
    print(f"Fetching releases for {company}...")
    try:
        with urllib.request.urlopen(url) as response:
            tree = ET.parse(response)
            root = tree.getroot()
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                entry_id = entry.find("atom:id", ns).text
                # Sanitize raw feed fields before passing to AI (blocks prompt injection)
                title = sanitize_input(entry.find("atom:title", ns).text)
                updated = entry.find("atom:updated", ns).text
                link = entry.find("atom:link", ns).attrib.get("href", "")
                content_el = entry.find("atom:content", ns)
                content = sanitize_input(content_el.text if content_el is not None else "")

                existing = cursor.execute(
                    "SELECT summary FROM releases WHERE id = ?", (entry_id,)
                ).fetchone()

                if existing is None:
                    print(f"  Getting AI summary for: {title}")
                    summary, analogy = get_ai_summary(title, content or title)
                    voices = {col: get_voice_analogy(analogy, instr) for col, instr in VOICE_PROMPTS.items()}
                    cursor.execute("""
                        INSERT OR IGNORE INTO releases
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
                elif existing[0] is None or existing[0] == "":
                    print(f"  Backfilling AI summary for: {title}")
                    summary, analogy = get_ai_summary(title, content or title)
                    voices = {col: get_voice_analogy(analogy, instr) for col, instr in VOICE_PROMPTS.items()}
                    cursor.execute("""
                        UPDATE releases SET summary = ?, analogy = ?,
                            analogy_90s = ?, analogy_genz = ?,
                            analogy_medieval = ?, analogy_aifluff = ?, analogy_plain = ?
                        WHERE id = ?
                    """, (sanitize_input(summary), sanitize_input(analogy),
                          sanitize_input(voices["analogy_90s"]),
                          sanitize_input(voices["analogy_genz"]),
                          sanitize_input(voices["analogy_medieval"]),
                          sanitize_input(voices["analogy_aifluff"]),
                          sanitize_input(voices["analogy_plain"]),
                          entry_id))

    except Exception as e:
        print(f"Error fetching {company}: {e}")

# Fetch blog/changelog posts
for company, url in BLOG_FEEDS.items():
    print(f"Fetching blog for {company}...")
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
                    "SELECT id FROM blog_posts WHERE id = ?", (entry_id,)
                ).fetchone()

                if existing is None:
                    print(f"  Getting AI summary for blog: {title}")
                    summary = get_blog_summary(title, content or title)
                    cursor.execute("""
                        INSERT OR IGNORE INTO blog_posts (id, company, title, updated, link, summary)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (entry_id, company,
                          sanitize_input(title), updated, link,
                          sanitize_input(summary)))

                count += 1

    except Exception as e:
        print(f"Error fetching blog for {company}: {e}")

conn.commit()
conn.close()
print("Done!")