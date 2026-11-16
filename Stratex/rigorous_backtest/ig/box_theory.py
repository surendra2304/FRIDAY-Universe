"""'Box Theory' RD candidate — signal generation only, PRE-DECLARED.

TASK-IG2-STR-13 (IG wave 2, cluster #101; source shortcode
DWDUW26DYbZ, sweep crew-14). RESEARCH-ONLY / DEMO-ONLY.

The frozen declaration governs this family:
``box_theory_declaration.json`` + ``BOX_THEORY_DECLARATION.md`` in
this directory, declared BEFORE any backtest of this family has been
run. If this code and the declaration disagree, the declaration wins
and the code is wrong. This module implements ONLY the declared
signal rules — it contains no backtest runner, no simulator and no
performance statistics, by design: the declared run is a separate,
later step (see the declaration's data plan and the task's board
fragment next_action), executed once, against the frozen spec.

The method (from the source, with every ambiguity resolved IN THE
DECLARATION before any run):

1. Box — for each day, the box is the PREVIOUS day's range: high =
   max high, low = min low of the previous day's 15-minute bars;
   mid = (high + low) / 2; height = high - low. Only bars from days
   strictly before the signal day define the box (no lookahead).
2. Extremes only — entries are allowed only in the outer quartiles:
   the bottom zone [low, low + 0.25*height] for longs, the top zone
   [high - 0.25*height, high] for shorts. The middle 50% of the box
   is a no-trade zone ("that's where all the false signals are").
3. Trigger — a 'John Wick' candlestick in the zone: for a long, a
   candle whose lower wick is at least twice its body and which
   closes in the upper half of its own range (a rejection of the
   low); mirror for a short (upper wick >= 2x body, close in the
   lower half). Entry at the trigger bar's close.
4. Stop / targets — long: stop = box low, T1 = box mid, T2 = box
   high; short mirrored. At most ONE signal per day (the first
   qualifying extreme of the day), so the declared run's trial count
   stays clean.

Bars are plain dicts {"time", "open", "high", "low", "close"} where
"time" is an ISO-8601 string or a datetime; days are UTC calendar
days. Stdlib only, Python 3.10-compatible, fully deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Sequence

ZONE_FRACTION = 0.25      # outer quartile at each end (frozen)
WICK_TO_BODY = 2.0        # John Wick wick must be >= 2x the body (frozen)


@dataclass(frozen=True)
class Box:
    day: str                # ISO date the box applies TO
    source_day: str         # ISO date the box was drawn FROM
    high: float
    low: float

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2.0

    @property
    def height(self) -> float:
        return self.high - self.low

    @property
    def bottom_zone_top(self) -> float:
        return self.low + ZONE_FRACTION * self.height

    @property
    def top_zone_bottom(self) -> float:
        return self.high - ZONE_FRACTION * self.height


@dataclass(frozen=True)
class BoxSignal:
    day: str
    bar_index: int          # index into the input bar sequence
    time: Any
    side: str               # "LONG" | "SHORT"
    entry: float            # trigger bar close
    stop: float
    target1: float          # box mid
    target2: float          # opposite box extreme
    box_high: float
    box_low: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "day": self.day, "bar_index": self.bar_index,
            "time": str(self.time), "side": self.side,
            "entry": self.entry, "stop": self.stop,
            "target1": self.target1, "target2": self.target2,
            "box_high": self.box_high, "box_low": self.box_low,
        }


def _day_of(bar: dict) -> str:
    t = bar["time"]
    if isinstance(t, datetime):
        return t.date().isoformat()
    return str(t)[:10]


def compute_boxes(bars: Sequence[dict]) -> dict[str, Box]:
    """One box per day (from the previous present day's range)."""
    by_day: dict[str, list[dict]] = {}
    for bar in bars:
        by_day.setdefault(_day_of(bar), []).append(bar)
    days = sorted(by_day)
    boxes: dict[str, Box] = {}
    for prev_day, day in zip(days, days[1:]):
        prev = by_day[prev_day]
        high = max(b["high"] for b in prev)
        low = min(b["low"] for b in prev)
        if high > low:
            boxes[day] = Box(day=day, source_day=prev_day,
                             high=high, low=low)
    return boxes


def _is_long_wick(bar: dict) -> bool:
    body = abs(bar["close"] - bar["open"])
    if body <= 0:
        return False
    lower_wick = min(bar["open"], bar["close"]) - bar["low"]
    rng = bar["high"] - bar["low"]
    if rng <= 0:
        return False
    return (lower_wick >= WICK_TO_BODY * body
            and bar["close"] >= bar["low"] + 0.5 * rng)


def _is_short_wick(bar: dict) -> bool:
    body = abs(bar["close"] - bar["open"])
    if body <= 0:
        return False
    upper_wick = bar["high"] - max(bar["open"], bar["close"])
    rng = bar["high"] - bar["low"]
    if rng <= 0:
        return False
    return (upper_wick >= WICK_TO_BODY * body
            and bar["close"] <= bar["low"] + 0.5 * rng)


def generate_signals(bars: Sequence[dict]) -> list[BoxSignal]:
    """Declared Box Theory signals over 15-minute bars (no backtest —
    signal generation only; exits are the declared run's business,
    simulated there under the harness convention)."""
    boxes = compute_boxes(bars)
    signals: list[BoxSignal] = []
    signalled_days: set[str] = set()
    for idx, bar in enumerate(bars):
        day = _day_of(bar)
        if day in signalled_days or day not in boxes:
            continue
        box = boxes[day]
        in_bottom = bar["low"] <= box.bottom_zone_top and bar["high"] >= box.low
        in_top = bar["high"] >= box.top_zone_bottom and bar["low"] <= box.high
        if in_bottom and _is_long_wick(bar):
            signals.append(BoxSignal(
                day=day, bar_index=idx, time=bar["time"], side="LONG",
                entry=bar["close"], stop=box.low, target1=box.mid,
                target2=box.high, box_high=box.high, box_low=box.low,
            ))
            signalled_days.add(day)
        elif in_top and _is_short_wick(bar):
            signals.append(BoxSignal(
                day=day, bar_index=idx, time=bar["time"], side="SHORT",
                entry=bar["close"], stop=box.high, target1=box.mid,
                target2=box.low, box_high=box.high, box_low=box.low,
            ))
            signalled_days.add(day)
    return signals
