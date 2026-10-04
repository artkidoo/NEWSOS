"""Story Clustering Engine with bounded candidate search and anti-spurious entity clustering."""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.intelligence import StoryCluster, StoryClusterArticle


class ClusteringEngine:
    """Groups articles reporting on the same underlying real-world event into StoryClusters."""

    # Default candidate search window in hours (bounded candidate search, not O(N^2))
    CANDIDATE_WINDOW_HOURS = 48
    SIMILARITY_THRESHOLD = 0.35

    COMMON_STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with",
        "by", "from", "up", "about", "into", "over", "after", "its", "it", "this",
        "that", "says", "said", "will", "would", "could", "should", "as", "is",
        "are", "was", "were", "has", "have", "had", "been", "news", "report", "update",
        "new", "amid", "first", "watch", "live", "amidst", "following", "during",
    }

    @classmethod
    def extract_informative_tokens(cls, title: str) -> set[str]:
        """Extracts stem/lemmatized lower-case alphanumeric tokens excluding generic words."""
        words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", title.lower())
        return {w for w in words if w not in cls.COMMON_STOPWORDS}

    @classmethod
    def calculate_lexical_similarity(cls, title_a: str, title_b: str) -> float:
        """Calculates Jaccard similarity across informative tokens."""
        tokens_a = cls.extract_informative_tokens(title_a)
        tokens_b = cls.extract_informative_tokens(title_b)
        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a.intersection(tokens_b)
        union = tokens_a.union(tokens_b)

        # Requirement 8: Anti-spurious clustering:
        # If intersection only has 1 word (e.g. only "apple" or only "artist"),
        # and union is large, it should not cluster.
        if len(intersection) <= 1 and len(union) >= 4:
            return 0.0

        return len(intersection) / len(union)

    @classmethod
    def find_best_cluster(
        cls,
        db: Session,
        article: Article,
        window_hours: int = CANDIDATE_WINDOW_HOURS,
        threshold: float = SIMILARITY_THRESHOLD,
    ) -> tuple[StoryCluster | None, float]:
        """Finds the most similar existing StoryCluster within the time window and category.
        Bounded candidate query: category filter + last_seen_at >= window_hours limit.
        """
        min_time = article.published_at - timedelta(hours=window_hours)
        max_time = article.published_at + timedelta(hours=window_hours)

        candidate_query = db.query(StoryCluster).filter(
            StoryCluster.last_seen_at >= min_time,
            StoryCluster.first_seen_at <= max_time,
        )

        # Category match constraint: articles in completely different categories don't cluster
        if article.category and article.category != "general":
            candidate_query = candidate_query.filter(
                (StoryCluster.category == article.category) | (StoryCluster.category == "general")
            )

        candidates: list[StoryCluster] = candidate_query.order_by(StoryCluster.last_seen_at.desc()).limit(50).all()

        best_cluster: StoryCluster | None = None
        best_score: float = 0.0

        for cluster in candidates:
            # Compare article title with cluster canonical title
            sim = cls.calculate_lexical_similarity(article.title, cluster.canonical_title)
            if sim > best_score:
                best_score = sim
                best_cluster = cluster

        if best_cluster and best_score >= threshold:
            return best_cluster, best_score

        return None, 0.0

    @classmethod
    def assign_article_to_cluster(
        cls,
        db: Session,
        article: Article,
        cluster: StoryCluster,
        similarity_score: float,
        assignment_method: str = "lexical",
    ) -> StoryClusterArticle:
        """Associates an article with an existing cluster and updates cluster bounds."""
        link = db.query(StoryClusterArticle).filter(StoryClusterArticle.article_id == article.id).first()
        if not link:
            link = StoryClusterArticle(
                story_cluster_id=cluster.id,
                article_id=article.id,
                similarity_score=similarity_score,
                assignment_method=assignment_method,
                assigned_at=datetime.now(timezone.utc),
            )
            db.add(link)

        # Update cluster time bounds
        cluster.first_seen_at = min(cluster.first_seen_at, article.published_at)
        cluster.last_seen_at = max(cluster.last_seen_at, article.published_at)

        db.commit()
        return link

    @classmethod
    def create_cluster_for_article(
        cls,
        db: Session,
        article: Article,
    ) -> StoryCluster:
        """Initializes a new StoryCluster seeded with the primary article."""
        cluster = StoryCluster(
            canonical_title=article.title,
            summary=article.summary,
            category=article.category or "general",
            status="EMERGING",
            first_seen_at=article.published_at,
            last_seen_at=article.published_at,
            article_count=1,
            source_count=1,
            velocity_score=0.0,
            freshness_score=100.0,
            relevance_score=50.0,
            corroboration_score=20.0,
            trending_score=25.0,
        )
        db.add(cluster)
        db.commit()
        db.refresh(cluster)

        # Link article
        link = StoryClusterArticle(
            story_cluster_id=cluster.id,
            article_id=article.id,
            similarity_score=1.0,
            assignment_method="seed",
            assigned_at=datetime.now(timezone.utc),
        )
        db.add(link)
        db.commit()
        return cluster
