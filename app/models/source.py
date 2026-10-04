"""News Source SQLAlchemy Model."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import SourceType, TrustLevel


class Source(Base):
    """Source configuration entity representing an RSS/Atom/Syndicated outlet."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(1024), nullable=False)
    feed_url = Column(String(1024), nullable=False, unique=True, index=True)
    source_type = Column(Enum(SourceType), nullable=False, default=SourceType.RSS)
    category = Column(String(100), nullable=False, default="general", index=True)
    language = Column(String(10), nullable=False, default="en")
    country = Column(String(10), nullable=False, default="US")
    trust_level = Column(Enum(TrustLevel), nullable=False, default=TrustLevel.MEDIUM)
    enabled = Column(Boolean, nullable=False, default=True)
    last_fetched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    articles = relationship("Article", back_populates="source", cascade="all, delete-orphan")
    ingestion_runs = relationship("IngestionRun", back_populates="source", cascade="all, delete-orphan")
