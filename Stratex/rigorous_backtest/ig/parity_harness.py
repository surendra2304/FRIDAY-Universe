"""Backtest = live parity harness for Stratex strategies — research tooling.

TASK-IG2-STR-05 (IG wave 2; pattern from the NautilusTrader repo card —
"the same strategy code runs in backtest and live with no
reimplementation").

WHY: a backtest only means something if the strategy that produced it
is the strategy that runs live. Stratex historically grew separate
backtest and execution code paths, so a strategy could behave one way
in research and another way in the (demo) engine. This harness makes
parity a tested property instead of an assumption:

  - A strategy is ONE object with one method: on_bar(bar) -> intents.
    It is never rewritten, subclassed or re-parameterised per runner.
  - Both runners drive that same object through ONE shared execution
    core (ExecutionCore): the batch BacktestRunner (all bars at once,
    as research does) and the streaming LiveRunner (one bar at a time,
    exactly as a live demo engine receives bars, optionally recording
    every event to an ig/event_replay.py log).
  - parity_report() diffs the two traces — signals, orders, fills —
    field by field and names the first divergence, if any.
  - replay_parity() takes a recorded session (event dicts in
    ig/event_replay.py format, e.g. read via event_replay.read_events),
    re-runs its market bars through the BacktestRunner with a fresh
    instance of the same strategy, and diffs the orders/fills the
    backtester produces against the ones the live session recorded.

Execution semantics are the harness MODULE convention, shared verbatim
by both runners because there is only one implementation: an intent
raised on the close of bar i fills at the OPEN of bar i+1; the entry
bar is exit-checked; stop is assumed hit before target when both are
inside one bar; costs are the harness model (5 bps fee + 3 bps
spread/slippage per side) applied in price space. One position at a
time; an intent raised while a position is open is recorded as a
signal but produces no order (same rule in both runners).

Bars are plain dicts {"time", "open", "high", "low", "close"}; intents
are dicts {"side": "LONG"|"SHORT", "sl": float, "tp": float,
"qty": float (optional, default 1.0)}.

RESEARCH-ONLY / DEMO-ONLY: the "live" runner is a paper driver for the
same bar stream — it connects to no venue and places no real orders.
Parity evidence supports the demo programme only; nothing here enables
or authorises live trading.

Stdlib only, Python 3.10-compatible. Fully deterministic.
"""
from __future__ import annotations

FEE_BPS_PER_SIDE = 5.0
SLIP_BPS_PER_SIDE = 3.0
_PER_SIDE_RATE = (FEE_BPS_PER_SIDE + SLIP_BPS_PER_SIDE) / 10000.0
_FLOAT_TOL = 1e-9


def _net_return(side: str, entry: float, exit_: float) -> float:
    r = _PER_SIDE_RATE
    if side == "LONG":
        entry_adj = entry * (1 + r)
        exit_adj = exit_ * (1 - r)
        return (exit_adj - entry_adj) / entry_adj
    entry_adj = entry * (1 - r)
    exit_adj = exit_ * (1 + r)
    return (entry_adj - exit_adj) / entry_adj


