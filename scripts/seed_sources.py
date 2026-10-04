"""Seeds default verified syndication news feeds into the database."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.enums import SourceType, TrustLevel
from app.models.source import Source

DEFAULT_SOURCES = [
    {
        "name": "BBC News - World",
        "url": "https://www.bbc.co.uk/news/world",
        "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "source_type": SourceType.RSS,
        "category": "world",
        "trust_level": TrustLevel.VERIFIED,
    },
    {
        "name": "Reuters - Top News",
        "url": "https://www.reuters.com",
        "feed_url": "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best",
        "source_type": SourceType.RSS,
        "category": "world",
        "trust_level": TrustLevel.VERIFIED,
    },
    {
        "name": "NPR News",
        "url": "https://www.npr.org",
        "feed_url": "https://feeds.npr.org/1001/rss.xml",
        "source_type": SourceType.RSS,
        "category": "general",
        "trust_level": TrustLevel.HIGH,
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com",
        "feed_url": "https://techcrunch.com/feed/",
        "source_type": SourceType.RSS,
        "category": "technology",
        "trust_level": TrustLevel.HIGH,
    },
    {
        "name": "Nature - Science",
        "url": "https://www.nature.com",
        "feed_url": "https://www.nature.com/nature.rss",
        "source_type": SourceType.RSS,
        "category": "science",
        "trust_level": TrustLevel.VERIFIED,
    },
]


def seed():
    db = SessionLocal()
    try:
        for s_data in DEFAULT_SOURCES:
            existing = db.query(Source).filter(Source.feed_url == s_data["feed_url"]).first()
            if not existing:
                s = Source(**s_data)
                db.add(s)
                print(f"[+] Added source: {s_data['name']}")
            else:
                print(f"[-] Source already exists: {s_data['name']}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
