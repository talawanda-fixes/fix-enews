#!/usr/bin/env python3
"""
Cache Invalidation Script

Invalidates (deletes) cache files based on configurable criteria.
Parameters are ANDed together to filter which cache files to delete.
Supports cascade deletion (e.g., deleting newsletters also deletes dependent parsed and summaries).
"""

import json
import hashlib
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime, timezone

# Import existing cache utilities
from common.cache import (
    NEWSLETTER_CACHE_DIR,
    PARSED_CACHE_DIR,
    SUMMARY_CACHE_DIR,
    get_cache_key,
    sanitize_cache_filename
)


def load_correlation_index(output_dir: Path = Path("output")) -> Dict[str, Dict]:
    """
    Load all school output JSON files and build correlation index.

    Returns:
        Dict mapping block_id to item metadata (source_url, date, school, etc.)
    """
    index = {}

    if not output_dir.exists():
        print(f"Warning: Output directory '{output_dir}' does not exist")
        return index

    # Load all {school}-items.json files
    for json_file in output_dir.glob("*-items.json"):
        school_slug = json_file.stem.replace("-items", "")

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                items = json.load(f)

            for item in items:
                block_id = item.get('block_id')
                if not block_id:
                    continue

                # Parse date string to datetime
                date_str = item.get('date')
                date_obj = None
                if date_str:
                    try:
                        date_obj = datetime.fromisoformat(date_str)
                    except (ValueError, TypeError):
                        pass

                # Store metadata with school information
                index[block_id] = {
                    'block_id': block_id,
                    'source_url': item.get('source_url'),
                    'date': date_obj,
                    'school': school_slug,
                    'title': item.get('title'),
                    'source_title': item.get('source_title')
                }

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load {json_file}: {e}")
            continue

    print(f"Loaded correlation index: {len(index)} items from {output_dir}")
    return index


def parse_date_input(date_str: str) -> datetime:
    """Parse ISO date string to datetime object (always returns timezone-aware)."""
    try:
        # Try with time component
        dt = datetime.fromisoformat(date_str)
    except ValueError:
        # Try date-only format and add midnight UTC
        try:
            dt = datetime.fromisoformat(date_str + "T00:00:00")
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")

    # Ensure timezone-aware (add UTC if naive)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def filter_by_feeds(index: Dict[str, Dict], feeds: List[str]) -> Set[str]:
    """Filter items by school slugs."""
    if not feeds or 'all' in feeds:
        return set(index.keys())

    return {
        block_id for block_id, metadata in index.items()
        if metadata.get('school') in feeds
    }


def filter_by_item_id(index: Dict[str, Dict], item_id: str) -> Set[str]:
    """Filter items by exact block_id match."""
    return {item_id} if item_id in index else set()


def filter_by_most_recent_n(index: Dict[str, Dict], block_ids: Set[str], n: int) -> Set[str]:
    """
    Filter to N most recent items based on publication date.

    Args:
        index: Full correlation index
        block_ids: Set of block_ids to filter from
        n: Number of most recent items to keep

    Returns:
        Set of block_ids for N most recent items
    """
    # Get items with dates
    items_with_dates = [
        (block_id, index[block_id]['date'])
        for block_id in block_ids
        if block_id in index and index[block_id].get('date')
    ]

    # Sort by date descending (newest first)
    items_with_dates.sort(key=lambda x: x[1], reverse=True)

    # Take top N
    return {block_id for block_id, _ in items_with_dates[:n]}


def filter_by_since_date(index: Dict[str, Dict], block_ids: Set[str], since_date: datetime) -> Set[str]:
    """
    Filter items published on or after the given date.

    Args:
        index: Full correlation index
        block_ids: Set of block_ids to filter from
        since_date: Minimum publication date (inclusive)

    Returns:
        Set of block_ids for items >= since_date
    """
    return {
        block_id for block_id in block_ids
        if block_id in index and index[block_id].get('date') and index[block_id]['date'] >= since_date
    }


def apply_filters(
    index: Dict[str, Dict],
    feeds: Optional[List[str]] = None,
    item_id: Optional[str] = None,
    most_recent_n: Optional[int] = None,
    since_date: Optional[datetime] = None
) -> Set[str]:
    """
    Apply all filters with AND logic.

    Returns:
        Set of block_ids matching ALL criteria
    """
    # Start with all items or filter by feeds first (most restrictive usually)
    if feeds:
        matching_ids = filter_by_feeds(index, feeds)
    else:
        matching_ids = set(index.keys())

    # Apply item_id filter (exact match)
    if item_id:
        matching_ids &= filter_by_item_id(index, item_id)

    # Apply since_date filter
    if since_date:
        matching_ids = filter_by_since_date(index, matching_ids, since_date)

    # Apply most_recent_n filter (must be last since it sorts)
    if most_recent_n:
        matching_ids = filter_by_most_recent_n(index, matching_ids, most_recent_n)

    return matching_ids


