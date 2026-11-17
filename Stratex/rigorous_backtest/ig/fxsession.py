"""fxsession.py — signal + execution engine for TASK-STR-RD-018
(FX Asia-Range Fade family).

Implements `fxsession_declaration.json` byte-for-byte in behaviour:
the declaration governs; if this code and the declaration disagree,
the declaration wins and this code is wrong.

Mechanics (all times UTC, fixed clock windows, no DST shifting):
  - Asian range = max high / min low over the M15 bars starting in
    [00:00, 06:00) of a UTC calendar date (24 bars), frozen at 06:00.
  - Fade window = bars starting in [06:00, 10:00). The FIRST bar
    touching an extreme (high >= range high -> SHORT fade;
    low <= range low -> LONG fade) is the signal; a bar touching
    both extremes voids the day.
  - Entry at the next bar's open, subject to the declared guards.
  - Stop = extreme -/+ 0.5 * range width; target = range midpoint.
  - Exit = first of target / stop / time exit at the 10:00 bar's
    open; within a bar, the stop fills first (worst case).
  - One trade per instrument per UTC date.
  - Tradeable day: all 40 bars starting in [00:00, 10:00) present,
    complete and contiguous, plus the 10:00 bar present.
  - Costs: programme FX-major model (rd2/costs2.py FX_MAJOR):
    3 bps per side spread+slippage, applied adversely in price
    space. The 2x shadow is slip_bps_per_side=6.0.

Pure functions over in-memory bars: no I/O, no network, no clock.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

BAR_LEN = timedelta(minutes=15)
RANGE_BARS = 24          # [00:00, 06:00)
FADE_BARS = 16           # [06:00, 10:00)
DAY_BARS = RANGE_BARS + FADE_BARS   # 40 bars in [00:00, 10:00)
STOP_FRAC = 0.5
DEFAULT_SLIP_BPS_PER_SIDE = 3.0     # 6 bps round trip (FX_MAJOR)


@dataclass(frozen=True)
class Bar:
    ts: datetime         # bar start, tz-aware UTC
    open: float
    high: float
    low: float
    close: float
    complete: bool = True


@dataclass(frozen=True)
class Trade:
    symbol: str
    date: str            # UTC date of the setup (ISO)
    side: str            # "LONG" | "SHORT"
    entry_time: datetime
    entry_price: float   # raw fill-bar open (before cost adjustment)
    stop: float
    target: float
    exit_time: datetime
    exit_price: float    # raw exit level/open (before cost adjustment)
    exit_reason: str     # "TP" | "SL" | "TIME"
    ret_gross: float     # signed return fraction, no costs
    ret_net: float       # signed return fraction, costs applied


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time(0, 0), tzinfo=timezone.utc)


def day_slice(bars: list[Bar], d: date) -> list[Bar]:
    """Bars starting in [00:00, 10:00] UTC of date d (41 slots max:
    the 40 window bars plus the 10:00 time-exit bar)."""
    start = _day_start(d)
    end = start + timedelta(hours=10)
    return [b for b in bars if start <= b.ts <= end]


def asian_range(day: list[Bar]) -> tuple[float, float] | None:
    """(range_high, range_low) from the first RANGE_BARS bars of a
    validated day slice, or None if the range is unusable."""
    if len(day) < RANGE_BARS:
        return None
    window = day[:RANGE_BARS]
    hi = max(b.high for b in window)
    lo = min(b.low for b in window)
    if not hi > lo:
        return None
    return hi, lo


def _tradeable(day: list[Bar], d: date) -> bool:
    """Declared tradeable-day rule: the 40 bars starting in
    [00:00, 10:00) present, complete, contiguous at 15-minute
    spacing, and the 10:00 bar present."""
    if len(day) != DAY_BARS + 1:
        return False
    start = _day_start(d)
    for i, b in enumerate(day):
        if b.ts != start + i * BAR_LEN:
            return False
    if any(not b.complete for b in day[:DAY_BARS]):
        return False
    return True


def _simulate(symbol: str, d: date, day: list[Bar], side: str,
              touch_idx: int, rng: tuple[float, float],
              slip_bps_per_side: float) -> Trade | None:
    hi, lo = rng
    width = hi - lo
    mid = (hi + lo) / 2.0
    if side == "SHORT":
        stop = hi + STOP_FRAC * width
        target = mid
    else:
        stop = lo - STOP_FRAC * width
        target = mid

    entry_idx = touch_idx + 1
    if entry_idx >= DAY_BARS:
        return None  # entry bar would start at/after 10:00 UTC
    entry_bar = day[entry_idx]
    entry = entry_bar.open
    if side == "SHORT":
        if not (stop > entry > target):
            return None
    else:
        if not (stop < entry < target):
            return None

    exit_price = None
    exit_time = None
    exit_reason = None
    for j in range(entry_idx, DAY_BARS):
        b = day[j]
        if side == "SHORT":
            stop_hit = b.high >= stop
            target_hit = b.low <= target
        else:
            stop_hit = b.low <= stop
            target_hit = b.high >= target
        if stop_hit:  # stop fills first within a bar (worst case)
            exit_price, exit_time, exit_reason = stop, b.ts, "SL"
            break
        if target_hit:
            exit_price, exit_time, exit_reason = target, b.ts, "TP"
            break
    if exit_price is None:
        exit_bar = day[DAY_BARS]  # the 10:00 bar; only its open is used
        exit_price, exit_time, exit_reason = exit_bar.open, exit_bar.ts, "TIME"

    s = slip_bps_per_side / 10000.0
    if side == "LONG":
        ret_gross = (exit_price - entry) / entry
        ret_net = (exit_price * (1.0 - s) - entry * (1.0 + s)) / (entry * (1.0 + s))
    else:
        ret_gross = (entry - exit_price) / entry
        ret_net = (entry * (1.0 - s) - exit_price * (1.0 + s)) / (entry * (1.0 - s))
    return Trade(symbol=symbol, date=d.isoformat(), side=side,
                 entry_time=entry_bar.ts, entry_price=entry,
                 stop=stop, target=target,
                 exit_time=exit_time, exit_price=exit_price,
                 exit_reason=exit_reason,
                 ret_gross=ret_gross, ret_net=ret_net)


def generate_trades(bars: list[Bar], symbol: str,
                    slip_bps_per_side: float = DEFAULT_SLIP_BPS_PER_SIDE
                    ) -> list[Trade]:
    """All declared trades for one instrument over the given bars.
    Bars must be sorted by start time; only completed bars and
    completed days per the tradeable-day rule can produce trades."""
    if any(bars[i].ts >= bars[i + 1].ts for i in range(len(bars) - 1)):
        raise ValueError("bars must be strictly increasing in time")
    trades: list[Trade] = []
    dates = sorted({b.ts.date() for b in bars})
    for d in dates:
        day = day_slice(bars, d)
        if not _tradeable(day, d):
            continue
        rng = asian_range(day)
        if rng is None:
            continue
        hi, lo = rng
        for idx in range(RANGE_BARS, DAY_BARS):
            b = day[idx]
            touch_hi = b.high >= hi
            touch_lo = b.low <= lo
            if touch_hi and touch_lo:
                break  # ambiguous bar: no setup today
            if not (touch_hi or touch_lo):
                continue
            side = "SHORT" if touch_hi else "LONG"
            t = _simulate(symbol, d, day, side, idx, rng,
                          slip_bps_per_side)
            if t is not None:
                trades.append(t)
            break  # the first touch defines the day's only setup
    return trades
