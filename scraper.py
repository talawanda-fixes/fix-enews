"""
Smore newsletter scraper
Fetches newsletters from Smore platform
"""

import requests
from typing import List, Dict
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


BLOG_URL = "https://www.talawanda.org/talawanda-high-school-blog/"


def get_newsletter_links(blog_url: str = BLOG_URL) -> List[str]:
    """
    Get all Smore newsletter URLs from the Talawanda blog page

    Args:
        blog_url: URL of the blog page containing newsletter links

    Returns:
        List of Smore newsletter URLs
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
    smore_links = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        if 'smore.com' in href.lower():
            if href not in smore_links:  # Avoid duplicates
                smore_links.append(href)

    print(f"Found {len(smore_links)} unique Smore newsletter links")
    return smore_links


def fetch_newsletter(url: str) -> Dict:
    """
    Fetch a single newsletter from Smore using Selenium
    (Smore uses JavaScript rendering)

    Args:
        url: Smore newsletter URL

    Returns:
        Dictionary with newsletter data (url, html, title)
    """
    print(f"  Fetching: {url}")

    # Setup headless Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    driver = None
    try:
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

        return {
            'url': url,
            'html': html,
            'soup': soup,
            'title': title
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
    # Get all newsletter links
    newsletter_urls = get_newsletter_links(blog_url)

    if not newsletter_urls:
        print("No newsletter links found!")
        return []

    # Fetch each newsletter
    newsletters = []
    for i, url in enumerate(newsletter_urls, 1):
        print(f"Fetching newsletter {i}/{len(newsletter_urls)}...")
        newsletter = fetch_newsletter(url)
        if newsletter:
            newsletters.append(newsletter)

        # Be polite - add a small delay between requests
        if i < len(newsletter_urls):
            time.sleep(1)

    print(f"\nSuccessfully fetched {len(newsletters)} newsletters")
    return newsletters
