"""Syndication Feed Parser and Discovery Engine."""

from typing import Any

import feedparser

from app.core.exceptions import ParseError
from app.core.logging import get_logger

logger = get_logger(__name__)


class FeedDetector:
    """Parses raw feed bytes (RSS 2.0, Atom 1.0, RDF) into structured item dictionaries."""

    @staticmethod
    def parse(raw_content: bytes) -> dict[str, Any]:
        """Parses raw XML/syndication content using feedparser."""
        if not raw_content or not raw_content.strip():
            raise ParseError("Cannot parse empty feed content.")

        parsed = feedparser.parse(raw_content)

        # Check for catastrophic XML parsing failure without any entries
        if getattr(parsed, "bozo", False) and not parsed.entries:
            bozo_exc = getattr(parsed, "bozo_exception", None)
            raise ParseError(f"Malformed syndication feed: {bozo_exc}")

        feed_metadata = {
            "title": parsed.feed.get("title", ""),
            "link": parsed.feed.get("link", ""),
            "description": parsed.feed.get("description", ""),
            "version": parsed.get("version", "unknown"),
        }

        entries: list[dict[str, Any]] = []
        for entry in parsed.entries:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "guid": entry.get("id") or entry.get("guid") or entry.get("link", ""),
                "published": entry.get("published") or entry.get("updated") or entry.get("pubDate"),
                "author": entry.get("author", ""),
                "summary": entry.get("summary", ""),
                "content": entry.get("content", [{}])[0].get("value", "") if "content" in entry else "",
                "category": entry.get("category", "") or (entry.get("tags", [{}])[0].get("term", "") if entry.get("tags") else ""),
                "enclosures": entry.get("enclosures", []),
                "media_content": entry.get("media_content", []),
            })

        return {
            "feed": feed_metadata,
            "entries": entries,
        }
