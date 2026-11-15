"""TASK-SEN-008: operations alerts dispatch through the shared human channel.

Covers:
- AlertEngine dispatches each NEW alert exactly once (dedup never re-sends).
- OperationsAlertDispatcher sends via the approval dispatcher's channel
  (TASK-SEN-006 credential resolution) and queues honestly when unconfigured.
- Registered webhooks receive a real HTTP POST of the alert.
- The operations scheduler run loop executes due jobs from a snapshot
  provider, and repeated probe failures escalate to an alert.
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from sentinel.core.models import SeverityLevel
from sentinel.modules.operations.alerting import AlertEngine
from sentinel.modules.operations.baseline import (
    BaselineDelta,
    ChangeType,
    SecurityBaselineSnapshot,
)
from sentinel.modules.operations.dispatch import OperationsAlertDispatcher
from sentinel.modules.operations.scheduler import AssessmentScheduler


def _delta(target: str, description: str, severity=SeverityLevel.HIGH) -> BaselineDelta:
    return BaselineDelta(
        delta_id=f"delta-{target}-{description[:12]}",
        target_ref=target,
        change_type=ChangeType.NEW_FINDING,
        severity=severity,
        description=description,
    )


class FakeChannel:
    """Stand-in for ApprovalDispatcher with the SEN-006 surface."""

    def __init__(self, configured: bool = True):
        self.channel_configured = configured
        self.calls: list[tuple[str, dict | None]] = []

    def dispatch_notification(self, html_text, discord_payload=None):
        self.calls.append((html_text, discord_payload))
        return {"telegram": True, "discord": False}


class ExplodingChannel:
    channel_configured = True

    def dispatch_notification(self, html_text, discord_payload=None):
        raise RuntimeError("transport exploded")


def test_new_alert_dispatches_once_dedup_never_resends():
    channel = FakeChannel()
    engine = AlertEngine(dispatcher=OperationsAlertDispatcher(channel=channel))
    delta = _delta("asset-dedup", "New finding: exposed admin panel")

    alert = engine.process_delta(delta)
    assert alert.dispatched is True
    assert alert.dispatch_channels == ["telegram"]
    assert alert.dispatch_queued is False
    assert len(channel.calls) == 1
    assert alert.alert_id in channel.calls[0][0]
    assert channel.calls[0][1] is not None  # discord payload built too

    again = engine.process_delta(delta)
    assert again.occurrence_count == 2
    assert len(channel.calls) == 1  # storm suppression: no second dispatch


def test_engine_without_dispatcher_keeps_store_only_behaviour():
    engine = AlertEngine()
    alert = engine.process_delta(_delta("asset-plain", "New finding: stale cert"))
    assert alert.dispatched is False
    assert alert.dispatch_channels == []
    assert alert.dispatch_queued is False


def test_unconfigured_channel_queues_honestly():
    channel = FakeChannel(configured=False)
    engine = AlertEngine(dispatcher=OperationsAlertDispatcher(channel=channel))
    alert = engine.process_delta(_delta("asset-queue", "New finding: open bucket"))
    assert alert.dispatched is False
    assert alert.dispatch_queued is True
    assert channel.calls == []  # nothing was even attempted


def test_dispatch_failure_never_breaks_alert_creation():
    engine = AlertEngine(dispatcher=OperationsAlertDispatcher(channel=ExplodingChannel()))
    alert = engine.process_delta(_delta("asset-boom", "New finding: drift"))
    assert alert.alert_id
    assert alert.dispatched is False


class _Receiver(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):  # noqa: N802 (http.server API)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        type(self).received.append(json.loads(body.decode("utf-8")))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):  # silence test server
        pass


@pytest.fixture()
def receiver():
    _Receiver.received = []
    server = HTTPServer(("127.0.0.1", 0), _Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/hook"
    server.shutdown()


def test_registered_webhook_receives_real_http_post(receiver):
    channel = FakeChannel(configured=False)
    engine = AlertEngine(dispatcher=OperationsAlertDispatcher(channel=channel))
    engine.register_webhook(receiver)
    alert = engine.process_delta(_delta("asset-hook", "New finding: webhook me"))
    assert alert.dispatched is True
    assert alert.dispatch_channels == [f"webhook:{receiver}"]
    assert len(_Receiver.received) == 1
    assert _Receiver.received[0]["alert_id"] == alert.alert_id


def test_default_dispatcher_uses_shared_approval_channel(receiver, monkeypatch):
    """The production dispatcher resolves the Discord webhook through the
    same SEN-006 credential path as approvals (env first) and delivers a
    real HTTP POST through the approval dispatcher's transport."""
    import sentinel.gatekeeper.approval_dispatcher as approval_module

    monkeypatch.setenv("DISCORD_WEBHOOK_URL", receiver)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(approval_module, "_FILE_ENV_CACHE", {})

    dispatcher = OperationsAlertDispatcher()  # default: approval singleton
    assert dispatcher.channel_configured is True

    engine = AlertEngine(dispatcher=dispatcher)
    alert = engine.process_delta(_delta("asset-shared", "New finding: shared channel"))
    assert alert.dispatched is True
    assert alert.dispatch_channels == ["discord"]
    assert len(_Receiver.received) == 1
    payload = _Receiver.received[0]
    assert "SENTINEL OPERATIONS ALERT" in payload["content"]
    assert payload["embeds"][0]["title"] == alert.title


