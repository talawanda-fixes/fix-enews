"""
Newsletter parser and deduplicator
Extracts individual items and removes duplicates
"""

from typing import List, Dict, Set
import hashlib
import json
from pathlib import Path


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

        # Find all content blocks (skip header and separators)
        blocks = soup.find_all('div', {'data-block-type': True})

        current_item = None
        item_blocks = []

        for block in blocks:
            block_type = block.get('data-block-type')

            # Skip certain block types
            if block_type in ['header', 'misc.separator', 'signature']:
                # If we have a current item, save it
                if current_item and item_blocks:
                    current_item['blocks'] = item_blocks
                    all_items.append(current_item)
                    current_item = None
                    item_blocks = []
                continue

            # text.title starts a new item
            if block_type == 'text.title':
                # Save previous item if exists
                if current_item and item_blocks:
                    current_item['blocks'] = item_blocks
                    all_items.append(current_item)

                # Start new item
                title_text = block.get_text().strip()
                current_item = {
                    'title': title_text,
                    'content': '',
                    'images': [],
                    'source_url': newsletter['url'],
                    'source_title': newsletter['title']
                }
                item_blocks = [{'type': block_type, 'content': title_text}]

            # Add other blocks to current item
            elif current_item:
                if block_type == 'text.paragraph':
                    text = block.get_text().strip()
                    item_blocks.append({'type': block_type, 'content': text})

                elif block_type == 'image.single':
                    img = block.find('img')
                    if img:
                        img_src = img.get('src', '')
                        # Get full size image (remove 'thumbs/' from path)
                        full_img_src = img_src.replace('/thumbs/', '/').replace('/thumb-', '/')
                        item_blocks.append({'type': block_type, 'url': full_img_src})
                        current_item['images'].append(full_img_src)

                elif block_type == 'items':
                    # List items block
                    text = block.get_text().strip()
                    item_blocks.append({'type': block_type, 'content': text})

        # Don't forget the last item
        if current_item and item_blocks:
            current_item['blocks'] = item_blocks
            all_items.append(current_item)

    print(f"\nExtracted {len(all_items)} items total")
    return all_items


def deduplicate_items(items: List[Dict], state_file: str = "output/seen_items.json") -> List[Dict]:
    """
    Remove duplicate items based on content

    Args:
        items: List of news items
        state_file: Path to file storing seen item hashes

    Returns:
        List of unique items
    """
    print(f"\nDeduplicating {len(items)} items...")

    # Load previously seen hashes
    seen_hashes = load_seen_items(state_file)
    print(f"Loaded {len(seen_hashes)} previously seen item hashes")

    unique_items = []
    new_hashes = set()

    for item in items:
        item_hash = _hash_item(item)
        item['hash'] = item_hash

        if item_hash not in seen_hashes and item_hash not in new_hashes:
            unique_items.append(item)
            new_hashes.add(item_hash)
        else:
            print(f"  Skipping duplicate: {item['title'][:50]}...")

    # Update seen hashes with new ones
    all_hashes = seen_hashes | new_hashes
    save_seen_items(all_hashes, state_file)

    print(f"Found {len(unique_items)} unique items ({len(items) - len(unique_items)} duplicates)")
    return unique_items


def _hash_item(item: Dict) -> str:
    """
    Generate a hash for a news item

    Args:
        item: News item dictionary

    Returns:
        SHA256 hash of the item content
    """
    # Hash based on title and all block content
    parts = [item.get('title', '')]

    for block in item.get('blocks', []):
        if 'content' in block:
            parts.append(block['content'])

    content = ''.join(parts)
    return hashlib.sha256(content.encode()).hexdigest()


def load_seen_items(state_file: str) -> Set[str]:
    """Load previously seen item hashes"""
    state_path = Path(state_file)
    if state_path.exists():
        with open(state_path) as f:
            data = json.load(f)
            return set(data.get('seen_hashes', []))
    return set()


def save_seen_items(hashes: Set[str], state_file: str):
    """Save item hashes to state file"""
    state_path = Path(state_file)
    state_path.parent.mkdir(exist_ok=True)
    with open(state_path, 'w') as f:
        json.dump({'seen_hashes': list(hashes)}, f, indent=2)
