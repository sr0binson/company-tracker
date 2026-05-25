import urllib.request
import xml.etree.ElementTree as ET
import sqlite3
import json
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

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
        analogy TEXT
    )
""")

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
                title = entry.find("atom:title", ns).text
                updated = entry.find("atom:updated", ns).text
                link = entry.find("atom:link", ns).attrib.get("href", "")
                content_el = entry.find("atom:content", ns)
                content = content_el.text if content_el is not None else ""

                existing = cursor.execute(
                    "SELECT summary FROM releases WHERE id = ?", (entry_id,)
                ).fetchone()

                if existing is None:
                    print(f"  Getting AI summary for: {title}")
                    summary, analogy = get_ai_summary(title, content or title)
                    cursor.execute("""
                        INSERT OR IGNORE INTO releases (id, company, title, updated, link, summary, analogy)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (entry_id, company, title, updated, link, summary, analogy))
                elif existing[0] is None or existing[0] == "":
                    print(f"  Backfilling AI summary for: {title}")
                    summary, analogy = get_ai_summary(title, content or title)
                    cursor.execute("""
                        UPDATE releases SET summary = ?, analogy = ? WHERE id = ?
                    """, (summary, analogy, entry_id))

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

                title = get_text("title")
                link = get_text("link")
                updated = get_text("pubDate")
                content = get_text("description")
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
                    """, (entry_id, company, title, updated, link, summary))

                count += 1

    except Exception as e:
        print(f"Error fetching blog for {company}: {e}")

conn.commit()
conn.close()
print("Done!")