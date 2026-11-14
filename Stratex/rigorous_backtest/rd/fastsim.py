"""Fast trade simulation with the harness's MODULE convention plus exit
engineering options (TASK-STR-RD-001).

Semantics (identical to simulator.simulate_module unless stated):
- a signal produced on the close of bar i enters at the OPEN of bar i+1;
- the entry bar itself is exit-checked (a live bracket is live immediately);
- a bar that gaps through a level fills at the bar open;
- when stop and target are both inside one bar, the STOP is hit first;
- one position at a time; signals arriving while a position is open are
  ignored (same as simulate_module, which only acts on signals when flat);
- a position still open at the end is closed at the final close.

Entry input is a list of (signal_bar, side) plus the ATR series; bracket
levels are anchored to the ENTRY price: level = entry +/- mult * ATR[signal
bar]. (Production modules anchor to the signal-bar close instead; for the
new research families the entry-price anchor is the declared convention,
and it is the more conservative of the two when price gaps overnight.)

Exit specs (dicts):
  {"type": "bracket", "sl_atr": x, "tp_atr": y}
  {"type": "trail", "sl_atr": x, "trail_atr": y}          # ATR trailing stop, no fixed TP
  {"type": "bracket_trail", "sl_atr": x, "tp_atr": y, "trail_atr": z, "trail_arm_atr": w}
  {"type": "bracket_time", "sl_atr": x, "tp_atr": y, "max_bars": n}
Costs are applied exactly as the harness does (simulator._net_return).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..simulator import Costs, Trade, _net_return


def _first_hit_long(lows: np.ndarray, highs: np.ndarray, opens: np.ndarray,
                    start: int, sl: float, tp: float | None):
    """First exit at/after `start` for a LONG with fixed levels.

    Returns (bar, price, reason) or None. Stop checked first within a bar;
    gap-through fills at the open.
    """
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


def _first_hit_short(lows: np.ndarray, highs: np.ndarray, opens: np.ndarray,
                     start: int, sl: float, tp: float | None):
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


def _simulate_trail(df: pd.DataFrame, entry_bar: int, side: str, entry_price: float,
                    atr_entry: float, spec: dict, costs: Costs, symbol: str):
    """Bar-loop simulation for trailing-stop specs (trades are sparse)."""
    opens = df["open"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    index = df.index
    n = len(df)
    sl_mult = float(spec["sl_atr"])
    tp_mult = spec.get("tp_atr")
    trail_mult = float(spec["trail_atr"])
    arm_mult = float(spec.get("trail_arm_atr", 0.0))
    max_bars = spec.get("max_bars")
    if side == "LONG":
        stop = entry_price - sl_mult * atr_entry
        target = entry_price + float(tp_mult) * atr_entry if tp_mult else None
        best = entry_price
    else:
        stop = entry_price + sl_mult * atr_entry
        target = entry_price - float(tp_mult) * atr_entry if tp_mult else None
        best = entry_price
    armed = arm_mult <= 0.0
    exit_bar = exit_price = reason = None
    j = entry_bar
    while j < n:
        o, h, l = opens[j], highs[j], lows[j]
        if side == "LONG":
            if o <= stop:
                exit_bar, exit_price, reason = j, o, "TRAIL" if armed and stop > entry_price - sl_mult * atr_entry else "SL"
                break
            if l <= stop:
                exit_bar, exit_price, reason = j, stop, "TRAIL" if armed and stop > entry_price - sl_mult * atr_entry else "SL"
                break
            if target is not None and h >= target:
                exit_bar, exit_price, reason = j, (o if o >= target else target), "TP"
                break
            if h > best:
                best = h
            if not armed and best >= entry_price + arm_mult * atr_entry:
                armed = True
            if armed:
                stop = max(stop, best - trail_mult * atr_entry)
        else:
            if o >= stop:
                exit_bar, exit_price, reason = j, o, "TRAIL" if armed and stop < entry_price + sl_mult * atr_entry else "SL"
                break
            if h >= stop:
                exit_bar, exit_price, reason = j, stop, "TRAIL" if armed and stop < entry_price + sl_mult * atr_entry else "SL"
                break
            if target is not None and l <= target:
                exit_bar, exit_price, reason = j, (o if o <= target else target), "TP"
                break
            if l < best:
                best = l
            if not armed and best <= entry_price - arm_mult * atr_entry:
                armed = True
            if armed:
                stop = min(stop, best + trail_mult * atr_entry)
        if max_bars is not None and j - entry_bar + 1 >= int(max_bars):
            exit_bar, exit_price, reason = j, closes[j], "TIME"
            break
        j += 1
    if exit_bar is None:
        exit_bar, exit_price, reason = n - 1, closes[n - 1], "END_OF_DATA"
    return Trade(symbol, index[entry_bar], index[exit_bar], side, entry_price,
                 float(exit_price), _net_return(side, entry_price, float(exit_price), costs),
                 reason), exit_bar


def simulate_entries(df: pd.DataFrame, entries: list[tuple[int, str]],
                     atr: np.ndarray, spec: dict, symbol: str,
                     costs: Costs) -> list[Trade]:
    """Simulate (signal_bar, side) entries under an exit spec.

    Entry occurs at the open of signal_bar+1; ATR is taken at the signal bar.
    Entries are consumed in bar order; entries inside an open position are
    skipped (one position at a time).
    """
    opens = df["open"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    index = df.index
    n = len(df)
    trades: list[Trade] = []
    cursor = 0  # earliest signal bar we may still act on
    ordered = sorted(entries, key=lambda e: e[0])
    etype = spec["type"]
    for sig_bar, side in ordered:
        if sig_bar < cursor or sig_bar + 1 >= n:
            continue
        a = float(atr[sig_bar])
        if not np.isfinite(a) or a <= 0:
            continue
        entry_bar = sig_bar + 1
        entry_price = float(opens[entry_bar])
        if etype in ("trail", "bracket_trail"):
            trade, exit_bar = _simulate_trail(df, entry_bar, side, entry_price,
                                              a, spec, costs, symbol)
            trades.append(trade)
            cursor = exit_bar  # next signal must be after the exit bar's close
            continue
        if side == "LONG":
            sl = entry_price - float(spec["sl_atr"]) * a
            tp = entry_price + float(spec["tp_atr"]) * a if spec.get("tp_atr") else None
            hit = _first_hit_long(lows, highs, opens, entry_bar, sl, tp)
        else:
            sl = entry_price + float(spec["sl_atr"]) * a
            tp = entry_price - float(spec["tp_atr"]) * a if spec.get("tp_atr") else None
            hit = _first_hit_short(lows, highs, opens, entry_bar, sl, tp)
        max_bars = spec.get("max_bars") if etype == "bracket_time" else None
        if hit is not None and (max_bars is None or hit[0] - entry_bar < int(max_bars)):
            exit_bar, exit_price, reason = hit
        elif max_bars is not None:
            exit_bar = min(entry_bar + int(max_bars) - 1, n - 1)
            exit_price, reason = float(closes[exit_bar]), "TIME"
            if hit is not None and hit[0] <= exit_bar:
                exit_bar, exit_price, reason = hit
        else:
            exit_bar, exit_price, reason = n - 1, float(closes[n - 1]), "END_OF_DATA"
        trades.append(Trade(symbol, index[entry_bar], index[exit_bar], side,
                            entry_price, float(exit_price),
                            _net_return(side, entry_price, float(exit_price), costs),
                            reason))
        cursor = exit_bar
    return trades
