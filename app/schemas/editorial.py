"""Pydantic schemas for Phase 3 AI Editorial Desk."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DraftSourceItem(BaseModel):
    id: int
    draft_id: int
    article_id: int
    source_id: int
    relevance: int
    citation_role: str
    article_title: str | None = None
    publisher: str | None = None
    canonical_url: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class EditorialDraftResponse(BaseModel):
    id: int
    story_cluster_id: int
    draft_type: str
    status: str
    title: str | None = None
    body: str | None = None
    summary: str | None = None
    dek: str | None = None
    editorial_angle: str | None = None
    tone: str | None = None
    target_platform: str | None = None
    language: str
    quality_score: int | None = None
    confidence_score: int | None = None
    risk_flags: list[str] = []
    quality_breakdown: dict[str, Any] = {}
    payload: dict[str, Any] = {}
    generation_id: int | None = None
    requires_human_review: bool = True
    created_at: datetime
    updated_at: datetime
    generated_at: datetime
    sources: list[DraftSourceItem] = []


class EditorialGenerationResponse(BaseModel):
    id: int
    story_cluster_id: int
    provider: str
    model: str
    prompt_version: str
    generation_type: str
    input_context_hash: str
    output_hash: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    success: int
    error_code: str | None = None
    created_at: datetime
    draft_ids: list[int] = []

    class Config:
        from_attributes = True


class GenerateRequestOptions(BaseModel):
    """Optional body for generate endpoints."""

    force: bool = Field(False, description="Explicit regeneration; bypasses idempotent reuse.")
    tone: str | None = None
    target_platform: str | None = None
    language: str | None = None


class GenerationEnvelope(BaseModel):
    """Response returned by every /generate/* endpoint."""

    draft_id: int
    story_id: int
    generation_id: int | None = None
    generation_type: str
    draft_type: str
    status: str
    reused_existing_generation: bool = False
    is_demo_output: bool = False
    requires_human_review: bool = True
    payload: dict[str, Any] = {}
    package: dict[str, Any] = {}
    quality_breakdown: dict[str, Any] = {}
    risk_flags: list[str] = []
    sources: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    generated_at: str
    regenerated_from_draft_id: int | None = None


class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
