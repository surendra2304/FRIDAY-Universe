"""strategy_volume_breakout — TASK-STR-FWD-019 FORWARD-TEST lane
entrant. THIS MODULE'S LOGIC WAS REPLACED by the judged port below
(disclosed in the PR body): the previous module was a different,
never-judged strategy (prior-10-bar breakout + EMA50/EMA200 trend
filter + 2.5x/5.0x ATR bracket, rolling-mean ATR) that was
UNREGISTERED in governance (no PRODUCTION_STRATEGY_REGISTRY entry),
so the daemon never executed it, and no live code path imports it
(verified by grep 2026-11-18: only the offline
analysis/run_all_backtests.py name list references it).

Judged configuration (TASK-STR-RD-002 near-miss audit,
~/workspace/str-nearmiss/REPORT.md §1.4 row 11): volume_breakout /
donch20_vol1.5 @ CRYPTO30 1d — 558 pooled OOS trades, +2.417%/trade,
PF 1.3038, win rate 0.3925, 3/5 positive folds, PF @2x costs 1.2801.
It meets the owner's second tier (expectancy > 0, PF >= 1.05,
>= 200 OOS trades, pre-Bonferroni) but did NOT pass the full frozen
bar (Bonferroni at programme N=3,899) — not a promotion, not
VALIDATED. NOTE: the sibling row volume_breakout/donch20_novol @ 1d
is an exact duplicate of donchian_turtle n20_b24 (audit §1.4 ‡dup)
and is NOT wired here — the donchian crew wires that stream
canonically; this module is only the vol1.5 stream.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections (0.1% per-trade risk on venue equity, 2% aggregate heat
cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50
closed trades or mark-to-market drawdown >5% of venue equity),
fills tagged FORWARD_TEST. Scorecards must never blend this lane
with the VALIDATED entrants.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families2.py ``sig_volume_breakout(df,
confirm=1.5, warmup)``: close breaks the prior 20-bar high/low AND
volume > 1.5 x the trailing 20-bar mean volume) and the judged exit
bracket (families2 BR24: SL 2.0 x ATR(14), TP 4.0 x ATR(14)).
Equivalence is pinned by tests/test_fwd019_volume_breakout_lane.py.

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
    from config_strategy import VOLUME_BREAKOUT_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
DONCHIAN_BARS = int(_CFG.get("DONCHIAN_BARS", 20))
VOLUME_WINDOW = int(_CFG.get("VOLUME_WINDOW", 20))
VOLUME_CONFIRM = float(_CFG.get("VOLUME_CONFIRM", 1.5))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3925))
RR_RATIO = TP_ATR / SL_ATR

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


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — sig_volume_breakout(df, 1.5, warmup):
    close above the prior 20-bar high / below the prior 20-bar low,
    confirmed by volume > 1.5 x the trailing 20-bar mean volume."""
    hi = df["high"].rolling(DONCHIAN_BARS).max().shift(1)
    lo = df["low"].rolling(DONCHIAN_BARS).min().shift(1)
    long_sig = df["close"] > hi
    short_sig = df["close"] < lo
    vma = df["volume"].rolling(VOLUME_WINDOW).mean()
    ok = df["volume"] > VOLUME_CONFIRM * vma
    return long_sig & ok, short_sig & ok


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families2._entries over
    sig_volume_breakout's masks: bars [warmup, len-1] INCLUSIVE of
    the final bar (families2._entries' range — unlike the families3
    convention, which excludes the last bar), long before short."""
    long_mask, short_mask = signal_masks(df)
    lm = long_mask.fillna(False).to_numpy(dtype=bool)
    sm = short_mask.fillna(False).to_numpy(dtype=bool)
    out: List[Tuple[int, str]] = []
    for i in range(warmup, len(lm)):
        if lm[i]:
            out.append((i, "LONG"))
        elif sm[i]:
            out.append((i, "SHORT"))
    return out


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
        return {
            "side": "BUY" if is_long else "SELL",
            "sl_dist": SL_ATR * atr_i,
            "tp_dist": TP_ATR * atr_i,
            "win_rate_prior": WIN_RATE_PRIOR,
            "rr_ratio": RR_RATIO,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal
