"""
Caching utilities for all use cases
Consolidated from scraper.py, parser.py, and summarizer.py
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


# Cache directories
NEWSLETTER_CACHE_DIR = Path("cache/newsletters")
PARSED_CACHE_DIR = Path("cache/parsed")
SUMMARY_CACHE_DIR = Path("cache/summaries")


# ============================================================================
# Newsletter/HTML Caching (from scraper.py)
# ============================================================================

def get_cache_key(url: str) -> str:
    """Generate cache key from URL"""
    return hashlib.md5(url.encode()).hexdigest()


def load_from_cache(url: str) -> Optional[Dict]:
    """Load newsletter/HTML from cache if available"""
    NEWSLETTER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = NEWSLETTER_CACHE_DIR / f"{get_cache_key(url)}.json"

    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                return cached
        except Exception:
            return None
    return None


def save_to_cache(url: str, html: str, title: str):
    """Save newsletter/HTML to cache"""
    NEWSLETTER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = NEWSLETTER_CACHE_DIR / f"{get_cache_key(url)}.json"

    cache_data = {
        'url': url,
        'html': html,
        'title': title
    }

    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False)


def get_all_cached_urls() -> List[str]:
    """Get all URLs that are cached"""
    NEWSLETTER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached_urls = []

    for cache_file in NEWSLETTER_CACHE_DIR.glob("*.json"):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                if 'url' in cached:
                    cached_urls.append(cached['url'])
        except Exception:
            continue

    return cached_urls


# ============================================================================
# Parsed Items Caching (from parser.py)
# ============================================================================

def get_newsletter_cache_key(newsletter: Dict) -> str:
    """Generate cache key for a newsletter based on URL"""
    url = newsletter.get('url', '')
    return hashlib.md5(url.encode()).hexdigest()


def load_parsed_items_from_cache(newsletter: Dict) -> Optional[List[Dict]]:
    """Load parsed items for a newsletter from cache if available"""
    PARSED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = get_newsletter_cache_key(newsletter)
    cache_file = PARSED_CACHE_DIR / f"{cache_key}.json"

    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_items = json.load(f)
                # Convert date strings back to datetime objects
                for item in cached_items:
                    if 'date' in item and item['date']:
                        item['date'] = datetime.fromisoformat(item['date'])
                return cached_items
        except Exception:
            return None
    return None


def save_parsed_items_to_cache(newsletter: Dict, items: List[Dict]):
    """Save parsed items for a newsletter to cache"""
    PARSED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = get_newsletter_cache_key(newsletter)
    cache_file = PARSED_CACHE_DIR / f"{cache_key}.json"

    # Convert items to JSON-serializable format
    serializable_items = []
    for item in items:
        serializable_item = item.copy()
        # Remove soup object if present
        if 'soup' in serializable_item:
            del serializable_item['soup']
        # Convert datetime to ISO format
        if 'date' in serializable_item and isinstance(serializable_item['date'], datetime):
            serializable_item['date'] = serializable_item['date'].isoformat()
        serializable_items.append(serializable_item)

    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_items, f, ensure_ascii=False, indent=2)


# ============================================================================
# Summary Caching (from summarizer.py)
# ============================================================================

def sanitize_cache_filename(block_id: str) -> str:
    """Sanitize block_id for use as a cache filename by replacing invalid path characters"""
    # For blog posts with URLs, use hash to avoid path separator issues
    if block_id.startswith('blog_post_'):
        # Use hash of the full block_id for blog posts to avoid path issues
        return hashlib.md5(block_id.encode()).hexdigest()
    # For newsletter block IDs (like "abc123-def456"), use as-is
    return block_id


def load_summary_from_cache(block_id: str) -> Optional[Dict]:
    """Load summary, title, and event info from cache if available"""
    SUMMARY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_filename = sanitize_cache_filename(block_id)
    cache_file = SUMMARY_CACHE_DIR / f"{cache_filename}.json"

    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                # Return dict with title, summary, and event_info
                result = {
                    'title': cached.get('title', ''),
                    'summary': cached.get('summary', '')
                }
                if 'event_info' in cached:
                    # Convert ISO format strings back to datetime objects
                    event_info = cached['event_info']

                    # Handle both single event (dict) and multiple events (list) for backward compatibility
                    if isinstance(event_info, dict):
                        # Single event - convert to single-item list
                        result['event_info'] = [{
                            'title': event_info['title'],
                            'start': datetime.fromisoformat(event_info['start']),
                            'end': datetime.fromisoformat(event_info['end']),
                            'description': event_info['description'],
                            'location': event_info['location']
                        }]
                    elif isinstance(event_info, list):
                        # Multiple events
                        result['event_info'] = [
                            {
                                'title': ev['title'],
                                'start': datetime.fromisoformat(ev['start']),
                                'end': datetime.fromisoformat(ev['end']),
                                'description': ev['description'],
                                'location': ev['location']
                            }
                            for ev in event_info
                        ]
                return result
        except Exception:
            return None
    return None


def save_summary_to_cache(block_id: str, summary: str, title: str = '', event_info=None):
    """Save summary, title, and event info to cache"""
    SUMMARY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_filename = sanitize_cache_filename(block_id)
    cache_file = SUMMARY_CACHE_DIR / f"{cache_filename}.json"

    cache_data = {
        'block_id': block_id,
        'title': title,
        'summary': summary
    }

    if event_info:
        # Convert datetime objects to ISO format strings for JSON serialization
        # Handle both single event (dict) and multiple events (list)
        if isinstance(event_info, dict):
            # Single event - save as-is for backward compatibility
            serializable_event_info = {
                'title': event_info['title'],
                'start': event_info['start'].isoformat(),
                'end': event_info['end'].isoformat(),
                'description': event_info['description'],
                'location': event_info['location']
            }
            cache_data['event_info'] = serializable_event_info
        elif isinstance(event_info, list):
            # Multiple events - save as array
            cache_data['event_info'] = [
                {
                    'title': ev['title'],
                    'start': ev['start'].isoformat(),
                    'end': ev['end'].isoformat(),
                    'description': ev['description'],
                    'location': ev['location']
                }
                for ev in event_info
            ]

    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
