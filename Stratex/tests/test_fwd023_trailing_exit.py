"""TASK-STR-FWD-023: daemon trailing-stop exit support — unit coverage.

Production context (TASK-STR-FWD-019, WAVE2 §C1): eight FORWARD_TEST
streams were judged under the families2 TRAIL spec — initial stop
2.0 x ATR(14), trailing stop 2.5 x ATR(14), NO fixed take-profit
(rigorous_backtest/rd/fastsim.py) — and were registered deliberately
NON-executable, because the daemon's execution path required a fixed
TP distance: the modules return tp_dist=None / rr_ratio=None, the scan
quality gate skipped rr <= 0 as "no R:R metric", and _execute_signal
refused take_profit <= 0. (The wave-2 prose says "7 TRAIL streams" but
enumerates 8 registry keys; all 8 enumerated keys are wired here.)

The fix, in three parts, all keyed to an explicit registry declaration
(``exit_mode == "trailing"`` + ``exit_sl_atr`` / ``exit_trail_atr`` on
the entry — see config_strategy.py):

1. ``trailing_stop_path`` (autonomy/run_daemon.py): a faithful port of
   fastsim._simulate_trail for the TRAIL spec — ATR frozen at the
   signal bar, stop checked before the running extreme updates within
   each bar, gap-through exits at the bar open, ratchet favourable-only.
2. ``_execute_signal`` / scan gate: the TP-dependent preconditions are
   relaxed ONLY for declared entries. An undeclared strategy returning
   tp_dist=None still cannot trade (fail-closed pins below).
3. ``_manage_trailing_exits``: on each scan, open declared positions
   with an entry-time state record are replayed over closed bars; a
   closed-bar breach closes at market (the trend/time-exit pattern —
   the reconciler books the PnL). The venue-side order keeps the judged
   INITIAL stop as the intrabar/gap backstop.

Everything is offline: fake engines/adapters only, no network, no
orders. Equivalence is asserted against the judged harness itself
(fastsim.simulate_entries + families2 entry lists) on the fwd002
fixture slices — exit bar, exit price and exit reason must match for
every harness trade.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260
TRAIL_SPEC = {"type": "trail", "sl_atr": 2.0, "trail_atr": 2.5}

TRAIL_KEYS = (
    "donchian_turtle_n20_trail",
    "donchian_turtle_n55_trail",
    "donchian_turtle_n55_trail_4h",
    "donchian_turtle_n20_trail_4h",
    "turtle2",
    "turtle2_n20_trail_filt",
    "turtle2_n55_trail_filt_4h",
    "turtle2_n20_trail_filt_4h",
)
BRACKET_KEYS = (
    "donchian_turtle",
    "donchian_turtle_n20_b26",
    "donchian_turtle_n20_b24",
    "donchian_turtle_n20_b26_4h",
    "donchian_turtle_n55_b24",
)


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence: trailing_stop_path vs the judged harness (fastsim)
# ---------------------------------------------------------------------------


def _check_stream_against_harness(df, entries):
    """Every fastsim trade's exit bar/price/reason must be reproduced
    by trailing_stop_path fed the same entry bar, entry price (the
    entry bar's open) and signal-bar ATR. Returns (trades, reasons)."""
    from rigorous_backtest.rd.common import atr as harness_atr
    from rigorous_backtest.rd.fastsim import simulate_entries
    from rigorous_backtest.simulator import Costs

    from autonomy.run_daemon import trailing_stop_path

    atr_arr = harness_atr(df, 14).to_numpy(dtype=float)
    trades = simulate_entries(df, entries, atr_arr, dict(TRAIL_SPEC), "TEST", Costs())
    opens = df["open"].to_numpy(dtype=float)
    bars_all = df[["open", "high", "low", "close"]].to_dict("records")
    n = len(df)
    cursor = 0
    ti = 0
    reasons = []
    for sig_bar, side in sorted(entries):
        if sig_bar < cursor or sig_bar + 1 >= n:
            continue
        a = float(atr_arr[sig_bar])
        if not np.isfinite(a) or a <= 0:
            continue
        entry_bar = sig_bar + 1
        trade = trades[ti]
        ti += 1
        assert trade.entry_price == pytest.approx(opens[entry_bar])
        path = trailing_stop_path(
            side, float(opens[entry_bar]), a, 2.0, 2.5, bars_all[entry_bar:]
        )
        exit_pos = int(df.index.get_loc(trade.exit_time))
        if trade.exit_reason == "END_OF_DATA":
            assert path["exit_index"] is None, (sig_bar, side)
        else:
            assert path["exit_index"] == exit_pos - entry_bar, (sig_bar, side)
            assert path["exit_price"] == pytest.approx(trade.exit_price), (
                sig_bar,
                side,
            )
            assert path["exit_reason"] == trade.exit_reason, (sig_bar, side)
        reasons.append(trade.exit_reason)
        cursor = exit_pos
    assert ti == len(trades)
    return len(trades), reasons


def test_trailing_path_matches_judged_harness_on_fixtures():
    from rigorous_backtest.rd2 import families2

    cases = [
        ("BTCUSDT", "1d", families2.sig_donchian, (20,)),
        ("SOLUSDT", "1d", families2.sig_donchian, (55,)),
        ("BTCUSDT", "4h", families2.sig_donchian, (20,)),
        ("SOLUSDT", "4h", families2.sig_donchian, (55,)),
        ("BTCUSDT", "1d", families2.sig_turtle2, (55, True)),
        ("SOLUSDT", "1d", families2.sig_turtle2, (20, True)),
    ]
    total = 0
    all_reasons: list[str] = []
    for symbol, tf, fn, args in cases:
        df = _load(f"{symbol}_{tf}.csv")
        entries = fn(df, *args, WARMUP)
        checked, reasons = _check_stream_against_harness(df, entries)
        assert checked >= 5, (symbol, tf, args)
        total += checked
        all_reasons.extend(reasons)
    assert total >= 30
    # Both exit branches genuinely exercised across the fixtures: the
    # initial stop (SL) and the ratcheted trailing stop (TRAIL).
    assert all_reasons.count("SL") >= 3
    assert all_reasons.count("TRAIL") >= 3


# ---------------------------------------------------------------------------
# 2. Path properties (synthetic bars)
# ---------------------------------------------------------------------------


def _bars(rows):
    return [
        {"open": o, "high": h, "low": l, "close": c} for (o, h, l, c) in rows
    ]


def test_stop_never_moves_backwards_long():
    from autonomy.run_daemon import trailing_stop_path

    rows = [
        (100.0, 104.0, 99.0, 103.0),
        (103.0, 108.0, 102.0, 107.0),
        (107.0, 112.0, 106.0, 111.0),
        (111.0, 116.0, 110.0, 115.0),
        (115.0, 121.0, 114.0, 120.0),
        (120.0, 124.0, 118.0, 123.0),
    ]
    stops = [
        trailing_stop_path("LONG", 100.0, 4.0, 2.0, 2.5, _bars(rows[:k]))["stop"]
        for k in range(1, len(rows) + 1)
    ]
    assert stops == sorted(stops)
    assert stops[0] == pytest.approx(94.0)  # best 104 - 2.5*4
    assert stops[-1] == pytest.approx(114.0)  # best 124 - 2.5*4


def test_stop_never_moves_backwards_short():
    from autonomy.run_daemon import trailing_stop_path

    rows = [
        (100.0, 101.0, 96.0, 97.0),
        (97.0, 98.0, 92.0, 93.0),
        (93.0, 94.0, 88.0, 89.0),
        (89.0, 90.0, 84.0, 85.0),
        (85.0, 86.0, 79.0, 80.0),
        (80.0, 82.0, 76.0, 77.0),
    ]
    stops = [
        trailing_stop_path("SHORT", 100.0, 4.0, 2.0, 2.5, _bars(rows[:k]))["stop"]
        for k in range(1, len(rows) + 1)
    ]
    assert stops == sorted(stops, reverse=True)
    assert stops[-1] == pytest.approx(86.0)  # best 76 + 2.5*4


def test_entry_bar_high_does_not_lift_stop_before_low_check():
    from autonomy.run_daemon import trailing_stop_path

    # Initial stop 80 (entry 100, sl 2.0 x ATR 10). The entry bar's own
    # high (130) must NOT ratchet the stop to 105 before its low (79) is
    # tested: the judged order is check-then-update, so the exit is at
    # the initial stop, labelled SL.
    path = trailing_stop_path(
        "LONG", 100.0, 10.0, 2.0, 2.5, _bars([(100.0, 130.0, 79.0, 120.0)])
    )
    assert path["exit_index"] == 0
    assert path["exit_price"] == pytest.approx(80.0)
    assert path["exit_reason"] == "SL"


def test_gap_through_stop_exits_at_bar_open():
    from autonomy.run_daemon import trailing_stop_path

    path = trailing_stop_path(
        "LONG",
        100.0,
        2.0,
        2.0,
        2.5,
        _bars([(100.0, 101.0, 99.0, 100.0), (94.0, 95.0, 93.0, 94.0)]),
    )
    assert path["exit_index"] == 1
    assert path["exit_price"] == pytest.approx(94.0)
    assert path["exit_reason"] == "SL"  # stop never ratcheted (best 101 -> 96)


def test_ratcheted_exit_is_labelled_trail():
    from autonomy.run_daemon import trailing_stop_path

    path = trailing_stop_path(
        "LONG",
        100.0,
        2.0,
        2.0,
        2.5,
        _bars([(100.0, 110.0, 99.0, 109.0), (108.0, 109.0, 104.0, 105.0)]),
    )
    assert path["exit_index"] == 1
    assert path["exit_price"] == pytest.approx(105.0)  # best 110 - 2.5*2
    assert path["exit_reason"] == "TRAIL"


def test_short_ratchet_mirror():
    from autonomy.run_daemon import trailing_stop_path

    path = trailing_stop_path(
        "SHORT",
        100.0,
        2.0,
        2.0,
        2.5,
        _bars([(100.0, 101.0, 90.0, 91.0), (92.0, 96.0, 91.0, 95.0)]),
    )
    assert path["exit_index"] == 1
    assert path["exit_price"] == pytest.approx(95.0)  # best 90 + 2.5*2
    assert path["exit_reason"] == "TRAIL"


# ---------------------------------------------------------------------------
# 3. Registry declaration pins + the daemon's spec helper
# ---------------------------------------------------------------------------


def test_registry_trail_entries_declare_trailing_exit():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    for key in TRAIL_KEYS:
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["exit_mode"] == "trailing", key
        assert entry["exit_sl_atr"] == pytest.approx(2.0), key
        assert entry["exit_trail_atr"] == pytest.approx(2.5), key
        # Governance untouched: still the FORWARD_TEST lane.
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["forward_protocol"] is True, key


def test_no_other_registry_entry_declares_trailing():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    declared = {
        k for k, e in PRODUCTION_STRATEGY_REGISTRY.items()
        if e.get("exit_mode") == "trailing"
    }
    assert declared == set(TRAIL_KEYS)
    for key in BRACKET_KEYS:
        assert "exit_mode" not in PRODUCTION_STRATEGY_REGISTRY[key], key


def test_trailing_spec_helper_reads_declaration_only():
    from autonomy.run_daemon import StratexTradingEngine

    d = StratexTradingEngine.__new__(StratexTradingEngine)
    assert d._trailing_spec_for_strategy(
        "strategy_donchian_turtle_n20_trail"
    ) == {"sl_atr": 2.0, "trail_atr": 2.5}
    assert d._trailing_spec_for_strategy("strategy_turtle2") == {
        "sl_atr": 2.0,
        "trail_atr": 2.5,
    }
    # Undeclared strategies and unknown names: None (fail-closed).
    assert d._trailing_spec_for_strategy("strategy_bollinger_trend") is None
    assert d._trailing_spec_for_strategy("strategy_donchian_turtle") is None
    assert d._trailing_spec_for_strategy("strategy_no_such") is None
    assert d._trailing_spec_for_strategy("") is None


# ---------------------------------------------------------------------------
# 4. _execute_signal: trailing contract + fail-closed pins
# ---------------------------------------------------------------------------


class _Ticker:
    last = 100.0
    bid = 99.99
    ask = 100.01


class _ExecAdapter:
    def round_quantity(self, symbol, qty):
        return qty

    def min_notional(self, symbol):
        return 0.0


class _ExecEngine:
    """Minimal MultiVenueEngine stand-in for _execute_signal."""

    def __init__(self):
        self.venues = {"binance_futures": _ExecAdapter()}
        self.positions = {}
        self.position_strategy = {}
        self.orders = []

    def can_open_position(self, venue):
        return True, ""

    def has_open_position(self, venue, symbol):
        return False

    def symbol_in_cooldown(self, venue, symbol):
        return False

    def get_ticker(self, venue, symbol):
        return _Ticker()

    def get_candles(self, venue, symbol, timeframe, limit):
        return [
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
             "volume": 1.0}
            for _ in range(30)
        ]

    def get_venue_equity(self, venue):
        return 10_000.0

    def get_free_margin(self, venue):
        return 1_000_000.0

    def place_order(self, **kwargs):
        from exchanges.base_exchange import UnifiedOrderResult

        self.orders.append(kwargs)
        return UnifiedOrderResult(
            order_id="FWD023-1", symbol=kwargs["symbol"], side=kwargs["side"],
            order_type="MARKET", price=100.0, quantity=kwargs["quantity"],
            status="FILLED", executed_qty=kwargs["quantity"], avg_price=100.0,
        )


