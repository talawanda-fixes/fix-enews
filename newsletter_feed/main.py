#!/usr/bin/env python3
"""
Talawanda Enews RSS Converter
Main entry point for the scraper pipeline
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime, timezone


def load_schools() -> list:
    """Load school configurations from newsletters.json"""
    newsletters_file = Path(__file__).parent.parent / "newsletters.json"
    with open(newsletters_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def filter_cross_posted_items(items: list, current_blog_url: str) -> tuple:
    """
    Filter items to remove cross-posts (items that originated from a different blog)

    Args:
        items: List of parsed items
        current_blog_url: The blog URL we're currently processing

    Returns:
        Tuple of (filtered_items, filtered_count)
    """
    # Normalize current_blog_url to ensure trailing slash for consistent comparison
    if not current_blog_url.endswith('/'):
        current_blog_url = current_blog_url + '/'

    filtered_items = []
    cross_posts_filtered = []

    for item in items:
        origin_url = item.get('origin_blog_url')

        # If no origin URL detected, item belongs to current blog (default behavior)
        if not origin_url:
            filtered_items.append(item)
            continue

        # If origin URL matches current blog, keep it
        if origin_url == current_blog_url:
            filtered_items.append(item)
            continue

        # Item originated from different blog - filter it out
        cross_posts_filtered.append({
            'title': item.get('title', ''),
            'current_blog': current_blog_url,
            'origin_blog': origin_url,
            'source_url': item.get('source_url', '')
        })

    if cross_posts_filtered:
        print(f"\n  Filtered {len(cross_posts_filtered)} cross-posted items:")
        for cp in cross_posts_filtered:
            title_display = cp['title'][:60] if cp['title'] else '(no title)'
            # Extract slug from URL path (handles with/without trailing slash)
            origin_slug = cp['origin_blog'].rstrip('/').split('/')[-1] if cp['origin_blog'] else 'unknown'
            print(f"    - {title_display} (from {origin_slug})")

    return filtered_items, len(cross_posts_filtered)


def process_school(school: dict, output_dir: Path, limit: int = None) -> int:
    """
    Process a single school's newsletters

    Args:
        school: School configuration dict with 'name', 'slug', 'blog_url', 'description'
        output_dir: Output directory path for this school
        limit: Maximum number of items to summarize and include in feed (None for all)

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    school_name = school['name']
    school_slug = school['slug']
    blog_url = school['blog_url']
    description = school.get('description', '')

    print(f"\n{'=' * 70}")
    print(f"Processing: {school_name}")
    print(f"{'=' * 70}")

    try:
        # Step 1: Scrape newsletters from Smore
        print(f"\n[1/7] Scraping newsletters for {school_name}...")
        start_time = time.time()
        from common.scraper import fetch_newsletters
        newsletters = fetch_newsletters(blog_url)
        elapsed = time.time() - start_time
        print(f"  ⏱️  Scraping took {elapsed:.2f}s")

        if not newsletters:
            print("Error: No newsletters found!")
            return 1

        # Step 2: Parse and extract items
        print("\n[2/7] Parsing and extracting items...")
        start_time = time.time()
        from common.parser import parse_newsletters, deduplicate_items
        items = parse_newsletters(newsletters)
        elapsed = time.time() - start_time
        print(f"  ⏱️  Parsing took {elapsed:.2f}s")

        if not items:
            print("Warning: No items found in newsletters")
            return 0

        # Step 3: Deduplicate items
        print("\n[3/7] Deduplicating items...")
        start_time = time.time()
        unique_items = deduplicate_items(items)
        elapsed = time.time() - start_time
        print(f"  ⏱️  Deduplication took {elapsed:.2f}s")

        if not unique_items:
            print("No new items to add to feed")
            return 0

        # Step 4: Filter cross-posted items
        print(f"\n[4/7] Filtering cross-posted items for {school_name}...")
        start_time = time.time()
        unique_items, filtered_count = filter_cross_posted_items(unique_items, blog_url)
        elapsed = time.time() - start_time
        print(f"  ⏱️  Filtering took {elapsed:.2f}s")
        print(f"  Kept {len(unique_items)} items after filtering {filtered_count} cross-posts")

        if not unique_items:
            print("No items remaining after cross-post filtering")
            return 0

        # Apply limit if specified (take most recent items)
        if limit and len(unique_items) > limit:
            print(f"\n[Limiting to {limit} most recent items out of {len(unique_items)} total]")
            # Sort by date descending (newest first) to get most recent
            unique_items = sorted(
                unique_items,
                key=lambda x: x.get('date') or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True
            )[:limit]

        # Step 5: Summarize items with Claude
        print("\n[5/7] Generating summaries with Claude...")
        start_time = time.time()
        from newsletter_feed.summarizer import summarize_items
        unique_items = summarize_items(unique_items)
        elapsed = time.time() - start_time
        print(f"  ⏱️  Summarization took {elapsed:.2f}s")

        # Step 6: Save JSON output
        print("\n[6/7] Saving JSON output...")
        start_time = time.time()

        # Sort items by date (newest first)
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

            # Convert event_info datetime objects (handle both single dict and array of dicts)
            if 'event_info' in json_item:
                event_info = json_item['event_info']

                if isinstance(event_info, dict):
                    # Single event
                    event_copy = event_info.copy()
                    if 'start' in event_copy and isinstance(event_copy['start'], datetime):
                        event_copy['start'] = event_copy['start'].isoformat()
                    if 'end' in event_copy and isinstance(event_copy['end'], datetime):
                        event_copy['end'] = event_copy['end'].isoformat()
                    json_item['event_info'] = event_copy
                elif isinstance(event_info, list):
                    # Multiple events
                    json_item['event_info'] = [
                        {
                            **ev,
                            'start': ev['start'].isoformat() if isinstance(ev['start'], datetime) else ev['start'],
                            'end': ev['end'].isoformat() if isinstance(ev['end'], datetime) else ev['end']
                        }
                        for ev in event_info
                    ]

            json_items.append(json_item)

        # Use school slug for filenames
        json_path = output_dir / f"{school_slug}-items.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_items, f, indent=2, ensure_ascii=False)
        print(f"JSON saved to {json_path}")
        elapsed = time.time() - start_time
        print(f"  ⏱️  JSON output took {elapsed:.2f}s")

        # Use sorted items for feed generation too
        unique_items = sorted_items

        # Step 7: Generate RSS feed
        print("\n[7/7] Generating RSS feed...")
        start_time = time.time()
        from newsletter_feed.feed_generator import generate_feed
        feed_path = output_dir / f"{school_slug}-feed.rss"
        feed = generate_feed(unique_items, str(feed_path), school_name, description)
        elapsed = time.time() - start_time
        print(f"  ⏱️  RSS generation took {elapsed:.2f}s")

        print("\n" + "=" * 50)
        print(f"Success!")
        print(f"  RSS feed: {feed_path}")
        print(f"  JSON data: {json_path}")
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


def main():
    """Main entry point with optional school parameter"""
    parser = argparse.ArgumentParser(description='Generate RSS feeds for Talawanda school newsletters')
    parser.add_argument('--school', type=str, help='Process only the specified school slug (e.g., "ths", "tms")')
    parser.add_argument('--output', type=str, default='output', help='Output directory (default: output)')
    parser.add_argument('--limit', type=int, default=20, help='Limit number of items to summarize and include in feed (default: 7)')
    args = parser.parse_args()

    # Load all schools
    schools = load_schools()

    # Filter to specific school if requested
    if args.school:
        schools = [s for s in schools if s['slug'] == args.school]
        if not schools:
            print(f"Error: School '{args.school}' not found in newsletters.json")
            print(f"Available schools: {', '.join(s['slug'] for s in load_schools())}")
            return 1

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process each school
    exit_codes = []
    for school in schools:
        exit_code = process_school(school, output_dir, limit=args.limit)
        exit_codes.append(exit_code)

    # Return non-zero if any school failed
    return max(exit_codes) if exit_codes else 0


if __name__ == "__main__":
    sys.exit(main())
