"""Deduplication Engine: Exact content hash, canonical URL, and title similarity checking."""

import re

from sqlalchemy.orm import Session

from app.models.article import Article


class Deduplicator:
    """Detects exact and near duplicates across incoming feeds and stored articles."""

    @staticmethod
    def tokenize(text: str) -> set[str]:
        """Extracts normalized word tokens for Jaccard similarity."""
        return set(re.findall(r"\b\w{3,}\b", text.lower()))

    @classmethod
    def calculate_similarity(cls, title_a: str, title_b: str) -> float:
        """Calculates Jaccard similarity coefficient between two titles."""
        tokens_a = cls.tokenize(title_a)
        tokens_b = cls.tokenize(title_b)
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a.intersection(tokens_b)
        union = tokens_a.union(tokens_b)
        return len(intersection) / len(union)

    @classmethod
    def check_duplicate(cls, db: Session, content_hash: str, canonical_url: str, title: str) -> tuple[bool, int | None]:
        """Checks if an article is an exact hash duplicate or canonical URL duplicate.
        Returns: (is_duplicate, duplicate_of_id)
        """
        # 1. Exact hash match
        existing_hash = db.query(Article).filter(Article.content_hash == content_hash).first()
        if existing_hash:
            return True, existing_hash.id

        # 2. Canonical URL match
        existing_url = db.query(Article).filter(Article.canonical_url == canonical_url).first()
        if existing_url:
            return True, existing_url.id

        # 3. High-threshold title similarity within recent articles (same title across different URLs)
        recent_candidates = db.query(Article).order_by(Article.id.desc()).limit(100).all()
        for candidate in recent_candidates:
            sim = cls.calculate_similarity(title, candidate.title)
            if sim >= 0.85:
                return True, candidate.id

        return False, None
