"""
tests/test_execution_quality_rd010.py — TASK-STR-RD-010 execution audit.

Pins the three fixes from the execution-quality audit:

1. MultiVenueEngine.close_position fee truth. The path used to book
   fees=0 / net=gross (fees_source="estimate"), overstating every close
   routed through it by the full round-trip commission. It now books
   the adapter's broker figures (userTrades sum, like the reconciler)
   when available, else a taker-schedule estimate — never zero — and
   records the real entry_time instead of 0.0.

2. Daemon expectancy-gate friction. The gate charged fees only
   (STRATEX_FEE_ROUNDTRIP, 8 bps round trip) while the strategies it
   gates were judged by TASK-STR-RD-002 at 16 bps round trip (5 fee +
   3 spread/slippage per side; config_strategy total_friction_bps=16).
   The gate now charges friction_rate_roundtrip (default 0.0016), with
   a getattr fallback to the legacy attribute for engines constructed
   without __init__ (older tests).

3. Legacy import fee scope. Staged records whose fills cover only the
   close order are stamped fees_scope="exit_only" (their fees are the
   exit-side commission alone — the 2026-11-14 rows miss $9.37 of
   entry-side commission, exchange-verified), and the scorecard counts
   them so the caveat travels with the numbers.
"""

import json
import time

import pytest

from measurement import fill_ledger, import_legacy_closes, scorecard


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# 1. close_position fee truth
# ---------------------------------------------------------------------------
class _CloseVenue:
    """Venue adapter stand-in for MultiVenueEngine.close_position."""

    def __init__(self, position, pnl_info=None):
        self._position = position
        self._pnl_info = pnl_info
        self.orders = []

    def get_positions(self):
        return [self._position]

    def place_order(self, *args, **kwargs):
        from exchanges.base_exchange import UnifiedOrderResult

        self.orders.append((args, kwargs))
        return UnifiedOrderResult(
            order_id="CLOSE-1",
            symbol=kwargs.get("symbol", args[0] if args else ""),
            side=kwargs.get("side", "SELL"),
            order_type="MARKET",
            price=90.0,
            quantity=kwargs.get("quantity", 0.0),
            status="FILLED",
            executed_qty=kwargs.get("quantity", 0.0),
            avg_price=90.0,
        )


def _engine_with_position(venue_adapter, opened_ms=1_700_000_000_000):
    from autonomy.multi_venue_engine import MultiVenueEngine
    from exchanges.base_exchange import UnifiedPosition

    engine = MultiVenueEngine()
    engine.venues["binance_futures"] = venue_adapter
    pos = UnifiedPosition(
        symbol="BTCUSDT", side="LONG", quantity=0.5,
        entry_price=100.0, mark_price=90.0, unrealized_pnl=-5.0,
        exchange="binance_futures",
    )
    venue_adapter._position = pos
    key = "binance_futures:BTCUSDT"
    engine.positions[key] = pos
    engine.position_strategy[key] = "strategy_test"
    engine.position_timeframe[key] = "4h"
    engine.position_opened_at[key] = opened_ms
    return engine


class _CloseVenueWithPnl(_CloseVenue):
    """Venue whose adapter reports broker realized PnL (Binance-like)."""

    def get_realized_pnl(self, symbol, since_ms=None):
        return self._pnl_info


def test_close_position_books_broker_fees_when_adapter_reports(state_dir):
    venue = _CloseVenueWithPnl(
        None,
        pnl_info={
            "gross": -5.0, "fees": 0.038, "net": -5.038,
            "trades": 4, "last_price": 90.0, "last_time": 1_700_000_100_000,
        },
    )
    engine = _engine_with_position(venue)
    assert engine.close_position("binance_futures", "BTCUSDT") is True

    rows = fill_ledger.read_fills()
    assert len(rows) == 1
    row = rows[0]
    assert row["exit_reason"] == "ENGINE_CLOSE"
    assert row["fees_source"] == "broker"
    assert row["fees"] == pytest.approx(0.038)
    assert row["net_pnl"] == pytest.approx(-5.038)
    assert row["gross_pnl"] == pytest.approx(-5.0)
    # The real open time is recorded, not 0.0.
    assert row["entry_time"] == pytest.approx(1_700_000_000.0)


def test_close_position_estimates_fees_never_zero_without_broker_path(state_dir):
    venue = _CloseVenue(None)  # no get_realized_pnl attribute at all
    engine = _engine_with_position(venue)
    assert engine.close_position("binance_futures", "BTCUSDT") is True

    rows = fill_ledger.read_fills()
    assert len(rows) == 1
    row = rows[0]
    # Price-math gross: (90 - 100) * 0.5 = -5.0. Round-trip estimate at
    # the 0.04%/side taker schedule on (entry + exit) notionals:
    # (100 + 90) * 0.5 * 0.0004 = 0.038.
    assert row["fees_source"] == "estimate"
    assert row["fees"] == pytest.approx(0.038)
    assert row["fees"] > 0
    assert row["net_pnl"] == pytest.approx(-5.038)


def test_close_position_zero_trade_pnl_report_falls_back_to_estimate(state_dir):
    # The Binance adapter returns a zeros dict (trades=0) when its
    # userTrades lookup fails; that must not book a phantom zero-fee,
    # zero-PnL "broker" row.
    venue = _CloseVenueWithPnl(
        None,
        pnl_info={"gross": 0.0, "fees": 0.0, "net": 0.0, "trades": 0,
                  "last_price": 0.0, "last_time": 0},
    )
    engine = _engine_with_position(venue)
    assert engine.close_position("binance_futures", "BTCUSDT") is True
    row = fill_ledger.read_fills()[0]
    assert row["fees_source"] == "estimate"
    assert row["fees"] == pytest.approx(0.038)
    assert row["net_pnl"] == pytest.approx(-5.038)


