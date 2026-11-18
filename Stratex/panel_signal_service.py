"""panel_signal_service — TASK-STR-FWD-024: cross-sectional (panel)
signal machinery for the FORWARD_TEST lane.

Two near-miss audit rows could not be wired by the wave-2 family
ports (evidence: WAVE2-D.md) because they are CROSS-SECTIONAL: at
each rebalance bar they rank the whole CRYPTO30 panel against
itself and long/short the extremes —

- xs_momentum / roc60_rb20 (families2.xs_entries): rank by ROC(60);
  long the top-3, short the bottom-3; rebalance every 20 bars;
  bracket_time SL 3.0 x ATR(14), TP 6.0 x ATR(14), max_bars 20.
  Judged record: 258 pooled OOS trades, expectancy +0.865%/trade,
  PF 1.1347, win rate 0.5194, 2/5 positive folds.
- xs_lowvol / lv20_r10 (families3.xs_custom_entries via
  xs_lowvol_fn): rank by the 20-bar rolling stdev of daily returns;
  long the 3 LOWEST-volatility symbols, short the 3 HIGHEST;
  rebalance every 10 bars; bracket_time SL 2.0 x ATR(14),
  TP 4.0 x ATR(14), max_bars 10. Judged record: 510 pooled OOS
  trades, expectancy +0.716%/trade, PF 1.1790, win rate 0.5392,
  4/5 positive folds.

The daemon's signal contract is per-symbol ``get_signal(df)`` — it
never sees the panel — so, following the wf_select_service pattern
(TASK-STR-FWD-022), the ranking lives here:

- The daemon hook (autonomy/run_daemon.py
  _maybe_run_panel_rankings) gathers the lane panel's candle
  history from an attested demo venue on a throttled cadence and
  calls run_membership(), which evaluates the judged ranking over
  bars already closed and persists the CURRENT membership: for
  each picked symbol, its side and the signal bar at which its
  entry fires (state file + append-only membership log, so every
  decision is auditable with its full ranked table).
- The entrant modules (strategy_xs_momentum.py,
  strategy_xs_lowvol.py) only look their own symbol up in the
  persisted membership: they fire when the membership's signal bar
  for their symbol is the frame's last closed bar, with the judged
  bracket. The daemon never ranks anything at signal time.
- Fail-closed: a ranking run that cannot be computed (reference
  series missing, panel not aligned to the judged anchor, fewer
  than 2k rankable symbols at every rebalance) changes nothing —
  the previous membership stays in place and the refusal is
  logged. save_membership() additionally refuses to overwrite a
  membership with one whose panel data has not advanced or whose
  rebalance bar moved backwards.

Fidelity: the ranking functions below are line-faithful ports of
rigorous_backtest/rd2/families2.py ``xs_entries`` and
rigorous_backtest/rd2/families3.py ``xs_custom_entries`` (the
xs_lowvol_fn instantiation), generalised only by an ``offset``
parameter (bars between the judged series anchor and the supplied
frames' first bar; offset=0 reproduces the harness exactly).
tests/test_fwd024_panel_xs.py pins the ports against the harness
on the full RD-002 cache panel: entry lists identical, and the
judged brackets reproduce the recorded pooled OOS metrics
(258 / 510 trades, PF 1.1347 / 1.1790) exactly.

Disclosed live translations: (1) the judged rebalance grid is
anchored at the RD-002 series start (2022-01-01 00:00 UTC for
CRYPTO30 1d — the first bar of the reference symbol's judged
series); the offset mechanism reproduces that grid phase from bar
timestamps whatever window the venue returns, and the span used is
recorded in every membership decision. (2) Live history is the
venue candle history (the hook requests 1500 bars), not the
judged cache from 2022. (3) The judged books are per-symbol
standalone simulations pooled; live, the panel shares one demo
account with one venue position per symbol, so a symbol held by
another strategy blocks that scan's xs entry (the daemon's
standing rule) and entries missed while the ranking hook is down
are never backfilled — the membership only ever fires on its own
rebalance bar.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

BAR_SECONDS = {"1d": 24 * 3600}

# The judged CRYPTO30 panel, in the judged order (rd2/panels.py
# CRYPTO30; identical to config_strategy.CRYPTO30_SYMBOLS — pinned
# by test). The FIRST symbol is the reference series: the harness
# aligns every other series to its index.
PANEL_SYMBOLS: Tuple[str, ...] = (
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT", "TRXUSDT", "AVAXUSDT",
    "NEARUSDT", "ATOMUSDT", "UNIUSDT", "ETCUSDT", "BCHUSDT", "FILUSDT",
    "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT", "XLMUSDT",
    "HBARUSDT", "ALGOUSDT", "VETUSDT", "SANDUSDT", "MANAUSDT", "AAVEUSDT",
)

# First bar of the reference symbol's judged 1d series (the RD-002
# cache start). The rebalance grid is positions >= warmup from this
# anchor, stepping `rebalance` bars.
PANEL_ANCHOR = "2022-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Judged-logic ports (rd/common atr; rd2 families2/families3 xs rankers)
# ---------------------------------------------------------------------------

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


def _xs_run(panel_dfs: Dict[str, pd.DataFrame], scores: Dict[str, pd.Series],
            long_high: bool, rebalance: int, k: int, warmup: int,
            offset: int = 0):
    """Shared skeleton of families2.xs_entries / families3.
    xs_custom_entries. ``scores`` are per-symbol score series on
    each symbol's own closes reindexed to the reference index
    (ffill), exactly as the harness builds them. long_high=True
    reproduces xs_entries (rank descending, long the top-k);
    long_high=False reproduces xs_custom_entries with
    long_low=True (rank ascending, long the lowest-k). The sort is
    over (score, symbol) tuples in both cases, so tie-breaking
    matches the harness bit-for-bit.

    ``offset`` shifts the rebalance grid: grid positions are
    warmup, warmup+rebalance, ... counted from the judged anchor;
    the supplied frames start ``offset`` bars after the anchor, so
    grid position j is evaluated at local bar j - offset. With
    offset=0 this is the harness iteration exactly.

    Returns (entries, rebalances, last_ranked): entries maps each
    symbol to [(bar_pos, side, grid_pos), ...]; rebalances lists
    the grid positions at which picks were actually made (at least
    one pick survived the stale-series mapping); last_ranked is
    the (score, symbol) ranked table of the final effective
    rebalance, in ranked order.
    """
    ref = next(iter(panel_dfs.values()))
    idx = ref.index
    out: Dict[str, list] = {s: [] for s in panel_dfs}
    rebalances: List[int] = []
    last_ranked: List[Tuple[float, str]] = []
    n = len(idx)
    bar = idx[1] - idx[0] if n > 1 else None
    j = warmup
    while j < offset + n - 1:
        jl = j - offset
        if jl >= 0:
            if long_high:
                ranked = sorted(
                    ((scores[s].iloc[jl], s) for s in scores
                     if pd.notna(scores[s].iloc[jl])),
                    reverse=True,
                )
            else:
                ranked = sorted(
                    (scores[s].iloc[jl], s) for s in scores
                    if pd.notna(scores[s].iloc[jl])
                )
            if len(ranked) >= 2 * k:
                picks = [(s, "LONG") for _, s in ranked[:k]] + \
                        [(s, "SHORT") for _, s in ranked[-k:]]
                t = idx[jl]
                made = False
                for sym, side in picks:
                    df = panel_dfs[sym]
                    pos = df.index.get_indexer([t], method="pad")[0]
                    if pos < 0 or pos >= len(df) - 1:
                        continue
                    if bar is not None and df.index[pos] < t - 3 * bar:
                        continue  # stale series (long market closure)
                    out[sym].append((int(pos), side, int(j)))
                    made = True
                if made:
                    rebalances.append(int(j))
                    last_ranked = [(float(v), s) for v, s in ranked]
        j += rebalance
    return out, rebalances, last_ranked


def xs_momentum_entries(panel_dfs: Dict[str, pd.DataFrame], lookback: int,
                        rebalance: int, k: int, warmup: int,
                        offset: int = 0) -> Dict[str, List[Tuple[int, str]]]:
    """families2.xs_entries, verbatim apart from the offset
    generalisation: rank the panel by ROC(lookback) at each
    rebalance bar; long the top-k, short the bottom-k."""
    ref = next(iter(panel_dfs.values()))
    idx = ref.index
    closes = {}
    for sym, df in panel_dfs.items():
        closes[sym] = df["close"].reindex(idx).ffill()
    roc = {s: (c / c.shift(lookback) - 1.0) for s, c in closes.items()}
    out, _, _ = _xs_run(panel_dfs, roc, True, rebalance, k, warmup, offset)
    return {s: [(pos, side) for pos, side, _j in entries]
            for s, entries in out.items()}


def xs_lowvol_entries(panel_dfs: Dict[str, pd.DataFrame], warmup: int,
                      offset: int = 0, rebalance: int = 10, k: int = 3,
                      vol_window: int = 20) -> Dict[str, List[Tuple[int, str]]]:
    """families3.xs_lowvol_fn, verbatim apart from the offset
    generalisation: score = rolling stdev of pct_change over
    ``vol_window`` bars; long the k LOWEST scores, short the k
    HIGHEST (xs_custom_entries with long_low=True)."""
    ref = next(iter(panel_dfs.values()))
    idx = ref.index
    closes = {s: df["close"].reindex(idx).ffill()
              for s, df in panel_dfs.items()}
    scores = {s: c.pct_change().rolling(vol_window).std()
              for s, c in closes.items()}
    out, _, _ = _xs_run(panel_dfs, scores, False, rebalance, k, warmup, offset)
    return {s: [(pos, side) for pos, side, _j in entries]
            for s, entries in out.items()}


def _stream_entries(stream: Dict[str, Any],
                    panel_dfs: Dict[str, pd.DataFrame], offset: int):
    """(entries, rebalances, last_ranked) for one registered
    stream over the supplied panel frames."""
    ref = next(iter(panel_dfs.values()))
    idx = ref.index
    closes = {}
    for sym, df in panel_dfs.items():
        closes[sym] = df["close"].reindex(idx).ffill()
    if stream["score"] == "roc":
        scores = {s: (c / c.shift(int(stream["lookback"])) - 1.0)
                  for s, c in closes.items()}
        long_high = True
    elif stream["score"] == "lowvol":
        scores = {s: c.pct_change().rolling(int(stream["vol_window"])).std()
                  for s, c in closes.items()}
        long_high = False
    else:  # pragma: no cover - registry guard
        raise ValueError(f"unknown score kind {stream['score']!r}")
    return _xs_run(panel_dfs, scores, long_high, int(stream["rebalance"]),
                   int(stream["k"]), int(stream["warmup"]), offset)


# ---------------------------------------------------------------------------
# Stream registry
# ---------------------------------------------------------------------------

STREAMS: Dict[str, Dict[str, Any]] = {
    "xs_momentum__crypto30__1d": {
        "family": "xs_momentum",
        "variant": "roc60_rb20",
        "panel": "crypto30",
        "timeframe": "1d",
        "score": "roc",
        "lookback": 60,
        "rebalance": 20,
        "k": 3,
        "warmup": 260,
        "sl_atr": 3.0,
        "tp_atr": 6.0,
        "max_bars": 20,
        "anchor": PANEL_ANCHOR,
        "judged": {
            "oos_trades": 258,
            "oos_expectancy_pct": 0.865,
            "oos_profit_factor": 1.1347,
            "oos_win_rate": 0.5194,
            "positive_folds": 2,
        },
    },
    "xs_lowvol__crypto30__1d": {
        "family": "xs_lowvol",
        "variant": "lv20_r10",
        "panel": "crypto30",
        "timeframe": "1d",
        "score": "lowvol",
        "vol_window": 20,
        "rebalance": 10,
        "k": 3,
        "warmup": 260,
        "sl_atr": 2.0,
        "tp_atr": 4.0,
        "max_bars": 10,
        "anchor": PANEL_ANCHOR,
        "judged": {
            "oos_trades": 510,
            "oos_expectancy_pct": 0.716,
            "oos_profit_factor": 1.1790,
            "oos_win_rate": 0.5392,
            "positive_folds": 4,
        },
    },
}


# ---------------------------------------------------------------------------
# Membership run (pure, causal)
# ---------------------------------------------------------------------------

def _fail(stream_id: str, reason: str) -> Dict[str, Any]:
    return {"ok": False, "stream": stream_id, "reason": reason,
            "computed_at": pd.Timestamp.now(tz="UTC").isoformat()}


def run_membership(stream_id: str,
                   frames: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """Evaluate the judged ranking for one stream over the supplied
    panel frames and return the CURRENT membership decision: the
    picks of the latest effective rebalance bar, each with the
    per-symbol signal bar at which its entry fires.

    Pure and causal: scores at a rebalance bar use only bars up to
    that bar (trailing windows on the aligned closes), and the
    decision names only the latest effective rebalance, so no
    future bar can influence a membership that fires today.

    Fail-closed: returns {"ok": False, ...} — and changes no
    state — when the reference series is missing, the frames are
    not aligned to the judged anchor grid, or no rebalance in the
    supplied history ever ranked 2k symbols.
    """
    stream = STREAMS[stream_id]
    tf = stream["timeframe"]
    bar_seconds = BAR_SECONDS[tf]
    panel = [s for s in PANEL_SYMBOLS if s in frames]
    ref_sym = PANEL_SYMBOLS[0]
    if ref_sym not in frames:
        return _fail(stream_id, f"reference series {ref_sym} missing")
    panel_dfs = {s: frames[s] for s in panel}
    ref = panel_dfs[ref_sym]
    if ref is None or len(ref) < 2:
        return _fail(stream_id, "reference series empty")
    anchor = pd.Timestamp(stream["anchor"])
    first = ref.index[0]
    offset_f = (first - anchor).total_seconds() / bar_seconds
    offset = int(round(offset_f))
    if offset < 0 or abs(offset_f - offset) > 1e-6:
        return _fail(
            stream_id,
            f"reference series starts at {first.isoformat()}, not on the "
            f"judged anchor grid ({stream['anchor']})",
        )
    try:
        entries, rebalances, last_ranked = _stream_entries(
            stream, panel_dfs, offset)
    except Exception as e:
        return _fail(stream_id, f"ranking failed: {e}")
    if not rebalances:
        return _fail(
            stream_id,
            "no effective rebalance in the supplied history "
            "(never ranked 2k symbols)",
        )
    latest = rebalances[-1]
    membership: Dict[str, Dict[str, Any]] = {}
    for sym, sym_entries in entries.items():
        for pos, side, j in sym_entries:
            if j == latest:
                bar_time = panel_dfs[sym].index[pos]
                membership[sym] = {
                    "side": side,
                    "signal_bar": bar_time.isoformat(),
                    "signal_bar_epoch": int(bar_time.timestamp()),
                }
    ref_idx = ref.index
    rebalance_time = ref_idx[latest - offset]
    return {
        "ok": True,
        "stream": stream_id,
        "computed_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "rebalance_bar": rebalance_time.isoformat(),
        "rebalance_epoch": int(rebalance_time.timestamp()),
        "panel_asof": ref_idx[-1].isoformat(),
        "panel_asof_epoch": int(ref_idx[-1].timestamp()),
        "entries": membership,
        "ranked": [
            {"symbol": s, "score": v} for v, s in last_ranked
        ],
        "panel": {
            "symbols_present": len(panel),
            "symbols_ranked": len(last_ranked),
            "offset": offset,
            "bars_ref": int(len(ref_idx)),
        },
    }


# ---------------------------------------------------------------------------
# Persistence: current-membership state + append-only membership log
# ---------------------------------------------------------------------------

def state_dir() -> str:
    override = os.environ.get("PANEL_SIGNAL_STATE_DIR")
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "panel_signal")


def _state_path(stream_id: str) -> str:
    return os.path.join(state_dir(), f"{stream_id}.json")


def _log_path(stream_id: str) -> str:
    return os.path.join(state_dir(), f"{stream_id}_memberships.jsonl")


def load_membership(stream_id: str) -> Optional[Dict[str, Any]]:
    try:
        with open(_state_path(stream_id), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def current_entries(stream_id: str) -> Dict[str, Dict[str, Any]]:
    state = load_membership(stream_id)
    if not state:
        return {}
    return state.get("entries") or {}


def save_membership(decision: Dict[str, Any]) -> bool:
    """Persist a membership decision: replace the current state
    atomically and append the full decision to the membership log.

    Refuses (returns False, changes nothing) when the decision is
    a failure record, when its panel data has not advanced past
    the persisted state's (stale panel), or when its rebalance bar
    is older than the persisted one — a stale or regressed ranking
    run must never displace a fresher membership.
    """
    if not decision.get("ok"):
        return False
    stream_id = decision["stream"]
    prev = load_membership(stream_id)
    if prev is not None:
        if decision["panel_asof_epoch"] <= int(prev.get("panel_asof_epoch", 0)):
            return False
        if decision["rebalance_epoch"] < int(prev.get("rebalance_epoch", 0)):
            return False
    os.makedirs(state_dir(), exist_ok=True)
    path = _state_path(stream_id)
    tmp = f"{path}.tmp.{int(time.time() * 1000)}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(decision, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)
    with open(_log_path(stream_id), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(decision, sort_keys=True) + "\n")
    return True
