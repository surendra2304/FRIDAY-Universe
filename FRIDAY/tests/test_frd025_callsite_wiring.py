"""TASK-FRD-025 call-site wiring: the severity gate is no longer inert.

PR #953 built the gate (``friday.proactive.owner_notify``) but no
production caller routed through it, so in production it decided
nothing. This suite pins the wiring for the three call-site classes
named in the gate's own docstring, each driven through a REAL
``OwnerNotifier`` (fake clock + recording sender) so the behaviour
proven is the gate's, not a mock's:

- autonomous daemon findings: ``DaemonTaskSource`` offers every seeded
  finding as ALERT (healthy state offers nothing), and the daemon
  offers a finished source-seeded goal's report — ALERT when it
  FAILED/PARTIAL, ROUTINE when it completed; owner-submitted goals are
  never offered at all;
- fleet alerts: the agent_watch site sweep is ALERT only when it found
  degradation (healthy = ROUTINE, held as ``below_bar`` with
  ``gate_held`` set, and the scheduler keeps its latch on a held
  result); the watchlist briefing is ROUTINE; the Sentinel digest is
  ROUTINE unless Sentinel was unreachable, which is ALERT;
- trade events: a fired market alert rule is ALERT and reaches the
  owner, the daily portfolio report is ROUTINE, and StratexWatcher
  trade events keep posting to the NotificationManager while the gate
  admits only the breaker / kill-criterion / measurement events to
  Telegram (trade opens/closes are ROUTINE).

An injected ``deliver`` callable keeps the pre-gate behaviour — that
contract is covered by the batch6/batch7 suites and is not repeated
here beyond the alert-check latch they already pin.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from friday.autonomous import task_source
from friday.autonomous.daemon import AutonomousDaemon, AutonomousGoal
from friday.autonomous.task_source import DaemonTaskSource
from friday.core.owner_time import OWNER_TZ
from friday.proactive import agent_watch as aw
from friday.proactive import market_watch as mw
from friday.proactive import owner_notify
from friday.proactive import stratex_watch as sw
from friday.proactive.owner_notify import NotifyResult, OwnerNotifier


# ---------------------------------------------------------------------------
# a real gate with a fake clock + recording sender, plus a call recorder
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class GateHarness:
    """A real OwnerNotifier whose notify() calls are also recorded."""

    def __init__(self, tmp_path):
        self.sent: list[str] = []
        self.calls: list[dict] = []
        self.notifier = OwnerNotifier(
            sender=lambda text: self.sent.append(text) or True,
            state_path=str(tmp_path / "gate_state.json"),
            clock=FakeClock(),
            per_key_cooldown_seconds=6 * 3600.0,
            text_dedupe_seconds=3600.0,
            global_floor_seconds=0.0,
            daily_cap=20,
        )

    def notify(self, text, *, severity, event_key=""):
        self.calls.append(
            {"text": text, "severity": severity, "event_key": event_key}
        )
        return self.notifier.notify(text, severity=severity, event_key=event_key)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# 1. autonomous daemon findings — the task source
# ---------------------------------------------------------------------------


class _FakeGoal:
    def __init__(self, text, priority=0, metadata=None):
        self.id = f"goal_{abs(hash(text)) % 10_000_000}"
        self.goal = text
        self.priority = priority
        self.metadata = metadata or {}
        self.status = "QUEUED"
        self.completed_at = 0.0


class _FakeDaemon:
    def __init__(self):
        self._goal_queue: list = []
        self._running_goals: dict = {}
        self._completed_goals: list = []
        self.submitted: list[_FakeGoal] = []

    def submit_goal(self, goal_text, priority=0, metadata=None):
        goal = _FakeGoal(goal_text, priority, metadata)
        self.submitted.append(goal)
        return goal


@pytest.fixture()
def _flag_on(monkeypatch):
    monkeypatch.setattr(
        task_source,
        "get_settings",
        lambda: SimpleNamespace(autonomous_mode=True),
    )
    monkeypatch.delenv("FRIDAY_AUTONOMOUS_TASK_SOURCE", raising=False)


def _status(agent_id="stratex", status="UNREACHABLE", name="Stratex"):
    return SimpleNamespace(
        id=agent_id,
        name=name,
        status=status,
        details="probe failed",
        last_checked="2026-11-18T00:00:00+00:00",
    )


class TestTaskSourceFindings:
    def test_unhealthy_fleet_agent_seeds_and_alerts_the_owner(self, tmp_path, _flag_on):
        gate = GateHarness(tmp_path)

        async def fleet():
            return [_status()]

        src = DaemonTaskSource(
            state_path=tmp_path / "ts.json",
            fleet_statuses=fleet,
            stratex_heartbeat_age_s=lambda: None,
            notify_fn=gate.notify,
        )
        daemon = _FakeDaemon()
        seeded = _run(src.maybe_seed(daemon))
        assert len(seeded) == 1 and len(daemon.submitted) == 1
        # The finding reached the owner exactly once, as ALERT, keyed by
        # the seed's own trigger key.
        assert len(gate.calls) == 1
        assert gate.calls[0]["severity"] == owner_notify.Severity.ALERT
        assert gate.calls[0]["event_key"] == "fleet_agent_unhealthy:stratex"
        assert len(gate.sent) == 1
        assert "stratex" in gate.sent[0] and "UNREACHABLE" in gate.sent[0]

    def test_healthy_fleet_offers_nothing(self, tmp_path, _flag_on):
        gate = GateHarness(tmp_path)

        async def fleet():
            return [_status("memora", "ONLINE", "Memora")]

        src = DaemonTaskSource(
            state_path=tmp_path / "ts.json",
            fleet_statuses=fleet,
            stratex_heartbeat_age_s=lambda: None,
            notify_fn=gate.notify,
        )
        assert _run(src.maybe_seed(_FakeDaemon())) == []
        assert gate.calls == [] and gate.sent == []

    def test_stale_stratex_heartbeat_alerts(self, tmp_path, _flag_on):
        gate = GateHarness(tmp_path)

        async def fleet():
            return []

        src = DaemonTaskSource(
            state_path=tmp_path / "ts.json",
            fleet_statuses=fleet,
            stratex_heartbeat_age_s=lambda: 3600.0,
            notify_fn=gate.notify,
        )
        seeded = _run(src.maybe_seed(_FakeDaemon()))
        assert len(seeded) == 1
        assert len(gate.sent) == 1 and "Stratex" in gate.sent[0]
        assert gate.calls[0]["event_key"] == "stratex_heartbeat_stale"

    def test_gate_failure_never_blocks_seeding(self, tmp_path, _flag_on):
        def boom(text, *, severity, event_key=""):
            raise RuntimeError("gate down")

        async def fleet():
            return [_status()]

        src = DaemonTaskSource(
            state_path=tmp_path / "ts.json",
            fleet_statuses=fleet,
            stratex_heartbeat_age_s=lambda: None,
            notify_fn=boom,
        )
        daemon = _FakeDaemon()
        assert len(_run(src.maybe_seed(daemon))) == 1  # seeding survived


# ---------------------------------------------------------------------------
# 1b. autonomous daemon findings — finished source-seeded goals
# ---------------------------------------------------------------------------


class TestDaemonFinishFindings:
    def _daemon_with_gate(self, tmp_path, monkeypatch):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(owner_notify, "notify_owner", gate.notify)
        return AutonomousDaemon(), gate

    def _goal(self, *, status, metadata, summary="It confirmed the finding."):
        goal = AutonomousGoal(id="goal_test_1", goal="verify something", metadata=metadata)
        goal.status = status
        goal.summary = summary
        return goal

    def test_failed_source_goal_alerts(self, tmp_path, monkeypatch):
        daemon, gate = self._daemon_with_gate(tmp_path, monkeypatch)
        goal = self._goal(
            status="FAILED",
            metadata={
                "source": "autonomous_task_source",
                "trigger": "fleet_agent_unhealthy",
                "trigger_key": "fleet_agent_unhealthy:stratex",
            },
        )
        _run(daemon._finish_goal(goal))
        assert len(gate.calls) == 1
        assert gate.calls[0]["severity"] == owner_notify.Severity.ALERT
        assert gate.calls[0]["event_key"] == "fleet_agent_unhealthy:stratex"
        assert len(gate.sent) == 1

    def test_completed_source_goal_is_routine_and_held(self, tmp_path, monkeypatch):
        daemon, gate = self._daemon_with_gate(tmp_path, monkeypatch)
        goal = self._goal(
            status="COMPLETED",
            metadata={
                "source": "autonomous_task_source",
                "trigger": "stratex_heartbeat_stale",
                "trigger_key": "stratex_heartbeat_stale",
            },
        )
        _run(daemon._finish_goal(goal))
        assert len(gate.calls) == 1  # offered…
        assert gate.calls[0]["severity"] == owner_notify.Severity.ROUTINE
        assert gate.sent == []  # …but the gate held it below the bar

    def test_owner_submitted_goal_is_never_offered(self, tmp_path, monkeypatch):
        daemon, gate = self._daemon_with_gate(tmp_path, monkeypatch)
        goal = self._goal(status="FAILED", metadata={})
        _run(daemon._finish_goal(goal))
        assert gate.calls == [] and gate.sent == []


# ---------------------------------------------------------------------------
# 2. fleet alerts — agent_watch
# ---------------------------------------------------------------------------


def _fake_fleet_client(monkeypatch):
    import friday.ecosystem.fleet_client as fc

    class FakeClient:
        async def request_cortex_web_ops(self):
            return {"reply": "Cortex summary line"}

        async def aclose(self):
            pass

    monkeypatch.setattr(fc, "FleetClient", FakeClient)


class TestSiteSweepGate:
    def test_degraded_sweep_alerts_the_owner(self, tmp_path, monkeypatch):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(aw, "notify_owner", gate.notify)
        _fake_fleet_client(monkeypatch)

        async def mixed_probe(url: str):
            ok = "sentinel" not in url
            return ok, (200 if ok else 0), ("200 in 0.1s" if ok else "unreachable (ConnectError)")

        r = _run(aw.run_site_health_sweep(probe_fn=mixed_probe))
        assert r["degraded"] == ["sentinel: unreachable (ConnectError)"]
        assert r["delivered"] is True
        assert r["notify_result"] == NotifyResult.SENT.value
        assert r["gate_held"] is False
        assert len(gate.sent) == 1 and "DEGRADED" in gate.sent[0]
        assert gate.calls[0]["severity"] == owner_notify.Severity.ALERT

    def test_healthy_sweep_is_routine_and_held(self, tmp_path, monkeypatch):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(aw, "notify_owner", gate.notify)
        _fake_fleet_client(monkeypatch)

        async def healthy_probe(url: str):
            return True, 200, "200 in 0.12s"

        r = _run(aw.run_site_health_sweep(probe_fn=healthy_probe))
        assert r["healthy"] == r["checked"]
        assert len(gate.calls) == 1
        assert gate.calls[0]["severity"] == owner_notify.Severity.ROUTINE
        assert gate.sent == []  # nothing reached Telegram
        assert r["delivered"] is False
        assert r["notify_result"] == NotifyResult.BELOW_BAR.value
        assert r["gate_held"] is True


class TestWatchlistAndSentinelGate:
    def test_watchlist_briefing_is_routine(self, tmp_path, monkeypatch):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(aw, "notify_owner", gate.notify)
        store = aw.WatchlistStore(str(tmp_path / "watch" / "watchlist.json"))
        monkeypatch.setattr(aw, "watchlist_store", store)
        store.add_topic("crude oil")

        async def brief(topic: str):
            return "Demand outlook improved in Asia\nOPEC supply steady\n"

        r = _run(aw.run_watchlist_briefing(brief_fn=brief))
        assert r["topics"] == 1
        assert gate.calls and gate.calls[0]["severity"] == owner_notify.Severity.ROUTINE
        assert gate.sent == []
        assert r["gate_held"] is True and r["delivered"] is False

    def test_sentinel_digest_is_routine(self, tmp_path, monkeypatch):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(aw, "notify_owner", gate.notify)

        async def fake_sentinel():
            return (
                {"reply": "Posture score 87/100. Critical: 0. Read-only surface."},
                {"reply": "2 open findings: 1 medium (TLS-2026), 1 low (banner)."},
            )

        r = _run(aw.run_sentinel_digest(sentinel_fn=fake_sentinel))
        assert gate.calls[0]["severity"] == owner_notify.Severity.ROUTINE
        assert gate.sent == [] and r["gate_held"] is True

    def test_sentinel_unreachable_is_an_alert(self, tmp_path, monkeypatch):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(aw, "notify_owner", gate.notify)

        async def broken():
            raise RuntimeError("sentinel down")

        r = _run(aw.run_sentinel_digest(sentinel_fn=broken))
        assert gate.calls[0]["severity"] == owner_notify.Severity.ALERT
        assert len(gate.sent) == 1 and "could not reach Sentinel" in gate.sent[0]
        assert r["delivered"] is True and r["gate_held"] is False


class TestTickLatchWithGate:
    def test_held_result_keeps_the_latch(self):
        aw.reset_latches_for_tests()
        calls: list[int] = []

        async def held_site():
            calls.append(1)
            return {"delivered": False, "gate_held": True}

        async def noop():
            return {"delivered": True}

        morning = datetime(2026, 11, 12, 8, 30, tzinfo=OWNER_TZ)
        _run(aw.agent_watch_tick(now=morning, site_coro_factory=held_site, watch_coro_factory=noop, sentinel_coro_factory=noop, portfolio_coro_factory=noop, alert_coro_factory=noop, forecast_coro_factory=noop, prediction_coro_factory=noop))
        _run(aw.agent_watch_tick(now=morning, site_coro_factory=held_site, watch_coro_factory=noop, sentinel_coro_factory=noop, portfolio_coro_factory=noop, alert_coro_factory=noop, forecast_coro_factory=noop, prediction_coro_factory=noop))
        assert len(calls) == 1  # held by the gate: latched, not re-offered
        aw.reset_latches_for_tests()

    def test_unheld_failure_still_unlatches(self):
        aw.reset_latches_for_tests()
        calls: list[int] = []

        async def failing_site():
            calls.append(1)
            return {"delivered": False, "gate_held": False}

        async def noop():
            return {"delivered": True}

        morning = datetime(2026, 11, 12, 8, 30, tzinfo=OWNER_TZ)
        _run(aw.agent_watch_tick(now=morning, site_coro_factory=failing_site, watch_coro_factory=noop, sentinel_coro_factory=noop, portfolio_coro_factory=noop, alert_coro_factory=noop, forecast_coro_factory=noop, prediction_coro_factory=noop))
        _run(aw.agent_watch_tick(now=morning, site_coro_factory=failing_site, watch_coro_factory=noop, sentinel_coro_factory=noop, portfolio_coro_factory=noop, alert_coro_factory=noop, forecast_coro_factory=noop, prediction_coro_factory=noop))
        assert len(calls) == 2  # retry-worthy failure: unlatched
        aw.reset_latches_for_tests()


# ---------------------------------------------------------------------------
# 3. trade events — market_watch
# ---------------------------------------------------------------------------


class TestMarketWatchGate:
    def test_fired_alert_rule_reaches_the_owner(self, tmp_path, monkeypatch):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(mw, "notify_owner", gate.notify)
        store = mw.AlertStore(str(tmp_path / "alerts.json"))
        monkeypatch.setattr(mw, "alert_store", store)
        store.add(mw.AlertRule("BTC", "above", 100000))

        async def fake_query(symbol: str):
            return {"signals": [{"symbol": "BTC", "price": 100500}]}

        r = _run(mw.run_alert_check(query_fn=fake_query))
        assert r["fired"] == 1 and r["deliveries"] == 1
        assert r["notify_results"] == [NotifyResult.SENT.value]
        assert len(gate.sent) == 1 and "Alert fired" in gate.sent[0]
        assert gate.calls[0]["severity"] == owner_notify.Severity.ALERT
        assert gate.calls[0]["event_key"].startswith("market_alert:")

    def test_daily_portfolio_report_is_routine(self, tmp_path, monkeypatch):
        gate = GateHarness(tmp_path)
        monkeypatch.setattr(mw, "notify_owner", gate.notify)

        async def snapshot():
            return "Balance $20,549. 3 open positions."

        r = _run(mw.run_daily_portfolio_report(snapshot_fn=snapshot))
        assert gate.calls[0]["severity"] == owner_notify.Severity.ROUTINE
        assert gate.sent == []
        assert r["delivered"] is False
        assert r["notify_result"] == NotifyResult.BELOW_BAR.value
        assert r["gate_held"] is True


# ---------------------------------------------------------------------------
# 3b. trade events — StratexWatcher (NotificationManager + gate)
# ---------------------------------------------------------------------------


class _FakeNotifications:
    def __init__(self):
        self.posted = []

    def post_notification(self, message, category="x", severity="info", metadata=None, notification_id=None):
        self.posted.append(
            {"message": message, "category": category, "severity": severity, "metadata": metadata or {}}
        )
        return f"id-{len(self.posted)}"


def _at(hour: int, minute: int = 0, day: int = 15) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=OWNER_TZ)


def _tag(order_id="ord-1"):
    return {
        "record_type": "POSITION_TAG", "ts": 1763200000.0, "engine": "multi_venue",
        "venue": "binance_demo", "symbol": "BTCUSDT",
        "strategy": "strategy_ichimoku_trend", "side": "LONG", "qty": 0.01,
        "entry_price": 97432.5, "order_id": order_id, "client_order_id": "",
    }


def _heartbeat(hit=False):
    return {
        "status": "RUNNING", "timestamp": "2026-11-15T02:00:00Z",
        "total_equity": 10792.80, "daily_start_equity": 10559.09,
        "daily_loss_limit_hit": hit, "open_positions": 0,
        "measurement_alerts": [],
    }


class _StratexWorld:
    def __init__(self, tmp_path, gate):
        self.dir = tmp_path / "stratex_state"
        self.dir.mkdir()
        self.paths = sw.StratexPaths(
            fills=self.dir / "fill_ledger.jsonl",
            tags=self.dir / "position_tags.jsonl",
            alerts=self.dir / "measurement_alerts.json",
            denylist=self.dir / "strategy_denylist.json",
            heartbeat=self.dir / "daemon_heartbeat.json",
        )
        self.notifications = _FakeNotifications()
        self.watcher = sw.StratexWatcher(
            paths=self.paths,
            state_path=tmp_path / "watcher_state.json",
            enabled_fn=lambda: True,
            notify_fn=gate.notify,
        )

    def write(self, *, tags=(), fills=(), denylist=(), heartbeat=None, alerts=None):
        self.paths.tags.write_text("".join(json.dumps(r) + "\n" for r in tags), encoding="utf-8")
        self.paths.fills.write_text("".join(json.dumps(r) + "\n" for r in fills), encoding="utf-8")
        self.paths.denylist.write_text(json.dumps(list(denylist)), encoding="utf-8")
        self.paths.heartbeat.write_text(json.dumps(heartbeat or _heartbeat()), encoding="utf-8")
        self.paths.alerts.write_text(json.dumps({"alerts": alerts or {}}), encoding="utf-8")

    def cycle(self, now):
        return self.watcher.run_cycle(self.notifications, now=now)

    def triggers(self):
        return [p["metadata"].get("trigger") for p in self.notifications.posted]


class TestStratexWatchGate:
    def test_trade_open_posts_in_app_but_is_routine_for_telegram(self, tmp_path):
        gate = GateHarness(tmp_path)
        world = _StratexWorld(tmp_path, gate)
        world.write()
        world.cycle(_at(14))  # silent baseline
        world.write(tags=[_tag()])
        world.cycle(_at(14, 5))
        # In-app notification still posted exactly as before…
        assert world.triggers() == ["trade_opened"]
        # …and the gate was offered it as ROUTINE and held it.
        assert len(gate.calls) == 1
        assert gate.calls[0]["severity"] == owner_notify.Severity.ROUTINE
        assert gate.calls[0]["event_key"].startswith("stratex:tag:")
        assert gate.sent == []
        log = world.watcher._load_state()["alert_log"]
        assert log[-1]["owner_notify"] == NotifyResult.BELOW_BAR.value

    def test_daily_breaker_trips_straight_to_the_owner(self, tmp_path):
        gate = GateHarness(tmp_path)
        world = _StratexWorld(tmp_path, gate)
        world.write()
        world.cycle(_at(14))
        world.write(heartbeat=_heartbeat(hit=True))
        world.cycle(_at(14, 5))
        assert world.triggers() == ["daily_breaker_tripped"]
        assert len(gate.sent) == 1 and "DAILY LOSS BREAKER" in gate.sent[0]
        assert gate.calls[0]["severity"] == owner_notify.Severity.ALERT

    def test_kill_criterion_alerts_the_owner(self, tmp_path):
        gate = GateHarness(tmp_path)
        world = _StratexWorld(tmp_path, gate)
        world.write()
        world.cycle(_at(14))
        world.write(denylist=["strategy_ichimoku_trend"])
        world.cycle(_at(14, 5))
        assert world.triggers() == ["kill_criterion_tripped"]
        assert len(gate.sent) == 1 and "KILL CRITERION" in gate.sent[0]
        assert gate.calls[0]["severity"] == owner_notify.Severity.ALERT

    def test_measurement_alert_alerts_the_owner(self, tmp_path):
        gate = GateHarness(tmp_path)
        world = _StratexWorld(tmp_path, gate)
        world.write()
        world.cycle(_at(14))
        world.write(alerts={"unrecorded_close": {"active": True, "detail": "fill append failed", "count": 1}})
        world.cycle(_at(14, 5))
        assert world.triggers() == ["measurement_alert"]
        assert len(gate.sent) == 1
        assert gate.calls[0]["severity"] == owner_notify.Severity.ALERT


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
