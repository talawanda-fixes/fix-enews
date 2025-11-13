"""
Newsletter parser and deduplicator
Extracts individual items and removes duplicates
"""

from typing import List, Dict, Set
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime


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
    Parse newsletters and extract individual items

    Args:
        newsletters: List of newsletter data

    Returns:
        List of individual news items
    """
    all_items = []

    for newsletter in newsletters:
        print(f"  Parsing: {newsletter['title']}")
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

    print(f"\nExtracted {len(all_items)} items total")
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

    # Group items by hash and find earliest date
    for item in items:
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

    print(f"Found {len(unique_items)} unique items ({len(items) - len(unique_items)} duplicates)")
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
