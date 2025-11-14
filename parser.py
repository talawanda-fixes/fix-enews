"""
Newsletter parser and deduplicator
Extracts individual items and removes duplicates
"""

from typing import List, Dict, Set, Optional
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime

PARSED_CACHE_DIR = Path("cache/parsed")


def _get_newsletter_cache_key(newsletter: Dict) -> str:
    """Generate cache key for a newsletter based on URL"""
    url = newsletter.get('url', '')
    return hashlib.md5(url.encode()).hexdigest()


def _load_parsed_items_from_cache(newsletter: Dict) -> List[Dict]:
    """Load parsed items for a newsletter from cache if available"""
    PARSED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = _get_newsletter_cache_key(newsletter)
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


def _save_parsed_items_to_cache(newsletter: Dict, items: List[Dict]):
    """Save parsed items for a newsletter to cache"""
    PARSED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = _get_newsletter_cache_key(newsletter)
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


def extract_origin_blog_url(soup) -> Optional[str]:
    """
    Extract origin blog URL from links in blog post content

    Looks for links to talawanda.org school blogs to identify cross-posted content.
    Blog posts that reference another blog are considered cross-posts.

    Args:
        soup: BeautifulSoup object of blog post HTML

    Returns:
        Origin blog URL if found, None otherwise
    """
    # Find main content area
    main = soup.find('main') or soup.find('div', id='main') or soup.find('article')
    if not main:
        return None

    # Pattern to match Talawanda blog URLs: https://www.talawanda.org/{blog-slug}/...
    blog_pattern = re.compile(r'https?://(?:www\.)?talawanda\.org/([^/\?#]+)')

    for link in main.find_all('a', href=True):
        href = link.get('href', '')
        match = blog_pattern.search(href)

        if match:
            blog_slug = match.group(1)
            # Only match blog URLs (end with -blog)
            if blog_slug.endswith('-blog'):
                # Normalize: add trailing slash
                return f"https://www.talawanda.org/{blog_slug}/"

    return None


def clean_title(title: str) -> str:
    """
    Clean up title text by removing duplicates, extra whitespace, and normalizing

    Args:
        title: Raw title text

    Returns:
        Cleaned title
    """
    if not title:
        return ""

    # Remove excessive whitespace and newlines
    title = re.sub(r'\s+', ' ', title).strip()

    # Check if title is duplicated (e.g., "BRAVE DAY BRAVE DAY")
    words = title.split()
    if len(words) % 2 == 0:
        mid = len(words) // 2
        first_half = ' '.join(words[:mid])
        second_half = ' '.join(words[mid:])
        if first_half == second_half:
            title = first_half

    # Limit length
    if len(title) > 100:
        title = title[:100].rsplit(' ', 1)[0] + '...'

    return title


