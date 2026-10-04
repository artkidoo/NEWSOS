"""Tests for database tables, models, and constraints."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.article import Article
from app.models.enums import IngestionStatus, SourceType
from app.models.ingestion_run import IngestionRun
from app.models.source import Source


def test_unique_source_feed_url(db_session, sample_source):
    """Verify feed_url unique constraint on sources table."""
    duplicate_source = Source(
        name="Duplicate Source",
        url="https://dup.example.com",
        feed_url=sample_source.feed_url,
        source_type=SourceType.RSS,
    )
    db_session.add(duplicate_source)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_article_content_hash(db_session, sample_source):
    """Verify content_hash unique constraint on articles table."""
    art1 = Article(
        source_id=sample_source.id,
        title="Article 1",
        url="https://example.com/1",
        canonical_url="https://example.com/1",
        published_at=datetime.now(timezone.utc),
        content_hash="hash_abc_123",
    )
    db_session.add(art1)
    db_session.commit()

    art2 = Article(
        source_id=sample_source.id,
        title="Article 2",
        url="https://example.com/2",
        canonical_url="https://example.com/2",
        published_at=datetime.now(timezone.utc),
        content_hash="hash_abc_123",
    )
    db_session.add(art2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_cascade_delete_source_articles(db_session, sample_source):
    """Deleting a source cascades and deletes associated articles."""
    art = Article(
        source_id=sample_source.id,
        title="Article Cascade",
        url="https://example.com/cascade",
        canonical_url="https://example.com/cascade",
        published_at=datetime.now(timezone.utc),
        content_hash="cascade_hash_999",
    )
    db_session.add(art)
    db_session.commit()

    db_session.delete(sample_source)
    db_session.commit()

    found = db_session.query(Article).filter(Article.content_hash == "cascade_hash_999").first()
    assert found is None


def test_ingestion_run_creation(db_session, sample_source):
    """Verify IngestionRun model records metrics."""
    run = IngestionRun(
        source_id=sample_source.id,
        status=IngestionStatus.COMPLETED,
        articles_found=5,
        articles_ingested=4,
        articles_skipped=1,
    )
    db_session.add(run)
    db_session.commit()
    assert run.id is not None
    assert run.articles_ingested == 4
