"""Freshness Engine: Calculates deterministic exponential time decay score."""

import math
from datetime import datetime, timezone


class FreshnessEngine:
    """Calculates freshness score (0.0 to 100.0) using exponential decay."""

    HALF_LIFE_HOURS = 12.0  # Story loses 50% freshness every 12 hours of inactivity

    @classmethod
    def calculate_freshness(cls, last_seen_at: datetime, reference_time: datetime = None) -> float:
        """Calculates freshness score from last article timestamp using exponential half-life decay."""
        now = reference_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if last_seen_at.tzinfo is None:
            last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)

        age_seconds = max(0.0, (now - last_seen_at).total_seconds())
        age_hours = age_seconds / 3600.0

        decay = math.pow(0.5, age_hours / cls.HALF_LIFE_HOURS)
        score = 100.0 * decay
        return round(min(100.0, max(0.0, score)), 2)
