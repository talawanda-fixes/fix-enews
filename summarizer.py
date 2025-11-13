"""
AI-powered content summarizer
Uses Claude to generate concise, text-only summaries of newsletter items
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from anthropic import Anthropic


CACHE_DIR = Path("cache/summaries")


def _load_summary_from_cache(block_id: str) -> Optional[str]:
    """Load summary from cache if available"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{block_id}.json"

    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                return cached.get('summary')
        except Exception:
            return None
    return None


def _save_summary_to_cache(block_id: str, summary: str):
    """Save summary to cache"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{block_id}.json"

    cache_data = {
        'block_id': block_id,
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
        cached_summary = _load_summary_from_cache(block_id) if block_id else None

        if cached_summary:
            print(f"  Summarizing item {i}/{len(items)}: {title_preview}... (from cache)")
            item['summary'] = cached_summary
            cache_hits += 1
        else:
            print(f"  Summarizing item {i}/{len(items)}: {title_preview}...")

            # Build content from blocks
            content_parts = []
            for block in item.get('blocks', []):
                if block.get('type') == 'text.title':
                    content_parts.append(f"# {block.get('content', '')}")
                elif block.get('type') == 'text.paragraph':
                    content_parts.append(block.get('content', ''))
                elif block.get('type') == 'items':
                    content_parts.append(block.get('content', ''))
                elif block.get('type') == 'image.single':
                    content_parts.append(f"[Image: {block.get('url', '')}]")

            original_content = '\n\n'.join(content_parts)

            # Generate summary - fail hard on error
            try:
                summary = _generate_summary(client, item['title'], original_content)
                item['summary'] = summary

                # Save to cache
                if block_id:
                    _save_summary_to_cache(block_id, summary)

                cache_misses += 1
            except Exception as e:
                raise Exception(
                    f"Failed to summarize item '{title_preview}': {e}"
                ) from e

        summarized_items.append(item)

    print(f"Completed summarization of {len(summarized_items)} items")
    print(f"  Cache hits: {cache_hits}, Cache misses: {cache_misses}")
    return summarized_items


def _generate_summary(client: Anthropic, title: str, content: str) -> str:
    """
    Use Claude to generate a concise summary

    Args:
        client: Anthropic client
        title: Item title
        content: Original content

    Returns:
        Markdown-formatted summary
    """
    prompt = f"""You are summarizing a newsletter item from Talawanda High School.

The item title is: {title}

The original content is:
{content}

Please create a concise, clear, text-only summary in markdown format that:
1. Conveys the key information from the original item
2. Is brief but complete (2-4 sentences or bullet points)
3. Uses simple, accessible language
4. Preserves important dates, times, locations, and links
5. Does NOT reference images - just extract and convey the information
6. Uses markdown formatting (bold, lists, links, etc.) for readability

Your summary:"""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip()


