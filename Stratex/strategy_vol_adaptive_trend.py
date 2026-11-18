"""strategy_vol_adaptive_trend — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002, near-miss re-audit
~/workspace/str-nearmiss/REPORT.md §1.4 row 2): vol_adaptive_trend /
ema12_26_nogate @ CRYPTO30 1d — 299 pooled OOS trades, +6.233%/trade,
PF 1.6956, win rate 0.4482, 4/5 positive folds, PF @2x costs 1.6721.
It meets the owner's second tier (expectancy > 0, PF >= 1.05, >= 200
OOS trades, judged before Bonferroni) but did NOT pass the full frozen
bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED.
This stream is also a member of the live Stage-C sleeve book under its
sleeve key — a distinct judged object; records are never blended.

Governance: registered FORWARD_TEST in config_strategy.py — executable
on DEMO venues only (fail-closed in strategies/strategy_registry.py),
phase-3 forward protocol protections (0.1% risk cap, 3% daily breaker,
kill criteria via measurement/forward_guard.py), fills tagged
FORWARD_TEST in the Phase-2 ledger. Scorecards must never blend this
lane with ichimoku/dow/sleeve.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families2.py ``sig_vol_trend(df, 12, 26, False,
warmup)``) and the judged exit bracket (families2 build_configs
vol_adaptive_trend spec: SL 2.5 x ATR(14), TP 5.0 x ATR(14); ATR and
EMA exactly as rigorous_backtest/rd/common.py ``atr`` / ``ema``).
Equivalence is pinned by tests/test_fwd019_vol_adaptive_lane.py, which
runs this module and the rd2 harness side by side on real historical
slices and requires identical entry lists.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The daemon feed's final row is
the still-forming bar; it is dropped by timestamp before evaluation.
A signal on bar i means "enter at the open of bar i+1" in the judged
simulator; live, the daemon places a market order during bar i+1 and
re-anchors the returned sl_dist/tp_dist (multiples of ATR at bar i)
to the fill price, exactly as the simulator anchors them to the
entry price. Warmup is the judged 260 bars, counted within the
evaluated frame; the EMA/ATR EWMs' initialisation error after 260
bars is negligible, so a live frame reproduces the judged series.

This is the family's CORE module: it also exposes the parameterised
helpers (``signal_masks_cfg`` / ``entries_for_frame_cfg`` /
``get_signal_cfg``) that the family's thin variant modules
(strategy_vol_adaptive_trend_<variant>.py) bind to their own judged
configurations.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import VOL_ADAPTIVE_TREND_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
FAST_EMA = int(_CFG.get("FAST_EMA", 12))
SLOW_EMA = int(_CFG.get("SLOW_EMA", 26))
GATE = bool(_CFG.get("GATE", False))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.5))
TP_ATR = float(_CFG.get("TP_ATR", 5.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.4482))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR

_TF_BAR_SECONDS = {"1d": 24 * 3600, "4h": 4 * 3600, "1h": 3600}


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


def signal_masks_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any]
) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — families2.sig_vol_trend(df, fast,
    slow, gate, warmup)'s masks for an arbitrary judged cfg."""
    f = _ema(df["close"], int(cfg.get("FAST_EMA", 12)))
    s = _ema(df["close"], int(cfg.get("SLOW_EMA", 26)))
    long_sig = (f > s) & (f.shift(1) <= s.shift(1))
    short_sig = (f < s) & (f.shift(1) >= s.shift(1))
    if bool(cfg.get("GATE", False)):
        atrp = atr14(df, int(cfg.get("ATR_PERIOD", 14))) / df["close"]
        pct = atrp.rolling(200).rank(pct=True)
        ok = (pct >= 0.2) & (pct <= 0.8)
        long_sig = long_sig & ok
        short_sig = short_sig & ok
    return long_sig, short_sig


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — sig_vol_trend(df, 12, 26, False)."""
    return signal_masks_cfg(df, _CFG)


def entries_for_frame_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], warmup: Optional[int] = None
) -> List[Tuple[int, str]]:
    """Entry list identical to families2._entries over sig_vol_trend's
    masks: bars [warmup, len-1], long before short."""
    w = int(cfg.get("WARMUP_BARS", 260)) if warmup is None else warmup
    long_mask, short_mask = signal_masks_cfg(df, cfg)
    ls = long_mask.fillna(False).to_numpy(dtype=bool)
    ss = short_mask.fillna(False).to_numpy(dtype=bool)
    out: List[Tuple[int, str]] = []
    for i in range(w, len(ls)):
        if ls[i]:
            out.append((i, "LONG"))
        elif ss[i]:
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
    """Evaluate the last closed bar under an arbitrary judged cfg."""
    none_signal: Dict[str, Any] = {"side": None}
    warmup = int(cfg.get("WARMUP_BARS", 260))
    bar_seconds = _TF_BAR_SECONDS.get(str(cfg.get("TIMEFRAME", "1d")), BAR_SECONDS)
    try:
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
        atr = atr14(frame, int(cfg.get("ATR_PERIOD", 14)))
        atr_i = float(atr.iloc[i])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
        sl_atr = float(cfg.get("SL_ATR", 2.5))
        tp_atr = float(cfg.get("TP_ATR", 5.0))
        side = "BUY" if is_long else "SELL"
        return {
            "side": side,
            "sl_dist": sl_atr * atr_i,
            "tp_dist": tp_atr * atr_i,
            "win_rate_prior": float(cfg.get("OOS_WIN_RATE", 0.4482)),
            "rr_ratio": tp_atr / sl_atr,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed 1d bar; return the daemon signal dict."""
    return get_signal_cfg(df, _CFG)
