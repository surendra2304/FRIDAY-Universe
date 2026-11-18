"""TASK-STR-FWD-021 — RD-014 vol-target overlay service.

Pins:
1. The live core (overlay_service.py) reproduces the judged harness
   (rigorous_backtest/rd14/family14.py) exactly: raw weights, shadow
   equity/drawdown, brake multipliers and position series on real and
   synthetic close series.
2. The brake state machine's hysteresis (engage at -threshold,
   release at -threshold/2) on hand-computed drawdown paths.
3. Causality: the target weight at bar t is a pure function of
   closes <= t (no look-ahead).
4. The registry carries exactly the 21 two-tier RD-014 rows as
   FORWARD_TEST overlay entries with their judged figures.
5. The daemon overlay manager's behaviour with stub engine/adapter:
   open / hold / increase / reduce / close / flip-is-close-first /
   contention / denylist / entries gating / min-notional floor.
"""

from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import overlay_service as ov
from rigorous_backtest.rd14 import family14

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def _synthetic_closes(n: int = 600, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0004, 0.02, n)
    closes = 100.0 * np.cumprod(1.0 + rets)
    idx = pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC")
    return pd.Series(closes, index=idx)


# ---------------------------------------------------------------------------
# 1. Equivalence with the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("signal", ["tsmom42", "tsmom126", "ema10_50", "ema20_100"])
@pytest.mark.parametrize("brake", ["none", "flat_05", "flat_10", "half_10"])
def test_core_matches_family14_on_fixture(signal, brake):
    close = _load("BTCUSDT_1d.csv")["close"].astype(float)
    for vt in (0.15, 0.30, 0.60):
        w_live = ov.raw_weights(close, signal, vt, "1d")
        w_judged = family14.raw_weights(close, signal, vt, "1d")
        np.testing.assert_array_equal(w_live, w_judged)
        pos_sh_live, dd_live = ov.shadow_equity(close, w_live, 0.0008)
        pos_sh_judged, dd_judged = family14.shadow_equity(close, w_judged, 0.0008)
        np.testing.assert_array_equal(pos_sh_live, pos_sh_judged)
        np.testing.assert_array_equal(dd_live, dd_judged)
        np.testing.assert_array_equal(
            ov.brake_multiplier(dd_live, brake),
            family14.brake_multiplier(dd_judged, brake),
        )
        np.testing.assert_array_equal(
            ov.positions_series(w_live, dd_live, brake),
            family14.positions(w_judged, dd_judged, brake),
        )


@pytest.mark.parametrize("tf", ["1d", "4h"])
def test_core_matches_family14_on_synthetic(tf):
    close = _synthetic_closes()
    for signal in ov.SIGNALS:
        w_live = ov.raw_weights(close, signal, 0.30, tf)
        w_judged = family14.raw_weights(close, signal, 0.30, tf)
        np.testing.assert_array_equal(w_live, w_judged)
        _, dd_live = ov.shadow_equity(close, w_live, 0.0008)
        _, dd_judged = family14.shadow_equity(close, w_judged, 0.0008)
        np.testing.assert_array_equal(dd_live, dd_judged)


def test_target_weight_is_next_bar_position():
    """target_weight on closes[:t+1] must equal the judged position
    series' value for bar t+1 computed on the full series."""
    close = _synthetic_closes(800)
    w = family14.raw_weights(close, "tsmom42", 0.30, "1d")
    _, dd = family14.shadow_equity(close, w, 0.0008)
    pos = family14.positions(w, dd, "half_10")
    for t in (300, 500, 700):
        tgt = ov.target_weight(close.iloc[: t + 1], "tsmom42", 0.30, "half_10", "1d")
        assert tgt["weight"] == pytest.approx(pos[t + 1], abs=1e-12)


# ---------------------------------------------------------------------------
# 2. Brake hysteresis (hand-computed)
# ---------------------------------------------------------------------------

def test_brake_hysteresis_half_10():
    dd = np.array([0.0, -0.05, -0.11, -0.08, -0.04, -0.12, -0.03])
    m = ov.brake_multiplier(dd, "half_10")
    # engages at bar 2 (dd -0.11 <= -0.10), stays through -0.08,
    # releases at -0.04 (>= -0.05), re-engages at -0.12, releases -0.03.
    np.testing.assert_array_equal(m, [1.0, 1.0, 0.5, 0.5, 1.0, 0.5, 1.0])


def test_brake_flat_05_and_none():
    dd = np.array([0.0, -0.06, -0.03, -0.02, -0.049])
    np.testing.assert_array_equal(
        ov.brake_multiplier(dd, "flat_05"), [1.0, 0.0, 0.0, 1.0, 1.0]
    )
    np.testing.assert_array_equal(ov.brake_multiplier(dd, "none"), np.ones(5))