class ExecutionCore:
    """The single execution implementation both runners share.

    Feed bars one at a time with on_bar(bar, intents) where `intents`
    are the strategy's intents for THIS bar's close. Returns the trace
    events produced by that bar: orders (fills at this bar's open for
    intents raised on the previous bar) and fills (position exits).
    """

    def __init__(self, symbol: str = "TEST"):
        self.symbol = symbol
        self._bar_index = -1
        self._pending = None   # intent waiting to fill at next bar open
        self._position = None  # dict(side, sl, tp, qty, entry_bar, entry_price)
        self.trace = {"signals": [], "orders": [], "fills": []}

    def _exit_check(self, bar: dict, pos: dict):
        o, h, l = bar["open"], bar["high"], bar["low"]
        sl, tp = pos["sl"], pos["tp"]
        if pos["side"] == "LONG":
            if o <= sl:
                return o, "SL"
            if l <= sl:
                return sl, "SL"
            if o >= tp:
                return o, "TP"
            if h >= tp:
                return tp, "TP"
        else:
            if o >= sl:
                return o, "SL"
            if h >= sl:
                return sl, "SL"
            if o <= tp:
                return o, "TP"
            if l <= tp:
                return tp, "TP"
        return None

    def _close(self, exit_bar: int, exit_price: float, reason: str) -> dict:
        pos = self._position
        fill = {"bar": exit_bar, "side": pos["side"], "qty": pos["qty"],
                "entry_bar": pos["entry_bar"], "entry_price": pos["entry_price"],
                "exit_price": exit_price, "exit_reason": reason,
                "net_return": _net_return(pos["side"], pos["entry_price"], exit_price)}
        self.trace["fills"].append(fill)
        self._position = None
        return fill

    def on_bar(self, bar: dict, intents) -> list[dict]:
        """Advance one bar. `intents` are evaluated on this bar's close."""
        self._bar_index += 1
        i = self._bar_index
        produced: list[dict] = []
        # 1. A pending intent fills at this bar's open.
        if self._pending is not None and self._position is None:
            intent = self._pending
            self._pending = None
            order = {"bar": i, "side": intent["side"], "qty": intent.get("qty", 1.0),
                     "kind": "BRACKET", "price": bar["open"],
                     "sl": intent["sl"], "tp": intent["tp"]}
            self.trace["orders"].append(order)
            produced.append({"kind": "order", "order": order})
            self._position = {"side": intent["side"], "sl": intent["sl"],
                              "tp": intent["tp"], "qty": order["qty"],
                              "entry_bar": i, "entry_price": bar["open"]}
        elif self._pending is not None:
            self._pending = None  # position already open: intent lapses (both runners)
        # 2. Exit-check the open position on this bar (entry bar included).
        if self._position is not None:
            hit = self._exit_check(bar, self._position)
            if hit is not None:
                exit_price, reason = hit
                fill = self._close(i, exit_price, reason)
                produced.append({"kind": "fill", "fill": fill})
        # 3. Record this bar's signals; the first becomes pending.
        for intent in intents or []:
            signal = {"bar": i, "side": intent["side"], "sl": intent["sl"],
                      "tp": intent["tp"], "qty": intent.get("qty", 1.0)}
            self.trace["signals"].append(signal)
            if self._pending is None and self._position is None:
                self._pending = intent
        return produced

    def finish(self, last_bar: dict) -> None:
        """Close any open position at the final bar's close (END_OF_DATA),
        matching the backtest harness convention."""
        if self._position is not None:
            self._close(self._bar_index, last_bar["close"], "END_OF_DATA")


class BacktestRunner:
    """Batch driver: resets the strategy, feeds every bar, returns the trace."""

    def __init__(self, symbol: str = "TEST"):
        self.symbol = symbol

    def run(self, bars, strategy) -> dict:
        strategy.reset()
        core = ExecutionCore(self.symbol)
        for bar in bars:
            core.on_bar(bar, strategy.on_bar(bar))
        if bars:
            core.finish(bars[-1])
        return core.trace


class LiveRunner:
    """Streaming driver: one bar at a time, as a live demo engine would
    receive it. Optionally records market/signal/order/fill events to an
    event_replay.EventRecorder (duck-typed: anything with market /
    signal / order / fill methods). The strategy object and execution
    core are exactly the ones the backtester uses."""

    def __init__(self, strategy, symbol: str = "TEST", recorder=None):
        self.strategy = strategy
        self.core = ExecutionCore(symbol)
        self.recorder = recorder
        self._last_bar = None
        strategy.reset()

    def on_bar(self, bar: dict) -> list[dict]:
        if self.recorder is not None:
            self.recorder.market(bar, ts=bar.get("time"))
        intents = self.strategy.on_bar(bar)
        if self.recorder is not None:
            for intent in intents or []:
                self.recorder.signal(
                    {"bar": self.core._bar_index + 1, "side": intent["side"],
                     "sl": intent["sl"], "tp": intent["tp"],
                     "qty": intent.get("qty", 1.0)}, ts=bar.get("time"))
        produced = self.core.on_bar(bar, intents)
        if self.recorder is not None:
            for item in produced:
                if item["kind"] == "order":
                    self.recorder.order(item["order"], ts=bar.get("time"))
                else:
                    self.recorder.fill(item["fill"], ts=bar.get("time"))
        self._last_bar = bar
        return produced

    def finish(self) -> dict:
        if self._last_bar is not None:
            before = len(self.core.trace["fills"])
            self.core.finish(self._last_bar)
            if self.recorder is not None and len(self.core.trace["fills"]) > before:
                self.recorder.fill(self.core.trace["fills"][-1],
                                   ts=self._last_bar.get("time"))
        return self.core.trace

    @property
    def trace(self) -> dict:
        return self.core.trace


def _values_match(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) <= _FLOAT_TOL
        except (TypeError, ValueError):
            return False
    return a == b


def _diff_stream(name: str, a_list, b_list):
    """First divergence between two trace streams, or None."""
    if len(a_list) != len(b_list):
        return {"stream": name, "index": min(len(a_list), len(b_list)),
                "reason": f"count differs: {len(a_list)} vs {len(b_list)}",
                "a": a_list[min(len(a_list), len(b_list))] if len(a_list) > len(b_list) else None,
                "b": b_list[min(len(a_list), len(b_list))] if len(b_list) > len(a_list) else None}
    for idx, (a, b) in enumerate(zip(a_list, b_list)):
        keys = sorted(set(a) | set(b))
        for k in keys:
            if k not in a or k not in b or not _values_match(a[k], b[k]):
                return {"stream": name, "index": idx, "field": k,
                        "reason": f"field {k!r} differs", "a": a, "b": b}
    return None


def parity_report(trace_a: dict, trace_b: dict) -> dict:
    """Diff two traces (signals, orders, fills). `identical` is True only
    if every stream matches exactly (floats within 1e-9)."""
    divergence = None
    for stream in ("signals", "orders", "fills"):
        divergence = _diff_stream(stream, trace_a.get(stream, []), trace_b.get(stream, []))
        if divergence is not None:
            break
    return {"identical": divergence is None,
            "counts": {s: {"a": len(trace_a.get(s, [])),
                           "b": len(trace_b.get(s, []))}
                       for s in ("signals", "orders", "fills")},
            "first_divergence": divergence}


def run_parity_check(bars, strategy_factory, symbol: str = "TEST") -> dict:
    """The headline check: build the strategy twice from the same factory
    (the SAME definition, unchanged), run one instance through the
    backtester and one through the streaming live runner over the same
    bars, and diff the traces."""
    backtest_trace = BacktestRunner(symbol).run(bars, strategy_factory())
    live = LiveRunner(strategy_factory(), symbol=symbol)
    for bar in bars:
        live.on_bar(bar)
    live_trace = live.finish()
    return parity_report(backtest_trace, live_trace)


def replay_parity(events, strategy_factory, symbol: str = "TEST") -> dict:
    """Replay a recorded session: extract its market bars, re-run them
    through the backtester with a fresh instance of the same strategy,
    and diff the produced orders/fills against the recorded ones.
    `events` are ig/event_replay.py event dicts."""
    bars = [e["payload"]["bar"] for e in events if e["type"] == "market"]
    recorded_orders = [e["payload"] for e in events if e["type"] == "order"]
    recorded_fills = [e["payload"] for e in events if e["type"] == "fill"]
    trace = BacktestRunner(symbol).run(bars, strategy_factory())
    report = parity_report(
        {"signals": [], "orders": trace["orders"], "fills": trace["fills"]},
        {"signals": [], "orders": recorded_orders, "fills": recorded_fills})
    report["bars_replayed"] = len(bars)
    report["recorded"] = {"orders": len(recorded_orders), "fills": len(recorded_fills)}
    return report
