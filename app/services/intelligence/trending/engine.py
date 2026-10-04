"""Trending Engine: Calculates composite trending score and evaluates the Story State Machine."""

import json

from sqlalchemy.orm import Session

from app.models.intelligence import StoryCluster
from app.services.intelligence.corroboration.engine import CorroborationEngine
from app.services.intelligence.freshness.engine import FreshnessEngine
from app.services.intelligence.relevance.engine import RelevanceEngine
from app.services.intelligence.velocity.engine import VelocityEngine


class TrendingEngine:
    """Calculates weighted trending score and transitions story lifecycle states."""

    # Documented weights:
    # velocity: 0.30
    # freshness: 0.25
    # corroboration: 0.25
    # relevance: 0.20
    WEIGHT_VELOCITY = 0.30
    WEIGHT_FRESHNESS = 0.25
    WEIGHT_CORROBORATION = 0.25
    WEIGHT_RELEVANCE = 0.20

    @classmethod
    def evaluate_state(
        cls,
        trending_score: float,
        velocity: float,
        freshness: float,
        article_count: int,
        source_count: int,
    ) -> str:
        """Determines the story cluster's lifecycle state based on measurable signals.
        Possible states: EMERGING, RISING, TRENDING, PEAK, COOLING, STALE.
        Allows bidirectional transitions (e.g. from PEAK to COOLING, or COOLING back to RISING if new coverage arrives).
        """
        if freshness <= 10.0:
            return "STALE"

        if trending_score >= 80.0 and velocity >= 60.0 and source_count >= 2:
            return "PEAK"

        if trending_score >= 65.0 and article_count >= 2:
            return "TRENDING"

        if freshness <= 35.0 and velocity <= 20.0:
            return "COOLING"

        if trending_score >= 45.0 or velocity >= 30.0:
            return "RISING"

        return "EMERGING"

    @classmethod
    def score_cluster(cls, db: Session, cluster: StoryCluster) -> StoryCluster:
        """Computes all score components, updates cluster record, and evaluates state."""
        # 1. Component scores
        velocity = VelocityEngine.calculate_velocity(db, cluster)
        freshness = FreshnessEngine.calculate_freshness(cluster.last_seen_at)
        corroboration, label, source_count = CorroborationEngine.calculate_corroboration(db, cluster)
        relevance = RelevanceEngine.calculate_relevance(db, cluster)

        # 2. Weighted formula
        raw_trending = (
            (velocity * cls.WEIGHT_VELOCITY) +
            (freshness * cls.WEIGHT_FRESHNESS) +
            (corroboration * cls.WEIGHT_CORROBORATION) +
            (relevance * cls.WEIGHT_RELEVANCE)
        )
        trending = round(min(100.0, max(0.0, raw_trending)), 2)

        # 3. Article count
        article_count = len(cluster.cluster_articles)

        # 4. State evaluation
        new_state = cls.evaluate_state(
            trending_score=trending,
            velocity=velocity,
            freshness=freshness,
            article_count=article_count,
            source_count=source_count,
        )

        # 5. Persist updates
        cluster.velocity_score = velocity
        cluster.freshness_score = freshness
        cluster.corroboration_score = corroboration
        cluster.relevance_score = relevance
        cluster.trending_score = trending
        cluster.article_count = article_count
        cluster.source_count = source_count
        cluster.status = new_state

        breakdown = {
            "formula": "velocity * 0.30 + freshness * 0.25 + corroboration * 0.25 + relevance * 0.20",
            "weights": {
                "velocity": cls.WEIGHT_VELOCITY,
                "freshness": cls.WEIGHT_FRESHNESS,
                "corroboration": cls.WEIGHT_CORROBORATION,
                "relevance": cls.WEIGHT_RELEVANCE,
            },
            "components": {
                "velocity": velocity,
                "freshness": freshness,
                "corroboration": corroboration,
                "relevance": relevance,
            },
            "corroboration_label": label,
            "state": new_state,
        }
        cluster.scoring_metadata = json.dumps(breakdown)

        db.commit()
        db.refresh(cluster)
        return cluster
