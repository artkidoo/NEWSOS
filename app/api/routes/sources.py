"""Sources Management API Routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.source_repo import SourceRepository
from app.schemas.source import SourceCreate, SourceResponse, SourceUpdate

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceResponse])
def list_sources(
    enabled_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    repo = SourceRepository(db)
    return repo.list_sources(enabled_only=enabled_only, skip=skip, limit=limit)


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(source_in: SourceCreate, db: Session = Depends(get_db)):
    repo = SourceRepository(db)
    existing = repo.get_by_feed_url(source_in.feed_url)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source with feed URL '{source_in.feed_url}' already exists.",
        )
    return repo.create(source_in)


@router.get("/{source_id}", response_model=SourceResponse)
def get_source(source_id: int, db: Session = Depends(get_db)):
    repo = SourceRepository(db)
    source = repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return source


@router.put("/{source_id}", response_model=SourceResponse)
def update_source(source_id: int, source_in: SourceUpdate, db: Session = Depends(get_db)):
    repo = SourceRepository(db)
    source = repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return repo.update(source, source_in)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    repo = SourceRepository(db)
    if not repo.delete(source_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
