"""TASK-FRD-028: the G7/G8 self-report goes through the owner-notify gate.

The daily (21:00 IST) and weekly (Sunday 20:00 IST) reports were the last
ungated direct Telegram path in ``friday.proactive`` (PR #1071 review,
condition 1). This suite pins the wiring, each case driven through a REAL
``OwnerNotifier`` (fake clock + recording sender) so the behaviour proven
is the gate's, not a mock's:

- both reports are offered at ``Severity.REPORT`` with a per-day event
  key (``self_report:daily:<date>`` / ``self_report:weekly:<date>``) and
  reach the owner;
- the gate's kill switch, daily cap and per-key cooldown hold the
  reports, and a held report latches for the day (never re-offered
  every tick), exactly like the agent_watch scheduler;
- a failed or unconfigured send does NOT latch — the next cycle retries;
- nothing is offered outside the windows, and no direct
  ``send_owner_message`` call remains in the module (bypass audit).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from friday.core.owner_time import OWNER_TZ
from friday.proactive import daily_self_report as dsr
from friday.proactive.owner_notify import (
    NotifyResult,
    OwnerNotifier,
    Severity,
)


class FakeClock:
    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class GateHarness:
    """A real OwnerNotifier whose notify() calls are also recorded."""

    def __init__(self, tmp_path, sender_result=True, configured=None, **overrides):
        self.sent: list[str] = []
        self.calls: list[dict] = []
        self._sender_result = sender_result
        params = dict(
            per_key_cooldown_seconds=6 * 3600.0,
            text_dedupe_seconds=3600.0,
            global_floor_seconds=0.0,
            daily_cap=20,
        )
        params.update(overrides)
        self.clock = FakeClock()
        self.notifier = OwnerNotifier(
            sender=self._send,
            configured=configured,
            state_path=str(tmp_path / "gate_state.json"),
            clock=self.clock,
            **params,
        )

    def _send(self, text: str) -> bool:
        self.sent.append(text)
        return self._sender_result

    def notify(self, text, *, severity, event_key=""):
        self.calls.append(
            {"text": text, "severity": severity, "event_key": event_key}
        )
        return self.notifier.notify(text, severity=severity, event_key=event_key)


def _stub_stats(monkeypatch):
    monkeypatch.setattr(dsr, "_conversation_stats", lambda: {"total": 0, "failed": 0})
    monkeypatch.setattr(dsr, "_task_ledger_stats", lambda: {"total": 0, "by_agent": {}})
    monkeypatch.setattr(dsr, "_fleet_stats", lambda: {"total": 9, "reachable": 9, "last_error": None})
    monkeypatch.setattr(dsr, "_mission_stats", lambda: {"pending": 0, "line": ""})
    monkeypatch.setattr(dsr, "_memory_growth", lambda: {"stored_today": 0})


@pytest.fixture(autouse=True)
def _reset_latches():
    dsr.reset_for_tests()
    yield
    dsr.reset_for_tests()


class TestSelfReportGate:
    def test_daily_report_goes_through_the_gate_at_report_severity(
        self, tmp_path, monkeypatch
    ):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(dsr, "notify_owner", gate.notify)
        _stub_stats(monkeypatch)
        evening = datetime(2026, 11, 11, 21, 30, tzinfo=OWNER_TZ)

        r1 = dsr.maybe_deliver_reports(now=evening)
        assert r1["daily"] == "sent"
        assert len(gate.calls) == 1
        assert gate.calls[0]["severity"] is Severity.REPORT
        assert gate.calls[0]["event_key"] == f"self_report:daily:{dsr._today()}"
        assert len(gate.sent) == 1 and "End of day" in gate.sent[0]

        # Latched: the second tick inside the window offers nothing.
        r2 = dsr.maybe_deliver_reports(now=evening.replace(minute=45))
        assert r2["daily"] is None
        assert len(gate.calls) == 1

    def test_weekly_report_goes_through_the_gate_then_daily_follows(
        self, tmp_path, monkeypatch
    ):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(dsr, "notify_owner", gate.notify)
        _stub_stats(monkeypatch)

        sun_early = datetime(2026, 11, 15, 20, 30, tzinfo=OWNER_TZ)
        assert sun_early.weekday() == 6
        r = dsr.maybe_deliver_reports(now=sun_early)
        assert r["weekly"] == "sent" and r["daily"] is None
        assert gate.calls[0]["severity"] is Severity.REPORT
        assert gate.calls[0]["event_key"] == f"self_report:weekly:{dsr._today()}"
        assert len(gate.sent) == 1 and "Sunday roll-up" in gate.sent[0]

        sun_late = datetime(2026, 11, 15, 21, 30, tzinfo=OWNER_TZ)
        r = dsr.maybe_deliver_reports(now=sun_late)
        assert r["weekly"] is None and r["daily"] == "sent"
        assert gate.calls[1]["severity"] is Severity.REPORT
        assert gate.calls[1]["event_key"] == f"self_report:daily:{dsr._today()}"
        assert len(gate.sent) == 2

    def test_no_delivery_outside_window(self, tmp_path, monkeypatch):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(dsr, "notify_owner", gate.notify)
        _stub_stats(monkeypatch)
        morning = datetime(2026, 11, 11, 10, 0, tzinfo=OWNER_TZ)

        assert dsr.maybe_deliver_reports(now=morning)["daily"] is None
        assert gate.calls == [] and gate.sent == []

    def test_kill_switch_holds_and_latches_the_report(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("FRIDAY_OWNER_NOTIFY", "off")
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(dsr, "notify_owner", gate.notify)
        _stub_stats(monkeypatch)
        evening = datetime(2026, 11, 11, 21, 30, tzinfo=OWNER_TZ)

        r1 = dsr.maybe_deliver_reports(now=evening)
        assert r1["daily"] == "held:disabled"
        assert gate.sent == []
        # Held, not failed: latched for the day, never re-offered.
        r2 = dsr.maybe_deliver_reports(now=evening.replace(minute=45))
        assert r2["daily"] is None
        assert len(gate.calls) == 1

    def test_daily_cap_holds_and_latches_the_report(
        self, tmp_path, monkeypatch
    ):
        gate = GateHarness(tmp_path, daily_cap=1)
        monkeypatch.setattr(dsr, "notify_owner", gate.notify)
        _stub_stats(monkeypatch)
        # One unrelated alert consumes the whole day's cap first.
        assert (
            gate.notify("Stratex is down", severity=Severity.ALERT, event_key="fleet_down:stratex")
            is NotifyResult.SENT
        )
        evening = datetime(2026, 11, 11, 21, 30, tzinfo=OWNER_TZ)

        r1 = dsr.maybe_deliver_reports(now=evening)
        assert r1["daily"] == "held:daily_cap"
        assert len(gate.sent) == 1  # the alert only; the report never went
        r2 = dsr.maybe_deliver_reports(now=evening.replace(minute=45))
        assert r2["daily"] is None
        assert len(gate.calls) == 2  # no re-offer after the hold

    def test_repeat_offer_inside_the_key_cooldown_is_held(
        self, tmp_path, monkeypatch
    ):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(dsr, "notify_owner", gate.notify)
        _stub_stats(monkeypatch)
        evening = datetime(2026, 11, 11, 21, 30, tzinfo=OWNER_TZ)

        assert dsr.maybe_deliver_reports(now=evening)["daily"] == "sent"
        # The latch is reset (fresh process thinking it is a new day is
        # simulated by reset_for_tests) but the gate still holds the
        # same per-day key inside its 6h cooldown.
        dsr.reset_for_tests()
        r = dsr.maybe_deliver_reports(now=evening.replace(minute=45))
        assert r["daily"] == "held:cooldown"
        assert len(gate.sent) == 1
        # The hold itself latches: no third offer this evening.
        assert dsr.maybe_deliver_reports(now=evening.replace(minute=50))["daily"] is None
        assert len(gate.calls) == 2

    def test_failed_send_does_not_latch(self, tmp_path, monkeypatch):
        gate = GateHarness(tmp_path, sender_result=False)
        monkeypatch.setattr(dsr, "notify_owner", gate.notify)
        _stub_stats(monkeypatch)
        evening = datetime(2026, 11, 11, 21, 30, tzinfo=OWNER_TZ)

        r1 = dsr.maybe_deliver_reports(now=evening)
        assert r1["daily"] == "send_failed"
        # Next cycle retries because nothing was delivered.
        r2 = dsr.maybe_deliver_reports(now=evening.replace(minute=45))
        assert r2["daily"] == "send_failed"
        # Both cycles offered to the gate (the latch never engaged);
        # the recording sender was asked twice and failed both times.
        assert len(gate.calls) == 2 and len(gate.sent) == 2

    def test_not_configured_does_not_latch(self, tmp_path, monkeypatch):
        gate = GateHarness(tmp_path, configured=lambda: False)
        monkeypatch.setattr(dsr, "notify_owner", gate.notify)
        _stub_stats(monkeypatch)
        evening = datetime(2026, 11, 11, 21, 30, tzinfo=OWNER_TZ)

        r1 = dsr.maybe_deliver_reports(now=evening)
        assert r1["daily"] == "not_configured"
        r2 = dsr.maybe_deliver_reports(now=evening.replace(minute=45))
        assert r2["daily"] == "not_configured"
        assert len(gate.calls) == 2 and gate.sent == []

    def test_no_direct_telegram_send_remains(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "friday"
            / "proactive"
            / "daily_self_report.py"
        ).read_text(encoding="utf-8")
        assert "send_owner_message" not in source  # bypass audit: gate only
        assert "notify_owner" in source
        assert "Severity.REPORT" in source


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
