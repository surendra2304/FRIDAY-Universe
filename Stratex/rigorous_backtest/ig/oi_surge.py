"""OI-surge follow-through — signal + execution harness, PRE-DECLARED.

TASK-STR-RD-022 (discovery census slate #2). RESEARCH-ONLY /
DEMO-ONLY.

The frozen declaration governs this family: ``oi_declaration.json``
(SHA-256 6368711d5fcef1541b6af49a1d2f48f5b0caafe9b8f6f9109bdd9e7ca3aaecf8)
+ ``OI_DECLARATION.md`` in Stratex/rigorous_backtest/ig/. If this
code and the declaration disagree, the declaration wins and the code
is wrong. This module was staged in ~/workspace/str-oi/harness/
BEFORE the declared run; the run is a separate, later, gated step
(see ../RUNBOOK.md). Nothing here has been run against the real
panel.

The declared rules, implemented exactly:

1. Series — per symbol, price bars at the cell timeframe (4h or 1d)
   plus the open-interest value at each bar's close, produced by a
   causal asof over Binance Vision metrics snapshots (see
   metrics_feed.py): the last snapshot with create_time <= bar
   close. A bar whose asof snapshot is more than 30 minutes old at
   the bar close is NOT evaluable (feed gap, not a signal).
2. OI change — dOI_t = OI_t / OI_{t-1} - 1 over consecutive bars;
   undefined if either endpoint is missing or OI_{t-1} <= 0.
3. Extreme — the percentile rank of dOI_t within the trailing
   365 days of dOI values at the same timeframe, current bar
   included: rank = #{window values <= dOI_t} / #{window values}.
   Evaluable only if the bar's timestamp is >= 2023-01-01 (365
   days after the 2022-01-01 panel start) AND >= 95% of the bars
   in the trailing window have defined dOI. A surge is rank >= 0.95.
4. Entry — FOLLOW: on a surge bar t that the symbol spent entirely
   flat, a positive close-to-close return (close_t/close_{t-1}-1)
   enters LONG and a negative one enters SHORT at the OPEN of bar
   t+1; a return of exactly zero produces no trade.
5. Bracket — Wilder ATR(14), value at the signal bar t (seeded as
   the simple mean of the first 14 true ranges, then
   ATR = (ATR*13 + TR)/14). Stop = entry -/+ 2.0*ATR_t,
   target = entry +/- 4.0*ATR_t. ATR_t <= 0 -> no trade.
6. Exit — evaluated on every bar from the entry bar onward, in the
   programme simulator's order: gap through the stop at the bar
   open fills at the open; stop touch fills at the stop; gap
   through the target at the open fills at the open; target touch
   fills at the target (stop before target within a bar — worst
   case). Max hold 120 hours (30 bars at 4h, 5 bars at 1d, the
   entry bar counting as bar 1): if no bracket exit has occurred
   by the max-hold bar's close, exit at that close (exit_reason
   "TIME"; the max-hold bar's bracket checks run first). A
   position still open at the end of the data is closed at the
   final close, exit_reason "END_OF_DATA".
7. Frequency — one position at a time per symbol; signals while a
   position is open are skipped (counted); a bar on which an exit
   occurred is never also a signal bar.
8. Costs — the programme model (simulator.Costs): Binance USDT-M
   taker fee 5 bps + spread/slippage 3 bps per side, applied
   adversely in price space; round trip 16 bps. The 2x shadow is
   Costs(10, 6) = 32 bps round trip. Both must pass at the run.

Bars are plain dicts {"time", "open", "high", "low", "close"} where
"time" is a datetime (UTC) or an ISO-8601 string; the OI input is a
parallel list of (oi_value, snapshot_age_minutes) tuples-or-None,
aligned by bar index (see metrics_feed.oi_at_bar_close). Stdlib
only, Python 3.10-compatible, fully deterministic.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

OI_PCT_WINDOW_DAYS = 365        # frozen by the declaration
OI_SURGE_RANK = 0.95            # frozen by the declaration
WINDOW_MIN_COVERAGE = 0.95      # frozen by the declaration
SNAPSHOT_MAX_AGE_MIN = 30.0     # frozen by the declaration
ATR_PERIOD = 14                 # frozen by the declaration
SL_ATR_MULT = 2.0               # frozen by the declaration
TP_ATR_MULT = 4.0               # frozen by the declaration
MAX_HOLD_HOURS = 120            # frozen by the declaration
FIRST_EVALUABLE = datetime(2023, 1, 1, tzinfo=timezone.utc)  # frozen

MAX_HOLD_BARS = {"4h": 30, "1d": 5}   # 120h expressed per cell


def _as_dt(t: Any) -> datetime:
    if isinstance(t, datetime):
        return t if t.tzinfo is not None else t.replace(tzinfo=timezone.utc)
    s = str(t).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def compute_doi(oi_values: Sequence[float | None]) -> list[float | None]:
    """dOI_t = OI_t / OI_{t-1} - 1 over consecutive bars; None where
    either endpoint is missing or OI_{t-1} <= 0."""
    out: list[float | None] = [None] * len(oi_values)
    for t in range(1, len(oi_values)):
        prev, cur = oi_values[t - 1], oi_values[t]
        if prev is None or cur is None or prev <= 0:
            continue
        out[t] = cur / prev - 1.0
    return out


def percentile_ranks(times: Sequence[datetime],
                     doi: Sequence[float | None],
                     window_days: int = OI_PCT_WINDOW_DAYS,
                     min_coverage: float = WINDOW_MIN_COVERAGE,
                     first_evaluable: datetime = FIRST_EVALUABLE,
                     ) -> list[float | None]:
    """Causal trailing percentile rank of each bar's dOI.

    rank_t = #{defined dOI in (time_t - window, time_t] with value
    <= dOI_t} / #{defined dOI in that window}; None when bar t is
    before first_evaluable, when dOI_t is undefined, or when fewer
    than min_coverage of the window's bars have defined dOI. Only
    bars <= t ever enter bar t's window (no look-ahead)."""
    n = len(times)
    out: list[float | None] = [None] * n
    defined_prefix = [0] * (n + 1)
    for i, v in enumerate(doi):
        defined_prefix[i + 1] = defined_prefix[i] + (1 if v is not None else 0)
    window = timedelta(days=window_days)
    for t in range(n):
        if doi[t] is None or times[t] < first_evaluable:
            continue
        lo = bisect_right(times, times[t] - window, 0, t + 1)
        bars_in_window = t + 1 - lo
        if bars_in_window == 0:
            continue
        defined_in_window = defined_prefix[t + 1] - defined_prefix[lo]
        if defined_in_window < min_coverage * bars_in_window:
            continue
        win_vals = [doi[j] for j in range(lo, t + 1) if doi[j] is not None]
        le = sum(1 for v in win_vals if v <= doi[t])
        out[t] = le / len(win_vals)
    return out


