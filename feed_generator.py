"""
RSS feed generator
Creates RSS 2.0 feed from parsed items
"""

from typing import List, Dict
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
from pathlib import Path


def generate_feed(items: List[Dict], output_file: str = "output/feed.rss") -> FeedGenerator:
    """
    Generate RSS feed from news items

    Args:
        items: List of news items
        output_file: Path to save RSS feed

    Returns:
        FeedGenerator object
    """
    print(f"\nGenerating RSS feed with {len(items)} items...")

    # Create feed with metadata
    fg = create_feed_metadata()

    # Add each item to the feed
    for item in items:
        add_item_to_feed(fg, item)

    # Ensure output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(exist_ok=True, parents=True)

    # Save to file
    fg.rss_file(str(output_path))
    print(f"RSS feed saved to {output_file}")

    return fg


def create_feed_metadata() -> FeedGenerator:
    """
    Create feed with basic metadata

    Returns:
        FeedGenerator with metadata set
    """
    fg = FeedGenerator()
    fg.title('Talawanda High School News')
    fg.description('Newsletter items from Talawanda High School')
    fg.link(href='https://www.talawanda.org/talawanda-high-school-blog/', rel='alternate')
    fg.language('en')
    fg.generator('Talawanda Enews RSS Converter')

    return fg


def add_item_to_feed(fg: FeedGenerator, item: Dict):
    """
    Add a news item to the feed

    Args:
        fg: FeedGenerator object
        item: News item dictionary
    """
    fe = fg.add_entry()

    # Title
    title = item.get('title', 'Untitled').replace('\n', ' ').strip()
    fe.title(title)

    # Build HTML content from blocks
    content_parts = []

    for block in item.get('blocks', []):
        block_type = block.get('type', '')

        if block_type == 'text.title':
            content_parts.append(f"<h3>{block.get('content', '')}</h3>")
        elif block_type == 'text.paragraph':
            content_parts.append(f"<p>{block.get('content', '')}</p>")
        elif block_type == 'image.single':
            img_url = block.get('url', '')
            content_parts.append(f'<p><img src="{img_url}" alt="Newsletter image" /></p>')
        elif block_type == 'items':
            content_parts.append(f"<div>{block.get('content', '')}</div>")

    # Add link back to source
    source_url = item.get('source_url', '')
    if source_url:
        content_parts.append(f'<p><a href="{source_url}">View original newsletter</a></p>')

    content_html = '\n'.join(content_parts)
    fe.description(content_html)

    # Link to source newsletter
    if source_url:
        fe.link(href=source_url)

    # GUID using block_id
    guid = item.get('block_id') or item.get('hash', '')
    if guid:
        fe.guid(guid, permalink=False)

    # Publication date - use current time
    # (Smore newsletters don't expose reliable dates easily)
    fe.pubDate(datetime.now(timezone.utc))
