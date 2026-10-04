"""Tests for ingestion idempotency."""

from unittest.mock import MagicMock

from app.models.article import Article
from app.services.discovery.feed_client import FeedClient
from app.services.ingestion.engine import IngestionEngine
from tests.conftest import SAMPLE_RSS_XML


def test_ingestion_idempotent_repeated_runs(db_session, sample_source):
    """Running ingestion repeatedly on unchanged feed results in 0 duplicate articles inserted."""
    mock_client = MagicMock(spec=FeedClient)
    mock_client.fetch.return_value = SAMPLE_RSS_XML

    engine = IngestionEngine(db_session, feed_client=mock_client)

    # First run
    res1 = engine.ingest_source(sample_source)
    assert res1["found"] == 2
    assert res1["ingested"] == 2
    assert res1["skipped"] == 0
    assert db_session.query(Article).count() == 2

    # Second run with identical feed
    res2 = engine.ingest_source(sample_source)
    assert res2["found"] == 2
    assert res2["ingested"] == 0
    assert res2["skipped"] == 2
    assert db_session.query(Article).count() == 2


def test_ingestion_audit_run_created(db_session, sample_source):
    """Verify IngestionRun record accurately tracks counts."""
    mock_client = MagicMock(spec=FeedClient)
    mock_client.fetch.return_value = SAMPLE_RSS_XML

    engine = IngestionEngine(db_session, feed_client=mock_client)
    engine.ingest_source(sample_source)

    runs = engine.run_repo.list_runs(source_id=sample_source.id)
    assert len(runs) >= 1
    assert runs[0].articles_found == 2
    assert runs[0].articles_ingested == 2


def test_failed_feed_handled_gracefully(db_session, sample_source):
    """Network failure logs error and marks run as FAILED without crashing."""
    mock_client = MagicMock(spec=FeedClient)
    mock_client.fetch.side_effect = Exception("Connection timeout")

    engine = IngestionEngine(db_session, feed_client=mock_client)
    res = engine.ingest_source(sample_source)
    assert "error" in res

    runs = engine.run_repo.list_runs(source_id=sample_source.id)
    assert runs[0].status.value == "failed"
