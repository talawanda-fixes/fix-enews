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

    # Sort items by date, ascending (oldest first)
    # feedgen reverses the order when generating XML, so we sort ascending to get descending output
    # Items without dates go to the beginning
    sorted_items = sorted(
        items,
        key=lambda x: x.get('date') or datetime.max.replace(tzinfo=timezone.utc),
        reverse=False
    )

    # Create feed with metadata
    fg = create_feed_metadata()

    # Add each item to the feed
    for item in sorted_items:
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

    # Use AI-generated summary (required)
    summary = item.get('summary')

    if not summary:
        raise ValueError(f"Item '{title}' is missing AI-generated summary")

    # Convert markdown summary to HTML
    import markdown
    content_html = markdown.markdown(summary)

    # Add link back to source
    source_url = item.get('source_url', '')
    if source_url:
        content_html += f'\n<p><a href="{source_url}">View original newsletter</a></p>'

    fe.description(content_html)

    # Link to source newsletter
    if source_url:
        fe.link(href=source_url)

    # GUID using block_id
    guid = item.get('block_id') or item.get('hash', '')
    if guid:
        fe.guid(guid, permalink=False)

    # Publication date - use item date from newsletter, or current time as fallback
    item_date = item.get('date')
    if item_date:
        # Convert to timezone-aware datetime if needed
        if item_date.tzinfo is None:
            item_date = item_date.replace(tzinfo=timezone.utc)
        fe.pubDate(item_date)
    else:
        fe.pubDate(datetime.now(timezone.utc))
