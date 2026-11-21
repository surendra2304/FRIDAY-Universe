"""strategy_zscore_reversion — TASK-STR-FWD-030 ensemble-book gap module.

Judged configuration (TASK-STR-RD-002 grid row, results_rd2/
synthesis.json): zscore_reversion / w50_t2.5_filt @ FOREX28 1d — 130
pooled OOS trades, expectancy +0.3473%/trade, PF 1.4759, 4/5 positive
folds. It is the forex member (ZSC) of the RD-025 PROVEN ensemble
book 3978 (DUAL+SHW+ZSC+HA1d+XSL).

No win rate was published for this cell — none is recorded. The
pooled OOS row carries trades / expectancy / PF / folds only, and
the RD-002 trade lists needed to recompute the win rate are not in
this repo (the RD-002 cache is absent from this machine). The module
therefore carries no win-rate prior: no _OOS_WIN_RATE_PRIOR, no
win_rate_prior in its signal dict, no oos_win_rate_prior in its
registry entry. The daemon's expectancy gate fails closed on that
(a standalone scan skips it for "no measured win-rate"); the book
path is unaffected — the ensemble engine nets member signals and the
book's own signal carries the book's judged win rate. When the
RD-002 backup is available the pooled OOS win rate belongs here.

Governance: registered FORWARD_TEST in config_strategy.py — executable
on DEMO venues only (fail-closed in strategies/strategy_registry.py),
phase-3 forward protocol protections (0.1% risk cap, 3% daily breaker,
kill criteria via measurement/forward_guard.py), fills tagged
FORWARD_TEST in the Phase-2 ledger.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families2.py ``sig_zscore(df, 50, 2.5, True,
warmup)``: z = (close - 50-bar mean) / 50-bar stdev; LONG on the
cross down through -2.5, SHORT on the cross up through +2.5, both
gated on ADX(14) < 25) and the judged exit bracket (families2
build_configs zscore_reversion spec: SL 2.0 x ATR(14), TP 2.0 x
ATR(14)). ADX/ATR exactly as rigorous_backtest/rd/common.py.
Equivalence is pinned by tests/test_fwd030_ensemble_context_passing.py.

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
    from config_strategy import ZSCORE_REVERSION_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
ZSCORE_WINDOW = int(_CFG.get("ZSCORE_WINDOW", 50))
ZSCORE_THETA = float(_CFG.get("ZSCORE_THETA", 2.5))
USE_FILTER = bool(_CFG.get("USE_ADX_FILTER", True))
ADX_PERIOD = int(_CFG.get("ADX_PERIOD", 14))
ADX_MAX = float(_CFG.get("ADX_MAX", 25.0))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 2.0))
# No win rate was published for this cell — none is recorded (see
# docstring). WIN_RATE_PRIOR stays None; the signal dict carries no
# win_rate_prior key.
WIN_RATE_PRIOR = _CFG.get("OOS_WIN_RATE")
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO


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


def adx14(df: pd.DataFrame, period: int = ADX_PERIOD) -> pd.Series:
    """ADX exactly as rigorous_backtest/rd/common.py ``adx``.

    Wilder-smoothed ADX, replicating strategy_adx_ema.compute_adx.
    """
    plus_dm = df["high"].diff()
    minus_dm = -df["low"].diff()
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift(1)),
        abs(df["low"] - df["close"].shift(1)),
    ], axis=1).max(axis=1)
    tr_s = tr.ewm(alpha=1 / period, adjust=False).mean()
    pdi = pd.Series(plus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False).mean() / tr_s * 100
    mdi = pd.Series(minus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False).mean() / tr_s * 100
    dx = (abs(pdi - mdi) / (pdi + mdi + 1e-9)) * 100
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — sig_zscore(df, 50, 2.5, True, warmup)."""
    mid = df["close"].rolling(ZSCORE_WINDOW).mean()
    sd = df["close"].rolling(ZSCORE_WINDOW).std()
    z = (df["close"] - mid) / sd
    prev = z.shift(1)
    long_sig = (prev >= -ZSCORE_THETA) & (z < -ZSCORE_THETA)
    short_sig = (prev <= ZSCORE_THETA) & (z > ZSCORE_THETA)
    if USE_FILTER:
        ok = adx14(df) < ADX_MAX
        long_sig = long_sig & ok
        short_sig = short_sig & ok
    return long_sig, short_sig


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families2._entries over
    sig_zscore's masks: bars [warmup, len-1], long first."""
    long_mask, short_mask = signal_masks(df)
    ls = long_mask.fillna(False).to_numpy(dtype=bool)
    ss = short_mask.fillna(False).to_numpy(dtype=bool)
    out: List[Tuple[int, str]] = []
    for i in range(warmup, len(ls)):
        if ls[i]:
            out.append((i, "LONG"))
        elif ss[i]:
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
            "rr_ratio": RR_RATIO,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal
