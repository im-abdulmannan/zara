"""Intent-based routing for Zara.

Maps classified intents to tool payloads so the assistant can dispatch
directly to the correct module without an LLM round-trip when confidence
is high and required entities are present.
"""
from router.intent_router import IntentRouter, reload_router, route_intent

__all__ = ["IntentRouter", "reload_router", "route_intent"]
