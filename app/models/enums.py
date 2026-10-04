"""Enumeration types for NEWSROOM OS domain models."""

import enum


class SourceType(str, enum.Enum):
    RSS = "rss"
    ATOM = "atom"
    JSON_FEED = "json_feed"
    CUSTOM = "custom"


class TrustLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StoryState(str, enum.Enum):
    EMERGING = "EMERGING"
    RISING = "RISING"
    TRENDING = "TRENDING"
    PEAK = "PEAK"
    COOLING = "COOLING"
    STALE = "STALE"


class DraftType(str, enum.Enum):
    """Editorial draft artifact types supported by the AI Editorial Desk (Phase 3)."""

    ARTICLE = "ARTICLE"
    BREAKING = "BREAKING"
    NEWS_UPDATE = "NEWS_UPDATE"
    EXPLAINER = "EXPLAINER"
    SOCIAL_POST = "SOCIAL_POST"
    SHORT_CAPTION = "SHORT_CAPTION"


class DraftStatus(str, enum.Enum):
    """Phase 3 draft lifecycle states only.

    APPROVED / PUBLISHED states intentionally do NOT exist yet; they belong to
    Phase 4 (editorial control) and Phase 5 (publishing).
    """

    GENERATED = "GENERATED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REGENERATE = "REGENERATE"
    ARCHIVED = "ARCHIVED"


class GenerationType(str, enum.Enum):
    """Kinds of AI generation operations tracked in editorial_generations."""

    HEADLINES = "HEADLINES"
    SUMMARY = "SUMMARY"
    ARTICLE = "ARTICLE"
    SOCIAL = "SOCIAL"
    PACKAGE = "PACKAGE"


class RiskFlag(str, enum.Enum):
    """Deterministic fact/claim guard risk flags (guardrail, not a truth oracle)."""

    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    UNSUPPORTED_ENTITY = "UNSUPPORTED_ENTITY"
    UNSUPPORTED_NUMBER = "UNSUPPORTED_NUMBER"
    UNSUPPORTED_DATE = "UNSUPPORTED_DATE"
    UNSUPPORTED_QUOTE = "UNSUPPORTED_QUOTE"
    UNSUPPORTED_URL = "UNSUPPORTED_URL"
    MISSING_ATTRIBUTION = "MISSING_ATTRIBUTION"
    LOW_EVIDENCE = "LOW_EVIDENCE"
    CONFLICTING_SOURCES = "CONFLICTING_SOURCES"
