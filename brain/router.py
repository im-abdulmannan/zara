"""Intent routing facade for the brain layer."""
from __future__ import annotations

from router import route_intent
from router.intent_router import IntentRouter

__all__ = ["route_intent", "IntentRouter"]