def _exec_daemon(engine):
    from autonomy.run_daemon import StratexTradingEngine

    d = StratexTradingEngine.__new__(StratexTradingEngine)
    d.engine = engine
    d.min_stop_pct = 0.005
    d.max_stop_pct = 0.15
    d.risk_per_trade = 0.001
    d.max_heat_pct = 0.02
    d.max_position_pct = 0.10
    d.adx_threshold = 0.0
    d.fee_rate_roundtrip = 0.0008
    d.friction_rate_roundtrip = 0.0016
    d.min_expectancy_r = 0.10
    d.strategy_priors = {
        "strategy_donchian_turtle_n20_trail": 0.3885,
        "strategy_turtle2": 0.3725,
        "strategy_bollinger_trend": 0.55,
    }
    return d


@pytest.fixture
def _no_pause(monkeypatch):
    monkeypatch.setattr("trading_pause.is_trading_paused", lambda: False)
    monkeypatch.setattr("panic_state.is_panic_active", lambda: False)
    monkeypatch.setattr("panic_state.is_kill_switch_locked", lambda: False)


@pytest.fixture
def _trail_state_file(monkeypatch, tmp_path):
    path = tmp_path / "trailing_positions.json"
    monkeypatch.setenv("STRATEX_TRAILING_STATE_FILE", str(path))
    return path


