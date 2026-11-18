"""strategy_wf_select_tsmom — TASK-STR-FWD-022 FORWARD-TEST entrant.

The entrant is not a fixed configuration: it is the walk-forward
SELECTION PROCEDURE ts_momentum @ CRYPTO30 1d from Appendix A of the
near-miss re-audit (TASK-STR-RD-002 records: 453 pooled OOS trades,
expectancy +1.4096%/trade, PF 1.1694, win rate 0.3664, 3/5 positive
folds; historical picks roc24 / roc168 / roc72 / roc42 / roc42 under
the judged rule — expanding in-sample window, rank by
(profit_factor_net, win_rate), top 1). It meets the owner's second
tier (expectancy > 0, PF >= 1.05, >= 200 trades, pre-Bonferroni) and
was admitted to the FORWARD_TEST lane on 2026-11-18.

How it trades: wf_select_service.py holds the procedure registry and
the selection machinery. At each calendar-month (UTC) epoch the
daemon's selection hook re-runs the judged rule over candle history
closed before the epoch start and persists the pick (state file +
append-only selection log under data/wf_select/). This module's
get_signal evaluates ONLY the current pick's variant — the ts_momentum
ROC-cross entries and the judged BR24 bracket (SL 2.0 x ATR(14),
TP 4.0 x ATR(14)) — on the last closed bar, exactly as the fixed
lane modules do. With no persisted pick (the first selection has
not run yet) it returns no signal: an unselected procedure must not
trade. A stale pick (epoch rolled, hook has not run yet) keeps
trading — the hook runs on the scan cadence and refreshes within
minutes; every refresh is logged.

The procedure's forward record is its own: fills carry this
module's strategy name, tagged FORWARD_TEST, and are never blended
with the fixed ts_momentum configurations wired by other waves.
Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections and kill criteria via measurement/forward_guard.py.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import WF_SELECT_TSMOM_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

import wf_select_service as wfs

PROCEDURE_ID = str(_CFG.get("PROCEDURE", "ts_momentum__crypto30__1d"))
TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3664))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR

_SPEC = wfs.PROCEDURES[PROCEDURE_ID]
_VARIANTS: Dict[str, int] = dict(_SPEC["variants"])

_pick_cache: Dict[str, Any] = {"pick": None, "mtime": None}


def current_pick() -> Optional[str]:
    """The persisted pick for the current epoch (mtime-cached read
    of the selection state file). None before the first selection."""
    import os

    path = wfs._state_path(PROCEDURE_ID)
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        return None
    if _pick_cache["mtime"] != mtime:
        _pick_cache["pick"] = wfs.current_pick(PROCEDURE_ID)
        _pick_cache["mtime"] = mtime
    return _pick_cache["pick"]


def entries_for_frame(
    df: pd.DataFrame, variant: str, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list of one variant over a frame — the judged
    sig_ts_momentum entries (wf_select_service port)."""
    return wfs.ts_momentum_entries(df, _VARIANTS[variant], warmup)


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
    """Evaluate the current pick's variant on the last closed 1d bar;
    return the daemon signal dict with the judged BR24 bracket."""
    none_signal: Dict[str, Any] = {"side": None}
    try:
        pick = current_pick()
        if pick is None or pick not in _VARIANTS:
            return none_signal
        if df is None or len(df) < WARMUP_BARS + 1:
            return none_signal
        frame = _closed_frame(df)
        if len(frame) < WARMUP_BARS + 1:
            return none_signal
        i = len(frame) - 1
        if i < WARMUP_BARS:
            return none_signal
        entries = entries_for_frame(frame, pick)
        if not entries or entries[-1][0] != i:
            return none_signal
        side = "BUY" if entries[-1][1] == "LONG" else "SELL"
        atr = wfs.atr14(frame)
        atr_i = float(atr.iloc[i])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
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
