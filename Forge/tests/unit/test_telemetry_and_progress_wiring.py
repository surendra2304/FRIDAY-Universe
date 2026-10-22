"""
Regression tests for the dead-telemetry and frozen-progress defects found in the
2026-10 audit.

Bug #7   ProgressTracker.start_stage / complete_stage existed but had no callers,
         so every snapshot froze at current_stage=Project,
         progress_percentage=0, estimated_remaining_seconds=15.0.

Bug #13  ProductionMonitor.record_request / record_task_event / record_verification /
         record_security_scan had no callers anywhere in app/, so /metrics always
         exported zeros and the error-rate and task-failure-rate alerts in
         check_alerts() could never fire.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.progress_tracker import ProgressTracker
from app.monitoring.production_monitor import ProductionMonitor
from app.planning.tree import PipelineStage


@pytest.fixture(autouse=True)
def _clear_tracker_registry():
    ProgressTracker._instances.clear()
    yield
    ProgressTracker._instances.clear()


# ---------------------------------------------------------------------------
# Bug #7 -- the tracker must actually advance
# ---------------------------------------------------------------------------


def test_starting_a_stage_advances_the_snapshot():
    tracker = ProgressTracker("task_progress_1", project_type="cli")
    before = tracker.get_snapshot()
    assert before.current_stage == PipelineStage.PROJECT
    assert before.progress_percentage == 0

    _run(tracker.start_stage(PipelineStage.REQUIREMENTS))
    after = tracker.get_snapshot()
    assert after.current_stage == PipelineStage.REQUIREMENTS
    assert after.progress_percentage > 0, "progress did not advance on stage start"
    assert after.stages["Requirements"].status == "running"


def test_completing_stages_accumulates_progress():
    tracker = ProgressTracker("task_progress_2", project_type="cli")
    for stage in (
        PipelineStage.PROJECT,
        PipelineStage.REQUIREMENTS,
        PipelineStage.ARCHITECTURE,
        PipelineStage.IMPLEMENTATION,
    ):
        _run(tracker.start_stage(stage))
        _run(tracker.complete_stage(stage))

    snapshot = tracker.get_snapshot()
    assert snapshot.progress_percentage >= 65, snapshot.progress_percentage
    assert snapshot.stages["Implementation"].status == "completed"


def test_complete_task_reaches_100_percent():
    tracker = ProgressTracker("task_progress_3", project_type="cli")
    _run(tracker.complete_task(success=True))
    snapshot = tracker.get_snapshot()
    assert snapshot.is_completed is True
    assert snapshot.progress_percentage == 100
    assert snapshot.estimated_remaining_seconds == 0.0


def test_failed_task_is_flagged_in_the_snapshot():
    tracker = ProgressTracker("task_progress_4", project_type="cli")
    _run(tracker.complete_task(success=False, error="boom"))
    snapshot = tracker.get_snapshot()
    assert snapshot.is_failed is True
    assert snapshot.is_completed is False


def test_orchestrator_drives_the_tracker():
    """The orchestrator must be the caller that was missing (bug #7)."""
    import inspect

    from app.core import orchestrator

    source = inspect.getsource(orchestrator)
    assert "ProgressTracker.get_or_create" in source, (
        "the orchestrator never creates a ProgressTracker"
    )
    assert "start_stage" in source, "the orchestrator never calls start_stage"
    assert "complete_stage" in source, "the orchestrator never calls complete_stage"
    assert "_finalize_tracker" in source, "the orchestrator never finalizes the tracker"


def test_stage_progress_is_driven_end_to_end():
    """A simulated DAG wave must move the tracker off its frozen default."""
    tracker = ProgressTracker("task_progress_5", project_type="website")

    stage = PipelineStage.IMPLEMENTATION
    _run(tracker.start_stage(stage, details={"node": "build api"}))
    snapshot = tracker.get_snapshot()
    assert snapshot.current_stage == PipelineStage.IMPLEMENTATION
    assert snapshot.stages["Implementation"].details["node"] == "build api"

    _run(tracker.complete_stage(stage, details={"node": "build api"}))
    assert tracker.get_snapshot().progress_percentage > 0


# ---------------------------------------------------------------------------
# Bug #13 -- the monitor must be fed
# ---------------------------------------------------------------------------


def test_monitor_starts_at_zero():
    monitor = ProductionMonitor()
    assert monitor.total_requests == 0
    assert monitor.task_submissions == 0
    assert "forge_requests_total 0" in monitor.export_prometheus_metrics()


def test_record_request_updates_counters_and_metrics():
    monitor = ProductionMonitor()
    monitor.record_request("/api/tasks")
    monitor.record_request("/api/tasks")
    monitor.record_request("/api/tasks", is_error=True)

    assert monitor.total_requests == 3
    assert monitor.total_errors == 1
    assert monitor.endpoint_requests["/api/tasks"] == 3

    text = monitor.export_prometheus_metrics()
    assert "forge_requests_total 3" in text
    assert "forge_errors_total 1" in text


def test_record_task_event_tracks_submissions_completions_and_failures():
    monitor = ProductionMonitor()
    monitor.record_task_event("submitted")
    monitor.record_task_event("completed")
    monitor.record_task_event("failed")
    monitor.record_task_event("failed")

    assert monitor.task_submissions == 1
    assert monitor.task_completions == 1
    assert monitor.task_failures == 2


def test_record_verification_tracks_pass_and_fail():
    monitor = ProductionMonitor()
    monitor.record_verification(passed=True)
    monitor.record_verification(passed=False)
    assert monitor.verification_passes == 1
    assert monitor.verification_fails == 1


def test_record_security_scan_tracks_totals_and_findings():
    monitor = ProductionMonitor()
    monitor.record_security_scan(passed=True, blocked=False, findings_count=0)
    monitor.record_security_scan(passed=False, blocked=True, findings_count=3)
    assert monitor.security_scans_total == 2
    assert monitor.security_findings_total == 3
    assert monitor.security_scans_blocked == 1


def test_error_rate_alert_can_fire():
    """Before the wiring, total_requests never rose so this branch was dead."""
    monitor = ProductionMonitor()
    for _ in range(25):
        monitor.record_request("/api/tasks", is_error=True)
    status = monitor.check_alerts()
    assert status.has_active_alerts is True
    assert any("error rate" in a.lower() for a in status.alerts)


def test_task_failure_rate_alert_can_fire():
    monitor = ProductionMonitor()
    for _ in range(5):
        monitor.record_task_event("failed")
    status = monitor.check_alerts()
    assert status.has_active_alerts is True
    assert any("failure rate" in a.lower() for a in status.alerts)


def test_request_telemetry_middleware_increments_the_monitor():
    """The HTTP middleware is the caller that was missing (bug #13)."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.monitoring.production_monitor import production_monitor

    before = production_monitor.total_requests
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/tasks/definitely-not-a-task").status_code == 404
    after = production_monitor.total_requests
    assert after > before, "no request telemetry was recorded"


def test_verification_engine_records_telemetry():
    """VerificationEngine must call record_verification (bug #13)."""
    import inspect

    from app.verification import engine as engine_module

    source = inspect.getsource(engine_module)
    assert "record_verification" in source, "VerificationEngine never records telemetry"


def test_security_scanner_records_telemetry():
    import inspect

    from app.verification import security_scanner as scanner_module

    source = inspect.getsource(scanner_module)
    assert "record_security_scan" in source, "OutputSecurityScanner never records telemetry"


def test_orchestrator_records_task_telemetry():
    import inspect

    from app.core import orchestrator

    source = inspect.getsource(orchestrator)
    assert 'record_task_event("submitted")' in source
    assert 'record_task_event("completed")' in source
    assert 'record_task_event("failed")' in source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    import asyncio

    return asyncio.run(coro)


# Keep unused-import linters quiet about the datetime symbols used by fixtures.
_ = (UTC, datetime, timedelta)
