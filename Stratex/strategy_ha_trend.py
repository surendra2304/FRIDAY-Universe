"""strategy_ha_trend — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002 near-miss, second tier per the
2026-11-18 audit ~/workspace/str-nearmiss/REPORT.md S1.4: OOS
expectancy > 0, PF >= 1.05, >= 200 OOS trades, judged BEFORE the
Bonferroni correction; it did NOT pass the full frozen bar —
Bonferroni at programme N=3,899 — so it is NOT promoted and NOT
VALIDATED; the owner directed 2026-11-18 that ALL actionable
near-miss candidates be forward-tested on demo):
ha_trend / two_candle @ CRYPTO30 1d — 775 pooled OOS trades,
+1.671%/trade, PF 1.1878, win rate 0.3639, 3/5 positive folds,
PF @2x costs 1.1682.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections (0.1% per-trade risk on venue equity, 2% heat cap, 3%
daily breaker, kill criteria via measurement/forward_guard.py),
fills tagged FORWARD_TEST in the Phase-2 ledger. Scorecards must
never blend this lane with ichimoku/dow/sleeve.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families3.py ``sig_ha(df, True, warmup)``)
and the judged exit bracket (families3 BR24: SL 2.0 x ATR(14),
TP 4.0 x ATR(14); ATR exactly as rigorous_backtest/rd/common.py
``atr``). Heikin-Ashi candles are RECURSIVE — HA-open depends on the
prior HA bar — so ``ha_series`` computes the recursion from the
frame start exactly as the harness does; a two_candle entry needs
TWO consecutive qualifying HA candles (bull: HA-close > HA-open
with HA-open == HA-low, i.e. no lower wick; bear mirrored).
Equivalence is pinned by tests/test_fwd019_ha_trend_lane.py.

This module is the family core: it also exposes the parameterised
helpers (``signal_masks_cfg`` / ``entries_for_frame_cfg`` /
``get_signal_cfg``) that the thin variant modules
(strategy_ha_trend_*.py) bind to their own judged CFG dicts.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The daemon feed's final row is
the still-forming bar; it is dropped by timestamp before evaluation.
A signal on bar i means "enter at the open of bar i+1" in the judged
simulator; live, the daemon places a market order during bar i+1 and
re-anchors the returned sl_dist/tp_dist (multiples of ATR at bar i)
to the fill price. Warmup is the judged 260 bars
(families2.warmup_for), counted within the evaluated frame; the HA
recursion starts at bar 0 of the evaluated frame exactly as in the
harness, so a live frame reproduces the judged series.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import HA_TREND_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
TWO_CANDLE = bool(_CFG.get("TWO_CANDLE", True))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3639))
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


def ha_series(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(hao, hah, hal, hac) — families3.sig_ha's Heikin-Ashi
    recursion, line for line: HA-close = mean(OHLC); HA-open[0] =
    (open[0]+close[0])/2; HA-open[i] = (HA-open[i-1]+HA-close[i-1])/2;
    HA-high/low = max/min of (raw high/low, HA-open, HA-close)."""
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    n = len(df)
    hac = (o + h + low + c) / 4.0
    hao = np.empty(n)
    if n:
        hao[0] = (o[0] + c[0]) / 2.0
        for i in range(1, n):
            hao[i] = (hao[i - 1] + hac[i - 1]) / 2.0
    hah = np.maximum.reduce([h, hao, hac]) if n else h
    hal = np.minimum.reduce([low, hao, hac]) if n else low
    return hao, hah, hal, hac


def _bull_bear(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    hao, hah, hal, hac = ha_series(df)
    bull = (hac > hao) & (np.abs(hao - hal) < 1e-12)
    bear = (hac < hao) & (np.abs(hao - hah) < 1e-12)
    return bull, bear


def signal_masks_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any]
) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) for a judged ha cfg: two_candle
    requires the qualifying candle on bar i AND bar i-1."""
    bull, bear = _bull_bear(df)
    two = bool(cfg.get("TWO_CANDLE", TWO_CANDLE))
    if two:
        long_np = bull & np.concatenate([[False], bull[:-1]])
        short_np = bear & np.concatenate([[False], bear[:-1]])
    else:
        long_np, short_np = bull, bear
    return (
        pd.Series(long_np, index=df.index),
        pd.Series(short_np, index=df.index),
    )


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — sig_ha(df, True, warmup) masks."""
    return signal_masks_cfg(df, _CFG)


def entries_for_frame_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], warmup: int
) -> List[Tuple[int, str]]:
    """Entry list identical to families3.sig_ha: bars
    [max(warmup, 2), len-2], long before short."""
    long_mask, short_mask = signal_masks_cfg(df, cfg)
    lm = long_mask.fillna(False).to_numpy()
    sm = short_mask.fillna(False).to_numpy()
    out: List[Tuple[int, str]] = []
    for i in range(max(warmup, 2), len(df) - 1):
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
    """Drop still-forming trailing bars (bar open + duration > now)."""
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    idx = df.index
    try:
        opens = idx.view("int64") / 1e9
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
