"""Pytest fixtures for NEWSROOM OS test suite."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.enums import SourceType, TrustLevel
from app.models.source import Source

SAMPLE_RSS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Global Dispatch News</title>
    <link>https://globaldispatch.example.com</link>
    <description>Latest international breaking news</description>
    <item>
      <title>Global Summit Concludes with Historic Accord</title>
      <link>https://globaldispatch.example.com/world/summit-accord?utm_source=rss&amp;utm_medium=feed&amp;ref=newsroom</link>
      <guid isPermaLink="false">guid-summit-2026-001</guid>
      <pubDate>Thu, 02 Oct 2026 14:30:00 GMT</pubDate>
      <author>correspondent@example.com (Jane Doe)</author>
      <description>&lt;p&gt;World leaders reached a unanimous consensus on clean energy standards.&lt;/p&gt;&lt;img src="https://images.example.com/summit.jpg"/&gt;</description>
      <category>Diplomacy</category>
    </item>
    <item>
      <title>Breakthrough in Fusion Energy Reactor Testing</title>
      <link>https://globaldispatch.example.com/science/fusion-milestone?utm_campaign=daily</link>
      <guid isPermaLink="false">guid-fusion-2026-002</guid>
      <pubDate>Fri, 03 Oct 2026 09:15:00 GMT</pubDate>
      <author>Mark Smith</author>
      <description>Scientists sustained net energy gain for over twenty minutes.</description>
      <media:content url="https://images.example.com/fusion.jpg" medium="image"/>
      <category>Science</category>
    </item>
  </channel>
</rss>
"""

SAMPLE_ATOM_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Tech Horizons</title>
  <link href="https://techhorizons.example.com/feed.atom" rel="self"/>
  <link href="https://techhorizons.example.com/"/>
  <updated>2026-10-03T12:00:00Z</updated>
  <id>urn:uuid:60a76c80-d399-11d9-b93C-0003939e0af6</id>
  <entry>
    <title>Autonomous Systems Pass New Safety Benchmark</title>
    <link href="https://techhorizons.example.com/articles/auto-safety?utm_medium=atom" rel="alternate"/>
    <id>urn:article:auto-safety-458</id>
    <updated>2026-10-03T11:45:00Z</updated>
    <published>2026-10-03T11:45:00Z</published>
    <author>
      <name>Alex Vance</name>
    </author>
    <summary type="html">&lt;p&gt;Independent regulators certified the new vehicle operating system.&lt;/p&gt;</summary>
    <category term="Robotics"/>
  </entry>
</feed>
"""

SAMPLE_MALFORMED_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Broken Feed
    <item>
      <title>Unclosed Tag Article</title>
      <link>https://broken.example.com/story-1</link>
      <description>Malformed content without closing tags
"""


@pytest.fixture(scope="function")
def test_engine():
    """Create a single SQLite in-memory test engine using StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Provide a database session attached to the shared in-memory test engine."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_client(test_engine, db_session):
    """FastAPI TestClient with overridden database session and engine."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_source(db_session) -> Source:
    """Insert a standard test news source."""
    source = Source(
        name="Global Dispatch News",
        url="https://globaldispatch.example.com",
        feed_url="https://globaldispatch.example.com/rss.xml",
        source_type=SourceType.RSS,
        category="world",
        language="en",
        country="GLOBAL",
        trust_level=TrustLevel.HIGH,
        enabled=True,
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source