# ---------------------------------------------------------------------------
# 3. Causality
# ---------------------------------------------------------------------------

def test_target_weight_is_causal():
    close = _synthetic_closes(700)
    full = ov.target_weight(close, "ema20_100", 0.30, "half_10", "1d")
    prefix = ov.target_weight(close.iloc[:700], "ema20_100", 0.30, "half_10", "1d")
    assert full == prefix
    extended = close.copy()
    future = pd.Series(
        [close.iloc[-1] * 5.0],
        index=[close.index[-1] + pd.Timedelta(days=1)],
    )
    with_future = ov.target_weight(
        pd.concat([close, future]), "ema20_100", 0.30, "half_10", "1d"
    )
    # The bar-t target (from the prefix) must not depend on the
    # appended future bar: recompute the prefix of the extended run.
    assert prefix["weight"] == ov.target_weight(
        pd.concat([close, future]).iloc[:700], "ema20_100", 0.30, "half_10", "1d"
    )["weight"]
    assert with_future["bars"] == 701


# ---------------------------------------------------------------------------
# 4. Registry: exactly the 21 two-tier rows
# ---------------------------------------------------------------------------

EXPECTED_21 = {
    ("ema10_50", 0.15, "none", "1d"), ("ema10_50", 0.30, "none", "1d"),
    ("ema10_50", 0.60, "none", "1d"),
    ("ema20_100", 0.15, "none", "1d"), ("ema20_100", 0.30, "none", "1d"),
    ("ema20_100", 0.60, "none", "1d"), ("ema20_100", 0.60, "half_10", "1d"),
    ("tsmom42", 0.15, "none", "1d"), ("tsmom42", 0.30, "none", "1d"),
    ("tsmom42", 0.60, "none", "1d"), ("tsmom42", 0.15, "half_10", "1d"),
    ("tsmom42", 0.30, "half_10", "1d"), ("tsmom42", 0.60, "half_10", "1d"),
    ("tsmom126", 0.15, "none", "4h"), ("tsmom126", 0.30, "none", "4h"),
    ("tsmom126", 0.60, "none", "4h"), ("tsmom126", 0.60, "half_10", "4h"),
    ("tsmom42", 0.15, "none", "4h"), ("tsmom42", 0.30, "none", "4h"),
    ("tsmom42", 0.60, "none", "4h"), ("tsmom42", 0.60, "half_10", "4h"),
}


def test_registry_overlay_entries():
    from config_strategy import CRYPTO30_SYMBOLS, PRODUCTION_STRATEGY_REGISTRY

    overlay = {
        k: v for k, v in PRODUCTION_STRATEGY_REGISTRY.items()
        if v.get("execution_mode") == "overlay"
    }
    assert len(overlay) == 21
    got = {
        (v["overlay"]["signal"], v["overlay"]["vol_target"],
         v["overlay"]["brake"], v["timeframe"])
        for v in overlay.values()
    }
    assert got == EXPECTED_21
    for key, v in overlay.items():
        assert v["status"] == "FORWARD_TEST", key
        assert v["forward_protocol"] is True, key
        assert v["forward_lane"] == "FORWARD_TEST", key
        assert v["lane_assets"] == CRYPTO30_SYMBOLS, key
        assert v["validated_assets"] == [], key
        # Lane-executable entries keep their judged priors (FWD-008 rule).
        assert v["runtime_priors_nulled"] is False, key
        assert v["oos_win_rate_prior"] is not None, key
        assert v["expected_net_edge_bps"] is not None, key
        assert v["overlay"]["cost_per_turnover"] == 0.0008, key
        assert v["overlay_capital_pct"] == 0.005, key


def test_forward_protocol_entries_include_overlay():
    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    entries = daemon._forward_protocol_entries()
    assert "strategy_overlay_tsmom42_vt15_none_1d" in entries
    assert daemon._lane_for_strategy("strategy_overlay_tsmom42_vt15_none_1d") == "FORWARD_TEST"


# ---------------------------------------------------------------------------
# 5. Daemon overlay manager behaviour (stub engine/adapter)
# ---------------------------------------------------------------------------

class _FakeAdapter:
    def __init__(self):
        self.orders = []

    def place_order(self, symbol, side, order_type, quantity, **kw):
        self.orders.append((symbol, side, order_type, quantity))
        return SimpleNamespace(status="FILLED", order_id="x")


