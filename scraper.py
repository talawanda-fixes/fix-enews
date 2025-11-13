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
from datetime import datetime, timezone
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
            return datetime(year, int(month), int(day), tzinfo=timezone.utc)
        except ValueError:
            return None

    return None


def get_newsletter_links(blog_url: str = BLOG_URL, stop_at_cached: bool = True) -> List[Dict[str, str]]:
    """
    Get all blog entries (newsletters and regular posts) from the Talawanda blog page
    Follows pagination links and optionally stops when hitting all cached content

    Args:
        blog_url: URL of the blog page containing entries
        stop_at_cached: If True, stop scraping when we hit a page with all cached content

    Returns:
        List of dictionaries with 'url', 'date', 'type', and 'cached' keys
        type can be 'newsletter' (Smore) or 'blog_post' (regular blog entry)
    """
    print(f"Fetching blog entries from {blog_url}...")

    entries_data = []
    seen_urls = set()
    page_num = 1

    while True:
        # Construct page URL
        if page_num == 1:
            page_url = blog_url
        else:
            separator = '&' if '?' in blog_url else '?'
            page_url = f"{blog_url}{separator}page={page_num}"

        print(f"  Scraping page {page_num}: {page_url}")

        try:
            response = requests.get(page_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"  Error fetching page {page_num}: {e}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all blog entry wrappers
        blog_wrappers = soup.find_all('div', class_='divBlogWrapper')

        if not blog_wrappers:
            print(f"  No blog entries found on page {page_num}, stopping pagination")
            break

        page_entries = []
        found_new_entry = False

        for wrapper in blog_wrappers:
            # Get title and entry URL
            title_elem = wrapper.find('h3', class_='divBlogDetail-title')
            if not title_elem:
                continue

            title_link = title_elem.find('a')
            if not title_link:
                continue

            entry_url = title_link.get('href', '')
            if not entry_url or entry_url in seen_urls:
                continue

            seen_urls.add(entry_url)

            # Get title text
            title = title_link.get_text().strip()

            # Try to extract date from the entry
            date = parse_date_from_text(title)

            # Check if this entry contains a Smore link
            smore_link = wrapper.find('a', href=lambda h: h and 'smore.com' in h.lower())

            if smore_link:
                # This is a newsletter entry - use the Smore URL
                smore_url = smore_link.get('href', '')
                is_cached = _load_from_cache(smore_url) is not None

                page_entries.append({
                    'url': smore_url,
                    'entry_url': entry_url,
                    'title': title,
                    'date': date,
                    'type': 'newsletter',
                    'cached': is_cached
                })
            else:
                # This is a regular blog post - use the entry URL
                is_cached = _load_from_cache(entry_url) is not None

                page_entries.append({
                    'url': entry_url,
                    'entry_url': entry_url,
                    'title': title,
                    'date': date,
                    'type': 'blog_post',
                    'cached': is_cached
                })

            if not is_cached:
                found_new_entry = True

        if not page_entries:
            print(f"  No entries found on page {page_num}, stopping pagination")
            break

        # Add entries from this page
        entries_data.extend(page_entries)
        newsletters_count = sum(1 for e in page_entries if e['type'] == 'newsletter')
        blog_posts_count = sum(1 for e in page_entries if e['type'] == 'blog_post')
        new_count = sum(1 for e in page_entries if not e['cached'])
        cached_count = sum(1 for e in page_entries if e['cached'])

        print(f"  Found {len(page_entries)} entries on page {page_num} ({newsletters_count} newsletters, {blog_posts_count} blog posts, {new_count} new, {cached_count} cached)")

        # Stop if we should stop at cached and didn't find any new entries
        if stop_at_cached and not found_new_entry:
            print(f"  All entries on page {page_num} are cached, stopping pagination")
            break

        # Check if there's a next page link
        next_link = soup.find('a', class_='anchPaginationLink-next')
        if not next_link:
            print(f"  No next page link found, stopping pagination")
            break

        page_num += 1

    newsletters = sum(1 for e in entries_data if e['type'] == 'newsletter')
    blog_posts = sum(1 for e in entries_data if e['type'] == 'blog_post')
    print(f"Found {len(entries_data)} entries across {page_num} page(s) ({newsletters} newsletters, {blog_posts} blog posts)")
    return entries_data


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


def _get_all_cached_urls() -> List[str]:
    """Get all URLs that are cached"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached_urls = []

    for cache_file in CACHE_DIR.glob("*.json"):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                if 'url' in cached:
                    cached_urls.append(cached['url'])
        except Exception:
            continue

    return cached_urls


def fetch_blog_post(url: str, date: Optional[datetime] = None, title: str = "") -> Optional[Dict]:
    """
    Fetch a blog post (non-newsletter entry) from the school website

    Args:
        url: Blog post URL
        date: Date of the blog post
        title: Title of the blog post

    Returns:
        Dictionary with blog post data (url, html, title, date, type)
    """
    # Try to load from cache first
    cached = _load_from_cache(url)
    if cached:
        print(f"  Fetching: {url} (from cache)")
        soup = BeautifulSoup(cached['html'], 'html.parser')
        return {
            'url': url,
            'html': cached['html'],
            'soup': soup,
            'title': cached.get('title', title),
            'date': date,
            'type': 'blog_post'
        }

    print(f"  Fetching: {url}")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # Extract title if not provided
        if not title:
            title_elem = soup.find(['h1', 'h2'])
            title = title_elem.get_text().strip() if title_elem else url

        # Save to cache
        _save_to_cache(url, html, title)

        return {
            'url': url,
            'html': html,
            'soup': soup,
            'title': title,
            'date': date,
            'type': 'blog_post'
        }
    except Exception as e:
        print(f"  Error fetching blog post: {e}")
        return None


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
            'date': date,
            'type': 'newsletter'
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

        # Wait for Smore content to be present (more specific than just body)
        # Smore newsletters have data-block-type attributes
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-block-type]"))
            )
        except:
            # Fallback to body if no data-block-type found
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

        # Small delay to ensure all content is rendered
        time.sleep(1)

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
            'date': date,
            'type': 'newsletter'
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
    Fetch all blog entries (newsletters and regular posts) from the Talawanda blog

    Args:
        blog_url: URL of the blog page (default: Talawanda High School blog)

    Returns:
        List of entry data dictionaries (newsletters and blog posts)
    """
    # Get all entry links with dates (may stop early at cached content)
    entries_data = get_newsletter_links(blog_url)

    if not entries_data:
        print("No entries found!")
        return []

    # Get URLs we found from scraping
    scraped_urls = {data['url'] for data in entries_data}

    # Find any cached entries that weren't in the scraped pages
    all_cached_urls = _get_all_cached_urls()
    cached_only_urls = [url for url in all_cached_urls if url not in scraped_urls]

    if cached_only_urls:
        print(f"\nFound {len(cached_only_urls)} additional cached entries not in scraped pages")
        # Add them to the list (without dates or type since we don't know them)
        # Assume they're newsletters since that's what we've historically cached
        for url in cached_only_urls:
            entries_data.append({
                'url': url,
                'title': '',
                'date': None,
                'type': 'newsletter',  # Assume newsletter for old cached content
                'cached': True
            })

    # Fetch each entry
    # Optimize by grouping cached vs non-cached
    entries = []
    import time as time_module
    fetch_start = time_module.time()

    cached_entries = [d for d in entries_data if d.get('cached', False)]
    non_cached_entries = [d for d in entries_data if not d.get('cached', False)]

    # Quickly load all cached entries (should be very fast)
    if cached_entries:
        print(f"Loading {len(cached_entries)} cached entries...")
        cache_start = time_module.time()
        for data in cached_entries:
            url = data['url']
            date = data['date']
            entry_type = data.get('type', 'newsletter')
            title = data.get('title', '')

            if entry_type == 'blog_post':
                entry = fetch_blog_post(url, date, title)
            else:
                entry = fetch_newsletter(url, date)

            if entry:
                entries.append(entry)
        cache_elapsed = time_module.time() - cache_start
        print(f"  Loaded {len(entries)} cached entries in {cache_elapsed:.2f}s")

    # Fetch non-cached entries with delays
    if non_cached_entries:
        print(f"Fetching {len(non_cached_entries)} new entries...")
        for i, data in enumerate(non_cached_entries, 1):
            url = data['url']
            date = data['date']
            entry_type = data.get('type', 'newsletter')
            title = data.get('title', '')
            date_str = date.strftime('%m/%d/%Y') if date else 'unknown date'
            type_str = 'blog post' if entry_type == 'blog_post' else 'newsletter'
            print(f"  Fetching {type_str} {i}/{len(non_cached_entries)} ({date_str})...")

            if entry_type == 'blog_post':
                entry = fetch_blog_post(url, date, title)
            else:
                entry = fetch_newsletter(url, date)

            if entry:
                entries.append(entry)

            # Be polite - add a small delay between requests
            if i < len(non_cached_entries):
                time.sleep(0.2)

    fetch_elapsed = time_module.time() - fetch_start
    newsletters_count = sum(1 for e in entries if e.get('type') == 'newsletter')
    blog_posts_count = sum(1 for e in entries if e.get('type') == 'blog_post')
    print(f"\nSuccessfully fetched {len(entries)} entries ({newsletters_count} newsletters, {blog_posts_count} blog posts)")
    print(f"Total fetch time: {fetch_elapsed:.2f}s")
    return entries
