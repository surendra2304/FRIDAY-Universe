"""strategy_vol_regime_trend — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-004, vol_regime_trend family):
ema24_96_gate_lo @ CRYPTO30 2h — 2,286 pooled OOS trades,
+0.203%/trade, PF 1.1072, win rate 0.3675, 2/5 positive folds
(results_rd4/synthesis.json ``configs`` on origin/main). It meets the
owner's second tier (expectancy > 0, PF >= 1.05, >= 200 OOS trades,
pre-Bonferroni) but did NOT pass the full frozen bar — not a
promotion, not VALIDATED. The RD-004 WF-2h walk-forward-select
procedure's pooled stream is identical to this cell (it picked
ema24_96_gate_lo in all 5 folds); it is NOT a separate config and is
not wired twice.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections (TASK-STR-FWD-006 package), fills tagged FORWARD_TEST.
Scorecards must never blend this lane with the VALIDATED entrants.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd4/families_rd4.py ``base_entries`` +
``regime_rank_by_bar`` + ``apply_mode(..., "gate_lo", ...)``): the
base trend signal (EMA cross or Donchian breakout) is gated by a
daily volatility-regime rank — entries only on days whose rank
R(d) < 0.50 (the low-volatility gate). R(d) is yesterday's daily
mean bar-ATR%(14) ranked against the prior 180 days; all bars of
day d use R(d); the first 181 days have no rank and take no gated
entries. The judged bracket is RD-004's own (families_rd4 module
docstring + rd4/sim_rd4.py SL_BASE/TP_BASE): SL 2.0 x ATR(14),
TP 4.0 x ATR(14) — the same values as RD-002's BR24, carried in
RD-004's harness, not assumed from it. Warmup 260 bars
(families_rd4 WARMUP). ATR/EMA exactly as rigorous_backtest/rd/
common.py. Equivalence is pinned by
tests/test_fwd019_vol_regime_trend_lane.py against the rd4 harness
on the fwd002 fixture slices (4h and 1d frames — the bar-series
logic is timeframe-agnostic; only 1d/4h fixture slices exist).

This core module exposes the gated-mask machinery parameterised by
base-signal choice (``entries_for_frame_cfg`` / ``signal_masks_cfg``
/ ``get_signal_cfg``); the sibling variants don20_gate_lo and
ema12_48_gate_lo are thin modules binding their own CFG dicts to
these helpers.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar (the still-forming trailing bar
is dropped by timestamp). A signal on bar i means "enter at the
open of bar i+1" in the judged simulator; live, the daemon places a
market order during bar i+1 and re-anchors the returned
sl_dist/tp_dist (multiples of ATR at bar i) to the fill price.
Because the regime rank needs 181 days of history, a live frame
shorter than that yields no signal (fail-closed, exactly as the
harness takes no entries on NaN-rank days).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import VOL_REGIME_TREND_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "2h"))
BAR_SECONDS = 7200
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
REGIME_DAYS = int(_CFG.get("REGIME_DAYS", 180))
GATE_THRESHOLD = float(_CFG.get("GATE_THRESHOLD", 0.50))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3675))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd4/families_rd4.py + rd/common.py)
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


def base_signal_masks(
    df: pd.DataFrame, signal: str
) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — the ungated cross/breakout events of
    families_rd4.base_entries for one signal spec ("don20",
    "ema12_48", "ema24_96", ...)."""
    close = df["close"]
    if signal.startswith("don"):
        n = int(signal[3:])
        hi = df["high"].rolling(n).max().shift(1)
        lo = df["low"].rolling(n).min().shift(1)
        long_sig = (close > hi) & (close.shift(1) <= hi.shift(1))
        short_sig = (close < lo) & (close.shift(1) >= lo.shift(1))
        return long_sig, short_sig
    f, s = (int(x) for x in signal[3:].split("_"))
    ef, es = _ema(close, f), _ema(close, s)
    long_sig = (ef > es) & (ef.shift(1) <= es.shift(1))
    short_sig = (ef < es) & (ef.shift(1) >= es.shift(1))
    return long_sig, short_sig


