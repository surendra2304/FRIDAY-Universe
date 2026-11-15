"""TASK-STR-FWD-002 sleeve extension — the RD-002 Stage-C sleeve.

The judged sleeve (best_per_class, equal weight) had four legs; venue
fidelity (verified live 2026-11-15: the OANDA practice account holds
68 instruments, ALL currency pairs) excludes two of them:

  IN : shock_breakout/k1.0 @ crypto30 1wk   -> strategy_sleeve_shock_breakout
  IN : tsmom2_dual/roc90_ema200 @ forex28 1d -> oanda_demo/sleeve_runner
  OUT: vol_adaptive_trend @ comm7 4h (no commodity instruments)
  OUT: keltner_breakout @ idx7 1d    (no index instruments)

This suite pins: (1) EQUIVALENCE of both traded legs against the
judged rd2 implementations on real historical slices, including the
judged weekly-bar construction (7-day buckets anchored at each
symbol's judged series start — NOT native weekly klines); (2) the
sleeve-level kill rule (combined drawdown only); (3) the daemon
sleeve-guard actions (denylist + OANDA runner pause file); (4) the
FX-MR-v4 engine's ownership scoping (it must never manage sleeve
positions on the shared account); (5) the sleeve runner's governed
scan behaviour with a fake broker.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_sleeve_shock_breakout as shock
from measurement import forward_guard
from oanda_demo import sleeve_signals
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families2, families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")

SHOCK_TAG = "strategy_sleeve_shock_breakout"
TSMOM_TAG = "strategy_sleeve_tsmom2_dual"


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def _candles(df: pd.DataFrame) -> list:
    return [
        {
            "timestamp": int(ts.timestamp()),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(getattr(r, "volume", 0.0)),
        }
        for ts, r in df.iterrows()
    ]


# ---------------------------------------------------------------------------
# Equivalence: shock leg (weekly bars are the judged construction)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_1wk.csv", "SUIUSDT_1wk.csv"])
def test_shock_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_shock(df, 1.0, 104)
    assert shock.entries_for_frame(df) == judged
    assert len(judged) > 0  # the slice actually exercises the signal


@pytest.mark.parametrize(
    "daily_fixture,weekly_fixture,symbol",
    [
        ("BTCUSDT_1d_for_wk.csv", "BTCUSDT_1wk.csv", "BTCUSDT"),
        ("SUIUSDT_1d_for_wk.csv", "SUIUSDT_1wk.csv", "SUIUSDT"),
    ],
)
def test_weekly_aggregation_rebuilds_judged_bars(daily_fixture, weekly_fixture, symbol):
    daily = _load(daily_fixture)
    judged_weekly = _load(weekly_fixture)
    rebuilt = shock.weekly_candles(_candles(daily), symbol)
    got = pd.DataFrame(rebuilt)
    got.index = pd.to_datetime(got.pop("timestamp"), unit="s", utc=True)
    # The rebuilt series must cover the judged frame bar-for-bar
    # (the trailing partial bucket, if any, is beyond the judged frame).
    n = len(judged_weekly)
    got = got.iloc[:n]
    assert len(got) == n
    for col in ("open", "high", "low", "close"):
        np.testing.assert_allclose(
            got[col].to_numpy(), judged_weekly[col].to_numpy(), rtol=0, atol=1e-9
        )
    assert (got.index == judged_weekly.index).all()


def test_shock_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_1wk.csv")
    entries = shock.entries_for_frame(df)
    i, side = entries[-1]
    frame = df.iloc[: i + 1]
    sig = shock.get_signal(frame)
    assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
    atr_i = float(harness_atr(frame).iloc[i])
    assert sig["sl_dist"] == pytest.approx(2.0 * atr_i)
    assert sig["tp_dist"] == pytest.approx(4.0 * atr_i)
    assert sig["rr_ratio"] == pytest.approx(2.0)


def test_shock_forming_bucket_is_never_evaluated():
    df = _load("BTCUSDT_1wk.csv")
    entries = shock.entries_for_frame(df)
    i, _side = entries[-1]
    frame = df.iloc[: i + 1].copy()
    # Append a still-forming bucket timestamped at the current week:
    # the signal on the last CLOSED bar must be unaffected... and if
    # the last closed bar had no signal, none may appear.
    now_bucket = (int(time.time()) // 604800) * 604800
    forming = frame.iloc[[-1]].copy()
    forming.index = [pd.Timestamp(now_bucket, unit="s", tz="UTC")]
    joined = pd.concat([frame, forming])
    sig = shock.get_signal(joined)
    assert sig == shock.get_signal(frame)


# ---------------------------------------------------------------------------
# Equivalence: tsmom leg (OANDA sleeve runner signal core)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fixture", ["FX_EURUSD_1d.csv", "FX_GBPJPY_1d.csv", "FX_USDJPY_1d.csv"]
)
def test_tsmom_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families2.sig_dual_momentum(df, 90, 260)
    assert sleeve_signals.entries_for_frame(df) == judged
    assert len(judged) > 0


def test_tsmom_last_bar_bracket_distances():
    df = _load("FX_EURUSD_1d.csv")
    entries = sleeve_signals.entries_for_frame(df)
    i, side = entries[-1]
    frame = df.iloc[: i + 1]
    sig = sleeve_signals.evaluate_last_bar(frame)
    assert sig is not None
    assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
    atr_i = float(harness_atr(frame).iloc[i])
    assert sig["sl_dist"] == pytest.approx(2.5 * atr_i)
    assert sig["tp_dist"] == pytest.approx(5.0 * atr_i)


# ---------------------------------------------------------------------------
# Governance: the reduced sleeve is registered honestly
# ---------------------------------------------------------------------------

def test_sleeve_registry_entries():
    from config_strategy import (
        FOREX28_SYMBOLS,
        PRODUCTION_STRATEGY_REGISTRY,
        SLEEVE_NAME,
    )

    assert len(FOREX28_SYMBOLS) == 28
    shock_e = PRODUCTION_STRATEGY_REGISTRY["sleeve_shock_breakout"]
    assert shock_e["status"] == "VALIDATED"
    assert shock_e["sleeve"] == SLEEVE_NAME == "best_per_class"
    assert shock_e["timeframe"] == "1wk"
    assert len(shock_e["validated_assets"]) == 30
    tsmom_e = PRODUCTION_STRATEGY_REGISTRY["sleeve_tsmom2_dual"]
    assert tsmom_e["status"] == "VALIDATED"
    assert tsmom_e["sleeve"] == "best_per_class"
    assert tsmom_e["validated_assets"] == FOREX28_SYMBOLS
    # The excluded legs are on the record as DISABLED, with reasons.
    for key in ("sleeve_vol_adaptive_trend", "sleeve_keltner_breakout"):
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "DISABLED"
        assert "EXCLUDED" in entry["reason"]


def test_sleeve_executability_matrix():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    assert reg.executable(SHOCK_TAG, "1wk", "BTCUSDT")[0]
    assert not reg.executable(SHOCK_TAG, "4h", "BTCUSDT")[0]
    assert not reg.executable(SHOCK_TAG, "1wk", "EURUSD")[0]
    # The tsmom leg has NO daemon module by design (the OANDA sleeve
    # runner executes it); the daemon must never claim it.
    assert TSMOM_TAG not in reg.get_all_strategy_names()


# ---------------------------------------------------------------------------
# Sleeve kill rule: combined drawdown only
# ---------------------------------------------------------------------------

def _fill(strategy, net, exit_time):
    return {"strategy": strategy, "net_pnl": net, "exit_time": exit_time}


def test_sleeve_guard_combines_components():
    rows = [
        _fill(SHOCK_TAG, +400.0, 1.0),
        _fill(TSMOM_TAG, -500.0, 2.0),
        _fill(SHOCK_TAG, -250.0, 3.0),
        _fill("strategy_ichimoku_trend", -9999.0, 4.0),  # not a component
    ]
    sleeves = {"best_per_class": [SHOCK_TAG, TSMOM_TAG]}
    (d,) = forward_guard.evaluate_sleeves(rows, 10_000.0, sleeves)
    assert d["trades"] == 3
    # Curve: +400 (peak) -> -100 -> -350: max DD = 400 - (-350) = 750
    assert d["max_drawdown_usd"] == pytest.approx(750.0)
    assert d["breached"] is True  # 750 > 5% of 10,000


def test_sleeve_guard_holds_within_limit():
    rows = [_fill(SHOCK_TAG, +100.0, 1.0), _fill(TSMOM_TAG, -150.0, 2.0)]
    (d,) = forward_guard.evaluate_sleeves(
        rows, 10_000.0, {"best_per_class": [SHOCK_TAG, TSMOM_TAG]}
    )
    assert d["max_drawdown_usd"] == pytest.approx(150.0)
    assert d["breached"] is False


def test_daemon_sleeve_guard_hook_pauses_everything(monkeypatch, tmp_path):
    import measurement.fill_ledger as ledger
    from autonomy import run_daemon as rd

    rows = [
        _fill(SHOCK_TAG, +400.0, 1.0),
        _fill(TSMOM_TAG, -500.0, 2.0),
        _fill(SHOCK_TAG, -250.0, 3.0),
    ]
    monkeypatch.setattr(ledger, "read_fills", lambda: rows)

    daemon = rd.StratexTradingEngine.__new__(rd.StratexTradingEngine)
    daemon.engine = SimpleNamespace(
        get_risk_summary=lambda: {"total_equity": 10_000.0, "daily_loss_limit_hit": False}
    )
    daemon.strategy_denylist = set()
    persisted = []
    daemon._persist_denylist = lambda: persisted.append(True)

    pause_file = (
        os.path.join(os.path.dirname(os.path.dirname(rd.__file__)),
                     "data", "sleeve_oanda", "sleeve_entries_paused")
    )
    preexisting = os.path.exists(pause_file)
    try:
        daemon._maybe_apply_forward_guard()
        assert SHOCK_TAG in daemon.strategy_denylist
        assert TSMOM_TAG in daemon.strategy_denylist
        assert persisted, "denylist must be persisted on a sleeve kill"
        assert os.path.exists(pause_file), "OANDA runner pause file must be written"
        with open(pause_file) as fh:
            assert "sleeve" in fh.read().lower()
    finally:
        if not preexisting and os.path.exists(pause_file):
            os.remove(pause_file)


# ---------------------------------------------------------------------------
# FX-MR-v4 engine ownership scoping (shared practice account)
# ---------------------------------------------------------------------------

class _TraderFakeAdapter:
    def __init__(self, candles):
        self._candles = candles
        self.closed = []

    def get_historical_data(self, symbol, timeframe, count):
        return self._candles

    def close_trade(self, trade_id):
        self.closed.append(trade_id)
        return True

    def get_pricing(self, symbols):
        return {}


def _rising_candles(n=30):
    base = int(time.time()) - n * 86400
    return [
        {
            "timestamp": base + k * 86400,
            "open": 1.10 + k * 0.001,
            "high": 1.10 + k * 0.001,
            "low": 1.10 + k * 0.001,
            "close": 1.10 + k * 0.001,
            "volume": 100,
        }
        for k in range(n)
    ]


def _mr_trade(trade_id, units=1000):
    # Opened at the first fake candle (30 bars ago): held >= max_hold,
    # and the rising series also satisfies the EMA5 rule exit — either
    # way the MR management WOULD close this trade if it were managed.
    opened = int(time.time()) - 30 * 86400
    return {
        "id": trade_id,
        "instrument": "EURUSD",
        "units": units,
        "price": 1.10,
        "open_time": datetime.fromtimestamp(opened, tz=timezone.utc).isoformat(),
        "unrealizedPL": 0.0,
        "stop_loss": None,
        "take_profit": None,
    }


def test_trader_never_manages_foreign_trades():
    from oanda_demo.trader import OandaDemoTrader, build_default_strategy

    adapter = _TraderFakeAdapter(_rising_candles())
    trader = OandaDemoTrader(adapter=adapter, strategy=build_default_strategy(),
                             timeframe="1d", dry_run=False)
    foreign = _mr_trade("F1")  # rising series => MR rule exit WOULD fire
    state = {"own_trade_ids": [], "known_trade_ids": ["F1"]}
    summary: dict = {}
    trader._manage_open_trades([foreign], {}, state, summary)
    assert adapter.closed == [], "foreign trade must not be closed"
    assert "rule_exits" not in summary
    assert summary["foreign_open_trades"] == 1


def test_trader_still_manages_own_trades():
    from oanda_demo.trader import OandaDemoTrader, build_default_strategy

    adapter = _TraderFakeAdapter(_rising_candles())
    trader = OandaDemoTrader(adapter=adapter, strategy=build_default_strategy(),
                             timeframe="1d", dry_run=False)
    own = _mr_trade("T1")
    state = {"own_trade_ids": ["T1"], "known_trade_ids": ["T1"]}
    summary: dict = {}
    trader._manage_open_trades([own], {}, state, summary)
    assert adapter.closed == ["T1"]
    assert summary.get("rule_exits") == ["T1"]


def test_trader_adoption_migration_records_existing_trades():
    from oanda_demo.trader import OandaDemoTrader, build_default_strategy

    adapter = _TraderFakeAdapter(_rising_candles())
    trader = OandaDemoTrader(adapter=adapter, strategy=build_default_strategy(),
                             timeframe="1d", dry_run=True)
    state: dict = {}  # no own_trade_ids key: pre-scoping state file
    summary: dict = {}
    trader._manage_open_trades([_mr_trade("T9")], {}, state, summary)
    assert state["own_trade_ids"] == ["T9"]


# ---------------------------------------------------------------------------
# Sleeve runner: governed scan with a fake broker
# ---------------------------------------------------------------------------

class _RunnerFakeAdapter:
    """OANDA-shaped fake: EURUSD serves the judged fixture (truncated
    at a signal bar); every other symbol serves a flat series."""

    account_id = "101-001-FAKE"

    def __init__(self, eurusd_candles, fail_orders=False):
        self._eurusd = eurusd_candles
        self.orders = []
        self.fail_orders = fail_orders
        self.pricing_requests = []

    # adapter surface used by the runner
    def normalize_symbol(self, s):
        return s.replace("_", "")

    def denormalize_symbol(self, s):
        return s[:3] + "_" + s[3:] if len(s) == 6 else s

    def get_account_summary(self):
        return {"balance": 10_000.0, "equity": 10_000.0,
                "margin_used": 0.0, "margin_available": 10_000.0,
                "unrealized_pl": 0.0, "margin_rate": 0.02}

    def open_trades(self):
        return []

    def get_pricing(self, symbols):
        self.pricing_requests.append(list(symbols))
        out = {}
        for s in symbols:
            out[s] = {"bid": 1.0, "ask": 1.0, "mid": 1.0, "spread": 0.0}
        if self._eurusd:
            last = self._eurusd[-1]["close"]
            out["EURUSD"] = {"bid": last, "ask": last, "mid": last, "spread": 0.0}
        return out

    def _request(self, method, path, params=None):
        if "/candles" in path:
            if "EUR_USD" in path:
                rows = self._eurusd
            else:
                base = 1700000000
                rows = [
                    {"timestamp": base + k * 86400, "open": 1.0, "high": 1.0,
                     "low": 1.0, "close": 1.0, "volume": 1}
                    for k in range(400)
                ]
            return {"candles": [
                {
                    "complete": True,
                    "time": datetime.fromtimestamp(
                        r["timestamp"], tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%S.000000000Z"),
                    "mid": {"o": str(r["open"]), "h": str(r["high"]),
                            "l": str(r["low"]), "c": str(r["close"])},
                    "volume": r["volume"],
                }
                for r in rows
            ]}
        return {}

    def place_order(self, symbol, side, order_type, units, **kw):
        self.orders.append((symbol, side, units, kw))
        if self.fail_orders:
            raise RuntimeError("MARKET_HALTED")
        return SimpleNamespace(trade_id="9001", order_id="9000", price=1.0,
                               status="FILLED")


def _eurusd_signal_frame():
    df = _load("FX_EURUSD_1d.csv")
    entries = sleeve_signals.entries_for_frame(df)
    i, _side = entries[-1]
    return _candles(df.iloc[: i + 1])


def _make_runner(tmp_path, adapter, dry_run=True):
    from oanda_demo.sleeve_runner import SleeveRunner

    return SleeveRunner(
        adapter=adapter,
        dry_run=dry_run,
        state_file=tmp_path / "sleeve_state.json",
        data_dir=tmp_path,
    )


def test_runner_dry_run_finds_the_judged_signal(tmp_path):
    adapter = _RunnerFakeAdapter(_eurusd_signal_frame())
    runner = _make_runner(tmp_path, adapter, dry_run=True)
    out = runner.run_once()
    assert out.get("evaluated", 0) >= 20  # most of FOREX28 evaluated
    assert any("EURUSD" in a for a in out.get("actions", [])), out
    assert adapter.orders == []  # dry-run never orders


def test_runner_places_governed_order_when_live(tmp_path):
    adapter = _RunnerFakeAdapter(_eurusd_signal_frame())
    runner = _make_runner(tmp_path, adapter, dry_run=False)
    out = runner.run_once()
    assert len(adapter.orders) == 1
    symbol, _side, units, kw = adapter.orders[0]
    assert symbol == "EURUSD" and units >= 1
    assert kw.get("stop_loss") and kw.get("take_profit")
    state = json.loads((tmp_path / "sleeve_state.json").read_text())
    assert "9001" in state["own_trades"]
    assert state["own_trades"]["9001"]["symbol"] == "EURUSD"


def test_runner_honours_its_own_pause_file(tmp_path):
    (tmp_path / "sleeve_entries_paused").write_text("test pause")
    adapter = _RunnerFakeAdapter(_eurusd_signal_frame())
    runner = _make_runner(tmp_path, adapter, dry_run=False)
    out = runner.run_once()
    assert out.get("entries_paused") is True
    assert adapter.orders == []


def test_runner_refuses_when_governance_revoked(tmp_path, monkeypatch):
    from oanda_demo import sleeve_runner

    monkeypatch.setattr(sleeve_runner, "governance_ok", lambda: False)
    adapter = _RunnerFakeAdapter(_eurusd_signal_frame())
    runner = _make_runner(tmp_path, adapter, dry_run=False)
    out = runner.run_once()
    assert "governance" in str(out.get("halted", ""))
    assert adapter.orders == []


# ---------------------------------------------------------------------------
# Runner execution hygiene (defects found in the first live hour,
# 2026-11-15: duplicate pricing instrument 400; JPY-pair notional
# math shrinking sizes ~150x; rejected orders retried every scan)
# ---------------------------------------------------------------------------

def test_runner_pricing_request_has_no_duplicates(tmp_path):
    adapter = _RunnerFakeAdapter(_eurusd_signal_frame())
    runner = _make_runner(tmp_path, adapter, dry_run=True)
    runner.run_once()
    assert adapter.pricing_requests, "pricing must be requested"
    for req in adapter.pricing_requests:
        assert len(req) == len(set(req)), f"duplicate instruments in {req}"


def test_runner_sizing_jpy_pair_uses_real_notional(tmp_path):
    adapter = _RunnerFakeAdapter(_eurusd_signal_frame())
    runner = _make_runner(tmp_path, adapter, dry_run=True)
    pricing = {"USDJPY": {"bid": 159.7, "ask": 159.73, "mid": 159.717, "spread": 0.0}}
    units = runner._position_units(
        "USDJPY", 2.098, pricing, equity=10_000.0,
        free_margin=10_000.0, margin_rate=0.02,
    )
    # Notional per unit is $1 for USDJPY -> the 25% notional cap is
    # 2,500 units (the raw-price formula would give 15).
    assert units == 2500


def test_runner_sizing_eurusd_sanity(tmp_path):
    adapter = _RunnerFakeAdapter(_eurusd_signal_frame())
    runner = _make_runner(tmp_path, adapter, dry_run=True)
    pricing = {"EURUSD": {"bid": 1.08, "ask": 1.08, "mid": 1.08, "spread": 0.0}}
    units = runner._position_units(
        "EURUSD", 0.02, pricing, equity=10_000.0,
        free_margin=10_000.0, margin_rate=0.02,
    )
    assert units == int(2500 / 1.08)


def test_runner_failed_order_backs_off_instrument(tmp_path):
    adapter = _RunnerFakeAdapter(_eurusd_signal_frame(), fail_orders=True)
    runner = _make_runner(tmp_path, adapter, dry_run=False)
    runner.run_once()
    assert len(adapter.orders) == 1  # one attempt, rejected
    state = json.loads((tmp_path / "sleeve_state.json").read_text())
    assert state["cooldowns"]["EURUSD"] > time.time()
    runner.run_once()
    assert len(adapter.orders) == 1  # no retry while cooling down
