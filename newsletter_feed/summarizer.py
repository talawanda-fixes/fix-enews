"""
AI-powered content summarizer
Uses Claude to generate concise, text-only summaries of newsletter items
"""

import re
from typing import List, Dict
from datetime import datetime, timedelta

from common.ai_integration import get_anthropic_client, fetch_and_encode_image
from common.cache import load_summary_from_cache, save_summary_to_cache


def summarize_items(items: List[Dict], api_key: str = None) -> List[Dict]:
    """
    Generate concise summaries for newsletter items using Claude
    Uses cache to avoid re-generating summaries for items with same block_id

    Args:
        items: List of news items
        api_key: Anthropic API key (or uses ANTHROPIC_API_KEY env var)

    Returns:
        List of items with 'summary' field added

    Raises:
        ValueError: If API key is not available
        Exception: If any summarization fails
    """
    print(f"\nSummarizing {len(items)} items with Claude...")

    client = get_anthropic_client(api_key)
    summarized_items = []
    cache_hits = 0
    cache_misses = 0

    for i, item in enumerate(items, 1):
        block_id = item.get('block_id', '')
        title_preview = item['title'][:50]

        # Try to load from cache first
        cached_result = load_summary_from_cache(block_id) if block_id else None

        if cached_result and cached_result.get('summary'):
            print(f"  Summarizing item {i}/{len(items)}: {title_preview}... (from cache)")
            item['summary'] = cached_result['summary']
            if cached_result.get('title'):
                item['title'] = cached_result['title']
            if cached_result.get('event_info'):
                item['event_info'] = cached_result['event_info']
            cache_hits += 1
        else:
            print(f"  Summarizing item {i}/{len(items)}: {title_preview}...")

            # Build content from blocks, collecting text and images separately
            content_parts = []
            image_urls = []

            for block in item.get('blocks', []):
                if block.get('type') == 'text.title':
                    content_parts.append(f"# {block.get('content', '')}")
                elif block.get('type') == 'text.paragraph':
                    content_parts.append(block.get('content', ''))
                elif block.get('type') == 'items':
                    content_parts.append(block.get('content', ''))
                elif block.get('type') == 'image.single':
                    img_url = block.get('url', '')
                    if img_url:
                        image_urls.append(img_url)

            original_content = '\n\n'.join(content_parts)

            # Generate summary and improved title - fail hard on error
            try:
                result = _generate_summary(
                    client,
                    item['title'],
                    original_content,
                    image_urls,
                    item.get('date')
                )
                item['title'] = result['title']
                item['summary'] = result['summary']

                # Add event info if present
                if 'event_info' in result:
                    item['event_info'] = result['event_info']

                # Save to cache (with title and event info)
                if block_id:
                    save_summary_to_cache(
                        block_id,
                        result['summary'],
                        result['title'],
                        result.get('event_info')
                    )

                cache_misses += 1
            except Exception as e:
                raise Exception(
                    f"Failed to summarize item '{title_preview}': {e}"
                ) from e

        summarized_items.append(item)

    print(f"Completed summarization of {len(summarized_items)} items")
    print(f"  Cache hits: {cache_hits}, Cache misses: {cache_misses}")
    return summarized_items