def parse_newsletters(newsletters: List[Dict]) -> List[Dict]:
    """
    Parse newsletters and blog posts and extract individual items

    Args:
        newsletters: List of newsletter/blog post data

    Returns:
        List of individual news items
    """
    all_items = []
    cached_count = 0
    parsed_count = 0

    for newsletter in newsletters:
        # Try to load from cache first
        cached_items = _load_parsed_items_from_cache(newsletter)
        if cached_items:
            all_items.extend(cached_items)
            cached_count += 1
            continue

        # Not in cache, parse it
        parsed_count += 1
        print(f"  Parsing: {newsletter['title']}")

        # Track items for this newsletter to cache them
        newsletter_items = []

        # Check if this is a blog post or newsletter
        entry_type = newsletter.get('type', 'newsletter')

        if entry_type == 'blog_post':
            # Blog posts become a single item with full content
            soup = newsletter['soup']

            # Extract main content from the blog post
            main = soup.find('main') or soup.find('div', id='main') or soup.find('article')
            if main:
                # Get the content body
                content_body = main.find('div', class_='divBlockBody') or main

                # Extract text content
                content_text = content_body.get_text().strip() if content_body else ""

                # Extract any images
                images = []
                for img in content_body.find_all('img') if content_body else []:
                    img_src = img.get('src', '')
                    if img_src:
                        images.append(img_src)

                # Extract origin blog URL (for cross-post detection)
                origin_blog_url = extract_origin_blog_url(soup)

                # Create a single item for the blog post
                blog_item = {
                    'title': newsletter['title'],
                    'block_id': f"blog_post_{newsletter['url']}",
                    'content': content_text,
                    'images': images,
                    'source_url': newsletter['url'],
                    'source_title': newsletter['title'],
                    'date': newsletter.get('date'),
                    'origin_blog_url': origin_blog_url,
                    'blocks': [{
                        'type': 'blog_post_content',
                        'content': content_text,
                        'id': newsletter['url']
                    }],
                    'type': 'blog_post'
                }
                all_items.append(blog_item)
                newsletter_items.append(blog_item)

            # Save to cache
            _save_parsed_items_to_cache(newsletter, newsletter_items)
            continue

        # Handle newsletter (original logic)
        soup = newsletter['soup']

        # Find all content blocks
        blocks = soup.find_all('div', {'data-block-type': True})

        current_item = None
        item_blocks = []
        item_block_ids = []  # Collect all block IDs for this item

        for block in blocks:
            block_type = block.get('data-block-type')
            block_id = block.get('data-block-id', '')

            # Skip header
            if block_type == 'header':
                continue

            # Separator or signature ends the current item and starts a new one
            if block_type in ['misc.separator', 'signature']:
                # Save previous item if exists and has content
                if current_item and item_blocks:
                    current_item['blocks'] = item_blocks
                    # Use all block IDs concatenated as unique identifier
                    current_item['block_id'] = '-'.join(item_block_ids)

                    # If no title was found, use first content as title
                    if not current_item['title']:
                        for block in item_blocks:
                            if 'content' in block and block['content'].strip():
                                current_item['title'] = clean_title(block['content'][:100])
                                break

                    # Only add items that have some content
                    if current_item['title'] and item_block_ids:
                        all_items.append(current_item)
                        newsletter_items.append(current_item)

                # Start a new item (even if separator - it might be the only thing between separators)
                current_item = {
                    'title': '',  # Will be set from first content block
                    'block_id': '',  # Will be set when item is complete
                    'content': '',
                    'images': [],
                    'source_url': newsletter['url'],
                    'source_title': newsletter['title'],
                    'date': newsletter.get('date')
                }
                item_blocks = []
                item_block_ids = []
                continue

            # If we don't have a current item yet, start one
            if current_item is None:
                current_item = {
                    'title': '',
                    'block_id': '',
                    'content': '',
                    'images': [],
                    'source_url': newsletter['url'],
                    'source_title': newsletter['title'],
                    'date': newsletter.get('date')
                }
                item_blocks = []
                item_block_ids = []

            # Add block ID to list
            if block_id:
                item_block_ids.append(block_id)

            # Process different block types
            if block_type == 'text.title':
                title_text = block.get_text().strip()
                # Use first title as the item title
                if not current_item['title']:
                    current_item['title'] = clean_title(title_text)
                item_blocks.append({'type': block_type, 'content': title_text, 'id': block_id})

            elif block_type == 'text.paragraph':
                text = block.get_text().strip()
                item_blocks.append({'type': block_type, 'content': text, 'id': block_id})

            elif block_type == 'image.single':
                img = block.find('img')
                if img:
                    img_src = img.get('src', '')
                    # Get full size image (remove 'thumbs/' from path)
                    full_img_src = img_src.replace('/thumbs/', '/').replace('/thumb-', '/')
                    item_blocks.append({'type': block_type, 'url': full_img_src, 'id': block_id})
                    current_item['images'].append(full_img_src)

            elif block_type == 'items':
                # List items block
                text = block.get_text().strip()
                item_blocks.append({'type': block_type, 'content': text, 'id': block_id})

        # Don't forget the last item
        if current_item and item_blocks:
            current_item['blocks'] = item_blocks
            current_item['block_id'] = '-'.join(item_block_ids)
            # If no title was found, use first content as title
            if not current_item['title']:
                for block in item_blocks:
                    if 'content' in block and block['content'].strip():
                        current_item['title'] = clean_title(block['content'][:100])
                        break

            # Only add items that have some content
            if current_item['title'] or current_item['blocks']:
                all_items.append(current_item)
                newsletter_items.append(current_item)

        # Save parsed items for this newsletter to cache
        if newsletter_items:
            _save_parsed_items_to_cache(newsletter, newsletter_items)

    print(f"\nExtracted {len(all_items)} items total ({cached_count} from cache, {parsed_count} newly parsed)")
    return all_items


