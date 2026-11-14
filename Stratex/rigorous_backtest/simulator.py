"""Bar-by-bar trade simulation with an explicit, conservative cost model.

Two entry conventions exist, each faithful to the claim it tests:

- MODULE (default): the convention used to judge production strategy modules.
  A signal produced on the close of bar i enters at the OPEN of bar i+1 (no
  look-ahead). The signal's absolute stop/target levels are kept. The entry
  bar itself is exit-checked (a live bracket would be live immediately);
  a bar that gaps through a level fills at the bar open; when stop and target
  are both inside one bar, the STOP is assumed hit first (worst case).

- FACTORY_ORIGINAL: the exact semantics of the legacy mass_backtester whose
  rankings promoted the factory winners — a signal on bar i enters at the
  CLOSE of bar i+1, exits are checked from bar i+2 onward, stop checked
  before target. Used only to re-test the factory selection claim under its
  own procedure (with honest walk-forward windows and honest costs added).

Costs (stated in every result): Binance USDT-M futures taker fee 5 bps per
side, plus 3 bps per side for spread + slippage, applied adversely in price
space. Round trip total = 16 bps. P&L fractions are relative to entry price.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Costs:
    fee_bps_per_side: float = 5.0
    slip_bps_per_side: float = 3.0

    @property
    def per_side_rate(self) -> float:
        return (self.fee_bps_per_side + self.slip_bps_per_side) / 10000.0

    def describe(self) -> dict:
        return {
            "venue_model": "Binance USDT-M futures, taker",
            "fee_bps_per_side": self.fee_bps_per_side,
            "spread_slippage_bps_per_side": self.slip_bps_per_side,
            "round_trip_bps": 2 * (self.fee_bps_per_side + self.slip_bps_per_side),
        }


@dataclass
class Trade:
    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: str  # "LONG" | "SHORT"
    entry_price: float  # raw (pre-cost) fill reference
    exit_price: float   # raw (pre-cost) fill reference
    net_return: float   # fraction of entry price, net of all costs
    exit_reason: str    # "TP" | "SL" | "END_OF_DATA"


def _net_return(side: str, entry: float, exit_: float, costs: Costs) -> float:
    r = costs.per_side_rate
    if side == "LONG":
        entry_adj = entry * (1 + r)
        exit_adj = exit_ * (1 - r)
        return (exit_adj - entry_adj) / entry_adj
    entry_adj = entry * (1 - r)
    exit_adj = exit_ * (1 + r)
    return (entry_adj - exit_adj) / entry_adj


def simulate_module(df: pd.DataFrame, signals: list[tuple[int, str, float, float]],
                    symbol: str, costs: Costs) -> list[Trade]:
    """MODULE convention. `signals` = (signal_bar_idx, side, sl_price, tp_price)
    evaluated on the close of that bar. One position at a time."""
    opens = df["open"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    index = df.index
    n = len(df)
    sig_by_bar = {i: (side, sl, tp) for (i, side, sl, tp) in signals}
    trades: list[Trade] = []
    pos = None  # (side, sl, tp, entry_bar, entry_price)
    for i in range(n):
        if pos is not None:
            side, sl, tp, entry_bar, entry_price = pos
            exit_price = None
            reason = None
            if side == "LONG":
                if opens[i] <= sl:
                    exit_price, reason = opens[i], "SL"
                elif lows[i] <= sl:
                    exit_price, reason = sl, "SL"
                elif opens[i] >= tp:
                    exit_price, reason = opens[i], "TP"
                elif highs[i] >= tp:
                    exit_price, reason = tp, "TP"
            else:
                if opens[i] >= sl:
                    exit_price, reason = opens[i], "SL"
                elif highs[i] >= sl:
                    exit_price, reason = sl, "SL"
                elif opens[i] <= tp:
                    exit_price, reason = opens[i], "TP"
                elif lows[i] <= tp:
                    exit_price, reason = tp, "TP"
            if exit_price is not None:
                trades.append(Trade(symbol, index[entry_bar], index[i],
                                    side, entry_price, exit_price,
                                    _net_return(side, entry_price, exit_price, costs),
                                    reason))
                pos = None
        if pos is None and i in sig_by_bar and i + 1 < n:
            side, sl, tp = sig_by_bar[i]
            entry_bar = i + 1
            entry_price = opens[entry_bar]
            # Entry bar is exit-checked on the next loop pass via pos state;
            # to check the entry bar itself we test it right away:
            pos = (side, sl, tp, entry_bar, entry_price)
            j = entry_bar
            exit_price = None
            reason = None
            if side == "LONG":
                if lows[j] <= sl:
                    exit_price, reason = (opens[j] if opens[j] <= sl else sl), "SL"
                elif highs[j] >= tp:
                    exit_price, reason = (opens[j] if opens[j] >= tp else tp), "TP"
            else:
                if highs[j] >= sl:
                    exit_price, reason = (opens[j] if opens[j] >= sl else sl), "SL"
                elif lows[j] <= tp:
                    exit_price, reason = (opens[j] if opens[j] <= tp else tp), "TP"
            if exit_price is not None:
                trades.append(Trade(symbol, index[entry_bar], index[j],
                                    side, entry_price, exit_price,
                                    _net_return(side, entry_price, exit_price, costs),
                                    reason))
                pos = None
    if pos is not None:
        side, sl, tp, entry_bar, entry_price = pos
        exit_price = closes[n - 1]
        trades.append(Trade(symbol, index[entry_bar], index[n - 1],
                            side, entry_price, exit_price,
                            _net_return(side, entry_price, exit_price, costs),
                            "END_OF_DATA"))
    return trades


def simulate_factory_original(df: pd.DataFrame, long_sig: np.ndarray, short_sig: np.ndarray,
                              sl_mult: float, tp_mult: float, atr: np.ndarray,
                              symbol: str, costs: Costs) -> list[Trade]:
    """FACTORY_ORIGINAL convention — a faithful re-implementation of the legacy
    mass_backtester's trade loop (signal on bar i -> enter at close of bar
    i+1; exits checked from bar i+2; stop before target), returning timestamped
    trades and applying this harness's cost model in price space. Equivalence
    with the legacy function is asserted by the test-suite replication check.
    """
    closes = df["close"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    index = df.index
    n = len(df)
    trades: list[Trade] = []
    in_pos = False
    side = ""
    entry_p = sl_p = tp_p = 0.0
    entry_bar = -1
    for i in range(30, n):
        if not in_pos:
            if long_sig[i - 1] and atr[i - 1] > 0:
                in_pos, side = True, "LONG"
                entry_p = closes[i]
                sl_p = entry_p - sl_mult * atr[i - 1]
                tp_p = entry_p + tp_mult * atr[i - 1]
                entry_bar = i
            elif short_sig[i - 1] and atr[i - 1] > 0:
                in_pos, side = True, "SHORT"
                entry_p = closes[i]
                sl_p = entry_p + sl_mult * atr[i - 1]
                tp_p = entry_p - tp_mult * atr[i - 1]
                entry_bar = i
        else:
            exit_price = None
            reason = None
            if side == "LONG":
                if lows[i] <= sl_p:
                    exit_price, reason = sl_p, "SL"
                elif highs[i] >= tp_p:
                    exit_price, reason = tp_p, "TP"
            else:
                if highs[i] >= sl_p:
                    exit_price, reason = sl_p, "SL"
                elif lows[i] <= tp_p:
                    exit_price, reason = tp_p, "TP"
            if exit_price is not None:
                trades.append(Trade(symbol, index[entry_bar], index[i], side,
                                    entry_p, exit_price,
                                    _net_return(side, entry_p, exit_price, costs),
                                    reason))
                in_pos = False
    if in_pos:
        trades.append(Trade(symbol, index[entry_bar], index[n - 1], side,
                            entry_p, closes[n - 1],
                            _net_return(side, entry_p, closes[n - 1], costs),
                            "END_OF_DATA"))
    return trades


def trade_metrics(trades: list[Trade]) -> dict:
    """Aggregate metrics for a trade list. All returns net of costs."""
    n = len(trades)
    if n == 0:
        return {"trades": 0, "wins": 0, "win_rate": None, "expectancy_net": None,
                "profit_factor_net": None, "avg_win_net": None, "avg_loss_net": None,
                "total_return_net": None, "max_drawdown_net": None}
    nets = np.array([t.net_return for t in trades], dtype=float)
    wins = nets[nets > 0]
    losses = nets[nets < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    if gross_loss > 0:
        pf = gross_profit / gross_loss
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
        "profit_factor_net": (float(pf) if pf is not None and pf != float("inf") else pf),
        "avg_win_net": float(wins.mean()) if len(wins) else None,
        "avg_loss_net": float(losses.mean()) if len(losses) else None,
        "total_return_net": float(np.prod(1.0 + nets) - 1.0),
        "max_drawdown_net": max_dd,
    }
