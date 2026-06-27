"""The automation engine facade.

:class:`AutomationEngine` owns a background APScheduler instance and exposes a
small, intention-revealing API (create/delete/pause/resume/list) over it. It
depends on abstractions -- an injected :class:`TriggerFactory` and an injected
scheduler -- rather than constructing everything itself, satisfying the
dependency-inversion principle and making the engine unit-testable.

The scheduler runs in its own daemon thread, so calling code (the Zara
assistant loop) is never blocked.
"""
from __future__ import annotations

from typing import Any, List, Optional

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED, JobExecutionEvent
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.base import ConflictingIdError, JobLookupError
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.job import Job

from automation.callbacks import dispatch_reminder
from automation.config import AutomationConfig
from automation.exceptions import (
    DuplicateJobError,
    JobNotFoundError,
    SchedulerNotRunningError,
)
from automation.logging_config import get_logger
from automation.models import JobInfo, JobSpec
from automation.triggers import TriggerFactory


class AutomationEngine:
    """Background scheduling engine for Zara reminders."""

    def __init__(
        self,
        config: Optional[AutomationConfig] = None,
        trigger_factory: Optional[TriggerFactory] = None,
        scheduler: Optional[BaseScheduler] = None,
    ) -> None:
        """Wires the engine's collaborators.

        Args:
            config: Engine configuration; loaded from the environment if omitted.
            trigger_factory: Strategy resolver for triggers; defaults to the
                built-in factory.
            scheduler: Pre-built scheduler (mainly for testing); a configured
                :class:`BackgroundScheduler` is created if omitted.
        """
        self._config = config or AutomationConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        self._trigger_factory = trigger_factory or TriggerFactory()
        self._scheduler = scheduler or self._build_scheduler(self._config)
        self._register_event_listeners()

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        """Starts the background scheduler (idempotent)."""
        if self._scheduler.running:
            self._logger.debug("Scheduler already running; start() ignored.")
            return
        self._scheduler.start()
        self._logger.info(
            "Automation engine started (timezone=%s, store=%s).",
            self._config.timezone,
            "memory" if self._config.use_memory_store else self._config.jobstore_url,
        )

    def shutdown(self, wait: bool = True) -> None:
        """Stops the scheduler. ``wait`` blocks until running jobs finish."""
        if not self._scheduler.running:
            self._logger.debug("Scheduler not running; shutdown() ignored.")
            return
        self._scheduler.shutdown(wait=wait)
        self._logger.info("Automation engine shut down (wait=%s).", wait)

    @property
    def is_running(self) -> bool:
        """True while the background scheduler thread is active."""
        return bool(self._scheduler.running)

    # -- job management ----------------------------------------------------
    def create_job(
        self,
        spec: JobSpec,
        *,
        replace_existing: bool = False,
    ) -> JobInfo:
        """Schedules a reminder described by ``spec`` and returns its snapshot.

        Raises:
            SchedulerNotRunningError: if the engine has not been started.
            DuplicateJobError: if ``spec.job_id`` already exists and
                ``replace_existing`` is False.
            InvalidScheduleError / UnsupportedReminderTypeError: from the factory.
        """
        self._ensure_running()
        trigger = self._trigger_factory.create(
            reminder_type=spec.reminder_type,
            schedule=spec.schedule,
            timezone=self._config.timezone,
        )
        # Carry the reminder type inside metadata so JobInfo can report it
        # after a restart, when only the persisted job is available.
        metadata = {**dict(spec.metadata), "reminder_type": spec.reminder_type.value}
        try:
            job = self._scheduler.add_job(
                func=dispatch_reminder,
                trigger=trigger,
                id=spec.job_id,  # None -> APScheduler generates a uuid
                name=spec.name,
                kwargs={
                    "reminder_id": spec.job_id or "",  # corrected below once id known
                    "name": spec.name,
                    "message": spec.message,
                    "metadata": metadata,
                },
                replace_existing=replace_existing,
                misfire_grace_time=self._config.misfire_grace_time,
                coalesce=self._config.coalesce,
                max_instances=self._config.max_instances,
            )
        except ConflictingIdError as exc:
            raise DuplicateJobError(
                f"A job with id {spec.job_id!r} already exists."
            ) from exc

        # The reminder_id passed to the handler must match the real job id,
        # which APScheduler may have generated. Patch it in now that we know it.
        if job.kwargs.get("reminder_id") != job.id:
            self._scheduler.modify_job(
                job.id, kwargs={**job.kwargs, "reminder_id": job.id}
            )
            job = self._scheduler.get_job(job.id)

        action = "Rescheduled" if replace_existing else "Created"
        self._logger.info(
            "%s %s reminder id=%s name=%r next_run=%s.",
            action,
            spec.reminder_type.value,
            job.id,
            spec.name,
            job.next_run_time,
        )
        return self._to_job_info(job)

    def update_job(self, spec: JobSpec) -> JobInfo:
        """Reschedules an existing APScheduler job from ``spec``.

        Updates the trigger, name, and handler kwargs in place so the job id
        (which equals the reminder id) stays stable.

        Raises:
            JobNotFoundError: if no job with ``spec.job_id`` exists.
        """
        self._ensure_running()
        if not spec.job_id:
            raise ValueError("JobSpec.job_id is required for update_job().")

        trigger = self._trigger_factory.create(
            reminder_type=spec.reminder_type,
            schedule=spec.schedule,
            timezone=self._config.timezone,
        )
        metadata = {**dict(spec.metadata), "reminder_type": spec.reminder_type.value}
        kwargs = {
            "reminder_id": spec.job_id,
            "name": spec.name,
            "message": spec.message,
            "metadata": metadata,
        }
        try:
            self._scheduler.reschedule_job(spec.job_id, trigger=trigger)
            self._scheduler.modify_job(
                spec.job_id,
                name=spec.name,
                kwargs=kwargs,
            )
        except JobLookupError as exc:
            raise JobNotFoundError(
                f"No job found with id {spec.job_id!r}."
            ) from exc

        job = self._get_job_or_raise(spec.job_id)
        self._logger.info(
            "Rescheduled %s reminder id=%s name=%r next_run=%s.",
            spec.reminder_type.value,
            job.id,
            spec.name,
            job.next_run_time,
        )
        return self._to_job_info(job)

    def delete_job(self, job_id: str, *, require_running: bool = False) -> None:
        """Removes a scheduled job from APScheduler.

        Args:
            job_id: The APScheduler job id (same as the reminder id).
            require_running: When True, raises if the scheduler is stopped.

        Raises:
            SchedulerNotRunningError: if ``require_running`` and engine is stopped.
            JobNotFoundError: if no job with ``job_id`` exists.
        """
        if require_running:
            self._ensure_running()
        try:
            self._scheduler.remove_job(job_id)
        except JobLookupError as exc:
            raise JobNotFoundError(f"No job found with id {job_id!r}.") from exc
        self._logger.info("Deleted reminder id=%s.", job_id)

    def pause_job(self, job_id: str) -> JobInfo:
        """Pauses a job (its ``next_run_time`` becomes ``None``)."""
        self._ensure_running()
        try:
            self._scheduler.pause_job(job_id)
        except JobLookupError as exc:
            raise JobNotFoundError(f"No job found with id {job_id!r}.") from exc
        self._logger.info("Paused reminder id=%s.", job_id)
        return self._to_job_info(self._get_job_or_raise(job_id))

    def resume_job(self, job_id: str) -> JobInfo:
        """Resumes a previously paused job."""
        self._ensure_running()
        try:
            self._scheduler.resume_job(job_id)
        except JobLookupError as exc:
            raise JobNotFoundError(f"No job found with id {job_id!r}.") from exc
        self._logger.info("Resumed reminder id=%s.", job_id)
        return self._to_job_info(self._get_job_or_raise(job_id))

    def list_jobs(self) -> List[JobInfo]:
        """Returns snapshots of all scheduled jobs."""
        self._ensure_running()
        return [self._to_job_info(job) for job in self._scheduler.get_jobs()]

    def get_job(self, job_id: str) -> JobInfo:
        """Returns a snapshot of a single job.

        Raises:
            JobNotFoundError: if no job with ``job_id`` exists.
        """
        self._ensure_running()
        return self._to_job_info(self._get_job_or_raise(job_id))

    # -- internals ---------------------------------------------------------
    def _build_scheduler(self, config: AutomationConfig) -> BackgroundScheduler:
        """Constructs a configured background scheduler from ``config``."""
        if config.use_memory_store:
            jobstore: Any = MemoryJobStore()
        else:
            jobstore = SQLAlchemyJobStore(url=config.jobstore_url)

        return BackgroundScheduler(
            jobstores={"default": jobstore},
            executors={"default": ThreadPoolExecutor(config.thread_pool_size)},
            job_defaults={
                "coalesce": config.coalesce,
                "max_instances": config.max_instances,
                "misfire_grace_time": config.misfire_grace_time,
            },
            timezone=config.timezone,
        )

    def _register_event_listeners(self) -> None:
        """Subscribes to job execution events for observability."""
        self._scheduler.add_listener(
            self._on_job_event,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED,
        )

    def _on_job_event(self, event: JobExecutionEvent) -> None:
        """Logs the outcome of a job run."""
        if event.exception:
            self._logger.error(
                "Reminder job id=%s raised an exception.",
                event.job_id,
                exc_info=event.exception,
            )
        elif event.code == EVENT_JOB_MISSED:
            self._logger.warning("Reminder job id=%s missed its run time.", event.job_id)
        else:
            self._logger.debug("Reminder job id=%s executed successfully.", event.job_id)

    def _ensure_running(self) -> None:
        """Guards operations that require a started scheduler."""
        if not self._scheduler.running:
            raise SchedulerNotRunningError(
                "Automation engine is not running. Call start() first."
            )

    def _get_job_or_raise(self, job_id: str) -> Job:
        """Fetches a job or raises :class:`JobNotFoundError`."""
        job = self._scheduler.get_job(job_id)
        if job is None:
            raise JobNotFoundError(f"No job found with id {job_id!r}.")
        return job

    @staticmethod
    def _to_job_info(job: Job) -> JobInfo:
        """Maps an APScheduler :class:`Job` to the public :class:`JobInfo`.

        A job whose ``next_run_time`` is ``None`` while it still exists in the
        store is treated as paused (APScheduler does not expose an explicit
        paused flag).
        """
        kwargs = job.kwargs or {}
        return JobInfo(
            job_id=job.id,
            name=job.name,
            message=kwargs.get("message"),
            reminder_type=(kwargs.get("metadata") or {}).get("reminder_type"),
            trigger=str(job.trigger),
            next_run_time=job.next_run_time,
            paused=job.next_run_time is None,
        )
