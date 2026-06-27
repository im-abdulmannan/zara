"""APScheduler bridge for the reminder domain.

Maps :class:`Reminder` objects to APScheduler jobs via
:class:`automation.AutomationEngine`. This is the single place that knows how
a reminder's ``repeat_type`` and ``remind_at`` translate into triggers.

Lifecycle:
    create  -> :meth:`schedule`   -> ``AutomationEngine.create_job``
    update  -> :meth:`reschedule` -> ``AutomationEngine.update_job``
    delete  -> :meth:`remove`     -> ``AutomationEngine.delete_job``
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping, Tuple

from automation import AutomationEngine, JobInfo, JobSpec, ReminderType
from automation.exceptions import DuplicateJobError, JobNotFoundError
from automation.logging_config import get_logger
from reminders.config import ReminderConfig
from reminders.models import Reminder, ReminderStatus, RepeatType

# APScheduler day-of-week names, indexed by datetime.weekday() (Mon=0).
_WEEKDAY_NAMES: Tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_REPEAT_TO_REMINDER_TYPE = {
    RepeatType.ONCE: ReminderType.ONE_TIME,
    RepeatType.DAILY: ReminderType.DAILY,
    RepeatType.WEEKLY: ReminderType.WEEKLY,
    RepeatType.MONTHLY: ReminderType.MONTHLY,
}


class ReminderScheduler:
    """Synchronises reminders with APScheduler jobs."""

    def __init__(
        self,
        engine: AutomationEngine,
        config: ReminderConfig | None = None,
    ) -> None:
        self._engine = engine
        self._config = config or ReminderConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)

    @property
    def engine(self) -> AutomationEngine:
        return self._engine

    def schedule(self, reminder: Reminder) -> JobInfo:
        """Create an APScheduler job when a reminder is created."""
        spec = self._to_job_spec(reminder)
        try:
            job = self._engine.create_job(spec)
        except DuplicateJobError:
            job = self._engine.update_job(spec)
        self._logger.debug(
            "Scheduled reminder id=%s next_run=%s.",
            reminder.id,
            job.next_run_time,
        )
        return job

    def reschedule(self, reminder: Reminder) -> JobInfo:
        """Reschedule the APScheduler job when a reminder is updated."""
        spec = self._to_job_spec(reminder)
        try:
            job = self._engine.update_job(spec)
        except JobNotFoundError:
            job = self._engine.create_job(spec)
        self._logger.debug(
            "Rescheduled reminder id=%s next_run=%s.",
            reminder.id,
            job.next_run_time,
        )
        return job

    def remove(self, reminder_id: str) -> None:
        """Remove the APScheduler job when a reminder is deleted or cancelled."""
        try:
            self._engine.delete_job(reminder_id)
        except JobNotFoundError:
            self._logger.debug(
                "No APScheduler job to remove for reminder %s.", reminder_id
            )

    def rehydrate(self, reminders: Iterable[Reminder]) -> int:
        """Recreate APScheduler jobs for persisted reminders on startup."""
        count = 0
        now = datetime.now()
        for reminder in reminders:
            if reminder.status is not ReminderStatus.SCHEDULED:
                continue
            if (
                reminder.repeat_type is RepeatType.ONCE
                and reminder.remind_at < now
            ):
                continue
            self.schedule(reminder)
            count += 1
        self._logger.info("Rehydrated %d APScheduler job(s) from reminders.", count)
        return count

    def list_jobs(self) -> list[JobInfo]:
        """Return snapshots of all APScheduler jobs managed by the engine."""
        if not self._engine.is_running:
            return []
        return self._engine.list_jobs()

    def _to_job_spec(self, reminder: Reminder) -> JobSpec:
        reminder_type, schedule = self._to_trigger_schedule(reminder)
        return JobSpec(
            name=reminder.title,
            message=reminder.description or reminder.title,
            reminder_type=reminder_type,
            schedule=schedule,
            job_id=reminder.id,
            metadata={"repeat_type": reminder.repeat_type.value},
        )

    @staticmethod
    def _to_trigger_schedule(
        reminder: Reminder,
    ) -> Tuple[ReminderType, Mapping[str, Any]]:
        when = reminder.remind_at
        repeat = reminder.repeat_type
        reminder_type = _REPEAT_TO_REMINDER_TYPE[repeat]

        if repeat is RepeatType.ONCE:
            return reminder_type, {"run_date": when}
        if repeat is RepeatType.DAILY:
            return reminder_type, {"hour": when.hour, "minute": when.minute}
        if repeat is RepeatType.WEEKLY:
            return reminder_type, {
                "day_of_week": _WEEKDAY_NAMES[when.weekday()],
                "hour": when.hour,
                "minute": when.minute,
            }
        return reminder_type, {
            "day": when.day,
            "hour": when.hour,
            "minute": when.minute,
        }
