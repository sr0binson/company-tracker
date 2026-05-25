import sqlite3
import urllib.request
import xml.etree.ElementTree as ET

# Company GitHub releases Atom feeds
feeds = [
    {"company": "PostHog", "url": "https://github.com/PostHog/posthog/releases.atom"},
    {"company": "Zapier", "url": "https://github.com/zapier/zapier-platform/releases.atom"},
    {"company": "Replit", "url": "https://github.com/replit/desktop/releases.atom"},
    {"company": "Linear", "url": "https://github.com/linear/linear/releases.atom"},
]

ns = {"atom": "http://www.w3.org/2005/Atom"}

conn = sqlite3.connect("releases.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS releases (
        company TEXT,
        title TEXT,
        updated TEXT,
        link TEXT
    )
""")

for feed in feeds:
    print(f"Fetching {feed['company']}...")
    response = urllib.request.urlopen(feed["url"])
    xml_data = response.read()
    tree = ET.fromstring(xml_data)

    for entry in tree.findall("atom:entry", ns):
        title = entry.find("atom:title", ns).text
        updated = entry.find("atom:updated", ns).text
        link = entry.find("atom:link", ns).attrib["href"]
        existing = cursor.execute("SELECT * FROM releases WHERE link = ?", (link,)).fetchone()
        if not existing:
            cursor.execute("INSERT INTO releases VALUES (?, ?, ?, ?)", (feed["company"], title, updated, link))

conn.commit()
conn.close()
print("Done! Data saved to releases.db")
