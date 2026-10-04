"""SQLAlchemy models for Phase 2 Story Intelligence and Trending Engine."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class StoryCluster(Base):
    """Represents a real-world story cluster derived from multiple normalized articles."""

    __tablename__ = "story_clusters"

    id = Column(Integer, primary_key=True, index=True)
    canonical_title = Column(String(512), nullable=False, index=True)
    summary = Column(Text, nullable=True)
    category = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="EMERGING", index=True)
    first_seen_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    last_seen_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    article_count = Column(Integer, nullable=False, default=0)
    source_count = Column(Integer, nullable=False, default=0)
    velocity_score = Column(Float, nullable=False, default=0.0)
    freshness_score = Column(Float, nullable=False, default=0.0)
    relevance_score = Column(Float, nullable=False, default=0.0)
    corroboration_score = Column(Float, nullable=False, default=0.0)
    trending_score = Column(Float, nullable=False, default=0.0, index=True)
    scoring_metadata = Column(Text, nullable=True)  # JSON-encoded scoring breakdown
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    cluster_articles = relationship("StoryClusterArticle", back_populates="cluster", cascade="all, delete-orphan")
    cluster_entities = relationship("StoryClusterEntity", back_populates="cluster", cascade="all, delete-orphan")


class StoryClusterArticle(Base):
    """Association table linking articles to story clusters with similarity and assignment metadata."""

    __tablename__ = "story_cluster_articles"

    story_cluster_id = Column(Integer, ForeignKey("story_clusters.id", ondelete="CASCADE"), primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True, unique=True)
    similarity_score = Column(Float, nullable=False, default=1.0)
    assignment_method = Column(String(32), nullable=False, default="lexical")
    assigned_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    cluster = relationship("StoryCluster", back_populates="cluster_articles")
    article = relationship("Article", back_populates="cluster_links")


class Entity(Base):
    """Extracted normalized named entities (person, organization, location, brand, etc.)."""

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    normalized_name = Column(String(256), nullable=False, unique=True, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    article_links = relationship("ArticleEntity", back_populates="entity", cascade="all, delete-orphan")
    cluster_links = relationship("StoryClusterEntity", back_populates="entity", cascade="all, delete-orphan")


class ArticleEntity(Base):
    """Association linking articles to extracted entities with confidence scoring."""

    __tablename__ = "article_entities"

    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    confidence = Column(Float, nullable=False, default=1.0)
    extraction_method = Column(String(64), nullable=False, default="deterministic_nlp")

    article = relationship("Article", back_populates="entities")
    entity = relationship("Entity", back_populates="article_links")


class StoryClusterEntity(Base):
    """Aggregated entity mentions across a story cluster."""

    __tablename__ = "story_cluster_entities"

    story_cluster_id = Column(Integer, ForeignKey("story_clusters.id", ondelete="CASCADE"), primary_key=True)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    mention_count = Column(Integer, nullable=False, default=1)

    cluster = relationship("StoryCluster", back_populates="cluster_entities")
    entity = relationship("Entity", back_populates="cluster_links")
