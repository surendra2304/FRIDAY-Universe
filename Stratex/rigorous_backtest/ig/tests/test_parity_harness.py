"""Tests for TASK-IG2-STR-05 parity_harness (stdlib-only, offline).

Deterministic hand-built price paths only — mechanics evidence, never
performance evidence (same rule as the harness's own test suite).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.parity_harness import (  # noqa: E402
    BacktestRunner, LiveRunner, parity_report, replay_parity,
    run_parity_check,
)


def make_bars(n=240):
    bars = []
    price = 100.0
    deltas = [0.006, 0.006, 0.006, -0.012, 0.004, 0.004, -0.002, 0.008]
    prev = price
    for i in range(n):
        price *= 1.0 + deltas[i % len(deltas)]
        bars.append({"time": i, "open": prev, "high": max(prev, price) * 1.001,
                     "low": min(prev, price) * 0.999, "close": price})
        prev = price
    return bars


class MeanCrossStrategy:
    """One strategy definition: cross of close vs its trailing mean.
    Used UNCHANGED by both runners — that is the point of the harness."""

    def __init__(self, window=5, sl_pct=0.03, tp_pct=0.05):
        self.window = window
        self.sl_pct = sl_pct
        self.tp_pct = tp_pct
        self.reset()

    def reset(self):
        self.closes = []
        self.above = None

    def on_bar(self, bar):
        out = []
        if len(self.closes) >= self.window:
            mean = sum(self.closes[-self.window:]) / self.window
            above = bar["close"] > mean
            if self.above is False and above:
                out.append({"side": "LONG", "sl": bar["close"] * (1 - self.sl_pct),
                            "tp": bar["close"] * (1 + self.tp_pct)})
            elif self.above is True and not above:
                out.append({"side": "SHORT", "sl": bar["close"] * (1 + self.sl_pct),
                            "tp": bar["close"] * (1 - self.tp_pct)})
            self.above = above
        self.closes.append(bar["close"])
        return out


def factory():
    return MeanCrossStrategy()


BARS = make_bars()


def test_backtest_and_live_traces_are_identical():
    report = run_parity_check(BARS, factory)
    assert report["identical"], report["first_divergence"]
    # the comparison is only meaningful if the strategy actually traded
    assert report["counts"]["signals"]["a"] > 0
    assert report["counts"]["orders"]["a"] > 0
    assert report["counts"]["fills"]["a"] > 0


def test_same_strategy_object_semantics_in_both_runners():
    bt = BacktestRunner().run(BARS, factory())
    live = LiveRunner(factory())
    for bar in BARS:
        live.on_bar(bar)
    lv = live.finish()
    assert parity_report(bt, lv)["identical"]


def test_divergence_is_detected_and_located():
    bt = BacktestRunner().run(BARS, factory())
    other = BacktestRunner().run(BARS, MeanCrossStrategy(sl_pct=0.02))
    report = parity_report(bt, other)
    assert not report["identical"]
    assert report["first_divergence"]["stream"] in ("signals", "orders", "fills")


def test_replay_parity_against_recorded_session():
    events = []

    class ListRecorder:
        def market(self, bar, ts=None):
            events.append({"type": "market", "payload": {"bar": bar}})

        def signal(self, signal, ts=None):
            events.append({"type": "signal", "payload": signal})

        def order(self, order, ts=None):
            events.append({"type": "order", "payload": order})

        def fill(self, fill, ts=None):
            events.append({"type": "fill", "payload": fill})

    live = LiveRunner(factory(), recorder=ListRecorder())
    for bar in BARS:
        live.on_bar(bar)
    live.finish()
    report = replay_parity(events, factory)
    assert report["bars_replayed"] == len(BARS)
    assert report["recorded"]["orders"] > 0
    assert report["identical"], report["first_divergence"]


def test_replay_parity_detects_a_changed_strategy():
    events = []

    class ListRecorder:
        def market(self, bar, ts=None):
            events.append({"type": "market", "payload": {"bar": bar}})

        def signal(self, signal, ts=None):
            events.append({"type": "signal", "payload": signal})

        def order(self, order, ts=None):
            events.append({"type": "order", "payload": order})

        def fill(self, fill, ts=None):
            events.append({"type": "fill", "payload": fill})

    live = LiveRunner(factory(), recorder=ListRecorder())
    for bar in BARS:
        live.on_bar(bar)
    live.finish()
    report = replay_parity(events, lambda: MeanCrossStrategy(tp_pct=0.02))
    assert not report["identical"]


def test_event_log_file_roundtrip_replays_with_parity(tmp_path):
    """End-to-end with the real TASK-IG2-STR-06 log: record a live
    session to disk, read it back, replay it through the backtester."""
    from ig.event_replay import EventRecorder, read_events

    path = tmp_path / "session.jsonl"
    with EventRecorder(path, "parity-test") as rec:
        live = LiveRunner(factory(), recorder=rec)
        for bar in BARS:
            live.on_bar(bar)
        live.finish()
    events = read_events(path)
    report = replay_parity(events, factory)
    assert report["identical"], report["first_divergence"]
