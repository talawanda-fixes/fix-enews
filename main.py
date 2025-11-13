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
        print("\n[3/6] Deduplicating items...")
        unique_items = deduplicate_items(items)

        if not unique_items:
            print("No new items to add to feed")
            return 0

        # Step 4: Summarize items with Claude
        print("\n[4/6] Generating summaries with Claude...")
        from summarizer import summarize_items
        unique_items = summarize_items(unique_items)

        # Step 5: Save JSON output
        print("\n[5/6] Saving JSON output...")
        import json
        from datetime import datetime, timezone

        # Sort items by date, ascending (oldest first)
        # Will be reversed when generating feed to get newest first in RSS
        sorted_items = sorted(
            unique_items,
            key=lambda x: x.get('date') or datetime.max.replace(tzinfo=timezone.utc),
            reverse=True
        )

        # Convert datetime objects to ISO format strings for JSON serialization
        json_items = []
        for item in sorted_items:
            json_item = item.copy()
            if 'date' in json_item and isinstance(json_item['date'], datetime):
                json_item['date'] = json_item['date'].isoformat()
            json_items.append(json_item)

        json_path = output_dir / "items.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_items, f, indent=2, ensure_ascii=False)
        print(f"JSON saved to {json_path}")

        # Use sorted items for feed generation too
        unique_items = sorted_items

        # Step 6: Generate RSS feed
        print("\n[6/6] Generating RSS feed...")
        from feed_generator import generate_feed
        feed = generate_feed(unique_items, str(output_dir / "feed.rss"))

        print("\n" + "=" * 50)
        print(f"Success!")
        print(f"  RSS feed: output/feed.rss")
        print(f"  JSON data: output/items.json")
        print(f"  Total items: {len(unique_items)}")
        print("=" * 50)

        return 0

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except ValueError as e:
        # Configuration errors (like missing API key)
        print(f"\n\nConfiguration Error: {e}")
        return 1
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