def get_cache_files_for_block_ids(
    block_ids: Set[str],
    index: Dict[str, Dict],
    cache_types: List[str]
) -> Dict[str, List[Path]]:
    """
    Map block_ids to actual cache file paths with cascade logic.

    Args:
        block_ids: Set of block_ids to delete
        index: Correlation index for URL lookups
        cache_types: List of cache types to delete (newsletters, parsed, summaries, all)

    Returns:
        Dict mapping cache_type to list of file paths to delete
    """
    files_to_delete = {
        'newsletters': [],
        'parsed': [],
        'summaries': []
    }

    # Expand 'all' to all three types
    if 'all' in cache_types:
        cache_types = ['newsletters', 'parsed', 'summaries']

    # Track unique files (avoid duplicates)
    newsletter_files = set()
    parsed_files = set()
    summary_files = set()

    for block_id in block_ids:
        metadata = index.get(block_id)
        if not metadata:
            continue

        source_url = metadata.get('source_url')

        # Summary cache file
        if source_url:
            sanitized_id = sanitize_cache_filename(block_id)
            summary_file = SUMMARY_CACHE_DIR / f"{sanitized_id}.json"
            if summary_file.exists():
                summary_files.add(summary_file)

        # Parsed and newsletter cache files (keyed by source URL)
        if source_url:
            cache_key = get_cache_key(source_url)
            parsed_file = PARSED_CACHE_DIR / f"{cache_key}.json"
            newsletter_file = NEWSLETTER_CACHE_DIR / f"{cache_key}.json"

            if parsed_file.exists():
                parsed_files.add(parsed_file)
            if newsletter_file.exists():
                newsletter_files.add(newsletter_file)

    # Apply cascade logic based on cache_types
    # Cascade rules: newsletters → parsed → summaries
    # Each cache type includes itself and all downstream dependencies
    cascade_requested = False

    if 'newsletters' in cache_types:
        # Deleting newsletters cascades to parsed and summaries
        files_to_delete['newsletters'].extend(newsletter_files)
        files_to_delete['parsed'].extend(parsed_files)
        files_to_delete['summaries'].extend(summary_files)
        cascade_requested = True

    if 'parsed' in cache_types and not cascade_requested:
        # Deleting parsed cascades to summaries (unless newsletters already handled it)
        files_to_delete['parsed'].extend(parsed_files)
        files_to_delete['summaries'].extend(summary_files)
        cascade_requested = True

    if 'summaries' in cache_types and not cascade_requested:
        # Deleting summaries only (no cascade)
        files_to_delete['summaries'].extend(summary_files)

    return files_to_delete


def delete_cache_files(files_map: Dict[str, List[Path]], dry_run: bool = False) -> Dict[str, int]:
    """
    Physically delete cache files.

    Args:
        files_map: Dict mapping cache_type to list of file paths
        dry_run: If True, only print what would be deleted without deleting

    Returns:
        Dict mapping cache_type to count of files deleted
    """
    deleted_counts = {
        'newsletters': 0,
        'parsed': 0,
        'summaries': 0
    }

    for cache_type, file_paths in files_map.items():
        print(f"\n{cache_type.upper()} cache:")

        if not file_paths:
            print(f"  No files to delete")
            continue

        for file_path in file_paths:
            if dry_run:
                print(f"  [DRY RUN] Would delete: {file_path}")
                deleted_counts[cache_type] += 1
            else:
                try:
                    file_path.unlink()
                    print(f"  Deleted: {file_path.name}")
                    deleted_counts[cache_type] += 1
                except OSError as e:
                    print(f"  Error deleting {file_path}: {e}")

    return deleted_counts


def validate_feeds(feeds: List[str]) -> List[str]:
    """Validate feed slugs against newsletters.json."""
    newsletters_file = Path(__file__).parent.parent / "newsletters.json"

    try:
        with open(newsletters_file, 'r', encoding='utf-8') as f:
            schools = json.load(f)
            valid_slugs = {school['slug'] for school in schools}
    except (IOError, json.JSONDecodeError, KeyError) as e:
        print(f"Warning: Could not load newsletters.json for validation: {e}")
        return feeds

    if 'all' in feeds:
        return feeds

    invalid_slugs = [feed for feed in feeds if feed not in valid_slugs]
    if invalid_slugs:
        raise ValueError(f"Invalid feed slugs: {', '.join(invalid_slugs)}. Valid: {', '.join(sorted(valid_slugs))}, all")

    return feeds


