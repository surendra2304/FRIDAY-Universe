"""overlay_service — TASK-STR-FWD-021: the RD-014 vol-target overlay core.

The judged object (TASK-STR-RD-014, declaration hashed on issue #35
before the first run; code rigorous_backtest/rd14/family14.py) is NOT
a bracket strategy. Per symbol it is a continuous target weight

    w_t = s_t * min(1, sigma_target / sigma_t)

with s_t in {-1, 0, +1} from one of four signals (tsmom42, tsmom126,
ema10_50, ema20_100), sigma_t the annualised sample stdev (ddof=1) of
the trailing 42 bar log returns, and the position actually held over
bar t+1 scaled by a drawdown-brake multiplier m_t driven causally by
the drawdown of the SAME configuration's UNBRAKED (shadow) per-symbol
equity curve: the brake engages at dd <= -threshold and releases at
dd >= -threshold/2 (flat_05: 0.05 -> m 0; flat_10: 0.10 -> m 0;
half_10: 0.10 -> m 0.5; none: m 1). Costs in the judgement are
0.0008 per unit of |delta position| turnover. The judgement unit is
the position episode (maximal constant-sign non-zero run).

The 21 configurations admitted to the FORWARD_TEST lane under the
owner's two-tier rule (2026-11-18: OOS expectancy > 0 AND PF >= 1.05
AND >= 200 OOS episodes, pre-Bonferroni) are registered in
config_strategy.py with execution_mode "overlay" and are executed by
the daemon's overlay manager (autonomy/run_daemon.py
_manage_overlay_positions), NOT by the get_signal/_execute_signal
path — that path requires an SL/TP bracket and this judged object
has none. There is deliberately no strategy_*.py module for these
entries. TASK-STR-FWD-031: live entries DO carry a venue bracket — a
catastrophic backstop derived from this module's own judged sigma
(bracket_levels), placed with the entry and held for the position's
life. The bracket is execution safety, not judged exit logic: the
judged exits remain the target weight and the drawdown brake, and no
judged SL/TP is invented.

The functions below are a line-faithful port of family14.py; the
equivalence is pinned by tests/test_fwd021_overlay_service.py, which
runs this module and the judged harness side by side on identical
close series and requires identical weights, shadow drawdowns, brake
multipliers and position series.

Execution translation (disclosed in each registry entry's reason):
the judged books are per-symbol standalone equity curves; live, the
21 configurations share one demo account. Each configuration holds a
declared virtual book of overlay_capital_pct x venue equity and a
symbol's target notional is m * w * book. One venue position per
symbol account-wide (the daemon's standing rule) means a
configuration whose target symbol is held by another strategy waits
(logged as contention) — the judged signal/vol/brake state itself is
a pure function of the close series and is unaffected. Actions are
bar-cadenced and target-based, hence idempotent across restarts:
the state needs no persistence, the shadow equity warm-starts from
the candle history the venue returns (the manager logs the depth).
"""

from __future__ import annotations

import math
from typing import Any, Dict

import numpy as np
import pandas as pd

SIGNALS = ("tsmom42", "tsmom126", "ema10_50", "ema20_100")
VOL_TARGETS = (0.15, 0.30, 0.60)
BRAKES = ("none", "flat_05", "flat_10", "half_10")
VOL_WINDOW = 42
COST_PER_TURNOVER = 0.0008          # judged: 8 bps per unit turnover
BARS_PER_YEAR = {"4h": 2190.0, "1d": 365.0}
BAR_SECONDS = {"4h": 4 * 3600, "1d": 24 * 3600}
_BRAKE_PARAMS = {                   # name -> (threshold, multiplier while braked)
    "flat_05": (0.05, 0.0),
    "flat_10": (0.10, 0.0),
    "half_10": (0.10, 0.5),
}
# Bars before a target is meaningful: the slowest ingredient is the
# 126-bar tsmom lookback; the vol window needs 42 returns and the
# ema20_100 slow EMA is seeded at the first close. 200 bars keeps the
# shadow-equity path past its shallowest stretch on every signal.
MIN_BARS = 200


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd14/family14.py)
# ---------------------------------------------------------------------------

def signal_series(close: pd.Series, name: str) -> np.ndarray:
    """Signal per bar close: -1 / 0 / +1 (warm-up -> 0).

    family14._signal, verbatim.
    """
    if name.startswith("tsmom"):
        look = int(name[5:])
        s = np.sign(np.log(close).diff(look))
    elif name.startswith("ema"):
        fast, slow = (int(x) for x in name[3:].split("_"))
        ef = close.ewm(span=fast, adjust=False).mean()
        es = close.ewm(span=slow, adjust=False).mean()
        s = np.sign(ef - es)
    else:
        raise ValueError(f"unknown signal {name}")
    return s.fillna(0.0).to_numpy(dtype=float)


def raw_weights(close: pd.Series, signal: str, vol_target: float,
                tf: str) -> np.ndarray:
    """w_t fixed at close of bar t: signal * min(1, target / sigma_t).

    family14.raw_weights, verbatim.
    """
    logret = np.log(close).diff()
    sigma = (logret.rolling(VOL_WINDOW).std(ddof=1)
             * np.sqrt(BARS_PER_YEAR[tf]))
    s = signal_series(close, signal)
    sig = sigma.to_numpy(dtype=float)
    ok = (sig > 0) & np.isfinite(sig)
    scale = np.where(ok, np.minimum(1.0, vol_target / np.where(ok, sig, 1.0)),
                     0.0)
    return s * scale


