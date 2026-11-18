"""TASK-STR-FWD-020 — FORWARD-TEST lane entrant: supertrend_bare.

Gap-fill for the near-miss audit's one unassigned second-tier row
(REPORT section 1.4 #91): governed strategy_supertrend:bare
@ CRYPTO30 4h — 3,109 pooled OOS trades, expectancy +0.1911%/trade,
PF 1.0529, win rate 0.2602, 3/5 positive folds, holdout PASS
(untouched expectancy +0.1097%, 1,048 trades). It did NOT pass the
frozen full bar (PF < 1.2, folds < 4/5, Bonferroni FAIL); the family
was deleted by TASK-STR-CLEANUP-001 under the old PF<1.2 rule. The
owner's two-tier admission (2026-11-18) admits it to the FORWARD_TEST
lane on the second tier (expectancy>0, PF>=1.05, >=200 OOS trades).

This file pins:

1. EQUIVALENCE: strategy_supertrend_bare reproduces the judged
   rd2/gov2 bare evaluation entry-for-entry on the fwd002 4h
   fixtures. The judged side is an INDEPENDENT TRANSCRIPTION of the
   judged module (pre-cleanup strategy_supertrend.py, blob
   ba3cc8006688d6e6399e91c89cb8a80c791f1c2c) run through an inline
   replica of gov2.eval_module_cell (shared features.add_features
   pipeline — the pipeline the row detail records — get_signal on
   trailing <=500-bar windows, module_eval._extract semantics,
   NO signal filter).
2. BRACKET GEOMETRY: the module's judged bracket — stop = supertrend
   band bounded by 2.0 x ATR(14); TP = 3.0 x risk with the risk
   floored at 0.8 x ATR(14); both legs >= 0.30% of price (the
   module's anti-churn floor) at every judged entry.
3. LIVE CONTRACT: the daemon get_signal reproduces judged entries
   on truncated frames, stays silent on quiet bars, and never
   evaluates a still-forming bar.
4. GOVERNANCE: the FORWARD_TEST registry entry (lane terms, judged
   priors kept, governance_status_for classification) and the
   demo-venue-only enforcement; the deleted production name
   strategy_supertrend stays UNREGISTERED — the lane entrant is a
   separate module and the two are never blended.
5. STOP-CAP (TASK-STR-FWD-012): the decision is NO override.
   Measured 2026-11-18 with the wave-1 capcheck method (judged gov2
   loop over current Binance spot 4h klines, CRYPTO30 x 1,500 bars,
   4,441 judged signals): median stop 3.61% of price, p99 9.28%,
   max 14.28%, share above the 0.15 production cap 0.00%, minimum
   0.312% (the module's own 0.30% anti-churn floor). The global cap
   binds only as a sanity bound; the registry key stays absent and
   the daemon lookup returns None.
"""

from __future__ import annotations

import os
import sys
from collections import namedtuple

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import features as shared_features
import strategy_supertrend_bare as stb

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260
WINDOW = 500


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# Independent transcription of the judged module
# (pre-cleanup strategy_supertrend.py, blob ba3cc800...).
# ---------------------------------------------------------------------------

_TSignalResult = namedtuple(
    "_TSignalResult",
    ["side", "sl", "tp", "strategy_type", "win_rate_prior", "rr_ratio"],
)
_T_RR = 3.0
_T_PRIOR = 0.266
_T_MIN_BRACKET_PCT = 0.0030
_T_BLOCK_SHORTS = (
    os.getenv("BLOCK_SHORTS_IN_BULL_REGIME", "true").strip().lower()
    in ("1", "true", "yes", "on")
)


def _t_bracket_ok(entry, sl, tp, side):
    if entry <= 0:
        return False
    floor_dist = entry * _T_MIN_BRACKET_PCT
    if side == "BUY":
        return (entry - sl) >= floor_dist and (tp - entry) >= floor_dist
    return (sl - entry) >= floor_dist and (entry - tp) >= floor_dist


def _t_get_signal(df):
    """Transcription of the judged module's get_signal (blob ba3cc800)."""
    none_res = _TSignalResult(None, None, None, "RULE_BASED", _T_PRIOR, _T_RR)
    if df is None or len(df) < 50:
        return none_res
    if "supertrend" not in df.columns or "ema_200" not in df.columns:
        try:
            df = shared_features.add_features(df)
        except Exception:
            return none_res
    if "supertrend" not in df.columns:
        return none_res

    last = df.iloc[-1]
    prev = df.iloc[-2]

    adx = float(last.get("adx", last.get("adx_14", 0.0)))
    if 0.0 < adx < 25.0:
        return none_res

    st_now = bool(last["supertrend"])
    st_prev = bool(prev["supertrend"])
    close = float(last["close"])
    open_p = float(last["open"])
    low = float(last["low"])
    high = float(last.get("high", close))
    prev_high = float(prev.get("high", prev["close"]))

    ema_200 = float(last.get("ema_200", close))
    ema_50 = float(last.get("ema_50", close))
    ema_21 = float(last.get("ema_21", last.get("ema_20", close)))
    atr = float(last.get("atr", last.get("atr_14", close * 0.01)))
    rsi = float(last.get("rsi", last.get("rsi_14", 50.0)))
    st_lower = float(last.get("st_lower", close - 1.5 * atr))
    st_upper = float(last.get("st_upper", close + 1.5 * atr))

    if st_now == True and st_prev == False and close > ema_200:
        sl = max(st_lower, close - (atr * 2.0))
        risk = max(close - sl, atr * 0.8)
        tp = close + (risk * _T_RR)
        if _t_bracket_ok(close, sl, tp, "BUY"):
            return _TSignalResult("BUY", sl, tp, "RULE_BASED", _T_PRIOR, _T_RR)
        return none_res

    if st_now == True and st_prev == True and close > ema_200 and ema_21 >= ema_50:
        pulled_back = (low <= ema_21 * 1.002 or prev["low"] <= ema_21 * 1.002)
        bullish_bounce = (close > open_p) and (close >= ema_21)
        rsi_healthy = (38 <= rsi <= 68)
        if pulled_back and bullish_bounce and rsi_healthy:
            sl = max(st_lower, close - (atr * 2.0))
            risk = max(close - sl, atr * 0.8)
            tp = close + (risk * _T_RR)
            if _t_bracket_ok(close, sl, tp, "BUY"):
                return _TSignalResult("BUY", sl, tp, "RULE_BASED", _T_PRIOR, _T_RR)
            return none_res

    if _T_BLOCK_SHORTS and ema_50 > ema_200:
        return none_res
    if st_now == False and st_prev == True and close < ema_200:
        sl = min(st_upper, close + (atr * 2.0))
        risk = max(sl - close, atr * 0.8)
        tp = close - (risk * _T_RR)
        if _t_bracket_ok(close, sl, tp, "SELL"):
            return _TSignalResult("SELL", sl, tp, "RULE_BASED", _T_PRIOR, _T_RR)
        return none_res

    if _T_BLOCK_SHORTS and ema_50 > ema_200:
        return none_res
    if st_now == False and st_prev == False and close < ema_200 and ema_21 <= ema_50:
        pulled_back = (high >= ema_21 * 0.998 or prev_high >= ema_21 * 0.998)
        bearish_bounce = (close < open_p) and (close <= ema_21 * 1.002)
        rsi_healthy = (32 <= rsi <= 62)
        if pulled_back and bearish_bounce and rsi_healthy:
            sl = min(st_upper, close + (atr * 2.0))
            risk = max(sl - close, atr * 0.8)
            tp = close - (risk * _T_RR)
            if _t_bracket_ok(close, sl, tp, "SELL"):
                return _TSignalResult("SELL", sl, tp, "RULE_BASED", _T_PRIOR, _T_RR)
            return none_res

    return none_res


def _t_extract(res):
    """rigorous_backtest/module_eval.py _extract, verbatim semantics."""
    if res is None:
        return None
    side = res.get("side") if isinstance(res, dict) else getattr(res, "side", None)
    sl = res.get("sl") if isinstance(res, dict) else getattr(res, "sl", None)
    tp = res.get("tp") if isinstance(res, dict) else getattr(res, "tp", None)
    if side in ("BUY", "LONG"):
        side = "LONG"
    elif side in ("SELL", "SHORT"):
        side = "SHORT"
    else:
        return None
    if sl is None or tp is None:
        return None
    sl_f, tp_f = float(sl), float(tp)
    if sl_f <= 0 or tp_f <= 0:
        return None
    return side, sl_f, tp_f


def _gov2_bare_entries(df: pd.DataFrame):
    """Inline replica of the judged gov2 bare evaluation for this row:
    shared features.add_features once over the frame, transcribed
    judged get_signal on trailing <=500-bar windows, bars
    [260, len-2], module_eval._extract, NO signal filter; distances
    from the signal-bar close."""
    featured = shared_features.add_features(df)
    closes = df["close"].to_numpy(dtype=float)
    out = []
    for i in range(WARMUP, len(df) - 1):
        res = _t_get_signal(featured.iloc[max(0, i - WINDOW + 1): i + 1].copy())
        ex = _t_extract(res)
        if ex is None:
            continue
        side, sl, tp = ex
        if side == "LONG":
            out.append((i, "LONG", closes[i] - sl, tp - closes[i]))
        else:
            out.append((i, "SHORT", sl - closes[i], closes[i] - tp))
    return out


