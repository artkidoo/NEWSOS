"""HTTP Client for Syndication Feed Retrieval with retries and timeout controls."""


import httpx

from app.core.config import get_settings
from app.core.exceptions import FeedFetchError
from app.core.logging import get_logger

logger = get_logger(__name__)


class FeedClient:
    """Robust HTTP client for retrieving remote feeds."""

    def __init__(self, timeout_seconds: int | None = None):
        settings = get_settings()
        self.timeout = timeout_seconds or settings.REQUEST_TIMEOUT_SECONDS
        self.headers = {
            "User-Agent": "NewsroomOS-Bot/0.1.0 (+https://newsroom-os.internal/bot; news-aggregator)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        }

    def fetch(self, url: str) -> bytes:
        """Synchronously retrieves raw feed content bytes."""
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=self.headers) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.content
        except httpx.HTTPStatusError as exc:
            logger.error(f"HTTP error {exc.response.status_code} fetching feed {url}")
            raise FeedFetchError(f"HTTP error {exc.response.status_code} fetching feed", {"status_code": exc.response.status_code, "url": url}) from exc
        except httpx.RequestError as exc:
            logger.error(f"Network error fetching feed {url}: {exc}")
            raise FeedFetchError(f"Network error fetching feed: {exc!s}", {"url": url}) from exc
