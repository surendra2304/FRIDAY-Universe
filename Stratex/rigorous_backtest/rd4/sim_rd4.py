"""Per-entry bracket simulation for TASK-STR-RD-004's scale mode.

Identical semantics to rd.fastsim.simulate_entries (MODULE convention:
entry at the open of signal_bar+1, entry bar exit-checked, gap-through
fills at the open, stop before target within a bar, one position at a
time, end-of-data close at the final close), except the bracket
multiples are per-entry: mult = base_mult * f, where f is the regime
scale factor (f = 1 for base/gate modes). With all f = 1 the trade list
is identical to simulate_entries under a fixed bracket spec — the
runner asserts this on a probe cell before trusting any number.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..rd.fastsim import _first_hit_long, _first_hit_short
from ..simulator import Costs, Trade, _net_return

SL_BASE = 2.0
TP_BASE = 4.0


def simulate_scaled(df: pd.DataFrame, entries: list[tuple[int, str, float]],
                    atr: np.ndarray, symbol: str,
                    costs: Costs) -> list[Trade]:
    opens = df["open"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    index = df.index
    n = len(df)
    trades: list[Trade] = []
    cursor = 0
    for sig_bar, side, f in sorted(entries, key=lambda e: e[0]):
        if sig_bar < cursor or sig_bar + 1 >= n:
            continue
        a = float(atr[sig_bar])
        if not np.isfinite(a) or a <= 0:
            continue
        entry_bar = sig_bar + 1
        entry_price = float(opens[entry_bar])
        sl_mult = SL_BASE * f
        tp_mult = TP_BASE * f
        if side == "LONG":
            sl = entry_price - sl_mult * a
            tp = entry_price + tp_mult * a
            hit = _first_hit_long(lows, highs, opens, entry_bar, sl, tp)
        else:
            sl = entry_price + sl_mult * a
            tp = entry_price - tp_mult * a
            hit = _first_hit_short(lows, highs, opens, entry_bar, sl, tp)
        if hit is not None:
            exit_bar, exit_price, reason = hit
        else:
            exit_bar, exit_price, reason = n - 1, float(closes[n - 1]), \
                "END_OF_DATA"
        trades.append(Trade(symbol, index[entry_bar], index[exit_bar], side,
                            entry_price, float(exit_price),
                            _net_return(side, entry_price,
                                        float(exit_price), costs),
                            reason))
        cursor = exit_bar
    return trades
