"""Zara Intent Classifier.

Classifies user requests with Gemini before the main LLM call.

Public API:
    Intent, ClassificationResult  -- domain model
    IntentClassifier              -- Gemini-backed classifier
    classify_intent               -- convenience function
    IntentConfig                  -- env-driven configuration
"""
from intent.classifier import IntentClassifier, classify_intent, get_classifier
from intent.config import IntentConfig
from intent.models import ClassificationResult, Intent
from intent.exceptions import (
    IntentError,
    IntentClassificationError,
    IntentConfigError,
)

__all__ = [
    "Intent",
    "ClassificationResult",
    "IntentConfig",
    "IntentClassifier",
    "classify_intent",
    "get_classifier",
    "IntentError",
    "IntentClassificationError",
    "IntentConfigError",
]
