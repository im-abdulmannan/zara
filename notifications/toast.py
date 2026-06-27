"""Desktop (Windows toast) notification adapters.

A second delivery channel alongside voice. The :class:`DesktopNotifier`
protocol abstracts "show a popup"; :class:`WindowsToastNotifier` implements it
with ``win11toast``.

``win11toast.toast()`` BLOCKS until the toast is dismissed or times out
(~5 seconds), so each toast is shown on its own daemon thread. That keeps the
notification worker free to speak immediately instead of waiting for the popup
to disappear -- voice and toast happen together.
"""
from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from automation.logging_config import get_logger

_logger = get_logger(__name__)

DEFAULT_APP_NAME = "Zara"
# 'short' (~5s) or 'long' (~25s) per the Windows toast API.
DEFAULT_DURATION = "short"


@runtime_checkable
class DesktopNotifier(Protocol):
    """Shows a desktop notification. Implementations must not block the caller."""

    def notify(self, title: str, message: str) -> None:
        ...


class WindowsToastNotifier:
    """Shows native Windows 11 toasts via ``win11toast`` (non-blocking)."""

    def __init__(
        self,
        app_name: str = DEFAULT_APP_NAME,
        duration: str = DEFAULT_DURATION,
    ) -> None:
        self._app_name = app_name
        self._duration = duration

    def notify(self, title: str, message: str) -> None:
        """Shows a toast on a daemon thread so the caller is never blocked."""
        thread = threading.Thread(
            target=self._show,
            args=(title, message),
            name="zara-toast",
            daemon=True,
        )
        thread.start()

    def _show(self, title: str, message: str) -> None:
        try:
            from win11toast import toast

            toast(
                title,
                message,
                duration=self._duration,
                app_id=self._app_name,
            )
            _logger.debug("Toast shown: %r / %r", title, message)
        except Exception:  # noqa: BLE001 -- a popup failure must never crash Zara
            _logger.exception("Failed to show desktop toast.")


class ConsoleToastNotifier:
    """Fallback notifier that prints, for headless/test environments."""

    def notify(self, title: str, message: str) -> None:
        print(f"[TOAST] {title} - {message}")


def create_desktop_notifier(app_name: str = DEFAULT_APP_NAME) -> DesktopNotifier:
    """Returns a Windows toast notifier if available, else a console fallback.

    Importing ``win11toast`` is the availability probe; if it (or its WinRT
    dependencies) is missing, desktop toasts degrade gracefully to console
    output instead of breaking the assistant.
    """
    try:
        import win11toast  # noqa: F401 -- availability probe only

        return WindowsToastNotifier(app_name=app_name)
    except Exception:  # noqa: BLE001
        _logger.warning(
            "win11toast unavailable; desktop toasts disabled (console fallback)."
        )
        return ConsoleToastNotifier()
