"""
tests/test_task_records.py — TASK-CORE-003 unified task records.

Covers the task record lifecycle (submitted -> assigned -> dispatched ->
completed | failed, plus routing_failed), the immutable history audit trail,
TaskRecordStore queries/reporting, the non-breaking integrations of
UniverseTaskRouter and UniverseDispatchBus with an optional shared store,
and a thread-safety smoke test (the bus can dispatch from threads).

Import pattern follows tests/test_deep_autonomy_friday.py: direct
``from friday_core...`` imports, with the friday_core package made importable
by tests/conftest.py's sys.path setup.
"""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi import HTTPException

from friday_core.task_records import TaskRecord, TaskRecordStore, TaskStatus
from friday_core.universe_task_router import UniverseTaskRouter
from friday_core.universe_dispatch_bus import UniverseDispatchBus

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# A tiny local HTTP double for the dispatch-bus integration tests.
#
# Deliberately NOT tests/stub_fleet.py's fleet double: these tests exercise
# the bus<->store wiring, not the nine-agent wire contract, and they must not
# depend on FRIDAY_TEST_FLEET mode (stub or live).
# ---------------------------------------------------------------------------
class _ResultHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep test output quiet
        return

    def do_POST(self):
        # Consume the request body before responding: on a keep-alive
        # connection (httpx pools one) unread body bytes would be parsed as
        # the next request line and break the connection (cf. stub_fleet.py).
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        if self.path.rstrip("/").endswith("/enqueue"):
            body = json.dumps({"task_id": "queued-1"}).encode()
            code = 202  # async acceptance: work queued, not completed
        else:
            body = json.dumps({"status": "SUCCESS", "result": "stub result"}).encode()
            code = 200
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def result_server():
    """A local agent double; yields its base URL."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ResultHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _transitions(record: TaskRecord) -> list[tuple[str, str]]:
    """History as (from_status, to_status) pairs, ignoring timestamps."""
    return [(frm, to) for _, frm, to in record.history]


# ---------------------------------------------------------------------------
# TaskRecordStore lifecycle
# ---------------------------------------------------------------------------
class TestTaskRecordLifecycle:

    def test_full_lifecycle_submitted_assigned_dispatched_completed(self):
        store = TaskRecordStore()
        record = store.create("task_lifecycle_1", description="Categorize invoices")

        assert record.task_id == "task_lifecycle_1"
        assert record.status == TaskStatus.SUBMITTED.value == "submitted"
        assert record.owner_agent == ""
        assert record.result is None
        assert record.error == ""
        assert record.rationale is None
        assert record.created_at > 0
        assert record.updated_at == record.created_at
        assert record.assigned_at is None
        assert record.completed_at is None

        store.record_assignment("task_lifecycle_1", "Cortex", rationale="best match")
        record = store.get("task_lifecycle_1")
        assert record.status == "assigned"
        assert record.owner_agent == "Cortex"
        assert record.rationale == "best match"
        assert record.assigned_at is not None
        assert record.assigned_at >= record.created_at

        store.record_dispatch("task_lifecycle_1")
        record = store.get("task_lifecycle_1")
        assert record.status == "dispatched"

        store.record_completion("task_lifecycle_1", result={"status": "completed"})
        record = store.get("task_lifecycle_1")
        assert record.status == "completed"
        assert record.result == {"status": "completed"}
        assert record.completed_at is not None
        assert record.completed_at >= record.assigned_at
        assert _transitions(record) == [
            ("", "submitted"),
            ("submitted", "assigned"),
            ("assigned", "dispatched"),
            ("dispatched", "completed"),
        ]

    def test_failure_path_records_failed_with_error(self):
        store = TaskRecordStore()
        store.create("task_fail_1", description="Doomed dispatch")
        store.record_assignment("task_fail_1", "Forge")
        store.record_dispatch("task_fail_1")
        store.record_failure("task_fail_1", error="Connection refused - agent not running")

        record = store.get("task_fail_1")
        assert record.status == "failed"
        assert record.error == "Connection refused - agent not running"
        assert record.result is None
        assert _transitions(record) == [
            ("", "submitted"),
            ("submitted", "assigned"),
            ("assigned", "dispatched"),
            ("dispatched", "failed"),
        ]

    def test_history_is_an_append_only_audit_trail(self):
        store = TaskRecordStore()
        store.create("task_hist_1", description="audit me")
        store.record_assignment("task_hist_1", "Sentinel")
        store.record_dispatch("task_hist_1")
        store.record_failure("task_hist_1", error="timeout")

        record = store.get("task_hist_1")
        # Each entry is (timestamp, from_status, to_status) and timestamps
        # never go backwards.
        assert len(record.history) == 4
        timestamps = [entry[0] for entry in record.history]
        assert timestamps == sorted(timestamps)
        assert all(isinstance(frm, str) and isinstance(to, str)
                   for _, frm, to in record.history)

    def test_unknown_task_id_raises_keyerror_on_every_mutator(self):
        store = TaskRecordStore()
        for mutate in (
            lambda: store.record_assignment("ghost", "FRIDAY"),
            lambda: store.record_dispatch("ghost"),
            lambda: store.record_completion("ghost", result="x"),
            lambda: store.record_failure("ghost", error="x"),
            lambda: store.record_routing_failed("ghost", reason="x"),
        ):
            with pytest.raises(KeyError, match="Unknown task_id 'ghost'"):
                mutate()

    def test_duplicate_create_raises_valueerror(self):
        store = TaskRecordStore()
        store.create("task_dup_1", description="first")
        with pytest.raises(ValueError, match="already exists"):
            store.create("task_dup_1", description="second")
        # The original record is untouched.
        assert store.get("task_dup_1").description == "first"

    def test_get_unknown_returns_none(self):
        store = TaskRecordStore()
        assert store.get("never-submitted") is None

    def test_invalid_status_filter_raises_valueerror(self):
        store = TaskRecordStore()
        with pytest.raises(ValueError, match="Invalid status filter"):
            store.list(status="complete")  # typo must fail loudly, not return []


# ---------------------------------------------------------------------------
# TaskRecordStore queries and reporting
# ---------------------------------------------------------------------------
class TestTaskRecordStoreQueries:

    def test_list_insertion_order_and_filters_by_status_and_agent(self):
        store = TaskRecordStore()
        store.create("q1", description="one")
        store.create("q2", description="two")
        store.create("q3", description="three")
        store.record_assignment("q1", "FRIDAY")
        store.record_assignment("q2", "Inference")
        store.record_completion("q3", result="done")

        # Insertion order is preserved (dict by task_id).
        assert [r.task_id for r in store.list()] == ["q1", "q2", "q3"]

        assigned = store.list(status="assigned")
        assert [r.task_id for r in assigned] == ["q1", "q2"]

        assert [r.task_id for r in store.list(agent="Inference")] == ["q2"]
        assert [r.task_id for r in store.list(agent="FRIDAY")] == ["q1"]
        assert store.list(agent="Nobody") == []

        # Combined filter.
        store.record_assignment("q2", "FRIDAY")
        both = store.list(status="assigned", agent="FRIDAY")
        assert [r.task_id for r in both] == ["q1", "q2"]

    def test_report_counts_by_status_and_agent(self):
        store = TaskRecordStore()
        store.create("r1", description="a")
        store.create("r2", description="b")
        store.create("r3", description="c")
        store.create("r4", description="d")
        store.record_assignment("r1", "FRIDAY")
        store.record_assignment("r2", "FRIDAY")
        store.record_assignment("r3", "Inference")
        store.record_dispatch("r3")
        store.record_routing_failed("r4", reason="No agents registered")

        report = store.report()
        assert report["total"] == 4
        # Every documented status key is present, with a deterministic shape.
        assert set(report["by_status"]) == {s.value for s in TaskStatus}
        assert report["by_status"]["submitted"] == 0
        assert report["by_status"]["assigned"] == 2
        assert report["by_status"]["dispatched"] == 1
        assert report["by_status"]["routing_failed"] == 1
        assert report["by_agent"] == {"FRIDAY": 2, "Inference": 1}
        assert report["unassigned"] == 1  # r4 never got an owner

    def test_empty_report_shape(self):
        report = TaskRecordStore().report()
        assert report == {
            "total": 0,
            "by_status": {s.value: 0 for s in TaskStatus},
            "by_agent": {},
            "unassigned": 0,
        }


# ---------------------------------------------------------------------------
# UniverseTaskRouter integration (TASK-CORE-003)
# ---------------------------------------------------------------------------
class TestRouterIntegration:

    def test_router_with_store_records_submission_and_assignment(self):
        store = TaskRecordStore()
        router = UniverseTaskRouter(task_records=store)
        # A made-up agent + capability: no registry agent can match it, so
        # the assignment is deterministic.
        router.register_agent("RecordProbeAgent", ["quantum_tetris_reconciliation"])

        task = router.submit_task(
            "Reconcile the quantum tetris",
            required_capabilities=["quantum_tetris_reconciliation"],
        )
        record = store.get(task.task_id)
        assert record is not None
        assert record.status == "submitted"
        assert record.description == "Reconcile the quantum tetris"
        assert record.owner_agent == ""

        decision = router.route_task(task.task_id)
        record = store.get(task.task_id)
        assert record.status == "assigned"
        assert record.owner_agent == decision.assigned_agent == "RecordProbeAgent"
        assert record.rationale == decision.reason
        assert record.assigned_at is not None
        assert _transitions(record) == [("", "submitted"), ("submitted", "assigned")]

    def test_router_records_routing_failed_when_no_agents_registered(self):
        store = TaskRecordStore()
        router = UniverseTaskRouter(task_records=store)
        task = router.submit_task("Route me nowhere")
        # The router auto-registers fleet agents from the mesh registry; the
        # "No agents registered" branch is only reachable with an empty
        # capability table, so clear it (the router offers no public way).
        router._capabilities.clear()

        with pytest.raises(HTTPException) as excinfo:
            router.route_task(task.task_id)
        assert excinfo.value.status_code == 400
        assert excinfo.value.detail == "No agents registered"

        record = store.get(task.task_id)
        assert record.status == "routing_failed"
        assert record.error == "No agents registered"
        assert _transitions(record) == [
            ("", "submitted"),
            ("submitted", "routing_failed"),
        ]

    def test_router_records_routing_failed_for_unknown_task(self):
        store = TaskRecordStore()
        router = UniverseTaskRouter(task_records=store)
        # A record the router itself never submitted (e.g. created by a
        # peer component sharing the store): routing it must fail 404 and
        # leave a truthful routing_failed audit entry.
        store.create("task_orphan_1", description="known to the store only")

        with pytest.raises(HTTPException) as excinfo:
            router.route_task("task_orphan_1")
        assert excinfo.value.status_code == 404

        record = store.get("task_orphan_1")
        assert record.status == "routing_failed"
        assert record.error == "Task not found"

    def test_router_without_store_behaves_exactly_as_before(self):
        # Default (store None) must change nothing: submit, route, report all
        # work exactly as the pre-TASK-CORE-003 contract.
        router = UniverseTaskRouter()
        router.register_agent("RecordProbeAgent", ["quantum_tetris_reconciliation"])
        task = router.submit_task(
            "Legacy behavior probe",
            required_capabilities=["quantum_tetris_reconciliation"],
        )
        decision = router.route_task(task.task_id)

        assert decision.assigned_agent == "RecordProbeAgent"
        assert decision.confidence > 0
        assert task.status == "routed"
        assert router.get_report()["total_tasks"] == 1
        assert router.get_report()["routed_tasks"] == 1

        # An equally-configured store-less router and store-wired router
        # produce the same routing decisions.
        store = TaskRecordStore()
        wired = UniverseTaskRouter(task_records=store)
        wired.register_agent("RecordProbeAgent", ["quantum_tetris_reconciliation"])
        wired_task = wired.submit_task(
            "Legacy behavior probe",
            required_capabilities=["quantum_tetris_reconciliation"],
        )
        wired_decision = wired.route_task(wired_task.task_id)
        assert wired_decision.assigned_agent == decision.assigned_agent


# ---------------------------------------------------------------------------
# UniverseDispatchBus integration (TASK-CORE-003)
# ---------------------------------------------------------------------------
class TestBusIntegration:

    def test_bus_with_store_records_dispatch_and_completion(self, result_server):
        store = TaskRecordStore()
        bus = UniverseDispatchBus(task_records=store)
        bus.register_agent(
            "RecordProbeAgent", result_server,
            health_url=f"{result_server}/health", max_retries=0, timeout_sec=5.0,
        )

        receipt = bus.dispatch("RecordProbeAgent", "run", {"x": 1})
        assert receipt.status == "completed"
        assert receipt.result == "stub result"

        record = store.get(receipt.task_id)
        assert record is not None
        assert record.status == "completed"
        assert record.owner_agent == "RecordProbeAgent"
        assert record.description == "Dispatch run to RecordProbeAgent"
        # The record carries the receipt/result summary.
        assert record.result["task_id"] == receipt.task_id
        assert record.result["agent"] == "RecordProbeAgent"
        assert record.result["status"] == "completed"
        assert record.result["result"] == "stub result"
        assert record.completed_at is not None
        assert _transitions(record) == [
            ("", "submitted"),
            ("submitted", "dispatched"),
            ("dispatched", "completed"),
        ]

    def test_bus_with_store_records_failure(self):
        store = TaskRecordStore()
        bus = UniverseDispatchBus(task_records=store)
        # Nothing listens on 127.0.0.1:1; max_retries=0 -> one attempt, no
        # backoff sleeps. This agent is test-local: the default fleet configs
        # and the circuit breaker semantics are untouched.
        bus.register_agent("DeadProbeAgent", "http://127.0.0.1:1",
                           max_retries=0, timeout_sec=5.0)

        receipt = bus.dispatch("DeadProbeAgent", "run", {})
        assert receipt.status == "failed"

        record = store.get(receipt.task_id)
        assert record.status == "failed"
        assert record.error == receipt.error
        assert "ConnectError" in record.error
        assert record.result is None
        assert _transitions(record) == [
            ("", "submitted"),
            ("submitted", "dispatched"),
            ("dispatched", "failed"),
        ]

    def test_bus_accepted_receipt_stays_dispatched_no_fabricated_completion(self):
        # An agent that queues work asynchronously (HTTP 202) has NOT
        # completed it. The record must stay at `dispatched` — recording
        # `completed` would fabricate success (the TASK-CORE-002 defect).
        store = TaskRecordStore()
        bus = UniverseDispatchBus(task_records=store)
        server = ThreadingHTTPServer(("127.0.0.1", 0), _ResultHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            bus.register_agent("AsyncProbeAgent", base, max_retries=0, timeout_sec=5.0)
            receipt = bus.dispatch("AsyncProbeAgent", "enqueue", {})
        finally:
            server.shutdown()
            server.server_close()

        assert receipt.status == "accepted"
        record = store.get(receipt.task_id)
        assert record.status == "dispatched"
        assert record.result is None
        assert _transitions(record) == [
            ("", "submitted"),
            ("submitted", "dispatched"),
        ]

    def test_bus_async_dispatch_records_outcome(self, result_server):
        store = TaskRecordStore()
        bus = UniverseDispatchBus(task_records=store)
        bus.register_agent("RecordProbeAgent", result_server,
                           max_retries=0, timeout_sec=5.0)

        receipt = asyncio.run(bus.dispatch_async("RecordProbeAgent", "run", {"x": 2}))
        assert receipt.status == "completed"

        record = store.get(receipt.task_id)
        assert record.status == "completed"
        assert record.result["result"] == "stub result"

    def test_bus_batch_dispatch_records_every_task(self, result_server):
        store = TaskRecordStore()
        bus = UniverseDispatchBus(task_records=store)
        bus.register_agent("RecordProbeAgent", result_server,
                           max_retries=0, timeout_sec=5.0)

        receipts = bus.dispatch_batch([
            {"agent": "RecordProbeAgent", "action": "run", "payload": {"i": 1}},
            {"agent": "RecordProbeAgent", "action": "run", "payload": {"i": 2}},
        ])
        assert len(receipts) == 2
        for receipt in receipts:
            record = store.get(receipt.task_id)
            assert record.status == "completed"
            assert record.owner_agent == "RecordProbeAgent"
        assert store.report()["total"] == 2

    def test_bus_without_store_behaves_exactly_as_before(self, result_server):
        bus = UniverseDispatchBus()  # default: no store, no behavior change
        bus.register_agent("RecordProbeAgent", result_server,
                           max_retries=0, timeout_sec=5.0)

        receipt = bus.dispatch("RecordProbeAgent", "run", {"x": 3})
        assert receipt.status == "completed"
        assert receipt.agent == "RecordProbeAgent"

        # Receipt lookup and report still work exactly as before.
        lookup = bus.get_receipt(receipt.task_id)
        assert lookup["task_id"] == receipt.task_id
        assert lookup["status"] == "completed"
        assert lookup["result"] == "stub result"
        report = bus.get_report()
        assert report["total_dispatches"] >= 1
        assert report["completed"] >= 1


# ---------------------------------------------------------------------------
# Thread safety (the bus dispatches from threads)
# ---------------------------------------------------------------------------
class TestThreadSafety:

    def test_concurrent_record_completion_from_many_threads(self):
        store = TaskRecordStore()
        n_threads = 16
        task_ids = [f"task_thread_{i}" for i in range(n_threads)]
        for task_id in task_ids:
            store.create(task_id, description=f"concurrent {task_id}")
            store.record_assignment(task_id, "RecordProbeAgent")

        barrier = threading.Barrier(n_threads)
        errors: list[Exception] = []

        def worker(i: int) -> None:
            try:
                barrier.wait()  # maximize contention on the store
                store.record_completion(task_ids[i], result=f"result-{i}")
            except Exception as exc:  # pragma: no cover - only on a bug
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert not any(t.is_alive() for t in threads)

        assert errors == []
        for i, task_id in enumerate(task_ids):
            record = store.get(task_id)
            assert record.status == "completed"
            assert record.result == f"result-{i}"
            # Exactly one transition per mutation: no torn or lost updates.
            assert _transitions(record) == [
                ("", "submitted"),
                ("submitted", "assigned"),
                ("assigned", "completed"),
            ]
        report = store.report()
        assert report["total"] == n_threads
        assert report["by_status"]["completed"] == n_threads

    def test_concurrent_reads_and_writes_do_not_tear(self):
        store = TaskRecordStore()
        store.create("task_rw_1", description="reader/writer probe")
        store.record_assignment("task_rw_1", "RecordProbeAgent")

        stop = threading.Event()
        readers: list[Exception] = []

        def reader() -> None:
            try:
                while not stop.is_set():
                    report = store.report()
                    assert report["total"] == 1
                    record = store.get("task_rw_1")
                    assert record is not None
                    assert store.list(agent="RecordProbeAgent")
            except Exception as exc:  # pragma: no cover - only on a bug
                readers.append(exc)
                stop.set()

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        try:
            for i in range(200):
                store.record_dispatch("task_rw_1")
                store.record_failure("task_rw_1", error=f"attempt {i}")
        finally:
            stop.set()
            for t in threads:
                t.join(timeout=10)
        assert not any(t.is_alive() for t in threads)
        assert readers == []
        # The audit trail kept every transition even under concurrent reads.
        assert len(store.get("task_rw_1").history) == 1 + 1 + 2 * 200
