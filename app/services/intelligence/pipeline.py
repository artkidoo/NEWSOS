"""Story Intelligence Pipeline: Coordinates entity extraction, clustering, and trending scoring."""

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.article import Article
from app.models.intelligence import (
    ArticleEntity,
    Entity,
    StoryCluster,
    StoryClusterArticle,
    StoryClusterEntity,
)
from app.services.intelligence.clustering.engine import ClusteringEngine
from app.services.intelligence.entities.extractor import EntityExtractor
from app.services.intelligence.trending.engine import TrendingEngine

logger = get_logger(__name__)


class IntelligencePipeline:
    """End-to-end intelligence processor transforming normalized articles into scored story clusters."""

    def __init__(self, db: Session):
        self.db = db

    def extract_and_link_entities(self, article: Article) -> list[Entity]:
        """Extracts entities from article and creates idempotent links."""
        extracted = EntityExtractor.extract_entities(article.title, article.summary or "")
        linked_entities: list[Entity] = []

        for name, etype, conf in extracted:
            norm_name = EntityExtractor.normalize_name(name)
            if not norm_name:
                continue

            # Find or create entity idempotently
            entity = self.db.query(Entity).filter(Entity.normalized_name == norm_name).first()
            if not entity:
                entity = Entity(
                    name=name,
                    normalized_name=norm_name,
                    entity_type=etype,
                )
                self.db.add(entity)
                self.db.commit()
                self.db.refresh(entity)

            # Link entity to article idempotently
            link = (
                self.db.query(ArticleEntity)
                .filter(ArticleEntity.article_id == article.id, ArticleEntity.entity_id == entity.id)
                .first()
            )
            if not link:
                link = ArticleEntity(
                    article_id=article.id,
                    entity_id=entity.id,
                    confidence=conf,
                    extraction_method="deterministic_nlp",
                )
                self.db.add(link)
                self.db.commit()

            linked_entities.append(entity)

        return linked_entities

    def process_article(self, article: Article) -> StoryCluster:
        """Processes a single article through entity extraction, clustering, and cluster scoring."""
        # 1. Entity extraction
        entities = self.extract_and_link_entities(article)

        # 2. Check if article already assigned to a cluster (idempotency guard)
        existing_link = (
            self.db.query(StoryClusterArticle)
            .filter(StoryClusterArticle.article_id == article.id)
            .first()
        )

        cluster: StoryCluster
        if existing_link:
            cluster = existing_link.cluster
        else:
            # 3. Find candidate cluster or create new cluster
            best_cluster, sim_score = ClusteringEngine.find_best_cluster(self.db, article)
            if best_cluster:
                ClusteringEngine.assign_article_to_cluster(
                    self.db,
                    article=article,
                    cluster=best_cluster,
                    similarity_score=sim_score,
                    assignment_method="lexical",
                )
                cluster = best_cluster
            else:
                cluster = ClusteringEngine.create_cluster_for_article(self.db, article)

        # 4. Update cluster-entity mention counts idempotently
        for ent in entities:
            cluster_ent = (
                self.db.query(StoryClusterEntity)
                .filter(
                    StoryClusterEntity.story_cluster_id == cluster.id,
                    StoryClusterEntity.entity_id == ent.id,
                )
                .first()
            )
            if not cluster_ent:
                cluster_ent = StoryClusterEntity(
                    story_cluster_id=cluster.id,
                    entity_id=ent.id,
                    mention_count=1,
                )
                self.db.add(cluster_ent)
            else:
                cluster_ent.mention_count += 1
            self.db.commit()

        # 5. Score cluster
        TrendingEngine.score_cluster(self.db, cluster)
        return cluster

    def run_pipeline(self, limit: int = 200) -> dict[str, int]:
        """Runs the intelligence pipeline across all unassigned or recent articles."""
        articles = (
            self.db.query(Article)
            .filter(Article.is_duplicate == False)
            .order_by(Article.published_at.asc())
            .limit(limit)
            .all()
        )

        clusters_created = 0
        clusters_updated = 0
        affected_clusters = set()

        for article in articles:
            had_cluster = (
                self.db.query(StoryClusterArticle)
                .filter(StoryClusterArticle.article_id == article.id)
                .first()
                is not None
            )

            cluster = self.process_article(article)
            affected_clusters.add(cluster.id)

            if had_cluster:
                clusters_updated += 1
            else:
                clusters_created += 1

        # Rescore all affected clusters
        for cid in affected_clusters:
            cl = self.db.query(StoryCluster).filter(StoryCluster.id == cid).first()
            if cl:
                TrendingEngine.score_cluster(self.db, cl)

        return {
            "articles_evaluated": len(articles),
            "clusters_created": clusters_created,
            "clusters_updated": clusters_updated,
            "entities_extracted": self.db.query(Entity).count(),
            "clusters_scored": len(affected_clusters),
        }
