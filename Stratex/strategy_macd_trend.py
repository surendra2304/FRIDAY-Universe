"""strategy_macd_trend — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002, near-miss re-audit
~/workspace/str-nearmiss/REPORT.md §1.4 row 6): macd_trend / hist_raw
@ CRYPTO30 1d — 369 pooled OOS trades, +5.840%/trade, PF 1.5522, win
rate 0.4201, 2/5 positive folds (flagged weak), PF @2x costs 1.5330 —
the most cost-robust row in the audit. It meets the owner's second
tier (expectancy > 0, PF >= 1.05, >= 200 OOS trades, judged before
Bonferroni) but did NOT pass the full frozen bar (Bonferroni at
programme N=3,899) — not a promotion, not VALIDATED. This stream is
also a member of the live Stage-C sleeve book under its sleeve key —
a distinct judged object; records are never blended.

Governance: registered FORWARD_TEST in config_strategy.py — executable
on DEMO venues only (fail-closed in strategies/strategy_registry.py),
phase-3 forward protocol protections (0.1% risk cap, 3% daily breaker,
kill criteria via measurement/forward_guard.py), fills tagged
FORWARD_TEST in the Phase-2 ledger. Scorecards must never blend this
lane with ichimoku/dow/sleeve.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families3.py ``sig_macd(df, False, warmup)``:
MACD(12,26) histogram zero-cross, unfiltered) and the judged exit
bracket (families3 BR25: SL 2.5 x ATR(14), TP 5.0 x ATR(14); EMA and
ATR exactly as rigorous_backtest/rd/common.py ``ema`` / ``atr``).
Equivalence is pinned by tests/test_fwd019_macd_lane.py, which runs
this module and the rd2 harness side by side on real historical
slices and requires identical entry lists.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The daemon feed's final row is
the still-forming bar; it is dropped by timestamp before evaluation.
A signal on bar i means "enter at the open of bar i+1" in the judged
simulator; live, the daemon places a market order during bar i+1 and
re-anchors the returned sl_dist/tp_dist (multiples of ATR at bar i)
to the fill price, exactly as the simulator anchors them to the
entry price. Warmup is the judged 260 bars, counted within the
evaluated frame; the EMA/ATR EWMs' initialisation error after 260
bars is negligible, so a live frame reproduces the judged series.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import MACD_TREND_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
MACD_FAST = int(_CFG.get("MACD_FAST", 12))
MACD_SLOW = int(_CFG.get("MACD_SLOW", 26))
MACD_SIGNAL = int(_CFG.get("MACD_SIGNAL", 9))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.5))
TP_ATR = float(_CFG.get("TP_ATR", 5.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.4201))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd2/families3.py + rd/common.py)
# ---------------------------------------------------------------------------

def _ema(series: pd.Series, span: int) -> pd.Series:
    """EMA exactly as rigorous_backtest/rd/common.py ``ema``."""
    return series.ewm(span=span, adjust=False).mean()


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
    """(long_mask, short_mask) — sig_macd(df, False, warmup): the
    MACD histogram crossing zero, with NO EMA(200) filter (hist_raw)."""
    macd = _ema(df["close"], MACD_FAST) - _ema(df["close"], MACD_SLOW)
    hist = macd - _ema(macd, MACD_SIGNAL)
    up = (hist > 0) & (hist.shift(1) <= 0)
    dn = (hist < 0) & (hist.shift(1) >= 0)
    return up, dn


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families3._entries_from_masks over
    sig_macd's masks: bars [max(warmup, 1), len-2], long before short."""
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
