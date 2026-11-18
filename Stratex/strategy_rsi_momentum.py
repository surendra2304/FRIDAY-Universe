"""strategy_rsi_momentum — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002 near-miss audit,
~/workspace/str-nearmiss/REPORT.md §1.4 row 67): rsi_momentum /
rsi14_55_45 @ CRYPTO30 1d — 648 pooled OOS trades, +0.913%/trade,
PF 1.1016, win rate 0.3642, 4/5 positive folds. It meets the owner's
second tier (expectancy > 0, PF >= 1.05, >= 200 OOS trades, judged
before Bonferroni) but did NOT pass the full frozen bar (Bonferroni
at programme N=3,899) — not a promotion, not VALIDATED.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections (0.1% per-trade risk on venue equity, 2% aggregate heat
cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50
closed trades or mark-to-market drawdown >5% of venue equity), fills
tagged FORWARD_TEST. Scorecards must never blend this lane with the
VALIDATED entrants.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families3.py ``sig_rsi_momentum(df, 14, 55.0,
45.0, warmup)``; RSI exactly as rigorous_backtest/rd/common.py
``rsi``) and the judged exit bracket (families3 BR24: SL 2.0 x
ATR(14), TP 4.0 x ATR(14)). Equivalence is pinned by
tests/test_fwd019_rsi_momentum_lane.py. This module is the family's
canonical core: the rsi7_60_40 and forex28 variants are thin modules
binding their own CFG dicts to the parameterised helpers here.

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
    from config_strategy import RSI_MOMENTUM_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
RSI_PERIOD = int(_CFG.get("RSI_PERIOD", 14))
RSI_HI = float(_CFG.get("RSI_HI", 55.0))
RSI_LO = float(_CFG.get("RSI_LO", 45.0))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3642))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd2/families3.py + rd/common.py)
# ---------------------------------------------------------------------------

def rsi_series(close: pd.Series, period: int) -> pd.Series:
    """RSI exactly as rigorous_backtest/rd/common.py ``rsi``."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    return 100.0 - (100.0 / (1.0 + rs))


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
    families3.sig_rsi_momentum's masks: RSI(period) crosses up through
    RSI_HI -> long; crosses down through RSI_LO -> short."""
    r = rsi_series(df["close"], int(cfg.get("RSI_PERIOD", RSI_PERIOD)))
    return (
        _cross_up(r, float(cfg.get("RSI_HI", RSI_HI))),
        _cross_down(r, float(cfg.get("RSI_LO", RSI_LO))),
    )


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    return signal_masks_cfg(df, _CFG)


def entries_for_frame_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], warmup: Optional[int] = None
) -> List[Tuple[int, str]]:
    """Entry list identical to families3._entries_from_masks over
    sig_rsi_momentum's masks: bars [max(warmup, 1), len-2], long
    before short."""
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
# Daemon entry point
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
