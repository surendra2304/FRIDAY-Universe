"""strategy_tsmom2_dual_crypto — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002, near-miss re-audit
~/workspace/str-nearmiss/REPORT.md §1.4 row 70): tsmom2_dual /
roc90_ema200 @ CRYPTO30 4h — 1,580 pooled OOS trades, +0.402%/trade,
PF 1.0965, win rate 0.3627, 3/5 positive folds. It meets the owner's
second tier (expectancy > 0, PF >= 1.05, >= 200 OOS trades, judged
before Bonferroni) but did NOT pass the full frozen bar (Bonferroni
at programme N=3,899) — not a promotion, not VALIDATED.

KEY NOTE: the registry key is ``tsmom2_dual_crypto`` because the plain
key ``tsmom2_dual`` is already taken by the EXCLUDED comm7 documentary
registration (roc30_ema200 @ comm7 4h, lane_assets empty, no module).
The two are different judged objects and their records are never
blended. The same ``sig_dual_momentum`` function also serves the live
Stage-C sleeve leg (sleeve_tsmom2_dual) at 1d on forex28 via the
OANDA sleeve runner — again a distinct judged object.

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
ATR(14) — the same bracket the sleeve leg uses at 1d, verified for
this 4h cell rather than assumed). EMA/ATR exactly as
rigorous_backtest/rd/common.py. Equivalence is pinned by
tests/test_fwd019_ts_momentum_lane.py.

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
    from config_strategy import TSMOM2_DUAL_CRYPTO_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "4h"))
BAR_SECONDS = 4 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
ROC_LOOKBACK = int(_CFG.get("ROC_LOOKBACK", 90))
EMA_PERIOD = int(_CFG.get("EMA_PERIOD", 200))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.5))
TP_ATR = float(_CFG.get("TP_ATR", 5.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3627))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


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
    """Evaluate the last closed 4h bar; return the daemon signal dict."""
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
