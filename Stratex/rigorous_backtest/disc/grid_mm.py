"""Grid / passive market-making — signal + execution harness, PRE-DECLARED.

TASK-STR-RD-023 (FRIDAY Universe strategy-discovery census,
2026-11-17, recommended slate #7). RESEARCH-ONLY / DEMO-ONLY.

The frozen declaration governs this family:
``grid_mm_declaration.json`` (SHA-256
2b5d807a5b00c893b1dd28af4d23b943a7fb587c15dc9a7e6cf8a5bdd8a7d66c) +
``GRID_MM_DECLARATION.md`` in Stratex/rigorous_backtest/disc/. If
this code and the declaration disagree, the declaration wins and
the code is wrong. This module was staged in
~/workspace/str-grid/harness/ BEFORE the declared run; the run is a
separate, later, gated step (see ../RUNBOOK.md). Nothing here has
been run against the real panel.

This harness REPLACES Stratex/strategies/grid_trading.py (read in
full at declaration time; disposition recorded in the declaration):
that module has no callable signal path (the census's NOT_EVALUABLE
finding), fills on a mere touch of a single price print with zero
fees anywhere — the exact fantasy-fill mechanism this family's
haircut exists to eliminate — alternates buy/sell by index parity
instead of running a paired grid book, re-centres on the current
price with no causal placement rule, and has no inventory limits.

The declared rules, implemented exactly:

1. Universe / timeframe — BTCUSDT, ETHUSDT, SOLUSDT, 15m bars
   (the runner enforces the universe; this module is per-symbol).
2. Placement — first placement at the close of bar index 671,
   then every EPOCH_BARS (96) bars at that bar's close. The grid
   placed at bar j is active for bars j+1 .. j+96.
3. Range (causal) — lower = 10th percentile, upper = 90th
   percentile of the trailing TRAILING_WINDOW_BARS (672) bar
   closes ending AT the placement bar (type-7 linear-interpolation
   percentiles over completed bars only). If upper <= lower, no
   grid is placed for that epoch.
4. Lines — GRID_INTERVALS (10) arithmetic intervals, 11 lines
   L_k = lower + k * (upper - lower) / 10, frozen for the epoch.
5. Units (long-only) — line L_k (k = 0..9) holds at most ONE long
   unit. It opens when a bar trades through it downward (fill
   model below); entry price = L_k. L_10 never buys. No shorts.
6. Exit — a unit on L_k exits when a LATER bar trades through
   L_(k+1) upward; exit price = L_(k+1), exit_reason "GRID_SELL".
   No stop-loss, no other take-profit.
7. Teardown — at every placement bar's close, all open units are
   force-closed at that close (exit_reason "TEARDOWN", full
   costs) BEFORE the new grid is placed; no inventory carries
   across epochs. Units open after the final bar close at the
   final close (exit_reason "END_OF_DATA").
8. Inventory cap — one open unit per buy line, at most 10 open
   units per symbol at any time (structural).

THE FILL MODEL (the pre-declared haircut — the heart of the
declaration):
- Trade-through — a resting BUY at level P fills in bar i ONLY if
  bar i's range SPANS the level and trades THROUGH it downward:
  high >= P AND low <= P * (1 - TRADE_THROUGH_MARGIN); a resting
  SELL at P ONLY if low <= P AND high >= P * (1 +
  TRADE_THROUGH_MARGIN); TRADE_THROUGH_MARGIN = 0.001 (10 bps).
  A mere touch NEVER fills, and a level the bar never reached
  cannot fill either (no phantom fills at unvisited prices;
  gap-through bars miss — a deliberate conservative bias);
  touches are counted in the stats (touch_no_fill) as the
  rejected fantasy fills.
- Fill price — the level price exactly (limit-order semantics).
- Sequencing — within a bar, exits are evaluated only for units
  open at that bar's START (a unit bought in bar i is managed
  from bar i+1); a line whose unit sold in bar i cannot re-buy
  in bar i; buys on different lines in the same bar are
  independent and all may fill. Placement bars: fills under the
  old grid, then teardown at that bar's close, then placement.
- Costs — charged on EVERY fill (buys, grid sells, teardown and
  end-of-data exits alike): the programme fee/slippage model
  (simulator.Costs: 5 bps fee + 3 bps slippage per fill) PLUS the
  declared adverse-selection allowance of 5 bps per fill.
  GRID_COSTS = 13 bps per fill (26 bps effective round trip);
  GRID_COSTS_2X doubles only the fee/slippage component =
  21 bps per fill (42 bps effective round trip). Applied
  adversely in price space, identical in form to
  simulator._net_return for a long trade.

Counting — one completed round trip (buy fill + its matching
exit fill) is ONE Trade, attributed by ENTRY time (the runner
applies the programme's walk-forward folds on entry time).

Bars are plain dicts {"time", "open", "high", "low", "close"}
where "time" is an ISO-8601 string or a datetime/Timestamp;
stdlib only, Python 3.10-compatible, fully deterministic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

DECLARATION_SHA256 = "2b5d807a5b00c893b1dd28af4d23b943a7fb587c15dc9a7e6cf8a5bdd8a7d66c"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]   # frozen by the declaration
TIMEFRAME = "15m"                             # frozen by the declaration
TRAILING_WINDOW_BARS = 672                    # 7 days of 15m bars
RANGE_LOW_PCT = 10.0                          # trailing-close percentile
RANGE_HIGH_PCT = 90.0                         # trailing-close percentile
GRID_INTERVALS = 10                           # 11 lines, 10 buy lines
EPOCH_BARS = 96                               # 24h between placements
FIRST_PLACEMENT_BAR = TRAILING_WINDOW_BARS - 1   # bar index 671
TRADE_THROUGH_MARGIN = 0.001                  # 10 bps — frozen haircut
ADVERSE_SELECTION_BPS_PER_FILL = 5.0          # frozen haircut
MAX_OPEN_UNITS = GRID_INTERVALS               # one unit per buy line


def percentile_type7(sorted_values: Sequence[float], pct: float) -> float:
    """Type-7 (linear interpolation) percentile of PRE-SORTED values.

    rank = (pct/100) * (n-1); value interpolated between the floor
    and ceil ranks. Identical to numpy.percentile's default method.
    """
    n = len(sorted_values)
    if n == 0:
        raise ValueError("percentile of an empty sequence")
    if n == 1:
        return float(sorted_values[0])
    rank = (pct / 100.0) * (n - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(sorted_values[lo])
    frac = rank - lo
    return float(sorted_values[lo]) * (1.0 - frac) + float(sorted_values[hi]) * frac


def build_grid(window_closes: Sequence[float]) -> list[float] | None:
    """The declared grid for one epoch, from the trailing window's
    closes (completed bars only — causality is the caller's
    contract, enforced in simulate()). Returns the 11 line prices
    (ascending), or None for a degenerate (zero-width) range."""
    if len(window_closes) != TRAILING_WINDOW_BARS:
        raise ValueError(
            f"window must hold exactly {TRAILING_WINDOW_BARS} closes, "
            f"got {len(window_closes)}")
    s = sorted(float(c) for c in window_closes)
    lower = percentile_type7(s, RANGE_LOW_PCT)
    upper = percentile_type7(s, RANGE_HIGH_PCT)
    if not upper > lower:
        return None
    step = (upper - lower) / GRID_INTERVALS
    return [lower + k * step for k in range(GRID_INTERVALS + 1)]


@dataclass(frozen=True)
class GridCosts:
    """Per-fill cost stack. fee_slip_bps_per_fill mirrors
    rigorous_backtest.simulator.Costs per side (5 fee + 3
    slippage = 8 programme; 10 + 6 = 16 in the 2x shadow);
    adverse_bps_per_fill is the declaration's frozen
    adverse-selection haircut, identical at both stacks."""
    fee_slip_bps_per_fill: float = 8.0
    adverse_bps_per_fill: float = ADVERSE_SELECTION_BPS_PER_FILL

    @property
    def per_fill_rate(self) -> float:
        return (self.fee_slip_bps_per_fill + self.adverse_bps_per_fill) / 10000.0

    def describe(self) -> dict:
        return {
            "venue_model": "Binance USDT-M futures, passive limit fills",
            "fee_slippage_bps_per_fill": self.fee_slip_bps_per_fill,
            "adverse_selection_bps_per_fill": self.adverse_bps_per_fill,
            "total_bps_per_fill": self.fee_slip_bps_per_fill + self.adverse_bps_per_fill,
            "effective_round_trip_bps": 2 * (self.fee_slip_bps_per_fill + self.adverse_bps_per_fill),
        }


GRID_COSTS = GridCosts()                  # 13 bps/fill, 26 bps RT
GRID_COSTS_2X = GridCosts(16.0, ADVERSE_SELECTION_BPS_PER_FILL)  # 21 bps/fill, 42 bps RT


def net_return_long(entry: float, exit_: float, costs: GridCosts) -> float:
    """Long round-trip net return with per-fill costs applied
    adversely in price space — identical in form to
    rigorous_backtest.simulator._net_return for side == 'LONG',
    with the per-side rate replaced by the per-fill stack rate."""
    c = costs.per_fill_rate
    entry_adj = entry * (1 + c)
    exit_adj = exit_ * (1 - c)
    return (exit_adj - entry_adj) / entry_adj


@dataclass
class Trade:
    """Field-compatible with rigorous_backtest.simulator.Trade."""
    symbol: str
    entry_time: Any
    exit_time: Any
    side: str           # always "LONG" in this family
    entry_price: float  # the grid line price (raw, pre-cost)
    exit_price: float   # the exit line / teardown close (raw, pre-cost)
    net_return: float   # fraction of entry price, net of all costs
    exit_reason: str    # "GRID_SELL" | "TEARDOWN" | "END_OF_DATA"


def simulate(bars: Sequence[dict], symbol: str,
             costs: GridCosts = GRID_COSTS) -> tuple[list[Trade], dict]:
    """Declared execution over one symbol's bars.

    Grids are placed at the closes of bars 671, 767, 863, ...;
    fills are evaluated bar by bar under the declared fill model;
    every opened unit is closed by a grid sell, a teardown, or the
    end of the data. Returns (trades, stats)."""
    n = len(bars)
    closes = [float(b["close"]) for b in bars]
    trades: list[Trade] = []
    stats = {"placements": 0, "epochs_with_grid": 0, "buy_fills": 0,
             "sell_fills": 0, "teardown_exits": 0, "end_of_data_exits": 0,
             "touch_no_fill": 0, "max_open_units": 0}
    open_units: dict[int, dict] = {}   # line index -> unit record
    lines: list[float] | None = None
    next_placement = FIRST_PLACEMENT_BAR
    m = TRADE_THROUGH_MARGIN

    for j in range(n):
        bar = bars[j]
        hi, lo = float(bar["high"]), float(bar["low"])
        if lines is not None:
            open_at_start = dict(open_units)
            sold_lines: set[int] = set()
            # Exits — only for units open at this bar's START.
            # A fill requires the bar's range to SPAN the target
            # (low <= target) and trade THROUGH it (high >=
            # target * (1 + m)); a span-and-touch without the
            # through-margin is the rejected fantasy fill.
            for k in sorted(open_at_start):
                unit = open_at_start[k]
                target = lines[k + 1]
                if lo <= target:
                    if hi >= target * (1 + m):
                        trades.append(Trade(
                            symbol, unit["entry_time"], bar["time"], "LONG",
                            unit["entry_price"], target,
                            net_return_long(unit["entry_price"], target, costs),
                            "GRID_SELL"))
                        del open_units[k]
                        sold_lines.add(k)
                        stats["sell_fills"] += 1
                    elif hi >= target:
                        stats["touch_no_fill"] += 1
            # Entries — lines free at bar start that did not sell
            # in this bar. Occupied lines have no resting buy.
            # Same span + trade-through rule, downward.
            for k in range(GRID_INTERVALS):
                if k in open_at_start or k in sold_lines:
                    continue
                p = lines[k]
                if hi >= p:
                    if lo <= p * (1 - m):
                        open_units[k] = {"entry_price": p, "entry_bar": j,
                                         "entry_time": bar["time"]}
                        stats["buy_fills"] += 1
                    elif lo <= p:
                        stats["touch_no_fill"] += 1
            if len(open_units) > stats["max_open_units"]:
                stats["max_open_units"] = len(open_units)
        if j == next_placement:
            # Teardown at this bar's close (full costs), THEN place
            # the new grid from the trailing window ending at j.
            for k in sorted(open_units):
                unit = open_units[k]
                trades.append(Trade(
                    symbol, unit["entry_time"], bar["time"], "LONG",
                    unit["entry_price"], closes[j],
                    net_return_long(unit["entry_price"], closes[j], costs),
                    "TEARDOWN"))
                stats["teardown_exits"] += 1
            open_units = {}
            window = closes[j - TRAILING_WINDOW_BARS + 1: j + 1]
            lines = build_grid(window)
            stats["placements"] += 1
            if lines is not None:
                stats["epochs_with_grid"] += 1
            next_placement += EPOCH_BARS

    if open_units:
        for k in sorted(open_units):
            unit = open_units[k]
            trades.append(Trade(
                symbol, unit["entry_time"], bars[n - 1]["time"], "LONG",
                unit["entry_price"], closes[n - 1],
                net_return_long(unit["entry_price"], closes[n - 1], costs),
                "END_OF_DATA"))
            stats["end_of_data_exits"] += 1
    stats["round_trips"] = len(trades)
    return trades, stats
