"""
tests/test_daemon_governance.py — TASK-STR-SAFETY-001 regression coverage.

Historical hole (found by the 2026-11-14 complete system audit):
strategies/strategy_registry.py glob-discovered every strategy module and
hardcoded status="VALIDATED" for all of them, and autonomy/run_daemon.py
executes through that registry — so strategies that config_strategy.py
governance marks DISABLED (friction-loser scalpers), OBSERVE_ONLY (the
post-incident supertrend, see docs/INCIDENT_2026-11-11_LOSSES.md), or does
not classify at all (a never-register Donchian, a placeholder hybrid) all
reached order placement in the daemon, while the testnet engine — which
honours PRODUCTION_STRATEGY_REGISTRY — ran only the governed set.

These tests pin the fix:
1. Registry statuses come from config_strategy governance, never discovery.
2. A DISABLED strategy's signal function is never even invoked for
   execution; an UNREGISTERED strategy can neither execute nor evaluate.
3. An OBSERVE_ONLY strategy may be evaluated (result tagged observe_only)
   but is BLOCKED on the execution path.
4. Through the daemon's own scan_and_execute: a DISABLED and an
   OBSERVE_ONLY strategy cannot reach engine.place_order; a VALIDATED
   strategy still can (the governed path keeps trading demo).
5. The daemon reads strategy_denylist.json back at startup, so auto-pruned
   strategies stay pruned across restarts.
"""

import time

import pandas as pd
import pytest

import autonomy.run_daemon as run_daemon
from autonomy.run_daemon import StratexTradingEngine
from strategies.strategy_registry import (
    UnifiedStrategyRegistry,
    governance_key_for,
    governance_status_for,
)


@pytest.fixture(scope="module")
def registry():
    return UnifiedStrategyRegistry()


