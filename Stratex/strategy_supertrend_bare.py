"""strategy_supertrend_bare — TASK-STR-FWD-020 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002, governed family, judged "as
coded" from the live module via rigorous_backtest/rd2/gov2.py
``eval_module_cell``, config "bare"): strategy_supertrend:bare
@ CRYPTO30 4h — 3,109 pooled OOS trades, +0.1911%/trade, PF 1.0529,
win rate 0.2602, 3/5 positive folds, untouched-holdout expectancy
+0.1097% (1,048 trades, holdout PASS). It meets the owner's second
tier (expectancy > 0, PF >= 1.05, >= 200 OOS trades, pre-Bonferroni)
but did NOT pass the full frozen bar (PF < 1.2, folds < 4/5,
Bonferroni FAIL) — not a promotion, not VALIDATED. The owner
directed 2026-11-18 (implement-all) that such near-miss candidates
be decided by real demo forward evidence in the FORWARD_TEST lane.
This was the near-miss audit's one unassigned tier row (REPORT
§1.4 #91): absent from §7's wave lists, it was skipped by waves 1–2.

JUDGED-MODULE STATE (read before touching this file): the live
module gov2 judged (strategy_supertrend.py) was DELETED from main
by TASK-STR-CLEANUP-001 (commit 020ea57b) under the earlier PF<1.2
evidence rule (the cleanup record cites "supertrend (PF 0.82)" —
an earlier aggregate; the family's crypto30 1d cell measured
PF 0.8689 in RD-002 and STAYS deleted; only the 4h bare cell is
admitted here). The judged signal code is restored VERBATIM in
this wrapper from the pre-cleanup blob (strategy_supertrend.py
blob ba3cc8006688d6e6399e91c89cb8a80c791f1c2c — the file's last
content state, from commit 7c149a2b; no commit touched the file
between the RD-002 judgement and the deletion), so the code path
below is byte-equivalent in logic to what gov2 evaluated:
supertrend flip / pullback-continuation entries over the shared
features frame, module bracket SL = supertrend band bounded by
2.0 x ATR(14), risk floored at 0.8 x ATR(14), TP = 3.0R,
anti-churn floor 0.30% of price on both legs. The feature pipeline
gov2 recorded for this row is the SHARED features.add_features
(the judged module has no add_features of its own; features.py
blob 9920313e0500d9bdbcd54f3b230427ab6e0540a6 is byte-identical
then and now). The judged module's ADX chop filter is inert under
that pipeline: the shared frame carries no ADX column, so the
filter's default (0.0) never triggers — exactly as judged.

BARE means the module's OWN signals with NO downstream filter:
the judged harness called the module's get_signal on sliding
windows of the shared-featured frame (feature pipeline
"features.add_features (shared)", recorded in the row detail)
and simulated the module's absolute SL/TP. This wrapper
reproduces that evaluation exactly (``entries_for_frame``) and
adds the daemon contract (``get_signal`` evaluating ONLY the
last closed bar, returning bracket distances from the signal
bar's close; the engine re-anchors them to the fill price,
exactly as the judged simulator anchors the absolute levels to
the entry price).

WHY THE _bare NAME: the lane entrant is the BARE configuration
of the governed strategy_supertrend module — the adx_ema_bare
relationship. The wrapper does not resurrect the deleted
production module's filename: that name carries the 2026-11-11
incident-era governance (OBSERVE_ONLY parking) and a surviving
test file (tests/test_batch2_strategy_depth.py) written against
the deleted module's direct SignalResult contract; those two
tests fail on main today with ModuleNotFoundError and are NOT
modified by this task (see the PR body). The judged code inside
this wrapper is identical either way.

Governance: registered FORWARD_TEST in config_strategy.py under
the key "supertrend_bare" — the key
strategies/strategy_registry.py's governance_key_for maps this
module name to (it strips the "strategy_" prefix). Executable on
DEMO venues only (fail-closed in the registry), phase-3 forward
protocol protections (0.1% per-trade risk, 2% heat cap, 3% daily
breaker, kill criteria via measurement/forward_guard.py), fills
tagged FORWARD_TEST. It is NOT a VALIDATED entrant.

Equivalence is pinned by tests/test_fwd020_supertrend_bare_lane.py,
which re-implements the gov2 evaluation loop inline (with an
independent transcription of the judged module) and requires
identical entries on the fwd002 4h fixture slices.
"""

