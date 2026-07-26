"""Compatibility shim — prefer ProviderPanel / IntentPanel."""
from __future__ import annotations

from ui.provider_panel import ProviderPanel

# Older imports still resolve.
LlmSettingsPanel = ProviderPanel

__all__ = ["LlmSettingsPanel", "ProviderPanel"]