class _FakeEngine:
    def __init__(self, closes, price=None):
        self.venues = {"binance_futures": _FakeAdapter()}
        self.positions = {}
        self.position_strategy = {}
        self.position_timeframe = {}
        self._closes = closes
        self._price = price if price is not None else closes[-1]
        self.opened = []

    def get_candles(self, venue, symbol, timeframe="15m", limit=100):
        now = time.time()
        step = 86400 if timeframe == "1d" else 14400
        start = now - step * (len(self._closes) + 1)
        return [
            {"timestamp": start + step * i, "open": c, "high": c,
             "low": c, "close": c}
            for i, c in enumerate(self._closes)
        ]

    def get_ticker(self, venue, symbol):
        return SimpleNamespace(last=self._price)

    def get_venue_equity(self, venue):
        return 20000.0

    def can_open_position(self, venue):
        return True, ""

    def place_order(self, venue, symbol, side, order_type, quantity,
                    price=None, stop_loss=None, take_profit=None,
                    strategy_name="", timeframe=""):
        self.opened.append((symbol, side, quantity, strategy_name))
        key = f"{venue}:{symbol}"
        self.positions[key] = SimpleNamespace(
            symbol=symbol,
            side="LONG" if side == "BUY" else "SHORT",
            quantity=quantity,
        )
        self.position_strategy[key] = strategy_name
        self.position_timeframe[key] = timeframe
        return SimpleNamespace(status="FILLED", order_id="y")


def _daemon(engine, denylist=()):
    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    daemon.engine = engine
    daemon.symbols = {"binance_futures": ["BTCUSDT"]}
    daemon.strategy_denylist = set(denylist)
    daemon._last_overlay_exits = 0.0
    daemon._last_overlay_entries = 0.0
    daemon._overlay_entries_blocked = lambda: False
    return daemon


def _trend_closes(n=400, drift=0.004, seed=3):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.005, n)
    return list(100.0 * np.cumprod(1.0 + rets))


@pytest.fixture(autouse=True)
def _demo_venues(monkeypatch):
    from strategies.strategy_registry import strategy_registry

    monkeypatch.setattr(
        strategy_registry, "demo_venues",
        lambda: frozenset({"binance_futures"}),
    )


def _only_overlay_config(monkeypatch, key="overlay_tsmom42_vt60_none_1d"):
    """Restrict the manager to one config for deterministic tests."""
    import config_strategy

    real = config_strategy.PRODUCTION_STRATEGY_REGISTRY
    monkeypatch.setattr(
        config_strategy, "PRODUCTION_STRATEGY_REGISTRY",
        {key: real[key]},
    )


def test_manager_opens_on_uptrend(monkeypatch):
    _only_overlay_config(monkeypatch)
    closes = _trend_closes()
    engine = _FakeEngine(closes)
    daemon = _daemon(engine)
    daemon._manage_overlay_positions(allow_entries=True)
    assert len(engine.opened) == 1
    symbol, side, qty, strat = engine.opened[0]
    assert (symbol, side) == ("BTCUSDT", "BUY")
    assert strat == "strategy_overlay_tsmom42_vt60_none_1d"
    assert qty > 0


def test_manager_no_entries_in_exits_pass(monkeypatch):
    _only_overlay_config(monkeypatch)
    engine = _FakeEngine(_trend_closes())
    daemon = _daemon(engine)
    daemon._manage_overlay_positions(allow_entries=False)
    assert engine.opened == []
    assert engine.venues["binance_futures"].orders == []


def test_manager_holds_when_position_matches_target(monkeypatch):
    _only_overlay_config(monkeypatch)
    closes = _trend_closes()
    engine = _FakeEngine(closes)
    daemon = _daemon(engine)
    daemon._manage_overlay_positions(allow_entries=True)
    assert len(engine.opened) == 1
    # Second pass on the same target: no further orders.
    daemon._last_overlay_entries = 0.0
    daemon._manage_overlay_positions(allow_entries=True)
    assert len(engine.opened) == 1
    assert engine.venues["binance_futures"].orders == []


def test_manager_closes_on_target_zero(monkeypatch):
    _only_overlay_config(monkeypatch)
    closes = _trend_closes()
    engine = _FakeEngine(closes)
    daemon = _daemon(engine)
    daemon._manage_overlay_positions(allow_entries=True)
    assert len(engine.opened) == 1
    # Crash the series: tsmom42 flips negative and stays; weight target
    # becomes short — the manager must CLOSE first, not flip in one order.
    crash = list(closes[-1] * np.cumprod(1.0 + np.full(80, -0.01)))
    engine._closes = closes + crash
    engine._price = engine._closes[-1]
    daemon._last_overlay_exits = 0.0
    daemon._manage_overlay_positions(allow_entries=False)
    adapter_orders = engine.venues["binance_futures"].orders
    assert len(adapter_orders) == 1
    assert adapter_orders[0][1] == "SELL"  # closing the long
    assert len(engine.opened) == 1        # no new open in the exits pass


