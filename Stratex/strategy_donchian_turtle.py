"""strategy_donchian_turtle — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002, near-miss second tier per the
2026-11-18 audit ~/workspace/str-nearmiss/REPORT.md S1.4 row 3):
donchian_turtle / n55_b26 @ CRYPTO30 1d — 298 pooled OOS trades,
+5.614%/trade, PF 1.6502, win rate 0.3523, 4/5 positive folds,
PF @2x costs 1.6246. It did NOT pass the full frozen bar (Bonferroni
at programme N=3,899) — not a promotion, not VALIDATED. This stream
is also a member of the live Stage-C sleeve book under its sleeve
key — a distinct judged object; records are never blended.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections, fills tagged FORWARD_TEST.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families2.py ``sig_donchian(df, 55, warmup)``)
and the judged exit bracket (families2 BR26: SL 2.0 x ATR(14),
TP 6.0 x ATR(14); ATR exactly as rigorous_backtest/rd/common.py
``atr``). Equivalence is pinned by
tests/test_fwd019_donchian_turtle_lane.py, which runs this module
and the rd2 harness side by side on real historical slices and
requires identical entry lists.

This module is also the CORE for the donchian_turtle variant family:
the thin modules strategy_donchian_turtle_<variant>.py import its
parameterised helpers and bind their own CFG dicts. Variant exit
specs differ (BR24 / BR26 brackets and the TRAIL spec: SL 2.0 x
ATR(14) with a 2.5 x ATR(14) trailing stop and NO fixed take-profit,
rigorous_backtest/rd/fastsim.py); TRAIL variants return tp_dist=None
— see their registry reasons for the daemon trailing-exit limitation.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The daemon feed's final row is
the still-forming bar; it is dropped by timestamp before evaluation.
A signal on bar i means "enter at the open of bar i+1" in the judged
simulator; live, the daemon places a market order during bar i+1 and
re-anchors the returned sl_dist/tp_dist (multiples of ATR at bar i)
to the fill price. Warmup is the judged 260 bars.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import DONCHIAN_TURTLE_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600 if TIMEFRAME == "1d" else 4 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
CHANNEL_N = int(_CFG.get("CHANNEL_N", 55))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
_TP = _CFG.get("TP_ATR", 6.0)
TP_ATR = None if _TP is None else float(_TP)
TRAIL_ATR = float(_CFG.get("TRAIL_ATR", 2.5))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3523))
RR_RATIO = (TP_ATR / SL_ATR) if TP_ATR else None

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd2/families2.py + rd/common.py)
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
    """(long_mask, short_mask) — families2.sig_donchian(df, n, warmup):
    close above the prior-n-bar highest high / below the lowest low."""
    n = int(cfg.get("CHANNEL_N", CHANNEL_N))
    hi = df["high"].rolling(n).max().shift(1)
    lo = df["low"].rolling(n).min().shift(1)
    return df["close"] > hi, df["close"] < lo


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    return signal_masks_cfg(df, _CFG)


def entries_for_frame_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families2._entries over sig_donchian's
    masks: bars [warmup, len-1] inclusive, long before short."""
    long_mask, short_mask = signal_masks_cfg(df, cfg)
    lm = long_mask.fillna(False).to_numpy(dtype=bool)
    sm = short_mask.fillna(False).to_numpy(dtype=bool)
    out: List[Tuple[int, str]] = []
    for i in range(warmup, len(df)):
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

def _bar_seconds(cfg: Dict[str, Any]) -> int:
    return 24 * 3600 if str(cfg.get("TIMEFRAME", "1d")) == "1d" else 4 * 3600


def _closed_frame(
    df: pd.DataFrame,
    bar_seconds: int = BAR_SECONDS,
    now_s: Optional[float] = None,
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


def get_signal_cfg(df: pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate the last closed bar under ``cfg``; daemon signal dict."""
    none_signal: Dict[str, Any] = {"side": None}
    try:
        warmup = int(cfg.get("WARMUP_BARS", WARMUP_BARS))
        if df is None or len(df) < warmup + 1:
            return none_signal
        frame = _closed_frame(df, _bar_seconds(cfg))
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
        atr = atr14(frame)
        atr_i = float(atr.iloc[i])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
        sl_atr = float(cfg.get("SL_ATR", SL_ATR))
        tp = cfg.get("TP_ATR", TP_ATR)
        side = "BUY" if is_long else "SELL"
        return {
            "side": side,
            "sl_dist": sl_atr * atr_i,
            "tp_dist": (float(tp) * atr_i) if tp is not None else None,
            "win_rate_prior": float(cfg.get("OOS_WIN_RATE", WIN_RATE_PRIOR)),
            "rr_ratio": (float(tp) / sl_atr) if tp is not None else None,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed bar; return the daemon signal dict."""
    return get_signal_cfg(df, _CFG)
