"""Integration test executing the full clean database lifecycle."""

from scripts.test_clean_database import run_clean_test


def test_clean_database_integration():
    """Verify clean database lifecycle end-to-end."""
    run_clean_test()
