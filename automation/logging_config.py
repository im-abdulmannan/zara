"""Centralised logging configuration for the automation package.

Keeping logging setup in one place avoids per-module duplication and lets the
log format/level be controlled from configuration rather than hardcoded at call
sites.
"""
from __future__ import annotations

import logging
import sys

LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


def resolve_level(level: str | int) -> int:
    """Translates a level name (e.g. ``"INFO"``) or int into a logging level.

    Falls back to :data:`logging.INFO` for unknown names.
    """
    if isinstance(level, int):
        return level
    return logging.getLevelName(str(level).upper()) if isinstance(
        logging.getLevelName(str(level).upper()), int
    ) else logging.INFO


def get_logger(name: str, level: str | int = logging.INFO) -> logging.Logger:
    """Returns a configured logger.

    A stream handler with the package format is attached exactly once so that
    repeated calls do not duplicate log lines. Propagation is disabled to avoid
    double logging through the root logger.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(resolve_level(level))
    return logger
