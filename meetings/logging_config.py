"""Centralised logging helpers for the meetings package."""
from __future__ import annotations

import logging
import sys

LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


def resolve_level(level: str | int) -> int:
    """Resolve a logging level name or integer.

    Unknown values fall back to :data:`logging.INFO`.
    """
    if isinstance(level, int):
        return level

    resolved = logging.getLevelName(str(level).upper())
    return resolved if isinstance(resolved, int) else logging.INFO


def get_logger(name: str, level: str | int = logging.INFO) -> logging.Logger:
    """Return a configured package logger without duplicate handlers."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(resolve_level(level))
    return logger
