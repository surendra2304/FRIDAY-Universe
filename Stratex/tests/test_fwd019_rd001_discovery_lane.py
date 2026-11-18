"""TASK-STR-FWD-019 WAVE-2 — RD-001 stage-1 discovery modules lane.

strategy_volatility_breakout and strategy_choppiness_breakout meet
the owner's second tier (audit ~/workspace/str-nearmiss/REPORT.md
§1.1) but did NOT pass the full frozen bar. This file pins:

1. EQUIVALENCE: the production modules reproduce the judged
   stage-1 evaluation entry-for-entry (with bracket distances) on
   the fwd002 fixture slices. The judged harness
   (rigorous_backtest/module_eval.py, driven by rd/stage1.py)
   called each module's OWN get_signal() on trailing <=500-bar
   windows from bar 260 and kept the module's own bracket. The
   judged module files were deleted by TASK-STR-CLEANUP-001 after
   judgement, so the reference below is a verbatim transcription
   of the judged sources (volatility_breakout @ bd9585c97b,
   choppiness_breakout @ 8b6ec77a4 — the last pre-deletion
   revisions), evaluated exactly as module_eval evaluated them.
   The judged calendar-date forming-bar drop is a no-op on these
   historical windows and is omitted from the transcription.
   The fixtures are daily-binned price slices used purely as bar
   series: the signal is a pure function of the bar series, so
   the equivalence property is timeframe-agnostic — the judged
   timeframe itself (1h) is pinned separately in section 2.
2. GOVERNANCE + TIMEFRAME: both keys are FORWARD_TEST lane
   entries with the judged priors, CRYPTO30 lane_assets, and
   neither is in the VALIDATED partition. Both are wired at the
   JUDGED 1h: registry timeframe, config TIMEFRAME, module
   TIMEFRAME / BAR_SECONDS, and the registry executable() binding
   all say 1h / 3600, and executable() at 1d is refused.
3. STOP-CAP: the FWD-012 check was re-measured at the judged 1h
   on the judged datasets (recorded below). volatility_breakout's
   judged stops exceed the 0.15 global cap at 1h (pooled all-bars
   max 0.1665), so it carries an override (0.25) — without it the
   widest judged stops would be cap-blocked and silently never
   trade. choppiness_breakout's judged stops stay below the cap
   at 1h (pooled all-bars max 0.1152), so it carries NO override.
   (The original overrides 1.20 / 0.80 rested on measurements over
   the fwd002 1d fixtures — not the judged timeframe — and are
   superseded.)

Timeframe provenance: JUDGED AT 1h. rd/stage1.py evaluated on
load_timeframe("1h") — the dataset selected by
run_all._infer_primary_timeframe (default "1h"; neither module's
text names a timeframe) — and the stage-1 row JSONs record
timeframe "1h" with data_provenance keyed BTCUSDT_1h /
ETHUSDT_1h / SOLUSDT_1h at 27,048 hourly rows per symbol. The
original 1d wiring rested on the near-miss audit REPORT §1.1
footnote ("stage-1 discovery ran one daily configuration per
module"), which the primary records contradict; corrected
2026-11-18 per the wave-2 review (comment 6975928782). See the
registry reasons for the full record.
"""

from __future__ import annotations

import math
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_choppiness_breakout as chop
import strategy_volatility_breakout as vol

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260
WINDOW = 500

KEYS = ("volatility_breakout", "choppiness_breakout")

# FWD-012 stop-cap measurements AT THE JUDGED 1h on the judged
# datasets (BTC/ETH/SOL 1h, 27,048 bars each, 2023-10 to 2026-10 —
# the stage-1 row provenance; judged stop / close, pooled over the
# three symbols, SOLUSDT the max on both measures):
# volatility_breakout (2.5 x ATR(14) SMA): entry-bar max 0.1284,
# all-bars >= warmup max 0.1665 -> override 0.25 (rounded bound
# above the measured max; the pooled max exceeds the 0.15 global
# cap, so the override is load-bearing).
# choppiness_breakout (2.0 x ATR(20) SMA): entry-bar max 0.0853,
# all-bars >= warmup max 0.1152 -> NO override (the pooled max is
# below the 0.15 global cap at the judged timeframe).
# Superseded: the original measurements were taken on the fwd002
# 1d fixtures (volatility 0.9525/0.9640 -> 1.20; choppiness
# 0.6297/0.6667 -> 0.80) — not at the judged timeframe.
MEASURED = {
    "volatility_breakout": (0.1284, 0.1665, 0.25),
    "choppiness_breakout": (0.0853, 0.1152, None),
}


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# Judged-source transcriptions (reference implementations)
# ---------------------------------------------------------------------------

