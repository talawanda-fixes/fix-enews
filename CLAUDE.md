# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python automation script that scrapes Talawanda School District's Smore newsletters, extracts and deduplicates content, performs OCR on image-only items, and generates an RSS feed. The script runs via GitHub Actions on a schedule.

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
# Run the full pipeline
python main.py

# Test individual components
python -m pytest tests/  # (if tests exist)
```

### Testing OCR
Tesseract must be installed system-wide:
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
- macOS: `brew install tesseract`
- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki

## Architecture

### Data Flow
1. **Scraper** (`scraper.py`) - Fetches newsletters from Smore
2. **Parser** (`parser.py`) - Extracts individual items and deduplicates
3. **OCR** (`ocr.py`) - Converts image-only content to text using Tesseract
4. **Feed Generator** (`feed_generator.py`) - Creates RSS 2.0 feed
5. **GitHub Actions** - Publishes feed to GitHub Pages or Releases

### Key Components

**scraper.py**: Handles HTTP requests to Smore, manages rate limiting, extracts newsletter HTML

**parser.py**:
- Parses newsletter HTML structure
- Extracts individual news items
- Implements deduplication logic (likely hash-based or content comparison)
- Maintains history of previously seen items

**ocr.py**:
- Detects image-only content
- Uses pytesseract wrapper for Tesseract OCR
- Handles image preprocessing for better OCR accuracy

**feed_generator.py**:
- Uses feedgen library
- Formats items according to RSS 2.0 spec
- Manages feed metadata (title, description, link)

### State Management
The script needs to maintain state between runs to deduplicate items. This is likely handled via:
- JSON file storing item hashes/IDs
- Committed to the repository or stored as artifact
- Checked and updated on each run

## GitHub Actions Workflow

The `.github/workflows/update-feed.yml` workflow:
- Runs on a schedule (cron)
- Sets up Python environment
- Installs Tesseract OCR
- Runs the scraper script
- Publishes output to GitHub Pages or Releases

## Important Notes

- The script must handle Smore's HTML structure changes gracefully
- Rate limiting is important when scraping to avoid being blocked
- OCR accuracy depends on image quality and preprocessing
- The deduplication mechanism must persist across workflow runs
- Feed should maintain item GUIDs for RSS reader compatibility
