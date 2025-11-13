# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This Python automation script scrapes Talawanda High School's Smore newsletters from their blog, extracts individual news items, deduplicates them across newsletters, and generates an RSS feed. The script runs via GitHub Actions on a schedule and publishes to GitHub Pages.

## Development Commands

### Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running the Script
```bash
# Set your Anthropic API key (required for AI summaries)
export ANTHROPIC_API_KEY='your-api-key-here'

# Run the full pipeline
python main.py

# Outputs:
# - output/feed.rss (RSS 2.0 feed with AI-generated summaries)
# - output/items.json (structured JSON data of all items with summaries)
```

### Testing Individual Components
```python
# Test scraper
from scraper import get_newsletter_links, fetch_newsletter
links = get_newsletter_links()
newsletter = fetch_newsletter(links[0])

# Test parser
from parser import parse_newsletters, deduplicate_items
items = parse_newsletters([newsletter])
unique = deduplicate_items(items)

# Test feed generation
from feed_generator import generate_feed
generate_feed(unique, "test_feed.rss")
```

## Architecture

### Data Flow
1. **Scraper** (`scraper.py`) - Fetches newsletter links from blog, then fetches each newsletter using Selenium
2. **Parser** (`parser.py`) - Extracts individual items from newsletters and deduplicates using block IDs
3. **Feed Generator** (`feed_generator.py`) - Creates RSS 2.0 feed with HTML content
4. **GitHub Actions** - Publishes feed to GitHub Pages and commits state file

### Key Components

**summarizer.py**:
- Uses Claude (model: claude-sonnet-4-5-20250929) to generate concise summaries of newsletter items
- Replaces verbose text and image descriptions with clear, text-only markdown
- Preserves important details (dates, locations, links) while making content accessible
- FAIL-HARD: Script will fail if API key is missing or summarization fails (no fallback)

**scraper.py**:
- Uses requests + BeautifulSoup to find Smore links on Talawanda blog (https://www.talawanda.org/talawanda-high-school-blog/)
- Finds all `<a>` tags with `href` containing "smore.com"
- Uses Selenium + Chrome (headless) to render JavaScript-heavy Smore newsletters
- Waits 5 seconds for content to load after page renders
- Returns list of dictionaries with 'url', 'html', 'soup', 'title'

**parser.py**:
- Parses rendered Smore HTML looking for `div` elements with `data-block-type` attribute
- Recognizes block types: header, text.title, text.paragraph, image.single, items, misc.separator, signature
- Groups content by `text.title` blocks (each title starts a new news item)
- Extracts `data-block-id` from title blocks for unique identification
- Deduplicates using block IDs (not content hashing) within current run only
- When an item appears in multiple newsletters, keeps the earliest date
- No state file is saved - full feed is regenerated on each run

**feed_generator.py**:
- Uses feedgen library to create RSS 2.0 feed
- Converts AI-generated markdown summaries to HTML for feed items
- REQUIRES summaries (no fallback) - will fail if summaries are missing
- Uses block_id as GUID for RSS reader compatibility
- Adds link back to source newsletter
- Publication dates use newsletter dates from blog

**ocr.py**:
- Currently not implemented (placeholder for future OCR functionality)
- Would use pytesseract for image-to-text conversion

### Smore Newsletter Structure

Smore newsletters are React/Svelte SPAs that require JavaScript rendering. Key HTML structure:
- Content blocks have `data-block-type` and `data-block-id` attributes
- Block IDs are unique and persistent (e.g., "bptr724lk3")
- Common block types: text.title (section headers), text.paragraph (text content), image.single (images)
- Images use CDN URLs like `https://cdn.smore.com/u/thumbs/...` (replace '/thumbs/' with '/' for full size)

## GitHub Actions Workflow

The `.github/workflows/update-feed.yml` workflow:
- Runs every 6 hours (cron: '0 */6 * * *'), on push to main, and can be manually triggered
- Installs chromium-browser and chromium-chromedriver (for Selenium)
- Caches Chromium installation for faster runs
- Runs `python main.py` to generate feed
- Deploys `output/` directory to GitHub Pages (gh-pages branch)
- RSS feed will be available at `https://[username].github.io/[repo]/feed.rss`

## Important Notes

- **Anthropic API Key REQUIRED**: Set `ANTHROPIC_API_KEY` environment variable for AI summaries
  - Script will FAIL if API key is missing or summarization fails (no fallback)
  - In GitHub Actions, add `ANTHROPIC_API_KEY` as a repository secret
  - Uses model: claude-sonnet-4-5-20250929
- Selenium requires ChromeDriver and Chrome/Chromium to be installed
- The 5-second wait in scraper is critical for Smore content to load
- Block IDs are the source of truth for deduplication (not content hashing)
- No state file is saved - the entire feed is regenerated from all newsletters each run
- RSS feed shows all unique items from all newsletters currently on the blog
- Items are dated based on their first newsletter appearance and sorted newest first
- AI summaries replace original content - images are described, verbose text is condensed
- Each summary costs ~$0.001-0.002 using Claude Sonnet 4 (~300 tokens per item)