def _judged_vol_window(work: pd.DataFrame):
    """strategy_volatility_breakout.get_signal @ bd9585c97b, verbatim
    logic (minus the no-op historical forming-bar drop)."""
    if len(work) < 205:
        return None
    close = work["close"].astype(float)
    high = work["high"].astype(float)
    low = work["low"].astype(float)
    ema_fast = close.ewm(span=50, adjust=False).mean()
    ema_slow = close.ewm(span=200, adjust=False).mean()
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(14).mean()
    atr_avg = atr.rolling(20).mean()
    prior_high_10 = high.rolling(10).max().shift(1)
    prior_low_10 = low.rolling(10).min().shift(1)
    c = float(close.iloc[-1])
    a = float(atr.iloc[-1])
    a_avg = float(atr_avg.iloc[-1])
    ef = float(ema_fast.iloc[-1])
    es = float(ema_slow.iloc[-1])
    ph = float(prior_high_10.iloc[-1])
    pl = float(prior_low_10.iloc[-1])
    if any(math.isnan(v) for v in (a, a_avg, ef, es, ph, pl)) or a <= 0 or c <= 0 or a_avg <= 0:
        return None
    vol_expanding = a > 1.2 * a_avg
    if c > ph and vol_expanding and ef > es:
        return ("LONG", 2.5 * a, 6.0 * a)
    if c < pl and vol_expanding and ef < es:
        return ("SHORT", 2.5 * a, 6.0 * a)
    return None


def _judged_chop_window(work: pd.DataFrame):
    """strategy_choppiness_breakout.get_signal @ 8b6ec77a4, verbatim
    logic (minus the no-op historical forming-bar drop; the source's
    _bracket clamp helper is never called by its get_signal)."""
    if len(work) < 250:
        return None
    close = work["close"].astype(float)
    high = work["high"].astype(float)
    low = work["low"].astype(float)
    c = float(close.iloc[-1])
    if c <= 0:
        return None
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(20).mean()
    a = float(atr.iloc[-1])
    hh = high.rolling(14).max()
    ll = low.rolling(14).min()
    tr_sum = tr.rolling(14).sum()
    rng = (hh - ll).replace(0, pd.NA)
    ratio = (tr_sum / rng).astype(float)
    chop_s = 100.0 * ratio.apply(
        lambda v: math.log10(v) if pd.notna(v) and v > 0 else float("nan")
    )
    chopv = float(chop_s.iloc[-1])
    hh20 = float(high.rolling(20).max().shift(1).iloc[-1])
    ll20 = float(low.rolling(20).min().shift(1).iloc[-1])
    s200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
    if any(math.isnan(v) for v in (a, chopv, hh20, ll20, s200)) or a <= 0:
        return None
    if chopv < 45.0:
        if c > hh20 and c > s200:
            return ("LONG", 2.0 * a, 4.5 * a)
        if c < ll20 and c < s200:
            return ("SHORT", 2.0 * a, 4.5 * a)
    return None


def _judged_entries(df: pd.DataFrame, window_fn):
    """module_eval's extraction: bars [260, len-2], trailing
    <=500-bar windows, (bar, side, sl_dist, tp_dist)."""
    out = []
    for i in range(WARMUP, len(df) - 1):
        res = window_fn(df.iloc[max(0, i - WINDOW + 1): i + 1].copy())
        if res is not None:
            out.append((i, res[0], res[1], res[2]))
    return out


def _production_entries(df: pd.DataFrame, module, window_fn_unused=None):
    out = []
    for i, side in module.entries_for_frame(df, WARMUP):
        res = module._signal_on_window(df.iloc[max(0, i - WINDOW + 1): i + 1])
        assert res is not None
        out.append((i, side, res[1], res[2]))
    return out


# ---------------------------------------------------------------------------
# 1. Equivalence: production modules vs the judged stage-1 evaluation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_volatility_entries_match_judged(fixture):
    df = _load(fixture)
    judged = _judged_entries(df, _judged_vol_window)
    production = _production_entries(df, vol)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_choppiness_entries_match_judged(fixture):
    df = _load(fixture)
    judged = _judged_entries(df, _judged_chop_window)
    production = _production_entries(df, chop)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged


def test_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_1d.csv")
    for module, wr, rr in ((vol, 0.3519, 2.4), (chop, 0.3564, 2.25)):
        judged = _judged_entries(
            df, _judged_vol_window if module is vol else _judged_chop_window
        )
        assert judged
        for i, side, sl_dist, tp_dist in judged[:3]:
            sig = module.get_signal(df.iloc[: i + 1])
            assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
            assert sig["sl_dist"] == pytest.approx(sl_dist)
            assert sig["tp_dist"] == pytest.approx(tp_dist)
            assert sig["win_rate_prior"] == pytest.approx(wr)
            assert sig["rr_ratio"] == pytest.approx(rr)
        entry_bars = {j for j, *_ in judged}
        quiet = next(j for j in range(WARMUP, len(df) - 2) if j not in entry_bars)
        assert module.get_signal(df.iloc[: quiet + 1])["side"] is None


# ---------------------------------------------------------------------------
# 2. Governance: registry / partition
# ---------------------------------------------------------------------------