def _df(rows: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=rows, freq="15min")
    return pd.DataFrame(
        {
            "open": [100.0] * rows,
            "high": [101.0] * rows,
            "low": [99.0] * rows,
            "close": [100.0] * rows,
            "volume": [1.0] * rows,
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# 1. Statuses come from governance
# ---------------------------------------------------------------------------


class TestRegistryGovernanceStatuses:
    def test_validated_set_is_exactly_the_governed_set(self, registry):
        validated = {s.name for s in registry.snapshot() if s.status == "VALIDATED"}
        # factory winners are governed VALIDATED but are loaded by the
        # testnet engine's own path, not discovered by this registry.
        assert validated == {"strategy_bb_reversion"}

    def test_disabled_strategies_are_disabled(self, registry):
        for name in (
            "strategy_scalper",
            "strategy_aggressive_scalper",
            "strategy_aggressor",
            "strategy_adx_ema_mtf",
            "strategy_rsi_burst",
            "strategy_vwap_trend",
            "strategy_swing",
            "strategy_ml",
        ):
            spec = registry.get(name)
            assert spec is not None, f"{name} not discovered"
            assert spec.status == "DISABLED", f"{name} status={spec.status}"

    def test_observe_only_strategies_are_observe_only(self, registry):
        for name in ("strategy_supertrend", "strategy_adx_ema"):
            spec = registry.get(name)
            assert spec is not None, f"{name} not discovered"
            assert spec.status == "OBSERVE_ONLY", f"{name} status={spec.status}"

    def test_never_register_and_placeholder_are_unregistered(self, registry):
        # strategy_donchian_observe_only's own docstring says it must never
        # be registered; strategy_hybrid is a self-declared placeholder.
        for name in ("strategy_donchian_observe_only", "strategy_hybrid"):
            assert registry.governance_status(name) == "UNREGISTERED"
            ok, _ = registry.executable(name, "15m", "BTCUSDT")
            assert ok is False

    def test_mapping_functions(self):
        assert governance_key_for("strategy_supertrend") == "supertrend"
        assert governance_key_for("ema_crossover") == "ema_crossover"
        assert governance_status_for("strategy_supertrend") == "OBSERVE_ONLY"
        assert governance_status_for("strategy_scalper") == "DISABLED"
        assert governance_status_for("strategy_bb_reversion") == "VALIDATED"
        assert governance_status_for("factory_winner_1") == "VALIDATED"
        assert governance_status_for("no_such_strategy") == "UNREGISTERED"


# ---------------------------------------------------------------------------
# 2/3. Execution vs evaluation semantics
# ---------------------------------------------------------------------------


class TestRegistryExecutionSemantics:
    def test_disabled_signal_function_never_invoked(self, registry, monkeypatch):
        called = []
        monkeypatch.setitem(
            registry._get_signal_fns,
            "strategy_scalper",
            lambda df: called.append(True) or {"side": "BUY"},
        )
        result = registry.execute_strategy("strategy_scalper", _df(), "1m", "BTCUSDT")
        assert result["status"] == "BLOCKED"
        assert result["reason"] == "STATUS_DISABLED"
        assert called == []
        # Not evaluable either: DISABLED means off, not observe.
        result_obs = registry.execute_strategy(
            "strategy_scalper", _df(), "1m", "BTCUSDT", allow_observe=True
        )
        assert result_obs["status"] == "BLOCKED"
        assert called == []

    def test_observe_only_blocked_for_execution_but_evaluable(self, registry, monkeypatch):
        monkeypatch.setitem(
            registry._get_signal_fns,
            "strategy_supertrend",
            lambda df: {
                "side": "BUY",
                "sl": 95.0,
                "tp": 110.0,
                "win_rate_prior": 0.9,
                "rr_ratio": 2.0,
                "strategy_type": "RULE_BASED",
            },
        )
        blocked = registry.execute_strategy("strategy_supertrend", _df(), "15m", "BTCUSDT")
        assert blocked["status"] == "BLOCKED"
        assert blocked["reason"] == "STATUS_OBSERVE_ONLY"

        observed = registry.execute_strategy(
            "strategy_supertrend", _df(), "15m", "BTCUSDT", allow_observe=True
        )
        assert observed["status"] == "SIGNAL"
        assert observed["observe_only"] is True

    def test_validated_strategy_executes_untagged(self, registry, monkeypatch):
        monkeypatch.setitem(
            registry._get_signal_fns,
            "strategy_bb_reversion",
            lambda df: {
                "side": "BUY",
                "sl": 95.0,
                "tp": 110.0,
                "win_rate_prior": 0.55,
                "rr_ratio": 2.0,
                "strategy_type": "RULE_BASED",
            },
        )
        result = registry.execute_strategy("strategy_bb_reversion", _df(), "15m", "BTCUSDT")
        assert result["status"] == "SIGNAL"
        assert result["observe_only"] is False


# ---------------------------------------------------------------------------
# 4. Through the daemon's own scan path
# ---------------------------------------------------------------------------


class _FakeAdapter:
    def round_quantity(self, symbol, qty):
        return qty

    def min_notional(self, symbol):
        return 0.0


class _FakeTicker:
    last = 100.0


class _FakeOrderResult:
    status = "FILLED"


class _FakeEngine:
    """MultiVenueEngine stand-in: records every place_order call."""

    def __init__(self, candles):
        self.venues = {"binance_futures": _FakeAdapter()}
        self.positions = {}
        self.position_opened_at = {}
        self.position_strategy = {}
        self.position_timeframe = {}
        self.realized_pnl = 0.0
        self.daily_realized_pnl = 0.0
        self.daily_start_equity = 100_000.0
        self.max_daily_loss_pct = 0.02
        self.daily_loss_limit_hit = False
        self.telegram_bot = None
        self._candles = candles
        self.orders = []

    def get_risk_summary(self):
        return {"daily_loss_limit_hit": False, "total_equity": 100_000.0}

    def get_candles(self, venue, symbol, tf, limit):
        return self._candles

    def get_ticker(self, venue, symbol):
        return _FakeTicker()

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
        return _FakeOrderResult()

    def save_state(self):
        pass


class _FakeSpec:
    def __init__(self, status, rr_ratio=2.0):
        self.status = status
        self.rr_ratio = rr_ratio


class _FakeRegistry:
    """Registry stand-in with one strategy per governance class, each
    emitting a strong BUY signal whenever it is (wrongly) invoked."""

    STATUSES = {
        "strategy_scalper": "DISABLED",
        "strategy_supertrend": "OBSERVE_ONLY",
        "strategy_bb_reversion": "VALIDATED",
    }

    def __init__(self):
        self.invoked = []

    def get_all_strategy_names(self):
        return list(self.STATUSES)

    def governance_status(self, name):
        return self.STATUSES[name]

    def executable(self, name, tf, symbol):
        if self.STATUSES[name] != "VALIDATED":
            return False, f"STATUS_{self.STATUSES[name]}"
        return True, "OK"

    def get(self, name):
        return _FakeSpec(self.STATUSES[name])

    def execute_strategy(self, name, df, tf, symbol, allow_observe=False):
        if self.STATUSES[name] == "DISABLED":
            raise AssertionError("DISABLED strategy must never be evaluated")
        if self.STATUSES[name] == "OBSERVE_ONLY" and not allow_observe:
            return {"status": "BLOCKED", "reason": "STATUS_OBSERVE_ONLY", "strategy": name}
        self.invoked.append(name)
        return {
            "status": "SIGNAL",
            "strategy": name,
            "side": "BUY",
            "stop_loss": 99.0,
            "take_profit": 102.0,
            "win_rate_prior": 0.55,
            "rr_ratio": 2.0,
            "confidence": 0.9,
            "strategy_type": "RULE_BASED",
            "observe_only": self.STATUSES[name] == "OBSERVE_ONLY",
        }


def _candles(rows: int = 100):
    now = int(time.time())
    return [
        {
            "timestamp": now - (rows - i) * 900,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1.0,
        }
        for i in range(rows)
    ]


def _daemon(fake_engine) -> StratexTradingEngine:
    d = StratexTradingEngine.__new__(StratexTradingEngine)
    d.engine = fake_engine
    d.scan_interval = 0.0
    d.max_positions = 9999
    d.min_confidence = 0.55
    d.min_rr = 1.5
    d.risk_per_trade = 0.005
    d.max_position_pct = 0.10
    d.min_stop_pct = 0.005
    d.max_stop_pct = 0.030
    d.entry_confluence = 1
    d.adx_threshold = 0.0  # disabled, per the daemon's own convention
    d.fee_rate_roundtrip = 0.0008
    d.min_expectancy_r = 0.10
    d._confluence_signals = {}
    d._last_signal_bar = {}
    d.adx_strategies = set()
    d.strategy_denylist = set()
    d.strategy_allowlist = set()
    d.strategy_priors = {"strategy_bb_reversion": 0.55}
    d.symbols = {"binance_futures": ["BTCUSDT"]}
    d.timeframes = ["15m"]
    d.running = True
    d.last_scan = 0
    d.scan_count = 0
    d._last_trend_manage = time.time()
    import datetime

    d._last_summary_date = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    return d


@pytest.fixture
def daemon_env(monkeypatch):
    fake_registry = _FakeRegistry()
    monkeypatch.setattr(run_daemon, "strategy_registry", fake_registry)
    monkeypatch.setattr("trading_pause.is_trading_paused", lambda: False)
    monkeypatch.setattr("panic_state.is_panic_active", lambda: False)
    monkeypatch.setattr("panic_state.is_kill_switch_locked", lambda: False)
    engine = _FakeEngine(_candles())
    return _daemon(engine), engine, fake_registry


class TestDaemonScanGovernance:
    def test_disabled_and_observe_only_never_reach_order_placement(self, daemon_env):
        daemon, engine, fake_registry = daemon_env
        daemon.scan_and_execute()
        placed_strategies = {o.get("strategy_name") for o in engine.orders}
        assert "strategy_scalper" not in placed_strategies
        assert "strategy_supertrend" not in placed_strategies
        # The DISABLED strategy was not even evaluated; the OBSERVE_ONLY
        # one was evaluated (evidence) but produced no order.
        assert "strategy_scalper" not in fake_registry.invoked
        assert "strategy_supertrend" in fake_registry.invoked

    def test_validated_strategy_still_trades(self, daemon_env):
        daemon, engine, _ = daemon_env
        daemon.scan_and_execute()
        placed_strategies = {o.get("strategy_name") for o in engine.orders}
        assert placed_strategies == {"strategy_bb_reversion"}

    def test_denylisted_validated_strategy_does_not_trade(self, daemon_env):
        daemon, engine, _ = daemon_env
        daemon.strategy_denylist = {"strategy_bb_reversion"}
        daemon.scan_and_execute()
        assert engine.orders == []


# ---------------------------------------------------------------------------
# 5. Denylist read-back
# ---------------------------------------------------------------------------


class TestDenylistReadBack:
    def test_load_denylist_roundtrip(self, monkeypatch, tmp_path):
        deny_file = tmp_path / "strategy_denylist.json"
        monkeypatch.setenv("STRATEX_STRATEGY_DENYLIST_FILE", str(deny_file))

        writer = StratexTradingEngine.__new__(StratexTradingEngine)
        writer.strategy_denylist = {"strategy_momentum", "strategy_hybrid"}
        writer._persist_denylist()

        reader = StratexTradingEngine.__new__(StratexTradingEngine)
        loaded = reader._load_denylist()
        assert loaded == {"strategy_momentum", "strategy_hybrid"}

    def test_load_denylist_missing_file_is_empty(self, monkeypatch, tmp_path):
        monkeypatch.setenv(
            "STRATEX_STRATEGY_DENYLIST_FILE", str(tmp_path / "absent.json")
        )
        engine = StratexTradingEngine.__new__(StratexTradingEngine)
        assert engine._load_denylist() == set()

    def test_load_denylist_corrupt_file_degrades_to_empty(self, monkeypatch, tmp_path):
        deny_file = tmp_path / "strategy_denylist.json"
        deny_file.write_text("{not json", encoding="utf-8")
        monkeypatch.setenv("STRATEX_STRATEGY_DENYLIST_FILE", str(deny_file))
        engine = StratexTradingEngine.__new__(StratexTradingEngine)
        assert engine._load_denylist() == set()
