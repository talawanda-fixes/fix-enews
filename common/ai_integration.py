"""
AI integration utilities
Extracted from summarizer.py for reuse across use cases
"""

import os
import base64
import requests
from typing import Optional, Dict
from anthropic import Anthropic


def get_anthropic_client(api_key: str = None) -> Anthropic:
    """
    Get Anthropic API client

    Args:
        api_key: API key (or uses ANTHROPIC_API_KEY env var)

    Returns:
        Anthropic client instance

    Raises:
        ValueError: If API key is not available
    """
    if not api_key:
        api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is required. "
            "Set it with: export ANTHROPIC_API_KEY='your-api-key-here'"
        )

    return Anthropic(api_key=api_key)


def fetch_and_encode_image(url: str) -> Optional[Dict]:
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
