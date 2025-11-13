"""
Smore newsletter scraper
Fetches newsletters from Smore platform
"""

import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import time
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import os


BLOG_URL = "https://www.talawanda.org/talawanda-high-school-blog/"
CACHE_DIR = Path("cache/newsletters")


def parse_date_from_text(text: str) -> Optional[datetime]:
    """
    Extract date from text like "THS Enews 11/7/25"

    Args:
        text: Text containing date

    Returns:
        datetime object or None
    """
    # Look for date patterns like MM/DD/YY or M/D/YY
    match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', text)
    if match:
        month, day, year = match.groups()

        # Convert 2-digit year to 4-digit
        year = int(year)
        if year < 100:
            year = 2000 + year if year < 50 else 1900 + year

        try:
            return datetime(year, int(month), int(day))
        except ValueError:
            return None

    return None


def get_newsletter_links(blog_url: str = BLOG_URL) -> List[Dict[str, str]]:
    """
    Get all Smore newsletter URLs and dates from the Talawanda blog page

    Args:
        blog_url: URL of the blog page containing newsletter links

    Returns:
        List of dictionaries with 'url' and 'date' keys
    """
    print(f"Fetching newsletter links from {blog_url}...")

    try:
        response = requests.get(blog_url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching blog page: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all links that point to smore.com
    newsletter_data = []
    seen_urls = set()

    for link in soup.find_all('a', href=True):
        href = link['href']
        if 'smore.com' in href.lower() and href not in seen_urls:
            seen_urls.add(href)

            # Try to extract date from surrounding text
            date = None
            parent = link.parent
            if parent:
                parent_text = parent.get_text()
                date = parse_date_from_text(parent_text)

            newsletter_data.append({
                'url': href,
                'date': date
            })

    print(f"Found {len(newsletter_data)} unique Smore newsletter links")
    return newsletter_data


def _get_cache_key(url: str) -> str:
    """Generate cache key from URL"""
    return hashlib.md5(url.encode()).hexdigest()


def _load_from_cache(url: str) -> Optional[Dict]:
    """Load newsletter from cache if available"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{_get_cache_key(url)}.json"

    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                return cached
        except Exception:
            return None
    return None


def _save_to_cache(url: str, html: str, title: str):
    """Save newsletter to cache"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{_get_cache_key(url)}.json"

    cache_data = {
        'url': url,
        'html': html,
        'title': title
    }

    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False)


def fetch_newsletter(url: str, date: Optional[datetime] = None) -> Dict:
    """
    Fetch a single newsletter from Smore using Selenium
    (Smore uses JavaScript rendering)
    Uses cache to avoid re-fetching unchanged newsletters

    Args:
        url: Smore newsletter URL
        date: Date of the newsletter

    Returns:
        Dictionary with newsletter data (url, html, title, date)
    """
    # Try to load from cache first
    cached = _load_from_cache(url)
    if cached:
        print(f"  Fetching: {url} (from cache)")
        # Recreate soup from cached HTML
        soup = BeautifulSoup(cached['html'], 'html.parser')
        return {
            'url': cached['url'],
            'html': cached['html'],
            'soup': soup,
            'title': cached['title'],
            'date': date
        }

    print(f"  Fetching: {url}")

    # Setup headless Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    # Use system chromedriver if specified (for GitHub Actions)
    chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')

    driver = None
    try:
        if chromedriver_path:
            service = Service(chromedriver_path)
        else:
            service = Service(ChromeDriverManager().install())

        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)

        # Wait for page to load - wait for body to be present
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Give JavaScript time to render content
        time.sleep(5)

        # Get the rendered HTML
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Extract title
        title = driver.title

        # Save to cache
        _save_to_cache(url, html, title)

        return {
            'url': url,
            'html': html,
            'soup': soup,
            'title': title,
            'date': date
        }

    except Exception as e:
        print(f"  Error fetching newsletter: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if driver:
            driver.quit()


def fetch_newsletters(blog_url: str = BLOG_URL) -> List[Dict]:
    """
    Fetch all newsletters from the Talawanda blog

    Args:
        blog_url: URL of the blog page (default: Talawanda High School blog)

    Returns:
        List of newsletter data dictionaries
    """
    # Get all newsletter links with dates
    newsletter_data = get_newsletter_links(blog_url)

    if not newsletter_data:
        print("No newsletter links found!")
        return []

    # Fetch each newsletter
    newsletters = []
    for i, data in enumerate(newsletter_data, 1):
        url = data['url']
        date = data['date']
        date_str = date.strftime('%m/%d/%Y') if date else 'unknown date'
        print(f"Fetching newsletter {i}/{len(newsletter_data)} ({date_str})...")

        newsletter = fetch_newsletter(url, date)
        if newsletter:
            newsletters.append(newsletter)

        # Be polite - add a small delay between requests
        if i < len(newsletter_data):
            time.sleep(1)

    print(f"\nSuccessfully fetched {len(newsletters)} newsletters")
    return newsletters
