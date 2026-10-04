"""Custom application exceptions for NEWSROOM OS."""

from typing import Any


class NewsroomException(Exception):
    """Base exception class for Newsroom OS."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class FeedFetchError(NewsroomException):
    """Raised when fetching syndication feed fails."""


class ParseError(NewsroomException):
    """Raised when parsing XML/RSS/Atom feed fails."""


class NormalizationError(NewsroomException):
    """Raised when article normalization fails validation."""


class DuplicateArticleError(NewsroomException):
    """Raised when duplicate article is detected."""
