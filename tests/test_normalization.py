"""Tests for article normalization engine."""

import pytest

from app.core.exceptions import NormalizationError
from app.services.normalization.normalizer import ArticleNormalizer


def test_clean_html_strips_scripts_and_tags():
    """Verify HTML cleaning strips harmful tags and extracts text."""
    raw = "<p>Hello <b>World</b>!</p><script>alert('xss');</script><style>body{color:red}</style>"
    cleaned = ArticleNormalizer.clean_html(raw)
    assert cleaned == "Hello World !"


def test_normalize_url_strips_tracking_params():
    """Verify UTM parameters and trailing slashes are stripped."""
    url = "https://example.com/article/123/?utm_source=twitter&utm_campaign=spring&fbclid=xyz"
    normalized = ArticleNormalizer.normalize_url(url)
    assert normalized == "https://example.com/article/123"


def test_content_hash_deterministic():
    """Verify compute_content_hash produces identical SHA-256 for identical inputs."""
    h1 = ArticleNormalizer.compute_content_hash("Headline Test", "https://example.com/item")
    h2 = ArticleNormalizer.compute_content_hash("Headline Test", "https://example.com/item")
    assert h1 == h2
    assert len(h1) == 64


def test_normalize_empty_title_raises():
    """Normalization raises NormalizationError if title is empty."""
    with pytest.raises(NormalizationError):
        ArticleNormalizer.normalize({"title": "", "link": "https://example.com"}, source_id=1)
