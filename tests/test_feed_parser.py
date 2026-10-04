"""Tests for syndication feed parsing."""

import pytest

from app.core.exceptions import ParseError
from app.services.discovery.feed_detector import FeedDetector
from tests.conftest import SAMPLE_ATOM_XML, SAMPLE_MALFORMED_XML, SAMPLE_RSS_XML


def test_parse_rss_feed():
    """Verify RSS 2.0 XML parsing."""
    result = FeedDetector.parse(SAMPLE_RSS_XML)
    assert result["feed"]["title"] == "Global Dispatch News"
    entries = result["entries"]
    assert len(entries) == 2
    assert "Global Summit" in entries[0]["title"]
    assert entries[0]["guid"] == "guid-summit-2026-001"


def test_parse_atom_feed():
    """Verify Atom 1.0 XML parsing."""
    result = FeedDetector.parse(SAMPLE_ATOM_XML)
    assert result["feed"]["title"] == "Tech Horizons"
    entries = result["entries"]
    assert len(entries) == 1
    assert "Autonomous Systems" in entries[0]["title"]


def test_parse_empty_content_raises():
    """Parsing empty bytes raises ParseError."""
    with pytest.raises(ParseError):
        FeedDetector.parse(b"")


def test_parse_malformed_xml():
    """Malformed XML without valid entries raises ParseError."""
    with pytest.raises(ParseError):
        FeedDetector.parse(SAMPLE_MALFORMED_XML)
