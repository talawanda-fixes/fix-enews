# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This Python automation framework supports multiple independent "scrape, parse, analyze, publish" pipelines. Currently implements:
- **newsletter_feed**: Scrapes Talawanda School District newsletters/blog posts → AI summaries → RSS feeds
- **menu_calendar** (stub): Future pipeline for scraping school menu calendars → ICS files

Configuration via `newsletters.json`. Runs via GitHub Actions, publishes to GitHub Pages.

## Commit Message Guidelines

When creating commits, follow these principles:
- **Be concise and consumable** - High-level summary followed by critical implementation details only
- **Focus on the "why"** rather than exhaustive "what"
- Keep to 1-2 sentences in the body, avoid bullet-point lists of every change
- End with attribution footer (see Git Workflow section below)

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

### Running the Newsletter Feed Pipeline
```bash
# Set your Anthropic API key (required for AI summaries)
export ANTHROPIC_API_KEY='your-api-key-here'

# Run for all schools (configured in newsletters.json)
python -m newsletter_feed.main

# Run for a specific school
python -m newsletter_feed.main --school ths

# Limit number of items (useful for testing)
python -m newsletter_feed.main --school ths --limit 10

# Outputs per school:
# - output/{school-slug}-feed.rss (RSS 2.0 feed with AI-generated summaries and calendar links)
# - output/{school-slug}-items.json (structured JSON data of all items with summaries)
```

### Testing Individual Components
```python
# Test scraper
from common.scraper import get_newsletter_links, fetch_newsletters
links = get_newsletter_links()
newsletters = fetch_newsletters()

# Test parser
from common.parser import parse_newsletters, deduplicate_items
items = parse_newsletters(newsletters)
unique = deduplicate_items(items)

# Test feed generation
from newsletter_feed.feed_generator import generate_feed
generate_feed(unique, "test_feed.rss", "Test School")
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test module
pytest tests/common/test_scraper.py

# Run with coverage
pytest --cov=common --cov=newsletter_feed
```

## Architecture

### Project Structure
```
project/
├── common/                      # Shared utilities across use cases
│   ├── rate_limiter.py         # HTTP rate limiting
│   ├── cache.py                # Three-tier caching (newsletters, parsed, summaries)
│   ├── scraper.py              # HTTP + Selenium fetching
│   ├── parser.py               # HTML parsing + deduplication
│   └── ai_integration.py       # Anthropic client + vision API
│
├── newsletter_feed/             # Newsletter → RSS pipeline
│   ├── main.py                 # Entry point
│   ├── summarizer.py           # AI summarization with event detection
│   ├── feed_generator.py       # RSS 2.0 generation
│   ├── calendar_helper.py      # Calendar link generation
│   ├── generate_index.py       # Static site generation
│   └── templates/              # HTML templates
│
├── menu_calendar/               # Menu → ICS pipeline (stub)
│   └── main.py                 # Placeholder
│
├── tests/                       # Test suite
│   ├── common/                 # Tests for shared utilities
│   ├── newsletter_feed/        # Tests for newsletter pipeline
│   └── fixtures/               # Test data
│
├── newsletters.json             # Configuration for newsletter sources
└── requirements.txt
```

### Newsletter Feed Data Flow
1. **Scraper** (`common.scraper`) - Fetches newsletters and blog posts from school blogs, using Selenium for Smore newsletters
2. **Parser** (`common.parser`) - Extracts individual items from sources and deduplicates using block IDs
3. **Summarizer** (`newsletter_feed.summarizer`) - Generates AI summaries with event detection and calendar link generation
4. **Feed Generator** (`newsletter_feed.feed_generator`) - Creates RSS 2.0 feed with HTML content and calendar links
5. **GitHub Actions** - Builds Docker image, runs pipeline per school, publishes to GitHub Pages

### Key Components

**newsletter_feed/summarizer.py**:
- Uses Claude (model: claude-sonnet-4-5-20250929) with vision API to analyze newsletter items and images
- Generates concise markdown summaries, replaces verbose text with clear descriptions
- **Event Detection**: Automatically detects events (meetings, games, deadlines) and extracts structured data
- **Year Inference**: For incomplete dates (e.g., "November 14th"), infers year as the FIRST occurrence of that date AFTER the item's publication date
- **Multi-Event Support**: Can extract multiple events from a single item (e.g., weekly club schedules)
- Returns `event_info` as array of dicts with: title, start/end datetime, location, description
- FAIL-HARD: Script will fail if API key is missing or summarization fails (no fallback)
- Caches summaries by block_id in `cache/summaries/` (handles both single dict and array formats for backward compatibility)

**common/scraper.py**:
- Uses requests + BeautifulSoup to scrape school blog pages configured in `newsletters.json`
- Supports both Smore newsletters (`.smore.com` links) and regular blog posts
- Uses Selenium + Chrome (headless) to render JavaScript-heavy Smore newsletters
- Uses WebDriverWait for efficient page rendering (event-based, not fixed delays)
- **Rate Limiting**: Implements per-host rate limiting (30 requests per 20 seconds) instead of fixed delays
- Caches by URL (MD5 hash) in `cache/newsletters/` to avoid re-fetching
- **Pagination**: Follows "next page" links, stops when hitting all-cached pages for efficiency
- Returns list of dicts with 'url', 'html', 'soup', 'title', 'date', 'type' (newsletter or blog_post)