def test_trailing_entry_executes_with_sl_only_and_records_state(
    _no_pause, _trail_state_file
):
    engine = _ExecEngine()
    daemon = _exec_daemon(engine)
    sig = {
        "side": "BUY",
        "strategy": "strategy_donchian_turtle_n20_trail",
        "sl_dist": 2.0,
        "tp_dist": None,
        "win_rate_prior": 0.3885,
    }
    assert daemon._execute_signal("binance_futures", "BTCUSDT", sig, "1d") is True
    assert len(engine.orders) == 1
    order = engine.orders[0]
    assert order["stop_loss"] == pytest.approx(98.0)  # re-anchored from sl_dist
    assert order["take_profit"] is None  # SL only — no invented TP
    record = json.loads(_trail_state_file.read_text())["binance_futures:BTCUSDT"]
    assert record["strategy"] == "strategy_donchian_turtle_n20_trail"
    assert record["side"] == "LONG"
    assert record["entry_price"] == pytest.approx(100.0)
    assert record["atr_entry"] == pytest.approx(1.0)  # sl_dist 2.0 / sl_atr 2.0
    assert record["timeframe"] == "1d"


def test_trailing_sell_mirrors(_no_pause, _trail_state_file):
    engine = _ExecEngine()
    daemon = _exec_daemon(engine)
    sig = {
        "side": "SELL",
        "strategy": "strategy_turtle2",
        "sl_dist": 3.0,
        "tp_dist": None,
        "win_rate_prior": 0.3725,
    }
    assert daemon._execute_signal("binance_futures", "ETHUSDT", sig, "1d") is True
    order = engine.orders[0]
    assert order["stop_loss"] == pytest.approx(103.0)
    assert order["take_profit"] is None
    record = json.loads(_trail_state_file.read_text())["binance_futures:ETHUSDT"]
    assert record["side"] == "SHORT"
    assert record["atr_entry"] == pytest.approx(1.5)  # 3.0 / 2.0


def test_undeclared_strategy_with_tp_dist_none_still_cannot_trade(
    _no_pause, _trail_state_file
):
    engine = _ExecEngine()
    daemon = _exec_daemon(engine)
    # The registry-wrapper shape for an undeclared tp_dist=None module:
    # no stop price at all.
    sig = {
        "side": "BUY",
        "strategy": "strategy_bollinger_trend",
        "sl_dist": 2.0,
        "tp_dist": None,
        "win_rate_prior": 0.55,
    }
    assert daemon._execute_signal("binance_futures", "BTCUSDT", sig, "1d") is False
    assert engine.orders == []
    # Even with a stop price supplied, take_profit=0 refuses it.
    sig2 = dict(sig, stop_loss=99.0, take_profit=0)
    assert daemon._execute_signal("binance_futures", "BTCUSDT", sig2, "1d") is False
    assert engine.orders == []


def test_trailing_declaration_without_sl_dist_cannot_trade(
    _no_pause, _trail_state_file
):
    engine = _ExecEngine()
    daemon = _exec_daemon(engine)
    sig = {
        "side": "BUY",
        "strategy": "strategy_donchian_turtle_n20_trail",
        "tp_dist": None,
        "win_rate_prior": 0.3885,
    }
    assert daemon._execute_signal("binance_futures", "BTCUSDT", sig, "1d") is False
    assert engine.orders == []


