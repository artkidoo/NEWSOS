"""Ingestion Orchestration Engine."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.article import Article
from app.models.source import Source
from app.repositories.ingestion_run_repo import IngestionRunRepository
from app.services.deduplication.deduplicator import Deduplicator
from app.services.discovery.feed_client import FeedClient
from app.services.discovery.feed_detector import FeedDetector
from app.services.normalization.normalizer import ArticleNormalizer

logger = get_logger(__name__)


class IngestionEngine:
    """Coordinates fetching, parsing, normalising, deduplicating, and persisting feed articles."""

    def __init__(self, db: Session, feed_client: FeedClient | None = None):
        self.db = db
        self.feed_client = feed_client or FeedClient()
        self.run_repo = IngestionRunRepository(db)

    def ingest_source(self, source: Source) -> dict[str, int]:
        """Ingests articles from a single source."""
        run = self.run_repo.create(source.id)
        found_count = 0
        ingested_count = 0
        skipped_count = 0

        try:
            raw_bytes = self.feed_client.fetch(source.feed_url)
            parsed_data = FeedDetector.parse(raw_bytes)
            entries: list[dict] = parsed_data.get("entries", [])
            found_count = len(entries)

            for raw_entry in entries:
                try:
                    norm_data = ArticleNormalizer.normalize(raw_entry, source.id)
                    is_dup, dup_of_id = Deduplicator.check_duplicate(
                        self.db,
                        norm_data["content_hash"],
                        norm_data["canonical_url"],
                        norm_data["title"],
                    )

                    if is_dup:
                        skipped_count += 1
                        continue

                    article = Article(
                        source_id=source.id,
                        title=norm_data["title"],
                        url=norm_data["url"],
                        canonical_url=norm_data["canonical_url"],
                        author=norm_data["author"],
                        published_at=norm_data["published_at"],
                        summary=norm_data["summary"],
                        content=norm_data["content"],
                        image_url=norm_data["image_url"],
                        category=norm_data["category"] or source.category,
                        content_hash=norm_data["content_hash"],
                        guid=norm_data["guid"],
                        language=norm_data["language"] or source.language,
                        is_duplicate=False,
                        duplicate_of_id=None,
                    )
                    self.db.add(article)
                    self.db.commit()
                    ingested_count += 1
                except Exception as norm_err:
                    logger.warning(f"Failed to process entry: {norm_err}")
                    skipped_count += 1
                    continue

            # Update source last_fetched_at
            source.last_fetched_at = datetime.now(timezone.utc)
            self.db.commit()

            self.run_repo.complete(run.id, found_count, ingested_count, skipped_count)
            return {"found": found_count, "ingested": ingested_count, "skipped": skipped_count}

        except Exception as exc:
            logger.error(f"Ingestion run failed for source {source.name}: {exc}")
            self.run_repo.fail(run.id, str(exc))
            return {"found": found_count, "ingested": ingested_count, "skipped": skipped_count, "error": str(exc)}
