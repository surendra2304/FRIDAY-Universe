"""strategy_shock_breakout — TASK-STR-FWD-003 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002 WATCHLIST: passed the mechanical
bar — expectancy>0, PF>=1.2, >=200 OOS trades, >=80% folds, holdout —
but FAILED Bonferroni multiple-testing significance at N=1,557, so it
was NOT promoted; the owner directed 2026-11-15 that near-bar
configurations be decided by real demo forward evidence instead):
shock_breakout / k1.0 @ CRYPTO30 1d — 732 pooled OOS trades,
+2.6957%/trade, PF 1.3179, win rate 0.3893, 4/5 positive folds,
max symbol share 0.109.

Governance: registered FORWARD_TEST in config_strategy.py — executable
on DEMO venues only (fail-closed in strategies/strategy_registry.py),
phase-3 forward protocol protections (1% risk cap, 3% daily breaker,
kill criteria via measurement/forward_guard.py), fills tagged
FORWARD_TEST in the Phase-2 ledger. It is NOT a VALIDATED entrant;
scorecards must never blend this lane with ichimoku/dow/sleeve.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families3.py ``sig_shock(df, 1.0, warmup)``:
a one-bar close move exceeding 1.0 x ATR(14) at the signal bar) and
the judged exit bracket (families3 BR24: SL 2.0 x ATR(14), TP 4.0 x
ATR(14); ATR exactly as rigorous_backtest/rd/common.py ``atr``).
Equivalence is pinned by tests/test_fwd003_forward_test_lane.py,
which runs this module and the rd2 harness side by side on real
historical slices and requires identical entry lists and bracket
distances.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The daemon feed's final row is
the still-forming bar; it is dropped by timestamp before evaluation.
A signal on bar i means "enter at the open of bar i+1" in the judged
simulator; live, the daemon places a market order during bar i+1 and
re-anchors the returned sl_dist/tp_dist (multiples of ATR at bar i)
to the fill price, exactly as the simulator anchors them to the
entry price. Warmup is the judged 260 bars, counted within the
evaluated frame; the ATR EWM's initialisation error after 260 bars
is negligible, so a live frame reproduces the judged series.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import SHOCK_BREAKOUT_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
SHOCK_K = float(_CFG.get("SHOCK_K", 1.0))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3893))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd2/families3.py + rd/common.py)
# ---------------------------------------------------------------------------

def atr14(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """ATR exactly as rigorous_backtest/rd/common.py ``atr``."""
    tr = pd.concat(
        [
            df["high"] - df["low"],
            abs(df["high"] - df["close"].shift(1)),
            abs(df["low"] - df["close"].shift(1)),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — sig_shock(df, 1.0, warmup) masks.

    The ATR is taken at the signal bar itself (unshifted), exactly as
    families3 computes it: the move of bar i is compared against
    k x ATR(14) at bar i.
    """
    a = atr14(df)
    up = (df["close"] - df["close"].shift(1)) > SHOCK_K * a
    dn = (df["close"].shift(1) - df["close"]) > SHOCK_K * a
    return up, dn


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families3._entries_from_masks over
    sig_shock's masks: bars [max(warmup, 1), len-2], long before short."""
    long_mask, short_mask = signal_masks(df)
    lm = long_mask.fillna(False).to_numpy()
    sm = short_mask.fillna(False).to_numpy()
    out: List[Tuple[int, str]] = []
    for i in range(max(warmup, 1), len(df) - 1):
        if lm[i]:
            out.append((i, "LONG"))
        elif sm[i]:
            out.append((i, "SHORT"))
    return out


# ---------------------------------------------------------------------------
# Daemon entry point
# ---------------------------------------------------------------------------

def _closed_frame(df: pd.DataFrame, now_s: Optional[float] = None) -> pd.DataFrame:
    """Drop still-forming trailing bars (bar open + duration > now)."""
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    idx = df.index
    try:
        opens = idx.view("int64") / 1e9
    except Exception:
        return df
    keep = int(np.sum(opens + BAR_SECONDS <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed 1d bar; return the daemon signal dict."""
    none_signal: Dict[str, Any] = {"side": None}
    try:
        if df is None or len(df) < WARMUP_BARS + 1:
            return none_signal
        frame = _closed_frame(df)
        if len(frame) < WARMUP_BARS + 1:
            return none_signal
        i = len(frame) - 1
        if i < WARMUP_BARS:
            return none_signal
        long_mask, short_mask = signal_masks(frame)
        is_long = bool(long_mask.fillna(False).iloc[i])
        is_short = bool(short_mask.fillna(False).iloc[i])
        if not (is_long or is_short):
            return none_signal
        atr = atr14(frame)
        atr_i = float(atr.iloc[i])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
        side = "BUY" if is_long else "SELL"
        return {
            "side": side,
            "sl_dist": SL_ATR * atr_i,
            "tp_dist": TP_ATR * atr_i,
            "win_rate_prior": WIN_RATE_PRIOR,
            "rr_ratio": RR_RATIO,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal
