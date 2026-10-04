"""Structured logging configuration for NEWSROOM OS."""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configures root logger with clean stdout formatting."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Returns a named logger."""
    return logging.getLogger(name)
