import sqlite3
import json
import re
import math
import random
import calendar
from collections import Counter
from datetime import date as date_cls

conn = sqlite3.connect("releases.db")
cursor = conn.cursor()

for col in ("analogy", "analogy_90s", "analogy_genz", "analogy_medieval", "analogy_aifluff", "analogy_plain"):
    try:
        cursor.execute(f"ALTER TABLE blog_posts ADD COLUMN {col} TEXT")
    except Exception:
        pass
conn.commit()

posts = cursor.execute("""
    SELECT company, title, updated, link, summary, analogy,
           analogy_90s, analogy_genz, analogy_medieval, analogy_aifluff, analogy_plain
    FROM blog_posts
    ORDER BY updated DESC
""").fetchall()

all_posts_for_stats = cursor.execute(
    "SELECT company, title, updated, summary FROM blog_posts WHERE title != ''"
).fetchall()

try:
    jobs_rows = cursor.execute(
        "SELECT company, department, title, url FROM jobs ORDER BY company, department, title"
    ).fetchall()
except Exception:
    jobs_rows = []

try:
    releases_rows = cursor.execute(
        "SELECT company, summary FROM releases WHERE summary IS NOT NULL AND summary != ''"
    ).fetchall()
except Exception:
    releases_rows = []

try:
    hiring_data = cursor.execute("""
        SELECT company, snapshot_date, COUNT(*) as open_roles
        FROM job_snapshots
        GROUP BY company, snapshot_date
        ORDER BY snapshot_date ASC
    """).fetchall()
except Exception:
    hiring_data = []

try:
    hiring_deltas = cursor.execute("""
        SELECT company, snapshot_date, open_roles, delta, note
        FROM hiring_deltas
        ORDER BY snapshot_date DESC, company
    """).fetchall()
except Exception:
    hiring_deltas = []

try:
    latest_summary = cursor.execute("""
        SELECT summary_date, summary FROM hiring_summaries
        ORDER BY summary_date DESC
        LIMIT 1
    """).fetchone()
except Exception:
    latest_summary = None

try:
    ticker_posts = cursor.execute("""
        SELECT company, title, link
        FROM blog_posts
        ORDER BY updated DESC
        LIMIT 20
    """).fetchall()
except Exception:
    ticker_posts = []

try:
    reddit_rows = cursor.execute("""
        SELECT company, summary FROM reddit_sentiment
        WHERE fetched_date = (SELECT MAX(fetched_date) FROM reddit_sentiment WHERE company = reddit_sentiment.company)
        GROUP BY company
    """).fetchall()
    reddit_sentiment_by_company = {company: summary for company, summary in reddit_rows}
except Exception:
    reddit_sentiment_by_company = {}

conn.close()

# ── helpers ──────────────────────────────────────────────────────────────────

def html_escape(s):
    if not s:
        return ''
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;').replace("'", '&#39;'))

def lighten_hex(hex_color, factor=0.45):
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return '#{:02x}{:02x}{:02x}'.format(
        min(255, int(r + (255 - r) * factor)),
        min(255, int(g + (255 - g) * factor)),
        min(255, int(b + (255 - b) * factor)),
    )

_FEATURE_WORDS = {
    'adds','add','new','introduces','introduce','launch','launches','enable','enables',
    'expand','expands','implement','implements','create','creates','allow','allows',
    'brings','provide','provides','major','feature','features','support','supports',
    'significant','offer','offers','debut','debuts','ship','ships',
}
_BUGFIX_WORDS = {
    'fix','fixes','fixed','bug','bugs','patch','patches','patched','resolve','resolves',
    'resolved','correct','corrects','corrected','error','errors','issue','issues',
    'address','addresses','addressed','vulnerability','vulnerabilities','cve','security',
}
_MAINT_WORDS = {
    'update','updates','updated','dependency','dependencies','maintenance','bump','bumps',
    'upgrade','upgrades','upgraded','routine','minor','refactor','refactors','cleanup',
    'compatibility','incremental','version','build','builds',
}

def classify_release(text):
    if not text:
        return 'maintenance'
    words = set(re.findall(r'\b\w+\b', text.lower()))
    b = len(words & _BUGFIX_WORDS)
    f = len(words & _FEATURE_WORDS)
    m = len(words & _MAINT_WORDS)
    if b >= f and b > 0:
        return 'bugfix'
    if f > 0:
        return 'feature'
    return 'maintenance'

def pie_chart_svg(counts, feat_color, bug_color, maint_color='#cccccc', size=72):
    total = sum(counts.values())
    cx = cy = size / 2
    r = size / 2 - 3
    ir = r * 0.52
    if total == 0:
        return (f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#eee"/>'
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{ir:.1f}" fill="white"/></svg>')
    color_map = {'feature': feat_color, 'bugfix': bug_color, 'maintenance': maint_color}
    parts = [f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}">']
    start = -math.pi / 2
    for key in ['feature', 'bugfix', 'maintenance']:
        count = counts.get(key, 0)
        if count == 0:
            continue
        angle = (count / total) * 2 * math.pi
        if angle >= 2 * math.pi - 0.001:
            parts.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" '
                         f'fill="{color_map[key]}" stroke="white" stroke-width="1"/>')
        else:
            end = start + angle
            x1o = cx + r * math.cos(start);  y1o = cy + r * math.sin(start)
            x2o = cx + r * math.cos(end);    y2o = cy + r * math.sin(end)
            x1i = cx + ir * math.cos(end);   y1i = cy + ir * math.sin(end)
            x2i = cx + ir * math.cos(start); y2i = cy + ir * math.sin(start)
            la = 1 if angle > math.pi else 0
            d = (f'M {x1o:.2f} {y1o:.2f} A {r:.2f} {r:.2f} 0 {la} 1 {x2o:.2f} {y2o:.2f} '
                 f'L {x1i:.2f} {y1i:.2f} A {ir:.2f} {ir:.2f} 0 {la} 0 {x2i:.2f} {y2i:.2f} Z')
            parts.append(f'<path d="{d}" fill="{color_map[key]}" stroke="white" stroke-width="1.2"/>')
            start = end
    parts.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{ir:.2f}" fill="white"/>')
    parts.append('</svg>')
    return ''.join(parts)

# ── static config ─────────────────────────────────────────────────────────────

company_colors = {
    "PostHog": "#E8E0D0",
    "Zapier":  "#FF7A3D",
    "Replit":  "#AAAAAA",
    "Linear":  "#8B94E0",
}
company_accent = {
    "PostHog": "#C06820",
    "Zapier":  "#E05515",
    "Replit":  "#777777",
    "Linear":  "#6B73CC",
}

WHO_THEY_SERVE = {
    "PostHog": ["devs", "product teams", "startups", "growth companies"],
    "Linear":  ["software teams", "product engineers", "design startups"],
    "Zapier":  ["small businesses", "ops teams", "solopreneurs", "non-technical users"],
    "Replit":  ["students", "beginner devs", "educators", "indie hackers"],
}
COMPETITORS = {
    "PostHog": ["Mixpanel", "Amplitude", "Heap", "FullStory", "LaunchDarkly"],
    "Linear":  ["Jira", "Asana", "GitHub Issues", "Shortcut"],
    "Zapier":  ["Make", "n8n", "Workato", "Power Automate"],
    "Replit":  ["GitHub Codespaces", "Glitch", "CodeSandbox", "Cursor"],
}
COMPETITOR_URLS = {
    "Mixpanel":         "https://mixpanel.com",
    "Amplitude":        "https://amplitude.com",
    "Heap":             "https://heap.io",
    "FullStory":        "https://www.fullstory.com",
    "LaunchDarkly":     "https://launchdarkly.com",
    "Jira":             "https://www.atlassian.com/software/jira",
    "Asana":            "https://asana.com",
    "GitHub Issues":    "https://github.com/features/issues",
    "Shortcut":         "https://shortcut.com",
    "Make":             "https://www.make.com",
    "n8n":              "https://n8n.io",
    "Workato":          "https://www.workato.com",
    "Power Automate":   "https://powerautomate.microsoft.com",
    "GitHub Codespaces":"https://github.com/features/codespaces",
    "Glitch":           "https://glitch.com",
    "CodeSandbox":      "https://codesandbox.io",
    "Cursor":           "https://cursor.com",
}

# ── data preparation ──────────────────────────────────────────────────────────

posts_by_company = {}
for company, title, updated, link, summary, analogy, a90s, agenz, amedieval, aaifluff, aplain in posts:
    if company not in posts_by_company:
        posts_by_company[company] = []
    if len(posts_by_company[company]) < 5:
        posts_by_company[company].append((
            title, updated, link,
            summary or '', analogy or '',
            a90s or '', agenz or '', amedieval or '', aaifluff or '', aplain or ''
        ))

jobs_by_company = {}
for company, dept, title, url in jobs_rows:
    if company not in jobs_by_company:
        jobs_by_company[company] = {}
    d = dept.strip() if dept and dept.strip() else "General"
    if d not in jobs_by_company[company]:
        jobs_by_company[company][d] = []
    jobs_by_company[company][d].append((title, url))

release_type_counts = {}
for _co, _sm in releases_rows:
    if _co not in release_type_counts:
        release_type_counts[_co] = {'feature': 0, 'bugfix': 0, 'maintenance': 0}
    release_type_counts[_co][classify_release(_sm)] += 1

STOP_WORDS = {
    'the','a','an','and','is','to','of','in','for','with','that','this','are',
    'we','our','it','be','as','at','by','or','on','do','not','from','but',
    'have','has','was','were','will','can','you','your','all','new','how',
    'what','why','when','more','get','its','their','they','them','which',
    'about','up','out','so','if','my','me','no','than','into','use','using',
    'used','just','now','also','been','best','amp','blog','post','like','one',
    'two','three','changelog','update','updates','release','releases','version',
    'vs','here','there','some','had','her','his','him','she','he','who','own',
    'any','well','make','made','let','set','see','say','said','does','did',
    'help','helps','work','works','working','team','teams','product','products',
    'company','companies','app','apps','tool','tools','user','users','page',
    'pages','list','lists','time','times','much','many','give','gives','need',
    'needs','take','takes','look','looks','feel','start','starts','first',
    'last','next','back','add','adds','added','know','keep','run','runs',
    'build','builds','built','want','wants','even','still','only','same',
    'most','every','never','always','already','soon','today','week','month',
    'year','thing','things','way','ways','each','both','few','own','such',
    'these','those','very','too','then','over','after','before','between',
    'through','off','where','being','without','while','should','could','would',
    'might','must','upon','per','let','got','put','com','www','http','https',
    'really','actually','simply','easily','quickly','better','great','good',
    'right','long','high','low','small','large','big','old','new','full',
    'open','free','easy','fast','data','based','across','within','whether',
    'built','allows','makes','give','able','want','lets',
}

def get_keywords(company_id):
    rows = [r for r in all_posts_for_stats if r[0] == company_id]
    text = " ".join((r[1] or "") + " " + (r[3] or "") for r in rows)
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    filtered = [w for w in words if w not in STOP_WORDS]
    return Counter(filtered)

keywords_by_company = {c: get_keywords(c) for c in ["PostHog", "Linear", "Zapier", "Replit"]}

def get_monthly_counts(company_id):
    today = date_cls.today()
    months = []
    y, m = today.year, today.month
    for i in range(5, -1, -1):
        mi = m - i
        yi = y
        if mi <= 0:
            mi += 12
            yi -= 1
        months.append((yi, mi))
    counts = {k: 0 for k in months}
    for row in all_posts_for_stats:
        if row[0] != company_id:
            continue
        upd = row[2]
        if upd and len(upd) >= 7:
            try:
                py, pm = int(upd[:4]), int(upd[5:7])
                if (py, pm) in counts:
                    counts[(py, pm)] += 1
            except Exception:
                pass
    return [(calendar.month_abbr[mi], counts.get((yi, mi), 0)) for yi, mi in months]

monthly_by_company = {c: get_monthly_counts(c) for c in ["PostHog", "Linear", "Zapier", "Replit"]}

# ── SVG generators ────────────────────────────────────────────────────────────

def compute_bubbles(counter, width=290, height=118):
    random.seed(42)
    items = counter.most_common(16)
    if not items:
        return []
    max_c, min_c = items[0][1], items[-1][1]
    placed = []
    for word, count in items:
        norm = (count - min_c) / max(max_c - min_c, 1)
        r = int(11 + norm * 17)
        opacity = round(0.28 + norm * 0.52, 2)
        best = None
        for _ in range(200):
            x = random.randint(r + 3, width - r - 3)
            y = random.randint(r + 3, height - r - 3)
            if all(math.sqrt((x-px)**2 + (y-py)**2) >= r + pr + 6
                   for px, py, pr, *_ in placed):
                best = (x, y)
                break
        if best:
            placed.append((best[0], best[1], r, word, opacity))
    return placed

def bubble_svg(counter, color, width=290, height=118):
    bubbles = compute_bubbles(counter, width, height)
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" '
             f'style="height:{height}px;display:block;overflow:hidden;">']
    for x, y, r, word, opacity in bubbles:
        fs = max(7, int(r * 0.62))
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" opacity="{opacity}"/>')
        parts.append(f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" '
                     f'font-family="Sora,sans-serif" font-size="{fs}" fill="#333" '
                     f'font-weight="600">{html_escape(word)}</text>')
    parts.append('</svg>')
    return ''.join(parts)

def sparkline_svg(monthly, color, width=270, bar_h=28, label_h=13):
    th = bar_h + label_h
    n = len(monthly)
    if n == 0:
        return f'<svg width="100%" height="{th}" style="display:block;"></svg>'
    max_c = max((c for _, c in monthly), default=0) or 1
    col_w = width / n
    bw = col_w * 0.55
    parts = [f'<svg viewBox="0 0 {width} {th}" width="100%" style="height:{th}px;display:block;">']
    for i, (label, count) in enumerate(monthly):
        xc = (i + 0.5) * col_w
        bh = (count / max_c) * bar_h
        draw_h = max(bh, 1)
        bar_opacity = "0.72" if count > 0 else "0.15"
        parts.append(f'<rect x="{xc - bw/2:.1f}" y="{bar_h - draw_h:.1f}" '
                     f'width="{bw:.1f}" height="{draw_h:.1f}" rx="2" '
                     f'fill="{color}" opacity="{bar_opacity}"/>')
        parts.append(f'<text x="{xc:.1f}" y="{bar_h + 10}" text-anchor="middle" '
                     f'font-family="Sora,sans-serif" font-size="8" fill="#bbb">{label}</text>')
    parts.append('</svg>')
    return ''.join(parts)