**common/parser.py**:
- Parses Smore HTML (`data-block-type` divs) and blog post HTML (standard HTML content)
- For Smore: Groups by `text.title` blocks, extracts `data-block-id` for unique identification
- For blog posts: Creates single item per post using URL-based ID
- **Parsed Cache**: Caches parsed items in `cache/parsed/` to avoid re-parsing HTML (~8x faster)
- Deduplicates using block IDs/hashes across all sources
- When an item appears in multiple sources, keeps the earliest date
- Filters noise (footer branding, empty content)

**newsletter_feed/feed_generator.py**:
- Uses feedgen library to create RSS 2.0 feed
- Converts AI-generated markdown summaries to HTML for feed items
- **Calendar Links**: For events, generates "Add to Calendar" links (Google Calendar, iCal, Outlook)
- **Multi-Event Support**: Creates separate calendar links for each event when item has multiple events
- **Anchor Links**: Adds `#block-id` anchors to source links for deep linking to specific items
- REQUIRES summaries (no fallback) - will fail if summaries are missing
- Uses block_id as GUID for RSS reader compatibility

**common/rate_limiter.py**:
- Implements per-host rate limiting (30 requests per 20 seconds)
- Used by scraper to prevent overwhelming servers
- Tracks request timestamps per host with sliding window

**common/cache.py**:
- Consolidates all caching functionality (newsletters, parsed items, summaries)
- Three-tier cache system for optimal performance
- Handles JSON serialization and datetime conversions

**common/ai_integration.py**:
- Anthropic API client wrapper
- Image fetching and base64 encoding for vision API
- Reusable across different use cases

### Smore Newsletter Structure

Smore newsletters are React/Svelte SPAs that require JavaScript rendering. Key HTML structure:
- Content blocks have `data-block-type` and `data-block-id` attributes
- Block IDs are unique and persistent (e.g., "bptr724lk3")
- Common block types: text.title (section headers), text.paragraph (text content), image.single (images)
- Images use CDN URLs like `https://cdn.smore.com/u/thumbs/...` (replace '/thumbs/' with '/' for full size)

**newsletter_feed/calendar_helper.py**:
- Generates calendar links for event items (Google Calendar, iCal, Outlook.com)
- Creates properly formatted URLs with encoded event data (title, dates, location, description)
- Used by feed_generator.py to add "Add to Calendar" functionality

**newsletter_feed/main.py**:
- Entry point that orchestrates the pipeline for each school
- Supports `--school` and `--limit` CLI arguments
- Loads school configurations from `newsletters.json`
- Handles JSON serialization of datetime objects and event_info arrays
- Provides timing metrics for each pipeline step

**newsletter_feed/generate_index.py**:
- Generates static HTML index pages for viewing feeds
- Uses Jinja2 templates to render school list
- Copies newsletters.json to output directory for viewer

## GitHub Actions Workflow

The `.github/workflows/update-feed.yml` workflow:
- Runs every 6 hours (cron: '0 */6 * * *'), on push to main, and can be manually triggered
- **Setup Job**: Reads school list from `newsletters.json` to create matrix
- **Build Job**: Builds Docker image with hash-based caching (skips build if Dockerfile/requirements.txt unchanged)
- **Generate Job**: Runs `python -m newsletter_feed.main` per school in parallel matrix, with separate cache layers per school
- **Deploy Job**: Combines all school feeds, runs `python -m newsletter_feed.generate_index`, deploys to GitHub Pages
- RSS feeds available at `https://[username].github.io/[repo]/{school-slug}-feed.rss`

## Important Notes

### API Requirements
- **Anthropic API Key REQUIRED**: Set `ANTHROPIC_API_KEY` environment variable
  - Script will FAIL if API key is missing or summarization fails (no fallback)
  - In GitHub Actions, add as repository secret
  - Uses model: claude-sonnet-4-5-20250929 with vision API

### Caching Strategy
Three-tier cache system for optimal performance:
- `cache/newsletters/` - Raw HTML by URL (MD5 hash), shared across all runs
- `cache/parsed/` - Parsed items by newsletter URL, ~8x faster than re-parsing
- `cache/summaries/` - AI summaries by block_id, saves API calls and costs
- GitHub Actions uses separate cache keys per school for parallel processing
- Cached runs complete in seconds vs minutes (no API calls, minimal Selenium)

### Performance Optimizations
- **Rate Limiting**: Per-host throttling (30 req/20s) instead of fixed delays
- **Pagination Short-Circuit**: Stops scraping when hitting all-cached pages
- **Event-Based Waiting**: WebDriverWait instead of fixed sleep delays
- **Parallel Execution**: GitHub Actions matrix runs schools in parallel
- **Docker Caching**: Hash-based image cache skips rebuilds when dependencies unchanged

### Key Behaviors
- Block IDs are source of truth for deduplication (not content hashing)
- No state file saved - full feed regenerated each run from all sources
- Items appearing in multiple sources keep earliest date
- AI summaries replace original content completely
- Cost: ~$0.001-0.002 per item for Claude Sonnet 4, but cache minimizes recurring costs

### Git Workflow
When committing changes, use this format:
```
Brief, high-level summary line

One to two sentences with critical implementation details. Focus on why, not exhaustive what.

Developed with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>
```