from __future__ import annotations

import time
from collections import namedtuple
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import SUPERTREND_BARE_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

try:  # The judged pipeline: shared features (gov2 row detail).
    import features as _features
except Exception:  # pragma: no cover - fail closed if absent
    _features = None

TIMEFRAME = str(_CFG.get("TIMEFRAME", "4h"))
BAR_SECONDS = 4 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
WINDOW = int(_CFG.get("WINDOW", 500))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.2602))
RR_RATIO = float(_CFG.get("RR_RATIO", 3.0))

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged module code, restored verbatim from the pre-cleanup blob
# (strategy_supertrend.py ba3cc800...). The only deviations from the
# blob are the names judged_get_signal / _JUDGED_OOS_WIN_RATE_PRIOR /
# _JUDGED_RR_RATIO (the wrapper owns the unprefixed names for the
# lane's own prior/RR; the judged values are unchanged: 0.266 / 3.0)
# and two placements with identical effect: _STRATEGY_TYPE is defined
# once in the wrapper header (same value, "RULE_BASED"), and the
# blob's header-level "import os" sits above BLOCK_SHORTS below.
# ---------------------------------------------------------------------------

class SignalResult(namedtuple("SignalResult", ["side", "sl", "tp", "strategy_type", "win_rate_prior", "rr_ratio"])):
    @property
    def confidence(self):
        return self.win_rate_prior


# Batch 2 (2026-11-11): shorts fighting the dominant trend were a ledger loss
# source. With this flag on (default), SELL entries require a FULL bear regime:
# close < EMA200 AND EMA50 < EMA200. A pullback that dips price under the
# EMA200 while the EMA50 still sits above it no longer counts as shortable.
import os

BLOCK_SHORTS_IN_BULL_REGIME = os.getenv("BLOCK_SHORTS_IN_BULL_REGIME", "true").strip().lower() in ("1", "true", "yes", "on")

# Honest, evidence-based priors (2026-11-11):
#   win rate 0.266 — measured on the closed-trade testnet ledger (17/64)
#   R:R 3.0        — realized avg-win/avg-loss was ~4.06:1; 3.0 is the haircut
_JUDGED_OOS_WIN_RATE_PRIOR = 0.266
_JUDGED_RR_RATIO = 3.0

# Anti-churn floor: stop/tp distances below this fraction of price are noise
# (they were getting hit inside a single candle). 0.30% floor ~= 3x the ~8 bps
# one-way futures friction x 2 sides, and wide enough to sit outside 15m noise.
MIN_BRACKET_PCT = 0.0030


def _bracket_ok(entry: float, sl: float, tp: float, side: str) -> bool:
    """True when both bracket legs clear the anti-churn minimum distance."""
    if entry <= 0:
        return False
    floor_dist = entry * MIN_BRACKET_PCT
    if side == "BUY":
        return (entry - sl) >= floor_dist and (tp - entry) >= floor_dist
    return (sl - entry) >= floor_dist and (entry - tp) >= floor_dist


