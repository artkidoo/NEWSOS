"""Phase 3: Deterministic Editorial Research Context Engine.

Builds a bounded, reproducible evidence package from a story cluster BEFORE any
AI generation occurs. The application — never the LLM — decides which sources
exist. Identical database state produces an identical context (and therefore an
identical SHA-256 context hash), enabling idempotent, auditable generation.

Sections:
- story: cluster identity + intelligence scores + lifecycle state
- articles: bounded, deterministically ordered evidence with provenance
- entities: recognized people/organizations/locations/etc.
- intelligence: velocity/freshness/corroboration/relevance/trending/state
- provenance: explicit source-article/publisher inventory + conflict detection
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.article import Article
from app.models.intelligence import Entity, StoryCluster, StoryClusterArticle, StoryClusterEntity
from app.models.source import Source

# Entities that materially affect factual claims; used by the fact guard.
FACTUAL_ENTITY_TYPES = {
    "person",
    "organization",
    "location",
    "country",
    "city",
    "brand",
    "event",
    "product",
    "artist",
    "sports_team",
}


@dataclass
class ResearchContext:
    """Reproducible evidence bundle supplied to editorial generation."""

    story: dict[str, Any]
    articles: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    intelligence: dict[str, Any]
    provenance: dict[str, Any]
    conflicts: list[dict[str, Any]]
    context_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "story": self.story,
            "articles": self.articles,
            "entities": self.entities,
            "intelligence": self.intelligence,
            "provenance": self.provenance,
            "conflicts": self.conflicts,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"), default=str)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _excerpt(article: Article, limit: int) -> str:
    base = (article.content or article.summary or article.title or "").strip()
    return base[:limit]


def detect_conflicts(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic heuristic conflict detection across evidence.

    Two articles reporting the same story but asserting materially different
    key numbers/dates are flagged CONFLICTING_SOURCES. The system preserves the
    conflict instead of silently choosing one version.
    """
    conflicts: list[dict[str, Any]] = []
    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            a, b = articles[i], articles[j]
            a_nums = set(a.get("numbers", []))
            b_nums = set(b.get("numbers", []))
            # Different numeric assertions and no shared numbers => potential conflict.
            if a_nums and b_nums and a_nums != b_nums and not (a_nums & b_nums):
                conflicts.append(
                    {
                        "type": "CONFLICTING_SOURCES",
                        "article_ids": [a["id"], b["id"]],
                        "publishers": [a["publisher"], b["publisher"]],
                        "detail": (
                            f"{a['publisher']} reports {sorted(a_nums)} while "
                            f"{b['publisher']} reports {sorted(b_nums)}"
                        ),
                    }
                )
    return conflicts


class ResearchContextEngine:
    """Constructs deterministic research contexts from persisted intelligence."""

    def __init__(self, db: Session, *, max_articles: int | None = None, max_content_chars: int | None = None):
        self.db = db
        settings = get_settings()
        self.max_articles = max_articles if max_articles is not None else settings.EDITORIAL_MAX_ARTICLES
        self.max_content_chars = (
            max_content_chars if max_content_chars is not None else settings.EDITORIAL_MAX_CONTENT_CHARS
        )

    def build(self, story_cluster_id: int) -> ResearchContext:
        cluster = self.db.get(StoryCluster, story_cluster_id)
        if cluster is None:
            raise LookupError(f"Story cluster {story_cluster_id} not found.")

        story = {
            "cluster_id": cluster.id,
            "cluster_title": cluster.canonical_title,
            "category": cluster.category,
            "state": cluster.status,
            "trending_score": round(float(cluster.trending_score), 2),
            "first_seen": cluster.first_seen_at.isoformat(),
            "last_seen": cluster.last_seen_at.isoformat(),
            "article_count": cluster.article_count,
            "source_count": cluster.source_count,
        }

        # Deterministic ordering: published_at DESC, then id ASC as tiebreaker.
        links = (
            self.db.query(StoryClusterArticle, Article, Source)
            .join(Article, Article.id == StoryClusterArticle.article_id)
            .join(Source, Source.id == Article.source_id)
            .filter(StoryClusterArticle.story_cluster_id == cluster.id)
            .order_by(Article.published_at.desc(), Article.id.asc())
            .all()
        )

        articles: list[dict[str, Any]] = []
        for link, art, src in links[: self.max_articles]:
            excerpt = _excerpt(art, self.max_content_chars)
            articles.append(
                {
                    "id": art.id,
                    "title": art.title,
                    "excerpt": excerpt,
                    "source_id": src.id,
                    "publisher": src.name,
                    "publisher_trust": src.trust_level.value,
                    "published_at": art.published_at.isoformat(),
                    "canonical_url": art.canonical_url,
                    "similarity_score": round(float(link.similarity_score), 4),
                    "numbers": _extract_numbers(excerpt + " " + art.title),
                    "dates": _extract_dates(excerpt + " " + art.title),
                }
            )

        entity_links = (
            self.db.query(StoryClusterEntity, Entity)
            .join(Entity, Entity.id == StoryClusterEntity.entity_id)
            .filter(StoryClusterEntity.story_cluster_id == cluster.id)
            .order_by(StoryClusterEntity.mention_count.desc(), Entity.id.asc())
            .all()
        )
        entities = [
            {
                "id": ent.id,
                "name": ent.name,
                "normalized_name": ent.normalized_name,
                "entity_type": ent.entity_type,
                "mention_count": link.mention_count,
            }
            for link, ent in entity_links
        ]

        intelligence = {
            "velocity": round(float(cluster.velocity_score), 2),
            "freshness": round(float(cluster.freshness_score), 2),
            "corroboration": round(float(cluster.corroboration_score), 2),
            "relevance": round(float(cluster.relevance_score), 2),
            "trending": round(float(cluster.trending_score), 2),
            "state": cluster.status,
        }

        publishers = sorted({a["publisher"] for a in articles})
        provenance = {
            "article_ids": [a["id"] for a in articles],
            "source_ids": sorted({a["source_id"] for a in articles}),
            "publishers": publishers,
            "urls": {a["id"]: a["canonical_url"] for a in articles},
            "policy": "The application selects all evidence; the model may not invent sources.",
        }

        conflicts = detect_conflicts(articles)

        ctx = ResearchContext(
            story=story,
            articles=articles,
            entities=entities,
            intelligence=intelligence,
            provenance=provenance,
            conflicts=conflicts,
            context_hash="",
        )
        ctx.context_hash = _sha256(ctx.canonical_json())
        return ctx


_NUMBER_PATTERN = re.compile(r"\b\d[\d,\.]*%?\b")
_DATE_PATTERN = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4}\b|"
    r"\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)


def _extract_numbers(text: str) -> list[str]:
    return sorted({m.group(0) for m in _NUMBER_PATTERN.finditer(text)})


def _extract_dates(text: str) -> list[str]:
    return sorted({m.group(0) for m in _DATE_PATTERN.finditer(text)})
