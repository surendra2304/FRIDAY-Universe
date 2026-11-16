"""Walk-forward validation gate for Stratex RD candidates — research tooling.

TASK-IG2-STR-04 (IG wave 2; pattern from the claude-trading-skills repo
card, agiprolabs — its backtesting skills name walk-forward validation,
not a single in-sample backtest, as the promotion test).

WHY: the RD programme already judges finished trade lists on fixed
calendar folds (rigorous_backtest/walkforward.py + the pre-registered
promotion bar in rd/common.py), but nothing forced a CANDIDATE to prove
itself on rolling train/test windows before it could be promoted to
forward/paper testing. A candidate tuned on one segment could pass a
single backtest and still be curve-fit. This gate closes that hole:

  for each rolling window (train segment strictly before test segment):
      1. fit_fn (if given) selects parameters on the TRAIN segment ONLY
      2. signal_fn generates signals over train+test (train bars are
         indicator warm-up; they can never produce a counted trade)
      3. trades are simulated with the harness MODULE convention
         (signal on close of bar i -> enter at open of bar i+1,
         stop-before-target worst case, entry bar exit-checked) and the
         harness cost model (5 bps fee + 3 bps spread/slippage per side)
      4. a trade counts ONLY if its ENTRY bar falls inside the test
         segment — the same entry-time attribution walkforward.py uses

The gate passes only if ALL pre-registered checks hold (see GateConfig):
enough windows, enough pooled test trades, pooled test expectancy > 0,
pooled test profit factor >= 1.2 (the RD programme's PROMOTION_BAR
value), and a minimum fraction of test windows with positive expectancy.
A window with zero test trades counts AGAINST the positive fraction —
a candidate that does not trade in a window has not validated there.

Bars are plain dicts {"time", "open", "high", "low", "close"} so the
gate runs on any bar source the RD programme can produce, with no
pandas dependency. RESEARCH-ONLY: this module imports nothing from
production, places no orders, and promotes nothing by itself — it
returns a verdict the RD pipeline must check (require_gate) before a
candidate advances. DEMO-ONLY programme: a pass here is evidence for
paper/forward testing, never for live trading.

Stdlib only, Python 3.10-compatible. Fully deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class GateFailed(Exception):
    """Raised by require_gate() when a candidate fails the gate."""


@dataclass(frozen=True)
class GateConfig:
    train_bars: int = 200
    test_bars: int = 100
    step_bars: int | None = None          # default: test_bars (non-overlapping tests)
    min_windows: int = 3
    min_pooled_test_trades: int = 30
    min_positive_window_fraction: float = 0.6
    min_pooled_profit_factor: float = 1.2  # rd/common.py PROMOTION_BAR value
    fee_bps_per_side: float = 5.0          # harness cost model (simulator.Costs)
    slip_bps_per_side: float = 3.0

    @property
    def step(self) -> int:
        return self.step_bars if self.step_bars is not None else self.test_bars

    @property
    def per_side_rate(self) -> float:
        return (self.fee_bps_per_side + self.slip_bps_per_side) / 10000.0


@dataclass
class Trade:
    entry_bar: int        # absolute bar index of the entry fill
    exit_bar: int
    side: str             # "LONG" | "SHORT"
    entry_price: float    # raw (pre-cost) fill reference
    exit_price: float
    net_return: float     # fraction of entry price, net of all costs
    exit_reason: str      # "TP" | "SL" | "END_OF_DATA"


def rolling_windows(n_bars: int, config: GateConfig) -> list[dict]:
    """Rolling (train, test) index windows. Test never overlaps its train
    and never starts before its train ends — no look-ahead by construction."""
    if config.train_bars <= 0 or config.test_bars <= 0 or config.step <= 0:
        raise ValueError("train_bars, test_bars and step must be positive")
    windows = []
    start = 0
    k = 0
    while start + config.train_bars + config.test_bars <= n_bars:
        train = (start, start + config.train_bars)
        test = (train[1], train[1] + config.test_bars)
        windows.append({"window": k, "train": train, "test": test})
        k += 1
        start += config.step
    return windows


def _net_return(side: str, entry: float, exit_: float, per_side_rate: float) -> float:
    r = per_side_rate
    if side == "LONG":
        entry_adj = entry * (1 + r)
        exit_adj = exit_ * (1 - r)
        return (exit_adj - entry_adj) / entry_adj
    entry_adj = entry * (1 - r)
    exit_adj = exit_ * (1 + r)
    return (entry_adj - exit_adj) / entry_adj


def simulate_signals(bars: list[dict], signals, config: GateConfig,
                     index_offset: int = 0) -> list[Trade]:
    """MODULE-convention simulation over `bars` (a view). `signals` are
    (view_bar_index, side, sl_price, tp_price) evaluated on that bar's
    close. Returned trade bar indices are absolute (view index +
    index_offset). One position at a time."""
    sig_by_bar = {i: (side, sl, tp) for (i, side, sl, tp) in signals}
    trades: list[Trade] = []
    pos = None  # (side, sl, tp, entry_view_idx, entry_price)

    def check_exit(view_idx: int, side: str, sl: float, tp: float):
        bar = bars[view_idx]
        o, h, l = bar["open"], bar["high"], bar["low"]
        if side == "LONG":
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

    n = len(bars)
    for i in range(n):
        if pos is not None:
            side, sl, tp, entry_idx, entry_price = pos
            hit = check_exit(i, side, sl, tp)
            if hit is not None:
                exit_price, reason = hit
                trades.append(Trade(index_offset + entry_idx, index_offset + i,
                                    side, entry_price, exit_price,
                                    _net_return(side, entry_price, exit_price,
                                                config.per_side_rate), reason))
                pos = None
        if pos is None and i in sig_by_bar and i + 1 < n:
            side, sl, tp = sig_by_bar[i]
            entry_idx = i + 1
            entry_price = bars[entry_idx]["open"]
            pos = (side, sl, tp, entry_idx, entry_price)
            hit = check_exit(entry_idx, side, sl, tp)
            if hit is not None:
                exit_price, reason = hit
                trades.append(Trade(index_offset + entry_idx,
                                    index_offset + entry_idx, side, entry_price,
                                    exit_price,
                                    _net_return(side, entry_price, exit_price,
                                                config.per_side_rate), reason))
                pos = None
    if pos is not None:
        side, sl, tp, entry_idx, entry_price = pos
        exit_price = bars[n - 1]["close"]
        trades.append(Trade(index_offset + entry_idx, index_offset + n - 1,
                            side, entry_price, exit_price,
                            _net_return(side, entry_price, exit_price,
                                        config.per_side_rate), "END_OF_DATA"))
    return trades


def trade_metrics(trades: list[Trade]) -> dict:
    """Aggregate metrics for a trade list. All returns net of costs."""
    n = len(trades)
    if n == 0:
        return {"trades": 0, "wins": 0, "win_rate": None, "expectancy_net": None,
                "profit_factor_net": None, "total_return_net": None,
                "max_drawdown_net": None}
    nets = [t.net_return for t in trades]
    wins = [r for r in nets if r > 0]
    losses = [r for r in nets if r < 0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    if gross_loss > 0:
        pf = gross_profit / gross_loss
    elif gross_profit > 0:
        pf = float("inf")
    else:
        pf = None
    equity = 1.0
    curve = [1.0]
    for t in sorted(trades, key=lambda t: t.entry_bar):
        equity *= 1.0 + t.net_return
        curve.append(equity)
    peak = curve[0]
    max_dd = 0.0
    for v in curve:
        peak = max(peak, v)
        max_dd = min(max_dd, v / peak - 1.0)
    total = 1.0
    for r in nets:
        total *= 1.0 + r
    return {"trades": n, "wins": len(wins), "win_rate": len(wins) / n,
            "expectancy_net": sum(nets) / n,
            "profit_factor_net": pf,
            "total_return_net": total - 1.0,
            "max_drawdown_net": max_dd}


@dataclass
class GateReport:
    passed: bool
    checks: dict
    windows: list
    pooled: dict
    config: GateConfig = field(default_factory=GateConfig)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "checks": self.checks,
                "windows": self.windows, "pooled": self.pooled,
                "config": {"train_bars": self.config.train_bars,
                           "test_bars": self.config.test_bars,
                           "step_bars": self.config.step,
                           "min_windows": self.config.min_windows,
                           "min_pooled_test_trades": self.config.min_pooled_test_trades,
                           "min_positive_window_fraction": self.config.min_positive_window_fraction,
                           "min_pooled_profit_factor": self.config.min_pooled_profit_factor,
                           "fee_bps_per_side": self.config.fee_bps_per_side,
                           "slip_bps_per_side": self.config.slip_bps_per_side}}


def evaluate_walk_forward(bars: list[dict], signal_fn, fit_fn=None,
                          config: GateConfig | None = None) -> GateReport:
    """Run the walk-forward gate over `bars`.

    signal_fn(view_bars, params) -> iterable of (view_bar_index, side,
    sl_price, tp_price). fit_fn(train_bars) -> params, called once per
    window with ONLY that window's train segment; without fit_fn, params
    is None. Trades are counted only when the entry bar is inside the
    window's test segment.
    """
    config = config or GateConfig()
    windows = rolling_windows(len(bars), config)
    window_reports = []
    pooled_trades: list[Trade] = []
    for w in windows:
        train_lo, train_hi = w["train"]
        test_lo, test_hi = w["test"]
        params = fit_fn(bars[train_lo:train_hi]) if fit_fn is not None else None
        view = bars[train_lo:test_hi]
        signals = signal_fn(view, params)
        all_trades = simulate_signals(view, signals, config, index_offset=train_lo)
        test_trades = [t for t in all_trades if test_lo <= t.entry_bar < test_hi]
        pooled_trades.extend(test_trades)
        m = trade_metrics(test_trades)
        window_reports.append({
            "window": w["window"], "train": [train_lo, train_hi],
            "test": [test_lo, test_hi],
            "params_from_train_only": fit_fn is not None,
            **m,
            "positive": bool(m["expectancy_net"] is not None and m["expectancy_net"] > 0),
        })
    pooled = trade_metrics(pooled_trades)
    n_windows = len(window_reports)
    positive = sum(1 for w in window_reports if w["positive"])
    positive_fraction = (positive / n_windows) if n_windows else 0.0
    pf = pooled["profit_factor_net"]
    checks = {
        "windows_gte_min": n_windows >= config.min_windows,
        "pooled_test_trades_gte_min": pooled["trades"] >= config.min_pooled_test_trades,
        "pooled_expectancy_gt_0": (pooled["expectancy_net"] or 0.0) > 0.0,
        "pooled_profit_factor_gte_min": (
            pf is not None and pf != float("inf") and pf >= config.min_pooled_profit_factor),
        "positive_window_fraction_gte_min": (
            positive_fraction >= config.min_positive_window_fraction),
    }
    return GateReport(passed=all(checks.values()),
                      checks={**checks,
                              "positive_windows": positive,
                              "windows_total": n_windows,
                              "positive_window_fraction": positive_fraction},
                      windows=window_reports, pooled=pooled, config=config)


def require_gate(report: GateReport) -> GateReport:
    """Pipeline guard: raise GateFailed unless the candidate passed.
    The RD pipeline calls this before a candidate advances to
    forward/paper testing."""
    if not report.passed:
        failed = [k for k, v in report.checks.items() if v is False]
        raise GateFailed(f"walk-forward gate FAILED; failing checks: {failed}")
    return report
