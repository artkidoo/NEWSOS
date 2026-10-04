"""Relevance Engine: Evaluates category priority, entity prominence, and editorial topic weighting."""

from sqlalchemy.orm import Session

from app.models.intelligence import StoryCluster, StoryClusterEntity


class RelevanceEngine:
    """Calculates editorial and topical relevance (0.0 to 100.0)."""

    CATEGORY_WEIGHTS: dict[str, float] = {
        "world": 85.0,
        "politics": 85.0,
        "business": 80.0,
        "technology": 80.0,
        "science": 75.0,
        "health": 75.0,
        "diplomacy": 85.0,
        "robotics": 80.0,
        "entertainment": 60.0,
        "sports": 60.0,
        "general": 50.0,
    }

    @classmethod
    def calculate_relevance(cls, db: Session, cluster: StoryCluster) -> float:
        """Calculates normalized relevance score (0-100)."""
        category_base = cls.CATEGORY_WEIGHTS.get(cluster.category.lower(), 50.0)

        # Count linked distinct entities
        entity_count = (
            db.query(StoryClusterEntity)
            .filter(StoryClusterEntity.story_cluster_id == cluster.id)
            .count()
        )

        # Entity bonus: up to 15 points for stories with multiple recognized entities
        entity_bonus = min(15.0, entity_count * 3.0)

        raw_score = category_base + entity_bonus
        return round(min(100.0, max(0.0, raw_score)), 2)
