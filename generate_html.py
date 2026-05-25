import sqlite3

conn = sqlite3.connect("releases.db")
cursor = conn.cursor()

releases = cursor.execute("""
    SELECT company, title, updated, link 
    FROM releases 
    ORDER BY updated DESC
""").fetchall()

conn.close()

company_colors = {
    "PostHog": "#E8E0D0",
    "Zapier": "#FF7A3D",
    "Replit": "#AAAAAA",
    "Linear": "#8B94E0",
}

company_text_colors = {
    "PostHog": "#111111",
    "Zapier": "#111111",
    "Replit": "#111111",
    "Linear": "#111111",
}

html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Company Tracker</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #f9f9f9; }
        h1 { font-size: 1.8rem; margin-bottom: 4px; }
        p.subtitle { color: #666; margin-top: 0; }
        .release { background: white; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .company { font-size: 0.75rem; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; color: #888; }
        .title a { text-decoration: none; color: #111; font-size: 1rem; font-weight: 600; }
        .title a:hover { text-decoration: underline; }
        .date { font-size: 0.8rem; color: #aaa; margin-top: 4px; }
    </style>
</head>
<body>
    <h1>Company Tracker</h1>
    <p class="subtitle">Latest releases from companies I want to work for.</p>
"""

for company, title, updated, link in releases:
    date = updated[:10]
    html += f"""
    <div class="release">
        <div class="company" style="background:{company_colors.get(company, '#eee')}; color:{company_text_colors.get(company, '#111')}; display:inline-block; padding:2px 8px; border-radius:20px;">{company}</div>
        <div class="title"><a href="{link}" target="_blank">{title}</a></div>
        <div class="date">{date}</div>
    </div>
"""

html += """
</body>
</html>
"""

with open("index.html", "w") as f:
    f.write(html)

print("Done! index.html generated.")
