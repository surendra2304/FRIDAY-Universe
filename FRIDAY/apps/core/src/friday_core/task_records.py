"""
FRIDAY/apps/core/src/friday_core/task_records.py — unified task records (TASK-CORE-003).

The universe task router knows *assignment* (which owner agent a task went to)
and the universe dispatch bus knows *execution* (the receipt and result), but
nothing tied the two into one trackable record. This module is that unified
record: TASK-ID, owner agent, status, result — with a full, immutable
lifecycle audit trail — so FRIDAY can assign work, track it and report
completion (the TASK-ORCH-002 dependency).

Design notes:
- In-memory only, by design, for this pass. Production storage is Oracle-only
  and fail-closed; introducing any persistence/DB layer here is out of scope.
  The ``TaskRecordStore`` interface is deliberately clean (create / record_*
  / get / list / report) so a durable backend can be swapped in later without
  touching the router or the bus.
- Thread-safe: every store method takes a lock because the dispatch bus can be
  called from worker threads. Mutation methods raise ``KeyError`` on unknown
  task IDs (fail loud, never silently no-op).
- The SAME store instance is meant to be shared between a ``UniverseTaskRouter``
  and a ``UniverseDispatchBus``; the caller (FRIDAY, under TASK-ORCH-002)
  wires them together. The router records submission/assignment; the bus
  records dispatch/completion per its own dispatch task IDs.

Lifecycle (canonical order):
    submitted -> assigned -> dispatched -> completed | failed
    submitted -> routing_failed          (router could not assign an owner)
Transitions are *recorded*, not policed: a re-dispatch after a failure is a
legitimate flow, so the store appends to history instead of rejecting.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Task record lifecycle statuses (minimal, documented set).

    - ``submitted``: the task exists (typically created by the task router)
      but no owner agent has been chosen yet.
    - ``assigned``: the router chose an owner agent for the task.
    - ``dispatched``: the task has been handed to the dispatch bus for
      delivery/execution by its owner agent.
    - ``completed``: execution finished successfully; ``TaskRecord.result``
      carries the receipt/result summary.
    - ``failed``: execution finished unsuccessfully; ``TaskRecord.error``
      carries the reason.
    - ``routing_failed``: the router could not assign an owner at all (e.g.
      no agents registered, or the routing request referenced an unknown
      task). Kept distinct from ``failed`` so assignment failures are never
      confused with execution failures.
    """

    SUBMITTED = "submitted"
    ASSIGNED = "assigned"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    ROUTING_FAILED = "routing_failed"


#: Every status value the store will accept as a transition target.
VALID_STATUSES: frozenset[str] = frozenset(s.value for s in TaskStatus)


#: Placeholder ``from_status`` for the history entry created with the record
#: (a new record has no prior status). Kept as "" so every history tuple is a
#: plain (timestamp, from_status, to_status) triple of strings.
_NO_PRIOR_STATUS = ""


