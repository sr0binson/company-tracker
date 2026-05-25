# Prompts

## Company Tracker Page Redesign

Update the Company Tracker `generate_html.py` and `index.html` with the following:

**Typography:**
- Import Sora from Google Fonts
- Page title: Sora, small, top left aligned, lightweight
- "Cool Companies, Fresh Releases" heading: Sora, large, bold, center aligned, with more vertical spacing from the title

**Layout:**
- Display companies in a 2x2 grid: PostHog and Linear on top row, Zapier and Replit on bottom row
- Each company is a card showing only the company name by default
- On click, the card expands with a smooth animation to reveal all releases newest to oldest

**Release content:**
- Each release shows: release title, plain English AI-generated summary, and formatted date
- Fetch full release notes from the GitHub release page for each entry
- Pass release notes to the Anthropic API to generate a 1-2 sentence plain English summary
- Store the summary in `releases.db` alongside existing fields
