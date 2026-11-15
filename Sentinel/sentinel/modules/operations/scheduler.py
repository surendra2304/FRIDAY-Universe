"""Recurring Security Assessment and Monitoring Scheduler Service.

Manages:
1. Scheduled task templates (Cron-style intervals).
2. Recurring lightweight probes (Port diff, Certificate expiry, DNS changes).
3. Run history and retry policies with automatic error escalation.
"""

import asyncio
from datetime import datetime, timezone
UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
try:
    from enum import StrEnum
except ImportError:  # Python < 3.11: behaviour-identical fallback
    from enum import Enum as _StrEnumBase

    class StrEnum(str, _StrEnumBase):
        """Stand-in for enum.StrEnum (3.11+) on older interpreters."""

        __str__ = str.__str__
        __format__ = str.__format__

        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()

from pydantic import BaseModel

from sentinel.modules.operations.alerting import Alert, alert_engine
from sentinel.modules.operations.baseline import (
    SecurityBaselineSnapshot,
    baseline_engine,
)


class ScheduleStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class ScheduledJob(BaseModel):
    job_id: str
    name: str
    target_ref: str
    interval_seconds: int
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    failure_count: int = 0


class AssessmentScheduler:
    """In-process scheduler managing continuous security monitoring jobs."""

    def __init__(self):
        self._jobs: dict[str, ScheduledJob] = {}
        self._running = False
        self._task_handle: asyncio.Task | None = None

    def add_monitoring_job(
        self,
        job_id: str,
        name: str,
        target_ref: str,
        interval_seconds: int = 300,
    ) -> ScheduledJob:
        job = ScheduledJob(
            job_id=job_id,
            name=name,
            target_ref=target_ref,
            interval_seconds=interval_seconds,
            next_run=datetime.now(UTC),
        )
        self._jobs[job_id] = job
        return job

    def list_jobs(self) -> list[ScheduledJob]:
        return list(self._jobs.values())

    async def execute_job_probe(self, job_id: str, current_snapshot: SecurityBaselineSnapshot) -> list[Alert]:
        job = self._jobs.get(job_id)
        if not job or job.status != ScheduleStatus.ACTIVE:
            return []

        deltas = baseline_engine.compute_deltas(job.target_ref, current_snapshot)
        alerts: list[Alert] = []
        for d in deltas:
            alert = alert_engine.process_delta(d)
            alerts.append(alert)

        job.last_run = datetime.now(UTC)
        job.run_count += 1
        return alerts


# Global Assessment Scheduler Singleton
assessment_scheduler = AssessmentScheduler()
