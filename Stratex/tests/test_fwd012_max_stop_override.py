"""TASK-STR-FWD-012: per-strategy max_stop_pct override — unit coverage.

Production evidence (sleeve-shock probe, 2026-11-17; daemon journal
2026-11-16 12:37 -> 2026-11-17 11:19 IST + ledgers over the sleeve's
whole life): the engine-global max-stop cap (production env
STRATEX_MAX_STOP_PCT=0.15) silently rejected every sleeve_shock_breakout
firing — judged stop 2.0 x weekly ATR, observed stops 21.2-22.3%; 28
detections, 24 max-stop rejections, 0 executions, and zero fills in the
leg's whole life — and blocked dow_effect (judged stop 3.0 x daily ATR)
on 27 of 30 symbols at the 2026-11-17 daily firing (81 skips, stops
16.07-36.00%), silently shaping its forward record toward low-vol
symbols. The skip line named only the symbol, never the strategy.

The fix: an OPTIONAL ``max_stop_pct`` on registry entries, honoured by
_execute_signal when present (registry lookup mirroring
_lane_for_strategy). sleeve_shock_breakout and dow_effect declare 0.90:
under FWD-006, dollar risk is quantity-controlled (size = risk budget /
stop distance, heat cap 0.02), so a wider stop shrinks the position
instead of adding risk — the value is a sanity bound against geometry /
unit errors, set above any plausible genuine ATR-multiple stop.
Strategies without the key keep the global cap exactly as before.

Follow-up (2026-11-18, TASK-STR-FWD-018 wave-1 §3 recommendation):
the two original FWD-003 FORWARD_TEST lane entries — bollinger_trend
(p50_sd2.0 @ CRYPTO30 1d) and shock_breakout (k1.0 @ CRYPTO30 1d) —
carry the same BR24 1d stop geometry (2.0 x ATR(14)) as the wave-1 1d
rows but shipped with NO override. Independent re-measurement with
the wave-1 capcheck method (RD-002 harness signal bars over current
Binance spot 1d klines, full CRYPTO30 universe) found 33.88% of
bollinger p50's 788 judged signals and 34.72% of shock k1.0's 2,180
judged signals above the 0.15 global cap (median stops 12.76% /
13.00%, max 36.24% both) — once the lane is allowlisted, ~1/3 of
their judged signals would be silently cap-rejected, the
sleeve_shock failure mode. Both entries now declare
max_stop_pct = 0.50, the wave-1 value (a sanity bound above the whole
measured distribution; under FWD-006 the wider stop shrinks the
position, it does not add risk). The third executable lane entry,
adx_ema_bare (4h, 3.0 x ATR module bracket), deliberately keeps NO
override — it is outside this follow-up's scope, and its absence is
pinned below.

Everything is offline: fake engine/adapter only, no network, no orders.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Ticker:
    last = 100.0
    bid = 99.99
    ask = 100.01


class _Adapter:
    def round_quantity(self, symbol, qty):
        return qty

    def min_notional(self, symbol):
        return 0.0


class _Engine:
    """Minimal MultiVenueEngine stand-in for _execute_signal."""

    def __init__(self):
        self.venues = {"binance_futures": _Adapter()}
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
            order_id="FWD012-1", symbol=kwargs["symbol"], side=kwargs["side"],
            order_type="MARKET", price=100.0, quantity=kwargs["quantity"],
            status="FILLED", executed_qty=kwargs["quantity"], avg_price=100.0,
        )


def _daemon(engine, global_cap=0.15):
    from autonomy.run_daemon import StratexTradingEngine

    d = StratexTradingEngine.__new__(StratexTradingEngine)
    d.engine = engine
    d.min_stop_pct = 0.005
    # Production env value (STRATEX_MAX_STOP_PCT=0.15), not the 3% default.
    d.max_stop_pct = global_cap
    d.risk_per_trade = 0.001   # FWD-006 package
    d.max_heat_pct = 0.02      # FWD-006 package
    d.max_position_pct = 0.10  # FWD-006 package
    d.adx_threshold = 0.0
    d.fee_rate_roundtrip = 0.0008
    d.friction_rate_roundtrip = 0.0016
    d.min_expectancy_r = 0.10
    d.strategy_priors = {
        "strategy_sleeve_shock_breakout": 0.4267,  # registry prior
        "strategy_dow_effect": 0.5227,             # registry prior
        "strategy_ichimoku_trend": 0.55,
    }
    return d


@pytest.fixture
def _no_pause(monkeypatch):
    monkeypatch.setattr("trading_pause.is_trading_paused", lambda: False)
    monkeypatch.setattr("panic_state.is_panic_active", lambda: False)
    monkeypatch.setattr("panic_state.is_kill_switch_locked", lambda: False)


# Wide-stop geometry at price 100: sl_dist 22 -> stop 22% (the observed
# sleeve_shock_breakout shape), tp_dist 44 -> rr 2.0 (the judged bracket).
_SHOCK_SIGNAL = {
    "side": "SELL",
    "strategy": "strategy_sleeve_shock_breakout",
    "sl_dist": 22.0,
    "tp_dist": 44.0,
}


# ----------------------------------------------------------------------
# (a) registry override honoured for a wide-stop signal
# ----------------------------------------------------------------------

def test_override_lets_sleeve_shock_wide_stop_execute(_no_pause):
    engine = _Engine()
    daemon = _daemon(engine)
    # 22% stop > 15% global cap: only the registry override lets this run.
    assert daemon._execute_signal(
        "binance_futures", "BTCUSDT", dict(_SHOCK_SIGNAL), "1wk"
    ) is True
    assert len(engine.orders) == 1


def test_override_lets_dow_effect_wide_stop_execute(_no_pause):
    engine = _Engine()
    daemon = _daemon(engine)
    # 30% stop: inside dow_effect's observed genuine range (16.07-36.00%),
    # above the 15% global cap.
    sig = {
        "side": "BUY",
        "strategy": "strategy_dow_effect",
        "sl_dist": 30.0,
        "tp_dist": 60.0,
    }
    assert daemon._execute_signal(
        "binance_futures", "SOLUSDT", sig, "1d"
    ) is True
    assert len(engine.orders) == 1


# ----------------------------------------------------------------------
# (b) no-override strategy still rejected above the global cap
# ----------------------------------------------------------------------

def test_strategy_without_override_still_rejected_above_global_cap(_no_pause):
    engine = _Engine()
    daemon = _daemon(engine)
    # ichimoku_trend declares no max_stop_pct: the global cap binds.
    sig = {
        "side": "BUY",
        "strategy": "strategy_ichimoku_trend",
        "sl_dist": 22.0,
        "tp_dist": 44.0,
    }
    assert daemon._execute_signal(
        "binance_futures", "BTCUSDT", sig, "4h"
    ) is False
    assert engine.orders == []


# ----------------------------------------------------------------------
# (c) override does not change position sizing math (FWD-006)
# ----------------------------------------------------------------------

def test_override_does_not_change_sizing_math(_no_pause):
    engine = _Engine()
    daemon = _daemon(engine)
    assert daemon._execute_signal(
        "binance_futures", "BTCUSDT", dict(_SHOCK_SIGNAL), "1wk"
    ) is True
    qty = engine.orders[0]["quantity"]
    # FWD-006: risk_amount = venue equity x risk_per_trade = 10,000 x
    # 0.001 = $10; size = risk / stop distance = 10 / 22. The wider stop
    # shrinks the position; dollar risk is unchanged by the override.
    assert qty == pytest.approx(10.0 / 22.0)


def test_narrow_stop_sizes_by_same_formula(_no_pause):
    # Control: a stop inside the global cap sizes by the identical
    # formula, with and without an override on the strategy.
    engine = _Engine()
    daemon = _daemon(engine)
    sig = dict(_SHOCK_SIGNAL, sl_dist=10.0, tp_dist=20.0)
    assert daemon._execute_signal(
        "binance_futures", "BTCUSDT", sig, "1wk"
    ) is True
    assert engine.orders[0]["quantity"] == pytest.approx(10.0 / 10.0)


# ----------------------------------------------------------------------
# (e) FWD-003 lane entries: the 0.50 override is honoured end-to-end
# ----------------------------------------------------------------------

def _lane_daemon(engine):
    daemon = _daemon(engine)
    # Registry priors (config_strategy.py) for the expectancy gate.
    daemon.strategy_priors["strategy_bollinger_trend"] = 0.3929
    daemon.strategy_priors["strategy_shock_breakout"] = 0.3893
    return daemon


def test_override_lets_bollinger_trend_wide_stop_execute(_no_pause):
    engine = _Engine()
    daemon = _lane_daemon(engine)
    # 22% stop at price 100: above the 15% global cap, inside the
    # entry's 0.50 override. Measured: 33.88% of bollinger p50's
    # judged 1d signals carry a stop above the global cap.
    sig = {
        "side": "BUY",
        "strategy": "strategy_bollinger_trend",
        "sl_dist": 22.0,
        "tp_dist": 44.0,
    }
    assert daemon._execute_signal(
        "binance_futures", "BTCUSDT", sig, "1d"
    ) is True
    assert len(engine.orders) == 1


def test_override_lets_shock_breakout_wide_stop_execute(_no_pause):
    engine = _Engine()
    daemon = _lane_daemon(engine)
    # Measured: 34.72% of shock k1.0's judged 1d signals carry a stop
    # above the global cap.
    sig = {
        "side": "SELL",
        "strategy": "strategy_shock_breakout",
        "sl_dist": 22.0,
        "tp_dist": 44.0,
    }
    assert daemon._execute_signal(
        "binance_futures", "ETHUSDT", sig, "1d"
    ) is True
    assert len(engine.orders) == 1


# ----------------------------------------------------------------------
# (d) max-stop skip log line names the strategy
# ----------------------------------------------------------------------

def test_max_stop_skip_log_names_strategy(_no_pause, monkeypatch):
    import autonomy.run_daemon as rd

    lines = []

    class _Log:
        def info(self, msg, *args, **kwargs):
            lines.append(str(msg))

        def warning(self, msg, *args, **kwargs):
            lines.append(str(msg))

        def error(self, msg, *args, **kwargs):
            lines.append(str(msg))

        def debug(self, msg, *args, **kwargs):
            pass

    monkeypatch.setattr(rd, "logger", _Log())
    engine = _Engine()
    daemon = _daemon(engine)
    sig = {
        "side": "BUY",
        "strategy": "strategy_ichimoku_trend",
        "sl_dist": 22.0,
        "tp_dist": 44.0,
    }
    assert daemon._execute_signal(
        "binance_futures", "ETHUSDT", sig, "4h"
    ) is False
    skips = [line for line in lines if "risk too large" in line]
    assert len(skips) == 1
    assert "strategy_ichimoku_trend" in skips[0]
    assert "ETHUSDT" in skips[0]
    assert "22.00%" in skips[0]
    assert "15.00%" in skips[0]


# ----------------------------------------------------------------------
# helper + registry pins
# ----------------------------------------------------------------------

def test_max_stop_override_lookup():
    from autonomy.run_daemon import StratexTradingEngine

    d = StratexTradingEngine.__new__(StratexTradingEngine)
    assert d._max_stop_pct_for_strategy("strategy_sleeve_shock_breakout") == 0.90
    assert d._max_stop_pct_for_strategy("strategy_dow_effect") == 0.90
    # FWD-003 lane follow-up (2026-11-18): both 1d lane entries declare
    # 0.50 (measured ~34% of judged signals above the 0.15 global cap).
    assert d._max_stop_pct_for_strategy("strategy_bollinger_trend") == 0.50
    assert d._max_stop_pct_for_strategy("strategy_shock_breakout") == 0.50
    # Bare registry keys (no module prefix) resolve too.
    assert d._max_stop_pct_for_strategy("sleeve_shock_breakout") == 0.90
    assert d._max_stop_pct_for_strategy("bollinger_trend") == 0.50
    # No key on the entry -> None (global cap applies).
    assert d._max_stop_pct_for_strategy("strategy_ichimoku_trend") is None
    # adx_ema_bare (the third executable lane entry) deliberately has
    # no override in this follow-up's scope.
    assert d._max_stop_pct_for_strategy("strategy_adx_ema_bare") is None
    # Unknown / empty strategies fail safe to None.
    assert d._max_stop_pct_for_strategy("strategy_does_not_exist") is None
    assert d._max_stop_pct_for_strategy("") is None


def test_registry_declares_overrides():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    assert PRODUCTION_STRATEGY_REGISTRY["sleeve_shock_breakout"]["max_stop_pct"] == 0.90
    assert PRODUCTION_STRATEGY_REGISTRY["dow_effect"]["max_stop_pct"] == 0.90
    # FWD-003 lane follow-up (2026-11-18).
    assert PRODUCTION_STRATEGY_REGISTRY["bollinger_trend"]["max_stop_pct"] == 0.50
    assert PRODUCTION_STRATEGY_REGISTRY["shock_breakout"]["max_stop_pct"] == 0.50
    assert "max_stop_pct" not in PRODUCTION_STRATEGY_REGISTRY["adx_ema_bare"]
