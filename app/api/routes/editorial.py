"""Phase 3 Editorial Draft API routes.

Mounted under /api/editorial. These endpoints generate and inspect editorial
material only. There are deliberately NO publish, schedule, or approval
endpoints — those belong to later phases.

Security notes:
- No provider credentials, prompts, or secrets are ever returned.
- AI output is treated as untrusted text; the frontend renders it as plain text.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.editorial import EditorialDraft, EditorialGeneration
from app.schemas.editorial import (
    DraftSourceItem,
    EditorialDraftResponse,
    EditorialGenerationResponse,
    GenerateRequestOptions,
    GenerationEnvelope,
)
from app.services.editorial.generator import (
    DraftNotFoundError,
    EditorialGenerationService,
    GenerationError,
    StoryNotFoundError,
)

router = APIRouter(prefix="/editorial", tags=["editorial"])


def _service(db: Session = Depends(get_db)) -> EditorialGenerationService:
    return EditorialGenerationService(db)


def _map_generation_error(exc: GenerationError) -> HTTPException:
    code = exc.error_code or "GENERATION_FAILED"
    http_status = status.HTTP_504_GATEWAY_TIMEOUT if code == "AI_TIMEOUT" else status.HTTP_502_BAD_GATEWAY
    return HTTPException(status_code=http_status, detail={"detail": exc.message, "error_code": code})


def _draft_to_response(draft: EditorialDraft) -> EditorialDraftResponse:
    sources: list[DraftSourceItem] = []
    for link in draft.draft_sources:
        article = link.article
        publisher_name = link.source.name if link.source else None
        sources.append(
            DraftSourceItem(
                id=link.id,
                draft_id=link.draft_id,
                article_id=link.article_id,
                source_id=link.source_id,
                relevance=link.relevance,
                citation_role=link.citation_role,
                article_title=article.title if article else None,
                publisher=publisher_name,
                canonical_url=article.canonical_url if article else None,
                created_at=link.created_at,
            )
        )
    return EditorialDraftResponse(
        id=draft.id,
        story_cluster_id=draft.story_cluster_id,
        draft_type=draft.draft_type,
        status=draft.status,
        title=draft.title,
        body=draft.body,
        summary=draft.summary,
        dek=draft.dek,
        editorial_angle=draft.editorial_angle,
        tone=draft.tone,
        target_platform=draft.target_platform,
        language=draft.language,
        quality_score=draft.quality_score,
        confidence_score=draft.confidence_score,
        risk_flags=json.loads(draft.risk_flags_json or "[]"),
        quality_breakdown=json.loads(draft.quality_breakdown_json or "{}"),
        payload=json.loads(draft.payload_json or "{}"),
        generation_id=draft.generation_id,
        requires_human_review=True,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        generated_at=draft.generated_at,
        sources=sources,
    )


def _envelope(result: dict[str, Any]) -> GenerationEnvelope:
    return GenerationEnvelope(**result)


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------


@router.get("/drafts", response_model=list[EditorialDraftResponse])
def list_drafts(
    story_id: int | None = Query(None, ge=1),
    draft_type: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List editorial drafts (newest first). Read-only listing."""
    query = db.query(EditorialDraft)
    if story_id is not None:
        query = query.filter(EditorialDraft.story_cluster_id == story_id)
    if draft_type:
        query = query.filter(EditorialDraft.draft_type == draft_type.upper())
    if status_filter:
        query = query.filter(EditorialDraft.status == status_filter.upper())
    drafts = query.order_by(EditorialDraft.created_at.desc(), EditorialDraft.id.desc()).offset(skip).limit(limit).all()
    return [_draft_to_response(d) for d in drafts]


