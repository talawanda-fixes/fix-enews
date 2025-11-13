#!/usr/bin/env python3
"""
Talawanda Enews RSS Converter
Main entry point for the scraper pipeline
"""

import os
import sys
from pathlib import Path


def main():
    """Main pipeline execution"""
    print("Talawanda Enews RSS Converter")
    print("=" * 50)

    # Create output directory
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    try:
        # Step 1: Scrape newsletters from Smore
        print("\n[1/4] Scraping newsletters from Smore...")
        from scraper import fetch_newsletters
        newsletters = fetch_newsletters()

        if not newsletters:
            print("Error: No newsletters found!")
            return 1

        # Step 2: Parse and extract items
        print("\n[2/4] Parsing and extracting items...")
        from parser import parse_newsletters, deduplicate_items
        items = parse_newsletters(newsletters)

        if not items:
            print("Warning: No items found in newsletters")
            return 0

        # Step 3: Deduplicate items
        print("\n[3/4] Deduplicating items...")
        unique_items = deduplicate_items(items)

        if not unique_items:
            print("No new items to add to feed")
            return 0

        # Step 4: Generate RSS feed
        print("\n[4/4] Generating RSS feed...")
        from feed_generator import generate_feed
        feed = generate_feed(unique_items, str(output_dir / "feed.rss"))

        print("\n" + "=" * 50)
        print(f"Success! RSS feed saved to output/feed.rss")
        print(f"Total items in feed: {len(unique_items)}")
        print("=" * 50)

        return 0

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
