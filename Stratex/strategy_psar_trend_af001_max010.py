"""strategy_psar_trend_af001_max010 — TASK-STR-FWD-019 FORWARD-TEST
lane entrant (psar_trend family core; registry key per the task's
key slug psar_trend_af001_max010).

Judged configuration (TASK-STR-RD-002 near-miss, second tier per the
2026-11-18 audit ~/workspace/str-nearmiss/REPORT.md S1.4: OOS
expectancy > 0, PF >= 1.05, >= 200 OOS trades, judged BEFORE the
Bonferroni correction; it did NOT pass the full frozen bar —
Bonferroni at programme N=3,899 — so it is NOT promoted and NOT
VALIDATED; the owner directed 2026-11-18 that ALL actionable
near-miss candidates be forward-tested on demo):
psar_trend / af0.01_max0.10 @ CRYPTO30 1d — 648 pooled OOS trades,
+1.828%/trade, PF 1.2165, win rate 0.3765, 3/5 positive folds,
PF @2x costs 1.1957.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections (0.1% per-trade risk on venue equity, 2% heat cap, 3%
daily breaker, kill criteria via measurement/forward_guard.py),
fills tagged FORWARD_TEST in the Phase-2 ledger. Scorecards must
never blend this lane with ichimoku/dow/sleeve.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families3.py ``_psar_flip_entries(df, 0.01,
0.10, warmup)``) and the judged exit bracket (families3 BR24:
SL 2.0 x ATR(14), TP 4.0 x ATR(14); ATR exactly as
rigorous_backtest/rd/common.py ``atr``). PSAR IS STATEFUL: the SAR
state machine (trend, SAR, extreme point, acceleration factor) is
computed over the WHOLE frame from bar 0 in ``psar_series`` — never
an incremental approximation — and entries are exactly the bars
where the trend flips, exactly as the harness records them.
Equivalence is pinned by tests/test_fwd019_psar_lane.py.

This module is the family core: it also exposes the parameterised
helpers (``signal_masks_cfg`` / ``entries_for_frame_cfg`` /
``get_signal_cfg``) that the thin variant module
(strategy_psar_trend_af002_max020.py) binds to its own judged CFG.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The daemon feed's final row is
the still-forming bar; it is dropped by timestamp before evaluation.
A signal on bar i means "enter at the open of bar i+1" in the judged
simulator; live, the daemon places a market order during bar i+1 and
re-anchors the returned sl_dist/tp_dist (multiples of ATR at bar i)
to the fill price. Warmup is the judged 260 bars
(families2.warmup_for), counted within the evaluated frame; because
the SAR recursion starts at bar 0 of the evaluated frame exactly as
in the harness, a live frame reproduces the judged series.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import PSAR_TREND_AF001_MAX010_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
AF_STEP = float(_CFG.get("AF_STEP", 0.01))
AF_MAX = float(_CFG.get("AF_MAX", 0.10))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3765))
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


def psar_series(
    df: pd.DataFrame, step: float, max_af: float
) -> Tuple[np.ndarray, np.ndarray]:
    """(trend, sar) arrays — the families3._psar_flip_entries state
    machine computed over the WHOLE frame, line for line: initial
    trend from close[1] vs close[0], SAR clamped against the prior
    two bars' extremes, flip resets SAR to the prior extreme point
    and AF to step, new extremes raise AF by step up to max_af."""
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    n = len(df)
    trend = np.zeros(n, dtype=int)
    sar = np.full(n, np.nan)
    if n < 3:
        return trend, sar
    t = 1 if close[1] >= close[0] else -1
    s = low[0] if t == 1 else high[0]
    ep = high[0] if t == 1 else low[0]
    af = step
    trend[0] = t
    sar[0] = s
    for i in range(1, n):
        s = s + af * (ep - s)
        if t == 1:
            s = min(s, low[i - 1], low[max(0, i - 2)])
            if low[i] < s:
                t = -1
                s = ep
                ep = low[i]
                af = step
            elif high[i] > ep:
                ep = high[i]
                af = min(af + step, max_af)
        else:
            s = max(s, high[i - 1], high[max(0, i - 2)])
            if high[i] > s:
                t = 1
                s = ep
                ep = high[i]
                af = step
            elif low[i] < ep:
                ep = low[i]
                af = min(af + step, max_af)
        sar[i] = s
        trend[i] = t
    return trend, sar


def signal_masks_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any]
) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask): a bar is a long (short) entry iff the
    PSAR trend flips to +1 (-1) on that bar."""
    trend, _sar = psar_series(
        df,
        float(cfg.get("AF_STEP", AF_STEP)),
        float(cfg.get("AF_MAX", AF_MAX)),
    )
    prev = np.concatenate([[0], trend[:-1]])
    long_np = (trend == 1) & (prev == -1)
    short_np = (trend == -1) & (prev == 1)
    return (
        pd.Series(long_np, index=df.index),
        pd.Series(short_np, index=df.index),
    )


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — _psar_flip_entries(0.01, 0.10) flips."""
    return signal_masks_cfg(df, _CFG)


def entries_for_frame_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], warmup: int
) -> List[Tuple[int, str]]:
    """Entry list identical to families3._psar_flip_entries: trend
    flips at bars i with warmup <= i < len-1, in bar order."""
    long_mask, short_mask = signal_masks_cfg(df, cfg)
    lm = long_mask.fillna(False).to_numpy()
    sm = short_mask.fillna(False).to_numpy()
    out: List[Tuple[int, str]] = []
    for i in range(max(warmup, 1), len(df) - 1):
        if lm[i]:
            out.append((i, "LONG"))
        elif sm[i]:
            out.append((i, "SHORT"))
    return out


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    return entries_for_frame_cfg(df, _CFG, warmup)


# ---------------------------------------------------------------------------
# Daemon entry point
# ---------------------------------------------------------------------------

def _closed_frame_s(
    df: pd.DataFrame, bar_seconds: int, now_s: Optional[float] = None
) -> pd.DataFrame:
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
    keep = int(np.sum(opens + bar_seconds <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def _closed_frame(df: pd.DataFrame, now_s: Optional[float] = None) -> pd.DataFrame:
    return _closed_frame_s(df, BAR_SECONDS, now_s)


def get_signal_cfg(df: pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate the last closed bar under ``cfg``; daemon signal dict."""
    none_signal: Dict[str, Any] = {"side": None}
    try:
        warmup = int(cfg.get("WARMUP_BARS", WARMUP_BARS))
        bar_seconds = 4 * 3600 if str(cfg.get("TIMEFRAME", TIMEFRAME)) == "4h" else 24 * 3600
        if df is None or len(df) < warmup + 1:
            return none_signal
        frame = _closed_frame_s(df, bar_seconds)
        if len(frame) < warmup + 1:
            return none_signal
        i = len(frame) - 1
        if i < warmup:
            return none_signal
        long_mask, short_mask = signal_masks_cfg(frame, cfg)
        is_long = bool(long_mask.fillna(False).iloc[i])
        is_short = bool(short_mask.fillna(False).iloc[i])
        if not (is_long or is_short):
            return none_signal
        atr = atr14(frame, int(cfg.get("ATR_PERIOD", ATR_PERIOD)))
        atr_i = float(atr.iloc[i])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
        side = "BUY" if is_long else "SELL"
        sl_atr = float(cfg.get("SL_ATR", SL_ATR))
        tp_atr = float(cfg.get("TP_ATR", TP_ATR))
        return {
            "side": side,
            "sl_dist": sl_atr * atr_i,
            "tp_dist": tp_atr * atr_i,
            "win_rate_prior": float(cfg.get("OOS_WIN_RATE", WIN_RATE_PRIOR)),
            "rr_ratio": tp_atr / sl_atr,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed 1d bar; return the daemon signal dict."""
    return get_signal_cfg(df, _CFG)
