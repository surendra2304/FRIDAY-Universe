"""Recurring Security Assessment and Monitoring Scheduler Service.

Manages:
1. Scheduled task templates (Cron-style intervals).
2. Recurring lightweight probes (Port diff, Certificate expiry, DNS changes).
3. Run history and retry policies with automatic error escalation.

Run loop (TASK-SEN-008): the scheduler previously had no way to run — jobs
could be registered and executed only by a caller hand-feeding snapshots.
It now has a real asyncio run loop (``start``/``stop``/``is_running``,
mirroring the TLS/DNS daemon's lifecycle) driven by a snapshot provider.
The API lifespan starts it in production. The default provider builds each
probe snapshot from the finding engine's current findings (carrying over
the previous baseline's port/DNS/certificate fields, which are owned by
the TLS/DNS daemon's active probing), so baseline deltas — and therefore
dispatched operations alerts — fire on finding drift. Probe failures are
counted per job; after ``failure_escalation_threshold`` consecutive
failures an escalation alert is raised through the AlertEngine.
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

import contextlib
import inspect
import logging
from collections.abc import Awaitable, Callable
from pydantic import BaseModel

from sentinel.core.models import SeverityLevel
from sentinel.modules.operations.alerting import Alert, alert_engine
from sentinel.modules.operations.baseline import (
    BaselineDelta,
    ChangeType,
    SecurityBaselineSnapshot,
    baseline_engine,
)

logger = logging.getLogger("sentinel.operations.scheduler")

SnapshotProvider = Callable[
    ["ScheduledJob"],
    "SecurityBaselineSnapshot | Awaitable[SecurityBaselineSnapshot | None] | None",
]

#: target_ref values that mean "all findings, fleet-wide"
FLEET_TARGETS = {"*", "fleet", ""}


def findings_snapshot_provider(job: "ScheduledJob") -> SecurityBaselineSnapshot:
    """Default snapshot provider: current findings as the probe snapshot.

    Port/DNS/certificate fields are carried over from the previous baseline
    snapshot for the target (those signals are actively probed by the
    TLS/DNS daemon, not here), so the only deltas this provider can produce
    are finding-drift deltas — no invented port/DNS changes.
    """
    from sentinel.intelligence.risk.finding_engine import finding_engine

    findings = finding_engine.list_findings()
    if job.target_ref not in FLEET_TARGETS:
        findings = [f for f in findings if (f.target_ref or "") == job.target_ref]
    previous = baseline_engine.get_baseline(job.target_ref)
    return SecurityBaselineSnapshot(
        snapshot_id=f"sched-{job.job_id}-{int(datetime.now(UTC).timestamp())}",
        target_ref=job.target_ref,
        open_ports=list(previous.open_ports) if previous else [],
        dns_records=dict(previous.dns_records) if previous else {},
        active_findings=[f.id for f in findings],
        cert_expiry_days=previous.cert_expiry_days if previous else None,
        cloud_public_resources=list(previous.cloud_public_resources) if previous else [],
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

    def __init__(
        self,
        snapshot_provider: SnapshotProvider | None = None,
        tick_seconds: float = 5.0,
        failure_escalation_threshold: int = 3,
    ):
        self._jobs: dict[str, ScheduledJob] = {}
        self._running = False
        self._task_handle: asyncio.Task | None = None
        self._snapshot_provider = snapshot_provider
        self._tick_seconds = max(0.05, tick_seconds)
        self._failure_escalation_threshold = max(1, failure_escalation_threshold)
        self._consecutive_failures: dict[str, int] = {}

    # -- job registry -----------------------------------------------------

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

    def set_snapshot_provider(self, provider: SnapshotProvider | None):
        self._snapshot_provider = provider

    # -- probe execution --------------------------------------------------

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
        job.next_run = datetime.fromtimestamp(
            job.last_run.timestamp() + job.interval_seconds, UTC
        )
        job.run_count += 1
        return alerts

    async def run_job_now(self, job_id: str) -> list[Alert]:
        """Run one job using the configured snapshot provider."""
        job = self._jobs.get(job_id)
        if not job or job.status != ScheduleStatus.ACTIVE:
            return []
        provider = self._snapshot_provider or findings_snapshot_provider
        snapshot = provider(job)
        if inspect.isawaitable(snapshot):
            snapshot = await snapshot
        if snapshot is None:
            return []
        return await self.execute_job_probe(job_id, snapshot)

    async def run_due_jobs(self) -> dict[str, list[Alert]]:
        """Run every ACTIVE job whose next_run has arrived."""
        now = datetime.now(UTC)
        results: dict[str, list[Alert]] = {}
        for job in list(self._jobs.values()):
            if job.status != ScheduleStatus.ACTIVE:
                continue
            if job.next_run is not None and job.next_run > now:
                continue
            try:
                results[job.job_id] = await self.run_job_now(job.job_id)
                self._consecutive_failures[job.job_id] = 0
            except Exception as e:
                job.failure_count += 1
                consecutive = self._consecutive_failures.get(job.job_id, 0) + 1
                self._consecutive_failures[job.job_id] = consecutive
                # Do not hot-loop a failing job: retry at its normal interval.
                job.next_run = datetime.fromtimestamp(now.timestamp() + job.interval_seconds, UTC)
                logger.error(
                    "Operations probe failed for job %s (%s, consecutive=%d): %s",
                    job.job_id, job.target_ref, consecutive, e,
                )
                if consecutive >= self._failure_escalation_threshold:
                    self._consecutive_failures[job.job_id] = 0
                    self._escalate_job_failure(job, consecutive, e)
        return results

    def _escalate_job_failure(self, job: ScheduledJob, consecutive: int, error: Exception) -> None:
        """Raise an operations alert for a repeatedly failing probe job."""
        try:
            alert_engine.process_delta(
                BaselineDelta(
                    delta_id=f"delta-sched-fail-{job.job_id}-{int(datetime.now(UTC).timestamp())}",
                    target_ref=job.target_ref,
                    change_type=ChangeType.NEW_FINDING,
                    severity=SeverityLevel.HIGH,
                    description=(
                        f"Operations monitoring job '{job.name}' ({job.job_id}) failed "
                        f"{consecutive} consecutive times; last error: {error}"
                    ),
                )
            )
        except Exception as e:  # escalation must never kill the loop
            logger.error("Failed to raise scheduler escalation alert for %s: %s", job.job_id, e)

    # -- run loop -----------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running and self._task_handle is not None and not self._task_handle.done()

    async def _run_loop(self) -> None:
        logger.info(
            "Operations assessment scheduler started (%d job(s), tick %.1fs)",
            len(self._jobs), self._tick_seconds,
        )
        while self._running:
            try:
                await self.run_due_jobs()
            except Exception as e:
                logger.error("Error in operations scheduler cycle: %s", e, exc_info=True)
            try:
                await asyncio.sleep(self._tick_seconds)
            except asyncio.CancelledError:
                break
        logger.info("Operations assessment scheduler stopped cleanly.")

    def start(self) -> asyncio.Task:
        """Start the run loop in the active event loop (idempotent)."""
        if self.is_running:
            return self._task_handle  # type: ignore[return-value]
        self._running = True
        self._task_handle = asyncio.create_task(self._run_loop(), name="sentinel_operations_scheduler")
        return self._task_handle

    async def stop(self) -> None:
        """Gracefully terminate the run loop."""
        self._running = False
        if self._task_handle and not self._task_handle.done():
            self._task_handle.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task_handle


# Global Assessment Scheduler Singleton
assessment_scheduler = AssessmentScheduler()
