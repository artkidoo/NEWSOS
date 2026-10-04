"""Ingestion Run Repository."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.enums import IngestionStatus
from app.models.ingestion_run import IngestionRun


class IngestionRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, source_id: int) -> IngestionRun:
        run = IngestionRun(
            source_id=source_id,
            status=IngestionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def complete(self, run_id: int, found: int, ingested: int, skipped: int) -> IngestionRun | None:
        run = self.db.query(IngestionRun).filter(IngestionRun.id == run_id).first()
        if run:
            run.status = IngestionStatus.COMPLETED
            run.articles_found = found
            run.articles_ingested = ingested
            run.articles_skipped = skipped
            run.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(run)
        return run

    def fail(self, run_id: int, error_message: str) -> IngestionRun | None:
        run = self.db.query(IngestionRun).filter(IngestionRun.id == run_id).first()
        if run:
            run.status = IngestionStatus.FAILED
            run.error_message = error_message
            run.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(run)
        return run

    def list_runs(self, source_id: int | None = None, limit: int = 50) -> list[IngestionRun]:
        query = self.db.query(IngestionRun)
        if source_id:
            query = query.filter(IngestionRun.source_id == source_id)
        return query.order_by(IngestionRun.started_at.desc()).limit(limit).all()