def deduplicate_items(items: List[Dict], state_file: str = "output/seen_items.json") -> List[Dict]:
    """
    Remove duplicate items based on content, keeping earliest date for each item

    Note: State file parameter is kept for compatibility but not used.
    Deduplication only happens within the current run across all newsletters.

    Args:
        items: List of news items
        state_file: (Unused) Path to file storing seen item data

    Returns:
        List of unique items with earliest dates
    """
    print(f"\nDeduplicating {len(items)} items across all newsletters...")

    unique_items = []
    items_by_hash = {}  # Track items by hash to find earliest date
    filtered_items = []

    # Group items by hash and find earliest date
    for item in items:
        # Filter out noise items
        title = item.get('title', '').lower()
        content = item.get('content', '').lower()

        # Check for specific footer/branding patterns
        # These are items that are ONLY branding, not real content
        matched_pattern = None

        # Footer items that start with zoom_out_map and only contain school name/hashtag
        if 'zoom_out_map' in title:
            # Check if it's ONLY the school footer (no other substantive content)
            footer_only_patterns = [
                'talawanda high school #educate',
                'talawanda middle school #',
                'bogan elementary #',
                'kramer elementary #',
                'marshall elementary #',
            ]
            if any(pattern in title for pattern in footer_only_patterns):
                matched_pattern = 'footer_branding'

        if matched_pattern:
            filtered_items.append({
                'title': item.get('title', ''),
                'reason': matched_pattern,
                'content_preview': item.get('content', '')[:100]
            })
            continue

        item_hash = _hash_item(item)
        item['hash'] = item_hash

        # If we haven't seen this item in current batch
        if item_hash not in items_by_hash:
            items_by_hash[item_hash] = item
        else:
            # Keep the one with earlier date
            existing = items_by_hash[item_hash]
            existing_date = existing.get('date')
            new_date = item.get('date')

            if new_date and (not existing_date or new_date < existing_date):
                items_by_hash[item_hash] = item
                print(f"  Using earlier date for: {item['title'][:50]}...")

    # All unique items from this run
    unique_items = list(items_by_hash.values())

    duplicates = len(items) - len(unique_items) - len(filtered_items)
    print(f"Found {len(unique_items)} unique items ({duplicates} duplicates, {len(filtered_items)} noise filtered)")

    # Log filtered items for review
    if filtered_items:
        print(f"\nFiltered noise items:")
        for filtered in filtered_items:
            title_display = filtered['title'][:60] if filtered['title'] else '(no title)'
            print(f"  - [{filtered['reason']}] {title_display}")

    return unique_items


def _hash_item(item: Dict) -> str:
    """
    Generate a unique identifier for a news item using its block_id

    Args:
        item: News item dictionary

    Returns:
        The block_id if available, otherwise SHA256 hash of content
    """
    # Use block_id as the unique identifier
    block_id = item.get('block_id', '')
    if block_id:
        return block_id

    # Fallback to content hash if no block_id
    parts = [item.get('title', '')]
    for block in item.get('blocks', []):
        if 'content' in block:
            parts.append(block['content'])

    content = ''.join(parts)
    return hashlib.sha256(content.encode()).hexdigest()


def load_seen_items(state_file: str) -> Set[str]:
    """Load previously seen item hashes (legacy function for compatibility)"""
    data = load_seen_items_with_dates(state_file)
    return set(data.keys())


def load_seen_items_with_dates(state_file: str) -> Dict[str, datetime]:
    """Load previously seen item hashes with their dates"""
    state_path = Path(state_file)
    if state_path.exists():
        with open(state_path) as f:
            data = json.load(f)

            # Handle old format (just hashes)
            if 'seen_hashes' in data:
                return {h: None for h in data['seen_hashes']}

            # New format (hash -> date)
            result = {}
            for item_hash, date_str in data.items():
                if date_str:
                    try:
                        result[item_hash] = datetime.fromisoformat(date_str)
                    except (ValueError, TypeError):
                        result[item_hash] = None
                else:
                    result[item_hash] = None
            return result

    return {}


def save_seen_items(hashes: Set[str], state_file: str):
    """Save item hashes to state file (legacy function)"""
    save_seen_items_with_dates({h: None for h in hashes}, state_file)


def save_seen_items_with_dates(items_data: Dict[str, datetime], state_file: str):
    """Save item hashes with their dates to state file"""
    state_path = Path(state_file)
    state_path.parent.mkdir(exist_ok=True)

    # Convert dates to ISO format strings
    data = {}
    for item_hash, date in items_data.items():
        data[item_hash] = date.isoformat() if date else None

    with open(state_path, 'w') as f:
        json.dump(data, f, indent=2)
