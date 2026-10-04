"""Ingestion Polling and Runs API Routes."""


from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.source import Source
from app.repositories.ingestion_run_repo import IngestionRunRepository
from app.schemas.ingestion import IngestionRunResponse, IngestionTriggerResponse
from app.services.ingestion.engine import IngestionEngine

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/trigger", response_model=IngestionTriggerResponse)
def trigger_ingestion(source_id: int | None = None, db: Session = Depends(get_db)):
    """Triggers feed polling and normalization for a specific source or all enabled sources."""
    engine = IngestionEngine(db)
    if source_id:
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
        sources = [source]
    else:
        sources = db.query(Source).filter(Source.enabled == True).all()

    for s in sources:
        engine.ingest_source(s)

    return IngestionTriggerResponse(
        status="success",
        message=f"Ingestion completed for {len(sources)} source(s).",
        runs_triggered=len(sources),
    )


@router.get("/runs", response_model=list[IngestionRunResponse])
def list_ingestion_runs(
    source_id: int | None = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    repo = IngestionRunRepository(db)
    return repo.list_runs(source_id=source_id, limit=limit)
