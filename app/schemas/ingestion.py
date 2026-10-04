"""Ingestion Run Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import IngestionStatus


class IngestionRunResponse(BaseModel):
    id: int
    source_id: int
    status: IngestionStatus
    articles_found: int
    articles_ingested: int
    articles_skipped: int
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class IngestionTriggerResponse(BaseModel):
    status: str
    message: str
    runs_triggered: int