def main():
    """Main entry point for cache invalidation."""
    parser = argparse.ArgumentParser(
        description='Invalidate cache files based on configurable criteria',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Delete summaries for specific item
  python -m common.cache_invalidator --cache-type summaries --item-id "bnb4ox7akq"

  # Delete all caches for THS items from last week
  python -m common.cache_invalidator --cache-type all --feeds ths --since-date 2025-11-11

  # Delete parsed + summaries for 10 most recent items
  python -m common.cache_invalidator --cache-type parsed --most-recent-n 10

  # Delete newsletters (cascades to parsed + summaries) for multiple schools
  python -m common.cache_invalidator --cache-type newsletters --feeds ths,tms
        """
    )

    parser.add_argument(
        '--cache-type',
        required=True,
        choices=['newsletters', 'parsed', 'summaries', 'all'],
        help='Type of cache to invalidate'
    )
    parser.add_argument(
        '--feeds',
        type=str,
        help='Comma-separated school slugs or "all" (default: all)',
        default='all'
    )
    parser.add_argument(
        '--item-id',
        type=str,
        help='Exact block_id to match'
    )
    parser.add_argument(
        '--most-recent-n',
        type=int,
        help='Number of most recent items to invalidate'
    )
    parser.add_argument(
        '--since-date',
        type=str,
        help='Invalidate items since this date (YYYY-MM-DD or ISO format)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Directory containing {school}-items.json files (default: output)'
    )

    args = parser.parse_args()

    # Validate inputs
    try:
        # Parse feeds
        feeds_list = [f.strip() for f in args.feeds.split(',')]
        feeds_list = validate_feeds(feeds_list)

        # Parse since_date if provided
        since_date = None
        if args.since_date:
            since_date = parse_date_input(args.since_date)

        # Ensure at least one filter is provided (besides cache_type)
        has_filter = any([
            feeds_list != ['all'],
            args.item_id,
            args.most_recent_n,
            args.since_date
        ])

        if not has_filter:
            print("Error: At least one filter parameter required (feeds, item-id, most-recent-n, or since-date)")
            print("Use --help for usage information")
            return 1

    except ValueError as e:
        print(f"Error: {e}")
        return 1

    # Load correlation index
    print(f"\n{'=' * 70}")
    print("CACHE INVALIDATION")
    print(f"{'=' * 70}\n")

    output_dir = Path(args.output_dir)
    index = load_correlation_index(output_dir)

    if not index:
        print("Error: No items found in output directory. Cannot correlate cache files.")
        return 1

    # Apply filters
    print(f"\nApplying filters:")
    print(f"  Cache type: {args.cache_type}")
    print(f"  Feeds: {', '.join(feeds_list)}")
    if args.item_id:
        print(f"  Item ID: {args.item_id}")
    if args.most_recent_n:
        print(f"  Most recent N: {args.most_recent_n}")
    if args.since_date:
        print(f"  Since date: {args.since_date}")

    matching_block_ids = apply_filters(
        index,
        feeds=feeds_list if feeds_list != ['all'] else None,
        item_id=args.item_id,
        most_recent_n=args.most_recent_n,
        since_date=since_date
    )

    print(f"\nMatched {len(matching_block_ids)} items")

    # Fail if no matches
    if not matching_block_ids:
        print("\nError: No items matched the specified criteria")
        return 1

    # Show matched items
    if len(matching_block_ids) <= 10:
        print("\nMatched items:")
        for block_id in sorted(matching_block_ids):
            metadata = index.get(block_id)
            if metadata:
                date_str = metadata['date'].strftime('%Y-%m-%d') if metadata.get('date') else 'no date'
                title = metadata.get('title', 'no title')[:50]
                school = metadata.get('school', 'unknown')
                print(f"  - [{school}] {title}... ({date_str})")

    # Get cache files to delete
    print(f"\nDetermining cache files to delete (cascade logic applied)...")
    files_to_delete = get_cache_files_for_block_ids(
        matching_block_ids,
        index,
        [args.cache_type]
    )

    # Count total files
    total_files = sum(len(files) for files in files_to_delete.values())
    if total_files == 0:
        print("\nError: No cache files found for matched items")
        return 1

    # Delete files
    if args.dry_run:
        print(f"\n{'=' * 70}")
        print("DRY RUN MODE - No files will be deleted")
        print(f"{'=' * 70}")

    deleted_counts = delete_cache_files(files_to_delete, dry_run=args.dry_run)

    # Report summary
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"Items matched: {len(matching_block_ids)}")
    print(f"Newsletters deleted: {deleted_counts['newsletters']}")
    print(f"Parsed deleted: {deleted_counts['parsed']}")
    print(f"Summaries deleted: {deleted_counts['summaries']}")
    print(f"Total files deleted: {sum(deleted_counts.values())}")

    if args.dry_run:
        print("\n(DRY RUN - No actual deletions performed)")

    print(f"{'=' * 70}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
