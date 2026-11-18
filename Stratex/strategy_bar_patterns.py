"""strategy_bar_patterns — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002 near-miss, second tier per the
2026-11-18 audit ~/workspace/str-nearmiss/REPORT.md S1.4: OOS
expectancy > 0, PF >= 1.05, >= 200 OOS trades, judged BEFORE the
Bonferroni correction; it did NOT pass the full frozen bar —
Bonferroni at programme N=3,899 — so it is NOT promoted and NOT
VALIDATED; the owner directed 2026-11-18 that ALL actionable
near-miss candidates be forward-tested on demo):
bar_patterns / engulfing @ CRYPTO30 1d — 548 pooled OOS trades,
+1.587%/trade, PF 1.1743, win rate 0.3850, 3/5 positive folds,
PF @2x costs 1.1555.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections (0.1% per-trade risk on venue equity, 2% heat cap, 3%
daily breaker, kill criteria via measurement/forward_guard.py),
fills tagged FORWARD_TEST in the Phase-2 ledger. Scorecards must
never blend this lane with ichimoku/dow/sleeve.

The signal core is a line-faithful port of the judged implementations
(rigorous_backtest/rd2/families3.py ``sig_engulfing(df, warmup)`` —
the canonical variant — and ``sig_inside_bar(df, warmup)``) and the
judged exit bracket (families3 BR24: SL 2.0 x ATR(14), TP 4.0 x
ATR(14); ATR exactly as rigorous_backtest/rd/common.py ``atr``).
Equivalence is pinned by tests/test_fwd019_bar_patterns_lane.py.

This module is the family core: it also exposes the parameterised
helpers (``signal_masks_cfg`` / ``entries_for_frame_cfg`` /
``get_signal_cfg``) that the thin variant module
(strategy_bar_patterns_inside_bar_4h.py) binds to its own judged CFG.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The daemon feed's final row is
the still-forming bar; it is dropped by timestamp before evaluation.
A signal on bar i means "enter at the open of bar i+1" in the judged
simulator; live, the daemon places a market order during bar i+1 and
re-anchors the returned sl_dist/tp_dist (multiples of ATR at bar i)
to the fill price. Warmup is the judged 260 bars
(families2.warmup_for), counted within the evaluated frame.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import BAR_PATTERNS_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
PATTERN = str(_CFG.get("PATTERN", "engulfing"))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3850))
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


def signal_masks_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any]
) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) for a judged bar_patterns cfg.

    engulfing (families3.sig_engulfing): bull = bull candle whose
    body fully engulfs the prior bear candle's body; bear mirrored.
    inside_bar (families3.sig_inside_bar): bar i-1 inside bar i-2
    and close of bar i breaks bar i-2's high (long) / low (short).
    """
    pattern = str(cfg.get("PATTERN", PATTERN))
    if pattern == "inside_bar":
        h = df["high"]
        low = df["low"]
        c = df["close"]
        inside_prev = (h.shift(1) < h.shift(2)) & (low.shift(1) > low.shift(2))
        up = inside_prev & (c > h.shift(2))
        dn = inside_prev & (c < low.shift(2))
        return up, dn
    o = df["open"]
    c = df["close"]
    po, pc = o.shift(1), c.shift(1)
    bull = (c > o) & (pc < po) & (c > po) & (o < pc)
    bear = (c < o) & (pc > po) & (c < po) & (o > pc)
    return bull, bear


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — sig_engulfing(df, warmup) masks."""
    return signal_masks_cfg(df, _CFG)


def entries_for_frame_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], warmup: int
) -> List[Tuple[int, str]]:
    """Entry list identical to families3._entries_from_masks over the
    pattern masks: bars [max(warmup, 1), len-2], long before short."""
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