def shadow_equity(close: pd.Series, w: np.ndarray, cost: float):
    """Unbraked positions (pos[i] holds w[i-1]) and the shadow equity
    drawdown series dd[t] (known at the close of bar t).

    family14.shadow_equity, verbatim.
    """
    n = len(close)
    ret = close.pct_change().fillna(0.0).to_numpy(dtype=float)
    pos = np.zeros(n)
    pos[1:] = w[:-1]
    prev = np.concatenate([[0.0], pos[:-1]])
    r = pos * ret - np.abs(pos - prev) * cost
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(eq)
    return pos, eq / peak - 1.0


def brake_multiplier(dd: np.ndarray, brake: str) -> np.ndarray:
    """m[t] set at the close of bar t from dd[t]: engages at
    dd <= -threshold, releases at dd >= -threshold/2 (hysteresis).

    family14.brake_multiplier, verbatim.
    """
    if brake == "none":
        return np.ones(len(dd))
    thr, mult = _BRAKE_PARAMS[brake]
    m = np.ones(len(dd))
    braked = False
    for t in range(len(dd)):
        d = dd[t]
        if np.isfinite(d):
            if not braked and d <= -thr:
                braked = True
            elif braked and d >= -thr / 2.0:
                braked = False
        m[t] = mult if braked else 1.0
    return m


def positions_series(w: np.ndarray, dd: np.ndarray, brake: str) -> np.ndarray:
    """Position held over bar i: m[i-1] * w[i-1] (both fixed at close
    of bar i-1). For brake == 'none' this is the shadow position.

    family14.positions, verbatim.
    """
    n = len(w)
    if brake == "none":
        pos = np.zeros(n)
        pos[1:] = w[:-1]
        return pos
    m = brake_multiplier(dd, brake)
    pos = np.zeros(n)
    pos[1:] = (m * w)[:-1]
    return pos


# ---------------------------------------------------------------------------
# Live evaluation
# ---------------------------------------------------------------------------

def target_weight(close: pd.Series, signal: str, vol_target: float,
                  brake: str, tf: str,
                  cost: float = COST_PER_TURNOVER) -> Dict[str, Any]:
    """Target weight to hold over the NEXT bar, evaluated on a close
    series whose last element is the last CLOSED bar.

    The judged timing is pos[i] = m[i-1] * w[i-1]: at the close of
    the last bar t the position for bar t+1 is m[t] * w[t], both
    fixed at that close. Everything here is causal — the result is a
    pure function of the closes supplied, so truncating the series
    at bar t reproduces the bar-t target exactly (pinned by test).
    """
    close = close.astype(float)
    w = raw_weights(close, signal, vol_target, tf)
    _pos, dd = shadow_equity(close, w, cost)
    m = brake_multiplier(dd, brake)
    logret = np.log(close).diff()
    sigma = (logret.rolling(VOL_WINDOW).std(ddof=1)
             * np.sqrt(BARS_PER_YEAR[tf]))
    sigma_t = float(sigma.iloc[-1]) if len(sigma) else float("nan")
    return {
        "weight": float(m[-1] * w[-1]),
        "raw_weight": float(w[-1]),
        "signal": float(signal_series(close, signal)[-1]),
        "sigma": sigma_t,
        "shadow_dd": float(dd[-1]),
        "brake_m": float(m[-1]),
        "bars": int(len(close)),
    }


# ---------------------------------------------------------------------------
# Venue bracket (TASK-STR-FWD-031)
# ---------------------------------------------------------------------------
#
# The judged object has no SL/TP, so the live bracket cannot come from
# the judgement — it comes from the judgement's own risk unit instead.
# The bracket is a catastrophic backstop, NOT a trading exit: it sits
# BRACKET_SIGMA_MULTIPLE one-bar sigmas from the entry price, where a
# one-bar sigma is the trailing-42-bar annualised vol (sigma_t, the
# same sigma that sizes the position) converted to a per-bar fraction.
# A move of that size is outside the judged distribution's ordinary
# range, so the bracket essentially never binds in normal operation —
# the judged exits (target weight, drawdown brake) govern every
# ordinary bar — and it only fires on a gap move the bar-cadenced
# judged management cannot catch intrabar. It is symmetric (SL + TP)
# because the venue bracket, as the venue adapters define it, is the
# SL/TP pair (the MT5 adapter requires both on every entry), and
# symmetry keeps the backstop neutral to the judged signal. The stop
# is deliberately WIDER than the daemon's signal-path stop band
# (min/max_stop_pct): that band prices trading stops, and clamping
# this backstop into it would turn it into a trading stop that binds
# on ordinary bars and distorts the judged forward record.

BRACKET_SIGMA_MULTIPLE = 4.0


def bracket_levels(sigma: float, tf: str, price: float,
                   is_long: bool) -> tuple[float | None, float | None]:
    """(stop_loss, take_profit) for an overlay entry, or (None, None).

    Long: (price - d, price + d); short: (price + d, price - d), where
    d = BRACKET_SIGMA_MULTIPLE * sigma / sqrt(bars_per_year[tf]) * price.
    Returns (None, None) when no bracket is computable (non-finite or
    non-positive sigma, unknown timeframe, non-positive price, or a
    level that would not be positive) — the caller must then NOT place
    the entry unprotected (fail-closed).
    """
    try:
        sigma_f = float(sigma)
        price_f = float(price)
    except (TypeError, ValueError):
        return None, None
    bars = BARS_PER_YEAR.get(tf)
    if bars is None or not math.isfinite(sigma_f) or sigma_f <= 0:
        return None, None
    if not math.isfinite(price_f) or price_f <= 0:
        return None, None
    dist = BRACKET_SIGMA_MULTIPLE * sigma_f / math.sqrt(bars) * price_f
    if not math.isfinite(dist) or dist <= 0:
        return None, None
    if is_long:
        stop, take = price_f - dist, price_f + dist
    else:
        stop, take = price_f + dist, price_f - dist
    if stop <= 0 or take <= 0:
        return None, None
    return stop, take
