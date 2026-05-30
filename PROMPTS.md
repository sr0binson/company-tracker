# Prompts

## Company Tracker Page Redesign - Update Content, Layout & Cursors

Update `generate_html.py` and `index.html` with the following:

### Typography
- Import Sora from Google Fonts
- Page title: Sora, medium weight, top left aligned, lightweight feel
- "Cool Companies, Fresh Releases" subheading: Sora, large, bold, center aligned, with generous vertical spacing below the title

### Layout
- Organize companies into a 2x2 grid. Each company gets two side-by-side cards: releases on the left, changelog/blog on the right
- Release card displays the company name and a "Releases" label
- Changelog card displays the most recent entry as a short plain English summary with a link to the full post
- Clicking a release card expands it with a smooth animation revealing all releases newest to oldest
- Clicking a changelog card flips through the 5 most recent entries like a deck of cards, with a flip animation and a "1 of 5" position indicator

### Release Content
- Each release displays: release title, formatted date, a 1-3 sentence plain English AI summary, and a brief corny analogy that describes what changed in everyday terms
- Fetch full release notes from each GitHub release page
- Send release notes to the Anthropic API to generate the summary and analogy
- Store both in `releases.db` alongside existing fields

### Changelog/Blog Content
- Fetch the 5 most recent changelog or blog entries per company
- Display a short plain English summary with a link to the full post
- Where an obvious connection exists between a changelog entry and a release, link them to each other

### Cursors & Animations
- PostHog: Max the hedgehog as custom cursor, animates on click
- Zapier: Al the pixel art mascot (glasses, mustache, tie) as custom cursor, animates on click
- Replit: Replit logo as custom cursor, falls apart and reassembles on click
- Linear: Linear logo as custom cursor, glows softly like a moon on hover and fully illuminates on click

### Blog Date Order and Heading Style

Blog posts are fetched with `ORDER BY updated DESC` in SQL and sliced to 5 per company in Python insertion order, so card 1 is always the most recent post. No code change needed — confirmed correct.

Style the "Fresh Releases." heading span with inline styles: `font-style: italic; color: #FF6B00; -webkit-text-stroke: 1.5px black; text-shadow: 0 0 12px #FF6B00, 2px 2px 0px #000`. The "Cool Companies," line is unstyled.

### Equal Height Cards Fix

Make both columns in `.company-row` equal height by changing `align-items: start` to `align-items: stretch`. Set `.release-stack-wrap` to `height: 100%; box-sizing: border-box` so it fills its grid cell. Give `.paper-stack` a height of `calc(100% - 60px)` to fill the wrapper after the company name. Set `.paper-behind` and `.paper-top` to `height: 100%` so they fill the stack; `.paper-top` keeps `overflow-y: auto` for scrolling.

### Release Stack Alignment and Company Name Visibility

Give `.release-stack-wrap` the same card styling as `.company-card` (white background, border-radius 12px, padding 20px, box-shadow) so the release column matches the blog card height and appearance. Remove the per-element `text-shadow` override from the company name span so the class rule applies cleanly.

For the company name, increase visibility with a strong black drop shadow and outline: `text-shadow: 2px 2px 0px #000, 4px 6px 16px rgba(0,0,0,0.4)` and `-webkit-text-stroke: 1px black`. Keep the brand color on the text itself.

### Paper Stack Fixed Height

Give `.paper-stack` a fixed height of 220px and `.paper-top` a fixed height of 200px (replacing `min-height`) with `overflow-y: auto`, so long release content scrolls inside the card instead of expanding it. This keeps the release column the same height as the blog card column, preventing misalignment in the two-column layout.

### Prompt Injection Defense

`sanitize_input(text)` in `fetch_feeds.py` strips four categories of suspicious content using `re.sub`:
- `<script>` tags and their contents
- `javascript:` pseudo-URLs
- `on*` event attributes (`onclick=`, `onload=`, etc.)
- Prompt injection phrases: `ignore previous instructions`, `you are now`, `disregard`, `new instructions:`

Applied at two points per field: (1) on raw RSS `title` and `description`/`content` **before** passing to Claude API calls — blocks prompt injection via feed content attacking the AI; (2) on all text fields (`title`, `summary`, `analogy`, all four voice variants) **before every DB INSERT/UPDATE** — defence in depth against stored XSS.

The CSP meta tag in `generate_html.py` is tightened with `object-src 'none'` (blocks plugin execution) and `base-uri 'self'` (blocks `<base>` tag injection). `script-src 'unsafe-inline'` is retained because the page is entirely inline JS — removing it would break all interactivity. `connect-src 'none'` already blocks all outbound fetch/XHR.

### Pre-generated Voice Selector and Security

Instead of live API calls from the browser, generate all voice variants at fetch time in `fetch_feeds.py`. Four new columns in `releases`: `analogy_90s`, `analogy_genz`, `analogy_medieval`, `analogy_aifluff`. Each is generated with a single Haiku call per voice per new release (4 extra calls per release — see rate-limit comment in `fetch_feeds.py`). Existing DBs get the columns via `ALTER TABLE ... ADD COLUMN` with a silent `except` guard.

In `generate_html.py`, all five analogy variants are passed into the per-company JS `releasesData` object. The paper stack shows five toggle buttons ("Original", "90s", "Gen Z", "Medieval", "AI Fluff"); clicking one calls `swapVoice(id, field, btn)` which does an instant DOM text swap — no fetch, no loading state. Navigating to a new release resets to "Original" active.

A `Content-Security-Policy` meta tag restricts resources to: inline styles/scripts (`unsafe-inline`), Google Fonts CSS and files, self-origin images and `data:` URIs, and `connect-src 'none'` to block all outbound fetch/XHR.

### 2026-05-25 — Update 90s voice to late 90s R&B hip hop slang

The original `analogy_90s` prompt was too generic (tubular, radical — more 80s/early 90s). Updated to specifically target late 90s R&B and hip hop slang with example phrases: "all that and a bag of chips", "da bomb", "feel me", "no doubt", "word", "straight up", "mad [adjective]", "on the real", "that joint is", "for real for real". Re-ran backfill for all 40 existing rows in `releases.db` using Haiku.

### 2026-05-25 — Add Plain voice option

Added a fifth analogy voice: `analogy_plain`. Prompt: rewrite in plain, clear one or two sentence language a normal person would understand — no slang, no jargon, no style. Added `analogy_plain` column to `releases` table schema and `ALTER TABLE` guard. Added to `VOICE_PROMPTS`, backfill query (triggers on `analogy_plain IS NULL`), and all INSERT/UPDATE statements in `fetch_feeds.py`. Added "Plain" pill button to the global voice selector in `generate_html.py`. Updated `loadPaper` to set `data-plain`; `setVoice` already handles it generically. Backfilled all 40 existing rows.

### 2026-05-25 — Voice selector swaps all page content

When a voice is selected, swap all visible page text (except "Company Tracker" in the top left). Elements targeted: `#heading-line1`, `#heading-line2`, `.releases-label`, `.releases-hint` (click to view), `.blog-label`, `.blog-nav-prev`, `.blog-nav-next`, `.coming-soon-label`. Added "Releases" and "click to view" hint labels to the release stack wrapper HTML. Added `blog-label`, `blog-nav-prev`, `blog-nav-next`, `coming-soon-label` classes to existing elements. `voiceContent` object in JS holds all 5 voice versions hardcoded. `setVoice` now swaps analogy data-attributes AND all `voiceContent` text strings. Five voices: `90s` (late 90s R&B hip hop), `genz` (Gen Z), `medieval` (town crier), `aifluff` (AI marketing), `plain` (default clear language).

### 2026-05-26 — Sticky header includes heading and voice buttons, only grid scrolls

Moved `.heading` div inside `.sticky-header` so the big "Cool Companies, / Fresh Releases." heading sticks with the voice controls. Only the company grid and cards scroll underneath. Removed `margin-top: 2rem` from `.heading` (no longer needed inside the header) and reduced `margin-bottom` to `1.2rem`. Increased sticky-header padding to `20px / 16px` to give the larger content breathing room. Added `padding-bottom: 100vh` to `body` so the last card can scroll completely off screen.

