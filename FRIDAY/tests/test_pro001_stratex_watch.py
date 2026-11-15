"""TASK-PRO-001: proactive Stratex watch.

FRIDAY speaks first about Stratex: trade opens/closes, kill-criterion
trips, daily-breaker trips and measurement alerts become proactive
notifications through the real NotificationManager path, and FRIDAY
composes + stores a morning self-check (fleet health + Stratex state)
itself, once per day.

Rules pinned here:
- first cycle on a fresh watcher state is a silent baseline;
- dedupe: a re-cycle never posts the same event twice (also across a
  watcher restart, via the persisted state file);
- quiet hours 23:00-07:00 IST hold everything except breaker trips;
  held events flush as ONE digest after 07:00;
- kill switch off -> no posts, no state churn;
- every figure in a message comes from the fixture rows (no invention);
- a shrinking ledger re-baselines silently;
- an unreadable source skips its diff instead of re-arming alerts.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

from friday.core.owner_time import OWNER_TZ
from friday.proactive import stratex_watch as sw


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


def _tag(strategy="strategy_ichimoku_trend", symbol="BTCUSDT", order_id="ord-1", **kw):
    row = {
        "record_type": "POSITION_TAG",
        "ts": 1763200000.0,
        "engine": "multi_venue",
        "venue": "binance_demo",
        "symbol": symbol,
        "strategy": strategy,
        "side": "LONG",
        "qty": 0.01,
        "entry_price": 97432.5,
        "order_id": order_id,
        "client_order_id": "",
    }
    row.update(kw)
    return row


def _fill(strategy="strategy_ichimoku_trend", symbol="BTCUSDT", order_id="ord-1", net=12.34, **kw):
    row = {
        "record_type": "FILL",
        "strategy": strategy,
        "engine": "multi_venue",
        "venue": "binance_demo",
        "symbol": symbol,
        "side": "LONG",
        "entry_price": 97432.5,
        "exit_price": 98100.0,
        "qty": 0.01,
        "gross_pnl": 13.0,
        "fees": 0.66,
        "net_pnl": net,
        "fees_source": "broker",
        "exit_reason": "TP",
        "entry_time": 1763200000.0,
        "exit_time": 1763203600.0,
        "order_id": order_id,
        "entry_order_id": order_id,
    }
    row.update(kw)
    return row


def _heartbeat(hit=False, **kw):
    payload = {
        "status": "RUNNING",
        "timestamp": "2026-11-15T02:00:00Z",
        "total_equity": 10792.80,
        "daily_start_equity": 10559.09,
        "daily_loss_limit_hit": hit,
        "open_positions": 0,
        "measurement_alerts": [],
    }
    payload.update(kw)
    return payload


class _World:
    """A synthetic Stratex state dir + watcher wired to it."""

    def __init__(self, tmp_path: Path):
        self.dir = tmp_path / "stratex_state"
        self.dir.mkdir()
        self.paths = sw.StratexPaths(
            fills=self.dir / "fill_ledger.jsonl",
            tags=self.dir / "position_tags.jsonl",
            alerts=self.dir / "measurement_alerts.json",
            denylist=self.dir / "strategy_denylist.json",
            heartbeat=self.dir / "daemon_heartbeat.json",
        )
        self.state_path = tmp_path / "watcher_state.json"
        self.notifications = _FakeNotifications()
        self.watcher = self._new_watcher()

    def _new_watcher(self) -> sw.StratexWatcher:
        return sw.StratexWatcher(
            paths=self.paths,
            state_path=self.state_path,
            enabled_fn=lambda: True,
        )

    def restart(self) -> None:
        self.watcher = self._new_watcher()

    def write_tags(self, rows):
        self.paths.tags.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def write_fills(self, rows):
        self.paths.fills.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def write_denylist(self, names):
        self.paths.denylist.write_text(json.dumps(names), encoding="utf-8")

    def write_heartbeat(self, payload):
        self.paths.heartbeat.write_text(json.dumps(payload), encoding="utf-8")

    def write_alerts(self, alerts):
        self.paths.alerts.write_text(json.dumps({"alerts": alerts}), encoding="utf-8")

    def cycle(self, now):
        return self.watcher.run_cycle(self.notifications, now=now)

    def triggers(self):
        return [p["metadata"].get("trigger") for p in self.notifications.posted]


@pytest.fixture()
def world(tmp_path):
    return _World(tmp_path)


def test_baseline_is_silent(world):
    world.write_tags([_tag()])
    world.write_fills([_fill()])
    world.write_denylist(["strategy_old"])
    world.write_heartbeat(_heartbeat(hit=True))
    report = world.cycle(_at(14))
    assert report["baseline"] is True
    assert report["posted"] == 0
    assert world.notifications.posted == []


def test_open_and_close_events_post_with_real_figures(world):
    world.write_tags([])
    world.write_fills([])
    world.write_heartbeat(_heartbeat())
    world.cycle(_at(14))  # baseline
    world.write_tags([_tag()])
    report = world.cycle(_at(14, 5))
    assert report["posted"] == 1
    post = world.notifications.posted[-1]
    assert post["metadata"]["trigger"] == "trade_opened"
    assert post["metadata"]["source"] == "TASK-PRO-001"
    assert "strategy_ichimoku_trend" in post["message"]
    assert "BTCUSDT" in post["message"]
    assert "97,432.5" in post["message"]

    world.write_fills([_fill(net=12.34), _fill(order_id="ord-2", net=-2.34, exit_reason="SL")])
    report = world.cycle(_at(14, 10))
    assert report["posted"] == 2
    closes = [p for p in world.notifications.posted if p["metadata"]["trigger"] == "trade_closed"]
    assert "+$12.34" in closes[0]["message"]
    assert "Ledger now: 2 closed trades, net +$10.00" in closes[-1]["message"]


def test_dedupe_across_cycles_and_restart(world):
    world.write_tags([])
    world.write_fills([])
    world.cycle(_at(14))
    world.write_tags([_tag()])
    world.cycle(_at(14, 5))
    world.cycle(_at(14, 6))
    world.cycle(_at(14, 7))
    assert world.triggers() == ["trade_opened"]
    world.restart()  # persisted state survives a process restart
    world.cycle(_at(14, 8))
    assert world.triggers() == ["trade_opened"]


def test_kill_criterion_trip_posts_strategy_stats(world):
    fills = [_fill(order_id=f"o{i}", net=-1.0) for i in range(3)]
    world.write_tags([])
    world.write_fills(fills)
    world.write_denylist([])
    world.cycle(_at(14))
    world.write_denylist(["strategy_ichimoku_trend"])
    report = world.cycle(_at(14, 5))
    assert report["posted"] == 1
    post = world.notifications.posted[-1]
    assert post["metadata"]["trigger"] == "kill_criterion_tripped"
    assert post["severity"] == "warning"
    assert "KILL CRITERION TRIPPED" in post["message"]
    assert "auto-paused by Stratex governance" in post["message"]
    assert "3 closed trades" in post["message"]
    assert "-$3.00" in post["message"]
    # latched: no repeat while the name stays on the denylist
    world.cycle(_at(14, 6))
    assert world.triggers().count("kill_criterion_tripped") == 1


def test_breaker_trip_is_critical_and_bypasses_quiet_hours(world):
    world.write_tags([])
    world.write_fills([])
    world.write_heartbeat(_heartbeat(hit=False))
    world.cycle(_at(22, 50))
    world.write_heartbeat(_heartbeat(hit=True, total_equity=10200.0))
    report = world.cycle(_at(23, 30))  # inside quiet hours
    assert report["posted"] == 1
    assert report["held"] == 0
    post = world.notifications.posted[-1]
    assert post["metadata"]["trigger"] == "daily_breaker_tripped"
    assert post["severity"] == "critical"
    assert "$10,559.09" in post["message"]
    assert "$10,200.00" in post["message"]


def test_quiet_hours_hold_and_single_digest_flush(world):
    world.write_tags([])
    world.write_fills([])
    world.write_heartbeat(_heartbeat())
    world.cycle(_at(22, 0))
    world.write_tags([_tag()])
    world.write_fills([_fill()])
    report = world.cycle(_at(23, 15))
    assert report["posted"] == 0
    assert report["held"] == 2
    assert world.notifications.posted == []
    report = world.cycle(_at(7, 15, day=16))
    assert report["flushed"] == 2
    assert report["posted"] == 1  # exactly one digest, not two messages
    digest = world.notifications.posted[-1]
    assert digest["metadata"]["trigger"] == "quiet_hours_digest"
    assert "opened" in digest["message"] and "closed" in digest["message"]
    # nothing left held; a later cycle posts nothing
    world.cycle(_at(13, 0, day=16))
    assert len(world.notifications.posted) == 1


def test_measurement_alert_posts_once_per_detail(world):
    world.write_tags([])
    world.write_fills([])
    world.write_alerts({})
    world.cycle(_at(14))
    world.write_alerts(
        {"unrecorded_close": {"active": True, "detail": "fill append failed for ETHUSDT", "count": 1}}
    )
    world.cycle(_at(14, 5))
    assert world.triggers() == ["measurement_alert"]
    assert "unrecorded_close" in world.notifications.posted[-1]["message"]
    world.cycle(_at(14, 6))  # same alert, unchanged detail: silent
    assert world.triggers() == ["measurement_alert"]


def test_kill_switch_off_posts_nothing(tmp_path):
    world = _World(tmp_path)
    world.watcher = sw.StratexWatcher(
        paths=world.paths, state_path=world.state_path, enabled_fn=lambda: False
    )
    world.write_tags([_tag()])
    report = world.cycle(_at(14))
    assert report["enabled"] is False
    assert world.notifications.posted == []
    assert sw.watch_enabled() is False  # env unset -> code default OFF


def test_morning_summary_stored_once_with_fixture_figures(world, monkeypatch):
    monkeypatch.setattr(sw.StratexWatcher, "_fleet_line", lambda self: "Fleet: all 10 agents healthy.")
    world.write_tags([])
    world.write_fills([_fill(net=195.06), _fill(order_id="ord-2", net=-0.65)])
    world.write_heartbeat(_heartbeat(total_equity=10792.80, open_positions=2))
    world.cycle(_at(7, 45))  # baseline + summary window
    summaries = [p for p in world.notifications.posted if p["metadata"]["trigger"] == "morning_self_check"]
    assert len(summaries) == 1
    body = summaries[0]["message"]
    assert summaries[0]["category"] == "morning_self_check"
    assert "all 10 agents healthy" in body
    assert "$10,792.80" in body
    assert "open positions 2" in body
    assert "2 closed trades, net +$194.41" in body
    world.cycle(_at(8, 30))  # same day: no second summary
    summaries = [p for p in world.notifications.posted if p["metadata"]["trigger"] == "morning_self_check"]
    assert len(summaries) == 1


def test_morning_summary_honest_when_sources_missing(world, monkeypatch):
    monkeypatch.setattr(sw.StratexWatcher, "_fleet_line", lambda self: "Fleet: probe failed.")
    # no heartbeat, no fills files at all
    report = world.cycle(_at(8, 0))
    summaries = [p for p in world.notifications.posted if p["metadata"]["trigger"] == "morning_self_check"]
    assert len(summaries) == 1
    body = summaries[0]["message"]
    assert "could not read the daemon heartbeat" in body
    assert "0 closed trades" in body  # absent ledger reads as empty, stated as zero
    assert report["source_errors"] == []


def test_shrinking_ledger_rebaselines_silently(world):
    world.write_tags([_tag()])
    world.write_fills([_fill()])
    world.cycle(_at(14))
    world.write_tags([])  # state dir reset
    world.write_fills([])
    report = world.cycle(_at(14, 5))
    assert report["baseline"] is True
    assert world.notifications.posted == []


def test_unreadable_denylist_does_not_rearm_kill_alert(world):
    world.write_tags([])
    world.write_fills([])
    world.write_denylist(["strategy_x"])
    world.cycle(_at(14))  # baseline WITH the name already denied
    world.paths.denylist.write_text("{corrupt", encoding="utf-8")
    report = world.cycle(_at(14, 5))
    assert "strategy_denylist unreadable" in report["source_errors"]
    world.write_denylist(["strategy_x"])  # file recovers, same content
    world.cycle(_at(14, 6))
    assert "kill_criterion_tripped" not in world.triggers()


def test_alert_log_records_every_message_with_trigger(world):
    world.write_tags([])
    world.write_fills([])
    world.cycle(_at(14))
    world.write_tags([_tag()])
    world.cycle(_at(23, 30))  # held, not posted — still logged
    state = json.loads(world.state_path.read_text(encoding="utf-8"))
    entries = [e for e in state["alert_log"] if e["trigger"] == "trade_opened"]
    assert len(entries) == 1
    assert entries[0]["delivery"] == "held_quiet_hours"
    assert entries[0]["dedupe_key"] == "tag:ord-1"
