"""SQLAlchemy models for Phase 3 AI Editorial Desk.

Tables:
- editorial_drafts: generated editorial artifacts (article/summary/social/package).
- editorial_generations: immutable generation audit/history records.
- editorial_draft_sources: source provenance links between drafts and evidence.

Provenance is never removed: every draft keeps explicit links to the original
articles and publishers that contributed evidence, plus the generation record
(provider, model, prompt version, context hash, output hash, latency).
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EditorialDraft(Base):
    """AI-generated editorial artifact requiring human review before publication."""

    __tablename__ = "editorial_drafts"

    id = Column(Integer, primary_key=True, index=True)
    story_cluster_id = Column(
        Integer, ForeignKey("story_clusters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    draft_type = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="GENERATED", index=True)

    title = Column(String(512), nullable=True)
    body = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    dek = Column(Text, nullable=True)
    editorial_angle = Column(String(128), nullable=True)
    tone = Column(String(64), nullable=True)
    target_platform = Column(String(64), nullable=True)
    language = Column(String(10), nullable=False, default="en")

    # Structured JSON payloads (list of headline candidates, package contents).
    payload_json = Column(Text, nullable=True)

    quality_score = Column(Integer, nullable=True)
    confidence_score = Column(Integer, nullable=True)
    quality_breakdown_json = Column(Text, nullable=True)
    risk_flags_json = Column(Text, nullable=True)

    generation_id = Column(
        Integer, ForeignKey("editorial_generations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    generated_at = Column(DateTime, nullable=False, default=_utcnow)

    cluster = relationship("StoryCluster", back_populates="drafts")
    generation = relationship("EditorialGeneration", back_populates="drafts")
    draft_sources = relationship(
        "EditorialDraftSource", back_populates="draft", cascade="all, delete-orphan"
    )


class EditorialGeneration(Base):
    """Immutable audit record of one AI generation request/response cycle.

    Historical generation evidence is never overwritten; regeneration always
    creates a new record. Secrets/API keys are never stored here.
    """

    __tablename__ = "editorial_generations"

    id = Column(Integer, primary_key=True, index=True)
    story_cluster_id = Column(
        Integer, ForeignKey("story_clusters.id", ondelete="CASCADE"), nullable=False, index=True
    )

    provider = Column(String(64), nullable=False)
    model = Column(String(128), nullable=False)
    prompt_version = Column(String(64), nullable=False)
    generation_type = Column(String(32), nullable=False, index=True)

    input_context_hash = Column(String(64), nullable=False, index=True)
    output_hash = Column(String(64), nullable=True)
    raw_response = Column(Text, nullable=True)

    latency_ms = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)

    success = Column(Integer, nullable=False, default=1)
    error_code = Column(String(64), nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)

    cluster = relationship("StoryCluster", back_populates="generations")
    drafts = relationship("EditorialDraft", back_populates="generation")


class EditorialDraftSource(Base):
    """Source provenance: which original article/publisher contributed to a draft."""

    __tablename__ = "editorial_draft_sources"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(
        Integer, ForeignKey("editorial_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    relevance = Column(Integer, nullable=False, default=0)
    citation_role = Column(String(64), nullable=False, default="evidence")
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    draft = relationship("EditorialDraft", back_populates="draft_sources")
    article = relationship("Article")
    source = relationship("Source")