def judged_get_signal(df):
    """
    Supertrend + 200 EMA + Value Pullback Strategy (honest-prior edition):
    1. Fresh Breakout: Supertrend flips Bullish + Price > 200 EMA + ADX >= 25
    2. Trend Pullback Continuation: Supertrend already Bullish + Pullback to EMA21/50
       + Bullish bounce + RSI in 40-65 zone + ADX >= 25
    Brackets: SL 2.0x ATR (floored at MIN_BRACKET_PCT of price), TP = 3R.
    Signals whose bracket sits inside the churn floor are suppressed (None).
    Returns: SignalResult
    """
    if df is None or len(df) < 50:
        return SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)

    # Required columns check
    if 'supertrend' not in df.columns or 'ema_200' not in df.columns:
        try:
            import features
            df = features.add_features(df)
        except Exception:
            return SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)

    if 'supertrend' not in df.columns:
        return SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Chop filter: skip weak markets if ADX is present
    adx = float(last.get('adx', last.get('adx_14', 0.0)))
    if 0.0 < adx < 25.0:
        return SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)

    st_now = bool(last['supertrend'])
    st_prev = bool(prev['supertrend'])
    close = float(last['close'])
    open_p = float(last['open'])
    low = float(last['low'])
    high = float(last.get('high', close))
    prev_high = float(prev.get('high', prev['close']))

    ema_200 = float(last.get('ema_200', close))
    ema_50  = float(last.get('ema_50', close))
    ema_21  = float(last.get('ema_21', last.get('ema_20', close)))
    atr     = float(last.get('atr', last.get('atr_14', close * 0.01)))
    rsi     = float(last.get('rsi', last.get('rsi_14', 50.0)))
    st_lower = float(last.get('st_lower', close - 1.5 * atr))
    st_upper = float(last.get('st_upper', close + 1.5 * atr))

    # --- 1. Fresh Trend Flip (Breakout Entry) ---
    if st_now == True and st_prev == False and close > ema_200:
        sl = max(st_lower, close - (atr * 2.0))
        risk = max(close - sl, atr * 0.8)
        tp = close + (risk * _JUDGED_RR_RATIO)
        if _bracket_ok(close, sl, tp, "BUY"):
            return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)
        return SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)

    # --- 2. Bullish Trend Continuation / Dynamic Pullback Entry ---
    # When established in an uptrend (Supertrend True for >1 bar, price above 200 EMA & EMA21 > EMA50)
    if st_now == True and st_prev == True and close > ema_200 and ema_21 >= ema_50:
        # Price dipped to touch EMA21 or EMA50 during this candle or prev candle
        pulled_back = (low <= ema_21 * 1.002 or prev['low'] <= ema_21 * 1.002)
        # Closed bullish (green candle bouncing back above EMA21)
        bullish_bounce = (close > open_p) and (close >= ema_21)
        # Healthy momentum (not overbought, resetting from support)
        rsi_healthy = (38 <= rsi <= 68)

        if pulled_back and bullish_bounce and rsi_healthy:
            sl = max(st_lower, close - (atr * 2.0))
            risk = max(close - sl, atr * 0.8)
            tp = close + (risk * _JUDGED_RR_RATIO)
            if _bracket_ok(close, sl, tp, "BUY"):
                return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)
            return SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)

    # --- 3. Fresh Bearish Trend Flip (Breakout Entry) ---
    # Regime gate: a bearish flip inside a still-bull big-picture regime (EMA50
    # above EMA200) is a pullback, not a trend change — shorts stay blocked.
    if BLOCK_SHORTS_IN_BULL_REGIME and ema_50 > ema_200:
        return SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)
    if st_now == False and st_prev == True and close < ema_200:
        sl = min(st_upper, close + (atr * 2.0))
        risk = max(sl - close, atr * 0.8)
        tp = close - (risk * _JUDGED_RR_RATIO)
        if _bracket_ok(close, sl, tp, "SELL"):
            return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)
        return SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)

    # --- 4. Bearish Trend Continuation / Dynamic Pullback Entry ---
    # Same regime gate as section 3: full bear regime required for shorts.
    if BLOCK_SHORTS_IN_BULL_REGIME and ema_50 > ema_200:
        return SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)
    # When established in a downtrend (Supertrend False for >1 bar, price below 200 EMA & EMA21 <= EMA50)
    if st_now == False and st_prev == False and close < ema_200 and ema_21 <= ema_50:
        # Price rallied to test EMA21 or EMA50 resistance during this candle or prev candle
        pulled_back = (high >= ema_21 * 0.998 or prev_high >= ema_21 * 0.998)
        # Closed bearish (red candle rejecting back down below EMA21)
        bearish_bounce = (close < open_p) and (close <= ema_21 * 1.002)
        # Healthy momentum (not oversold, resetting from resistance)
        rsi_healthy = (32 <= rsi <= 62)

        if pulled_back and bearish_bounce and rsi_healthy:
            sl = min(st_upper, close + (atr * 2.0))
            risk = max(sl - close, atr * 0.8)
            tp = close - (risk * _JUDGED_RR_RATIO)
            if _bracket_ok(close, sl, tp, "SELL"):
                return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)
            return SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)

    return SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)


