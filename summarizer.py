"""
AI-powered content summarizer
Uses Claude to generate concise, text-only summaries of newsletter items
"""

import os
import json
import re
import base64
import requests
from pathlib import Path
from typing import List, Dict, Optional
from anthropic import Anthropic


CACHE_DIR = Path("cache/summaries")


def _fetch_and_encode_image(url: str) -> Optional[Dict]:
    """
    Fetch an image from URL and encode it as base64 for Claude vision API

    Args:
        url: Image URL

    Returns:
        Dict with vision API format, or None if fetch fails
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Determine media type from content-type header
        content_type = response.headers.get('content-type', 'image/png')

        # Convert to supported media types
        if 'jpeg' in content_type or 'jpg' in content_type:
            media_type = 'image/jpeg'
        elif 'png' in content_type:
            media_type = 'image/png'
        elif 'gif' in content_type:
            media_type = 'image/gif'
        elif 'webp' in content_type:
            media_type = 'image/webp'
        else:
            media_type = 'image/png'  # default

        # Encode image to base64
        image_data = base64.standard_b64encode(response.content).decode('utf-8')

        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_data
            }
        }
    except Exception as e:
        print(f"    Warning: Failed to fetch image {url}: {e}")
        return None


def _load_summary_from_cache(block_id: str) -> Optional[Dict[str, str]]:
    """Load summary and title from cache if available"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{block_id}.json"

    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                # Return dict with title and summary (backwards compatible)
                return {
                    'title': cached.get('title', ''),
                    'summary': cached.get('summary', '')
                }
        except Exception:
            return None
    return None


def _save_summary_to_cache(block_id: str, summary: str, title: str = ''):
    """Save summary and title to cache"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{block_id}.json"

    cache_data = {
        'block_id': block_id,
        'title': title,
        'summary': summary
    }

    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)


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
    if not api_key:
        api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is required for summarization. "
            "Set it with: export ANTHROPIC_API_KEY='your-api-key-here'"
        )

    print(f"\nSummarizing {len(items)} items with Claude...")

    client = Anthropic(api_key=api_key)
    summarized_items = []
    cache_hits = 0
    cache_misses = 0

    for i, item in enumerate(items, 1):
        block_id = item.get('block_id', '')
        title_preview = item['title'][:50]

        # Try to load from cache first
        cached_result = _load_summary_from_cache(block_id) if block_id else None

        if cached_result and cached_result.get('summary'):
            print(f"  Summarizing item {i}/{len(items)}: {title_preview}... (from cache)")
            item['summary'] = cached_result['summary']
            if cached_result.get('title'):
                item['title'] = cached_result['title']
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
                result = _generate_summary(client, item['title'], original_content, image_urls)
                item['title'] = result['title']
                item['summary'] = result['summary']

                # Save to cache (with title)
                if block_id:
                    _save_summary_to_cache(block_id, result['summary'], result['title'])

                cache_misses += 1
            except Exception as e:
                raise Exception(
                    f"Failed to summarize item '{title_preview}': {e}"
                ) from e

        summarized_items.append(item)

    print(f"Completed summarization of {len(summarized_items)} items")
    print(f"  Cache hits: {cache_hits}, Cache misses: {cache_misses}")
    return summarized_items


def _generate_summary(client: Anthropic, title: str, content: str, image_urls: List[str] = None) -> Dict[str, str]:
    """
    Use Claude to generate a concise summary and improved title
    Uses vision API to analyze images when present

    Args:
        client: Anthropic client
        title: Item title (may be rough/duplicated)
        content: Original text content
        image_urls: List of image URLs to analyze

    Returns:
        Dict with 'title' and 'summary' keys
    """
    # Build the prompt
    prompt_text = f"""You are summarizing a newsletter item from Talawanda High School.

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

Format your response EXACTLY as:
TITLE: [your improved title here]

SUMMARY:
[your markdown summary here]
"""

    # Build message content with text and images
    message_content = []

    # Add images first if available
    if image_urls:
        for img_url in image_urls:
            image_data = _fetch_and_encode_image(img_url)
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
    summary_match = re.search(r'SUMMARY:\s*(.+)', response_text, re.DOTALL)

    improved_title = title_match.group(1).strip() if title_match else title
    summary = summary_match.group(1).strip() if summary_match else response_text

    return {
        'title': improved_title,
        'summary': summary
    }


