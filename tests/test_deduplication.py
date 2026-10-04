"""Tests for deduplication engine."""

from datetime import datetime, timezone

from app.models.article import Article
from app.services.deduplication.deduplicator import Deduplicator


def test_jaccard_similarity_identical_titles():
    """Identical titles return 1.0 similarity."""
    sim = Deduplicator.calculate_similarity(
        "Global summit reaches historic clean energy accord",
        "Global summit reaches historic clean energy accord",
    )
    assert sim == 1.0


def test_jaccard_similarity_unrelated_titles():
    """Completely different titles return 0.0 similarity."""
    sim = Deduplicator.calculate_similarity(
        "Global summit reaches historic clean energy accord",
        "Stock markets tumble following inflation report",
    )
    assert sim == 0.0


def test_exact_hash_duplicate_detected(db_session, sample_source):
    """Article with existing content_hash is identified as duplicate."""
    art = Article(
        source_id=sample_source.id,
        title="Breaking News",
        url="https://example.com/breaking",
        canonical_url="https://example.com/breaking",
        published_at=datetime.now(timezone.utc),
        content_hash="dup_hash_123",
    )
    db_session.add(art)
    db_session.commit()

    is_dup, orig_id = Deduplicator.check_duplicate(
        db_session,
        content_hash="dup_hash_123",
        canonical_url="https://example.com/breaking",
        title="Breaking News",
    )
    assert is_dup is True
    assert orig_id == art.id


def test_near_duplicate_title_detected(db_session, sample_source):
    """Article with near-identical title (sim >= 0.90) is flagged."""
    art = Article(
        source_id=sample_source.id,
        title="Historic Climate Treaty Signed by Fifty Nations",
        url="https://example.com/story-a",
        canonical_url="https://example.com/story-a",
        published_at=datetime.now(timezone.utc),
        content_hash="unique_hash_a",
    )
    db_session.add(art)
    db_session.commit()

    is_dup, orig_id = Deduplicator.check_duplicate(
        db_session,
        content_hash="unique_hash_b",
        canonical_url="https://example.com/story-b",
        title="Historic Climate Treaty Signed by Fifty Nations Today",
    )
    assert is_dup is True
    assert orig_id == art.id