# ---------------------------------------------------------------------------
# 2. Daemon expectancy gate charges full friction
# ---------------------------------------------------------------------------
class _GateTicker:
    last = 100.0
    bid = 99.99
    ask = 100.01


class _GateAdapter:
    def round_quantity(self, symbol, qty):
        return qty

    def min_notional(self, symbol):
        return 0.0


class _GateEngine:
    def __init__(self):
        self.venues = {"binance_futures": _GateAdapter()}
        self.orders = []

    def can_open_position(self, venue):
        return True, ""

    def has_open_position(self, venue, symbol):
        return False

    def symbol_in_cooldown(self, venue, symbol):
        return False

    def get_ticker(self, venue, symbol):
        return _GateTicker()

    def get_candles(self, venue, symbol, timeframe, limit):
        return [
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
             "volume": 1.0}
            for _ in range(30)
        ]

    def get_risk_summary(self):
        return {"total_equity": 10000.0}

    def get_free_margin(self, venue):
        return 100000.0

    def place_order(self, **kwargs):
        from exchanges.base_exchange import UnifiedOrderResult

        self.orders.append(kwargs)
        return UnifiedOrderResult(
            order_id="GATE-1", symbol=kwargs["symbol"], side=kwargs["side"],
            order_type="MARKET", price=100.0,
            quantity=kwargs["quantity"], status="FILLED",
            executed_qty=kwargs["quantity"], avg_price=100.0,
        )


def _gate_daemon(engine, friction):
    from autonomy.run_daemon import StratexTradingEngine

    d = StratexTradingEngine.__new__(StratexTradingEngine)
    d.engine = engine
    d.min_stop_pct = 0.005
    d.max_stop_pct = 0.030
    d.risk_per_trade = 0.005
    d.max_position_pct = 0.10
    d.adx_threshold = 0.0
    d.fee_rate_roundtrip = 0.0008
    if friction is not None:
        d.friction_rate_roundtrip = friction
    d.min_expectancy_r = 0.38
    d.strategy_priors = {"strategy_gate": 0.5}
    return d


# Signal geometry: price 100, sl_dist 1.0 (stop 1%), tp_dist 2.0 (rr 2.0),
# prior 0.5 -> gross expectancy 0.5*2 - 0.5 = 0.50R.
#   fees-only 8 bps  -> fee_r 0.08 -> expectancy 0.42R >= 0.38 floor: PASS
#   friction 16 bps  -> fee_r 0.16 -> expectancy 0.34R <  0.38 floor: SKIP
_SIGNAL = {
    "side": "BUY",
    "strategy": "strategy_gate",
    "sl_dist": 1.0,
    "tp_dist": 2.0,
}


@pytest.fixture
def _no_pause(monkeypatch):
    monkeypatch.setattr("trading_pause.is_trading_paused", lambda: False)
    monkeypatch.setattr("panic_state.is_panic_active", lambda: False)
    monkeypatch.setattr("panic_state.is_kill_switch_locked", lambda: False)


def test_gate_rejects_marginal_trade_at_judged_friction(_no_pause):
    engine = _GateEngine()
    daemon = _gate_daemon(engine, friction=0.0016)
    assert daemon._execute_signal(
        "binance_futures", "BTCUSDT", dict(_SIGNAL), "4h"
    ) is False
    assert engine.orders == []


def test_gate_accepts_same_trade_at_legacy_fees_only_rate(_no_pause):
    engine = _GateEngine()
    daemon = _gate_daemon(engine, friction=None)  # getattr fallback path
    assert daemon._execute_signal(
        "binance_futures", "BTCUSDT", dict(_SIGNAL), "4h"
    ) is True
    assert len(engine.orders) == 1


# ---------------------------------------------------------------------------
# 3. Legacy import fee scope + scorecard visibility
# ---------------------------------------------------------------------------
def _staged(state_dir, records):
    path = state_dir / "legacy_close_records.json"
    path.write_text(json.dumps({"records": records}))
    return path


_BASE_REC = {
    "symbol": "SOLUSDT", "venue": "binance_futures", "side_closed": "SHORT",
    "quantity": 146.03, "entry_price": 75.63, "exit_price": 75.83,
    "gross_pnl": -29.206, "fees": 4.42938196, "net_pnl": -33.63538196,
    "close_order_id": "4245510187", "closed_at_ms": 1794658249801,
}


def test_import_stamps_exit_only_when_fills_cover_close_order_only(state_dir):
    rec = dict(_BASE_REC, fill_order_ids=["4245510187"], fill_count=1)
    counts = import_legacy_closes.import_records(_staged(state_dir, [rec]))
    assert counts["imported"] == 1
    row = fill_ledger.read_fills()[0]
    assert row["fees_scope"] == "exit_only"
    card = scorecard.build_scorecard()
    assert card["totals"]["exit_only_fee_fills"] == 1


def test_import_stamps_round_trip_when_entry_fills_staged(state_dir):
    rec = dict(
        _BASE_REC, fill_order_ids=["4245384745", "4245510187"], fill_count=2
    )
    counts = import_legacy_closes.import_records(_staged(state_dir, [rec]))
    assert counts["imported"] == 1
    row = fill_ledger.read_fills()[0]
    assert row["fees_scope"] == "round_trip"
    card = scorecard.build_scorecard()
    assert card["totals"]["exit_only_fee_fills"] == 0


def test_import_stamps_unknown_without_fill_list(state_dir):
    counts = import_legacy_closes.import_records(
        _staged(state_dir, [dict(_BASE_REC)])
    )
    assert counts["imported"] == 1
    row = fill_ledger.read_fills()[0]
    assert row["fees_scope"] == "unknown"
