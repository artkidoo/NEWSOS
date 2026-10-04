"""Ingestion Run Audit SQLAlchemy Model."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import IngestionStatus


class IngestionRun(Base):
    """Audit run record tracking feed polling, articles ingested, and error logs."""

    __tablename__ = "ingestion_runs"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(IngestionStatus), nullable=False, default=IngestionStatus.PENDING)
    articles_found = Column(Integer, nullable=False, default=0)
    articles_ingested = Column(Integer, nullable=False, default=0)
    articles_skipped = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    source = relationship("Source", back_populates="ingestion_runs")