def _generate_summary(client, title: str, content: str, image_urls: List[str] = None, publication_date = None) -> Dict[str, str]:
    """
    Use Claude to generate a concise summary and improved title
    Uses vision API to analyze images when present

    Args:
        client: Anthropic client
        title: Item title (may be rough/duplicated)
        content: Original text content
        image_urls: List of image URLs to analyze
        publication_date: datetime when the item was published (used for inferring event years)

    Returns:
        Dict with 'title', 'summary', and optional 'event_info' keys
    """
    # Build the prompt with publication date context
    pub_date_str = publication_date.strftime('%Y-%m-%d') if publication_date else 'unknown'

    prompt_text = f"""You are summarizing a newsletter item from Talawanda High School.

This item was published on: {pub_date_str}

The item title is: {title}

The original text content is:
{content}

Please provide:
1. A clean, concise title (3-8 words) that describes what this item is about
2. A concise, clear, text-only summary in markdown format that:
   - Conveys the key information from the original item AND any images
   - Is brief but complete (2-4 sentences or bullet points)
   - Uses simple, accessible language
   - Preserves important dates, times, locations, and links
   - Extracts and conveys information from images (do NOT say "the image shows", just state the information)
   - Uses markdown formatting (bold, lists, links, etc.) for readability
3. If this item describes one or more events (meetings, games, performances, deadlines, school activities, special days, assemblies, etc.) that occur on specific dates, extract the event information
   - For dates without a year (like "November 14th"), ALWAYS assume this is the FIRST occurrence of that date AFTER the publication date shown above
   - For example: if published on 2025-11-07 and event says "November 14th", the event date is 2025-11-14 (same year, same month)
   - For example: if published on 2025-11-07 and event says "January 15th", the event date is 2026-01-15 (next year, since January comes after the publication month)
   - If a month/day is mentioned, that's sufficient to extract as an event (infer the year using the rule above)

Format your response EXACTLY as:
TITLE: [your improved title here]

SUMMARY:
[your markdown summary here]

EVENTS: [number of events, or 0 if none]
[If EVENTS > 0, for each event provide:]
---EVENT [number]---
TITLE: [specific event title]
DATE: [YYYY-MM-DD format - infer year if not explicitly stated using the rule above: first occurrence after publication date]
TIME: [HH:MM in 24-hour format, or "unknown" if not specified, or "00:00" for all-day events]
END_TIME: [HH:MM in 24-hour format, or "unknown" if not specified, or "23:59" for all-day events]
LOCATION: [location text, or "Talawanda High School" if not specified but clearly a school event]
"""

    # Build message content with text and images
    message_content = []

    # Add images first if available
    if image_urls:
        for img_url in image_urls:
            image_data = fetch_and_encode_image(img_url)
            if image_data:
                message_content.append(image_data)

    # Add the text prompt
    message_content.append({
        "type": "text",
        "text": prompt_text
    })

    # Call Claude API
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=500,
        messages=[{"role": "user", "content": message_content}]
    )

    response_text = message.content[0].text.strip()

    # Parse the response to extract title and summary
    title_match = re.search(r'TITLE:\s*(.+?)(?:\n|$)', response_text)
    summary_match = re.search(r'SUMMARY:\s*(.+?)(?:\n\nEVENTS:|$)', response_text, re.DOTALL)

    improved_title = title_match.group(1).strip() if title_match else title
    summary = summary_match.group(1).strip() if summary_match else response_text

    result = {
        'title': improved_title,
        'summary': summary
    }

    # Parse event information if present
    events_match = re.search(r'EVENTS:\s*(\d+)', response_text)
    if events_match:
        num_events = int(events_match.group(1))

        if num_events > 0:
            from datetime import datetime, timedelta

            # Find all event blocks
            event_blocks = re.findall(r'---EVENT \d+---\s*(.+?)(?=---EVENT \d+---|$)', response_text, re.DOTALL)

            events = []
            for event_block in event_blocks[:num_events]:  # Limit to declared number
                # Extract event details from this block
                event_title_match = re.search(r'TITLE:\s*(.+?)(?:\n|$)', event_block)
                date_match = re.search(r'DATE:\s*(.+?)(?:\n|$)', event_block)
                time_match = re.search(r'TIME:\s*(.+?)(?:\n|$)', event_block)
                end_time_match = re.search(r'END_TIME:\s*(.+?)(?:\n|$)', event_block)
                location_match = re.search(r'LOCATION:\s*(.+?)(?:\n|$)', event_block)

                event_title = event_title_match.group(1).strip() if event_title_match else improved_title
                event_date = date_match.group(1).strip() if date_match else 'unknown'
                event_time = time_match.group(1).strip() if time_match else 'unknown'
                event_end_time = end_time_match.group(1).strip() if end_time_match else 'unknown'
                event_location = location_match.group(1).strip() if location_match else 'unknown'

                # Only include event if we have at least a date
                if event_date != 'unknown':
                    try:
                        # Parse the date
                        event_datetime = datetime.fromisoformat(event_date)

                        # Add time if available
                        if event_time != 'unknown':
                            time_parts = event_time.split(':')
                            if len(time_parts) == 2:
                                event_datetime = event_datetime.replace(
                                    hour=int(time_parts[0]),
                                    minute=int(time_parts[1])
                                )

                        # Calculate end time
                        if event_end_time != 'unknown':
                            end_time_parts = event_end_time.split(':')
                            if len(end_time_parts) == 2:
                                event_end_datetime = event_datetime.replace(
                                    hour=int(end_time_parts[0]),
                                    minute=int(end_time_parts[1])
                                )
                            else:
                                event_end_datetime = event_datetime + timedelta(hours=1)
                        else:
                            event_end_datetime = event_datetime + timedelta(hours=1)

                        events.append({
                            'title': event_title,
                            'start': event_datetime,
                            'end': event_end_datetime,
                            'description': summary[:200],
                            'location': event_location if event_location != 'unknown' else ''
                        })
                    except (ValueError, IndexError):
                        # If parsing fails, skip this event
                        pass

            # Store events as array if we found any
            if events:
                result['event_info'] = events

    return result


