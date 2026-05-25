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