def test_bracket_entry_unaffected(_no_pause, _trail_state_file):
    engine = _ExecEngine()
    daemon = _exec_daemon(engine)
    sig = {
        "side": "BUY",
        "strategy": "strategy_bollinger_trend",
        "sl_dist": 2.0,
        "tp_dist": 4.0,
        "win_rate_prior": 0.55,
    }
    assert daemon._execute_signal("binance_futures", "BTCUSDT", sig, "1d") is True
    order = engine.orders[0]
    assert order["stop_loss"] == pytest.approx(98.0)
    assert order["take_profit"] == pytest.approx(104.0)
    # No trailing state is written for a bracket entry.
    assert not _trail_state_file.exists()


# ---------------------------------------------------------------------------
# 5. _manage_trailing_exits
# ---------------------------------------------------------------------------


class _MgrAdapter:
    def __init__(self):
        self.orders = []
        self.cancelled = []

    def place_order(self, symbol, side, order_type, quantity):
        self.orders.append(
            {"symbol": symbol, "side": side, "type": order_type, "qty": quantity}
        )
        return SimpleNamespace(status="FILLED")

    def cancel_protective_orders(self, symbol):
        self.cancelled.append(symbol)
        return 1


class _MgrEngine:
    def __init__(self, candles, key, pos, strat, tf="1d"):
        self.venues = {"binance_futures": _MgrAdapter()}
        self.positions = {key: pos}
        self.position_strategy = {key: strat}
        self.position_timeframe = {key: tf}
        self.position_opened_at = {key: 0}
        self._candles = candles

    def get_candles(self, venue, symbol, tf, limit):
        return self._candles


def _mgr_daemon(engine):
    from autonomy.run_daemon import StratexTradingEngine

    d = StratexTradingEngine.__new__(StratexTradingEngine)
    d.engine = engine
    return d


def _day_bars(base_ts, rows):
    return [
        {
            "timestamp": base_ts + k * 86400,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": 1.0,
        }
        for k, (o, h, l, c) in enumerate(rows)
    ]


def _write_state(path, key, **over):
    record = {
        "strategy": "strategy_donchian_turtle_n20_trail",
        "timeframe": "1d",
        "side": "LONG",
        "entry_price": 100.0,
        "atr_entry": 2.0,
        "opened_at_ms": over.pop("opened_at_ms"),
        "stop": 96.0,
        "best": 100.0,
    }
    record.update(over)
    path.write_text(json.dumps({key: record}))
    return record


# Long scenario: entry bar, two ratcheting bars, then a breach of the
# trailed stop (105.5 < 106) on bar 3. Stops: 96 -> 96 -> 105 -> 106.
_LONG_ROWS = [
    (100.0, 101.0, 99.0, 100.5),
    (100.5, 110.0, 100.0, 109.0),
    (109.0, 111.0, 106.5, 110.0),
    (110.0, 110.5, 105.5, 106.0),
]


