"""strategy_tsmom2_dual_crypto_1d — TASK-STR-FWD-030 ensemble-book gap module.

Judged configuration (TASK-STR-RD-002 grid row, results_rd2/
synthesis.json): tsmom2_dual / roc90_ema200 @ CRYPTO30 1d — 174 pooled
OOS trades, expectancy +7.6032%/trade, PF 1.8470, 4/5 positive folds.
It is a member of the RD-025 PROVEN ensemble book 3978
(DUAL+SHW+ZSC+HA1d+XSL) — NOT the 4h cell PR #991 built
(strategy_tsmom2_dual_crypto, 1,580 trades, PF 1.0965) and NOT the
sleeve's forex28 leg (127 trades, PF 1.5051): same judged signal
function, different panel cell and records; never blended.

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
(rigorous_backtest/rd2/families2.py ``sig_dual_momentum(df, 90,
warmup)``: ROC(90) zero-cross gated by close vs EMA(200)) and the
judged exit bracket (families2 build_configs tsmom2_dual spec,
verified in this cell's row record: SL 2.5 x ATR(14), TP 5.0 x
ATR(14) — the same bracket the 4h cell and the sleeve leg use).
EMA/ATR exactly as rigorous_backtest/rd/common.py. Equivalence is
pinned by tests/test_fwd030_ensemble_context_passing.py.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar; the still-forming final row is
dropped by timestamp before evaluation. A signal on bar i means
"enter at the open of bar i+1" in the judged simulator; live, the
daemon re-anchors the returned sl_dist/tp_dist to the fill price,
exactly as the simulator anchors them to the entry price. Warmup is
the judged 260 bars, counted within the evaluated frame.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import TSMOM2_DUAL_CRYPTO_1D_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
ROC_LOOKBACK = int(_CFG.get("ROC_LOOKBACK", 90))
EMA_PERIOD = int(_CFG.get("EMA_PERIOD", 200))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.5))
TP_ATR = float(_CFG.get("TP_ATR", 5.0))
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
    """(long_mask, short_mask) — sig_dual_momentum(df, 90, warmup)."""
    roc = df["close"] / df["close"].shift(ROC_LOOKBACK) - 1.0
    e200 = _ema(df["close"], EMA_PERIOD)
    long_sig = (roc > 0) & (roc.shift(1) <= 0) & (df["close"] > e200)
    short_sig = (roc < 0) & (roc.shift(1) >= 0) & (df["close"] < e200)
    return long_sig, short_sig


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families2._entries over
    sig_dual_momentum's masks: bars [warmup, len-1], long first."""
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
