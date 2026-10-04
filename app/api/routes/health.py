"""Health and System Status API Route."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Verifies service responsiveness and database connectivity."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {exc!s}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "system": "NEWSROOM OS",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
