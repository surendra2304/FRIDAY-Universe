"""strategy_bollinger_trend_p20 — TASK-STR-FWD-018 FORWARD-TEST
lane, wave 1 (parameter variant of the FWD-003 bollinger_trend
module).

Judged configuration (TASK-STR-RD-002, near-miss re-audit
2026-11-18): bollinger_trend / p20_sd2.0 @ CRYPTO30 1d — 632 pooled
OOS trades, expectancy +1.2651%/trade, PF 1.1474, win rate 0.3513,
3/5 positive folds, max symbol share 0.103 (grid_rows pooled_oos:
bollinger_trend__p20_sd2.0__crypto30__1d). It passes the owner's
second-tier demo-admission bar (expectancy>0, PF>=1.05, >=200 OOS
trades, pre-Bonferroni) but NOT the frozen promotion bar (PF>=1.2,
>=4/5 folds, Bonferroni, holdout), so it trades demo-only under the
forward protocol until its own forward record judges it.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families3.py ``sig_bollinger_trend(df, 20,
warmup)``) and the judged exit bracket (families3 BR24: SL 2.0 x
ATR(14), TP 4.0 x ATR(14)). Equivalence is pinned by
tests/test_fwd018_bollinger_variants.py against the rd2 harness on
real historical slices.

Governance: registered FORWARD_TEST in config_strategy.py under the
owner's two-tier admission doctrine (2026-11-18) — executable on DEMO
venues only (fail-closed in strategies/strategy_registry.py),
phase-3 forward protocol protections (0.1% risk per trade, 2% heat
cap, 3% daily breaker, kill criteria via
measurement/forward_guard.py: expectancy<0 or PF<1.0 after >=50
forward trades), fills tagged FORWARD_TEST in the Phase-2 ledger. It
is NOT a VALIDATED entrant; scorecards must never blend this lane
with ichimoku/dow/sleeve.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The daemon feed's final row is
the still-forming bar; it is dropped by timestamp before evaluation.
A signal on bar i means "enter at the open of bar i+1" in the judged
simulator; live, the daemon places a market order during bar i+1 and
re-anchors the returned sl_dist/tp_dist (multiples of ATR at bar i)
to the fill price, exactly as the simulator anchors them to the
entry price. Warmup is the judged 260 bars, counted within the
evaluated frame.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import BOLLINGER_TREND_P20_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
SMA_PERIOD = int(_CFG.get("SMA_PERIOD", 20))
SD_MULT = float(_CFG.get("SD_MULT", 2.0))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3929))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd2/families3.py + rd/common.py)
# ---------------------------------------------------------------------------

def _sma(series: pd.Series, w: int) -> pd.Series:
    return series.rolling(w).mean()


def _cross_up(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift(1) <= b.shift(1))


def _cross_down(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))


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
    """(long_mask, short_mask) — sig_bollinger_trend(df, 20, warmup)."""
    mid = _sma(df["close"], SMA_PERIOD)
    sd = df["close"].rolling(SMA_PERIOD).std()
    up = _cross_up(df["close"], mid + SD_MULT * sd)
    dn = _cross_down(df["close"], mid - SD_MULT * sd)
    return up, dn


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families3._entries_from_masks over
    sig_bollinger_trend's masks: bars [max(warmup, 1), len-2], long
    before short."""
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
