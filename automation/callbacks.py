"""Reminder dispatch and handler registry.

When a job fires, APScheduler invokes :func:`dispatch_reminder` -- a top-level
function so it is importable by a persistent (SQLAlchemy) job store, which
serialises jobs by their fully-qualified callable path. ``dispatch_reminder``
then fans out to handlers registered at runtime, keeping the engine decoupled
from *how* a reminder is delivered (TTS, desktop notification, logging, ...).

Handlers must be re-registered on process startup, because the registry lives
in memory, not in the persisted job.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from automation.logging_config import get_logger

_logger = get_logger(__name__)

# Module-level handler registry. Order of registration is preserved.
_handlers: list["ReminderHandler"] = []


@runtime_checkable
class ReminderHandler(Protocol):
    """Callable invoked when a reminder fires.

    Implementations should be side-effecting (speak, notify, log) and must not
    raise; any exception is caught and logged so one bad handler cannot prevent
    others from running.
    """

    def __call__(
        self,
        reminder_id: str,
        name: str,
        message: str,
        metadata: Mapping[str, Any],
    ) -> None:
        ...


def register_handler(handler: "ReminderHandler") -> None:
    """Registers a handler to be called on every reminder, if not already present."""
    if handler not in _handlers:
        _handlers.append(handler)
        _logger.info("Registered reminder handler: %r", getattr(handler, "__name__", handler))


def unregister_handler(handler: "ReminderHandler") -> None:
    """Removes a previously registered handler; no-op if absent."""
    try:
        _handlers.remove(handler)
        _logger.info("Unregistered reminder handler: %r", getattr(handler, "__name__", handler))
    except ValueError:
        _logger.debug("Handler not registered, nothing to remove: %r", handler)


def clear_handlers() -> None:
    """Removes all registered handlers (useful in tests / shutdown)."""
    _handlers.clear()
    _logger.debug("Cleared all reminder handlers.")


def dispatch_reminder(
    reminder_id: str,
    name: str,
    message: str,
    metadata: Optional[Mapping[str, Any]] = None,
) -> None:
    """Entry point executed by the scheduler when a reminder fires.

    This must remain a top-level, importable function: the persistent job store
    references it by ``module:function`` path. Each handler is isolated so a
    failing handler is logged but does not break the others.
    """
    metadata = metadata or {}
    _logger.info("Reminder fired: id=%s name=%r message=%r", reminder_id, name, message)

    if not _handlers:
        _logger.warning(
            "No reminder handlers registered; reminder %s (%r) was not delivered.",
            reminder_id,
            name,
        )
        return

    for handler in list(_handlers):
        try:
            handler(reminder_id=reminder_id, name=name, message=message, metadata=metadata)
        except Exception:  # noqa: BLE001 -- isolate handler failures deliberately
            _logger.exception(
                "Reminder handler %r failed for reminder %s.",
                getattr(handler, "__name__", handler),
                reminder_id,
            )
