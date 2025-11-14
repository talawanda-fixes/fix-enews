"""
Rate limiting for HTTP requests
Extracted from scraper.py to be reusable across use cases
"""

import time
from urllib.parse import urlparse
from collections import defaultdict, deque


class RateLimiter:
    """
    Rate limiter to ensure we don't make too many requests to the same host

    Limits requests to max_requests per time_window seconds per host
    """
    def __init__(self, max_requests: int = 30, time_window: float = 20.0):
        self.max_requests = max_requests
        self.time_window = time_window
        # Track request timestamps per host
        self.requests = defaultdict(deque)

    def wait_if_needed(self, url: str):
        """Wait if we've exceeded the rate limit for this host"""
        host = urlparse(url).netloc
        now = time.time()

        # Remove timestamps older than time_window
        while self.requests[host] and self.requests[host][0] < now - self.time_window:
            self.requests[host].popleft()

        # If we've hit the limit, wait until we can make another request
        if len(self.requests[host]) >= self.max_requests:
            oldest_request = self.requests[host][0]
            wait_time = (oldest_request + self.time_window) - now
            if wait_time > 0:
                print(f"    Rate limit: waiting {wait_time:.1f}s for {host}")
                time.sleep(wait_time)
                # Clean up again after waiting
                while self.requests[host] and self.requests[host][0] < time.time() - self.time_window:
                    self.requests[host].popleft()

        # Record this request
        self.requests[host].append(time.time())
