# Talawanda Enews RSS Converter

Automated script that converts Talawanda School District's Smore newsletters into an RSS feed format.

## Overview

This project scrapes newsletters from Smore, extracts individual items, deduplicates content, performs OCR on image-only content, and generates an RSS feed. The feed is automatically published via GitHub Actions.

## Features

- Scrapes Talawanda enews newsletters from Smore
- Parses individual newsletter items
- Deduplicates repeated content
- OCR for image-only information
- Generates RSS 2.0 feed
- Automated publishing via GitHub Actions

## Requirements

- Python 3.9+
- Tesseract OCR (for image-to-text conversion)

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Tesseract OCR (system dependency)
# Ubuntu/Debian: sudo apt-get install tesseract-ocr
# macOS: brew install tesseract
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
```

## Usage

```bash
# Run the scraper and generate RSS feed
python main.py

# Output will be in output/feed.rss
```

## GitHub Actions

The workflow runs automatically on a schedule to keep the RSS feed updated. See `.github/workflows/update-feed.yml` for configuration.

## Project Structure

```
├── main.py              # Main script entry point
├── scraper.py           # Smore newsletter scraper
├── parser.py            # Content parser and deduplicator
├── ocr.py               # Image-to-text conversion
├── feed_generator.py    # RSS feed generation
├── requirements.txt     # Python dependencies
└── .github/
    └── workflows/
        └── update-feed.yml  # GitHub Actions workflow
```