def test_config_registry_lane_entries():
    from config_strategy import (
        CHOPPINESS_BREAKOUT_STRATEGY,
        CRYPTO30_SYMBOLS,
        PRODUCTION_STRATEGY_REGISTRY,
        VOLATILITY_BREAKOUT_STRATEGY,
    )

    for key, wr, edge, rr in (
        ("volatility_breakout", 0.3519, 13.1, 2.4),
        ("choppiness_breakout", 0.3564, 7.4, 2.25),
    ):
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["forward_protocol"] is True, key
        assert entry["forward_lane"] == "FORWARD_TEST", key
        assert entry["timeframe"] == "1h", key
        assert entry["lane_assets"] == CRYPTO30_SYMBOLS, key
        assert entry["runtime_priors_nulled"] is False, key
        assert entry["oos_win_rate_prior"] == pytest.approx(wr), key
        assert entry["expected_net_edge_bps"] == pytest.approx(edge), key
        assert entry["rr_ratio"] == pytest.approx(rr), key
        assert entry["risk_per_trade_pct"] == pytest.approx(0.001), key
        assert entry["max_heat_pct"] == pytest.approx(0.02), key
        assert not entry.get("validated_assets"), key
        # The corrected timeframe-provenance record is on the entry.
        assert "JUDGED AT 1h" in entry["reason"], key
        assert "Wired at 1h" in entry["reason"], key
        assert "27,048 hourly rows" in entry["reason"], key
        assert "registered-but-not-allowlisted" in entry["reason"], key

    # The per-strategy config dicts the modules read say 1h too.
    assert VOLATILITY_BREAKOUT_STRATEGY["TIMEFRAME"] == "1h"
    assert CHOPPINESS_BREAKOUT_STRATEGY["TIMEFRAME"] == "1h"

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
    for key in KEYS:
        assert key not in validated


def test_registry_discovers_modules_and_binds_lane():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    for key in KEYS:
        assert reg.get(f"strategy_{key}") is not None, key
        assert reg.governance_status(f"strategy_{key}") == "FORWARD_TEST", key
    ok, reason = reg.executable(
        "strategy_volatility_breakout", "1h", "BTCUSDT", venue="binance_futures"
    )
    assert not ok and reason == "FORWARD_TEST_DEMO_VENUE_ONLY"
    reg.set_demo_venues({"binance_futures"})
    try:
        for key in KEYS:
            assert reg.executable(
                f"strategy_{key}", "1h", "BTCUSDT", venue="binance_futures"
            )[0], key
            # The judged timeframe is 1h; the pre-fix 1d wiring must
            # stay refused (regression pin for the wave-2 C5 fix).
            assert not reg.executable(
                f"strategy_{key}", "1d", "BTCUSDT", venue="binance_futures"
            )[0], key
    finally:
        reg.set_demo_venues(set())


def test_timeframe_wiring_matches_judged_1h():
    """Every layer of the wiring names the judged 1h — a regression
    to 1d in any one of them fails here (wave-2 review C5)."""
    from config_strategy import (
        CHOPPINESS_BREAKOUT_STRATEGY,
        PRODUCTION_STRATEGY_REGISTRY,
        VOLATILITY_BREAKOUT_STRATEGY,
    )

    for module in (vol, chop):
        assert module.TIMEFRAME == "1h", module.__name__
        assert module.BAR_SECONDS == 3600, module.__name__
    for cfg in (VOLATILITY_BREAKOUT_STRATEGY, CHOPPINESS_BREAKOUT_STRATEGY):
        assert cfg["TIMEFRAME"] == "1h"
    for key in KEYS:
        assert PRODUCTION_STRATEGY_REGISTRY[key]["timeframe"] == "1h", key


def test_daemon_forward_protocol_covers_modules():
    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    entries = daemon._forward_protocol_entries()
    for key in KEYS:
        assert f"strategy_{key}" in entries, key
        assert daemon._lane_for_strategy(f"strategy_{key}") == "FORWARD_TEST", key


# ---------------------------------------------------------------------------
# 3. Stop-cap consistency (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_override_consistent_with_measurements():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    for key, (entry_max, all_max, chosen) in MEASURED.items():
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        if chosen is None:
            # At the judged 1h this module's measured stops never
            # reach the 0.15 global cap — an override would admit
            # stops outside the judged distribution, so none is
            # carried (FWD-012 forex precedent).
            assert all_max < 0.15, key
            assert entry_max < 0.15, key
            assert "max_stop_pct" not in entry, key
        else:
            # The measured stops exceed the 0.15 global cap — the
            # override is load-bearing, not decorative, and it must
            # bound the measured 1h distribution.
            assert all_max > 0.15, key
            assert entry["max_stop_pct"] == pytest.approx(chosen), key
            assert entry["max_stop_pct"] > 0.15, key
            assert entry["max_stop_pct"] >= all_max, key
            assert entry["max_stop_pct"] >= entry_max, key