def atr_series(bars: Sequence[dict], period: int = ATR_PERIOD) -> list[float | None]:
    """Wilder ATR: seeded as the simple mean of the first `period`
    true ranges, then ATR_t = (ATR_{t-1}*(period-1) + TR_t)/period.
    None until the seed is complete."""
    n = len(bars)
    out: list[float | None] = [None] * n
    if n == 0:
        return out
    trs: list[float] = []
    for i, b in enumerate(bars):
        h, l = float(b["high"]), float(b["low"])
        if i == 0:
            trs.append(h - l)
        else:
            pc = float(bars[i - 1]["close"])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if n < period:
        return out
    atr = sum(trs[:period]) / period
    out[period - 1] = atr
    for i in range(period, n):
        atr = (atr * (period - 1) + trs[i]) / period
        out[i] = atr
    return out


@dataclass(frozen=True)
class OiSignal:
    bar_index: int      # index of the signal (surge) bar t
    time: Any
    side: str           # "LONG" | "SHORT"
    doi: float          # dOI at bar t
    rank: float         # percentile rank of dOI_t (>= OI_SURGE_RANK)
    atr: float          # Wilder ATR at bar t (> 0)

    def as_dict(self) -> dict[str, Any]:
        return {"bar_index": self.bar_index, "time": str(self.time),
                "side": self.side, "doi": self.doi, "rank": self.rank,
                "atr": self.atr}


def generate_signals(bars: Sequence[dict],
                     oi: Sequence[tuple[float, float] | None],
                     ) -> list[OiSignal]:
    """Declared OI-surge signals. `oi` is aligned with `bars`: each
    entry is (oi_value, snapshot_age_minutes) from the causal asof,
    or None when no snapshot exists at or before the bar close.
    A bar is evaluable only if its asof snapshot is at most
    SNAPSHOT_MAX_AGE_MIN old. Signal generation only — position
    state (flatness) is applied in simulate()."""
    times = [_as_dt(b["time"]) for b in bars]
    oi_values: list[float | None] = []
    for t in range(len(bars)):
        entry = oi[t] if t < len(oi) else None
        if entry is None or entry[1] is None or entry[1] > SNAPSHOT_MAX_AGE_MIN:
            oi_values.append(None)
        else:
            oi_values.append(float(entry[0]))
    doi = compute_doi(oi_values)
    ranks = percentile_ranks(times, doi)
    atrs = atr_series(bars)
    closes = [float(b["close"]) for b in bars]
    signals: list[OiSignal] = []
    for t in range(1, len(bars)):
        if ranks[t] is None or ranks[t] < OI_SURGE_RANK:
            continue
        if atrs[t] is None or atrs[t] <= 0:
            continue  # degenerate: declaration says NO trade
        ret = closes[t] / closes[t - 1] - 1.0 if closes[t - 1] > 0 else 0.0
        if ret > 0:
            side = "LONG"
        elif ret < 0:
            side = "SHORT"
        else:
            continue  # exactly zero: declaration says NO trade
        signals.append(OiSignal(bar_index=t, time=bars[t]["time"],
                                side=side, doi=doi[t], rank=ranks[t],
                                atr=atrs[t]))
    return signals


