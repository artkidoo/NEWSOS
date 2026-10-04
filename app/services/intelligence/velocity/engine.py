"""Velocity Engine: Measures article accumulation speed and coverage acceleration."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.intelligence import StoryCluster, StoryClusterArticle


class VelocityEngine:
    """Calculates coverage velocity (articles per time unit) and momentum."""

    WINDOW_HOURS = 12

    @classmethod
    def calculate_velocity(cls, db: Session, cluster: StoryCluster, reference_time: datetime = None) -> float:
        """Calculates normalized velocity score (0.0 to 100.0)."""
        now = reference_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # Get publication dates of articles in cluster
        articles = (
            db.query(Article.published_at)
            .join(StoryClusterArticle, StoryClusterArticle.article_id == Article.id)
            .filter(StoryClusterArticle.story_cluster_id == cluster.id)
            .all()
        )

        if not articles:
            return 0.0

        article_dates = [
            a[0].replace(tzinfo=timezone.utc) if a[0].tzinfo is None else a[0]
            for a in articles
        ]

        total_articles = len(article_dates)
        if total_articles <= 1:
            return 10.0

        # Articles published within recent window (last 6 hours)
        recent_cutoff = now - timedelta(hours=6)
        recent_count = sum(1 for d in article_dates if d >= recent_cutoff)

        # Articles published within previous window (6 to 12 hours ago)
        prev_cutoff = now - timedelta(hours=12)
        prev_count = sum(1 for d in article_dates if prev_cutoff <= d < recent_cutoff)

        # Base rate: articles per hour in the cluster's active lifespan
        lifespan_hours = max(1.0, (cluster.last_seen_at - cluster.first_seen_at).total_seconds() / 3600.0)
        overall_rate = total_articles / lifespan_hours

        # Acceleration factor
        acceleration = (recent_count + 1) / (prev_count + 1)

        # Scale to 0-100:
        # A breaking story with 5+ articles in 6 hours gets ~80+
        raw_velocity = (recent_count * 15.0) + (overall_rate * 10.0) * min(2.0, acceleration)
        return round(min(100.0, max(0.0, raw_velocity)), 2)
