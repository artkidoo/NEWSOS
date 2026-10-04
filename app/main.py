"""Main FastAPI application entry point for NEWSROOM OS."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import all models to ensure metadata registration
import app.models.article
import app.models.ingestion_run
import app.models.intelligence
import app.models.source
from app.api.routes import articles, health, ingestion, intelligence, sources
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.session import engine

settings = get_settings()
setup_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables for development/testing if not migrated
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade news discovery, normalization, deduplication, and story intelligence system.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router)
app.include_router(sources.router, prefix="/api")
app.include_router(articles.router, prefix="/api")
app.include_router(ingestion.router, prefix="/api")
app.include_router(intelligence.router, prefix="/api")


@app.get("/")
def root():
    return {
        "service": settings.APP_NAME,
        "version": "0.2.0",
        "docs_url": "/docs",
        "health_url": "/health",
    }