def _snapshot(target: str, findings: list[str], snap_id: str) -> SecurityBaselineSnapshot:
    return SecurityBaselineSnapshot(
        snapshot_id=snap_id,
        target_ref=target,
        open_ports=[443],
        dns_records={"A": ["10.0.0.1"]},
        active_findings=findings,
        cert_expiry_days=90,
    )


async def test_scheduler_run_loop_executes_due_jobs_and_alerts():
    target = "asset-loop"
    snapshots = [
        _snapshot(target, [], "loop-1"),               # baseline: no deltas
        _snapshot(target, ["finding-1"], "loop-2"),    # new finding -> alert
        _snapshot(target, ["finding-1"], "loop-3"),    # steady state
    ]
    calls = {"n": 0}

    def provider(job):
        snap = snapshots[min(calls["n"], len(snapshots) - 1)]
        calls["n"] += 1
        return snap

    scheduler = AssessmentScheduler(snapshot_provider=provider, tick_seconds=0.05)
    job = scheduler.add_monitoring_job("job-loop", "Loop watch", target, interval_seconds=1)
    scheduler.start()
    try:
        deadline = time.time() + 5
        while time.time() < deadline and job.run_count < 2:
            await __import__("asyncio").sleep(0.05)
    finally:
        await scheduler.stop()
    assert scheduler.is_running is False
    assert job.run_count >= 2
    assert calls["n"] >= 2


async def test_scheduler_escalates_after_repeated_probe_failures():
    from sentinel.modules.operations.alerting import alert_engine

    target = "asset-failing"

    def bad_provider(job):
        raise RuntimeError("probe exploded")

    scheduler = AssessmentScheduler(
        snapshot_provider=bad_provider, tick_seconds=0.05, failure_escalation_threshold=2
    )
    job = scheduler.add_monitoring_job("job-fail", "Failing watch", target, interval_seconds=1)
    await scheduler.run_due_jobs()
    # A failed job retries at its normal interval (no hot loop); advance the
    # due time to simulate the next scheduled attempt.
    job.next_run = datetime.now(UTC) - timedelta(seconds=1)
    await scheduler.run_due_jobs()
    assert job.failure_count == 2
    escalations = [
        a for a in alert_engine.list_alerts(target_ref=target)
        if "failed 2 consecutive times" in a.message
    ]
    assert len(escalations) == 1
