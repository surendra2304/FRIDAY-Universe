"""strategy_turtle2 — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002, near-miss second tier per the
2026-11-18 audit ~/workspace/str-nearmiss/REPORT.md S1.4 row 18):
turtle2 / n55_trail_filt @ CRYPTO30 1d — 400 pooled OOS trades,
+1.170%/trade, PF 1.2037, win rate 0.3725, 3/5 positive folds,
PF @2x costs 1.1727. It did NOT pass the full frozen bar (Bonferroni
at programme N=3,899) — not a promotion, not VALIDATED.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections, fills tagged FORWARD_TEST.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families2.py ``sig_turtle2(df, 55, True,
warmup)``): the donchian_turtle n=55 channel breakout filtered by
EMA(200) (longs only above, shorts only below; EMA exactly as
rigorous_backtest/rd/common.py ``ema``). The judged exit spec is
families2 TRAIL: SL 2.0 x ATR(14) with a 2.5 x ATR(14) trailing stop
and NO fixed take-profit (rigorous_backtest/rd/fastsim.py), so
``get_signal`` returns tp_dist=None — the daemon's execution path
requires a fixed TP distance, so this config's trailing exit is NOT
faithfully executable until the daemon gains trailing-exit support;
do NOT allowlist this module before that support exists (see the
registry reason). Equivalence is pinned by
tests/test_fwd019_donchian_turtle_lane.py against the rd2 harness.

NOTE: turtle2's UNFILTERED trail variants (n20_trail, n55_trail)
produce trade streams identical to donchian_turtle's trail variants
(audit S1.4 dup flags); they are wired ONCE under the donchian_turtle
keys and are NOT separately wired here. Only the trail_filt streams
are distinct, and they live in this family.

This module is also the CORE for the turtle2 trail_filt variants:
the thin modules strategy_turtle2_<variant>.py import its
parameterised helpers and bind their own CFG dicts.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar (the still-forming final row is
dropped by timestamp). A signal on bar i means "enter at the open
of bar i+1" in the judged simulator. Warmup is the judged 260 bars.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import TURTLE2_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600 if TIMEFRAME == "1d" else 4 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
CHANNEL_N = int(_CFG.get("CHANNEL_N", 55))
EMA_PERIOD = int(_CFG.get("EMA_PERIOD", 200))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TRAIL_ATR = float(_CFG.get("TRAIL_ATR", 2.5))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3725))
RR_RATIO = None  # judged TRAIL spec: no fixed take-profit, no fixed RR

_STRATEGY_TYPE = "RULE_BASED"
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


def _ema(series: pd.Series, span: int) -> pd.Series:
    """EMA exactly as rigorous_backtest/rd/common.py ``ema``."""
    return series.ewm(span=span, adjust=False).mean()


def signal_masks_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any]
) -> Tuple[pd.Series, pd.Series]:
    """Donchian channel masks (families2.sig_donchian) for cfg's n."""
    n = int(cfg.get("CHANNEL_N", CHANNEL_N))
    hi = df["high"].rolling(n).max().shift(1)
    lo = df["low"].rolling(n).min().shift(1)
    return df["close"] > hi, df["close"] < lo


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    return signal_masks_cfg(df, _CFG)


def entries_for_frame_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families2.sig_turtle2(df, n, filt, w):
    donchian entries, then (trail_filt) the EMA(200) trend filter."""
    long_mask, short_mask = signal_masks_cfg(df, cfg)
    lm = long_mask.fillna(False).to_numpy(dtype=bool)
    sm = short_mask.fillna(False).to_numpy(dtype=bool)
    entries: List[Tuple[int, str]] = []
    for i in range(warmup, len(df)):
        if lm[i]:
            entries.append((i, "LONG"))
        elif sm[i]:
            entries.append((i, "SHORT"))
    if cfg.get("USE_FILTER", True):
        e200 = _ema(df["close"], int(cfg.get("EMA_PERIOD", EMA_PERIOD)))
        close = df["close"].to_numpy()
        ev = e200.to_numpy()
        entries = [
            (i, s)
            for (i, s) in entries
            if (s == "LONG" and close[i] > ev[i])
            or (s == "SHORT" and close[i] < ev[i])
        ]
    return entries


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
        entries = entries_for_frame_cfg(frame, cfg, warmup)
        side_at_last = dict()
        for bar, s in entries:
            side_at_last[bar] = s
        if i not in side_at_last:
            return none_signal
        atr = atr14(frame)
        atr_i = float(atr.iloc[i])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
        sl_atr = float(cfg.get("SL_ATR", SL_ATR))
        return {
            "side": "BUY" if side_at_last[i] == "LONG" else "SELL",
            "sl_dist": sl_atr * atr_i,
            "tp_dist": None,  # judged TRAIL spec: no fixed take-profit
            "win_rate_prior": float(cfg.get("OOS_WIN_RATE", WIN_RATE_PRIOR)),
            "rr_ratio": None,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed bar; return the daemon signal dict."""
    return get_signal_cfg(df, _CFG)
