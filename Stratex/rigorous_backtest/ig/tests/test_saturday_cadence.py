"""Saturday retrain-cadence evaluation for TASK-STR-083, Leg 2 (S-16).

Head-to-head: the walk-forward gate's current every-window refit vs a
"retrain every Saturday" cadence, on the same synthetic daily panels.
The gate itself is unchanged — the cadence is a fit_fn wrapper that
refits only when the train segment's end crosses into a new
Saturday-anchored week. Bars carry epoch `time` (the gate treats
`time` as opaque; the wrapper derives the weekday from it).

Panels are deterministic hand-built price paths — mechanics evidence,
never performance evidence (same rule as the gate's own test suite).
The adopt/reject verdict is computed from the numbers by
cadence_verdict() and recorded in the task evidence doc; a negative
verdict closes the leg without changing the gate.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.walkforward_gate import GateConfig, evaluate_walk_forward  # noqa: E402

SATURDAY = 5  # datetime.weekday(): Monday 0 .. Sunday 6
DAY = 86400
# Monday 2026-01-05 00:00 UTC (verified: date -d 2026-01-05 -> Monday).
START_EPOCH = int(datetime(2026, 1, 5, tzinfo=timezone.utc).timestamp())

CFG = GateConfig(train_bars=60, test_bars=14, step_bars=1,
                 min_windows=3, min_pooled_test_trades=3)


def saturday_floor(ts: int) -> int:
    """Epoch of the most recent Saturday 00:00 UTC on or before ts."""
    day = datetime.fromtimestamp(ts, tz=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0)
    days_since_saturday = (day.weekday() - SATURDAY) % 7
    return int((day - timedelta(days=days_since_saturday)).timestamp())


class SaturdayCadenceFit:
    """fit_fn wrapper: refit only at Saturday boundaries.

    Keeps the params from the last refit until the train segment's end
    bar falls in a new Saturday-anchored week. `refits` counts actual
    refits; `calls` counts wrapper invocations (one per window).
    """

    def __init__(self, fit_fn):
        self._fit_fn = fit_fn
        self._cached = None
        self._cached_week = None
        self.refits = 0
        self.calls = 0

    def __call__(self, train_bars):
        self.calls += 1
        week = saturday_floor(train_bars[-1]["time"])
        if self._cached is None or week != self._cached_week:
            self._cached = self._fit_fn(train_bars)
            self._cached_week = week
            self.refits += 1
        return self._cached


def cadence_verdict(base: dict, sat: dict) -> dict:
    """Adopt the Saturday cadence only if it is no worse on the gate's
    pooled bars and buys fewer refits. `base`/`sat` are pooled metric
    dicts from trade_metrics plus a `refits` count."""
    same_or_better_pf = (
        sat["profit_factor_net"] is not None
        and base["profit_factor_net"] is not None
        and sat["profit_factor_net"] >= base["profit_factor_net"])
    same_or_better_pos = (
        sat["positive_window_fraction"] >= base["positive_window_fraction"])
    fewer_refits = sat["refits"] < base["refits"]
    adopt = same_or_better_pf and same_or_better_pos and fewer_refits
    return {"adopt": adopt, "same_or_better_pf": same_or_better_pf,
            "same_or_better_positive_fraction": same_or_better_pos,
            "fewer_refits": fewer_refits}


def make_daily_bars(closes):
    bars = []
    prev = closes[0]
    for i, c in enumerate(closes):
        o = prev
        bars.append({"time": START_EPOCH + i * DAY, "open": o,
                     "high": max(o, c) * 1.001, "low": min(o, c) * 0.999,
                     "close": c})
        prev = c
    return bars


def trend_closes(n, rate=0.005, dip_every=25):
    closes = []
    price = 100.0
    for i in range(n):
        price *= 1.0 + rate
        closes.append(price * (0.96 if (i + 1) % dip_every == 0 else 1.0))
    return closes


def flip_closes(n):
    """Uptrend for the first half, downtrend after — stale params hurt."""
    closes = []
    price = 100.0
    for i in range(n):
        price *= 1.005 if i < n // 2 else 0.995
        closes.append(price)
    return closes


def fit_trend(train_bars):
    return "LONG" if train_bars[-1]["close"] >= train_bars[0]["close"] else "SHORT"


def bracket_signal_fn(view, params):
    """One bracket signal every 8 bars of the test segment (the view's
    train segment is warm-up only)."""
    train_len = CFG.train_bars
    out = []
    for i in range(train_len, len(view) - 1, 8):
        ref = view[i]["close"]
        if params == "LONG":
            out.append((i, "LONG", ref * 0.975, ref * 1.03))
        else:
            out.append((i, "SHORT", ref * 1.025, ref * 0.97))
    return out


def head_to_head(bars):
    """Run both arms on the same panel; return (baseline, saturday) as
    pooled-metric dicts with refit counts and positive fractions."""
    base = evaluate_walk_forward(bars, bracket_signal_fn, fit_fn=fit_trend,
                                 config=CFG)
    sat_fit = SaturdayCadenceFit(fit_trend)
    sat = evaluate_walk_forward(bars, bracket_signal_fn, fit_fn=sat_fit,
                                config=CFG)
    base_pooled = dict(base.pooled)
    base_pooled["positive_window_fraction"] = base.checks["positive_window_fraction"]
    base_pooled["refits"] = len(base.windows)
    sat_pooled = dict(sat.pooled)
    sat_pooled["positive_window_fraction"] = sat.checks["positive_window_fraction"]
    sat_pooled["refits"] = sat_fit.refits
    return base_pooled, sat_pooled, sat_fit.calls


# ---------------- saturday_floor ----------------

def test_saturday_floor_anchors_on_saturday():
    # 2026-01-03 is a Saturday; 2026-01-05 a Monday; 2026-01-10 a Saturday.
    sat = int(datetime(2026, 1, 3, tzinfo=timezone.utc).timestamp())
    mon = int(datetime(2026, 1, 5, tzinfo=timezone.utc).timestamp())
    nxt_sat = int(datetime(2026, 1, 10, tzinfo=timezone.utc).timestamp())
    sun = int(datetime(2026, 1, 11, tzinfo=timezone.utc).timestamp())
    assert saturday_floor(sat) == sat
    assert saturday_floor(mon) == sat
    assert saturday_floor(nxt_sat) == nxt_sat
    assert saturday_floor(sun) == nxt_sat


def test_saturday_cadence_refits_only_at_week_boundaries():
    fit = SaturdayCadenceFit(fit_trend)
    bars = make_daily_bars(trend_closes(80))
    # Train segments ending Mon..Sun of one week, then the next week.
    fit(bars[0:60])    # ends Thu 2026-03-05 (week of Sat 2026-02-28)
    fit(bars[1:61])    # ends Fri 2026-03-06 -> same week, cached
    fit(bars[2:62])    # ends Sat 2026-03-07 -> new week, refit
    fit(bars[3:63])    # ends Sun 2026-03-08 -> same week, cached
    assert fit.calls == 4
    assert fit.refits == 2


# ---------------- head-to-head ----------------

def test_saturday_cadence_head_to_head_trend_panel():
    bars = make_daily_bars(trend_closes(300))
    base, sat, calls = head_to_head(bars)
    assert base["trades"] >= 3 and sat["trades"] >= 3
    assert calls == len(bars) - CFG.train_bars - CFG.test_bars + 1
    assert sat["refits"] < base["refits"]  # weekly refits, not per-window
    verdict = cadence_verdict(base, sat)
    assert set(verdict) == {"adopt", "same_or_better_pf",
                            "same_or_better_positive_fraction", "fewer_refits"}
    # Numbers recorded for the evidence doc (visible with -s / -v).
    print("\nTREND panel: base PF=%s pos=%.3f refits=%d | sat PF=%s pos=%.3f "
          "refits=%d | verdict=%s"
          % (base["profit_factor_net"], base["positive_window_fraction"],
             base["refits"], sat["profit_factor_net"],
             sat["positive_window_fraction"], sat["refits"], verdict))


def test_saturday_cadence_head_to_head_flip_panel():
    bars = make_daily_bars(flip_closes(300))
    base, sat, _calls = head_to_head(bars)
    assert base["trades"] >= 3 and sat["trades"] >= 3
    assert sat["refits"] < base["refits"]
    verdict = cadence_verdict(base, sat)
    print("\nFLIP panel: base PF=%s pos=%.3f refits=%d | sat PF=%s pos=%.3f "
          "refits=%d | verdict=%s"
          % (base["profit_factor_net"], base["positive_window_fraction"],
             base["refits"], sat["profit_factor_net"],
             sat["positive_window_fraction"], sat["refits"], verdict))
