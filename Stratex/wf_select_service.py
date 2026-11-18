"""wf_select_service — TASK-STR-FWD-022: walk-forward selection service.

Appendix A of the near-miss re-audit lists 33 two-tier objects that
are not fixed configurations but walk-forward selection PROCEDURES:
for each judgement window, a variant is chosen by a rule applied to
past data only, and the procedure's pooled OOS record is the record
of those picks. The judged rule (rigorous_backtest/rd/common.py
``wf_select_judge``) is: per window, for each variant compute trade
metrics over all simulated trades with entry_time < window start
(EXPANDING in-sample window); keep variants with trades > 0 and a
defined profit factor; rank by (profit_factor_net desc, win_rate
desc); take the top 1; the procedure trades that variant for the
window.

This service runs such a procedure live as a FORWARD_TEST entrant:

- Procedures are registered in PROCEDURES below (family, panel,
  timeframe, variant set, judged bracket, costs, warmup). Registering
  another Appendix-A procedure later = adding its spec here plus a
  ported signal function in FAMILY_SIGNALS — the selection machinery
  is shared and unchanged.
- At each selection epoch (declared per procedure; the first entrant
  uses calendar-month UTC epochs — the judged W1–W5 windows were the
  judgement calendar, not part of the procedure's definition), the
  daemon hook (autonomy/run_daemon.py _maybe_run_wf_selection)
  gathers the panel frames, this service simulates every variant
  over bars CLOSED BEFORE the epoch start, selects strictly from
  those in-sample metrics, and persists the decision: state file
  (current pick) + append-only selection log with the full
  per-variant in-sample table, so every pick is auditable.
- The entrant module (strategy_wf_select_tsmom.py) trades the
  current pick's variant through the normal lane signal path; fills
  carry the procedure's own strategy name, so its forward record is
  kept separate from every fixed configuration — including the same
  family's fixed configs wired by other waves.

Fidelity: the simulator, metrics and ranking below are line-faithful
ports of rigorous_backtest/rd/fastsim.py (bracket path),
rigorous_backtest/simulator.py (Costs, _net_return, trade_metrics)
and rd/common.py's wf_select_judge. tests/test_fwd022_wf_select_
service.py pins the ports against the harness on real slices and
reproduces the judged procedure record exactly from the recorded
RD-002 trade streams (picks roc24/roc168/roc72/roc42/roc42, pooled
453 trades, PF 1.1694).

Disclosed live translations: (1) the in-sample history is the candle
history the venue returns (the daemon requests 1500 bars), not the
judged run's full cache from 2022 — the span used is recorded in
every selection log line; (2) trades entered before an epoch start
but still open at the last pre-epoch bar are marked at that close
by the simulator's END_OF_DATA rule, where the retrospective judged
record used their final outcomes; (3) epoch cadence (monthly) is a
declared service parameter, as noted above.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

BAR_SECONDS = {"4h": 4 * 3600, "1d": 24 * 3600}


# ---------------------------------------------------------------------------
# Judged-logic ports (simulator.py / fastsim.py / rd families / common.py)
# ---------------------------------------------------------------------------

@dataclass
class SimTrade:
    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: str
    entry_price: float
    exit_price: float
    net_return: float
    exit_reason: str


@dataclass
class Costs:
    """simulator.Costs port: fee + slippage per side, in bps."""

    fee_bps_per_side: float = 5.0
    slip_bps_per_side: float = 3.0

    @property
    def per_side_rate(self) -> float:
        return (self.fee_bps_per_side + self.slip_bps_per_side) / 10000.0


def _net_return(side: str, entry: float, exit_: float, costs: Costs) -> float:
    """simulator._net_return, verbatim."""
    r = costs.per_side_rate
    if side == "LONG":
        entry_adj = entry * (1 + r)
        exit_adj = exit_ * (1 - r)
        return (exit_adj - entry_adj) / entry_adj
    entry_adj = entry * (1 - r)
    exit_adj = exit_ * (1 + r)
    return (entry_adj - exit_adj) / entry_adj


def atr14(df: pd.DataFrame, period: int = 14) -> pd.Series:
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


def _first_hit_long(lows, highs, opens, start, sl, tp):
    """fastsim._first_hit_long, verbatim."""
    sl_hits = np.nonzero(lows[start:] <= sl)[0]
    first_sl = (start + sl_hits[0]) if len(sl_hits) else None
    first_tp = None
    if tp is not None:
        tp_hits = np.nonzero(highs[start:] >= tp)[0]
        first_tp = (start + tp_hits[0]) if len(tp_hits) else None
    if first_sl is not None and (first_tp is None or first_sl <= first_tp):
        b = first_sl
        return b, (opens[b] if opens[b] <= sl else sl), "SL"
    if first_tp is not None:
        b = first_tp
        return b, (opens[b] if opens[b] >= tp else tp), "TP"
    return None


def _first_hit_short(lows, highs, opens, start, sl, tp):
    """fastsim._first_hit_short, verbatim."""
    sl_hits = np.nonzero(highs[start:] >= sl)[0]
    first_sl = (start + sl_hits[0]) if len(sl_hits) else None
    first_tp = None
    if tp is not None:
        tp_hits = np.nonzero(lows[start:] <= tp)[0]
        first_tp = (start + tp_hits[0]) if len(tp_hits) else None
    if first_sl is not None and (first_tp is None or first_sl <= first_tp):
        b = first_sl
        return b, (opens[b] if opens[b] >= sl else sl), "SL"
    if first_tp is not None:
        b = first_tp
        return b, (opens[b] if opens[b] <= tp else tp), "TP"
    return None


def simulate_bracket(df: pd.DataFrame, entries: List[Tuple[int, str]],
                     atr: np.ndarray, sl_atr: float, tp_atr: float,
                     symbol: str, costs: Costs) -> List[SimTrade]:
    """fastsim.simulate_entries restricted to the {"type": "bracket"}
    spec (the judged BR24 geometry of every Appendix-A procedure):
    entry at the open of signal_bar+1, ATR taken at the signal bar,
    one position at a time, open position closed at the final close.
    """
    opens = df["open"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    index = df.index
    n = len(df)
    trades: List[SimTrade] = []
    cursor = 0
    ordered = sorted(entries, key=lambda e: e[0])
    for sig_bar, side in ordered:
        if sig_bar < cursor or sig_bar + 1 >= n:
            continue
        a = float(atr[sig_bar])
        if not np.isfinite(a) or a <= 0:
            continue
        entry_bar = sig_bar + 1
        entry_price = float(opens[entry_bar])
        if side == "LONG":
            sl = entry_price - sl_atr * a
            tp = entry_price + tp_atr * a if tp_atr else None
            hit = _first_hit_long(lows, highs, opens, entry_bar, sl, tp)
        else:
            sl = entry_price + sl_atr * a
            tp = entry_price - tp_atr * a if tp_atr else None
            hit = _first_hit_short(lows, highs, opens, entry_bar, sl, tp)
        if hit is not None:
            exit_bar, exit_price, reason = hit
        else:
            exit_bar, exit_price, reason = n - 1, float(closes[n - 1]), "END_OF_DATA"
        trades.append(SimTrade(
            symbol, index[entry_bar], index[exit_bar], side,
            entry_price, float(exit_price),
            _net_return(side, entry_price, float(exit_price), costs),
            reason,
        ))
        cursor = exit_bar
    return trades


def ts_momentum_entries(df: pd.DataFrame, lookback: int,
                        warmup: int) -> List[Tuple[int, str]]:
    """rd2/families2.py sig_ts_momentum + _entries, verbatim: entries
    on ROC sign crosses (long when ROC crosses up through 0, short
    when it crosses down), bars [warmup, n)."""
    roc = df["close"] / df["close"].shift(lookback) - 1.0
    long_sig = (roc > 0) & (roc.shift(1) <= 0)
    short_sig = (roc < 0) & (roc.shift(1) >= 0)
    ls = long_sig.fillna(False).to_numpy(dtype=bool)
    ss = short_sig.fillna(False).to_numpy(dtype=bool)
    out: List[Tuple[int, str]] = []
    for i in range(warmup, len(ls)):
        if ls[i]:
            out.append((i, "LONG"))
        elif ss[i]:
            out.append((i, "SHORT"))
    return out


def trade_metrics(trades: List[SimTrade]) -> Dict[str, Any]:
    """simulator.trade_metrics port (the fields the selection rule
    and the records use)."""
    n = len(trades)
    if n == 0:
        return {"trades": 0, "wins": 0, "win_rate": None,
                "expectancy_net": None, "profit_factor_net": None,
                "avg_win_net": None, "avg_loss_net": None,
                "total_return_net": None, "max_drawdown_net": None}
    nets = np.array([t.net_return for t in trades], dtype=float)
    wins = nets[nets > 0]
    losses = nets[nets < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    if gross_loss > 0:
        pf: Optional[float] = gross_profit / gross_loss
    elif gross_profit > 0:
        pf = float("inf")
    else:
        pf = None
    ordered = sorted(trades, key=lambda t: t.entry_time)
    equity = np.cumprod(1.0 + np.array([t.net_return for t in ordered]))
    curve = np.concatenate([[1.0], equity])
    running_max = np.maximum.accumulate(curve)
    max_dd = float((curve / running_max - 1.0).min()) if len(curve) > 1 else 0.0
    return {
        "trades": n,
        "wins": int(len(wins)),
        "win_rate": float(len(wins) / n),
        "expectancy_net": float(nets.mean()),
        "profit_factor_net": pf,
        "avg_win_net": float(wins.mean()) if len(wins) else None,
        "avg_loss_net": float(losses.mean()) if len(losses) else None,
        "total_return_net": float(np.prod(1.0 + nets) - 1.0),
        "max_drawdown_net": max_dd,
    }


def select_from_streams(
    streams: Dict[str, List[SimTrade]], epoch_start: pd.Timestamp
) -> Tuple[Optional[str], Dict[str, Dict[str, Any]]]:
    """rd/common.py wf_select_judge's selection half, verbatim rule:
    in-sample = trades with entry_time < epoch_start (expanding
    window); candidates need trades > 0 and profit_factor_net not
    None; rank by the legacy key (profit_factor_net, win_rate)
    descending; top 1. Returns (pick or None, per-variant IS table).
    """
    table: Dict[str, Dict[str, Any]] = {}
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    for variant in sorted(streams):
        is_trades = [t for t in streams[variant] if t.entry_time < epoch_start]
        m = trade_metrics(is_trades)
        table[variant] = m
        if m["trades"] > 0 and m["profit_factor_net"] is not None:
            candidates.append((variant, m))
    if not candidates:
        return None, table
    candidates.sort(
        key=lambda vm: (vm[1]["profit_factor_net"], vm[1]["win_rate"]),
        reverse=True,
    )
    return candidates[0][0], table


# ---------------------------------------------------------------------------
# Procedure registry
# ---------------------------------------------------------------------------

FAMILY_SIGNALS: Dict[str, Callable[..., List[Tuple[int, str]]]] = {
    "ts_momentum": ts_momentum_entries,
}

PROCEDURES: Dict[str, Dict[str, Any]] = {
    "ts_momentum__crypto30__1d": {
        "family": "ts_momentum",
        "panel": "crypto30",
        "timeframe": "1d",
        "variants": {"roc24": 24, "roc42": 42, "roc72": 72, "roc168": 168},
        "sl_atr": 2.0,
        "tp_atr": 4.0,
        "warmup": 260,
        "costs": {"fee_bps_per_side": 5.0, "slip_bps_per_side": 3.0},
        "epoch": "calendar_month_utc",
        "judged": {
            "pooled_oos_trades": 453,
            "pooled_pf": 1.1694,
            "pooled_expectancy_pct": 1.4096,
            "pooled_win_rate": 0.3664,
            "positive_folds": 3,
            "picks": ["roc24", "roc168", "roc72", "roc42", "roc42"],
        },
    },
}


def register_procedure(procedure_id: str, spec: Dict[str, Any]) -> None:
    """Register another Appendix-A procedure. The spec's family must
    have a ported signal function in FAMILY_SIGNALS."""
    if spec["family"] not in FAMILY_SIGNALS:
        raise ValueError(
            f"family {spec['family']!r} has no ported signal function; "
            "port it into FAMILY_SIGNALS before registering"
        )
    PROCEDURES[procedure_id] = spec


# ---------------------------------------------------------------------------
# Selection run
# ---------------------------------------------------------------------------

def epoch_start_for(now: Optional[pd.Timestamp] = None) -> pd.Timestamp:
    """Start of the current calendar-month UTC epoch."""
    if now is None:
        now = pd.Timestamp.now(tz="UTC")
    return pd.Timestamp(year=now.year, month=now.month, day=1, tz="UTC")


def run_selection(procedure_id: str, frames: Dict[str, pd.DataFrame],
                  epoch_start: pd.Timestamp) -> Dict[str, Any]:
    """Simulate every variant over bars closed before epoch_start and
    apply the judged selection rule. Pure and causal: frames are
    trimmed to bars whose close time is <= epoch_start before any
    simulation, so no bar of the new epoch can influence the pick.
    """
    spec = PROCEDURES[procedure_id]
    tf = spec["timeframe"]
    bar_seconds = BAR_SECONDS[tf]
    signal_fn = FAMILY_SIGNALS[spec["family"]]
    costs = Costs(**spec["costs"])
    streams: Dict[str, List[SimTrade]] = {v: [] for v in spec["variants"]}
    bars_used: Dict[str, int] = {}
    for symbol in sorted(frames):
        df = frames[symbol]
        if df is None or len(df) == 0:
            continue
        close_times = df.index + pd.Timedelta(seconds=bar_seconds)
        trimmed = df[close_times <= epoch_start]
        bars_used[symbol] = int(len(trimmed))
        if len(trimmed) <= spec["warmup"] + 1:
            continue
        atr = atr14(trimmed).to_numpy()
        for variant, param in spec["variants"].items():
            entries = signal_fn(trimmed, param, spec["warmup"])
            streams[variant].extend(
                simulate_bracket(
                    trimmed, entries, atr, spec["sl_atr"], spec["tp_atr"],
                    symbol, costs,
                )
            )
    pick, table = select_from_streams(streams, epoch_start)
    return {
        "procedure": procedure_id,
        "epoch_start": epoch_start.isoformat(),
        "decided_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "pick": pick,
        "is_table": {
            v: {
                k: (None if val is None or (isinstance(val, float) and not np.isfinite(val)) else val)
                for k, val in m.items()
            }
            for v, m in table.items()
        },
        "history": {
            "symbols": len(bars_used),
            "bars_min": min(bars_used.values()) if bars_used else 0,
            "bars_max": max(bars_used.values()) if bars_used else 0,
        },
    }


# ---------------------------------------------------------------------------
# Persistence: current-pick state + append-only selection log
# ---------------------------------------------------------------------------

def state_dir() -> str:
    override = os.environ.get("WF_SELECT_STATE_DIR")
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "wf_select")


def _state_path(procedure_id: str) -> str:
    return os.path.join(state_dir(), f"{procedure_id}.json")


def _log_path(procedure_id: str) -> str:
    return os.path.join(state_dir(), f"{procedure_id}_selections.jsonl")


def load_state(procedure_id: str) -> Optional[Dict[str, Any]]:
    try:
        with open(_state_path(procedure_id), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def current_pick(procedure_id: str) -> Optional[str]:
    state = load_state(procedure_id)
    if not state:
        return None
    return state.get("pick")


def save_selection(decision: Dict[str, Any]) -> None:
    """Persist a selection decision: replace the current-pick state
    atomically and append the full decision to the selection log."""
    os.makedirs(state_dir(), exist_ok=True)
    procedure_id = decision["procedure"]
    path = _state_path(procedure_id)
    tmp = f"{path}.tmp.{int(time.time() * 1000)}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(decision, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)
    with open(_log_path(procedure_id), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(decision, sort_keys=True) + "\n")