def regime_rank_by_bar(df: pd.DataFrame) -> np.ndarray:
    """Per-bar regime rank R(d) — families_rd4.regime_rank_by_bar,
    verbatim: bar ATR%(14) averaged per UTC day = V(d); R(d) is the
    share of the prior REGIME_DAYS days' V values <= V(d-1); NaN for
    the first REGIME_DAYS + 1 days."""
    atr_pct = (atr14(df, 14) / df["close"])
    daily = atr_pct.groupby(df.index.date).mean()
    V = daily.to_numpy(dtype=float)
    R = np.full(len(V), np.nan)
    for j in range(REGIME_DAYS + 1, len(V)):
        window = V[j - REGIME_DAYS:j]          # V[j-180 .. j-1]
        R[j] = float(np.mean(window <= V[j - 1]))
    rank_of_day = dict(zip(daily.index, R))
    return np.array([rank_of_day[d] for d in df.index.date], dtype=float)


def signal_masks_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any]
) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) AFTER the gate_lo regime gate: base
    events kept only where R(d) is finite and < GATE_THRESHOLD
    (families_rd4.apply_mode with mode "gate_lo")."""
    long_sig, short_sig = base_signal_masks(df, str(cfg.get("SIGNAL", "ema24_96")))
    rank = regime_rank_by_bar(df)
    gate = pd.Series(
        np.isfinite(rank) & (rank < float(cfg.get("GATE_THRESHOLD", 0.50))),
        index=df.index,
    )
    return long_sig & gate, short_sig & gate


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — gated masks for this module's CFG."""
    return signal_masks_cfg(df, _CFG)


def _entries_from_masks(
    long_sig: pd.Series, short_sig: pd.Series, warmup: int
) -> List[Tuple[int, str]]:
    """families_rd4._entries, verbatim: bars [warmup, len), long
    before short."""
    out: List[Tuple[int, str]] = []
    ls = long_sig.fillna(False).to_numpy(dtype=bool)
    ss = short_sig.fillna(False).to_numpy(dtype=bool)
    for i in range(warmup, len(ls)):
        if ls[i]:
            out.append((i, "LONG"))
        elif ss[i]:
            out.append((i, "SHORT"))
    return out


def entries_for_frame_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], warmup: Optional[int] = None
) -> List[Tuple[int, str]]:
    """Entry list identical to the judged harness pipeline
    apply_mode(base_entries(df, signal), "gate_lo",
    regime_rank_by_bar(df)) with the bracket factor dropped (it is
    1.0 for gate_lo)."""
    w = int(cfg.get("WARMUP_BARS", WARMUP_BARS)) if warmup is None else warmup
    long_sig, short_sig = base_signal_masks(df, str(cfg.get("SIGNAL", "ema24_96")))
    entries = _entries_from_masks(long_sig, short_sig, w)
    rank = regime_rank_by_bar(df)
    threshold = float(cfg.get("GATE_THRESHOLD", 0.50))
    out: List[Tuple[int, str]] = []
    for i, side in entries:
        r = rank[i]
        if not np.isfinite(r):
            continue
        if r < threshold:
            out.append((i, side))
    return out


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Gated entries for this module's own judged configuration."""
    return entries_for_frame_cfg(df, _CFG, warmup)


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


def get_signal_cfg(df: pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate the last closed bar under ``cfg``; daemon signal dict."""
    none_signal: Dict[str, Any] = {"side": None}
    try:
        warmup = int(cfg.get("WARMUP_BARS", WARMUP_BARS))
        if df is None or len(df) < warmup + 1:
            return none_signal
        frame = _closed_frame(df)
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
        atr = atr14(frame)
        atr_i = float(atr.iloc[i])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
        sl_atr = float(cfg.get("SL_ATR", SL_ATR))
        tp_atr = float(cfg.get("TP_ATR", TP_ATR))
        side = "BUY" if is_long else "SELL"
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
    """Evaluate the last closed 2h bar; return the daemon signal dict."""
    return get_signal_cfg(df, _CFG)
