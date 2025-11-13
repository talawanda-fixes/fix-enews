"""
RSS feed generator
Creates RSS 2.0 feed from parsed items
"""

from typing import List, Dict
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
from pathlib import Path
from calendar_helper import generate_calendar_links


def generate_feed(items: List[Dict], output_file: str = "output/feed.rss",
                  school_name: str = "Talawanda High School",
                  description: str = "") -> FeedGenerator:
    """
    Generate RSS feed from news items

    Args:
        items: List of news items
        output_file: Path to save RSS feed
        school_name: Name of the school for feed metadata
        description: Description of the feed

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
    fg = create_feed_metadata(school_name, description)

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


def create_feed_metadata(school_name: str = "Talawanda High School",
                         description: str = "") -> FeedGenerator:
    """
    Create feed with basic metadata

    Args:
        school_name: Name of the school
        description: Feed description

    Returns:
        FeedGenerator with metadata set
    """
    fg = FeedGenerator()
    fg.title(f'{school_name} News')
    fg.description(description or f'Newsletter items from {school_name}')
    fg.link(href='https://www.talawanda.org/', rel='alternate')
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

    # Add calendar links if this is an event
    event_info = item.get('event_info')
    if event_info:
        try:
            # Handle both single event (dict) and multiple events (list)
            events = event_info if isinstance(event_info, list) else [event_info]

            for i, event in enumerate(events, 1):
                calendar_links = generate_calendar_links(event)

                # Add event title if there are multiple events
                if len(events) > 1:
                    content_html += f'\n<p><strong>{event["title"]}</strong><br>'
                    content_html += '<strong>Add to Calendar:</strong> '
                else:
                    content_html += '\n<p><strong>Add to Calendar:</strong> '

                content_html += f'<a href="{calendar_links["google"]}">Google Calendar</a> | '
                content_html += f'<a href="{calendar_links["ical"]}">iCal</a> | '
                content_html += f'<a href="{calendar_links["outlook"]}">Outlook</a>'
                content_html += '</p>'
        except Exception as e:
            # If calendar link generation fails, just skip it
            print(f"    Warning: Failed to generate calendar links for '{title}': {e}")

    # Add link back to source
    source_url = item.get('source_url', '')
    if source_url:
        # Add anchor to jump to specific item in newsletter
        block_id = item.get('block_id', '')
        # For multi-block items, use the first block ID as the anchor
        if block_id and '-' in block_id:
            anchor = block_id.split('-')[0]
        else:
            anchor = block_id

        if anchor:
            source_url_with_anchor = f"{source_url}#{anchor}"
        else:
            source_url_with_anchor = source_url

        content_html += f'\n<p><a href="{source_url_with_anchor}">View original newsletter</a></p>'

    fe.description(content_html)

    # Link to source newsletter with anchor
    if source_url:
        block_id = item.get('block_id', '')
        if block_id and '-' in block_id:
            anchor = block_id.split('-')[0]
        else:
            anchor = block_id

        if anchor:
            fe.link(href=f"{source_url}#{anchor}")
        else:
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
