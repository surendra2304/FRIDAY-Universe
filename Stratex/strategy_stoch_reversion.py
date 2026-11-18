"""strategy_stoch_reversion — TASK-STR-FWD-019 FORWARD-TEST lane
entrant (canonical core module for the stoch_reversion family).

Judged configuration (TASK-STR-RD-002 near-miss audit,
~/workspace/str-nearmiss/REPORT.md §1.4 row 12): stoch_reversion /
k14_raw @ FOREX28 1d — 365 pooled OOS trades, +0.286%/trade,
PF 1.2623, win rate 0.3863, 4/5 positive folds, PF @2x costs 1.1796.
The BEST forex row in the audit, and a measured member of the
low-correlation forex28 3-stream combo (mean correlation 0.083,
audit §4). It meets the owner's second tier (expectancy > 0,
PF >= 1.05, >= 200 OOS trades, pre-Bonferroni) but did NOT pass the
full frozen bar (Bonferroni at programme N=3,899) — not a promotion,
not VALIDATED.

Governance: registered FORWARD_TEST in config_strategy.py with
forward_venues ["oanda_practice"] — discoverable by the governed
OANDA runner; execution rides that runner (a separate PR), NOT the
Binance daemon. Phase-3 forward protocol protections (0.1%
per-trade risk on venue equity, 2% aggregate heat cap, 3% daily
breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or
mark-to-market drawdown >5% of venue equity), fills tagged
FORWARD_TEST. Scorecards must never blend this lane with the
VALIDATED entrants.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families3.py ``sig_stoch(df, filtered=False,
warmup)``: %K over the trailing 14-bar window INCLUDING the current
bar, smoothed by SMA(3); long on %K crossing up through 20, short on
crossing down through 80) and the judged exit bracket (families3
BR24: SL 2.0 x ATR(14), TP 4.0 x ATR(14)). Equivalence is pinned by
tests/test_fwd019_stoch_reversion_lane.py. Per the wave-2 slice this
forex cell is the family's canonical core even though its lane is
OANDA: the k14_filt forex variant and the k14_raw crypto variant are
thin modules binding their own CFG dicts to the helpers here.

Live-evaluation contract: ``get_signal(df)`` evaluates ONLY the last
CLOSED bar (the daemon/runner feed's final, still-forming row is
dropped by timestamp). A signal on bar i means "enter at the open of
bar i+1" in the judged simulator; live, the order is placed during
bar i+1 and the returned sl_dist/tp_dist (multiples of ATR at bar i)
are re-anchored to the fill price. Warmup is the judged 260 bars.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import STOCH_REVERSION_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
STOCH_PERIOD = int(_CFG.get("STOCH_PERIOD", 14))
STOCH_SMOOTH = int(_CFG.get("STOCH_SMOOTH", 3))
STOCH_LO = float(_CFG.get("STOCH_LO", 20.0))
STOCH_HI = float(_CFG.get("STOCH_HI", 80.0))
FILTERED = bool(_CFG.get("FILTERED", False))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3863))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd2/families3.py + rd/common.py)
# ---------------------------------------------------------------------------

def _sma(series: pd.Series, w: int) -> pd.Series:
    return series.rolling(w).mean()


def _ema(series: pd.Series, span: int) -> pd.Series:
    """EMA exactly as rigorous_backtest/rd/common.py ``ema``."""
    return series.ewm(span=span, adjust=False).mean()


def _cross_up(a: pd.Series, b) -> pd.Series:
    return (a > b) & (a.shift(1) <= (b.shift(1) if hasattr(b, "shift") else b))


def _cross_down(a: pd.Series, b) -> pd.Series:
    return (a < b) & (a.shift(1) >= (b.shift(1) if hasattr(b, "shift") else b))


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


def signal_masks_cfg(df: pd.DataFrame, cfg: Dict[str, Any]) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) for an explicit judged configuration —
    families3.sig_stoch's masks: %K(14, incl. current bar) smoothed
    SMA(3); cross up through 20 -> long, cross down through 80 ->
    short; the filtered variant additionally requires close on the
    EMA(200) side of the trade."""
    hh = df["high"].rolling(int(cfg.get("STOCH_PERIOD", STOCH_PERIOD))).max()
    ll = df["low"].rolling(int(cfg.get("STOCH_PERIOD", STOCH_PERIOD))).min()
    rng = (hh - ll).replace(0, np.nan)
    k = _sma(100.0 * (df["close"] - ll) / rng, int(cfg.get("STOCH_SMOOTH", STOCH_SMOOTH)))
    up = _cross_up(k, float(cfg.get("STOCH_LO", STOCH_LO)))
    dn = _cross_down(k, float(cfg.get("STOCH_HI", STOCH_HI)))
    if bool(cfg.get("FILTERED", FILTERED)):
        e200 = _ema(df["close"], 200)
        up = up & (df["close"] > e200)
        dn = dn & (df["close"] < e200)
    return up, dn


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    return signal_masks_cfg(df, _CFG)


def entries_for_frame_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], warmup: Optional[int] = None
) -> List[Tuple[int, str]]:
    """Entry list identical to families3._entries_from_masks over
    sig_stoch's masks: bars [max(warmup, 1), len-2], long before
    short."""
    w = int(cfg.get("WARMUP_BARS", WARMUP_BARS)) if warmup is None else warmup
    long_mask, short_mask = signal_masks_cfg(df, cfg)
    lm = long_mask.fillna(False).to_numpy()
    sm = short_mask.fillna(False).to_numpy()
    out: List[Tuple[int, str]] = []
    for i in range(max(w, 1), len(df) - 1):
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
# Daemon / runner entry point
# ---------------------------------------------------------------------------

def _closed_frame(
    df: pd.DataFrame, bar_seconds: int = BAR_SECONDS, now_s: Optional[float] = None
) -> pd.DataFrame:
    """Drop still-forming trailing bars (bar open + duration > now).

    Epoch seconds are computed by timedelta division (resolution-
    independent); the index's int64 view returns its native unit
    (microseconds under pandas 3), which silently disables the
    drop when divided by 1e9 (fixed fleet-wide, TASK-STR-FWD-025)."""
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    idx = df.index
    try:
        epoch = pd.Timestamp("1970-01-01", tz="UTC")
        opens = (idx - epoch).total_seconds().to_numpy(dtype=float)
    except Exception:
        return df
    keep = int(np.sum(opens + bar_seconds <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def get_signal_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], bar_seconds: int = BAR_SECONDS
) -> Dict[str, Any]:
    """Evaluate the last closed bar under an explicit configuration."""
    none_signal: Dict[str, Any] = {"side": None}
    try:
        warmup = int(cfg.get("WARMUP_BARS", WARMUP_BARS))
        if df is None or len(df) < warmup + 1:
            return none_signal
        frame = _closed_frame(df, bar_seconds)
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
        sl_atr = float(cfg.get("SL_ATR", SL_ATR))
        tp_atr = float(cfg.get("TP_ATR", TP_ATR))
        return {
            "side": "BUY" if is_long else "SELL",
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
    return get_signal_cfg(df, _CFG, BAR_SECONDS)
