"""Corroboration Engine: Calculates multi-source corroboration score and source diversity."""

from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.enums import TrustLevel
from app.models.intelligence import StoryCluster, StoryClusterArticle
from app.models.source import Source


class CorroborationEngine:
    """Calculates corroboration metrics based on distinct publisher verification and trust tiers.
    NOTE: Corroboration measures reporting breadth across independent outlets, NEVER absolute truth.
    """

    TRUST_WEIGHTS = {
        TrustLevel.LOW: 0.5,
        TrustLevel.MEDIUM: 1.0,
        TrustLevel.HIGH: 1.5,
        TrustLevel.VERIFIED: 2.0,
    }

    @classmethod
    def calculate_corroboration(cls, db: Session, cluster: StoryCluster) -> tuple[float, str, int]:
        """Calculates corroboration score (0-100) and human-readable corroboration label.
        Returns: (corroboration_score, label, distinct_source_count)
        """
        # Retrieve all distinct sources reporting on this cluster
        articles_with_sources = (
            db.query(Article.source_id, Source.trust_level)
            .join(StoryClusterArticle, StoryClusterArticle.article_id == Article.id)
            .join(Source, Source.id == Article.source_id)
            .filter(StoryClusterArticle.story_cluster_id == cluster.id)
            .all()
        )

        if not articles_with_sources:
            return 0.0, "Reported by 0 sources", 0

        # Group by distinct source ID
        source_trust_map: dict[int, TrustLevel] = {}
        for source_id, trust_level in articles_with_sources:
            source_trust_map[source_id] = trust_level

        distinct_sources = len(source_trust_map)

        # Calculate weighted trust sum
        weighted_sum = sum(cls.TRUST_WEIGHTS.get(tl, 1.0) for tl in source_trust_map.values())

        # Corroboration curve:
        # 1 source: 15-25
        # 2 sources: 40-55
        # 3 sources: 65-75
        # 4+ sources: 80-100
        raw_score = (weighted_sum / 5.0) * 100.0
        score = min(100.0, max(10.0, raw_score))

        label = f"Reported by {distinct_sources} independent {'source' if distinct_sources == 1 else 'sources'}"
        return round(score, 2), label, distinct_sources
