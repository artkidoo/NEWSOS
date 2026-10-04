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
