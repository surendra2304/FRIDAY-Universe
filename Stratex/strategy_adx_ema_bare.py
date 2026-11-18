"""strategy_adx_ema_bare — TASK-STR-FWD-003 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002 WATCHLIST: passed the mechanical
bar — expectancy>0, PF>=1.2, >=200 OOS trades, >=80% folds, holdout —
but FAILED Bonferroni multiple-testing significance at N=1,557, so it
was NOT promoted; the owner directed 2026-11-15 that near-bar
configurations be decided by real demo forward evidence instead):
adx_ema BARE @ CRYPTO30 4h — 837 pooled OOS trades, +0.7955%/trade,
PF 1.2332, win rate 0.5699, 4/5 positive folds, untouched-holdout
expectancy +0.9428% (292 trades).

BARE means the production module's OWN signals with NO downstream
filter: the judged harness (rigorous_backtest/rd2/gov2.py
``eval_module_cell`` with ``signal_filter=None``) called
``strategy_adx_ema.get_signal`` on sliding windows of the
module-featured frame and simulated the module's absolute SL/TP
(SL 3.0 x ATR(14), TP 3.0 x ATR(14) — RR 1.0). The PRODUCTION
configuration of adx_ema is a DIFFERENT judged object: the same
signals plus rd/stage2's LONG_ONLY + BTC-regime filter; it measured
+0.61%/PF 1.197 (sub-bar) and runs OBSERVE_ONLY under phase-3
measurement as ``strategy_adx_ema``. This wrapper never touches that
module's governance, evaluation path or records: it is a separate
module (``strategy_adx_ema_bare``), a separate registry entry, and
its fills are tagged FORWARD_TEST under its own strategy name. The
two measurements are never blended.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections (1% risk cap, 3% daily breaker, kill criteria via
measurement/forward_guard.py), fills tagged FORWARD_TEST in the
Phase-2 ledger. It is NOT a VALIDATED entrant.

Equivalence is pinned by tests/test_fwd003_forward_test_lane.py,
which re-implements the gov2 evaluation loop inline and requires
identical entries (bar, side, bracket distances) on real historical
slices.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The daemon feed's final row is
the still-forming bar; it is dropped by timestamp before evaluation.
The frame is featured with the production module's own
``add_features`` (exactly the judged pipeline) and the production
``get_signal`` is called on the trailing <=500-bar window — the
judged harness's WINDOW — so the live evaluation reproduces the
harness's per-bar semantics. The module's absolute SL/TP are
converted to distances from the signal bar's close; the daemon
re-anchors them to the fill price, exactly as the judged simulator
anchors the absolute levels to the entry price. All indicators are
causal; the EWM seed effect of a 600-bar live frame vs the harness's
full-history frame is <0.3% of the seed gap and cannot flip a cross
except within that margin of the boundary.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import ADX_EMA_BARE_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

try:  # The judged module itself — this wrapper adds no logic of its own.
    import strategy_adx_ema as _prod
except Exception:  # pragma: no cover - fail closed if the module is absent
    _prod = None

TIMEFRAME = str(_CFG.get("TIMEFRAME", "4h"))
BAR_SECONDS = 4 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
WINDOW = int(_CFG.get("WINDOW", 500))
SL_ATR = float(_CFG.get("SL_ATR", 3.0))
TP_ATR = float(_CFG.get("TP_ATR", 3.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.5699))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged evaluation (rigorous_backtest/rd2/gov2.py, bare configuration)
# ---------------------------------------------------------------------------

def _extract(res) -> Optional[Tuple[str, float, float]]:
    """(side, sl, tp) from a production SignalResult, or None."""
    if res is None:
        return None
    side = res.get("side") if isinstance(res, dict) else getattr(res, "side", None)
    if side not in ("BUY", "SELL"):
        return None
    sl = res.get("sl") if isinstance(res, dict) else getattr(res, "sl", None)
    tp = res.get("tp") if isinstance(res, dict) else getattr(res, "tp", None)
    if sl is None or tp is None:
        return None
    return side, float(sl), float(tp)


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str, float, float]]:
    """(bar, side, sl_dist, tp_dist) identical to the gov2 bare
    evaluation: features computed once over the frame with the
    production module's add_features, get_signal on trailing
    <=WINDOW-bar windows, bars [warmup, len-2], NO signal filter.
    Distances are measured from the signal bar's close (the judged
    simulator anchors the module's absolute levels to the entry
    price; the daemon re-anchors these distances to the fill)."""
    if _prod is None:
        return []
    featured = _prod.add_features(df)
    closes = df["close"].to_numpy(dtype=float)
    out: List[Tuple[int, str, float, float]] = []
    for i in range(warmup, len(df) - 1):
        window = featured.iloc[max(0, i - WINDOW + 1): i + 1].copy()
        ex = _extract(_prod.get_signal(window))
        if ex is None:
            continue
        side, sl, tp = ex
        close_i = closes[i]
        if side == "BUY":
            out.append((i, "LONG", close_i - sl, tp - close_i))
        else:
            out.append((i, "SHORT", sl - close_i, close_i - tp))
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
    if _prod is None:
        return none_signal
    try:
        if df is None or len(df) < WARMUP_BARS + 1:
            return none_signal
        frame = _closed_frame(df)
        if len(frame) < WARMUP_BARS + 1:
            return none_signal
        featured = _prod.add_features(frame)
        window = featured.iloc[-WINDOW:].copy()
        ex = _extract(_prod.get_signal(window))
        if ex is None:
            return none_signal
        side, sl, tp = ex
        close_last = float(frame["close"].iloc[-1])
        if side == "BUY":
            sl_dist, tp_dist = close_last - sl, tp - close_last
        else:
            sl_dist, tp_dist = sl - close_last, close_last - tp
        if sl_dist <= 0 or tp_dist <= 0:
            return none_signal
        return {
            "side": side,
            "sl_dist": sl_dist,
            "tp_dist": tp_dist,
            "win_rate_prior": WIN_RATE_PRIOR,
            "rr_ratio": RR_RATIO,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal
