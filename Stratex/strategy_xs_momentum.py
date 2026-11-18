"""strategy_xs_momentum — TASK-STR-FWD-024 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002, near-miss re-audit
2026-11-18): xs_momentum / roc60_rb20 @ CRYPTO30 1d — 258 pooled
OOS trades, expectancy +0.865%/trade, PF 1.1347, win rate 0.5194,
2/5 positive folds. It passes the owner's second-tier
demo-admission bar (expectancy>0, PF>=1.05, >=200 OOS trades,
pre-Bonferroni) but NOT the frozen promotion bar, so it trades
demo-only under the forward protocol until its own forward record
judges it.

The judged object is CROSS-SECTIONAL (rigorous_backtest/rd2/
families2.py ``xs_entries``): at each rebalance bar (every 20 bars
from the judged warmup) the whole CRYPTO30 panel is ranked by
ROC(60); the top-3 are longed and the bottom-3 shorted, each with
the judged bracket_time exit (SL 3.0 x ATR(14), TP 6.0 x ATR(14),
max_bars 20 — the time exit is enforced by the daemon's forward
time-exit manager via the registry's max_bars).

Wave 2 excluded this row: the daemon's contract is a per-symbol
``get_signal(df)`` and no panel path existed. The machinery is
panel_signal_service.py (TASK-STR-FWD-024), following the
wf_select_service pattern: the daemon's ranking hook re-evaluates
the judged ranking over closed bars on a throttled cadence and
persists the current membership (per-symbol side + signal bar);
this module only looks its own symbol up. It fires ONLY when the
persisted signal bar for its symbol is the frame's last closed
bar — the judged entry timing — with the judged bracket. With no
persisted membership (the first ranking has not run yet, or the
last run failed closed) it returns no signal: an unranked panel
must not trade.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections and kill criteria via measurement/forward_guard.py,
fills tagged FORWARD_TEST. Its forward record is its own and is
never blended with the VALIDATED entrants' scorecards.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

try:
    from config_strategy import XS_MOMENTUM_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

import panel_signal_service as pss

STREAM_ID = str(_CFG.get("STREAM", "xs_momentum__crypto30__1d"))
TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
SL_ATR = float(_CFG.get("SL_ATR", 3.0))
TP_ATR = float(_CFG.get("TP_ATR", 6.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.5194))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR

_membership_cache: Dict[str, Any] = {"state": None, "mtime": None}


def current_membership() -> Optional[Dict[str, Any]]:
    """The persisted membership decision (mtime-cached read of the
    panel service state file). None before the first ranking."""
    path = pss._state_path(STREAM_ID)
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        return None
    if _membership_cache["mtime"] != mtime:
        _membership_cache["state"] = pss.load_membership(STREAM_ID)
        _membership_cache["mtime"] = mtime
    return _membership_cache["state"]


def _closed_frame(df: pd.DataFrame, now_s: Optional[float] = None) -> pd.DataFrame:
    """Drop still-forming trailing bars (bar open + duration > now).

    Epoch seconds are computed by timedelta division
    (resolution-independent); the index's int64 view (asi8)
    returns the index's native unit — microseconds under
    pandas 3 — which silently disables the drop
    (TASK-STR-FWD-025).
    """
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    epoch = pd.Timestamp("1970-01-01", tz=df.index.tz)
    opens = (df.index - epoch).total_seconds().to_numpy(dtype=float)
    keep = int(np.sum(opens + BAR_SECONDS <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def get_signal(df: pd.DataFrame, symbol: Optional[str] = None,
               timeframe: Optional[str] = None,
               venue: Optional[str] = None) -> Dict[str, Any]:
    """Fire the judged bracket iff the persisted panel membership
    holds an entry for ``symbol`` whose signal bar is the frame's
    last closed bar. Without evaluation context (classic
    get_signal(df) call) the module cannot know its symbol and
    returns no signal — the ranking is panel-wide by construction.
    """
    none_signal: Dict[str, Any] = {"side": None}
    try:
        if symbol is None:
            return none_signal
        if timeframe is not None and timeframe != TIMEFRAME:
            return none_signal
        state = current_membership()
        if not state or not state.get("ok"):
            return none_signal
        entry = (state.get("entries") or {}).get(symbol)
        if entry is None:
            return none_signal
        if df is None or len(df) < WARMUP_BARS + 1:
            return none_signal
        frame = _closed_frame(df)
        if len(frame) < WARMUP_BARS + 1:
            return none_signal
        last_bar_epoch = int(frame.index[-1].timestamp())
        if last_bar_epoch != int(entry.get("signal_bar_epoch", -1)):
            return none_signal
        atr = pss.atr14(frame)
        atr_i = float(atr.iloc[-1])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
        return {
            "side": "BUY" if entry.get("side") == "LONG" else "SELL",
            "sl_dist": SL_ATR * atr_i,
            "tp_dist": TP_ATR * atr_i,
            "win_rate_prior": WIN_RATE_PRIOR,
            "rr_ratio": RR_RATIO,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal
