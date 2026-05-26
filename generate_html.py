import sqlite3

conn = sqlite3.connect("releases.db")
cursor = conn.cursor()

for col in ("analogy_90s", "analogy_genz", "analogy_medieval", "analogy_aifluff", "analogy_plain"):
    try:
        cursor.execute(f"ALTER TABLE releases ADD COLUMN {col} TEXT")
    except Exception:
        pass
conn.commit()

releases = cursor.execute("""
    SELECT company, title, updated, link, summary, analogy,
           analogy_90s, analogy_genz, analogy_medieval, analogy_aifluff, analogy_plain
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
for company, title, updated, link, summary, analogy, a90s, agenz, amedieval, aaifluff, aplain in releases:
    if company not in by_company:
        by_company[company] = []
    by_company[company].append((title, updated, link, summary, analogy, a90s, agenz, amedieval, aaifluff, aplain))

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
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; script-src 'self' 'unsafe-inline'; connect-src 'none'; object-src 'none'; base-uri 'self';">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Company Tracker</title>
    <link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;700&family=Oswald:ital,wght@1,700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Sora', sans-serif; max-width: 1100px; margin: 0 auto; padding: 220px 20px 100vh; background: #f9f9f9; }
        .sticky-header { position: fixed; top: 0; left: 50%; transform: translateX(-50%); width: 100%; max-width: 1100px; z-index: 100; background: #f9f9f9; padding: 20px 20px 16px; border-bottom: 1px solid #e8e8e8; }
        .header-logo { position: absolute; top: 12px; right: 20px; height: 70px; width: auto; pointer-events: none; mix-blend-mode: multiply; }
        .voice-label { font-size: 0.68rem; color: #bbb; font-family: 'Sora', sans-serif; font-weight: 300; margin: 0 0 7px 0; letter-spacing: 0.3px; }
        .heading { font-size: 3rem; font-weight: 700; margin-top: 0; line-height: 1.2; margin-bottom: 1.2rem; }
        .heading span { display: block; }
        .heading .line1 { text-align: left; padding-left: 15%; }
        .heading .line2 { text-align: center; }
        #heading-line2 { font-family: 'Oswald', sans-serif; font-style: italic; font-weight: 700; color: #FF6B00; }
        .company-row { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 40px; align-items: stretch; }
        .company-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); cursor: pointer; transition: box-shadow 0.2s ease; }
        .company-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.12); }
        .release-stack-wrap { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); height: 100%; box-sizing: border-box; overflow: hidden; }
        .company-name-large {
            font-family: 'Sora', sans-serif;
            font-size: 2rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #111;
            text-shadow: 2px 2px 0px #000, 4px 6px 16px rgba(0,0,0,0.4);
            -webkit-text-stroke: 1px black;
            margin-bottom: 14px;
            display: block;
            line-height: 1;
        }
        .company-tag { display: inline-block; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; padding: 3px 10px; border-radius: 20px; margin-bottom: 8px; border: 1.5px solid #111; background: white !important; color: #111 !important; }
        .card-label { font-size: 0.8rem; color: #888; margin-bottom: 4px; }
        .card-hint { font-size: 0.75rem; color: #bbb; }
        .releases-label { text-align: right; font-size: 0.68rem; color: #ccc; letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 6px; font-weight: 600; }

        .section-posthog, .section-posthog * { cursor: none !important; }
        .section-linear, .section-linear * { cursor: none !important; }
        .section-zapier, .section-zapier * { cursor: none !important; }
        .section-replit, .section-replit * { cursor: none !important; }

        /* PostHog hedgehog cursor */
        #hh-cursor {
            position: fixed;
            pointer-events: none;
            z-index: 99999;
            width: 52px;
            height: 52px;
            transform: translate(-50%, -50%);
            display: none;
        }
        #hh-cursor.waddle {
            animation: hh-waddle-slow 0.5s ease-in-out infinite alternate;
        }
        #hh-cursor.waddle-fast {
            animation: hh-waddle-fast 0.2s ease-in-out infinite alternate;
        }
        #hh-cursor.spike {
            animation: hh-spike 0.3s ease-out forwards;
        }
        @keyframes hh-waddle-slow {
            from { transform: translate(-50%, -50%) scaleX(var(--hh-dir,1)) rotate(-6deg) translateY(0px); }
            to   { transform: translate(-50%, -50%) scaleX(var(--hh-dir,1)) rotate(6deg) translateY(-3px); }
        }
        @keyframes hh-waddle-fast {
            from { transform: translate(-50%, -50%) scaleX(var(--hh-dir,1)) rotate(-10deg) translateY(0px); }
            to   { transform: translate(-50%, -50%) scaleX(var(--hh-dir,1)) rotate(10deg) translateY(-6px); }
        }
        @keyframes hh-spike {
            0%   { transform: translate(-50%, -50%) scaleX(var(--hh-dir,1)) scale(1); }
            40%  { transform: translate(-50%, -50%) scaleX(var(--hh-dir,1)) scale(1.6); }
            100% { transform: translate(-50%, -50%) scaleX(var(--hh-dir,1)) scale(1); }
        }

        /* Paw print */
        .paw-print {
            position: fixed;
            pointer-events: none;
            z-index: 99998;
            width: 12px;
            height: 12px;
            opacity: 0.6;
            animation: paw-fade 1s ease forwards;
        }
        @keyframes paw-fade {
            0%   { opacity: 0.6; transform: scale(1); }
            100% { opacity: 0; transform: scale(0.5); }
        }

        /* Linear cursor */
        #linear-cursor {
            position: fixed;
            pointer-events: none;
            z-index: 99999;
            width: 26px;
            height: 26px;
            transform: translate(-50%, -50%);
            display: none;
            filter: drop-shadow(0 0 6px #8B94E0) drop-shadow(0 0 12px #8B94E0);
            animation: linear-glow-idle 1.5s ease-in-out infinite alternate;
        }
        #linear-cursor.pulse {
            animation: linear-click-pulse 0.5s ease-out forwards;
        }
        @keyframes linear-glow-idle {
            from { filter: drop-shadow(0 0 4px #8B94E0) drop-shadow(0 0 8px #8B94E0); }
            to   { filter: drop-shadow(0 0 10px #8B94E0) drop-shadow(0 0 20px #b084f5); }
        }
        @keyframes linear-click-pulse {
            0%   { filter: drop-shadow(0 0 4px #8B94E0) drop-shadow(0 0 8px #8B94E0); transform: translate(-50%, -50%) scale(1); }
            40%  { filter: drop-shadow(0 0 18px #b084f5) drop-shadow(0 0 36px #8B94E0) drop-shadow(0 0 52px #8B94E0); transform: translate(-50%, -50%) scale(1.2); }
            100% { filter: drop-shadow(0 0 4px #8B94E0) drop-shadow(0 0 8px #8B94E0); transform: translate(-50%, -50%) scale(1); }
        }

        /* Zapier bolt trail */
        .zap-bolt-trail {
            position: fixed;
            pointer-events: none;
            z-index: 99997;
            transform: translate(-50%, -50%);
            animation: zap-trail-fade 0.35s ease forwards;
        }
        @keyframes zap-trail-fade {
            0%   { opacity: 0.7; }
            100% { opacity: 0; }
        }

        /* Zapier main cursor */
        #zap-cursor {
            position: fixed;
            pointer-events: none;
            z-index: 99999;
            transform: translate(-50%, -50%);
            display: none;
        }

        .paper-stack { position: relative; width: 100%; height: calc(100% - 66px); margin-top: 0; }
        .paper-behind { position: absolute; width: 100%; height: 100%; background: white; border-radius: 8px; border: 1px solid #eee; box-shadow: 0 2px 6px rgba(0,0,0,0.07); }
        .paper-top { position: absolute; width: 100%; height: 100%; overflow-y: auto; background: white; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 4px 14px rgba(0,0,0,0.11); padding: 18px; box-sizing: border-box; z-index: 3; transform-origin: center center; }
        .paper-top.toss { animation: toss-left 0.42s cubic-bezier(0.4,0,1,1) forwards; }
        .paper-top.rise { animation: rise-up 0.35s cubic-bezier(0.22,1,0.36,1) forwards; }
        .paper-top.warp { animation: warp-snap 0.5s ease-in-out forwards; }
        @keyframes toss-left {
            0%   { transform: translate(0,0) rotate(0deg) scale(1); opacity: 1; }
            30%  { transform: translate(-40px,-10px) rotate(-8deg) scale(0.95); opacity: 1; }
            100% { transform: translate(-360px,-20px) rotate(-28deg) scale(0.55); opacity: 0; }
        }
        @keyframes rise-up {
            0%   { transform: translate(0,10px) scale(0.97); opacity: 0.5; }
            100% { transform: translate(0,0) scale(1); opacity: 1; }
        }
        @keyframes warp-snap {
            0%   { transform: skewX(0deg) scaleX(1); }
            20%  { transform: skewX(18deg) scaleX(0.88); }
            45%  { transform: skewX(-12deg) scaleX(1.06); }
            65%  { transform: skewX(6deg) scaleX(0.97); }
            100% { transform: skewX(0deg) scaleX(1); }
        }
        .paper-arrow {
            position: absolute;
            top: 12px;
            background: none;
            border: none;
            font-size: 1.1rem;
            font-weight: 900;
            color: #111;
            cursor: pointer !important;
            padding: 0;
            line-height: 1;
            transition: transform 0.15s ease;
        }
        .paper-arrow:hover { transform: scale(1.3); }
        .paper-arrow-left { left: 14px; }
        .paper-arrow-right { right: 36px; }
        .paper-close-btn {
            position: absolute;
            top: 10px;
            right: 12px;
            background: none;
            border: none;
            font-size: 0.85rem;
            color: #bbb;
            cursor: pointer !important;
            padding: 0;
            line-height: 1;
        }
        .paper-close-btn:hover { color: #555; }
        .release-title-link { display: block; text-decoration: none; color: #111; font-size: 0.88rem; font-weight: 600; line-height: 1.4; cursor: pointer !important; margin-top: 28px; }
        .release-title-link:hover { text-decoration: underline; }
        .release-date { font-size: 0.72rem; color: #aaa; margin-top: 2px; margin-bottom: 8px; }
        .release-summary { font-size: 0.8rem; color: #555; margin-top: 6px; line-height: 1.5; }
        .release-analogy { font-size: 0.75rem; color: #888; margin-top: 8px; font-style: italic; }
        .paper-indicator { font-size: 0.68rem; color: #ccc; margin-top: 10px; text-align: center; }
        .blog-flip-container { position: relative; min-height: 120px; }
        .blog-card-inner { position: relative; width: 100%; }
        .blog-slide { display: none; }
        .blog-slide.active { display: block; }
        .blog-slide-title a { text-decoration: none; color: #111; font-size: 0.88rem; font-weight: 600; line-height: 1.4; cursor: pointer !important; }
        .blog-slide-title a:hover { text-decoration: underline; }
        .blog-slide-summary { font-size: 0.8rem; color: #666; margin-top: 6px; line-height: 1.5; }
        .blog-slide-date { font-size: 0.72rem; color: #aaa; margin-top: 4px; }
        .blog-indicator { font-size: 0.72rem; color: #bbb; margin-top: 12px; text-align: right; }
        .blog-nav { display: flex; justify-content: space-between; margin-top: 10px; }
        .blog-nav button { background: none; border: 1px solid #eee; border-radius: 6px; padding: 4px 10px; font-size: 0.75rem; color: #888; font-family: 'Sora', sans-serif; cursor: pointer !important; }
        .blog-nav button:hover { background: #f5f5f5; }
        .voice-global { display: flex; gap: 8px; flex-wrap: wrap; }
        .voice-pill { font-family: 'Sora', sans-serif; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.4px; padding: 5px 14px 6px; background: #f0f0f0; color: #222; border: 1px solid #bbb; border-bottom: 4px solid #999; border-radius: 6px; box-shadow: 0 2px 0 #aaa, 0 3px 4px rgba(0,0,0,0.12); cursor: pointer; transition: transform 0.07s ease, box-shadow 0.07s ease, border-bottom-width 0.07s ease; }
        .voice-pill:hover { background: #e6e6e6; transform: translateY(1px); border-bottom-width: 3px; box-shadow: 0 1px 0 #aaa, 0 2px 3px rgba(0,0,0,0.1); }
        .voice-pill.active { background: #ddd; color: #111; transform: translateY(3px); border-bottom-width: 1px; box-shadow: 0 0px 0 #aaa, inset 0 1px 3px rgba(0,0,0,0.15); }
    </style>
</head>
<body>

    <!-- Cursor elements -->
    <img id="hh-cursor" src="hedgehog.png" />
    <img id="linear-cursor" src="linear_cursor.png" />
    <div id="zap-cursor">
        <svg width="22" height="32" viewBox="0 0 22 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <polygon points="14,0 4,18 11,18 8,32 20,12 13,12 20,0" fill="#FF7A3D" stroke="white" stroke-width="1" stroke-linejoin="round"/>
        </svg>
    </div>
    <!-- Replit cursor -->
    <img id="replit-cursor" src="replit.png" style="position:fixed;pointer-events:none;z-index:99999;display:none;transform:translate(-50%,-50%);width:36px;height:auto;" />

    <div class="sticky-header">
        <img src="SteezyR.png" class="header-logo" alt="">
        <div class="heading">
            <span class="line1" id="heading-line1">Cool Companies,</span>
            <span class="line2" id="heading-line2">Fresh Releases.</span>
        </div>
        <p class="voice-label">Choose your own voice</p>
        <div class="voice-global">
            <button class="voice-pill active" onclick="setVoice('90s', this)">90s</button>
            <button class="voice-pill" onclick="setVoice('genz', this)">Gen Z</button>
            <button class="voice-pill" onclick="setVoice('medieval', this)">Medieval</button>
            <button class="voice-pill" onclick="setVoice('aifluff', this)">AI Fluff</button>
            <button class="voice-pill" onclick="setVoice('plain', this)">Plain</button>
        </div>
    </div>
    <div>
"""

# Build cards
for company in ["PostHog", "Linear", "Zapier", "Replit"]:
    color = company_colors.get(company, '#eee')
    company_releases = by_company.get(company, [])
    company_blogs = blog_by_company.get(company, [])
    card_id = company.lower().replace(" ", "-")
    section_class = f"section-{company.lower()}"

    html += f'<div class="company-row">'

    # Left: releases - no card, just floating name + paper stack
    html += f"""
    <div class="release-stack-wrap section-{company.lower()}" id="card-{card_id}">
        <span class="company-name-large" style="color:{color};">{company}</span>
        <div class="releases-label">Releases</div>
        <div class="paper-stack" id="stack-{card_id}">
            <div class="paper-behind" style="transform:translate(8px,10px); z-index:1; background:#f7f7f7;"></div>
            <div class="paper-behind" style="transform:translate(4px,5px); z-index:2; background:#fdfdfd;"></div>
            <div class="paper-top" id="paper-{card_id}">
                <button class="paper-arrow paper-arrow-left" onclick="event.stopPropagation(); paperNav('{card_id}', 'left')">&#8592;</button>
                <button class="paper-arrow paper-arrow-right" onclick="event.stopPropagation(); paperNav('{card_id}', 'right')">&#8594;</button>
                <a class="release-title-link" id="ptitle-{card_id}" href="#" target="_blank"></a>
                <div class="release-date" id="pdate-{card_id}"></div>
                <div class="release-summary" id="psummary-{card_id}"></div>
                <div class="release-analogy" id="panalogy-{card_id}"></div>
                <div class="paper-indicator" id="pindicator-{card_id}"></div>
            </div>
        </div>
    </div>
    """

    # Right: blog card
    html += f"""
    <div class="company-card section-{company.lower()}" onclick="event.stopPropagation()">
        <div class="company-tag">{company}</div>
        <div class="card-label blog-label">Blog & Changelog</div>
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
                <button class="blog-nav-prev" onclick="event.stopPropagation(); blogNav('{card_id}', -1)">&#8592; prev</button>
                <span class="blog-indicator" id="indicator-{card_id}">1 of {total}</span>
                <button class="blog-nav-next" onclick="event.stopPropagation(); blogNav('{card_id}', 1)">next &#8594;</button>
            </div>
        """
    else:
        html += """
            </div>
            <div class="coming-soon-label" style="color:#bbb; font-size:0.85rem; margin-top:8px;">Coming soon</div>
        """

    html += "</div></div>"
    html += "</div>"  # close company-row

    # Store releases as JS data
    releases_json = []
    import json
    for title, updated, link, summary, analogy, a90s, agenz, amedieval, aaifluff, aplain in company_releases:
        date = updated[:10] if updated else ""
        releases_json.append({
            'title': title,
            'date': date,
            'link': link,
            'summary': summary or '',
            'analogy': analogy or '',
            'analogy_90s': a90s or '',
            'analogy_genz': agenz or '',
            'analogy_medieval': amedieval or '',
            'analogy_aifluff': aaifluff or '',
            'analogy_plain': aplain or '',
        })

    html += f"""
    <script>
        window.releasesData = window.releasesData || {{}};
        window.releasesData['{card_id}'] = {json.dumps(releases_json)};
        window.releaseIndex = window.releaseIndex || {{}};
        window.releaseIndex['{card_id}'] = 0;
    </script>
    """

html += "    </div>\n"

html += """
    <script>
        var hhCursor = document.getElementById('hh-cursor');
        var linearCursor = document.getElementById('linear-cursor');
        var zapCursor = document.getElementById('zap-cursor');
        var replitCursor = document.getElementById('replit-cursor');
        var lastX = 0, lastY = 0;
        var facingLeft = false;

        var pawSVG = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><circle cx="10" cy="14" r="5" fill="#6f503a" opacity="0.5"/><circle cx="5" cy="8" r="3" fill="#6f503a" opacity="0.5"/><circle cx="15" cy="8" r="3" fill="#6f503a" opacity="0.5"/><circle cx="10" cy="4" r="2.5" fill="#6f503a" opacity="0.5"/></svg>');

        var boltSVG = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="20" viewBox="0 0 22 32"><polygon points="14,0 4,18 11,18 8,32 20,12 13,12 20,0" fill="#FF7A3D"/></svg>';

        document.addEventListener('mousemove', function(e) {
            var dx = e.clientX - lastX;
            var dy = e.clientY - lastY;
            var speed = Math.sqrt(dx*dx + dy*dy);

            // Hedgehog
            hhCursor.style.left = e.clientX + 'px';
            hhCursor.style.top = e.clientY + 'px';
            if (hhCursor.style.display === 'block') {
                if (dx < -2) facingLeft = true;
                else if (dx > 2) facingLeft = false;
                var dir = facingLeft ? -1 : 1;
                hhCursor.style.setProperty('--hh-dir', dir);

                if (!hhCursor.classList.contains('spike')) {
                    if (speed > 8) {
                        hhCursor.classList.remove('waddle');
                        void hhCursor.offsetWidth;
                        hhCursor.classList.add('waddle-fast');
                    } else {
                        hhCursor.classList.remove('waddle-fast');
                        void hhCursor.offsetWidth;
                        hhCursor.classList.add('waddle');
                    }
                }

                if (speed > 3 && Math.random() < 0.15) {
                    var paw = document.createElement('img');
                    paw.src = pawSVG;
                    paw.className = 'paw-print';
                    paw.style.left = (e.clientX - 6) + 'px';
                    paw.style.top = (e.clientY + 10) + 'px';
                    document.body.appendChild(paw);
                    setTimeout(function() { paw.remove(); }, 1000);
                }
            }

            // Linear
            linearCursor.style.left = e.clientX + 'px';
            linearCursor.style.top = e.clientY + 'px';

            // Replit cursor
            replitCursor.style.left = e.clientX + 'px';
            replitCursor.style.top = e.clientY + 'px';

            // Zapier cursor + bolt trail
            zapCursor.style.left = e.clientX + 'px';
            zapCursor.style.top = e.clientY + 'px';
            if (zapCursor.style.display === 'block' && Math.random() < 0.35) {
                var bolt = document.createElement('div');
                bolt.className = 'zap-bolt-trail';
                bolt.style.left = e.clientX + 'px';
                bolt.style.top = e.clientY + 'px';
                bolt.innerHTML = boltSVG;
                document.body.appendChild(bolt);
                setTimeout(function() { bolt.remove(); }, 380);
            }

            lastX = e.clientX;
            lastY = e.clientY;
        });

        // PostHog enter/leave
        document.querySelectorAll('.section-posthog').forEach(function(el) {
            el.addEventListener('mouseenter', function() {
                hhCursor.style.display = 'block';
                hhCursor.classList.add('waddle');
            });
            el.addEventListener('mouseleave', function() {
                hhCursor.style.display = 'none';
                hhCursor.classList.remove('waddle', 'waddle-fast', 'spike');
            });
        });

        // PostHog click - spines shoot out
        document.querySelectorAll('.section-posthog').forEach(function(el) {
            el.addEventListener('click', function(e) {
                hhCursor.classList.remove('waddle', 'waddle-fast', 'spike');
                void hhCursor.offsetWidth;
                hhCursor.classList.add('spike');
                setTimeout(function() {
                    hhCursor.classList.remove('spike');
                    void hhCursor.offsetWidth;
                    hhCursor.classList.add('waddle');
                }, 350);

                var colors = ['#e8962a', '#c45e00', '#f5b942', '#a0522d'];
                for (var i = 0; i < 8; i++) {
                    (function(idx) {
                        var spine = document.createElement('div');
                        var angle = (idx / 8) * 360;
                        var dist = 28 + Math.random() * 14;
                        spine.style.cssText = [
                            'position:fixed',
                            'pointer-events:none',
                            'z-index:99996',
                            'width:2px',
                            'height:' + (10 + Math.random() * 8) + 'px',
                            'background:' + colors[idx % colors.length],
                            'border-radius:2px',
                            'left:' + e.clientX + 'px',
                            'top:' + e.clientY + 'px',
                            'transform-origin:bottom center',
                            'transform:rotate(' + angle + 'deg) translateY(0px)',
                            'transition:transform 0.25s ease-out, opacity 0.3s ease-out'
                        ].join(';');
                        document.body.appendChild(spine);
                        void spine.offsetWidth;
                        spine.style.transform = 'rotate(' + angle + 'deg) translateY(-' + dist + 'px)';
                        spine.style.opacity = '0';
                        setTimeout(function() { spine.remove(); }, 350);
                    })(i);
                }
            });
        });

        // Linear enter/leave
        document.querySelectorAll('.section-linear').forEach(function(el) {
            el.addEventListener('mouseenter', function() { linearCursor.style.display = 'block'; });
            el.addEventListener('mouseleave', function() { linearCursor.style.display = 'none'; });
        });

        // Linear click - glow pulse
        document.querySelectorAll('.section-linear').forEach(function(el) {
            el.addEventListener('click', function(e) {
                linearCursor.classList.remove('pulse');
                void linearCursor.offsetWidth;
                linearCursor.classList.add('pulse');
                setTimeout(function() {
                    linearCursor.classList.remove('pulse');
                }, 520);
            });
        });

        // Zapier enter/leave
        document.querySelectorAll('.section-zapier').forEach(function(el) {
            el.addEventListener('mouseenter', function() { zapCursor.style.display = 'block'; });
            el.addEventListener('mouseleave', function() { zapCursor.style.display = 'none'; });
        });

        // Zapier click - zap burst
        document.querySelectorAll('.section-zapier').forEach(function(el) {
            el.addEventListener('click', function(e) {
                var ring = document.createElement('div');
                ring.style.cssText = 'position:fixed;pointer-events:none;z-index:99996;border-radius:50%;border:2px solid #FF7A3D;left:' + e.clientX + 'px;top:' + e.clientY + 'px;transform:translate(-50%,-50%);animation:zap-ring-out 0.5s ease-out forwards;';
                document.body.appendChild(ring);

                var burst = document.createElement('div');
                burst.style.cssText = 'position:fixed;pointer-events:none;z-index:99997;left:' + e.clientX + 'px;top:' + e.clientY + 'px;transform:translate(-50%,-50%);font-size:26px;animation:zap-burst-anim 0.5s ease-out forwards;';
                burst.textContent = '⚡';
                document.body.appendChild(burst);

                setTimeout(function() { ring.remove(); burst.remove(); }, 520);
            });
        });

        // Replit enter/leave
        document.querySelectorAll('.section-replit').forEach(function(el) {
            el.addEventListener('mouseenter', function() { replitCursor.style.display = 'block'; });
            el.addEventListener('mouseleave', function() { replitCursor.style.display = 'none'; });
        });

        // Replit click - image bounces/explodes
        document.querySelectorAll('.section-replit').forEach(function(el) {
            el.addEventListener('click', function(e) {
                replitCursor.style.transition = 'none';
                replitCursor.style.transform = 'translate(-50%, -50%) scale(1)';
                void replitCursor.offsetWidth;
                replitCursor.style.transition = 'transform 0.25s ease-out';
                replitCursor.style.transform = 'translate(-50%, -50%) scale(1.6)';
                setTimeout(function() {
                    replitCursor.style.transition = 'transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)';
                    replitCursor.style.transform = 'translate(-50%, -50%) scale(1)';
                }, 250);
            });
        });

        // Keyframes injected via JS for the zap ring + burst (avoids Python string escaping issues)
        var styleSheet = document.createElement('style');
        styleSheet.textContent = [
            '@keyframes zap-ring-out {',
            '  0%   { width:8px; height:8px; opacity:0.9; }',
            '  100% { width:60px; height:60px; margin-left:-26px; margin-top:-26px; opacity:0; border-width:0.5px; }',
            '}',
            '@keyframes zap-burst-anim {',
            '  0%   { opacity:1; transform:translate(-50%,-50%) scale(0.6) rotate(-20deg); }',
            '  30%  { opacity:1; transform:translate(-50%,-50%) scale(1.4) rotate(10deg); }',
            '  60%  { opacity:0.8; transform:translate(-50%,-50%) scale(1.1) rotate(-4deg); }',
            '  100% { opacity:0; transform:translate(-50%,-50%) scale(0.8); }',
            '}'
        ].join('\\n');
        document.head.appendChild(styleSheet);

        window.activeVoice = '90s';

        function loadPaper(id, idx) {
            var data = window.releasesData[id];
            if (!data || !data.length) return;
            var r = data[idx];
            document.getElementById('ptitle-' + id).textContent = r.title;
            document.getElementById('ptitle-' + id).href = r.link;
            document.getElementById('pdate-' + id).textContent = r.date;
            document.getElementById('psummary-' + id).textContent = r.summary;
            var el = document.getElementById('panalogy-' + id);
            el.dataset['90s']      = r.analogy_90s      || r.analogy || '';
            el.dataset.genz        = r.analogy_genz      || r.analogy || '';
            el.dataset.medieval    = r.analogy_medieval  || r.analogy || '';
            el.dataset.aifluff     = r.analogy_aifluff   || r.analogy || '';
            el.dataset.plain       = r.analogy_plain     || r.analogy || '';
            var text = el.dataset[window.activeVoice] || r.analogy || '';
            el.textContent = text ? '\u201c' + text + '\u201d' : '';
            document.getElementById('pindicator-' + id).textContent = (idx + 1) + ' of ' + data.length;
        }

        var voiceContent = {
            '90s': {
                line1:        'Dopest Companies,',
                line2:        'Da Bomb Drops.',
                releases:     'Drops',
                blog:         'Word On The Street',
                clickToView:  'peep it, feel me',
                comingSoon:   'coming soon, no doubt',
                blogPrev:     '\u2190 back it up',
                blogNext:     'keep it movin \u2192'
            },
            genz: {
                line1:        'Lowkey Cool Companies,',
                line2:        'No Cap Releases.',
                releases:     'Drops',
                blog:         'Tea & Updates',
                clickToView:  'tap to vibe check',
                comingSoon:   'dropping soon bestie',
                blogPrev:     '\u2190 slay back',
                blogNext:     'vibe forward \u2192'
            },
            medieval: {
                line1:        'Hear Ye, Noble Companies,',
                line2:        'Fresh Proclamations.',
                releases:     'Proclamations',
                blog:         "The Town Crier's Scroll",
                clickToView:  'hark and click hither',
                comingSoon:   'forthcoming, good patron',
                blogPrev:     '\u2190 prior scroll',
                blogNext:     'next scroll \u2192'
            },
            aifluff: {
                line1:        'Industry-Leading Companies,',
                line2:        'Transformative Releases.',
                releases:     'Deliverables',
                blog:         'Thought Leadership Hub',
                clickToView:  'engage for synergies',
                comingSoon:   'exciting content incoming',
                blogPrev:     '\u2190 previous insights',
                blogNext:     'next synergy \u2192'
            },
            plain: {
                line1:        'Cool Companies,',
                line2:        'Fresh Releases.',
                releases:     'Releases',
                blog:         'Blog & Changelog',
                clickToView:  'click to view',
                comingSoon:   'Coming soon',
                blogPrev:     '\u2190 prev',
                blogNext:     'next \u2192'
            }
        };

        function setVoice(voice, btn) {
            window.activeVoice = voice;
            document.querySelectorAll('.voice-pill').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            // Swap analogy text on all visible release cards
            document.querySelectorAll('.release-analogy').forEach(function(el) {
                var text = el.dataset[voice] || '';
                el.textContent = text ? '\u201c' + text + '\u201d' : '';
            });
            // Swap all other page text
            var v = voiceContent[voice];
            if (!v) return;
            document.getElementById('heading-line1').textContent = v.line1;
            document.getElementById('heading-line2').textContent = v.line2;
            document.querySelectorAll('.releases-label').forEach(function(el) { el.textContent = v.releases; });
            document.querySelectorAll('.releases-hint').forEach(function(el) { el.textContent = v.clickToView; });
            document.querySelectorAll('.blog-label').forEach(function(el) { el.textContent = v.blog; });
            document.querySelectorAll('.blog-nav-prev').forEach(function(el) { el.textContent = v.blogPrev; });
            document.querySelectorAll('.blog-nav-next').forEach(function(el) { el.textContent = v.blogNext; });
            document.querySelectorAll('.coming-soon-label').forEach(function(el) { el.textContent = v.comingSoon; });
        }

        function paperNav(id, dir) {
            var data = window.releasesData[id];
            if (!data || !data.length) return;
            var paper = document.getElementById('paper-' + id);
            if (paper._animating) return;
            paper._animating = true;
            var current = window.releaseIndex[id] || 0;
            var next = dir === 'left'
                ? (current + 1) % data.length
                : (current - 1 + data.length) % data.length;

            if (dir === 'left') {
                paper.classList.add('toss');
                setTimeout(function() {
                    paper.classList.remove('toss');
                    window.releaseIndex[id] = next;
                    loadPaper(id, next);
                    paper.classList.add('rise');
                    setTimeout(function() {
                        paper.classList.remove('rise');
                        paper._animating = false;
                    }, 370);
                }, 420);
            } else {
                paper.classList.add('warp');
                setTimeout(function() {
                    window.releaseIndex[id] = next;
                    loadPaper(id, next);
                }, 220);
                setTimeout(function() {
                    paper.classList.remove('warp');
                    paper._animating = false;
                }, 520);
            }
        }

        // Initialize all paper stacks on load
        document.addEventListener('DOMContentLoaded', function() {
            if (window.releasesData) {
                Object.keys(window.releasesData).forEach(function(id) {
                    window.releaseIndex[id] = 0;
                    loadPaper(id, 0);
                });
            }
        });

        document.addEventListener('click', function() {});

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