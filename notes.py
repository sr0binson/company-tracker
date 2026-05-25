# NOTES ON FETCH_FEEDS.PY
# Plain english explanations of what each part does

# --- IMPORTS ---
# import sqlite3
# SQLite is a mini database that lives as a single file on your computer.
# Importing it is like grabbing a toolbox so Python can talk to that database.

# import urllib.request
# This lets Python go out to the internet and fetch a webpage or file.
# Think of it like sending your dog to go pick up the newspaper.

# import xml.etree.ElementTree as ET
# GitHub releases are stored in a format called XML, which looks like HTML but for data.
# This tool reads that XML and lets us dig through it.
# "ET" is just a nickname so we don't have to type the whole thing every time.

# --- THE FEEDS LIST ---
# feeds = [...]
# This is our list of companies we want to track.
# Each company has a name and a URL pointing to their GitHub releases page.
# Think of it like a list of RSS subscriptions in an old school feed reader.
# Adding a new company later is as easy as adding a new line here.

# --- NAMESPACE ---
# ns = {"atom": "http://www.w3.org/2005/Atom"}
# Atom is the format GitHub uses for release feeds, like a specific dialect of XML.
# This line just tells Python which dialect we're reading so it can find the right data.
# Think of it like telling someone "we're reading a UK English document" before they start.

# --- DATABASE SETUP ---
# conn = sqlite3.connect("releases.db")
# This opens the database file called releases.db.
# If it doesn't exist yet, it creates it. Like opening a notebook, or making a new one if you don't have one.

# cursor = conn.cursor()
# The cursor is how we actually talk to the database.
# Think of it like a pen. The notebook is open (conn), but you need a pen (cursor) to write in it.

# --- CREATING THE TABLE ---
# cursor.execute("CREATE TABLE IF NOT EXISTS releases (...)")
# A table is like a spreadsheet inside the database with columns and rows.
# Our columns are: company, title, updated, link.
# "IF NOT EXISTS" means don't freak out if the table is already there, just skip it.

# --- THE LOOP ---
# for feed in feeds:
# This says "go through each company in our list one at a time and do the same thing for each."
# Like going down a to-do list and checking off each item.

# urllib.request.urlopen(feed["url"])
# This is the dog fetching the newspaper. It goes to the URL and grabs whatever is there.

# ET.fromstring(xml_data)
# This takes the raw XML data and turns it into something Python can actually navigate.
# Like taking a big block of text and turning it into a structured outline.

# --- LOOPING THROUGH ENTRIES ---
# for entry in tree.findall("atom:entry", ns):
# Each "entry" is one release. This loops through all of them.
# Like flipping through each page of a magazine.

# entry.find("atom:title", ns).text
# Grabs the title of the release. Like reading the headline of an article.

# entry.find("atom:updated", ns).text
# Grabs the date the release was published.

# entry.find("atom:link", ns).attrib["href"]
# Grabs the URL link to that specific release page.

# --- DUPLICATE CHECK ---
# cursor.execute("SELECT * FROM releases WHERE link = ?", (link,))
# Before saving anything, we check if that link is already in the database.
# No point saving the same release twice.
# Like checking if you already wrote something in your notebook before writing it again.

# --- SAVING ---
# cursor.execute("INSERT INTO releases VALUES (?, ?, ?, ?)", (...))
# If it's a new release, we write it into the database.

# conn.commit()
# This actually saves everything. Like hitting save on a Word doc.
# Without this, all your changes disappear when the script ends.

# conn.close()
# Close the database when we're done. Like closing the notebook and putting it away.