def test_manager_closes_on_trailed_stop_breach(monkeypatch, tmp_path):
    state_path = tmp_path / "trailing_positions.json"
    monkeypatch.setenv("STRATEX_TRAILING_STATE_FILE", str(state_path))
    base_ts = int(time.time()) - 9 * 86400
    key = "binance_futures:BTCUSDT"
    _write_state(state_path, key, opened_at_ms=(base_ts + 3600) * 1000)
    pos = SimpleNamespace(side="LONG", quantity=0.25, entry_price=100.0,
                          mark_price=106.0)
    engine = _MgrEngine(
        _day_bars(base_ts, _LONG_ROWS), key, pos,
        "strategy_donchian_turtle_n20_trail",
    )
    daemon = _mgr_daemon(engine)
    daemon._manage_trailing_exits()
    adapter = engine.venues["binance_futures"]
    assert adapter.orders == [
        {"symbol": "BTCUSDT", "side": "SELL", "type": "MARKET", "qty": 0.25}
    ]
    assert adapter.cancelled == ["BTCUSDT"]
    assert json.loads(state_path.read_text()) == {}  # record consumed


def test_manager_ratchets_without_closing(monkeypatch, tmp_path):
    state_path = tmp_path / "trailing_positions.json"
    monkeypatch.setenv("STRATEX_TRAILING_STATE_FILE", str(state_path))
    base_ts = int(time.time()) - 9 * 86400
    key = "binance_futures:BTCUSDT"
    rows = _LONG_ROWS[:3] + [(110.0, 110.5, 107.0, 108.0)]  # low 107 > stop 106
    _write_state(state_path, key, opened_at_ms=(base_ts + 3600) * 1000)
    pos = SimpleNamespace(side="LONG", quantity=0.25, entry_price=100.0,
                          mark_price=108.0)
    engine = _MgrEngine(
        _day_bars(base_ts, rows), key, pos,
        "strategy_donchian_turtle_n20_trail",
    )
    daemon = _mgr_daemon(engine)
    daemon._manage_trailing_exits()
    adapter = engine.venues["binance_futures"]
    assert adapter.orders == []
    record = json.loads(state_path.read_text())[key]
    assert record["stop"] == pytest.approx(106.0)  # ratcheted from 96
    assert record["best"] == pytest.approx(111.0)