# ---------------------------------------------------------------------------
# Judged evaluation (rigorous_backtest/rd2/gov2.py, bare configuration)
# ---------------------------------------------------------------------------

def _extract(res) -> Optional[Tuple[str, float, float]]:
    """(side, sl, tp) from a judged SignalResult, or None — mirroring
    rigorous_backtest/module_eval.py's _extract exactly, including
    its sl/tp positivity guard (the RD-002 row recorded exactly 1
    such unbracketed signal in 5,701 pooled trades; gov2 skipped it,
    and so does this wrapper)."""
    if res is None:
        return None
    side = res.get("side") if isinstance(res, dict) else getattr(res, "side", None)
    if side not in ("BUY", "SELL"):
        return None
    sl = res.get("sl") if isinstance(res, dict) else getattr(res, "sl", None)
    tp = res.get("tp") if isinstance(res, dict) else getattr(res, "tp", None)
    if sl is None or tp is None:
        return None
    sl_f, tp_f = float(sl), float(tp)
    if sl_f <= 0 or tp_f <= 0:
        return None
    return side, sl_f, tp_f


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str, float, float]]:
    """(bar, side, sl_dist, tp_dist) identical to the gov2 bare
    evaluation: features computed once over the frame with the
    SHARED features.add_features (the pipeline recorded for this
    row), judged get_signal on trailing <=WINDOW-bar windows, bars
    [warmup, len-2], NO signal filter. Distances are measured from
    the signal bar's close (the judged simulator anchors the
    module's absolute levels to the entry price; the engine
    re-anchors these distances to the fill)."""
    if _features is None:
        return []
    featured = _features.add_features(df)
    closes = df["close"].to_numpy(dtype=float)
    out: List[Tuple[int, str, float, float]] = []
    for i in range(warmup, len(df) - 1):
        window = featured.iloc[max(0, i - WINDOW + 1): i + 1].copy()
        ex = _extract(judged_get_signal(window))
        if ex is None:
            continue
        side, sl, tp = ex
        close_i = closes[i]
        if side == "BUY":
            out.append((i, "LONG", close_i - sl, tp - close_i))
        else:
            out.append((i, "SHORT", sl - close_i, close_i - tp))
    return out


# ---------------------------------------------------------------------------
# Daemon entry point
# ---------------------------------------------------------------------------

def _closed_frame(df: pd.DataFrame, now_s: Optional[float] = None) -> pd.DataFrame:
    """Drop still-forming trailing bars (bar open + duration > now).

    Epoch seconds are computed by timedelta division (resolution-
    independent); the index's int64 view returns its native unit
    (microseconds under pandas 3), which silently disables the
    drop when divided by 1e9 (TASK-STR-FWD-025).
    """
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    idx = df.index
    try:
        epoch = pd.Timestamp("1970-01-01", tz=idx.tz)
        opens = (idx - epoch).total_seconds().to_numpy(dtype=float)
    except Exception:
        return df
    keep = int(np.sum(opens + BAR_SECONDS <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed 4h bar; return the daemon signal dict."""
    none_signal: Dict[str, Any] = {"side": None}
    if _features is None:
        return none_signal
    try:
        if df is None or len(df) < WARMUP_BARS + 1:
            return none_signal
        frame = _closed_frame(df)
        if len(frame) < WARMUP_BARS + 1:
            return none_signal
        featured = _features.add_features(frame)
        window = featured.iloc[-WINDOW:].copy()
        ex = _extract(judged_get_signal(window))
        if ex is None:
            return none_signal
        side, sl, tp = ex
        close_last = float(frame["close"].iloc[-1])
        if side == "BUY":
            sl_dist, tp_dist = close_last - sl, tp - close_last
        else:
            sl_dist, tp_dist = sl - close_last, close_last - tp
        if sl_dist <= 0 or tp_dist <= 0:
            return none_signal
        return {
            "side": side,
            "sl_dist": sl_dist,
            "tp_dist": tp_dist,
            "win_rate_prior": WIN_RATE_PRIOR,
            "rr_ratio": RR_RATIO,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal
