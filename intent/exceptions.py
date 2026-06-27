"""Exception hierarchy for the intent classifier."""
from __future__ import annotations


class IntentError(Exception):
    """Base class for intent classifier errors."""


class IntentClassificationError(IntentError):
    """Raised when Gemini returns an unparseable classification."""


class IntentConfigError(IntentError):
    """Raised when required configuration is missing."""