def test_manager_closes_short_on_trailed_stop_breach(monkeypatch, tmp_path):
    state_path = tmp_path / "trailing_positions.json"
    monkeypatch.setenv("STRATEX_TRAILING_STATE_FILE", str(state_path))
    base_ts = int(time.time()) - 9 * 86400
    key = "binance_futures:BTCUSDT"
    rows = [
        (100.0, 101.0, 99.0, 99.5),
        (99.0, 100.0, 90.0, 91.0),
        (91.0, 96.0, 89.0, 95.0),  # high 96 >= trailed stop 95 -> breach
    ]
    _write_state(
        state_path, key, opened_at_ms=(base_ts + 3600) * 1000,
        side="SHORT", stop=104.0,
    )
    pos = SimpleNamespace(side="SHORT", quantity=0.25, entry_price=100.0,
                          mark_price=95.0)
    engine = _MgrEngine(
        _day_bars(base_ts, rows), key, pos,
        "strategy_donchian_turtle_n20_trail",
    )
    daemon = _mgr_daemon(engine)
    daemon._manage_trailing_exits()
    adapter = engine.venues["binance_futures"]
    assert adapter.orders == [
        {"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "qty": 0.25}
    ]


def test_manager_ignores_undeclared_strategy(monkeypatch, tmp_path):
    state_path = tmp_path / "trailing_positions.json"
    monkeypatch.setenv("STRATEX_TRAILING_STATE_FILE", str(state_path))
    base_ts = int(time.time()) - 9 * 86400
    key = "binance_futures:BTCUSDT"
    _write_state(
        state_path, key, opened_at_ms=(base_ts + 3600) * 1000,
        strategy="strategy_bollinger_trend",
    )
    pos = SimpleNamespace(side="LONG", quantity=0.25, entry_price=100.0,
                          mark_price=106.0)
    engine = _MgrEngine(
        _day_bars(base_ts, _LONG_ROWS), key, pos, "strategy_bollinger_trend"
    )
    daemon = _mgr_daemon(engine)
    daemon._manage_trailing_exits()
    assert engine.venues["binance_futures"].orders == []


def test_manager_ignores_declared_position_without_record(monkeypatch, tmp_path):
    state_path = tmp_path / "trailing_positions.json"
    monkeypatch.setenv("STRATEX_TRAILING_STATE_FILE", str(state_path))
    base_ts = int(time.time()) - 9 * 86400
    key = "binance_futures:BTCUSDT"
    pos = SimpleNamespace(side="LONG", quantity=0.25, entry_price=100.0,
                          mark_price=106.0)
    engine = _MgrEngine(
        _day_bars(base_ts, _LONG_ROWS), key, pos,
        "strategy_donchian_turtle_n20_trail",
    )
    daemon = _mgr_daemon(engine)
    daemon._manage_trailing_exits()
    assert engine.venues["binance_futures"].orders == []


def test_manager_drops_mismatched_record(monkeypatch, tmp_path):
    state_path = tmp_path / "trailing_positions.json"
    monkeypatch.setenv("STRATEX_TRAILING_STATE_FILE", str(state_path))
    base_ts = int(time.time()) - 9 * 86400
    key = "binance_futures:BTCUSDT"
    _write_state(
        state_path, key, opened_at_ms=(base_ts + 3600) * 1000,
        entry_price=90.0,  # live position entered at 100 — not this record's
    )
    pos = SimpleNamespace(side="LONG", quantity=0.25, entry_price=100.0,
                          mark_price=106.0)
    engine = _MgrEngine(
        _day_bars(base_ts, _LONG_ROWS), key, pos,
        "strategy_donchian_turtle_n20_trail",
    )
    daemon = _mgr_daemon(engine)
    daemon._manage_trailing_exits()
    assert engine.venues["binance_futures"].orders == []
    assert json.loads(state_path.read_text()) == {}  # stale record dropped


def test_manager_throttled(monkeypatch, tmp_path):
    state_path = tmp_path / "trailing_positions.json"
    monkeypatch.setenv("STRATEX_TRAILING_STATE_FILE", str(state_path))
    base_ts = int(time.time()) - 9 * 86400
    key = "binance_futures:BTCUSDT"
    _write_state(state_path, key, opened_at_ms=(base_ts + 3600) * 1000)
    pos = SimpleNamespace(side="LONG", quantity=0.25, entry_price=100.0,
                          mark_price=106.0)
    engine = _MgrEngine(
        _day_bars(base_ts, _LONG_ROWS), key, pos,
        "strategy_donchian_turtle_n20_trail",
    )
    daemon = _mgr_daemon(engine)
    daemon._last_trailing_manage = time.time()
    daemon._manage_trailing_exits()
    assert engine.venues["binance_futures"].orders == []


# ---------------------------------------------------------------------------
# 6. Scan gate: rr<=0 exemption is declaration-scoped
# ---------------------------------------------------------------------------


class _ScanAdapter:
    def round_quantity(self, symbol, qty):
        return qty

    def min_notional(self, symbol):
        return 0.0


class _ScanTicker:
    last = 100.0


class _ScanOrderResult:
    status = "FILLED"
    avg_price = 100.0


class _ScanEngine:
    def __init__(self, candles):
        self.venues = {"binance_futures": _ScanAdapter()}
        self.positions = {}
        self.position_opened_at = {}
        self.position_strategy = {}
        self.position_timeframe = {}
        self.realized_pnl = 0.0
        self.daily_realized_pnl = 0.0
        self.daily_start_equity = 100_000.0
        self.max_daily_loss_pct = 0.03
        self.daily_loss_limit_hit = False
        self.telegram_bot = None
        self._candles = candles
        self.orders = []

    def get_risk_summary(self):
        return {"daily_loss_limit_hit": False, "total_equity": 100_000.0}

    def get_venue_equity(self, venue):
        return 100_000.0

    def get_candles(self, venue, symbol, tf, limit):
        return self._candles

    def get_ticker(self, venue, symbol):
        return _ScanTicker()

    def can_open_position(self, venue):
        return True, "OK"

    def has_open_position(self, venue, symbol):
        return False

    def symbol_in_cooldown(self, venue, symbol):
        return False

    def get_free_margin(self, venue):
        return 100_000.0

    def place_order(self, **kwargs):
        self.orders.append(kwargs)
        return _ScanOrderResult()

    def save_state(self):
        pass


class _GateFakeRegistry:
    """Two FORWARD_TEST strategies, both emitting rr_ratio=None signals:
    the trailing-declared donchian (fires on BTCUSDT, sl_dist only) and
    the undeclared bollinger (fires on ETHUSDT with a valid bracket —
    only the scan R:R gate can stop it)."""

    NAMES = ("strategy_donchian_turtle_n20_trail", "strategy_bollinger_trend")

    def get_all_strategy_names(self):
        return list(self.NAMES)

    def governance_status(self, name):
        return "FORWARD_TEST"

    def get(self, name):
        return SimpleNamespace(status="FORWARD_TEST", rr_ratio=None)

    def executable(self, name, tf, symbol, venue=None):
        return True, "OK"

    def demo_venues(self):
        return frozenset({"binance_futures"})

    def execute_strategy(self, name, df, tf, symbol, allow_observe=False, venue=None):
        if name == "strategy_donchian_turtle_n20_trail" and symbol == "BTCUSDT":
            return {
                "status": "SIGNAL", "strategy": name, "side": "BUY",
                "stop_loss": 0, "take_profit": 0,
                "win_rate_prior": 0.3885, "rr_ratio": None,
                "strategy_type": "RULE_BASED", "sl_dist": 2.0,
                "tp_dist": None, "observe_only": False, "forward_test": True,
            }
        if name == "strategy_bollinger_trend" and symbol == "ETHUSDT":
            return {
                "status": "SIGNAL", "strategy": name, "side": "BUY",
                "stop_loss": 99.0, "take_profit": 102.0,
                "win_rate_prior": 0.5699, "rr_ratio": None,
                "strategy_type": "RULE_BASED", "sl_dist": None,
                "tp_dist": None, "observe_only": False, "forward_test": True,
            }
        return {
            "status": "NO_SIGNAL", "strategy": name,
            "observe_only": False, "forward_test": True,
        }


def _scan_candles(rows: int = 300, bar_seconds: int = 14400):
    now = int(time.time())
    return [
        {
            "timestamp": now - (rows - i) * bar_seconds,
            "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
            "volume": 1.0,
        }
        for i in range(rows)
    ]


def test_scan_gate_exempts_only_declared_trailing(monkeypatch, tmp_path):
    import datetime

    import autonomy.run_daemon as run_daemon
    from autonomy.run_daemon import StratexTradingEngine

    monkeypatch.setattr("trading_pause.is_trading_paused", lambda: False)
    monkeypatch.setattr("panic_state.is_panic_active", lambda: False)
    monkeypatch.setattr("panic_state.is_kill_switch_locked", lambda: False)
    monkeypatch.setenv(
        "STRATEX_TRAILING_STATE_FILE", str(tmp_path / "trailing_positions.json")
    )
    monkeypatch.setattr(run_daemon, "strategy_registry", _GateFakeRegistry())

    engine = _ScanEngine(_scan_candles())
    d = StratexTradingEngine.__new__(StratexTradingEngine)
    d.engine = engine
    d.scan_interval = 0.0
    d.max_positions = 9999
    d.min_confidence = 0.55
    d.min_rr = 1.5
    d.risk_per_trade = 0.001
    d.max_heat_pct = 0.02
    d.max_position_pct = 0.10
    d.min_stop_pct = 0.005
    d.max_stop_pct = 0.030
    d.entry_confluence = 1
    d.adx_threshold = 0.0
    d.fee_rate_roundtrip = 0.0008
    d.friction_rate_roundtrip = 0.0016
    d.min_expectancy_r = 0.05
    d._confluence_signals = {}
    d._last_signal_bar = {}
    d.adx_strategies = set()
    d.strategy_denylist = set()
    d.strategy_allowlist = set()
    d.strategy_priors = {}
    d.symbols = {"binance_futures": ["BTCUSDT", "ETHUSDT"]}
    d.timeframes = ["4h"]
    d.running = True
    d.last_scan = 0
    d.scan_count = 0
    d._last_trend_manage = time.time()
    d._shadow = None
    d._last_summary_date = datetime.datetime.now(
        datetime.timezone.utc
    ).date().isoformat()

    results = d.scan_and_execute()
    assert results["errors"] == 0
    assert results["executed"] == 1
    # The declared trailing signal executed, SL-only...
    assert len(engine.orders) == 1
    order = engine.orders[0]
    assert order["symbol"] == "BTCUSDT"
    assert order["take_profit"] is None
    assert order["stop_loss"] == pytest.approx(98.0)
    # ...while the undeclared rr=None signal was stopped at the scan
    # gate despite carrying a valid bracket (no ETHUSDT order exists).
    assert all(o["symbol"] != "ETHUSDT" for o in engine.orders)