# ── HTML ──────────────────────────────────────────────────────────────────────

html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; script-src 'self' 'unsafe-inline'; connect-src 'none'; object-src 'none'; base-uri 'self';">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Company Tracker</title>
    <link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;700&family=Oswald:ital,wght@1,700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Sora', sans-serif; max-width: 1100px; margin: 0 auto; padding: 320px 20px 100vh; background: #f9f9f9; }
        h1 { margin-top: 60px; }
        .sticky-header { position: fixed; top: 33px; left: 50%; transform: translateX(-50%); width: 100%; max-width: 1100px; z-index: 100; background: #f9f9f9; padding: 20px 20px 16px; border-bottom: 1px solid #e8e8e8; }
        .header-logo { position: absolute; top: 12px; right: 20px; height: 70px; width: auto; pointer-events: none; mix-blend-mode: multiply; }
        .voice-label { font-size: 0.68rem; color: #bbb; font-family: 'Sora', sans-serif; font-weight: 300; margin: 0 0 7px 0; letter-spacing: 0.3px; }
        .heading { font-size: 3rem; font-weight: 700; margin-top: 80px; line-height: 1.2; margin-bottom: 0.6rem; }
        .heading span { display: block; }
        .heading .line1 { text-align: left; padding-left: 15%; }
        .heading .line2 { text-align: center; }
        #heading-line2 { font-family: 'Oswald', sans-serif; font-style: italic; font-weight: 700; color: #FF6B00; }

        /* Row layout */
        .company-row { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; align-items: stretch; }

        /* Left paper-stack card */
        .company-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); cursor: pointer; transition: box-shadow 0.2s ease; overflow: hidden; display: flex; flex-direction: column; }
        .company-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.12); }
        .company-tag { display: inline-block; align-self: flex-start; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; padding: 3px 10px; border-radius: 20px; margin-bottom: 8px; border: 1.5px solid #111; background: white !important; color: #111 !important; }
        .card-label { font-size: 0.8rem; color: #888; margin-bottom: 10px; }

        /* Cursor zones */
        .section-posthog, .section-posthog * { cursor: none !important; }
        .section-linear,  .section-linear  * { cursor: none !important; }
        .section-zapier,  .section-zapier  * { cursor: none !important; }
        .section-replit,  .section-replit  * { cursor: none !important; }

        /* Paper stack */
        .blog-stack-wrap { position: relative; margin-right: 8px; margin-bottom: 10px; flex: 1; }
        .paper-behind { position: absolute; inset: 0; background: white; border-radius: 8px; border: 1px solid #ebebeb; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
        .paper-top { position: relative; z-index: 3; background: white; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 3px 12px rgba(0,0,0,0.10); padding: 14px 16px 16px; transform-origin: center center; min-height: 160px; }
        .paper-top.toss-left  { animation: toss-left  0.26s cubic-bezier(0.4,0,1,1) forwards; }
        .paper-top.toss-right { animation: toss-right 0.26s cubic-bezier(0.4,0,1,1) forwards; }
        .paper-top.rise       { animation: rise-up    0.24s cubic-bezier(0.22,1,0.36,1) forwards; }
        @keyframes toss-left  { 0% { transform: translate(0,0) rotate(0deg); opacity:1; } 100% { transform: translate(-300px,-15px) rotate(-18deg); opacity:0; } }
        @keyframes toss-right { 0% { transform: translate(0,0) rotate(0deg); opacity:1; } 100% { transform: translate(300px,-15px) rotate(18deg); opacity:0; } }
        @keyframes rise-up    { 0% { transform: translate(0,12px) scale(0.97); opacity:0; } 100% { transform: translate(0,0) scale(1); opacity:1; } }
        .paper-arrow { position: absolute; top: 10px; background: none; border: none; font-size: 1rem; color: #888; cursor: pointer !important; padding: 4px 6px; border-radius: 4px; line-height: 1; transition: background 0.1s; }
        .paper-arrow:hover { background: #f0f0f0; }
        .paper-arrow-left  { left: 10px; }
        .paper-arrow-right { right: 10px; }
        .post-title-link { display: block; text-decoration: none; color: #111; font-size: 0.88rem; font-weight: 600; line-height: 1.4; margin-top: 30px; cursor: pointer !important; }
        .post-title-link:hover { text-decoration: underline; }
        .post-date    { font-size: 0.72rem; color: #aaa; margin-top: 2px; }
        .post-summary { font-size: 0.8rem; color: #555; margin-top: 6px; line-height: 1.5; }
        .post-analogy { font-size: 0.75rem; color: #888; margin-top: 8px; font-style: italic; }
        .paper-indicator { font-size: 0.68rem; color: #ccc; margin-top: 10px; text-align: center; }

        /* Flip card (right column) */
        .flip-card-outer { background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); transition: box-shadow 0.2s ease; perspective: 1100px; min-height: 370px; }
        .flip-card-outer:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.12); }
        .flip-card-inner { position: relative; width: 100%; height: 100%; min-height: 370px; transform-style: preserve-3d; transition: transform 0.42s ease; }
        .flip-card-inner.flipped { transform: rotateY(180deg); }
        .flip-front, .flip-back { position: absolute; inset: 0; backface-visibility: hidden; -webkit-backface-visibility: hidden; padding: 16px 18px 14px; display: flex; flex-direction: column; gap: 10px; overflow: visible; }
        .flip-card-outer { overflow: visible; }
        .flip-back { transform: rotateY(180deg); }
        .flip-icon { position: absolute; top: 8px; right: 10px; background: none; border: none; font-size: 1.05rem; color: #ccc; cursor: pointer !important; padding: 4px 6px; border-radius: 4px; line-height: 1; transition: color 0.15s; z-index: 10; }
        .flip-icon:hover { color: #888; }

        /* Roles */
        .roles-wrap { position: relative; }
        .roles-count { font-size: 0.78rem; font-weight: 600; color: #bbb; cursor: pointer !important; user-select: none; line-height: 1.3; transition: opacity 0.15s; }
        .roles-count:hover { opacity: 0.75; }
        .roles-count:hover .roles-num,
        .roles-count:hover .roles-text { text-decoration: underline; text-underline-offset: 2px; }
        .roles-num { font-size: 1.5rem; font-weight: 700; line-height: 1; }
        .roles-text { font-size: 0.82rem; font-weight: 600; }

        /* Jobs popover */
        .jobs-popover { display: none; position: absolute; top: calc(100% + 6px); left: 0; right: 0; background: white; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 18px rgba(0,0,0,0.12); padding: 10px 12px 12px; z-index: 9999; max-height: 220px; overflow-y: auto; }
        .jobs-popover.open { display: block; }
        .dept-header { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; margin: 8px 0 3px; }
        .dept-header:first-child { margin-top: 0; }
        .job-link { display: block; font-size: 0.75rem; color: #444; text-decoration: none; padding: 2px 0; line-height: 1.4; }
        .job-link:hover { color: #111; text-decoration: underline; }

        /* Keyword bubbles */
        .bubble-wrap { flex: 1; min-height: 90px; }

        /* Sparkline */
        .sparkline-wrap { margin-top: auto; }
        .sparkline-label { font-size: 0.65rem; color: #bbb; margin-bottom: 2px; }

        /* Back face */
        .back-section { margin-bottom: 4px; }
        .back-header { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: #999; margin-bottom: 5px; }
        .pill-row { display: flex; flex-wrap: wrap; gap: 5px; }
        .serve-pill { font-size: 0.7rem; padding: 3px 9px; border-radius: 20px; background: #f4f4f4; color: #555; font-weight: 500; }
        .comp-pill  { font-size: 0.7rem; padding: 3px 9px; border-radius: 20px; background: white; font-weight: 500; border: 1.5px solid; cursor: pointer; text-decoration: none; }

        /* Voice pills */
        .voice-global { display: flex; gap: 8px; flex-wrap: wrap; }
        .voice-pill { font-family: 'Sora', sans-serif; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.4px; padding: 5px 14px 6px; background: #f0f0f0; color: #222; border: 1px solid #bbb; border-bottom: 4px solid #999; border-radius: 6px; box-shadow: 0 2px 0 #aaa, 0 3px 4px rgba(0,0,0,0.12); cursor: pointer; transition: transform 0.07s ease, box-shadow 0.07s ease, border-bottom-width 0.07s ease; }
        .voice-pill:hover { background: #e6e6e6; transform: translateY(1px); border-bottom-width: 3px; box-shadow: 0 1px 0 #aaa, 0 2px 3px rgba(0,0,0,0.1); }
        .voice-pill.active { background: #ddd; color: #111; transform: translateY(3px); border-bottom-width: 1px; box-shadow: 0 0px 0 #aaa, inset 0 1px 3px rgba(0,0,0,0.15); }

        /* PostHog hedgehog cursor */
        #hh-cursor { position: fixed; pointer-events: none; z-index: 99999; width: 52px; height: 52px; transform: translate(-50%, -50%); display: none; }
        #hh-cursor.waddle      { animation: hh-waddle-slow 0.5s ease-in-out infinite alternate; }
        #hh-cursor.waddle-fast { animation: hh-waddle-fast 0.2s ease-in-out infinite alternate; }
        #hh-cursor.spike       { animation: hh-spike 0.3s ease-out forwards; }
        @keyframes hh-waddle-slow { from { transform: translate(-50%,-50%) scaleX(var(--hh-dir,1)) rotate(-6deg) translateY(0px); } to { transform: translate(-50%,-50%) scaleX(var(--hh-dir,1)) rotate(6deg) translateY(-3px); } }
        @keyframes hh-waddle-fast { from { transform: translate(-50%,-50%) scaleX(var(--hh-dir,1)) rotate(-10deg) translateY(0px); } to { transform: translate(-50%,-50%) scaleX(var(--hh-dir,1)) rotate(10deg) translateY(-6px); } }
        @keyframes hh-spike { 0% { transform: translate(-50%,-50%) scaleX(var(--hh-dir,1)) scale(1); } 40% { transform: translate(-50%,-50%) scaleX(var(--hh-dir,1)) scale(1.6); } 100% { transform: translate(-50%,-50%) scaleX(var(--hh-dir,1)) scale(1); } }
        .paw-print { position: fixed; pointer-events: none; z-index: 99998; width: 12px; height: 12px; opacity: 0.6; animation: paw-fade 1s ease forwards; }
        @keyframes paw-fade { 0% { opacity:0.6; transform:scale(1); } 100% { opacity:0; transform:scale(0.5); } }

        /* Linear cursor */
        #linear-cursor { position: fixed; pointer-events: none; z-index: 99999; width: 26px; height: 26px; transform: translate(-50%,-50%); display: none; filter: drop-shadow(0 0 6px #8B94E0) drop-shadow(0 0 12px #8B94E0); animation: linear-glow-idle 1.5s ease-in-out infinite alternate; }
        #linear-cursor.pulse { animation: linear-click-pulse 0.5s ease-out forwards; }
        @keyframes linear-glow-idle { from { filter: drop-shadow(0 0 4px #8B94E0) drop-shadow(0 0 8px #8B94E0); } to { filter: drop-shadow(0 0 10px #8B94E0) drop-shadow(0 0 20px #b084f5); } }
        @keyframes linear-click-pulse { 0% { filter: drop-shadow(0 0 4px #8B94E0) drop-shadow(0 0 8px #8B94E0); transform: translate(-50%,-50%) scale(1); } 40% { filter: drop-shadow(0 0 18px #b084f5) drop-shadow(0 0 36px #8B94E0) drop-shadow(0 0 52px #8B94E0); transform: translate(-50%,-50%) scale(1.2); } 100% { filter: drop-shadow(0 0 4px #8B94E0) drop-shadow(0 0 8px #8B94E0); transform: translate(-50%,-50%) scale(1); } }

        /* Zapier bolt trail */
        .zap-bolt-trail { position: fixed; pointer-events: none; z-index: 99997; transform: translate(-50%,-50%); animation: zap-trail-fade 0.35s ease forwards; }
        @keyframes zap-trail-fade { 0% { opacity:0.7; } 100% { opacity:0; } }
        #zap-cursor { position: fixed; pointer-events: none; z-index: 99999; transform: translate(-50%,-50%); display: none; }

        /* Hiring Trends */
        .hiring-trends-wrap { max-width: 1100px; margin: 40px auto 0; padding: 0 20px; font-family: 'Sora', sans-serif; }
        .hiring-trends-heading { font-size: 1.1rem; font-weight: 600; color: #333; margin-bottom: 14px; }
        .hiring-trends-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
        .hiring-trends-table th { text-align: left; padding: 8px 12px; background: #f5f5f5; color: #666; font-weight: 600; border-bottom: 2px solid #e0e0e0; }
        .hiring-trends-table td { padding: 7px 12px; border-bottom: 1px solid #f0f0f0; color: #444; }
        .hiring-trends-table .ht-date { color: #999; font-size: 0.72rem; white-space: nowrap; }
        .hiring-trends-table tbody tr:hover { background: #fafafa; }
        /* Delta cards */
        .delta-cards-wrap { max-width: 1100px; margin: 28px auto 0; padding: 0 20px; font-family: 'Sora', sans-serif; display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
        .delta-card { background: white; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 16px 18px; border-top: 3px solid #ddd; }
        .delta-count { font-size: 2rem; font-weight: 700; line-height: 1; }
        .delta-company { font-size: 0.7rem; font-weight: 600; color: #aaa; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }
        .delta-note { font-size: 0.7rem; font-style: italic; color: #bbb; margin-top: 6px; line-height: 1.4; }
        /* Weekly summary */
        .hiring-summary-wrap { max-width: 1100px; margin: 24px auto 60px; padding: 0 20px; font-family: 'Sora', sans-serif; }
        .hiring-summary-card { background: white; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 20px 24px; display: flex; flex-direction: column; gap: 10px; }
        .hiring-summary-header { display: flex; justify-content: space-between; align-items: baseline; }
        .hiring-summary-label { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: #aaa; }
        .hiring-summary-date { font-size: 0.7rem; color: #ccc; }
        .hiring-summary-text { font-size: 0.85rem; color: #444; line-height: 1.65; }
        .reddit-sentiment-text { font-size: 0.73rem; color: #555; line-height: 1.6; }

        /* News ticker */
        .ticker-wrap { position: fixed; top: 0; left: 0; width: 100%; background: #0a0a0a; border-bottom: 1px solid #1a1a1a; padding: 8px 0; z-index: 9999; overflow: hidden; font-family: 'Courier New', monospace; }
        .ticker-track { display: flex; width: max-content; animation: ticker-scroll 60s linear infinite; }
        .ticker-track:hover { animation-play-state: paused; }
        .ticker-item { display: flex; align-items: center; gap: 8px; padding: 0 32px; white-space: nowrap; font-size: 0.75rem; color: #666; }
        .ticker-item a { color: #aaa; text-decoration: none; letter-spacing: 0.5px; }
        .ticker-item a:hover { color: #fff; }
        .ticker-company { font-size: 0.65rem; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; padding: 2px 6px; border-radius: 3px; }
        .ticker-dot { color: #333; font-size: 0.6rem; }
        .ticker-label { color: #2a2a2a; font-size: 0.65rem; letter-spacing: 3px; text-transform: uppercase; padding: 0 16px 0 0; border-right: 1px solid #222; margin-right: 16px; }
        @keyframes ticker-scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }

        @media (max-width: 600px) {
            .ticker-wrap { padding: 6px 0; }
            .ticker-item { font-size: 0.7rem; padding: 0 20px; }
            .heading { font-size: 1.8rem; margin-top: 1.5rem; margin-bottom: 1.5rem; }
            .heading .line1 { padding-left: 0; text-align: center; }
            .company-row { grid-template-columns: 1fr; }
            .voice-buttons { display: flex; flex-wrap: wrap; gap: 8px; }
            .voice-btn { flex: 1 1 calc(50% - 8px); min-width: 0; text-align: center; }
            body { margin: 20px auto; }
            .popover { width: calc(100vw - 40px) !important; left: 20px !important; }
        }
    </style>
<script>
    !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(a!==void 0?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return a!=="posthog"&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys onSessionId".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
    posthog.init('phc_t3jaEakQEn5EnLqurb3fyENpBrdhPri2gpMKZazc4sRh', {{
        api_host: 'https://us.i.posthog.com',
        autocapture: true,
        capture_pageview: true,
        capture_pageleave: true
    }});
</script>
</head>
<body>
{ticker_placeholder}
    <!-- Cursor elements -->
    <img id="hh-cursor" src="hedgehog.png" />
    <svg id="linear-cursor" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 26"><circle cx="13" cy="13" r="11" fill="#8B94E0"/></svg>
    <div id="zap-cursor">
        <svg width="22" height="32" viewBox="0 0 22 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <polygon points="14,0 4,18 11,18 8,32 20,12 13,12 20,0" fill="#FF7A3D" stroke="white" stroke-width="1" stroke-linejoin="round"/>
        </svg>
    </div>
    <svg id="replit-cursor" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 24" style="position:fixed;pointer-events:none;z-index:99999;display:none;transform:translate(-50%,-50%);width:30px;height:auto;">
        <rect id="replit-block-1" x="7" y="1" width="22" height="6" rx="1" fill="#AAAAAA"/>
        <rect id="replit-block-2" x="7" y="9" width="22" height="6" rx="1" fill="#AAAAAA"/>
        <rect id="replit-block-3" x="7" y="17" width="22" height="6" rx="1" fill="#AAAAAA"/>
    </svg>

    <div class="sticky-header">
        <img src="SteezyR.png" class="header-logo" alt="">
        <div class="heading">
            <span class="line1" id="heading-line1">Cool Companies,</span>
            <span class="line2" id="heading-line2">Fresh Releases.</span>
        </div>
        <p class="voice-label">Choose your own voice</p>
        <div class="voice-global">
            <button class="voice-pill" onclick="setVoice('90s', this)">90s</button>
            <button class="voice-pill" onclick="setVoice('genz', this)">Gen Z</button>
            <button class="voice-pill" onclick="setVoice('medieval', this)">Medieval</button>
            <button class="voice-pill" onclick="setVoice('aifluff', this)">AI Fluff</button>
            <button class="voice-pill active" onclick="setVoice('plain', this)">Plain</button>
        </div>
    </div>

    <div style="overflow-x: hidden; margin-top: 120px;">
"""

# ── News ticker ───────────────────────────────────────────────────────────────
company_glow = {
    "PostHog": {"color": "#E8E0D0"},
    "Zapier":  {"color": "#FF7A3D"},
    "Replit":  {"color": "#AAAAAA"},
    "Linear":  {"color": "#8B94E0"},
}
ticker_items = ""
for _tc, _tt, _tl in ticker_posts:
    _col = company_glow.get(_tc, {}).get("color", "#fff")
    ticker_items += (
        f'<div class="ticker-item">'
        f'<span class="ticker-company" style="color:{_col};text-shadow:0 0 8px {_col};border:1px solid {_col}33;">{html_escape(_tc)}</span>'
        f'<a href="{html_escape(_tl)}" target="_blank">{html_escape(_tt)}</a>'
        f'<span class="ticker-dot">&#9670;</span>'
        f'</div>'
    )
_ticker_html = (
    '<div class="ticker-wrap"><div class="ticker-track">'
    '<span class="ticker-label">// LIVE</span>'
    + ticker_items + ticker_items +
    '</div></div>'
) if ticker_items else ""
html = html.replace("{ticker_placeholder}", _ticker_html)

# ── per-company rows ───────────────────────────────────────────────────────────

for company in ["PostHog", "Linear", "Zapier", "Replit"]:
    card_id   = company.lower().replace(" ", "-")
    color     = company_colors[company]
    accent    = company_accent[company]
    c_posts   = posts_by_company.get(company, [])
    c_jobs    = jobs_by_company.get(company, {})
    total_jobs = sum(len(v) for v in c_jobs.values())
    kw        = keywords_by_company.get(company, Counter())
    monthly   = monthly_by_company.get(company, [])

    bsvg  = bubble_svg(kw, color)
    ssvg  = sparkline_svg(monthly, accent)
    reddit_summary = reddit_sentiment_by_company.get(company, "")

    rtypes     = release_type_counts.get(company, {'feature': 0, 'bugfix': 0, 'maintenance': 0})
    feat_color = accent
    bug_color  = lighten_hex(accent, 0.45)
    maint_color = '#cccccc'
    psvg       = pie_chart_svg(rtypes, feat_color, bug_color, maint_color)
    total_r    = sum(rtypes.values()) or 1
    f_pct      = round(rtypes['feature']     / total_r * 100)
    b_pct      = round(rtypes['bugfix']      / total_r * 100)
    m_pct      = 100 - f_pct - b_pct

    # ── left: paper-stack card ──────────────────────────────────────────────
    html += f'<div class="company-row">\n'
    html += f'<div class="company-card section-{card_id}" onclick="event.stopPropagation()">\n'
    html += f'    <div class="company-tag">{company}</div>\n'
    html += f'    <div class="card-label blog-label">Updates</div>\n'
    html += '    <div class="blog-stack-wrap">\n'
    html += '        <div class="paper-behind" style="transform: translate(8px, 10px); z-index:1; background:#f5f5f5;"></div>\n'
    html += '        <div class="paper-behind" style="transform: translate(4px, 5px); z-index:2; background:#fdfdfd;"></div>\n'
    if c_posts:
        html += f'        <div class="paper-top" id="paper-{card_id}">\n'
        html += f'            <button class="paper-arrow paper-arrow-left" onclick="event.stopPropagation(); postNav(\'{card_id}\', \'left\')">&#8592;</button>\n'
        html += f'            <button class="paper-arrow paper-arrow-right" onclick="event.stopPropagation(); postNav(\'{card_id}\', \'right\')">&#8594;</button>\n'
        html += f'            <a class="post-title-link" id="ptitle-{card_id}" href="#" target="_blank"></a>\n'
        html += f'            <div class="post-date" id="pdate-{card_id}"></div>\n'
        html += f'            <div class="post-summary" id="psummary-{card_id}"></div>\n'
        html += f'            <div class="post-analogy" id="panalogy-{card_id}"></div>\n'
        html += f'            <div class="paper-indicator" id="pindicator-{card_id}"></div>\n'
        html += '        </div>\n'
    else:
        html += '        <div style="color:#bbb;font-size:0.85rem;padding:14px 16px;position:relative;z-index:3;" class="coming-soon-label">Coming soon</div>\n'
    html += '    </div>\n'
    html += '</div>\n'

    # JS data for paper stack
    posts_json = []
    for title, updated, link, summary, analogy, a90s, agenz, amedieval, aaifluff, aplain in c_posts:
        posts_json.append({
            'title': title or '', 'date': (updated[:10] if updated else ''),
            'link': link or '', 'summary': summary or '',
            'analogy_90s': a90s or '', 'analogy_genz': agenz or '',
            'analogy_medieval': amedieval or '', 'analogy_aifluff': aaifluff or '',
            'analogy_plain': aplain or '',
        })
    html += f"""<script>
    window.postsData = window.postsData || {{}};
    window.postsData['{card_id}'] = {json.dumps(posts_json, ensure_ascii=False)};
    window.postIndex = window.postIndex || {{}};
    window.postIndex['{card_id}'] = 0;
</script>
"""

    # ── right: flip card ────────────────────────────────────────────────────
    # jobs popover content
    if total_jobs > 0:
        roles_html = (f'<span class="roles-num" style="color:{accent};">{total_jobs}</span>'
                      f'<span class="roles-text" style="color:{accent};"> open roles!</span>')
    else:
        roles_html = '<span style="color:#ccc;font-size:0.8rem;">Fetching soon...</span>'

    popover_inner = ''
    for dept in sorted(c_jobs):
        popover_inner += f'<div class="dept-header" style="color:{accent};">{html_escape(dept)}</div>'
        for jt, ju in c_jobs[dept]:
            popover_inner += (f'<a class="job-link" href="{html_escape(ju)}" '
                              f'target="_blank" rel="noopener">{html_escape(jt)}</a>')

    # back face pills
    serve_pills = ''.join(
        f'<span class="serve-pill">{html_escape(s)}</span>'
        for s in WHO_THEY_SERVE.get(company, [])
    )
    comp_pills = ''.join(
        f'<a class="comp-pill" href="{COMPETITOR_URLS.get(c, "#")}" target="_blank" rel="noopener" style="border-color:{color};color:{accent};">{html_escape(c)}</a>'
        for c in COMPETITORS.get(company, [])
    )

    html += f"""<div class="flip-card-outer section-{card_id}" onclick="event.stopPropagation()">
  <div class="flip-card-inner" id="flip-inner-{card_id}">

    <div class="flip-front">
      <button class="flip-icon" onclick="event.stopPropagation();flipCard('{card_id}')">&#8635;</button>
      <div class="roles-wrap">
        <div class="roles-count" onclick="event.stopPropagation();toggleJobsPopover('{card_id}')">
          {roles_html}
        </div>
        <div class="jobs-popover" id="jobs-popover-{card_id}">{popover_inner}</div>
      </div>
      <div>
        <div class="sparkline-label">Release types</div>
        <div style="display:flex;align-items:center;gap:10px;margin-top:4px;">
          {psvg}
          <div style="font-size:0.62rem;color:#888;line-height:1.9;">
            <div><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{feat_color};margin-right:5px;vertical-align:middle;"></span>Features <span style="color:#bbb;">({f_pct}%)</span></div>
            <div><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{bug_color};margin-right:5px;vertical-align:middle;"></span>Bug fixes <span style="color:#bbb;">({b_pct}%)</span></div>
            <div><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{maint_color};margin-right:5px;vertical-align:middle;"></span>Maintenance <span style="color:#bbb;">({m_pct}%)</span></div>
          </div>
        </div>
      </div>
      <div class="bubble-wrap">{bsvg}</div>
      <div class="sparkline-wrap">
        <div class="sparkline-label">Post activity — last 6 months</div>
        {ssvg}
      </div>
    </div>

    <div class="flip-back">
      <button class="flip-icon" onclick="event.stopPropagation();flipCard('{card_id}')">&#8635;</button>
      <div class="back-section">
        <div class="back-header">Who they serve</div>
        <div class="pill-row">{serve_pills}</div>
      </div>
      <div class="back-section">
        <div class="back-header">Competes with</div>
        <div class="pill-row">{comp_pills}</div>
      </div>
      {f'<div class="back-section"><div class="back-header">Community Pulse</div><div class="reddit-sentiment-text">{html_escape(reddit_summary)}</div></div>' if reddit_summary else ''}
    </div>

  </div>
</div>
</div>
"""

html += '    </div>\n'

# ── Hiring Trends table ───────────────────────────────────────────────────────
if hiring_data:
    from collections import defaultdict
    companies_order = ["PostHog", "Linear", "Zapier", "Replit"]
    by_date = defaultdict(dict)
    all_dates = []
    for company, snap_date, count in hiring_data:
        by_date[snap_date][company] = count
        if snap_date not in all_dates:
            all_dates.append(snap_date)
    all_dates.sort()

    header_cells = ''.join(f'<th>{c}</th>' for c in companies_order)
    rows_html = ''
    for d in all_dates:
        cells = ''.join(
            f'<td>{by_date[d].get(c, "—")}</td>' for c in companies_order
        )
        rows_html += f'<tr><td class="ht-date">{d}</td>{cells}</tr>\n'

    html += f"""
<div class="hiring-trends-wrap">
  <div onclick="toggleHiringTable()" style="cursor:pointer; display:flex; align-items:center; gap:8px; margin-bottom:16px;">
    <span style="font-family:'Sora',sans-serif; font-size:1rem; font-weight:700; color:#111;">Hiring Trends</span>
    <span id="hiring-toggle-icon" style="font-size:0.8rem; color:#aaa;">&#9660; show</span>
  </div>
  <div id="hiring-table-wrapper" style="display:none;">
    <table class="hiring-trends-table">
      <thead><tr><th>Date</th>{header_cells}</tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>
"""

# ── Delta cards ───────────────────────────────────────────────────────────────
if hiring_deltas:
    companies_order = ["PostHog", "Linear", "Zapier", "Replit"]
    # Most recent delta per company
    latest_delta = {}
    for company, snap_date, open_roles, delta, note in hiring_deltas:
        if company not in latest_delta:
            latest_delta[company] = (open_roles, note)

    cards_html = ''
    for c in companies_order:
        color = company_colors.get(c, '#e0e0e0')
        accent = company_accent.get(c, '#888')
        if c in latest_delta:
            count, note = latest_delta[c]
            cards_html += f"""<div class="delta-card" style="border-top-color:{color};">
  <div class="delta-count" style="color:{accent};">{count}</div>
  <div class="delta-company">{html_escape(c)}</div>
  <div class="delta-note">{html_escape(note)}</div>
</div>
"""
    html += f'<div class="delta-cards-wrap">{cards_html}</div>\n'

# ── Weekly summary ────────────────────────────────────────────────────────────
if latest_summary:
    summary_date, summary_text = latest_summary
    html += f"""<div class="hiring-summary-wrap">
  <div class="hiring-summary-card">
    <div class="hiring-summary-header">
      <span class="hiring-summary-label">Weekly Analysis</span>
      <span class="hiring-summary-date">{html_escape(summary_date)}</span>
    </div>
    <div class="hiring-summary-text">{html_escape(summary_text)}</div>
  </div>
</div>
"""
elif hiring_deltas:
    html += '<div style="height:60px;"></div>\n'

# ── JS ────────────────────────────────────────────────────────────────────────

html += """
    <script>
        var hhCursor     = document.getElementById('hh-cursor');
        var linearCursor = document.getElementById('linear-cursor');
        var zapCursor    = document.getElementById('zap-cursor');
        var replitCursor = document.getElementById('replit-cursor');
        var lastX = 0, lastY = 0;
        var facingLeft = false;

        var pawSVG  = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><circle cx="10" cy="14" r="5" fill="#6f503a" opacity="0.5"/><circle cx="5" cy="8" r="3" fill="#6f503a" opacity="0.5"/><circle cx="15" cy="8" r="3" fill="#6f503a" opacity="0.5"/><circle cx="10" cy="4" r="2.5" fill="#6f503a" opacity="0.5"/></svg>');
        var boltSVG = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="20" viewBox="0 0 22 32"><polygon points="14,0 4,18 11,18 8,32 20,12 13,12 20,0" fill="#FF7A3D"/></svg>';

        document.addEventListener('mousemove', function(e) {
            var dx = e.clientX - lastX, dy = e.clientY - lastY;
            var speed = Math.sqrt(dx*dx + dy*dy);

            hhCursor.style.left = e.clientX + 'px';
            hhCursor.style.top  = e.clientY + 'px';
            if (hhCursor.style.display === 'block') {
                if (dx < -2) facingLeft = true;
                else if (dx > 2) facingLeft = false;
                hhCursor.style.setProperty('--hh-dir', facingLeft ? -1 : 1);
                if (!hhCursor.classList.contains('spike')) {
                    if (speed > 8) { hhCursor.classList.remove('waddle'); void hhCursor.offsetWidth; hhCursor.classList.add('waddle-fast'); }
                    else           { hhCursor.classList.remove('waddle-fast'); void hhCursor.offsetWidth; hhCursor.classList.add('waddle'); }
                }
                if (speed > 3 && Math.random() < 0.15) {
                    var paw = document.createElement('img');
                    paw.src = pawSVG; paw.className = 'paw-print';
                    paw.style.left = (e.clientX - 6) + 'px';
                    paw.style.top  = (e.clientY + 10) + 'px';
                    document.body.appendChild(paw);
                    setTimeout(function() { paw.remove(); }, 1000);
                }
            }

            linearCursor.style.left = e.clientX + 'px';
            linearCursor.style.top  = e.clientY + 'px';
            replitCursor.style.left = e.clientX + 'px';
            replitCursor.style.top  = e.clientY + 'px';
            zapCursor.style.left    = e.clientX + 'px';
            zapCursor.style.top     = e.clientY + 'px';
            if (zapCursor.style.display === 'block' && Math.random() < 0.35) {
                var bolt = document.createElement('div');
                bolt.className = 'zap-bolt-trail';
                bolt.style.left = e.clientX + 'px'; bolt.style.top = e.clientY + 'px';
                bolt.innerHTML = boltSVG;
                document.body.appendChild(bolt);
                setTimeout(function() { bolt.remove(); }, 380);
            }
            lastX = e.clientX; lastY = e.clientY;
        });

        document.querySelectorAll('.section-posthog').forEach(function(el) {
            el.addEventListener('mouseenter', function() { hhCursor.style.display = 'block'; hhCursor.classList.add('waddle'); });
            el.addEventListener('mouseleave', function() { hhCursor.style.display = 'none'; hhCursor.classList.remove('waddle','waddle-fast','spike'); });
            el.addEventListener('click', function(e) {
                hhCursor.classList.remove('waddle','waddle-fast','spike');
                void hhCursor.offsetWidth;
                hhCursor.classList.add('spike');
                setTimeout(function() { hhCursor.classList.remove('spike'); void hhCursor.offsetWidth; hhCursor.classList.add('waddle'); }, 350);
                var colors = ['#e8962a','#c45e00','#f5b942','#a0522d'];
                for (var i = 0; i < 8; i++) {
                    (function(idx) {
                        var spine = document.createElement('div');
                        var angle = (idx / 8) * 360;
                        var dist  = 28 + Math.random() * 14;
                        spine.style.cssText = ['position:fixed','pointer-events:none','z-index:99996','width:2px','height:'+(10+Math.random()*8)+'px','background:'+colors[idx%colors.length],'border-radius:2px','left:'+e.clientX+'px','top:'+e.clientY+'px','transform-origin:bottom center','transform:rotate('+angle+'deg) translateY(0px)','transition:transform 0.25s ease-out, opacity 0.3s ease-out'].join(';');
                        document.body.appendChild(spine);
                        void spine.offsetWidth;
                        spine.style.transform = 'rotate('+angle+'deg) translateY(-'+dist+'px)';
                        spine.style.opacity = '0';
                        setTimeout(function() { spine.remove(); }, 350);
                    })(i);
                }
            });
        });

        document.querySelectorAll('.section-linear').forEach(function(el) {
            el.addEventListener('mouseenter', function() { linearCursor.style.display = 'block'; });
            el.addEventListener('mouseleave', function() { linearCursor.style.display = 'none'; });
            el.addEventListener('click', function() {
                linearCursor.classList.remove('pulse'); void linearCursor.offsetWidth;
                linearCursor.classList.add('pulse');
                setTimeout(function() { linearCursor.classList.remove('pulse'); }, 520);
            });
        });

        document.querySelectorAll('.section-zapier').forEach(function(el) {
            el.addEventListener('mouseenter', function() { zapCursor.style.display = 'block'; });
            el.addEventListener('mouseleave', function() { zapCursor.style.display = 'none'; });
            el.addEventListener('click', function(e) {
                var ring = document.createElement('div');
                ring.style.cssText = 'position:fixed;pointer-events:none;z-index:99996;border-radius:50%;border:2px solid #FF7A3D;left:'+e.clientX+'px;top:'+e.clientY+'px;transform:translate(-50%,-50%);animation:zap-ring-out 0.5s ease-out forwards;';
                document.body.appendChild(ring);
                var burst = document.createElement('div');
                burst.style.cssText = 'position:fixed;pointer-events:none;z-index:99997;left:'+e.clientX+'px;top:'+e.clientY+'px;transform:translate(-50%,-50%);font-size:26px;animation:zap-burst-anim 0.5s ease-out forwards;';
                burst.textContent = '⚡';
                document.body.appendChild(burst);
                setTimeout(function() { ring.remove(); burst.remove(); }, 520);
            });
        });

        document.querySelectorAll('.section-replit').forEach(function(el) {
            el.addEventListener('mouseenter', function() { replitCursor.style.display = 'block'; });
            el.addEventListener('mouseleave', function() { replitCursor.style.display = 'none'; });
            el.addEventListener('click', function() {
                var blocks = [document.getElementById('replit-block-1'), document.getElementById('replit-block-2'), document.getElementById('replit-block-3')];
                blocks.forEach(function(b) {
                    b.style.transition = 'transform 0.18s ease-out';
                    b.style.transform = 'translate('+((Math.random()-0.5)*36)+'px,'+((Math.random()-0.5)*36)+'px) rotate('+((Math.random()-0.5)*60)+'deg)';
                });
                setTimeout(function() {
                    blocks.forEach(function(b) { b.style.transition = 'transform 0.4s cubic-bezier(0.34,1.56,0.64,1)'; b.style.transform = 'translate(0,0) rotate(0deg)'; });
                }, 200);
            });
        });

        var styleSheet = document.createElement('style');
        styleSheet.textContent = [
            '@keyframes zap-ring-out { 0% { width:8px; height:8px; opacity:0.9; } 100% { width:60px; height:60px; margin-left:-26px; margin-top:-26px; opacity:0; border-width:0.5px; } }',
            '@keyframes zap-burst-anim { 0% { opacity:1; transform:translate(-50%,-50%) scale(0.6) rotate(-20deg); } 30% { opacity:1; transform:translate(-50%,-50%) scale(1.4) rotate(10deg); } 60% { opacity:0.8; transform:translate(-50%,-50%) scale(1.1) rotate(-4deg); } 100% { opacity:0; transform:translate(-50%,-50%) scale(0.8); } }'
        ].join('\\n');
        document.head.appendChild(styleSheet);

        // ── voice pills ──────────────────────────────────────────────────────
        window.activeVoice = 'plain';
        var voiceContent = {
            '90s':     { line1: 'Dopest Companies,',          line2: 'Da Bomb Drops.',           blog: 'Word On The Street',      comingSoon: 'coming soon, no doubt' },
            genz:      { line1: 'Lowkey Cool Companies,',     line2: 'No Cap Releases.',          blog: 'Tea & Updates',           comingSoon: 'dropping soon bestie' },
            medieval:  { line1: 'Hear Ye, Noble Companies,',  line2: 'Fresh Proclamations.',      blog: "The Town Crier's Scroll", comingSoon: 'forthcoming, good patron' },
            aifluff:   { line1: 'Industry-Leading Companies,',line2: 'Transformative Releases.',  blog: 'Thought Leadership Hub',  comingSoon: 'exciting content incoming' },
            plain:     { line1: 'Cool Companies,',            line2: 'Fresh Releases.',           blog: 'Updates',                 comingSoon: 'Coming soon' }
        };
        function setVoice(voice, btn) {
            window.activeVoice = voice;
            document.querySelectorAll('.voice-pill').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            document.querySelectorAll('.post-analogy').forEach(function(el) {
                var text = el.dataset[voice] || '';
                el.textContent = text ? '"' + text + '"' : '';
            });
            var v = voiceContent[voice];
            if (!v) return;
            document.getElementById('heading-line1').textContent = v.line1;
            document.getElementById('heading-line2').textContent = v.line2;
            document.querySelectorAll('.blog-label').forEach(function(el) { el.textContent = v.blog; });
            document.querySelectorAll('.coming-soon-label').forEach(function(el) { el.textContent = v.comingSoon; });
        }

        // ── paper stack ──────────────────────────────────────────────────────
        function loadPost(id, idx) {
            var data = window.postsData[id];
            if (!data || !data.length) return;
            var r = data[idx];
            document.getElementById('ptitle-' + id).textContent = r.title;
            document.getElementById('ptitle-' + id).href = r.link;
            document.getElementById('pdate-' + id).textContent = r.date;
            document.getElementById('psummary-' + id).textContent = r.summary;
            var el = document.getElementById('panalogy-' + id);
            el.dataset['90s']     = r.analogy_90s      || '';
            el.dataset.genz       = r.analogy_genz      || '';
            el.dataset.medieval   = r.analogy_medieval  || '';
            el.dataset.aifluff    = r.analogy_aifluff   || '';
            el.dataset.plain      = r.analogy_plain     || '';
            var text = el.dataset[window.activeVoice] || '';
            el.textContent = text ? '"' + text + '"' : '';
            document.getElementById('pindicator-' + id).textContent = (idx + 1) + ' of ' + data.length;
        }
        function postNav(id, dir) {
            var data = window.postsData[id];
            if (!data || !data.length) return;
            var paper = document.getElementById('paper-' + id);
            if (paper._animating) return;
            paper._animating = true;
            var current = window.postIndex[id] || 0;
            var next = dir === 'left' ? (current + 1) % data.length : (current - 1 + data.length) % data.length;
            var animClass = dir === 'left' ? 'toss-left' : 'toss-right';
            paper.classList.add(animClass);
            setTimeout(function() {
                paper.classList.remove(animClass);
                window.postIndex[id] = next;
                loadPost(id, next);
                void paper.offsetWidth;
                paper.classList.add('rise');
                setTimeout(function() { paper.classList.remove('rise'); paper._animating = false; }, 250);
            }, 260);
        }
        document.addEventListener('DOMContentLoaded', function() {
            if (window.postsData) {
                Object.keys(window.postsData).forEach(function(id) {
                    window.postIndex[id] = 0;
                    loadPost(id, 0);
                });
            }
        });

        // ── flip cards ───────────────────────────────────────────────────────
        function flipCard(id) {
            var inner = document.getElementById('flip-inner-' + id);
            if (inner) inner.classList.toggle('flipped');
        }

        // ── jobs popover ─────────────────────────────────────────────────────
        function toggleJobsPopover(id) {
            var p = document.getElementById('jobs-popover-' + id);
            if (!p) return;
            var isOpen = p.classList.contains('open');
            document.querySelectorAll('.jobs-popover.open').forEach(function(el) { el.classList.remove('open'); });
            if (!isOpen) p.classList.add('open');
        }
        document.addEventListener('click', function(e) {
            if (!e.target.closest || !e.target.closest('.roles-wrap')) {
                document.querySelectorAll('.jobs-popover.open').forEach(function(el) { el.classList.remove('open'); });
            }
        });
        function toggleHiringTable() {
            var wrapper = document.getElementById('hiring-table-wrapper');
            var icon = document.getElementById('hiring-toggle-icon');
            if (wrapper.style.display === 'none') {
                wrapper.style.display = 'block';
                icon.textContent = '▲ hide';
            } else {
                wrapper.style.display = 'none';
                icon.textContent = '▼ show';
            }
        }
    </script>
    <footer style="text-align:center;padding:60px 20px 40px;font-family:'Sora',sans-serif;font-size:0.72rem;color:#ccc;line-height:1.6;">
        Built by a quirky, clumsy little creature foraging at odd hours. Not affiliated with PostHog, Zapier, Replit, or Linear&hellip; yet.
    </footer>
</body>
</html>
"""

with open("index.html", "w") as f:
    f.write(html)

print("Done! index.html generated.")
