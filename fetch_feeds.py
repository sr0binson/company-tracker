import sqlite3
import urllib.request
import xml.etree.ElementTree as ET

# PostHog GitHub releases Atom feed
url = "https://github.com/PostHog/posthog/releases.atom"

# Namespace for Atom feeds
ns = {"atom": "http://www.w3.org/2005/Atom"}

# Fetch the feed
response = urllib.request.urlopen(url)
xml_data = response.read()

# Parse the XML
tree = ET.fromstring(xml_data)

# Open the database (creates it if it doesn't exist)
conn = sqlite3.connect("releases.db")
cursor = conn.cursor()

# Create the table if it doesn't exist yet
cursor.execute("""
    CREATE TABLE IF NOT EXISTS releases (
        title TEXT,
        updated TEXT,
        link TEXT
    )
""")

# Find all entries
for entry in tree.findall("atom:entry", ns):
    title = entry.find("atom:title", ns).text
    updated = entry.find("atom:updated", ns).text
    link = entry.find("atom:link", ns).attrib["href"]
    existing = cursor.execute("SELECT * FROM releases WHERE link = ?", (link,)).fetchone()
    if not existing:
        cursor.execute("INSERT INTO releases VALUES (?, ?, ?)", (title, updated, link))

conn.commit()
conn.close()
print("Done! Data saved to releases.db")