### 2026-05-26 — Fix sticky header to voice buttons only, remove Company Tracker, raised keycaps

Removed `<h1>Company Tracker</h1>` and its CSS rule entirely. Sticky header now contains only the "Choose your own voice" label and 5 voice buttons. Reduced sticky-header padding to 12px top / 10px bottom; added `border-bottom: 1px solid #e8e8e8` to visually separate it from scrolling content. Big heading and company grid scroll freely underneath.

Keycap redesign: light gray top face (#f0f0f0), dark text (#222), `border: 1px solid #bbb`, `border-bottom: 4px solid #999`, `box-shadow: 0 2px 0 #aaa, 0 3px 4px rgba(0,0,0,0.12)` — gives a raised physical key appearance. Hover shifts down 1px / reduces depth. Active (pressed) shifts down 3px, collapses border-bottom to 1px, adds `inset` shadow.

### 2026-05-26 — Sticky header, keycap voice buttons, Oswald Fresh Releases font

Added `Oswald:ital,wght@1,700` to Google Fonts import. Applied via CSS rule on `#heading-line2` (font-family, italic, 700 weight, #FF6B00 color) — removed the inline style from the span. "Cool Companies," stays in Sora.

Centered `h1` ("Company Tracker") with `text-align: center` and `padding-bottom: 16px`. Wrapped h1, voice label, and voice buttons in `<div class="sticky-header">` with `position: sticky; top: 0; z-index: 100; background: #f9f9f9`. Uses negative margin / restored padding to extend the background flush with body edges. The `.heading` (Cool Companies / Fresh Releases) sits below the sticky section and scrolls away. Body top margin removed (was 40px); header padding provides initial spacing.

Added `<p class="voice-label">Choose your own voice</p>` above voice buttons in the sticky header; styled small (0.72rem), muted (#aaa), Sora 300.

Voice pills restyled as keycaps: dark background (#1a1a1a), white text, `border-bottom: 3px solid #000` for depth, `border-radius: 5px`. Hover shifts down 1px and reduces bottom border. Active state shifts down 2px / 1px border (pressed look).

Company tags (`<div class="company-tag">`) now white background, black border (1.5px solid #111), black text — filled color backgrounds removed. Inline `style` attribute stripped from the template; CSS `!important` enforces the overrides.

### 2026-05-26 — Sticky header includes heading and voice buttons, header is position: fixed

Changed `.sticky-header` from `position: sticky` to `position: fixed` so it never moves even when scrolling back to the top. Added `left: 50%; transform: translateX(-50%); width: 100%; max-width: 1100px` so the fixed header stays centered within the 1100px body layout. Increased `body` padding-top to `220px` so scrollable content starts below the fixed header. The sticky header contains: big heading ("Cool Companies," and "Fresh Releases."), "Choose your own voice" label, and 5 voice buttons. Only the company grid scrolls underneath.

### 2026-05-26 — Tuck paper stack inside releases card, clean up layout

Removed the "Releases" card-label div and "click to view" card-hint div from the release stack HTML. Added a single `<div class="releases-label">` with `text-align: right`, `font-size: 0.68rem`, `color: #ccc`, uppercase + letter-spacing — sits right-aligned above the paper stack. Added `overflow: hidden` to `.release-stack-wrap` so nothing in the stack can poke outside the card boundary. Adjusted `.paper-stack` height from `calc(100% - 60px)` to `calc(100% - 66px)` to account for the new single-label layout. Voice swap still targets `.releases-label` class so text changes on voice select.

### 2026-05-26 — Copy SteezyR logo from Downloads and add to fixed header

Copied `SteezyR.png` from `~/Downloads/` into the project root. Added `<img src="SteezyR.png" class="header-logo">` inside `.sticky-header` in `generate_html.py`. CSS: `.header-logo { position: absolute; top: 12px; right: 20px; height: 70px; width: auto; pointer-events: none; }` — absolute-positioned top-right inside the fixed header so it floats without affecting heading or voice button layout. Committed `SteezyR.png` to git so it deploys to GitHub Pages.

### 2026-05-29 — Replace Linear and Replit cursor images with inline SVGs

Swapped `<img id="linear-cursor" src="linear_cursor.png">` for an inline SVG circle (fill `#8B94E0`) and `<img id="replit-cursor" src="replit.png">` for an inline SVG of three stacked rectangles (fill `#AAAAAA`). All CSS animations and JS event handlers unchanged — they reference the same element ids, which work identically on SVG nodes. Added prompt-logging rule to CLAUDE.md.

### 2026-05-29 — Smaller Replit cursor blocks with scatter-and-snap click animation

Shrunk the three Replit SVG rects (width 30→22, height 8→6, viewBox adjusted to 36×24, overall SVG width 36→30px). Replaced the old bounce/scale click handler with one that animates each block individually: on click each rect flies to a random translate+rotate offset, then snaps back via a spring cubic-bezier. All other CSS and JS untouched.

### 2026-05-29 — Fix empty-content AI complaints and rename "Blog & Changelog" to "Updates"

Added content-length guard to `get_ai_summary`: if content is empty or under 20 chars, skip the API call and return `(title, "")` immediately. Updated prompt to say "If you have very little information, write one short sentence based on the title alone." Changed call sites to pass raw `content` instead of `content or title`. Added backfill step that detects existing complaint-style summaries (LIKE patterns: "I don't have", "I cannot", etc.) and resets them to `summary = title, analogy = ""`. "Blog & Changelog" label was already "Updates" everywhere — no change needed.

### 2026-05-29 — Query PostHog blog post links from DB

Ran `sqlite3 releases.db "SELECT link FROM blog_posts WHERE company='PostHog' LIMIT 5;"` — returned 5 live PostHog blog URLs.

### 2026-05-29 — Major layout and feature overhaul: 4-row grid, flip cards, jobs, keyword bubbles, sparklines

Rewrote `generate_html.py` and extended `fetch_feeds.py` with:
- Layout changed from 2×2 grid to 4 rows × 2 columns (one row per company)
- Left column: existing paper stack blog/changelog cards (unchanged)
- Right column: new CSS 3D flip card (400ms horizontal flip, ↺ icon)
- Flip front: open roles count (clickable → popover of departments/jobs), keyword bubble SVG (frequency-weighted, packed, company color), sparkline bar chart (last 6 months post activity)
- Flip back: "Who they serve" pill tags, "Competes with" competitor outline pills
- Added `jobs` table to `releases.db`; `fetch_jobs()` hits Ashby public API for PostHog/Linear/Zapier/Replit, skips refetch if data is under 7 days old
- Jobs fetched: PostHog 16, Linear 26, Zapier 22, Replit 89
- Keyword extraction runs at generation time from all blog_posts titles + summaries; stop-word filtered
- Monthly post counts computed from DB grouped by calendar month

### 2026-05-29 — Run python3 generate_html.py

Ran `python3 generate_html.py` — no errors, index.html regenerated successfully.

### 2026-05-29 — Log session prompts to prompts.md; read CLAUDE.md before every prompt

Added all prompts from this session to `prompts.md`. Established rule: read `CLAUDE.md` before responding to every prompt going forward in this session.

### 2026-05-29 — Run python3 generate_html.py (2)

Ran `python3 generate_html.py` — no errors, index.html regenerated successfully.

### 2026-05-29 — cat claude.md

Printed CLAUDE.md contents to terminal.

### 2026-05-29 — cat prompts.md

Printed prompts.md contents to terminal.

### 2026-05-29 — Tested prompt logging

Tested prompt logging.

### 2026-05-29 — ls

Listed files in project root.

### Future Ideas

**Analogy Voice Selector:**
- Allow users to choose the "voice" for the corny analogy on each release
- Options: Simple (default), Middle English, Gen Z, 90s Slang
- Each voice rewrites the same analogy in that style via the Anthropic API
- Could be a small toggle or dropdown on each release card