@dataclass
class TaskRecord:
    """One unified, trackable task record (TASK-ID, owner agent, status, result).

    Fields:
        task_id: unique TASK-ID. Router tasks use their ``task_<hex>`` id;
            dispatch-bus executions use the receipt's ``disp_<hex>`` id.
        description: human-readable description of the work.
        owner_agent: agent responsible for the work ("" while unassigned).
        status: current ``TaskStatus`` value (plain string for JSON friendliness).
        result: outcome payload on completion (receipt/result summary from the
            dispatch bus, or whatever the caller considers the result). None
            until completion.
        error: failure reason when status is ``failed`` or ``routing_failed``.
        rationale: the router's ``RoutingDecision.reason`` for the assignment,
            when available (optional).
        created_at / updated_at: record creation and last-transition times.
        assigned_at: timestamp of the submitted->assigned transition (None before).
        completed_at: timestamp of the ->completed transition (None before).
        history: immutable audit trail of
            ``(timestamp, from_status, to_status)`` tuples, append-only, in
            order. Record creation is logged as ``("", "submitted")``.

    Callers should treat records as read-only; the store is the only writer.
    """

    task_id: str
    description: str = ""
    owner_agent: str = ""
    status: str = TaskStatus.SUBMITTED.value
    result: Any = None
    error: str = ""
    rationale: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = 0.0
    assigned_at: float | None = None
    completed_at: float | None = None
    history: list[tuple[float, str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = self.created_at
        if not self.history:
            self.history = [(self.created_at, _NO_PRIOR_STATUS, self.status)]


class TaskRecordStore:
    """In-memory, insertion-ordered, thread-safe store of :class:`TaskRecord`.

    Contract:
    - ``create`` raises ``ValueError`` on a duplicate task_id (fail loud).
    - All mutating ``record_*`` methods raise ``KeyError`` with a clear
      message for an unknown task_id (fail loud, never a silent no-op).
    - ``get``/``list``/``report`` are read-only and never raise on unknown ids.
    - Every mutation appends to the record's ``history`` and bumps
      ``updated_at``; history is append-only (auditability).
    """

    def __init__(self) -> None:
        # dict preserves insertion order -> list()/report() are deterministic.
        self._records: dict[str, TaskRecord] = {}
        # RLock: mutations are short and never re-enter today, but RLock keeps
        # the store safe if a future method ever composes two public calls.
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # internals (call only while holding self._lock)
    # ------------------------------------------------------------------
    def _require(self, task_id: str) -> TaskRecord:
        record = self._records.get(task_id)
        if record is None:
            raise KeyError(
                f"Unknown task_id {task_id!r}: no task record exists "
                f"(store holds {len(self._records)} record(s))"
            )
        return record

    def _transition(self, record: TaskRecord, to_status: str,
                    timestamp: float | None = None) -> None:
        if to_status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid task status {to_status!r}; expected one of "
                f"{sorted(VALID_STATUSES)}"
            )
        now = timestamp if timestamp is not None else time.time()
        record.history.append((now, record.status, to_status))
        record.status = to_status
        record.updated_at = now

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def create(self, task_id: str, description: str = "",
               owner_agent: str = "", rationale: str | None = None) -> TaskRecord:
        """Create a new record in ``submitted`` status.

        Raises ``ValueError`` if a record with this task_id already exists.
        """
        with self._lock:
            if task_id in self._records:
                raise ValueError(
                    f"Task record already exists for task_id {task_id!r}; "
                    "task IDs must be unique"
                )
            record = TaskRecord(
                task_id=task_id, description=description,
                owner_agent=owner_agent, rationale=rationale,
            )
            self._records[task_id] = record
            return record

    def record_assignment(self, task_id: str, owner_agent: str,
                          rationale: str | None = None) -> TaskRecord:
        """Record that the router assigned the task to ``owner_agent``."""
        with self._lock:
            record = self._require(task_id)
            record.owner_agent = owner_agent
            if rationale is not None:
                record.rationale = rationale
            self._transition(record, TaskStatus.ASSIGNED.value)
            record.assigned_at = record.updated_at
            return record

    def record_dispatch(self, task_id: str) -> TaskRecord:
        """Record that the task was handed to the dispatch bus for delivery."""
        with self._lock:
            record = self._require(task_id)
            self._transition(record, TaskStatus.DISPATCHED.value)
            return record

    def record_completion(self, task_id: str, result: Any = None) -> TaskRecord:
        """Record successful completion; ``result`` carries the outcome."""
        with self._lock:
            record = self._require(task_id)
            record.result = result
            record.error = ""
            self._transition(record, TaskStatus.COMPLETED.value)
            record.completed_at = record.updated_at
            return record

    def record_failure(self, task_id: str, error: str = "") -> TaskRecord:
        """Record an execution failure; ``error`` carries the reason."""
        with self._lock:
            record = self._require(task_id)
            record.error = error
            self._transition(record, TaskStatus.FAILED.value)
            return record

    def record_routing_failed(self, task_id: str, reason: str = "") -> TaskRecord:
        """Record that the router could not assign an owner agent at all."""
        with self._lock:
            record = self._require(task_id)
            record.error = reason
            self._transition(record, TaskStatus.ROUTING_FAILED.value)
            return record

    def get(self, task_id: str) -> TaskRecord | None:
        """Return the record for ``task_id`` or None (lookup, never raises)."""
        with self._lock:
            return self._records.get(task_id)

    def list(self, status: str | None = None,
             agent: str | None = None) -> list[TaskRecord]:
        """List records in insertion order, optionally filtered.

        ``status`` must be a valid :class:`TaskStatus` value when given
        (``ValueError`` otherwise — a typo in a filter must fail loudly, not
        silently return an empty list). ``agent`` filters by owner agent.
        """
        with self._lock:
            if status is not None and status not in VALID_STATUSES:
                raise ValueError(
                    f"Invalid status filter {status!r}; expected one of "
                    f"{sorted(VALID_STATUSES)}"
                )
            records = list(self._records.values())
        if status is not None:
            records = [r for r in records if r.status == status]
        if agent is not None:
            records = [r for r in records if r.owner_agent == agent]
        return records

    def report(self) -> dict[str, Any]:
        """Aggregate counts: per status, per owner agent.

        ``by_status`` always contains every documented status key (0 when
        absent) so the shape is deterministic; ``by_agent`` only contains
        agents that own at least one record, with ``unassigned`` counting
        records that have no owner yet.
        """
        with self._lock:
            by_status: dict[str, int] = {s.value: 0 for s in TaskStatus}
            by_agent: dict[str, int] = {}
            unassigned = 0
            for record in self._records.values():
                by_status[record.status] += 1
                if record.owner_agent:
                    by_agent[record.owner_agent] = (
                        by_agent.get(record.owner_agent, 0) + 1
                    )
                else:
                    unassigned += 1
            return {
                "total": len(self._records),
                "by_status": by_status,
                "by_agent": by_agent,
                "unassigned": unassigned,
            }


# ----------------------------------------------------------------------
# shared process-wide store (TASK-ORCH-002)
# ----------------------------------------------------------------------
_SHARED_STORE: "TaskRecordStore | None" = None
_SHARED_STORE_LOCK = threading.Lock()


def get_shared_task_records() -> "TaskRecordStore":
    """Return the one process-wide shared ``TaskRecordStore`` (lazily created).

    TASK-ORCH-002: the universe task router (assignment) and the universe
    dispatch bus (execution) record into the SAME store, so one task leaves
    one coherent lifecycle trail: ``submitted -> assigned -> dispatched ->
    completed | failed``. Both ``friday_core.universe_task_router.engine``
    and ``friday_core.universe_dispatch_bus.engine`` are wired to this
    singleton at import time; tests that need isolation construct their own
    ``TaskRecordStore`` and pass it explicitly.
    """
    global _SHARED_STORE
    if _SHARED_STORE is None:
        with _SHARED_STORE_LOCK:
            if _SHARED_STORE is None:
                _SHARED_STORE = TaskRecordStore()
    return _SHARED_STORE
