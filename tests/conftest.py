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


# ---------------------------------------------------------------------------
# Phase 3: AI Editorial Desk fixtures
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta
from datetime import timezone as _tz

from app.models.article import Article
from app.models.intelligence import Entity, StoryCluster, StoryClusterArticle, StoryClusterEntity
from app.services.editorial.context import ResearchContext, ResearchContextEngine
from app.services.editorial.generator import EditorialGenerationService
from app.services.editorial.providers import TestEditorialProvider


def make_story_cluster(db, *, articles: list[dict] | None = None) -> StoryCluster:
    """Create a source + story cluster with linked articles/entities and scores.

    Each entry in `articles` is a dict with keys: title, content, publisher_name,
    optionally published_at, url, entity (name, type).
    """
    now = datetime.now(_tz.utc)
    articles = articles or [
        {
            "title": "City Council Approves Transit Budget of 45 Million",
            "content": "The Springfield City Council approved a transit budget of 45 million on March 3, 2026. "
                       "Officials said the plan will expand bus routes across Springfield.",
            "publisher_name": "Global Dispatch News",
            "entity": ("Springfield City Council", "organization"),
        },
        {
            "title": "Transit Budget of 45 Million Clears Springfield Council",
            "content": "Springfield lawmakers finalized the 45 million transit package on March 3, 2026. "
                       "Mayor Elena Ramirez called it a practical step for commuters.",
            "publisher_name": "Capitol Wire",
            "entity": ("Elena Ramirez", "person"),
        },
    ]

    seen_sources: dict[str, Source] = {}
    cluster = StoryCluster(
        canonical_title="Springfield Transit Budget Approved",
        summary=None,
        category="politics",
        status="TRENDING",
        first_seen_at=now - timedelta(hours=8),
        last_seen_at=now,
        article_count=len(articles),
        source_count=len({a["publisher_name"] for a in articles}),
        velocity_score=72.5,
        freshness_score=88.0,
        relevance_score=65.0,
        corroboration_score=80.0,
        trending_score=77.25,
    )
    db.add(cluster)
    db.flush()

    for idx, spec in enumerate(articles):
        pub = spec["publisher_name"]
        if pub not in seen_sources:
            src = Source(
                name=pub,
                url=f"https://{pub.lower().replace(' ', '')}.example.com",
                feed_url=f"https://{pub.lower().replace(' ', '')}.example.com/rss",
                source_type=SourceType.RSS,
                category="politics",
                trust_level=TrustLevel.HIGH,
                enabled=True,
            )
            db.add(src)
            db.flush()
            seen_sources[pub] = src
        art = Article(
            source_id=seen_sources[pub].id,
            title=spec["title"],
            url=spec.get("url", f"https://e{idx}.example.com/story-{idx}"),
            canonical_url=spec.get("url", f"https://e{idx}.example.com/story-{idx}"),
            published_at=spec.get("published_at", now - timedelta(hours=idx)),
            content=spec["content"],
            category="politics",
            content_hash=f"phase3-hash-{idx}-{cluster.id}-{id(spec)}",
        )
        db.add(art)
        db.flush()
        db.add(StoryClusterArticle(
            story_cluster_id=cluster.id,
            article_id=art.id,
            similarity_score=0.9 - 0.1 * idx,
        ))
        ent_spec = spec.get("entity")
        if ent_spec:
            name, etype = ent_spec
            ent = db.query(Entity).filter(Entity.normalized_name == name.lower()).first()
            if ent is None:
                ent = Entity(name=name, normalized_name=name.lower(), entity_type=etype)
                db.add(ent)
                db.flush()
            existing_link = db.get(StoryClusterEntity, (cluster.id, ent.id))
            if existing_link is None:
                db.add(StoryClusterEntity(story_cluster_id=cluster.id, entity_id=ent.id, mention_count=2))

    db.commit()
    db.refresh(cluster)
    return cluster


@pytest.fixture
def editorial_cluster(db_session):
    """Standard two-article corroborated story cluster for editorial tests."""
    return make_story_cluster(db_session)


@pytest.fixture
def research_context(db_session, editorial_cluster) -> ResearchContext:
    engine = ResearchContextEngine(db_session)
    return engine.build(editorial_cluster.id)


@pytest.fixture
def demo_provider(research_context) -> TestEditorialProvider:
    provider = TestEditorialProvider()
    provider.set_context(research_context.as_dict())
    return provider


@pytest.fixture
def generation_service(db_session, demo_provider) -> EditorialGenerationService:
    return EditorialGenerationService(db_session, provider=demo_provider)


@pytest.fixture
def editorial_client(test_client, db_session, editorial_cluster, demo_provider):
    """TestClient whose editorial service uses the deterministic demo provider.

    Overrides the generation-service dependency so no real AI API is ever
    contacted during tests. The shared in-memory `db_session` is used by both
    the fixture data and the overridden service (StaticPool engine), matching
    the existing `test_client` get_db override.
    """
    from app.api.routes.editorial import _service
    from app.services.editorial.generator import EditorialGenerationService

    def service_override():
        return EditorialGenerationService(db_session, provider=demo_provider)

    test_client.app.dependency_overrides[_service] = service_override
    yield test_client
    test_client.app.dependency_overrides.pop(_service, None)