@dataclass(frozen=True)
class Costs:
    """Mirror of rigorous_backtest.simulator.Costs (same semantics:
    per-side fee + slippage applied adversely in price space)."""
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


COSTS = Costs()                 # programme model: 16 bps round trip
COSTS_2X = Costs(10.0, 6.0)     # 2x shadow: 32 bps round trip


def net_return(side: str, entry: float, exit_: float, costs: Costs) -> float:
    """Identical formula to rigorous_backtest.simulator._net_return."""
    r = costs.per_side_rate
    if side == "LONG":
        entry_adj = entry * (1 + r)
        exit_adj = exit_ * (1 - r)
        return (exit_adj - entry_adj) / entry_adj
    entry_adj = entry * (1 - r)
    exit_adj = exit_ * (1 + r)
    return (entry_adj - exit_adj) / entry_adj


@dataclass
class Trade:
    """Field-compatible with rigorous_backtest.simulator.Trade."""
    symbol: str
    entry_time: Any
    exit_time: Any
    side: str           # "LONG" | "SHORT"
    entry_price: float  # raw (pre-cost) fill reference
    exit_price: float   # raw (pre-cost) fill reference
    net_return: float   # fraction of entry price, net of all costs
    exit_reason: str    # "TP" | "SL" | "TIME" | "END_OF_DATA"


def _check_exit(pos: dict, bar: dict) -> tuple[float | None, str | None]:
    """Stop-before-target worst case, programme simulator order."""
    side = pos["side"]
    stop, tp = pos["stop"], pos["target"]
    o, h, l = float(bar["open"]), float(bar["high"]), float(bar["low"])
    if side == "LONG":
        if o <= stop:
            return o, "SL"
        if l <= stop:
            return stop, "SL"
        if o >= tp:
            return o, "TP"
        if h >= tp:
            return tp, "TP"
    else:
        if o >= stop:
            return o, "SL"
        if h >= stop:
            return stop, "SL"
        if o <= tp:
            return o, "TP"
        if l <= tp:
            return tp, "TP"
    return None, None


def simulate(bars: Sequence[dict],
             oi: Sequence[tuple[float, float] | None],
             symbol: str, timeframe: str,
             costs: Costs = COSTS) -> tuple[list[Trade], dict]:
    """Declared execution over one symbol's bars for one cell.

    Entry at the open of the bar AFTER the surge bar; exits from
    the entry bar onward; max-hold per MAX_HOLD_BARS[timeframe];
    one position at a time; a bar on which an exit occurred is
    never a signal bar; signals on the final bar cannot be taken
    (no next bar to enter on). Returns (trades, stats)."""
    if timeframe not in MAX_HOLD_BARS:
        raise ValueError(f"undeclared timeframe {timeframe!r}")
    max_hold = MAX_HOLD_BARS[timeframe]
    signals = generate_signals(bars, oi)
    sig_by_bar = {s.bar_index: s for s in signals}
    trades: list[Trade] = []
    stats = {"signals": len(signals), "taken": 0, "skipped_open": 0,
             "skipped_exit_bar": 0, "final_bar_signals": 0}
    n = len(bars)
    pos: dict | None = None
    for j in range(n):
        bar = bars[j]
        exited_this_bar = False
        if pos is not None:
            exit_price, reason = _check_exit(pos, bar)
            if exit_price is None and j - pos["entry_bar"] >= max_hold - 1:
                exit_price, reason = float(bar["close"]), "TIME"
            if exit_price is not None:
                trades.append(Trade(
                    symbol, bars[pos["entry_bar"]]["time"], bar["time"],
                    pos["side"], pos["entry"], exit_price,
                    net_return(pos["side"], pos["entry"], exit_price, costs),
                    reason))
                pos = None
                exited_this_bar = True
        if j in sig_by_bar:
            if pos is not None:
                stats["skipped_open"] += 1
            elif exited_this_bar:
                stats["skipped_exit_bar"] += 1
            elif j + 1 < n:
                s = sig_by_bar[j]
                entry = float(bars[j + 1]["open"])
                sign = 1.0 if s.side == "LONG" else -1.0
                pos = {"side": s.side, "entry": entry,
                       "stop": entry - sign * SL_ATR_MULT * s.atr,
                       "target": entry + sign * TP_ATR_MULT * s.atr,
                       "entry_bar": j + 1}
                stats["taken"] += 1
            else:
                stats["final_bar_signals"] += 1
    if pos is not None:
        exit_price = float(bars[n - 1]["close"])
        trades.append(Trade(
            symbol, bars[pos["entry_bar"]]["time"], bars[n - 1]["time"],
            pos["side"], pos["entry"], exit_price,
            net_return(pos["side"], pos["entry"], exit_price, costs),
            "END_OF_DATA"))
    return trades, stats