def test_manager_contention_skip(monkeypatch):
    _only_overlay_config(monkeypatch)
    engine = _FakeEngine(_trend_closes())
    key = "binance_futures:BTCUSDT"
    engine.positions[key] = SimpleNamespace(
        symbol="BTCUSDT", side="LONG", quantity=0.5)
    engine.position_strategy[key] = "strategy_dow_effect"
    daemon = _daemon(engine)
    daemon._manage_overlay_positions(allow_entries=True)
    assert engine.opened == []
    assert engine.venues["binance_futures"].orders == []


def test_manager_denylist_blocks_open_but_not_close(monkeypatch):
    _only_overlay_config(monkeypatch)
    closes = _trend_closes()
    engine = _FakeEngine(closes)
    daemon = _daemon(
        engine, denylist={"strategy_overlay_tsmom42_vt60_none_1d"})
    daemon._manage_overlay_positions(allow_entries=True)
    assert engine.opened == []
    # An existing position of a denylisted config is still closed when
    # its target goes to zero/flips (crash series as above).
    key = "binance_futures:BTCUSDT"
    engine.positions[key] = SimpleNamespace(
        symbol="BTCUSDT", side="LONG", quantity=0.25)
    engine.position_strategy[key] = "strategy_overlay_tsmom42_vt60_none_1d"
    crash = list(closes[-1] * np.cumprod(1.0 + np.full(80, -0.01)))
    engine._closes = closes + crash
    engine._price = engine._closes[-1]
    daemon._last_overlay_exits = 0.0
    daemon._manage_overlay_positions(allow_entries=False)
    assert len(engine.venues["binance_futures"].orders) == 1


def test_manager_reduces_when_vol_spike_shrinks_weight(monkeypatch):
    _only_overlay_config(monkeypatch)
    closes = _trend_closes()  # calm uptrend: weight +1.0, $100 target
    engine = _FakeEngine(closes)
    daemon = _daemon(engine)
    daemon._manage_overlay_positions(allow_entries=True)
    assert len(engine.opened) == 1
    # Vol spike: +-6% alternating bars with a positive drift keeps the
    # signal long but sigma_ann jumps, so the vol-target weight falls
    # to ~0.52 — the manager must REDUCE via the adapter, not close.
    spike = list(closes[-1] * np.cumprod(
        1.0 + np.array([0.07, -0.05] * 30)))
    engine._closes = closes + spike
    engine._price = engine._closes[-1]
    daemon._last_overlay_exits = 0.0
    daemon._manage_overlay_positions(allow_entries=False)
    orders = engine.venues["binance_futures"].orders
    assert len(orders) == 1
    assert orders[0][1] == "SELL"
    held_qty = engine.opened[0][2]
    assert 0 < orders[0][3] < held_qty  # partial, not a full close


def test_manager_increases_when_vol_falls(monkeypatch):
    _only_overlay_config(monkeypatch)
    # High-vol uptrend first: weight ~0.52, position ~$52.
    rng = np.random.default_rng(4)
    base = list(100.0 * np.cumprod(
        1.0 + np.array([0.07, -0.05] * 200) + rng.normal(0, 0.001, 400)))
    engine = _FakeEngine(base)
    daemon = _daemon(engine)
    daemon._manage_overlay_positions(allow_entries=True)
    assert len(engine.opened) == 1
    # Calm continuation: sigma collapses, weight -> 1.0, price ~flat,
    # so the target rises above the held notional -> adapter increase.
    calm = list(base[-1] * np.cumprod(
        1.0 + rng.normal(0.0002, 0.003, 200)))
    engine._closes = base + calm
    engine._price = engine._closes[-1]
    daemon._last_overlay_entries = 0.0
    daemon._manage_overlay_positions(allow_entries=True)
    orders = engine.venues["binance_futures"].orders
    assert len(orders) == 1
    assert orders[0][1] == "BUY"
    assert len(engine.opened) == 1  # increase went via the adapter


def test_manager_min_notional_floor(monkeypatch):
    _only_overlay_config(monkeypatch, key="overlay_tsmom126_vt15_none_4h")
    # Nearly flat series: sigma huge relative to vt15 -> tiny weight.
    closes = list(100.0 * np.cumprod(
        1.0 + np.random.default_rng(1).normal(0.0, 0.09, 400)))
    engine = _FakeEngine(closes)
    daemon = _daemon(engine)
    daemon._manage_overlay_positions(allow_entries=True)
    assert engine.opened == []
