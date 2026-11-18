"""TASK-STR-FWD-003 — the FORWARD-TEST lane for RD-002's watchlist.

The four RD-002 WATCHLIST configurations passed the mechanical bar but
failed Bonferroni significance; the owner directed that real demo
forward evidence decide them. This file pins:

1. EQUIVALENCE: the production lane modules (strategy_bollinger_trend,
   strategy_shock_breakout, strategy_adx_ema_bare) reproduce the judged
   rd2 harness entry-for-entry on real historical slices
   (tests/fixtures/fwd002/, shared with TASK-STR-FWD-002).
2. GOVERNANCE: the FORWARD_TEST classification is distinct from the
   VALIDATED entrants, keeps its judged priors, binds its lane_assets,
   and tsmom2_dual is registered-but-excluded (no module, no assets,
   forward_protocol off) because its judged Yahoo-futures universe
   cannot be traded faithfully on either demo venue.
3. DEMO-ONLY ENFORCEMENT: the registry executes FORWARD_TEST
   strategies only when the caller names a venue the host daemon has
   attested as demo; everywhere else the lane is blocked fail-closed.
4. DAEMON WIRING: the lane flows through the scan/execution path with
   its judged geometry (the forward-protocol min-RR exemption covers
   adx_ema_bare's RR 1.0), the phase-3 forward guard evaluates lane
   strategies (kill criteria), and closed lane positions are booked
   into the Phase-2 ledger tagged lane=FORWARD_TEST.
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

import strategy_adx_ema as prod_adx
import strategy_adx_ema_bare as adx_bare
import strategy_bollinger_trend as bol
import strategy_shock_breakout as shk
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence: production modules vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_bollinger_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_bollinger_trend(df, 50, WARMUP)
    production = bol.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_shock_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_shock(df, 1.0, WARMUP)
    production = shk.entries_for_frame(df, WARMUP)
    assert len(judged) >= 20, "fixture must contain a meaningful entry set"
    assert production == judged


def _gov2_bare_entries(df: pd.DataFrame):
    """Inline replica of the judged gov2 bare evaluation
    (rd2/gov2.py eval_module_cell with signal_filter=None):
    features once over the frame, get_signal on trailing <=500-bar
    windows, bars [260, len-2]; distances from the signal-bar close."""
    featured = prod_adx.add_features(df)
    closes = df["close"].to_numpy(dtype=float)
    out = []
    for i in range(WARMUP, len(df) - 1):
        res = prod_adx.get_signal(featured.iloc[max(0, i - 499): i + 1].copy())
        if res is None or res.side not in ("BUY", "SELL") or res.sl is None:
            continue
        if res.side == "BUY":
            out.append((i, "LONG", closes[i] - res.sl, res.tp - closes[i]))
        else:
            out.append((i, "SHORT", res.sl - closes[i], closes[i] - res.tp))
    return out


@pytest.mark.parametrize("fixture", ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"])
def test_adx_bare_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = _gov2_bare_entries(df)
    production = adx_bare.entries_for_frame(df, WARMUP)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged
    # The judged module bracket is 3.0 x ATR both sides (RR 1.0).
    featured = prod_adx.add_features(df)
    for i, _side, sl_dist, tp_dist in production:
        atr_i = float(featured["atr_adx_ema"].iloc[i])
        assert sl_dist == pytest.approx(3.0 * atr_i)
        assert tp_dist == pytest.approx(3.0 * atr_i)


@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "BTCUSDT_4h.csv"])
def test_atr_matches_judged_harness(fixture):
    df = _load(fixture)
    expected = harness_atr(df, 14)
    np.testing.assert_allclose(bol.atr14(df).to_numpy(), expected.to_numpy())
    np.testing.assert_allclose(shk.atr14(df).to_numpy(), expected.to_numpy())
    featured = prod_adx.add_features(df)
    np.testing.assert_allclose(
        featured["atr_adx_ema"].to_numpy(), expected.to_numpy()
    )


def test_bollinger_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_1d.csv")
    judged = families3.sig_bollinger_trend(df, 50, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:6]:
        sig = bol.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.3929)
        assert sig["rr_ratio"] == pytest.approx(2.0)
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert bol.get_signal(df.iloc[: quiet + 1])["side"] is None


def test_shock_live_signal_reproduces_judged_bracket():
    df = _load("SOLUSDT_1d.csv")
    judged = families3.sig_shock(df, 1.0, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:6]:
        sig = shk.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.3893)
        assert sig["rr_ratio"] == pytest.approx(2.0)
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert shk.get_signal(df.iloc[: quiet + 1])["side"] is None


def test_adx_bare_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_4h.csv")
    judged = adx_bare.entries_for_frame(df, WARMUP)
    assert judged, "fixture must contain judged entries"
    for i, side, sl_dist, tp_dist in judged[:4]:
        sig = adx_bare.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(sl_dist)
        assert sig["tp_dist"] == pytest.approx(tp_dist)
        # The lane's own RD-002 prior — NOT the production module's
        # (deliberately None) and NOT the production config's record.
        assert sig["win_rate_prior"] == pytest.approx(0.5699)
        assert sig["rr_ratio"] == pytest.approx(1.0)


def test_forming_bar_is_never_evaluated():
    now = 1_800_000_000.0  # fixed epoch, arbitrary
    # 1d modules: bars opening now-3d / now-2d / now-1d-1s are closed;
    # the bar opening now-1h is still forming.
    opens = [now - 3 * 86400, now - 2 * 86400, now - 86400 - 1, now - 3600]
    idx = pd.to_datetime(opens, unit="s", utc=True)
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx,
    )
    assert len(bol._closed_frame(df, now_s=now)) == 3
    assert len(shk._closed_frame(df, now_s=now)) == 3
    # 4h wrapper: opens at now-12h / now-8h / now-4h-1s closed, now-1h forming.
    opens4 = [now - 12 * 3600, now - 8 * 3600, now - 4 * 3600 - 1, now - 3600]
    idx4 = pd.to_datetime(opens4, unit="s", utc=True)
    df4 = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx4,
    )
    assert len(adx_bare._closed_frame(df4, now_s=now)) == 3


# ---------------------------------------------------------------------------
# 2. Governance: the FORWARD_TEST classification
# ---------------------------------------------------------------------------

def test_config_registry_lane_entries():
    from config_strategy import CRYPTO30_SYMBOLS, PRODUCTION_STRATEGY_REGISTRY

    for key, wr, pf, rr in (
        ("bollinger_trend", 0.3929, 1.456, 2.0),
        ("shock_breakout", 0.3893, 1.318, 2.0),
        ("adx_ema_bare", 0.5699, 1.233, 1.0),
    ):
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["forward_protocol"] is True, key
        assert entry["forward_lane"] == "FORWARD_TEST", key
        assert entry["lane_assets"] == CRYPTO30_SYMBOLS, key
        # Judged priors survive the registry's nulling loop (the
        # daemon's expectancy gate reads them) — this entry is
        # lane-executable, so the null-out stamp says so.
        assert entry["runtime_priors_nulled"] is False, key
        assert entry["oos_win_rate_prior"] == pytest.approx(wr), key
        assert entry["expected_net_edge_bps"] > 0, key
        assert entry["rr_ratio"] == pytest.approx(rr), key
        # The lane is not a validation: no validated_assets key may
        # carry the universe for a FORWARD_TEST entry.
        assert not entry.get("validated_assets"), key

    # The passed entrants are untouched. The VALIDATED set also holds
    # the FWD-002 sleeve extension's components (sleeve_shock_breakout
    # with a daemon module; sleeve_tsmom2_dual registry-only, running
    # through the OANDA sleeve runner) — separate judged objects from
    # this lane's shock_breakout / tsmom2_dual, with separate records —
    # and fx_mr_v4, the OANDA forward entrant registered by
    # TASK-STR-FWD-004 after this lane landed.
    validated = {
        k for k, e in PRODUCTION_STRATEGY_REGISTRY.items() if e["status"] == "VALIDATED"
    }
    assert validated == {
        "ichimoku_trend",
        "dow_effect",
        "fx_mr_v4",
        "sleeve_shock_breakout",
        "sleeve_tsmom2_dual",
    }
    # adx_ema's production configuration keeps its own measurement.
    assert PRODUCTION_STRATEGY_REGISTRY["adx_ema"]["status"] == "OBSERVE_ONLY"


def test_tsmom2_registered_but_excluded():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY
    from strategies.strategy_registry import UnifiedStrategyRegistry

    entry = PRODUCTION_STRATEGY_REGISTRY["tsmom2_dual"]
    assert entry["status"] == "FORWARD_TEST"
    assert entry["forward_protocol"] is False
    assert entry["lane_assets"] == []
    assert "EXCLUDED" in entry["reason"]
    # Null-out follow-up (2026-11-16): a registration that cannot trade
    # carries NO live runtime claims in the registry — its judged
    # numbers survive only in the TSMOM2_DUAL_STRATEGY config dict and
    # in the reason text above, and the record is stamped as nulled.
    assert entry["oos_win_rate_prior"] is None
    assert entry["expected_net_edge_bps"] is None
    assert entry["runtime_priors_nulled"] is True
    # No production module exists for it, so discovery finds nothing
    # and nothing can evaluate or execute it.
    reg = UnifiedStrategyRegistry()
    assert reg.get("strategy_tsmom2_dual") is None
    assert not reg.executable("strategy_tsmom2_dual", "4h", "XAUUSD", venue="oanda")[0]


# ---------------------------------------------------------------------------
# 3. Demo-only enforcement in the registry
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def registry():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    return UnifiedStrategyRegistry()


def test_lane_blocked_without_demo_attestation(registry):
    # Fresh registry: no daemon has attested demo venues yet.
    assert registry.demo_venues() == frozenset()
    ok, reason = registry.executable(
        "strategy_bollinger_trend", "1d", "BTCUSDT", venue="binance_futures"
    )
    assert not ok and reason == "FORWARD_TEST_DEMO_VENUE_ONLY"
    ok, reason = registry.executable("strategy_bollinger_trend", "1d", "BTCUSDT")
    assert not ok and reason == "FORWARD_TEST_REQUIRES_VENUE"


def test_lane_executable_only_on_attested_demo_venue(registry):
    registry.set_demo_venues({"binance_futures"})
    try:
        assert registry.executable(
            "strategy_bollinger_trend", "1d", "BTCUSDT", venue="binance_futures"
        )[0]
        assert registry.executable(
            "strategy_shock_breakout", "1d", "AAVEUSDT", venue="binance_futures"
        )[0]
        assert registry.executable(
            "strategy_adx_ema_bare", "4h", "ETHUSDT", venue="binance_futures"
        )[0]
        # Wrong timeframe / off-universe symbol / unattested venue.
        assert not registry.executable(
            "strategy_bollinger_trend", "4h", "BTCUSDT", venue="binance_futures"
        )[0]
        assert not registry.executable(
            "strategy_bollinger_trend", "1d", "EURUSD", venue="binance_futures"
        )[0]
        assert not registry.executable(
            "strategy_bollinger_trend", "1d", "BTCUSDT", venue="oanda"
        )[0]
        # VALIDATED entrants are unaffected by the venue rule.
        assert registry.executable("strategy_ichimoku_trend", "4h", "BTCUSDT")[0]
        assert registry.executable(
            "strategy_ichimoku_trend", "4h", "BTCUSDT", venue="anywhere"
        )[0]
    finally:
        registry.set_demo_venues(set())


def test_lane_execute_strategy_blocked_and_tagged(registry, monkeypatch):
    monkeypatch.setitem(
        registry._get_signal_fns,
        "strategy_shock_breakout",
        lambda df: {
            "side": "BUY",
            "sl_dist": 2.0,
            "tp_dist": 4.0,
            "win_rate_prior": 0.3893,
            "rr_ratio": 2.0,
            "strategy_type": "RULE_BASED",
        },
    )
    df = _load("BTCUSDT_1d.csv")
    blocked = registry.execute_strategy(
        "strategy_shock_breakout", df, "1d", "BTCUSDT", venue="binance_futures"
    )
    assert blocked["status"] == "BLOCKED"
    assert blocked["reason"] == "FORWARD_TEST_DEMO_VENUE_ONLY"

    registry.set_demo_venues({"binance_futures"})
    try:
        sig = registry.execute_strategy(
            "strategy_shock_breakout", df, "1d", "BTCUSDT", venue="binance_futures"
        )
        assert sig["status"] == "SIGNAL"
        assert sig["forward_test"] is True
        assert sig["observe_only"] is False
    finally:
        registry.set_demo_venues(set())


def test_adx_bare_and_adx_production_are_distinct_records(registry):
    assert registry.governance_status("strategy_adx_ema") == "OBSERVE_ONLY"
    assert registry.governance_status("strategy_adx_ema_bare") == "FORWARD_TEST"
    # The production config can evaluate for evidence but never execute,
    # even on an attested demo venue; the bare lane config is the
    # reverse — it exists to execute (demo only).
    assert not registry.executable(
        "strategy_adx_ema", "4h", "BTCUSDT", venue="binance_futures"
    )[0]
    assert registry.evaluable("strategy_adx_ema", "4h", "BTCUSDT")[0]
    assert registry.evaluable("strategy_adx_ema_bare", "4h", "BTCUSDT")[0]


# ---------------------------------------------------------------------------
# 4. Daemon wiring
# ---------------------------------------------------------------------------

def _daemon_bare():
    from autonomy.run_daemon import StratexTradingEngine

    return StratexTradingEngine.__new__(StratexTradingEngine)


def test_forward_protocol_entries_cover_the_lane():
    daemon = _daemon_bare()
    entries = daemon._forward_protocol_entries()
    for name in (
        "strategy_bollinger_trend",
        "strategy_shock_breakout",
        "strategy_adx_ema_bare",
        "strategy_ichimoku_trend",
        "strategy_dow_effect",
    ):
        assert name in entries, name
    # The excluded candidate is NOT under the forward protocol.
    assert "strategy_tsmom2_dual" not in entries


def test_lane_tag_mapping():
    daemon = _daemon_bare()
    assert daemon._lane_for_strategy("strategy_bollinger_trend") == "FORWARD_TEST"
    assert daemon._lane_for_strategy("strategy_shock_breakout") == "FORWARD_TEST"
    assert daemon._lane_for_strategy("strategy_adx_ema_bare") == "FORWARD_TEST"
    assert daemon._lane_for_strategy("strategy_ichimoku_trend") is None
    assert daemon._lane_for_strategy("strategy_dow_effect") is None
    assert daemon._lane_for_strategy("strategy_adx_ema") is None
    assert daemon._lane_for_strategy("strategy_unknown") is None


def test_forward_guard_hook_pauses_lane_strategy(monkeypatch):
    from measurement import fill_ledger

    base = 1_700_000_000.0
    rows = [
        {
            "strategy": "strategy_bollinger_trend",
            "engine": "daemon",
            "lane": "FORWARD_TEST",
            "net_pnl": -1.0,
            "exit_time": base + 3600 * k,
        }
        for k in range(55)
    ]
    monkeypatch.setattr(fill_ledger, "read_fills", lambda: rows)
    daemon = _daemon_bare()
    daemon.engine = SimpleNamespace(
        get_risk_summary=lambda: {"total_equity": 10_000.0}
    )
    daemon.strategy_denylist = set()
    persisted = []
    daemon._persist_denylist = lambda: persisted.append(True)
    daemon._maybe_apply_forward_guard()
    assert "strategy_bollinger_trend" in daemon.strategy_denylist
    assert persisted


# --- Scan-path behaviour with a fake registry -------------------------------

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
    def __init__(self, candles, venues=("binance_futures",)):
        self.venues = {v: _FakeAdapter() for v in venues}
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
        # TASK-STR-FWD-006: the daemon sizes on VENUE equity through
        # this method (MultiVenueEngine.get_venue_equity) and fails
        # closed when it is unavailable; the fake's venue holds the
        # full test equity.
        return 100_000.0

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


class _LaneFakeRegistry:
    """Registry stand-in: one FORWARD_TEST strategy with judged RR 1.0
    (adx_ema_bare's real name, so the daemon's forward-protocol set —
    read from the real config — covers it) and one VALIDATED strategy
    also with RR 1.0 (control: the generic min-RR filter must still
    block it)."""

    STATUSES = {
        "strategy_adx_ema_bare": "FORWARD_TEST",
        "strategy_fake_validated": "VALIDATED",
    }

    def __init__(self, demo_venues):
        self._demo = set(demo_venues)
        self.invoked = []

    def get_all_strategy_names(self):
        return list(self.STATUSES)

    def governance_status(self, name):
        return self.STATUSES[name]

    def get(self, name):
        return SimpleNamespace(status=self.STATUSES[name], rr_ratio=1.0)

    def executable(self, name, tf, symbol, venue=None):
        if self.STATUSES[name] == "FORWARD_TEST":
            if venue in self._demo:
                return True, "OK"
            return False, "FORWARD_TEST_DEMO_VENUE_ONLY"
        return True, "OK"

    def demo_venues(self):
        return frozenset(self._demo)

    def execute_strategy(self, name, df, tf, symbol, allow_observe=False, venue=None):
        ok, reason = self.executable(name, tf, symbol, venue=venue)
        if not ok:
            return {"status": "BLOCKED", "reason": reason, "strategy": name}
        self.invoked.append(name)
        return {
            "status": "SIGNAL",
            "strategy": name,
            "side": "BUY",
            "stop_loss": 99.0,
            "take_profit": 101.0,
            "win_rate_prior": 0.5699,
            "rr_ratio": 1.0,
            "strategy_type": "RULE_BASED",
            "observe_only": False,
            "forward_test": self.STATUSES[name] == "FORWARD_TEST",
        }


def _candles(rows: int = 300, bar_seconds: int = 14400):
    now = int(time.time())
    return [
        {
            "timestamp": now - (rows - i) * bar_seconds,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1.0,
        }
        for i in range(rows)
    ]


def _scan_daemon(fake_engine):
    import datetime

    from autonomy.run_daemon import StratexTradingEngine

    d = StratexTradingEngine.__new__(StratexTradingEngine)
    d.engine = fake_engine
    d.scan_interval = 0.0
    d.max_positions = 9999
    d.min_confidence = 0.55
    d.min_rr = 1.5
    d.risk_per_trade = 0.01
    d.max_heat_pct = 0.02  # mirrors __init__ (STRATEX_MAX_HEAT_PCT_PER_STRATEGY default; TASK-STR-FWD-006)
    d.max_position_pct = 0.10
    d.min_stop_pct = 0.005
    d.max_stop_pct = 0.030
    d.entry_confluence = 1
    d.adx_threshold = 0.0
    d.fee_rate_roundtrip = 0.0008
    d.min_expectancy_r = 0.05  # the live Server-1 value
    d._confluence_signals = {}
    d._last_signal_bar = {}
    d.adx_strategies = set()
    d.strategy_denylist = set()
    d.strategy_allowlist = set()
    d.strategy_priors = {}
    d.symbols = {v: ["BTCUSDT"] for v in fake_engine.venues}
    d.timeframes = ["4h"]
    d.running = True
    d.last_scan = 0
    d.scan_count = 0
    d._last_trend_manage = time.time()
    d._shadow = None
    d._last_summary_date = datetime.datetime.now(
        datetime.timezone.utc
    ).date().isoformat()
    return d


@pytest.fixture
def scan_env(monkeypatch):
    import autonomy.run_daemon as run_daemon

    monkeypatch.setattr("trading_pause.is_trading_paused", lambda: False)
    monkeypatch.setattr("panic_state.is_panic_active", lambda: False)
    monkeypatch.setattr("panic_state.is_kill_switch_locked", lambda: False)
    return run_daemon, monkeypatch


def test_lane_strategy_executes_on_demo_despite_min_rr(scan_env):
    run_daemon, monkeypatch = scan_env
    fake_registry = _LaneFakeRegistry({"binance_futures"})
    monkeypatch.setattr(run_daemon, "strategy_registry", fake_registry)
    engine = _FakeEngine(_candles())
    daemon = _scan_daemon(engine)
    results = daemon.scan_and_execute()
    assert results["errors"] == 0
    # The lane's judged RR 1.0 clears the forward-protocol exemption
    # and reaches order placement on the demo venue...
    assert fake_registry.invoked == ["strategy_adx_ema_bare"]
    placed = {o.get("strategy_name") for o in engine.orders}
    assert placed == {"strategy_adx_ema_bare"}
    # ...while the VALIDATED control with the same RR 1.0 is still
    # stopped by the generic min-RR pre-filter (never even evaluated).
    assert "strategy_fake_validated" not in fake_registry.invoked


def test_lane_strategy_blocked_on_non_demo_venue(scan_env):
    run_daemon, monkeypatch = scan_env
    fake_registry = _LaneFakeRegistry({"binance_futures"})
    monkeypatch.setattr(run_daemon, "strategy_registry", fake_registry)
    engine = _FakeEngine(_candles(), venues=("live_venue",))
    daemon = _scan_daemon(engine)
    results = daemon.scan_and_execute()
    assert results["errors"] == 0
    assert fake_registry.invoked == []
    assert engine.orders == []


# --- Ledger tagging through the reconciler ----------------------------------

class _ReconcileAdapter:
    def get_positions_or_none(self):
        return []  # flat at the broker: the tracked position has closed

    def get_realized_pnl(self, symbol, since_ms=None):
        return {
            "net": 5.0,
            "gross": 5.4,
            "fees": 0.4,
            "trades": 1,
            "last_price": 101.0,
        }

    def cancel_protective_orders(self, symbol):
        return 0


class _ReconcileEngine:
    def __init__(self, strategy_name):
        key = "binance_futures:BTCUSDT"
        self.venues = {"binance_futures": _ReconcileAdapter()}
        self.positions = {
            key: SimpleNamespace(
                symbol="BTCUSDT",
                side="LONG",
                quantity=0.1,
                entry_price=100.0,
                mark_price=101.0,
                position_id="t1",
            )
        }
        self.position_opened_at = {key: (time.time() - 3600) * 1000}
        self.position_strategy = {key: strategy_name}
        self.position_timeframe = {key: "1d"}
        self.realized_pnl = 0.0
        self.daily_realized_pnl = 0.0
        self.telegram_bot = None

    def _check_daily_loss_limit(self):
        pass

    def save_state(self):
        pass

    def mark_exit(self, venue, symbol):
        pass

    def equity_snapshot(self, trigger="fill"):
        return {"engine": "daemon", "trigger": trigger, "total_equity": 10_000.0}


def _run_reconcile(monkeypatch, tmp_path, strategy_name):
    import json as _json

    import autonomy.run_daemon as run_daemon
    from measurement import fill_ledger

    fills = tmp_path / "fills.jsonl"
    snaps = tmp_path / "snaps.jsonl"
    monkeypatch.setattr(fill_ledger, "fill_ledger_path", lambda: fills)
    monkeypatch.setattr(fill_ledger, "equity_snapshot_path", lambda: snaps)
    # The legacy ledger path derives from run_daemon.__file__.
    fake_file = tmp_path / "autonomy" / "run_daemon.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(run_daemon, "__file__", str(fake_file))

    daemon = _daemon_bare()
    daemon.engine = _ReconcileEngine(strategy_name)
    daemon._reconcile_pass = 1  # keep the untracked sweep out of this pass
    daemon._reconcile_positions()

    fill_rows = [
        _json.loads(line) for line in fills.read_text().splitlines() if line.strip()
    ]
    legacy = tmp_path / "testnet_trade_ledger.jsonl"
    legacy_rows = (
        [_json.loads(line) for line in legacy.read_text().splitlines() if line.strip()]
        if legacy.exists()
        else []
    )
    return fill_rows, legacy_rows


def test_lane_fill_is_tagged_forward_test(monkeypatch, tmp_path):
    fill_rows, legacy_rows = _run_reconcile(
        monkeypatch, tmp_path, "strategy_bollinger_trend"
    )
    assert len(fill_rows) == 1
    assert fill_rows[0]["strategy"] == "strategy_bollinger_trend"
    assert fill_rows[0]["lane"] == "FORWARD_TEST"
    assert len(legacy_rows) == 1
    assert legacy_rows[0]["lane"] == "FORWARD_TEST"


def test_entrant_fill_has_no_lane_tag(monkeypatch, tmp_path):
    fill_rows, legacy_rows = _run_reconcile(
        monkeypatch, tmp_path, "strategy_ichimoku_trend"
    )
    assert len(fill_rows) == 1
    assert "lane" not in fill_rows[0]
    assert len(legacy_rows) == 1
    assert "lane" not in legacy_rows[0]


# ---------------------------------------------------------------------------
# RD-003 additions (coordinator handoff from TASK-STR-RD-003,
# RESULTS_RD3.md SS2/SS3/SS5): four comm7 1d near-miss cells join the
# lane as documentary registrations — each failed ONLY the >=200-trade
# floor. Same unmappable-universe exclusion as tsmom2_dual.
# ---------------------------------------------------------------------------

RD3_ADDITIONS = {
    # key: (oos trades, expectancy bps, judged PF)
    "vol_regime_switch_a": (151, 117.3, 1.372),
    "vol_regime_switch_b": (124, 79.3, 1.237),
    "trend_pullback_ema100": (113, 76.6, 1.217),
    "trend_pullback_ema200": (109, 64.2, 1.182),
}


def test_rd3_additions_registered_documentary_only():
    import config_strategy as cs

    for key, (trades, edge_bps, pf) in RD3_ADDITIONS.items():
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST"
        assert entry["forward_lane"] == "FORWARD_TEST"
        # Documentary only: never in the executable forward protocol.
        assert entry["forward_protocol"] is False
        assert entry["lane_assets"] == []
        assert entry["validated_assets"] == []
        # The mandated lane note, verbatim.
        assert entry["lane_note"] == (
            "entered sample-starved; forward evidence is the settler"
        )
        assert str(trades) in entry["reason"]
        # Null-out follow-up (2026-11-16): the registry copy of a
        # non-tradable registration carries NO live runtime claims —
        # prior and edge are withdrawn by the null-out block and the
        # record is stamped. The judged evidence itself is preserved
        # in the entry's *_STRATEGY config dict (and its reason text),
        # which is where documentary numbers belong.
        assert entry["expected_net_edge_bps"] is None
        assert entry["runtime_priors_nulled"] is True
        judged = getattr(cs, f"{key.upper()}_STRATEGY")
        assert judged["OOS_TRADES"] == trades
        assert judged["OOS_EXPECTANCY_PCT"] * 100 == pytest.approx(edge_bps)
        assert judged["OOS_PROFIT_FACTOR"] == pytest.approx(pf)
        # No win rate was published for these cells — none is recorded.
        assert entry["oos_win_rate_prior"] is None
        # No production module may exist for an excluded entry.
        assert not os.path.exists(
            os.path.join(os.path.dirname(__file__), "..", f"strategy_{key}.py")
        )


def test_rd3_additions_do_not_expand_the_executable_lane():
    import config_strategy as cs

    protocol = {
        key
        for key, entry in cs.PRODUCTION_STRATEGY_REGISTRY.items()
        if entry.get("status") == "FORWARD_TEST"
        and entry.get("forward_protocol") is True
    }
    # The RD-003 documentary additions remain excluded. The lane's
    # executable set has since grown by deliberate, separately-tasked
    # admissions only: TASK-STR-FWD-018's wave-1 bracket variants
    # (the eight bracket keys below), TASK-STR-FWD-021's 21 RD-014
    # overlay entries (execution_mode "overlay", executed by the
    # daemon's overlay manager — see
    # test_fwd021_overlay_service.py) and TASK-STR-FWD-022's
    # wf_select_tsmom procedure entrant (execution_mode
    # "wf_select" — see test_fwd022_wf_select_service.py).
    overlay = {
        key
        for key, entry in cs.PRODUCTION_STRATEGY_REGISTRY.items()
        if entry.get("execution_mode") == "overlay"
    }
    assert len(overlay) == 21
    assert protocol == {
        "bollinger_trend",
        "shock_breakout",
        "adx_ema_bare",
        # TASK-STR-FWD-018 wave 1 (bollinger variants):
        "bollinger_trend_4h",
        "bollinger_trend_p20",
        # TASK-STR-FWD-018 wave 1 (shock variant):
        "shock_breakout_k15",
        # TASK-STR-FWD-018 wave 1 (ichimoku variants):
        "ichimoku_trend_1d",
        "ichimoku_trend_raw",
        # TASK-STR-FWD-022 (wf-select entrant):
        "wf_select_tsmom",
        # TASK-STR-FWD-019 Wave-2 (PR #981): vol_regime_trend family:
        "vol_regime_trend",
        "vol_regime_trend_don20_gate_lo",
        "vol_regime_trend_ema12_48_gate_lo",
        "vol_adaptive_trend",
        "vol_adaptive_trend_ema20_50_nogate",
        "vol_adaptive_trend_ema20_50_nogate_4h",
        "vol_adaptive_trend_ema12_26_nogate_4h",
        "vol_adaptive_trend_ema20_50_gate_4h",
        "keltner_breakout",
        "keltner_breakout_ema50_m2",
        "keltner_breakout_ema20_m15",
        "keltner_breakout_ema20_m2_4h",
        "keltner_breakout_ema20_m15_4h",
        "keltner_breakout_forex",
        # TASK-STR-FWD-019 Wave-2 (PR #985): bb_reversion + factory winners + fx28:
        "factory_winner_4",
        "factory_winner_3",
        "bb_reversion",
        "bollinger_trend_p20_fx28",
        # TASK-STR-FWD-019 Wave-2 (PR #987): donchian/turtle family:
        "donchian_turtle",
        "donchian_turtle_n20_trail",
        "donchian_turtle_n20_b26",
        "donchian_turtle_n55_trail",
        "donchian_turtle_n55_trail_4h",
        "donchian_turtle_n20_trail_4h",
        "donchian_turtle_n20_b24",
        "donchian_turtle_n20_b26_4h",
        "donchian_turtle_n55_b24",
        "turtle2",
        "turtle2_n20_trail_filt",
        "turtle2_n55_trail_filt_4h",
        "turtle2_n20_trail_filt_4h",
        # TASK-STR-FWD-019 Wave-2 (PR #988):
        "rsi_momentum",
        "rsi_momentum_rsi7_60_40",
        "rsi_momentum_forex",
        # TASK-STR-FWD-019 Wave-2 (PR #989): RD-001 choppiness + volatility breakout:
        "volatility_breakout",
        "choppiness_breakout",
        "psar_trend_af001_max010",
        "psar_trend_af002_max020",
        "tsmom2_dual_crypto",
        "ts_momentum",
        "ts_momentum_roc42",
        "ts_momentum_roc168",
        "ts_momentum_roc42_4h",
        "ts_momentum_roc168_rd001",
        "ha_trend",
        "ha_trend_two_candle_4h",
        "ha_trend_one_candle",
        "ha_trend_one_candle_4h",
        # TASK-STR-FWD-019 Wave-2 (PR #994):
        "stoch_reversion",
        "stoch_reversion_k14_filt",
        "stoch_reversion_crypto",
        "bar_patterns",
        "bar_patterns_inside_bar_4h",
        "macd_trend",
        # TASK-STR-FWD-019 Wave-2 (PR #999):
        "vol_compression",
        "vol_compression_squeeze_raw",
        # TASK-STR-FWD-019 Wave-2 (PR #1001):
        "volume_breakout",
        # TASK-STR-FWD-019 Wave-2 (PR #1002):
        "mtf_confluence",
        "mtf_confluence_1d",
        # TASK-STR-FWD-019 Wave-2 gap-fill (crew G): the two ts_momentum
        # FOREX cells join the executable protocol set.
        "ts_momentum_roc72_fx28",
        "ts_momentum_roc24_fx12",
        # TASK-STR-EXP-002: the 8 ensemble books are forward-protocol
        # entries too (registered but inert until their member modules
        # merge — see each entry's "execution" stamp).
        "ensemble_book_3905",
        "ensemble_book_3906",
        "ensemble_book_3927",
        "ensemble_book_3928",
        "ensemble_book_3929",
        "ensemble_book_3933",
        "ensemble_book_3978",
        "ensemble_book_3900",
    } | overlay


def test_non_tradable_lane_registrations_are_nulled_not_counted():
    """Null-out follow-up (2026-11-16): the FORWARD_TEST registry's
    non-tradable registrations must be visibly nulled on the record
    itself — no runtime prior, no runtime edge, runtime_priors_nulled
    stamped True — so no consumer counting registry records can
    mistake them for live lane entrants. Executable entrants (the
    original 3 bracket modules, TASK-STR-FWD-018's 5 wave-1 bracket
    variants and, since TASK-STR-FWD-021, the 21 overlay entries,
    plus the 8 TASK-STR-EXP-002 ensemble books, registered but inert
    until their member modules merge)
    keep their judged priors for the daemon's
    expectancy gate and are stamped False."""
    import config_strategy as cs

    non_tradable = {
        "tsmom2_dual",
        "vol_regime_switch_a",
        "vol_regime_switch_b",
        "trend_pullback_ema100",
        "trend_pullback_ema200",
    }
    forward_test = {
        key
        for key, entry in cs.PRODUCTION_STRATEGY_REGISTRY.items()
        if entry.get("status") == "FORWARD_TEST"
    }
    overlay = {
        key
        for key, entry in cs.PRODUCTION_STRATEGY_REGISTRY.items()
        if entry.get("execution_mode") == "overlay"
    }
    assert forward_test == non_tradable | {
        "bollinger_trend",
        "shock_breakout",
        "adx_ema_bare",
        # TASK-STR-FWD-018 wave 1 (bollinger variants):
        "bollinger_trend_4h",
        "bollinger_trend_p20",
        # TASK-STR-FWD-018 wave 1 (shock variant):
        "shock_breakout_k15",
        # TASK-STR-FWD-018 wave 1 (ichimoku variants):
        "ichimoku_trend_1d",
        "ichimoku_trend_raw",
        "wf_select_tsmom",
        # TASK-STR-FWD-019 Wave-2 (PR #981): vol_regime_trend family:
        "vol_regime_trend",
        "vol_regime_trend_don20_gate_lo",
        "vol_regime_trend_ema12_48_gate_lo",
        # TASK-STR-FWD-019 Wave-2 crew A: vol_adaptive_trend cells.
        "vol_adaptive_trend",
        "vol_adaptive_trend_ema20_50_nogate",
        "vol_adaptive_trend_ema20_50_nogate_4h",
        "vol_adaptive_trend_ema12_26_nogate_4h",
        "vol_adaptive_trend_ema20_50_gate_4h",
        "keltner_breakout",
        "keltner_breakout_ema50_m2",
        "keltner_breakout_ema20_m15",
        "keltner_breakout_ema20_m2_4h",
        "keltner_breakout_ema20_m15_4h",
        "keltner_breakout_forex",
        # TASK-STR-FWD-019 Wave-2 (PR #985): bb_reversion + factory winners + fx28:
        "factory_winner_4",
        "factory_winner_3",
        "bb_reversion",
        "bollinger_trend_p20_fx28",
        # TASK-STR-FWD-019 Wave-2 (PR #987): donchian/turtle family:
        "donchian_turtle",
        "donchian_turtle_n20_trail",
        "donchian_turtle_n20_b26",
        "donchian_turtle_n55_trail",
        "donchian_turtle_n55_trail_4h",
        "donchian_turtle_n20_trail_4h",
        "donchian_turtle_n20_b24",
        "donchian_turtle_n20_b26_4h",
        "donchian_turtle_n55_b24",
        "turtle2",
        "turtle2_n20_trail_filt",
        "turtle2_n55_trail_filt_4h",
        "turtle2_n20_trail_filt_4h",
        # TASK-STR-FWD-019 Wave-2 (PR #988):
        "rsi_momentum",
        "rsi_momentum_rsi7_60_40",
        "rsi_momentum_forex",
        # TASK-STR-FWD-019 Wave-2 (PR #989): RD-001 choppiness + volatility breakout:
        "volatility_breakout",
        "choppiness_breakout",
        "psar_trend_af001_max010",
        "psar_trend_af002_max020",
        # TASK-STR-FWD-019 Wave-2 crew A: ts_momentum/tsmom2 cells.
        "ts_momentum",
        "ts_momentum_roc42",
        "ts_momentum_roc168",
        "ts_momentum_roc42_4h",
        "ts_momentum_roc168_rd001",
        "tsmom2_dual_crypto",
        "ha_trend",
        "ha_trend_two_candle_4h",
        "ha_trend_one_candle",
        "ha_trend_one_candle_4h",
        # TASK-STR-FWD-019 Wave-2 (PR #994):
        "stoch_reversion",
        "stoch_reversion_k14_filt",
        "stoch_reversion_crypto",
        "bar_patterns",
        "bar_patterns_inside_bar_4h",
        # TASK-STR-FWD-019 Wave-2 crew A: macd_trend cell.
        "macd_trend",
        # TASK-STR-FWD-019 Wave-2 (PR #999):
        "vol_compression",
        "vol_compression_squeeze_raw",
        # TASK-STR-FWD-019 Wave-2 (PR #1001):
        "volume_breakout",
        # TASK-STR-FWD-019 Wave-2 (PR #1002):
        "mtf_confluence",
        "mtf_confluence_1d",
        # TASK-STR-FWD-019 Wave-2 gap-fill (crew G): the two ts_momentum
        # FOREX cells join the FORWARD_TEST registry population.
        "ts_momentum_roc72_fx28",
        "ts_momentum_roc24_fx12",
        # TASK-STR-EXP-002: the 8 ensemble books join the FORWARD_TEST set.
        "ensemble_book_3905",
        "ensemble_book_3906",
        "ensemble_book_3927",
        "ensemble_book_3928",
        "ensemble_book_3929",
        "ensemble_book_3933",
        "ensemble_book_3978",
        "ensemble_book_3900",
    } | overlay
    for key in non_tradable:
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["forward_protocol"] is False, key
        assert entry["lane_assets"] == [], key
        assert entry["oos_win_rate_prior"] is None, key
        assert entry["expected_net_edge_bps"] is None, key
        assert entry["runtime_priors_nulled"] is True, key
    for key in (
        "bollinger_trend",
        "shock_breakout",
        "adx_ema_bare",
        "bollinger_trend_4h",
        "bollinger_trend_p20",
        "shock_breakout_k15",
        "ichimoku_trend_1d",
        "ichimoku_trend_raw",
        "wf_select_tsmom",
        "vol_regime_trend",
        "vol_regime_trend_don20_gate_lo",
        "vol_regime_trend_ema12_48_gate_lo",
        "vol_adaptive_trend",
        "vol_adaptive_trend_ema20_50_nogate",
        "vol_adaptive_trend_ema20_50_nogate_4h",
        "vol_adaptive_trend_ema12_26_nogate_4h",
        "vol_adaptive_trend_ema20_50_gate_4h",
        "keltner_breakout",
        "keltner_breakout_ema50_m2",
        "keltner_breakout_ema20_m15",
        "keltner_breakout_ema20_m2_4h",
        "keltner_breakout_ema20_m15_4h",
        "keltner_breakout_forex",
        "factory_winner_4",
        "factory_winner_3",
        "bb_reversion",
        "bollinger_trend_p20_fx28",
        "donchian_turtle",
        "donchian_turtle_n20_trail",
        "donchian_turtle_n20_b26",
        "donchian_turtle_n55_trail",
        "donchian_turtle_n55_trail_4h",
        "donchian_turtle_n20_trail_4h",
        "donchian_turtle_n20_b24",
        "donchian_turtle_n20_b26_4h",
        "donchian_turtle_n55_b24",
        "turtle2",
        "turtle2_n20_trail_filt",
        "turtle2_n55_trail_filt_4h",
        "turtle2_n20_trail_filt_4h",
        "rsi_momentum",
        "rsi_momentum_rsi7_60_40",
        "rsi_momentum_forex",
        "volatility_breakout",
        "choppiness_breakout",
        "psar_trend_af001_max010",
        "psar_trend_af002_max020",
        "tsmom2_dual_crypto",
        "ts_momentum",
        "ts_momentum_roc42",
        "ts_momentum_roc168",
        "ts_momentum_roc42_4h",
        "ts_momentum_roc168_rd001",
        "ha_trend",
        "ha_trend_two_candle_4h",
        "ha_trend_one_candle",
        "ha_trend_one_candle_4h",
        "stoch_reversion",
        "stoch_reversion_k14_filt",
        "stoch_reversion_crypto",
        "bar_patterns",
        "bar_patterns_inside_bar_4h",
        "macd_trend",
        "vol_compression",
        "vol_compression_squeeze_raw",
        "volume_breakout",
        "mtf_confluence",
        "mtf_confluence_1d",
        "ts_momentum_roc72_fx28",
        "ts_momentum_roc24_fx12",
        "ensemble_book_3905",
        "ensemble_book_3906",
        "ensemble_book_3927",
        "ensemble_book_3928",
        "ensemble_book_3929",
        "ensemble_book_3933",
        "ensemble_book_3978",
        "ensemble_book_3900",
    ):
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["runtime_priors_nulled"] is False, key
        assert entry["oos_win_rate_prior"] is not None, key
        assert entry["expected_net_edge_bps"] is not None, key
    # TASK-STR-FWD-021: the 21 overlay entries are lane-executable
    # (forward_protocol True, lane_assets non-empty), so they too keep
    # their judged priors and are stamped False.
    for key in overlay:
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["forward_protocol"] is True, key
        assert entry["lane_assets"], key
        assert entry["runtime_priors_nulled"] is False, key
        assert entry["oos_win_rate_prior"] is not None, key
        assert entry["expected_net_edge_bps"] is not None, key


def test_tsmom2_cost_fragile_recorded():
    import config_strategy as cs

    entry = cs.PRODUCTION_STRATEGY_REGISTRY["tsmom2_dual"]
    assert entry["cost_fragile"] is True
    assert "1.149" in entry["reason"]
    assert "COST-FRAGILE" in entry["reason"]
    assert "BIT-IDENTICALLY" in entry["reason"]
