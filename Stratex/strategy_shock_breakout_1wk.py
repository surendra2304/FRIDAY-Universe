"""strategy_shock_breakout_1wk — TASK-STR-FWD-030 ensemble-book gap module.

Judged configuration (TASK-STR-RD-002 grid row, results_rd2/
synthesis.json; RD-011 stream record, results_rd11/streams/
shock_breakout__k1.0__crypto30__1wk.json): shock_breakout / k1.0 @
CRYPTO30 1w — 109 pooled OOS trades, expectancy +9.0431%/trade, PF
1.5750, win rate 0.4679 (51/109, pooled_oos), 4/5 positive folds.
It is the weekly member (SHW) of the RD-025 PROVEN ensemble book
3978 (DUAL+SHW+ZSC+HA1d+XSL) — and the same judged cell as the
FWD-002 sleeve's weekly leg (SLEEVE_SHOCK_BREAKOUT_STRATEGY, whose
0.4267 win rate is the FULL-cache simulation figure, 150 trades —
a different window from this module's pooled OOS 0.4679; the two
records are never blended).

Weekly bars are the JUDGED 7-day buckets (rigorous_backtest/rd2/
panels._to_weekly: resample "7D", origin = each symbol's judged 1d
series start). Binance native weekly klines are Monday-anchored and
are NOT the judged bars; the daemon rebuilds the judged buckets from
daily bars via strategy_sleeve_shock_breakout.weekly_candles using the
per-symbol anchors in config_strategy.WEEKLY_BUCKET_ANCHORS. The
module itself evaluates whatever weekly frame it is given; the venue
label for the weekly timeframe is '1w' (TASK-STR-FWD-029 — the API's
canonical TIMEFRAMES set and the Binance weekly interval). The
daemon's own scan timeframe list still says '1wk' (flagged follow-up
from TASK-STR-FWD-029, for Muse to decide — NOT changed here): until
that lands, the daemon scans the sleeve at '1wk' while this module
and book 3978 carry the venue label '1w'.

Governance: registered FORWARD_TEST in config_strategy.py — executable
on DEMO venues only (fail-closed in strategies/strategy_registry.py),
phase-3 forward protocol protections (0.1% risk cap, 3% daily breaker,
kill criteria via measurement/forward_guard.py), fills tagged
FORWARD_TEST in the Phase-2 ledger.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families3.py ``sig_shock(df, 1.0, warmup)``:
a one-bar close move exceeding 1.0 x ATR(14) at the signal bar) and
the judged exit bracket (families3 BR24: SL 2.0 x ATR(14), TP 4.0 x
ATR(14); ATR exactly as rigorous_backtest/rd/common.py ``atr``).
Equivalence is pinned by tests/test_fwd030_ensemble_context_passing.py,
which runs this module and the rd2 harness side by side on the
judged weekly fixture slices and requires identical entry lists and
bracket distances.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The daemon feed's final row is
the still-forming bar; it is dropped by timestamp before evaluation.
A signal on bar i means "enter at the open of bar i+1" in the judged
simulator; live, the daemon places a market order during bar i+1 and
re-anchors the returned sl_dist/tp_dist (multiples of ATR at bar i)
to the fill price, exactly as the simulator anchors them to the
entry price. Warmup is the judged 104 bars (warmup_for("1wk")),
counted within the evaluated frame.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import SHOCK_BREAKOUT_1WK_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1w"))
BAR_SECONDS = 7 * 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 104))
SHOCK_K = float(_CFG.get("SHOCK_K", 1.0))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.4679))
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


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — sig_shock(df, 1.0, warmup) masks.

    The ATR is taken at the signal bar itself (unshifted), exactly as
    families3 computes it: the move of bar i is compared against
    k x ATR(14) at bar i.
    """
    a = atr14(df)
    up = (df["close"] - df["close"].shift(1)) > SHOCK_K * a
    dn = (df["close"].shift(1) - df["close"]) > SHOCK_K * a
    return up, dn


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families3._entries_from_masks over
    sig_shock's masks: bars [max(warmup, 1), len-2], long before short."""
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
    """Evaluate the last closed weekly bar; return the daemon signal dict."""
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
