"""
tests/test_measurement_phase2.py — TASK-STR-PHASE2-001 measurement layer.

Pins the phase-2 build:
1. Fill ledger: strategy-tagged appends round-trip; a rejected fill
   latches a reconciliation alert instead of vanishing silently.
2. Legacy import: the 3 owner-directed closes (2026-11-14) import once,
   tagged LEGACY-UNATTRIBUTED / OWNER_DIRECTED_CLOSE, and re-importing
   is a no-op. Their exchange-verified net is +$195.71.
3. Scorecard: expectancy / profit factor / drawdown computed from fills
   only; strategies with no fills score exactly 0 trades.
4. Daemon breaker baseline: _load_state restores daily_start_equity
   (the phase-1/2 root cause: save_state wrote it, load never read it,
   so the daily-loss breaker could never fire), a zero same-day baseline
   is re-seeded from live equity, and the breaker evaluation reads it.
5. Venue-health gating: a venue whose account reads come back empty
   contributes 0 to totals, is flagged in venue_alerts, and appears as
   excluded (None) in equity snapshots — never as a cached figure.
6. Shadow trades: OBSERVE_ONLY signals open paper lifecycles; SL/TP
   touches close them with fees labelled ESTIMATE; state persists
   across tracker instances.
"""

import json
import time

import pytest

from measurement import fill_ledger, scorecard, shadow
from measurement import import_legacy_closes


@pytest.fixture(autouse=True)
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path))
    return tmp_path


def _fill(**overrides):
    row = {
        "strategy": "strategy_bb_reversion",
        "engine": "daemon",
        "venue": "binance_futures",
        "symbol": "ETHUSDT",
        "side": "SHORT",
        "qty": 0.5,
        "entry_price": 2000.0,
        "exit_price": 1990.0,
        "entry_time": 1000.0,
        "exit_time": 2000.0,
        "gross_pnl": 5.0,
        "fees": 0.5,
        "fees_source": "broker",
        "net_pnl": 4.5,
        "exit_reason": "SL_TP_BROKER",
        "order_id": "OID-1",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# 1. Fill ledger
# ---------------------------------------------------------------------------
def test_fill_append_roundtrip():
    stored = fill_ledger.append_fill(_fill())
    assert stored is not None
    rows = fill_ledger.read_fills()
    assert len(rows) == 1
    assert rows[0]["strategy"] == "strategy_bb_reversion"
    assert rows[0]["net_pnl"] == 4.5
    assert rows[0]["record_type"] == "FILL"
    assert fill_ledger.fill_recorded_since("daemon", "ETHUSDT", 1500.0)
    assert not fill_ledger.fill_recorded_since("daemon", "ETHUSDT", 2500.0)


def test_fill_missing_fields_latches_alert():
    bad = _fill()
    del bad["net_pnl"]
    assert fill_ledger.append_fill(bad) is None
    assert fill_ledger.read_fills() == []
    assert "unrecorded_close" in fill_ledger.active_alerts()


def test_position_tag_roundtrip():
    fill_ledger.append_position_tag(
        {"engine": "daemon", "venue": "binance_futures", "symbol": "SOLUSDT",
         "strategy": "strategy_bb_reversion", "side": "BUY", "qty": 1.0,
         "entry_price": 100.0, "order_id": "X1"}
    )
    tags = fill_ledger.read_position_tags()
    assert len(tags) == 1
    assert tags[0]["strategy"] == "strategy_bb_reversion"


# ---------------------------------------------------------------------------
# 2. Legacy import
# ---------------------------------------------------------------------------
_LEGACY = {
    "closed_at_utc": "2026-11-14T12:10:56Z",
    "actor": "muse_ai (owner decision 2026-11-14)",
    "records": [
        {"symbol": "SOLUSDT", "venue": "binance_futures", "side_closed": "SHORT",
         "quantity": 146.03, "entry_price": 75.63, "exit_price": 75.83,
         "gross_pnl": -29.206, "fees": 4.42938196, "net_pnl": -33.63538196,
         "close_order_id": "4245510187", "closed_at_ms": 1794658249801},
        {"symbol": "UNIUSDT", "venue": "binance_futures", "side_closed": "SHORT",
         "quantity": 1966.0, "entry_price": 5.62, "exit_price": 5.501,
         "gross_pnl": 233.954, "fees": 4.3259864, "net_pnl": 229.6280136,
         "close_order_id": "496125334", "closed_at_ms": 1794658252197},
        {"symbol": "PAXGUSDT", "venue": "binance_futures", "side_closed": "SHORT",
         "quantity": 0.274, "entry_price": 3868.62, "exit_price": 3867.73,
         "gross_pnl": 0.24385963, "fees": 0.52987896, "net_pnl": -0.28601933,
         "close_order_id": "614125393", "closed_at_ms": 1794658254120},
    ],
    "remaining_positions": {},
}


def test_legacy_import_once_and_idempotent(state_dir):
    (state_dir / "legacy_close_records.json").write_text(json.dumps(_LEGACY))
    counts = import_legacy_closes.import_records()
    assert counts == {"imported": 3, "skipped_existing": 0, "failed": 0}
    counts2 = import_legacy_closes.import_records()
    assert counts2 == {"imported": 0, "skipped_existing": 3, "failed": 0}

    rows = fill_ledger.read_fills()
    assert len(rows) == 3
    for row in rows:
        assert row["strategy"] == "LEGACY-UNATTRIBUTED"
        assert row["exit_reason"] == "OWNER_DIRECTED_CLOSE"
        assert row["fees_source"] == "broker"
    # Exchange-verified net of the three closes.
    assert round(sum(r["net_pnl"] for r in rows), 2) == 195.71


# ---------------------------------------------------------------------------
# 3. Scorecard
# ---------------------------------------------------------------------------
def test_scorecard_math_from_fills_only():
    fill_ledger.append_fill(_fill(net_pnl=10.0, gross_pnl=10.5, exit_time=100.0, order_id="A"))
    fill_ledger.append_fill(_fill(net_pnl=-4.0, gross_pnl=-3.5, exit_time=200.0, order_id="B"))
    fill_ledger.append_fill(_fill(net_pnl=-6.0, gross_pnl=-5.5, exit_time=300.0, order_id="C"))
    fill_ledger.append_fill(_fill(strategy="strategy_supertrend", net_pnl=3.0,
                                  gross_pnl=3.2, exit_time=400.0, order_id="D"))
    card = scorecard.build_scorecard()
    bb = card["strategies"]["strategy_bb_reversion"]
    assert bb["trades"] == 3
    assert bb["win_rate"] == round(1 / 3, 4)
    assert bb["net_pnl"] == 0.0
    assert bb["expectancy_net_per_trade"] == 0.0
    assert bb["profit_factor"] == 1.0
    # Curve: +10 -> -4 -> -6: peak 10, trough 0 => drawdown 10.
    assert bb["max_drawdown"] == 10.0
    assert card["strategies"]["strategy_supertrend"]["trades"] == 1
    assert card["totals"]["trades"] == 4


def test_reset_boundary_marks_snapshot_stream_and_scorecard():
    row = fill_ledger.append_reset_boundary(
        actor="owner (account reset)",
        venues_pre={"binance_futures": 10769.70},
        venues_post={"binance_futures": 10583.43},
        note="demo account reset by owner",
    )
    assert row is not None and row["record_type"] == "RESET_BOUNDARY"
    boundaries = fill_ledger.read_boundaries()
    assert len(boundaries) == 1
    assert boundaries[0]["venues_post"]["binance_futures"] == 10583.43
    # Snapshots and boundaries share one append-only stream; the regular
    # snapshot reader still sees the boundary row distinctly typed.
    card = scorecard.build_scorecard(fills=[])
    assert len(card["reset_boundaries"]) == 1
    lines = scorecard.render_lines(card)
    assert any("RESET BOUNDARY" in line and "NOT profit" in line for line in lines)


def test_scorecard_empty_is_honest_zero():
    card = scorecard.build_scorecard()
    assert card["total_fills"] == 0
    # Governed strategies render explicitly at 0 recorded forward trades.
    for name in ("bb_reversion", "factory_winner_1", "factory_winner_5",
                 "adx_ema", "supertrend"):
        assert card["strategies"][name]["trades"] == 0, name
    lines = scorecard.render_lines(card)
    assert any("bb_reversion: trades=0" in line for line in lines)
    assert any("factory_winner_1: trades=0" in line for line in lines)


# ---------------------------------------------------------------------------
# 4. Daemon breaker baseline (root-cause regression)
# ---------------------------------------------------------------------------
def _engine(state_dir, monkeypatch, **kwargs):
    from autonomy.multi_venue_engine import MultiVenueEngine

    return MultiVenueEngine(**kwargs)


def _write_state(state_dir, payload):
    (state_dir / "realized_pnl.json").write_text(json.dumps(payload))


def test_breaker_baseline_restored_on_load(state_dir, monkeypatch):
    today = time.strftime("%Y-%m-%d")
    _write_state(state_dir, {
        "realized_pnl": 10.0, "daily_realized_pnl": 5.0,
        "daily_start_date": today, "daily_loss_limit_hit": False,
        "daily_start_equity": 12345.0,
    })
    engine = _engine(state_dir, monkeypatch)
    # Pre-fix, _load_state never read this field back and the baseline
    # stayed 0.0 forever — the breaker could never fire.
    assert engine.daily_start_equity == 12345.0


def test_breaker_baseline_reseeded_when_zero_same_day(state_dir, monkeypatch):
    today = time.strftime("%Y-%m-%d")
    _write_state(state_dir, {
        "realized_pnl": 0.0, "daily_realized_pnl": 0.0,
        "daily_start_date": today, "daily_loss_limit_hit": False,
        "daily_start_equity": 0.0,
    })
    engine = _engine(state_dir, monkeypatch, max_daily_loss_pct=0.03)
    assert engine.daily_start_equity == 0.0
    monkeypatch.setattr(engine, "get_total_equity", lambda: 5000.0)
    engine._check_daily_reset()
    assert engine.daily_start_equity == 5000.0
    persisted = json.loads((state_dir / "realized_pnl.json").read_text())
    assert persisted["daily_start_equity"] == 5000.0

    # The breaker evaluation reads the seeded baseline: a -4% day latches.
    engine.daily_realized_pnl = -200.0
    engine._check_daily_loss_limit()
    assert engine.daily_loss_limit_hit is True


# ---------------------------------------------------------------------------
# 5. Venue-health gating
# ---------------------------------------------------------------------------
class _HealthyVenue:
    def get_account_summary(self):
        return {"equity": 1000.0, "balance": 900.0, "unrealized_pnl": 100.0}

    def get_balance(self):
        return {}

    def get_positions(self):
        return []


class _DeadVenue:
    """Adapter behaviour on auth failure: every read comes back empty."""

    def get_account_summary(self):
        return {}

    def get_balance(self):
        return {}

    def get_positions(self):
        return []


def test_unhealthy_venue_excluded_from_totals(state_dir, monkeypatch):
    engine = _engine(state_dir, monkeypatch)
    engine.venues = {"good": _HealthyVenue(), "oanda": _DeadVenue()}

    assert engine.get_total_equity() == 1000.0

    risk = engine.get_risk_summary()
    assert risk["total_equity"] == 1000.0
    assert risk["venue_alerts"] == ["oanda"]
    assert risk["venue_health"]["oanda"] is False
    assert "venue_unhealthy" in fill_ledger.active_alerts()

    snap = engine.equity_snapshot(trigger="test")
    assert snap["venues"]["good"] == 1000.0
    assert snap["venues"]["oanda"] is None
    assert snap["excluded_venues"] == ["oanda"]
    assert snap["total_equity"] == 1000.0


# ---------------------------------------------------------------------------
# 6. Shadow trades
# ---------------------------------------------------------------------------
def test_shadow_tp_close_with_estimated_fees(state_dir):
    tracker = shadow.ShadowTracker()
    tracker.on_signal("strategy_supertrend", "binance_futures", "BTCUSDT",
                      "BUY", 100.0, stop_loss=95.0, take_profit=110.0, ts=1000.0)
    assert len(tracker.open_positions()) == 1
    tracker.update("binance_futures", "BTCUSDT", high=111.0, low=99.0, close=110.5, ts=2000.0)
    rows = shadow.read_shadow_trades()
    assert len(rows) == 1
    row = rows[0]
    assert row["exit_reason"] == "TP"
    assert row["fees_source"] == "ESTIMATE"
    # +10% gross, minus 2 x 0.05% taker estimate.
    assert row["net_pct"] == round(0.10 - 0.001, 6)
    assert tracker.open_positions() == {}


def test_shadow_opposite_signal_closes_and_persists(state_dir):
    tracker = shadow.ShadowTracker()
    tracker.on_signal("strategy_adx_ema", "binance_futures", "ETHUSDT",
                      "SELL", 2000.0, stop_loss=2100.0, take_profit=1900.0, ts=1000.0)
    # A fresh tracker instance reloads the open shadow from disk.
    tracker2 = shadow.ShadowTracker()
    assert len(tracker2.open_positions()) == 1
    tracker2.on_signal("strategy_adx_ema", "binance_futures", "ETHUSDT",
                       "BUY", 1980.0, stop_loss=1900.0, take_profit=2100.0, ts=2000.0)
    rows = shadow.read_shadow_trades()
    assert len(rows) == 1
    assert rows[0]["exit_reason"] == "OPPOSITE_SIGNAL"
    # Short from 2000 -> 1980 is +1% gross.
    assert rows[0]["net_pct"] == round(0.01 - 0.001, 6)
    assert len(tracker2.open_positions()) == 1  # the new long shadow
