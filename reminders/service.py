"""Reminder service: the use-case layer.

Coordinates three collaborators (all injected -- dependency inversion):

* :class:`ReminderRepository` -- persistence (source of truth)
* :class:`ReminderScheduler`   -- APScheduler job sync (create/reschedule/remove)
* :class:`NotificationQueue`  -- delivery channel

When a reminder is **created**, an APScheduler job is added automatically.
When a reminder is **updated**, the job is **rescheduled** in place.
When a reminder is **deleted** or **cancelled**, the job is **removed**.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Mapping, Optional

from automation import register_handler, unregister_handler
from automation.logging_config import get_logger
from reminders.config import ReminderConfig
from reminders.models import Reminder, ReminderStatus, RepeatType
from reminders.notifications import NotificationMessage, NotificationQueue
from reminders.repository import ReminderRepository
from reminders.scheduler import ReminderScheduler


class ReminderService:
    """High-level API for creating and managing reminders."""

    def __init__(
        self,
        scheduler: ReminderScheduler,
        repository: ReminderRepository,
        notification_queue: NotificationQueue,
        config: Optional[ReminderConfig] = None,
    ) -> None:
        self._scheduler = scheduler
        self._repo = repository
        self._queue = notification_queue
        self._config = config or ReminderConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        # The handler is a bound method (never pickled), so registering it at
        # construction time is safe and must be repeated on each startup.
        register_handler(self._on_reminder_fired)

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        """Starts APScheduler and rehydrates jobs for all active reminders.

        The repository is the source of truth: on startup we rebuild
        APScheduler jobs for every reminder still in the SCHEDULED state.
        """
        self._scheduler.engine.start()
        self._reschedule_active()
        self._logger.info("Reminder service started.")

    def shutdown(self, wait: bool = True) -> None:
        """Stops APScheduler and detaches the notification handler."""
        unregister_handler(self._on_reminder_fired)
        self._scheduler.engine.shutdown(wait=wait)
        self._logger.info("Reminder service shut down.")

    # -- CRUD use cases ----------------------------------------------------
    def create_reminder(
        self,
        title: str,
        remind_at: datetime,
        description: str = "",
        repeat_type: "str | RepeatType" = RepeatType.ONCE,
    ) -> Reminder:
        """Creates, persists, and schedules a reminder."""
        reminder = Reminder(
            id=uuid.uuid4().hex,
            title=title,
            description=description,
            remind_at=remind_at,
            repeat_type=RepeatType.from_value(repeat_type),
            status=ReminderStatus.SCHEDULED,
            created_at=datetime.now(),
        )
        self._repo.add(reminder)
        self._scheduler.schedule(reminder)
        self._logger.info(
            "Created reminder id=%s title=%r repeat=%s due=%s.",
            reminder.id,
            reminder.title,
            reminder.repeat_type.value,
            reminder.remind_at.isoformat(),
        )
        return reminder

    def get_reminder(self, reminder_id: str) -> Reminder:
        """Returns a reminder or raises :class:`ReminderNotFoundError`."""
        return self._repo.get_or_raise(reminder_id)

    def list_reminders(
        self, status: Optional[ReminderStatus] = None
    ) -> List[Reminder]:
        """Lists reminders, optionally filtered by status."""
        return self._repo.list(status=status)

    def update_reminder(
        self,
        reminder_id: str,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        remind_at: Optional[datetime] = None,
        repeat_type: "Optional[str | RepeatType]" = None,
    ) -> Reminder:
        """Updates a reminder's fields and reschedules its APScheduler job."""
        reminder = self._repo.get_or_raise(reminder_id)
        if title is not None:
            reminder.title = title
        if description is not None:
            reminder.description = description
        if remind_at is not None:
            reminder.remind_at = remind_at
        if repeat_type is not None:
            reminder.repeat_type = RepeatType.from_value(repeat_type)
        reminder.__post_init__()

        self._repo.update(reminder)
        if reminder.status is ReminderStatus.SCHEDULED:
            self._scheduler.reschedule(reminder)
        else:
            self._scheduler.remove(reminder.id)
        self._logger.info("Updated reminder id=%s.", reminder.id)
        return reminder

    def pause_reminder(self, reminder_id: str) -> Reminder:
        """Pauses delivery without deleting the reminder."""
        from automation.exceptions import JobNotFoundError

        reminder = self._repo.get_or_raise(reminder_id)
        try:
            self._scheduler.engine.pause_job(reminder_id)
        except JobNotFoundError:
            self._logger.warning(
                "Pause: no APScheduler job for reminder %s.", reminder_id
            )
        self._repo.update_status(reminder_id, ReminderStatus.PAUSED)
        reminder.status = ReminderStatus.PAUSED
        self._logger.info("Paused reminder id=%s.", reminder_id)
        return reminder

    def resume_reminder(self, reminder_id: str) -> Reminder:
        """Resumes a paused reminder."""
        from automation.exceptions import JobNotFoundError

        reminder = self._repo.get_or_raise(reminder_id)
        try:
            self._scheduler.engine.resume_job(reminder_id)
        except JobNotFoundError:
            self._scheduler.schedule(reminder)
        self._repo.update_status(reminder_id, ReminderStatus.SCHEDULED)
        reminder.status = ReminderStatus.SCHEDULED
        self._logger.info("Resumed reminder id=%s.", reminder_id)
        return reminder

    def cancel_reminder(self, reminder_id: str) -> Reminder:
        """Cancels a reminder: removes its job and marks it CANCELLED."""
        reminder = self._repo.get_or_raise(reminder_id)
        self._scheduler.remove(reminder_id)
        self._repo.update_status(reminder_id, ReminderStatus.CANCELLED)
        reminder.status = ReminderStatus.CANCELLED
        self._logger.info("Cancelled reminder id=%s.", reminder_id)
        return reminder

    def delete_reminder(self, reminder_id: str) -> None:
        """Permanently removes a reminder and its APScheduler job."""
        self._scheduler.remove(reminder_id)
        self._repo.delete(reminder_id)
        self._logger.info("Deleted reminder id=%s.", reminder_id)

    # -- scheduling internals ---------------------------------------------
    def _reschedule_active(self) -> None:
        """Re-creates APScheduler jobs for all SCHEDULED reminders (startup)."""
        active = self._repo.list(status=ReminderStatus.SCHEDULED)
        now = datetime.now()
        rescheduled = 0
        for reminder in active:
            if (
                reminder.repeat_type is RepeatType.ONCE
                and reminder.remind_at < now
            ):
                self._repo.update_status(reminder.id, ReminderStatus.COMPLETED)
                self._logger.info(
                    "Reminder %s was due in the past; marked completed.",
                    reminder.id,
                )
                continue
            self._scheduler.schedule(reminder)
            rescheduled += 1
        self._logger.info("Rehydrated %d active reminder(s).", rescheduled)

    # -- notification handler (runs on an APScheduler worker thread) -------
    def _on_reminder_fired(
        self,
        reminder_id: str,
        name: str,
        message: str,
        metadata: Mapping[str, Any],
    ) -> None:
        """APScheduler callback: enqueue a notification. Never speaks directly."""
        reminder = self._repo.get(reminder_id)
        if reminder is None:
            self._logger.warning(
                "Fired reminder %s no longer exists; dropping notification.",
                reminder_id,
            )
            return

        notification = NotificationMessage(
            reminder_id=reminder.id,
            title=reminder.title,
            description=reminder.description,
            repeat_type=reminder.repeat_type.value,
            fired_at=datetime.now(),
        )
        self._queue.put(notification)
        self._logger.info("Queued notification for reminder %s.", reminder_id)

        if reminder.repeat_type is RepeatType.ONCE:
            self._repo.update_status(reminder_id, ReminderStatus.COMPLETED)