@router.get("/drafts/{draft_id}", response_model=EditorialDraftResponse)
def get_draft(draft_id: int, db: Session = Depends(get_db)):
    """Fetch one draft including full source provenance."""
    draft = db.get(EditorialDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Editorial draft {draft_id} not found.")
    return _draft_to_response(draft)


# ---------------------------------------------------------------------------
# Generation endpoints
# ---------------------------------------------------------------------------


@router.post("/generate/headlines/{story_id}", response_model=GenerationEnvelope)
def generate_headlines(story_id: int, options: GenerateRequestOptions | None = None, svc: EditorialGenerationService = Depends(_service)):
    """Generate up to 5 evidence-supported headline candidates."""
    return _run(lambda: svc.generate_headlines(story_id, force=bool(options and options.force)))


@router.post("/generate/summary/{story_id}", response_model=GenerationEnvelope)
def generate_summary(story_id: int, options: GenerateRequestOptions | None = None, svc: EditorialGenerationService = Depends(_service)):
    """Generate an evidence-bounded summary with key facts."""
    return _run(lambda: svc.generate_summary(story_id, force=bool(options and options.force)))


@router.post("/generate/article/{story_id}", response_model=GenerationEnvelope)
def generate_article(story_id: int, options: GenerateRequestOptions | None = None, svc: EditorialGenerationService = Depends(_service)):
    """Generate a structured editorial article draft."""
    return _run(lambda: svc.generate_article(story_id, force=bool(options and options.force)))


@router.post("/generate/social/{story_id}", response_model=GenerationEnvelope)
def generate_social(story_id: int, options: GenerateRequestOptions | None = None, svc: EditorialGenerationService = Depends(_service)):
    """Generate short-form editorial social copy (generation only — never publishing)."""
    return _run(lambda: svc.generate_social(story_id, force=bool(options and options.force)))


@router.post("/generate/package/{story_id}", response_model=GenerationEnvelope)
def generate_package(story_id: int, options: GenerateRequestOptions | None = None, svc: EditorialGenerationService = Depends(_service)):
    """Generate the complete editorial package for a story cluster."""
    return _run(lambda: svc.generate_package(story_id, force=bool(options and options.force)))


@router.post("/drafts/{draft_id}/regenerate", response_model=GenerationEnvelope)
def regenerate_draft(draft_id: int, svc: EditorialGenerationService = Depends(_service)):
    """Explicit regeneration: always creates a new generation record."""
    return _run(lambda: svc.regenerate_draft(draft_id))


def _run(fn) -> GenerationEnvelope:
    try:
        return _envelope(fn())
    except StoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DraftNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GenerationError as exc:
        raise _map_generation_error(exc) from exc


# ---------------------------------------------------------------------------
# Generation history
# ---------------------------------------------------------------------------


@router.get("/generations", response_model=list[EditorialGenerationResponse])
def list_generations(
    story_id: int | None = Query(None, ge=1),
    generation_type: str | None = None,
    success: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Audit trail of generation attempts (never includes prompts/secrets)."""
    query = db.query(EditorialGeneration)
    if story_id is not None:
        query = query.filter(EditorialGeneration.story_cluster_id == story_id)
    if generation_type:
        query = query.filter(EditorialGeneration.generation_type == generation_type.upper())
    if success is not None:
        query = query.filter(EditorialGeneration.success == (1 if success else 0))
    records = (
        query.order_by(EditorialGeneration.created_at.desc(), EditorialGeneration.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_generation_to_response(r, db) for r in records]


@router.get("/generations/{generation_id}", response_model=EditorialGenerationResponse)
def get_generation(generation_id: int, db: Session = Depends(get_db)):
    record = db.get(EditorialGeneration, generation_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Generation {generation_id} not found.")
    return _generation_to_response(record, db)


def _generation_to_response(record: EditorialGeneration, db: Session) -> EditorialGenerationResponse:
    draft_ids = [
        d.id
        for d in db.query(EditorialDraft).filter(EditorialDraft.generation_id == record.id).all()
    ]
    return EditorialGenerationResponse(
        id=record.id,
        story_cluster_id=record.story_cluster_id,
        provider=record.provider,
        model=record.model,
        prompt_version=record.prompt_version,
        generation_type=record.generation_type,
        input_context_hash=record.input_context_hash,
        output_hash=record.output_hash,
        latency_ms=record.latency_ms,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        success=record.success,
        error_code=record.error_code,
        created_at=record.created_at,
        draft_ids=draft_ids,
    )
