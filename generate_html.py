import sqlite3

conn = sqlite3.connect("releases.db")
cursor = conn.cursor()

releases = cursor.execute("""
    SELECT company, title, updated, link, summary, analogy
    FROM releases 
    ORDER BY updated DESC
""").fetchall()

blog_posts = cursor.execute("""
    SELECT company, title, updated, link, summary
    FROM blog_posts
    ORDER BY updated DESC
""").fetchall()

conn.close()

company_colors = {
    "PostHog": "#E8E0D0",
    "Zapier": "#FF7A3D",
    "Replit": "#AAAAAA",
    "Linear": "#8B94E0",
}

by_company = {}
for company, title, updated, link, summary, analogy in releases:
    if company not in by_company:
        by_company[company] = []
    by_company[company].append((title, updated, link, summary, analogy))

blog_by_company = {}
for company, title, updated, link, summary in blog_posts:
    if company not in blog_by_company:
        blog_by_company[company] = []
    if len(blog_by_company[company]) < 5:
        blog_by_company[company].append((title, updated, link, summary))

html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Company Tracker</title>
    <link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Sora', sans-serif; max-width: 1100px; margin: 40px auto; padding: 0 20px; background: #f9f9f9; }
        h1 { font-size: 1rem; font-weight: 300; text-align: left; margin-bottom: 0; }
        .heading { font-size: 3rem; font-weight: 700; margin-top: 4rem; line-height: 1.2; margin-bottom: 3rem; }
        .heading span { display: block; }
        .heading .line1 { text-align: left; padding-left: 15%; }
        .heading .line2 { text-align: center; }

        .company-row { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; align-items: start; }

        .company-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            cursor: pointer;
            transition: box-shadow 0.2s ease;
        }
        .company-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.12); }

        .company-tag {
            display: inline-block;
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 3px 10px;
            border-radius: 20px;
            margin-bottom: 8px;
        }
        .card-label { font-size: 0.8rem; color: #888; margin-bottom: 4px; }
        .card-hint { font-size: 0.75rem; color: #bbb; }

        /* Release expand */
        .releases-list {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.4s ease;
        }
        .release-item { padding: 10px 0; border-top: 1px solid #f0f0f0; }
        .release-item a { text-decoration: none; color: #111; font-size: 0.9rem; font-weight: 600; }
        .release-item a:hover { text-decoration: underline; }
        .release-date { font-size: 0.72rem; color: #aaa; margin-top: 2px; }
        .release-summary { font-size: 0.82rem; color: #555; margin-top: 6px; line-height: 1.5; }
        .release-analogy { font-size: 0.78rem; color: #888; margin-top: 4px; font-style: italic; }

        /* Blog flip card */
        .blog-flip-container { position: relative; min-height: 120px; }
        .blog-card-inner {
            position: relative;
            width: 100%;
        }
        .blog-slide { display: none; }
        .blog-slide.active { display: block; }
        .blog-slide-title a {
            text-decoration: none;
            color: #111;
            font-size: 0.88rem;
            font-weight: 600;
            line-height: 1.4;
        }
        .blog-slide-title a:hover { text-decoration: underline; }
        .blog-slide-summary { font-size: 0.8rem; color: #666; margin-top: 6px; line-height: 1.5; }
        .blog-slide-date { font-size: 0.72rem; color: #aaa; margin-top: 4px; }
        .blog-indicator {
            font-size: 0.72rem;
            color: #bbb;
            margin-top: 12px;
            text-align: right;
        }
        .blog-nav {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
        }
        .blog-nav button {
            background: none;
            border: 1px solid #eee;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 0.75rem;
            cursor: pointer;
            color: #888;
            font-family: 'Sora', sans-serif;
        }
        .blog-nav button:hover { background: #f5f5f5; }
    </style>
</head>
<body>
    <h1>Company Tracker</h1>
    <div class="heading">
        <span class="line1">Cool Companies,</span>
        <span class="line2">Fresh Releases.</span>
    </div>
    <div>
"""

for company in ["PostHog", "Linear", "Zapier", "Replit"]:
    color = company_colors.get(company, '#eee')
    company_releases = by_company.get(company, [])
    company_blogs = blog_by_company.get(company, [])
    card_id = company.lower().replace(" ", "-")

    html += '<div class="company-row">'

    # Left: releases card
    html += f"""
    <div class="company-card" onclick="toggleReleases('{card_id}')">
        <div class="company-tag" style="background:{color}; color:#111;">{company}</div>
        <div class="card-label">Releases</div>
        <div class="card-hint" id="hint-{card_id}">click to expand</div>
        <div id="releases-{card_id}" class="releases-list">
    """

    for title, updated, link, summary, analogy in company_releases:
        date = updated[:10] if updated else ""
        summary_html = f'<div class="release-summary">{summary}</div>' if summary else ""
        analogy_html = f'<div class="release-analogy">"{analogy}"</div>' if analogy else ""
        html += f"""
            <div class="release-item">
                <a href="{link}" target="_blank">{title}</a>
                <div class="release-date">{date}</div>
                {summary_html}
                {analogy_html}
            </div>
        """

    html += "</div></div>"

    # Right: blog card
    html += f"""
    <div class="company-card" onclick="event.stopPropagation()">
        <div class="company-tag" style="background:{color}; color:#111;">{company}</div>
        <div class="card-label">Blog & Changelog</div>
        <div class="blog-flip-container">
            <div class="blog-card-inner" id="blog-{card_id}">
    """

    if company_blogs:
        for i, (title, updated, link, summary) in enumerate(company_blogs):
            date = updated[:10] if updated else ""
            active = "active" if i == 0 else ""
            html += f"""
                <div class="blog-slide {active}" data-index="{i}">
                    <div class="blog-slide-title"><a href="{link}" target="_blank">{title}</a></div>
                    <div class="blog-slide-summary">{summary or ''}</div>
                    <div class="blog-slide-date">{date}</div>
                </div>
            """
        total = len(company_blogs)
        html += f"""
            </div>
            <div class="blog-nav">
                <button onclick="event.stopPropagation(); blogNav('{card_id}', -1)">&#8592; prev</button>
                <span class="blog-indicator" id="indicator-{card_id}">1 of {total}</span>
                <button onclick="event.stopPropagation(); blogNav('{card_id}', 1)">next &#8594;</button>
            </div>
        """
    else:
        html += """
            </div>
            <div style="color:#bbb; font-size:0.85rem; margin-top:8px;">Coming soon</div>
        """

    html += "</div></div>"
    html += "</div>"

html += """
    </div>
    <script>
        function toggleReleases(id) {
            var list = document.getElementById('releases-' + id);
            var hint = document.getElementById('hint-' + id);
            if (list.style.maxHeight && list.style.maxHeight !== '0px') {
                list.style.maxHeight = '0px';
                hint.textContent = 'click to expand';
            } else {
                list.style.maxHeight = list.scrollHeight + 'px';
                hint.textContent = 'click to collapse';
            }
        }

        function blogNav(id, dir) {
            var container = document.getElementById('blog-' + id);
            var slides = container.querySelectorAll('.blog-slide');
            var indicator = document.getElementById('indicator-' + id);
            var current = 0;
            slides.forEach(function(s, i) { if (s.classList.contains('active')) current = i; });
            slides[current].classList.remove('active');
            var next = (current + dir + slides.length) % slides.length;
            slides[next].classList.add('active');
            indicator.textContent = (next + 1) + ' of ' + slides.length;
        }
    </script>
</body>
</html>
"""

with open("index.html", "w") as f:
    f.write(html)

print("Done! index.html generated.")