# ---------------------------------------------------------------------------
# 1. Equivalence: production lane module vs the judged evaluation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"])
def test_supertrend_bare_entries_match_judged_evaluation(fixture):
    df = _load(fixture)
    judged = _gov2_bare_entries(df)
    production = stb.entries_for_frame(df, WARMUP)
    assert len(judged) >= 50, "fixture must contain a meaningful entry set"
    assert production == judged
    sides = {side for _i, side, _sl, _tp in judged}
    assert sides == {"LONG", "SHORT"}, "both judged directions must appear"


# ---------------------------------------------------------------------------
# 2. Bracket geometry (the judged module bracket)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"])
def test_supertrend_bare_bracket_geometry(fixture):
    df = _load(fixture)
    featured = shared_features.add_features(df)
    atr = featured["atr"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    entries = stb.entries_for_frame(df, WARMUP)
    assert entries
    for i, _side, sl_dist, tp_dist in entries:
        # Stop: supertrend band bounded by 2.0 x ATR(14).
        assert sl_dist <= 2.0 * atr[i] + 1e-9
        # Anti-churn floor: both legs >= 0.30% of the signal-bar close.
        assert sl_dist >= 0.0030 * closes[i] * (1 - 1e-9)
        assert tp_dist >= 0.0030 * closes[i] * (1 - 1e-9)
        # TP = 3.0R with the risk floored at 0.8 x ATR(14).
        assert tp_dist == pytest.approx(3.0 * max(sl_dist, 0.8 * atr[i]))


# ---------------------------------------------------------------------------
# 3. Live daemon contract
# ---------------------------------------------------------------------------

def test_supertrend_bare_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_4h.csv")
    judged = stb.entries_for_frame(df, WARMUP)
    assert judged, "fixture must contain judged entries"
    for i, side, sl_dist, tp_dist in judged[:4]:
        sig = stb.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(sl_dist)
        assert sig["tp_dist"] == pytest.approx(tp_dist)
        # The lane's own RD-002 prior — NOT the judged module's
        # internal ledger prior (0.266, kept verbatim in its
        # SignalResult, which gov2 never extracted).
        assert sig["win_rate_prior"] == pytest.approx(0.2602)
        assert sig["rr_ratio"] == pytest.approx(3.0)
    entry_bars = {i for i, _s, _sl, _tp in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert stb.get_signal(df.iloc[: quiet + 1])["side"] is None


def test_supertrend_bare_forming_bar_is_never_evaluated():
    now = 1_800_000_000.0  # fixed epoch, arbitrary
    # 4h wrapper: opens at now-12h / now-8h / now-4h-1s are closed;
    # the bar opening now-1h is still forming.
    opens = [now - 12 * 3600, now - 8 * 3600, now - 4 * 3600 - 1, now - 3600]
    idx = pd.to_datetime(opens, unit="s", utc=True)
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx,
    )
    assert len(stb._closed_frame(df, now_s=now)) == 3


def test_supertrend_bare_judged_constants_verbatim():
    # The judged module's own constants, restored verbatim.
    assert stb._JUDGED_OOS_WIN_RATE_PRIOR == pytest.approx(0.266)
    assert stb._JUDGED_RR_RATIO == pytest.approx(3.0)
    assert stb.MIN_BRACKET_PCT == pytest.approx(0.0030)
    assert stb.BLOCK_SHORTS_IN_BULL_REGIME is True  # judged default env
    # The lane's bindings come from SUPERTREND_BARE_STRATEGY.
    assert stb.TIMEFRAME == "4h"
    assert stb.BAR_SECONDS == 4 * 3600
    assert stb.WARMUP_BARS == 260
    assert stb.WINDOW == 500
    assert stb.WIN_RATE_PRIOR == pytest.approx(0.2602)
    assert stb.RR_RATIO == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# 4. Governance: the FORWARD_TEST classification
# ---------------------------------------------------------------------------

def test_config_registry_supertrend_bare_entry():
    from config_strategy import CRYPTO30_SYMBOLS, PRODUCTION_STRATEGY_REGISTRY

    entry = PRODUCTION_STRATEGY_REGISTRY["supertrend_bare"]
    assert entry["status"] == "FORWARD_TEST"
    assert entry["version"] == "v1.0.0 (TASK-STR-FWD-020)"
    assert entry["timeframe"] == "4h"
    assert entry["forward_protocol"] is True
    assert entry["forward_lane"] == "FORWARD_TEST"
    assert entry["lane_assets"] == CRYPTO30_SYMBOLS
    assert not entry.get("validated_assets")
    # Lane-executable, so the judged priors survive the null-out.
    assert entry["runtime_priors_nulled"] is False
    assert entry["oos_win_rate_prior"] == pytest.approx(0.2602)
    assert entry["expected_net_edge_bps"] == pytest.approx(19.1)
    assert entry["rr_ratio"] == pytest.approx(3.0)
    # FWD-006 lane terms.
    assert entry["risk_per_trade_pct"] == pytest.approx(0.001)
    assert entry["max_heat_pct"] == pytest.approx(0.02)
    # The RD-002 figures are on the record in the reason string.
    for needle in ("3,109", "1.0529", "+0.1911%", "0.2602", "ba3cc800"):
        assert needle in entry["reason"], needle


def test_config_dict_supertrend_bare():
    from config_strategy import SUPERTREND_BARE_STRATEGY as cfg

    assert cfg["TIMEFRAME"] == "4h"
    assert cfg["OOS_TRADES"] == 3109
    assert cfg["OOS_WIN_RATE"] == pytest.approx(0.2602)
    assert cfg["OOS_PROFIT_FACTOR"] == pytest.approx(1.0529)
    assert cfg["OOS_EXPECTANCY_PCT"] == pytest.approx(0.191)
    assert cfg["RR_RATIO"] == pytest.approx(3.0)
    assert cfg["MIN_BRACKET_PCT"] == pytest.approx(0.0030)


def test_governance_classification_supertrend_bare():
    from strategies.strategy_registry import (
        governance_key_for,
        governance_status_for,
    )

    assert governance_key_for("strategy_supertrend_bare") == "supertrend_bare"
    assert governance_status_for("strategy_supertrend_bare") == "FORWARD_TEST"
    # The deleted production module's name stays unregistered: the
    # lane entrant is a separate module with its own record, and the
    # incident-era module is not resurrected by this wiring.
    assert governance_status_for("strategy_supertrend") == "UNREGISTERED"


@pytest.fixture(scope="module")
def registry():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    return UnifiedStrategyRegistry()


def test_supertrend_bare_blocked_without_demo_attestation(registry):
    assert registry.demo_venues() == frozenset()
    ok, reason = registry.executable(
        "strategy_supertrend_bare", "4h", "BTCUSDT", venue="binance_futures"
    )
    assert not ok and reason == "FORWARD_TEST_DEMO_VENUE_ONLY"
    ok, reason = registry.executable("strategy_supertrend_bare", "4h", "BTCUSDT")
    assert not ok and reason == "FORWARD_TEST_REQUIRES_VENUE"


def test_supertrend_bare_executable_only_on_attested_demo_venue(registry):
    registry.set_demo_venues({"binance_futures"})
    try:
        assert registry.executable(
            "strategy_supertrend_bare", "4h", "BTCUSDT", venue="binance_futures"
        )[0]
        assert registry.executable(
            "strategy_supertrend_bare", "4h", "SOLUSDT", venue="binance_futures"
        )[0]
        # Wrong timeframe / off-universe symbol / unattested venue.
        assert not registry.executable(
            "strategy_supertrend_bare", "1d", "BTCUSDT", venue="binance_futures"
        )[0]
        assert not registry.executable(
            "strategy_supertrend_bare", "4h", "EURUSD", venue="binance_futures"
        )[0]
        assert not registry.executable(
            "strategy_supertrend_bare", "4h", "BTCUSDT", venue="oanda"
        )[0]
    finally:
        registry.set_demo_venues(set())


# ---------------------------------------------------------------------------
# 5. Stop-cap (TASK-STR-FWD-012): NO override — decision pinned
# ---------------------------------------------------------------------------

def test_stop_cap_decision_no_override_supertrend_bare():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    # Measured 2026-11-18 (see the module docstring of this file):
    # 4,441 judged signals, max stop 14.28% of price, 0.00% above
    # the 0.15 production cap — the key stays ABSENT.
    assert "max_stop_pct" not in PRODUCTION_STRATEGY_REGISTRY["supertrend_bare"]

    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    assert daemon._max_stop_pct_for_strategy("strategy_supertrend_bare") is None
    assert daemon._max_stop_pct_for_strategy("supertrend_bare") is None
    # Control: an existing override still resolves (lookup unharmed).
    assert daemon._max_stop_pct_for_strategy("strategy_sleeve_shock_breakout") == pytest.approx(0.90)
