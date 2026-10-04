"""Article Normalization Engine: HTML sanitization, canonical URL stripping, date parsing."""

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from app.core.exceptions import NormalizationError
from app.core.logging import get_logger

logger = get_logger(__name__)

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source", "mc_cid", "mc_eid", "igshid",
}


class ArticleNormalizer:
    """Normalizes raw feed items into canonical, clean Article records."""

    @staticmethod
    def clean_html(raw_html: str) -> str:
        """Removes script, style, iframe tags and strips HTML to plain clean text."""
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "iframe", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        # Collapse whitespace
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def normalize_url(url: str) -> str:
        """Strips tracking query parameters and normalizes protocol and scheme."""
        if not url:
            return ""
        parsed = urlparse(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return url.strip()

        # Filter out tracking query parameters
        filtered_queries = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in TRACKING_PARAMS
        ]
        new_query = urlencode(filtered_queries)

        clean_path = parsed.path
        if clean_path.endswith("/") and len(clean_path) > 1:
            clean_path = clean_path.rstrip("/")

        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            clean_path,
            parsed.params,
            new_query,
            "",  # Remove fragment
        ))

    @staticmethod
    def parse_datetime(raw_date: Any) -> datetime:
        """Parses arbitrary date representations into UTC datetime."""
        if isinstance(raw_date, datetime):
            if raw_date.tzinfo is None:
                return raw_date.replace(tzinfo=timezone.utc)
            return raw_date.astimezone(timezone.utc)

        if not raw_date or not str(raw_date).strip():
            return datetime.now(timezone.utc)

        try:
            parsed = date_parser.parse(str(raw_date))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    @classmethod
    def compute_content_hash(cls, title: str, canonical_url: str) -> str:
        """Computes a SHA-256 fingerprint from title and canonical URL."""
        normalized_str = f"{title.strip().lower()}|{canonical_url.strip().lower()}"
        return hashlib.sha256(normalized_str.encode("utf-8")).hexdigest()

    @classmethod
    def normalize(cls, raw_entry: dict[str, Any], source_id: int) -> dict[str, Any]:
        """Validates and normalizes raw entry into canonical article attributes."""
        title = raw_entry.get("title", "").strip()
        if not title:
            raise NormalizationError("Article must possess a non-empty title.")

        raw_url = raw_entry.get("link") or raw_entry.get("guid") or ""
        if not raw_url.strip():
            raise NormalizationError("Article missing link and GUID.")

        canonical_url = cls.normalize_url(raw_url)
        content_hash = cls.compute_content_hash(title, canonical_url)

        summary_text = cls.clean_html(raw_entry.get("summary", ""))
        content_text = cls.clean_html(raw_entry.get("content", "")) or summary_text

        # Extract image URL if present in media tags or enclosure
        image_url: str | None = None
        for enc in raw_entry.get("enclosures", []):
            if enc.get("type", "").startswith("image/"):
                image_url = enc.get("href")
                break
        if not image_url:
            for media in raw_entry.get("media_content", []):
                if media.get("medium") == "image" or media.get("type", "").startswith("image/"):
                    image_url = media.get("url")
                    break

        published_at = cls.parse_datetime(raw_entry.get("published"))

        return {
            "source_id": source_id,
            "title": title,
            "url": raw_url.strip(),
            "canonical_url": canonical_url,
            "author": (raw_entry.get("author") or "").strip() or None,
            "published_at": published_at,
            "summary": summary_text[:2000] if summary_text else None,
            "content": content_text[:10000] if content_text else None,
            "image_url": image_url,
            "category": (raw_entry.get("category") or "general").strip().lower(),
            "content_hash": content_hash,
            "guid": raw_entry.get("guid") or canonical_url,
            "language": "en",
        }
