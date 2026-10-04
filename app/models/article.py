"""Article SQLAlchemy Model."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Article(Base):
    """Normalized news article entity with deduplication hashes."""

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(512), nullable=False, index=True)
    url = Column(String(1024), nullable=False)
    canonical_url = Column(String(1024), nullable=False, index=True)
    author = Column(String(255), nullable=True)
    published_at = Column(DateTime, nullable=False, index=True)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    image_url = Column(String(1024), nullable=True)
    category = Column(String(100), nullable=True, index=True)
    language = Column(String(10), nullable=False, default="en")

    # Deduplication and provenance fields
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    simhash = Column(String(64), nullable=True, index=True)
    guid = Column(String(512), nullable=True, index=True)
    is_duplicate = Column(Boolean, nullable=False, default=False, index=True)
    duplicate_of_id = Column(Integer, ForeignKey("articles.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    source = relationship("Source", back_populates="articles")
    entities = relationship("ArticleEntity", back_populates="article", cascade="all, delete-orphan")
    cluster_links = relationship("StoryClusterArticle", back_populates="article", cascade="all, delete-orphan")
