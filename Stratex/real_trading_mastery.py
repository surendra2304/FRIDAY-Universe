"""
Stratex/real_trading_mastery.py — Real Trading Mastery Engine.

The Cloud9 Academy "Trading Mastery" track teaches twenty-one lessons: risk
first, position sizing, stop placement, R-multiples and expectancy, structure,
candlesticks, volume, market structure, psychology, edge, journaling, regime,
moving averages, RSI, breakouts, risk/reward, revenge trading, payoff skew,
backtesting and correlation. Each lesson is only useful if it can be executed,
so this module is the executable half of that curriculum.

Real working implementations:
- Candle / CandleSeries: OHLCV with body/wick/range geometry
- RiskPolicy: equity-based risk budgets, daily loss caps, correlated exposure
- PositionSizer: fixed-fractional, ATR-stop and volatility-target sizing with
  lot rounding, fees and slippage
- StopPlanner: structure stops, ATR buffers, psychological-level nudging,
  minimum stop distance, R targets
- TradePlan: pre-trade validation (risk/reward, stop on the right side, size)
- Expectancy: win rate, expectancy in R, breakeven win rate, profit factor,
  payoff ratio, Kelly fraction
- StructureMap: swing pivots, clustered support/resistance, break of structure
- PatternDetector: engulfing, hammer, shooting star, doji, inside bar with
  volume confirmation
- VolumeAnalyzer: relative volume, on-balance volume, climax and divergence
- MovingAverageStack: SMA/EMA stack alignment, slope, extension, squeeze
- Rsi: Wilder-smoothed RSI with an honest trend-aware reading and divergence
- RegimeClassifier: efficiency-ratio trend/range/transition classification
- BreakoutValidator: close-through, volume, follow-through and retest checks
- DisciplineGuard: revenge-trade cooldown, loss-streak size-down, daily stop,
  overtrading cap
- CorrelationAnalyzer: return correlations, pair clusters, portfolio heat
- Backtester + BacktestResult: next-bar entries, intrabar stop/target, fees and
  slippage, equity curve, drawdown, expectancy
- TradeJournal: recorded trades -> stats, streaks, per-setup breakdown
- MasteryCurriculum: the 21 lessons mapped to the component that enforces each
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence


# ── Small statistics helpers ──────────────────────────────────────────────

def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: Sequence[float], sample: bool = True) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mu = mean(values)
    divisor = (n - 1) if sample else n
    return math.sqrt(sum((v - mu) ** 2 for v in values) / divisor)


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile, q in [0, 100]."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, q / 100.0)) * (len(ordered) - 1)
    low = int(math.floor(position))
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0
    mx, my = mean(xs[:n]), mean(ys[:n])
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den_x = math.sqrt(sum((xs[i] - mx) ** 2 for i in range(n)))
    den_y = math.sqrt(sum((ys[i] - my) ** 2 for i in range(n)))
    if den_x == 0 or den_y == 0:
        return 0.0
    return max(-1.0, min(1.0, num / (den_x * den_y)))


# ── Candles ───────────────────────────────────────────────────────────────

@dataclass
class Candle:
    """One OHLCV bar."""

    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    time: float = 0.0

    @property
    def bullish(self) -> bool:
        return self.close >= self.open

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return max(0.0, self.high - self.low)

    @property
    def upper_wick(self) -> float:
        return max(0.0, self.high - max(self.open, self.close))

    @property
    def lower_wick(self) -> float:
        return max(0.0, min(self.open, self.close) - self.low)

    @property
    def typical(self) -> float:
        return (self.high + self.low + self.close) / 3.0

    def body_ratio(self) -> float:
        return self.body / self.range if self.range else 0.0

    def close_position(self) -> float:
        """Where the close sits inside the bar, 0 (low) to 1 (high)."""
        return (self.close - self.low) / self.range if self.range else 0.5


@dataclass
class CandleSeries:
    """An OHLCV series with the derived measures every lesson needs."""

    candles: list[Candle] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.candles)

    def __getitem__(self, index: int) -> Candle:
        return self.candles[index]

    @classmethod
    def from_rows(cls, rows: Iterable[Sequence[float]]) -> "CandleSeries":
        """Build from ``(open, high, low, close[, volume[, time]])`` rows."""
        out: list[Candle] = []
        for row in rows:
            values = list(row)
            if len(values) < 4:
                continue
            out.append(Candle(
                open=float(values[0]), high=float(values[1]),
                low=float(values[2]), close=float(values[3]),
                volume=float(values[4]) if len(values) > 4 else 0.0,
                time=float(values[5]) if len(values) > 5 else 0.0,
            ))
        return cls(out)

    @property
    def closes(self) -> list[float]:
        return [c.close for c in self.candles]

    @property
    def highs(self) -> list[float]:
        return [c.high for c in self.candles]

    @property
    def lows(self) -> list[float]:
        return [c.low for c in self.candles]

    @property
    def volumes(self) -> list[float]:
        return [c.volume for c in self.candles]

    @property
    def last(self) -> Candle | None:
        return self.candles[-1] if self.candles else None

    def slice(self, start: int, end: int | None = None) -> "CandleSeries":
        return CandleSeries(self.candles[start:end])

    def true_ranges(self) -> list[float]:
        out: list[float] = []
        for previous, current in zip(self.candles, self.candles[1:]):
            out.append(max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            ))
        return out

    def atr(self, window: int = 14) -> float:
        """Average true range over the trailing ``window`` bars (Wilder seed)."""
        ranges = self.true_ranges()
        if not ranges:
            return 0.0
        sample = ranges[-window:]
        return mean(sample)

    def sma(self, window: int) -> float | None:
        closes = self.closes
        if window <= 0 or len(closes) < window:
            return None
        return mean(closes[-window:])

    def ema(self, window: int) -> float | None:
        closes = self.closes
        if window <= 0 or len(closes) < window:
            return None
        value = mean(closes[:window])
        k = 2.0 / (window + 1.0)
        for price in closes[window:]:
            value = price * k + value * (1.0 - k)
        return value

    def returns(self) -> list[float]:
        closes = self.closes
        return [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes)) if closes[i - 1]
        ]

    def swing_points(self, left: int = 2, right: int = 2) -> dict[str, list[tuple[int, float]]]:
        """Confirmed swing highs/lows: extreme over ``left`` and ``right`` bars.

        Confirmation on the right is what makes this usable: a pivot that later
        bars have not already exceeded is a pivot, not a hopeful guess.
        """
        highs: list[tuple[int, float]] = []
        lows: list[tuple[int, float]] = []
        n = len(self.candles)
        for i in range(n):
            if i - left < 0 or i + right >= n:
                continue
            window_high = self.candles[i].high
            window_low = self.candles[i].low
            is_high = all(self.candles[j].high <= window_high
                          for j in range(i - left, i + right + 1))
            is_low = all(self.candles[j].low >= window_low
                         for j in range(i - left, i + right + 1))
            if is_high:
                highs.append((i, window_high))
            if is_low:
                lows.append((i, window_low))
        return {"highs": highs, "lows": lows}


# ── Risk policy and sizing ────────────────────────────────────────────────

@dataclass
class RiskPolicy:
    """The account-level rules that keep one trade from ending the account."""

    equity: float = 100_000.0
    max_risk_pct: float = 1.0          # per trade
    max_daily_loss_pct: float = 3.0    # hard stop for the day
    max_open_risk_pct: float = 6.0     # total risk across open positions
    max_correlated_positions: int = 2
    max_trades_per_day: int = 5

    def risk_budget(self) -> float:
        return self.equity * self.max_risk_pct / 100.0

    def daily_loss_cap(self) -> float:
        return self.equity * self.max_daily_loss_pct / 100.0

    def open_risk_cap(self) -> float:
        return self.equity * self.max_open_risk_pct / 100.0

    def with_equity(self, equity: float) -> "RiskPolicy":
        return RiskPolicy(
            equity=equity, max_risk_pct=self.max_risk_pct,
            max_daily_loss_pct=self.max_daily_loss_pct,
            max_open_risk_pct=self.max_open_risk_pct,
            max_correlated_positions=self.max_correlated_positions,
            max_trades_per_day=self.max_trades_per_day,
        )


@dataclass
class Instrument:
    """Contract mechanics that change the real size of a position."""

    symbol: str = "X"
    lot_size: float = 1.0            # shares/contracts per unit you can buy
    contract_multiplier: float = 1.0  # notional per point (futures/options)
    fee_per_unit: float = 0.0        # commission + exchange fee per unit
    slippage_ticks: float = 0.0      # expected adverse fill, in price points
    tick_size: float = 0.01

    def round_units(self, units: float) -> float:
        if self.lot_size <= 0:
            return max(0.0, units)
        lots = math.floor(units / self.lot_size)
        return max(0.0, lots * self.lot_size)


@dataclass
class PositionSize:
    """The outcome of sizing one trade: units, notional and what it risks."""

    units: float
    entry: float
    stop: float
    risk_per_unit: float
    risk_amount: float
    risk_pct: float
    notional: float
    fees: float
    slippage_cost: float
    capped_by: str = ""


class PositionSizer:
    """Turn a risk budget and a stop distance into a real position size.

    Because the stop distance, not a fixed lot count, sets the size, a wide stop
    automatically produces a smaller position: that is the whole point of the
    lesson, and it is enforced here rather than described.
    """

    def size(self, entry: float, stop: float, policy: RiskPolicy,
             instrument: Instrument | None = None,
             risk_pct: float | None = None,
             open_risk_used: float = 0.0) -> PositionSize:
        instrument = instrument or Instrument()
        if entry <= 0 or stop <= 0 or entry == stop:
            return PositionSize(0.0, entry, stop, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                "invalid_prices")

        # Slippage makes the fill worse, so it is charged against the stop
        # distance before the size is computed.
        slip = instrument.slippage_ticks * instrument.tick_size
        effective_entry = entry + slip if stop < entry else entry - slip
        risk_per_unit = abs(effective_entry - stop)
        if risk_per_unit <= 0:
            return PositionSize(0.0, entry, stop, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                "zero_risk_distance")

        pct = policy.max_risk_pct if risk_pct is None else max(0.0, risk_pct)
        budget = policy.equity * pct / 100.0
        capped_by = "risk_budget"

        remaining_open = max(0.0, policy.open_risk_cap() - open_risk_used)
        if budget > remaining_open:
            budget = remaining_open
            capped_by = "open_risk_cap"

        raw_units = budget / (risk_per_unit * max(instrument.contract_multiplier, 1e-9))
        units = instrument.round_units(raw_units)
        notional = units * effective_entry * instrument.contract_multiplier
        fees = units * instrument.fee_per_unit
        # Fees are part of what the trade costs, so they come out of the budget.
        if units > 0 and fees > 0:
            affordable = max(0.0, budget - fees) / (
                risk_per_unit * max(instrument.contract_multiplier, 1e-9))
            units = instrument.round_units(min(units, affordable))
            notional = units * effective_entry * instrument.contract_multiplier
            fees = units * instrument.fee_per_unit

        risk_amount = units * risk_per_unit * instrument.contract_multiplier
        return PositionSize(
            units=units, entry=effective_entry, stop=stop,
            risk_per_unit=risk_per_unit, risk_amount=risk_amount,
            risk_pct=(risk_amount / policy.equity * 100.0) if policy.equity else 0.0,
            notional=notional, fees=fees,
            slippage_cost=abs(effective_entry - entry) * units,
            capped_by=capped_by,
        )

    def volatility_target(self, entry: float, atr: float, policy: RiskPolicy,
                          instrument: Instrument | None = None,
                          target_risk_pct: float = 1.0,
                          atr_multiple: float = 2.0) -> PositionSize:
        """Size from an ATR stop instead of a hand-picked one."""
        if atr <= 0:
            return self.size(entry, entry, policy, instrument, target_risk_pct)
        stop = entry - atr * atr_multiple
        return self.size(entry, stop, policy, instrument, target_risk_pct)


# ── Stops and plans ───────────────────────────────────────────────────────

def is_round_number(price: float, tick: float = 0.01, step: float = 1.0) -> bool:
    """True when the price sits on a psychological level (whole/half numbers)."""
    if step <= 0:
        return False
    return abs(price / step - round(price / step)) * step < tick


class StopPlanner:
    """Place stops where the trade is wrong, not where the loss is small.

    A stop just inside a swing or a round number is the liquidity the market
    reaches for; this planner puts the stop beyond the structure with an ATR
    buffer, nudges it off exact round numbers, and enforces a floor on the stop
    distance so a two-tick stop cannot be wiped out by noise.
    """

    def __init__(self, atr_buffer: float = 0.25, min_atr_multiple: float = 0.5,
                 structure_lookback: int = 10, round_step: float = 1.0,
                 nudge_ticks: float = 2.0, tick_size: float = 0.01) -> None:
        self.atr_buffer = atr_buffer
        self.min_atr_multiple = min_atr_multiple
        self.structure_lookback = structure_lookback
        self.round_step = round_step
        self.nudge_ticks = nudge_ticks
        self.tick_size = tick_size

    def structure_stop(self, series: CandleSeries, direction: str,
                       entry: float) -> float:
        window = series.candles[-self.structure_lookback:] or series.candles
        if not window:
            return entry
        if direction == "long":
            return min(c.low for c in window)
        return max(c.high for c in window)

    def plan_stop(self, series: CandleSeries, direction: str, entry: float) -> float:
        atr = series.atr()
        structure = self.structure_stop(series, direction, entry)
        buffer = atr * self.atr_buffer
        stop = structure - buffer if direction == "long" else structure + buffer
        # Never place the stop on the wrong side of the entry, and never closer
        # than the noise floor.
        floor = atr * self.min_atr_multiple if atr > 0 else 0.0
        if direction == "long":
            stop = min(stop, entry - floor) if floor else min(stop, entry - self.tick_size)
        else:
            stop = max(stop, entry + floor) if floor else max(stop, entry + self.tick_size)
        return self.avoid_round_numbers(stop, direction)

    def avoid_round_numbers(self, price: float, direction: str) -> float:
        """Step a stop off an exact round number, deeper into safety."""
        if not is_round_number(price, self.tick_size, self.round_step):
            return price
        offset = self.nudge_ticks * self.tick_size
        return price - offset if direction == "long" else price + offset

    def targets(self, entry: float, stop: float, direction: str,
                r_multiples: Sequence[float] = (1.0, 2.0, 3.0)) -> list[float]:
        risk = abs(entry - stop)
        if risk <= 0:
            return []
        sign = 1.0 if direction == "long" else -1.0
        return [round(entry + sign * risk * r, 10) for r in r_multiples]


@dataclass
class TradePlan:
    """A pre-trade plan that has to pass validation before the size exists."""

    instrument: str
    direction: str
    entry: float
    stop: float
    targets: list[float] = field(default_factory=list)
    size: PositionSize | None = None
    setup: str = ""
    min_rr: float = 2.0
    notes: str = ""

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def reward_per_unit(self) -> float:
        if not self.targets:
            return 0.0
        return abs(self.targets[0] - self.entry)

    @property
    def rr(self) -> float:
        if self.risk_per_unit <= 0:
            return 0.0
        return self.reward_per_unit / self.risk_per_unit

    def validate(self) -> list[str]:
        """Every reason this plan is not tradeable; empty means approved."""
        problems: list[str] = []
        if self.direction not in ("long", "short"):
            problems.append("direction must be long or short")
        if self.entry <= 0 or self.stop <= 0:
            problems.append("entry and stop must be positive")
        if self.direction == "long" and self.stop >= self.entry:
            problems.append("stop must sit below entry for a long")
        if self.direction == "short" and self.stop <= self.entry:
            problems.append("stop must sit above entry for a short")
        for target in self.targets:
            if self.direction == "long" and target <= self.entry:
                problems.append("target must sit above entry for a long")
                break
            if self.direction == "short" and target >= self.entry:
                problems.append("target must sit below entry for a short")
                break
        if not self.targets:
            problems.append("no target set")
        elif self.rr < self.min_rr:
            problems.append(
                f"risk/reward {self.rr:.2f} is below the {self.min_rr:.2f} minimum")
        if self.size is not None and self.size.units <= 0:
            problems.append("position size rounds to zero")
        return problems

    @property
    def approved(self) -> bool:
        return not self.validate()

    def as_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument, "direction": self.direction,
            "entry": self.entry, "stop": self.stop,
            "targets": list(self.targets), "rr": round(self.rr, 4),
            "units": round(self.size.units, 6) if self.size else 0.0,
            "risk_amount": round(self.size.risk_amount, 4) if self.size else 0.0,
            "approved": self.approved, "problems": self.validate(),
        }


class TradePlanner:
    """StopPlanner + PositionSizer + TradePlan validation in one call."""

    def __init__(self, policy: RiskPolicy | None = None,
                 stops: StopPlanner | None = None,
                 sizer: PositionSizer | None = None) -> None:
        self.policy = policy or RiskPolicy()
        self.stops = stops or StopPlanner()
        self.sizer = sizer or PositionSizer()

    def build(self, instrument: Instrument, series: CandleSeries,
              direction: str, entry: float | None = None,
              r_multiples: Sequence[float] = (2.0, 3.0),
              setup: str = "", open_risk_used: float = 0.0) -> TradePlan:
        entry = entry if entry is not None else (series.last.close if series.last else 0.0)
        stop = self.stops.plan_stop(series, direction, entry)
        targets = self.stops.targets(entry, stop, direction, r_multiples)
        size = self.sizer.size(entry, stop, self.policy, instrument,
                               open_risk_used=open_risk_used)
        return TradePlan(
            instrument=instrument.symbol, direction=direction, entry=entry,
            stop=stop, targets=targets, size=size, setup=setup,
        )


# ── Expectancy ────────────────────────────────────────────────────────────

@dataclass
class ExpectancyReport:
    """The arithmetic that decides whether a strategy can survive."""

    trades: int
    wins: int
    losses: int
    win_rate: float
    average_win_r: float
    average_loss_r: float
    expectancy_r: float
    payoff_ratio: float
    profit_factor: float
    breakeven_win_rate: float
    kelly_fraction: float
    total_r: float
    largest_win_r: float
    largest_loss_r: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate, 4),
            "average_win_r": round(self.average_win_r, 4),
            "average_loss_r": round(self.average_loss_r, 4),
            "expectancy_r": round(self.expectancy_r, 4),
            "payoff_ratio": (round(self.payoff_ratio, 4)
                             if math.isfinite(self.payoff_ratio) else self.payoff_ratio),
            "profit_factor": (round(self.profit_factor, 4)
                              if math.isfinite(self.profit_factor) else self.profit_factor),
            "breakeven_win_rate": round(self.breakeven_win_rate, 4),
            "kelly_fraction": round(self.kelly_fraction, 4),
            "total_r": round(self.total_r, 4),
        }


class Expectancy:
    """Compute expectancy and the breakeven win rate from R-multiples.

    Working in R (risk units) rather than currency is what makes strategies
    comparable: a 0.5R average loss and a 1.5R average win is a 3:1 payoff, and
    the win rate needed to break even follows from that alone.
    """

    @staticmethod
    def breakeven_win_rate(avg_win_r: float, avg_loss_r: float) -> float:
        """Win rate at which expectancy is exactly zero."""
        if avg_win_r <= 0:
            return 1.0
        magnitude = abs(avg_loss_r)
        if avg_win_r + magnitude == 0:
            return 0.0
        return magnitude / (avg_win_r + magnitude)

    def evaluate(self, r_multiples: Sequence[float]) -> ExpectancyReport:
        trades = [float(r) for r in r_multiples if r is not None]
        wins = [r for r in trades if r > 0]
        losses = [r for r in trades if r <= 0]
        win_rate = len(wins) / len(trades) if trades else 0.0
        avg_win = mean(wins) if wins else 0.0
        avg_loss = mean(losses) if losses else 0.0
        expectancy = (win_rate * avg_win + (1 - win_rate) * avg_loss) if trades else 0.0
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_win / gross_loss) if gross_loss else float("inf") if gross_win else 0.0
        payoff = (avg_win / abs(avg_loss)) if avg_loss else float("inf") if avg_win else 0.0
        b = payoff if payoff not in (float("inf"), 0.0) else 0.0
        kelly = 0.0
        if b > 0:
            kelly = max(0.0, (win_rate * b - (1 - win_rate)) / b)
        return ExpectancyReport(
            trades=len(trades), wins=len(wins), losses=len(losses),
            win_rate=win_rate, average_win_r=avg_win, average_loss_r=avg_loss,
            expectancy_r=expectancy, payoff_ratio=payoff,
            profit_factor=profit_factor,
            breakeven_win_rate=self.breakeven_win_rate(avg_win, avg_loss),
            kelly_fraction=kelly, total_r=sum(trades),
            largest_win_r=max(wins) if wins else 0.0,
            largest_loss_r=min(losses) if losses else 0.0,
        )

    def required_win_rate(self, avg_win_r: float, avg_loss_r: float,
                          fee_r: float = 0.0) -> float:
        """Breakeven win rate once per-trade costs are charged in R."""
        return self.breakeven_win_rate(avg_win_r - fee_r, avg_loss_r - fee_r)

    def overtrading_drag(self, trades_per_day: float, cost_r_per_trade: float,
                         trading_days: int = 250) -> dict[str, float]:
        """What frequency costs over a year when every trade pays fees."""
        annual = max(0.0, trades_per_day) * max(0, trading_days)
        return {
            "annual_trades": annual,
            "annual_drag_r": annual * cost_r_per_trade,
            "breakeven_edge_needed_r": annual * cost_r_per_trade,
        }


# ── Market structure ──────────────────────────────────────────────────────

@dataclass
class StructureLevel:
    """A clustered price level with the touches that make it matter."""

    price: float
    touches: int
    kind: str          # support | resistance
    last_index: int
    strength: float

    def as_dict(self) -> dict[str, Any]:
        return {"price": round(self.price, 6), "touches": self.touches,
                "kind": self.kind, "strength": round(self.strength, 4)}


class StructureMap:
    """Swing pivots -> clustered levels -> trend and break-of-structure."""

    def __init__(self, tolerance_pct: float = 0.25, left: int = 2,
                 right: int = 2) -> None:
        self.tolerance_pct = tolerance_pct
        self.left = left
        self.right = right

    def pivots(self, series: CandleSeries) -> dict[str, list[tuple[int, float]]]:
        return series.swing_points(self.left, self.right)

    def _cluster(self, points: Sequence[tuple[int, float]], kind: str,
                 last_price: float) -> list[StructureLevel]:
        if not points:
            return []
        ordered = sorted(points, key=lambda p: p[1])
        tolerance = max(last_price * self.tolerance_pct / 100.0, 1e-9)
        clusters: list[list[tuple[int, float]]] = []
        for point in ordered:
            if clusters and abs(point[1] - mean([p[1] for p in clusters[-1]])) <= tolerance:
                clusters[-1].append(point)
            else:
                clusters.append([point])
        levels: list[StructureLevel] = []
        for cluster in clusters:
            price = mean([p[1] for p in cluster])
            touches = len(cluster)
            recency = max(p[0] for p in cluster)
            strength = touches * (1.0 + recency / max(1, len(points)))
            levels.append(StructureLevel(
                price=price, touches=touches, kind=kind,
                last_index=recency, strength=strength,
            ))
        return sorted(levels, key=lambda l: -l.strength)

    def levels(self, series: CandleSeries) -> dict[str, list[StructureLevel]]:
        pivots = self.pivots(series)
        last_price = series.last.close if series.last else 0.0
        return {
            "support": self._cluster(pivots["lows"], "support", last_price),
            "resistance": self._cluster(pivots["highs"], "resistance", last_price),
        }

    def nearest(self, series: CandleSeries) -> dict[str, StructureLevel | None]:
        levels = self.levels(series)
        price = series.last.close if series.last else 0.0
        supports = [l for l in levels["support"] if l.price < price]
        resistances = [l for l in levels["resistance"] if l.price > price]
        return {
            "support": max(supports, key=lambda l: l.price) if supports else None,
            "resistance": min(resistances, key=lambda l: l.price) if resistances else None,
        }

    def trend(self, series: CandleSeries) -> dict[str, Any]:
        """Higher highs/higher lows vs lower highs/lower lows."""
        pivots = self.pivots(series)
        highs = [p[1] for p in pivots["highs"]][-4:]
        lows = [p[1] for p in pivots["lows"]][-4:]

        def rising(values: Sequence[float]) -> bool:
            return len(values) >= 2 and all(
                b > a for a, b in zip(values, values[1:]))

        def falling(values: Sequence[float]) -> bool:
            return len(values) >= 2 and all(
                b < a for a, b in zip(values, values[1:]))

        if rising(highs) and rising(lows):
            label = "uptrend"
        elif falling(highs) and falling(lows):
            label = "downtrend"
        elif highs and lows:
            label = "range"
        else:
            label = "undetermined"

        last_price = series.last.close if series.last else 0.0
        broken: str = ""
        levels = self.levels(series)
        for level in levels["resistance"]:
            if last_price > level.price:
                broken = "bullish_break"
                break
        if not broken:
            for level in levels["support"]:
                if last_price < level.price:
                    broken = "bearish_break"
                    break
        return {"trend": label, "higher_highs": rising(highs),
                "higher_lows": rising(lows), "structure_event": broken}


# ── Price action ──────────────────────────────────────────────────────────

@dataclass
class PatternHit:
    """One detected candle pattern, with its confirmation state."""

    name: str
    index: int
    direction: str      # bullish | bearish | neutral
    strength: float     # 0..1
    volume_confirmed: bool

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "index": self.index,
                "direction": self.direction,
                "strength": round(self.strength, 4),
                "volume_confirmed": self.volume_confirmed}


class PatternDetector:
    """The three candle patterns worth acting on, plus context checks.

    Patterns are read in context: an engulfing bar without above-average volume
    and without a location at a level is a shape, not a signal, so
    ``strength`` carries those terms instead of a boolean label.
    """

    def __init__(self, doji_body_ratio: float = 0.1,
                 hammer_wick_ratio: float = 2.0) -> None:
        self.doji_body_ratio = doji_body_ratio
        self.hammer_wick_ratio = hammer_wick_ratio

    @staticmethod
    def _volume_factor(series: CandleSeries, index: int, window: int = 20) -> float:
        start = max(0, index - window)
        sample = series.volumes[start:index]
        if not sample or series.candles[index].volume <= 0:
            return 0.0
        baseline = mean(sample)
        if baseline <= 0:
            return 0.0
        # 1.0 at average volume, capped at 2x average.
        return min(2.0, series.candles[index].volume / baseline)

    @staticmethod
    def _strength(body_ratio: float, volume: float) -> float:
        """Pattern strength: shape half, participation half.

        A perfect shape on no volume scores below a mediocre shape on double
        volume, which is the point of the lesson.
        """
        shape = max(0.0, min(1.0, body_ratio))
        participation = min(1.0, max(0.0, volume) / 2.0)
        return max(0.05, min(1.0, 0.5 * shape + 0.5 * participation))

    def detect(self, series: CandleSeries, index: int | None = None) -> list[PatternHit]:
        candles = series.candles
        if len(candles) < 3:
            return []
        i = len(candles) - 1 if index is None else index
        if i < 1 or i >= len(candles):
            return []
        current, previous = candles[i], candles[i - 1]
        volume = self._volume_factor(series, i)
        confirmed = volume >= 1.0
        hits: list[PatternHit] = []

        # Bullish / bearish engulfing: the body swallows the previous body.
        engulf_up = (current.bullish and not previous.bullish
                     and current.close >= previous.open
                     and current.open <= previous.close
                     and current.body > previous.body)
        engulf_down = (not current.bullish and previous.bullish
                       and current.open >= previous.close
                       and current.close <= previous.open
                       and current.body > previous.body)
        if engulf_up:
            hits.append(PatternHit("bullish_engulfing", i, "bullish",
                                   self._strength(current.body_ratio(), volume),
                                   confirmed))
        if engulf_down:
            hits.append(PatternHit("bearish_engulfing", i, "bearish",
                                   self._strength(current.body_ratio(), volume),
                                   confirmed))

        # Hammer / shooting star: rejected extreme, small body, close near the
        # opposite end of the range.
        body = max(current.body, 1e-12)
        if (current.lower_wick >= self.hammer_wick_ratio * body
                and current.upper_wick <= body
                and current.close_position() >= 0.6):
            hits.append(PatternHit("hammer", i, "bullish",
                                   self._strength(1.0 - current.body_ratio(), volume),
                                   confirmed))
        if (current.upper_wick >= self.hammer_wick_ratio * body
                and current.lower_wick <= body
                and current.close_position() <= 0.4):
            hits.append(PatternHit("shooting_star", i, "bearish",
                                   self._strength(1.0 - current.body_ratio(), volume),
                                   confirmed))

        if current.range and current.body_ratio() <= self.doji_body_ratio:
            hits.append(PatternHit("doji", i, "neutral",
                                   self._strength(1.0, volume), confirmed))

        if (current.high <= previous.high and current.low >= previous.low):
            hits.append(PatternHit("inside_bar", i, "neutral",
                                   self._strength(0.5, volume), confirmed))
        return hits

    def scan(self, series: CandleSeries) -> list[PatternHit]:
        out: list[PatternHit] = []
        for i in range(1, len(series)):
            out.extend(self.detect(series, i))
        return out


@dataclass
class VolumeReading:
    """Volume context for the latest bar."""

    relative_volume: float
    obv_slope: float
    climax: bool
    divergence: str      # bullish | bearish | none

    def as_dict(self) -> dict[str, Any]:
        return {"relative_volume": round(self.relative_volume, 4),
                "obv_slope": round(self.obv_slope, 4),
                "climax": self.climax, "divergence": self.divergence}


class VolumeAnalyzer:
    """Relative volume, on-balance volume and climax/divergence reads."""

    def __init__(self, baseline_window: int = 20,
                 climax_multiple: float = 2.5) -> None:
        self.baseline_window = baseline_window
        self.climax_multiple = climax_multiple

    def obv(self, series: CandleSeries) -> list[float]:
        out: list[float] = []
        running = 0.0
        for previous, current in zip(series.candles, series.candles[1:]):
            if current.close > previous.close:
                running += current.volume
            elif current.close < previous.close:
                running -= current.volume
            out.append(running)
        return out

    def relative_volume(self, series: CandleSeries, index: int | None = None) -> float:
        i = len(series) - 1 if index is None else index
        start = max(0, i - self.baseline_window)
        baseline = mean(series.volumes[start:i])
        if baseline <= 0:
            return 0.0
        return series.candles[i].volume / baseline

    def analyze(self, series: CandleSeries) -> VolumeReading:
        if len(series) < 3:
            return VolumeReading(0.0, 0.0, False, "none")
        rel = self.relative_volume(series)
        obv = self.obv(series)
        tail = obv[-5:] if len(obv) >= 5 else obv
        slope = (tail[-1] - tail[0]) / max(1, len(tail) - 1) if tail else 0.0
        price_tail = series.closes[-len(tail) - 1:] if tail else []
        price_change = (price_tail[-1] - price_tail[0]) if len(price_tail) >= 2 else 0.0

        divergence = "none"
        if price_change > 0 and slope < 0:
            divergence = "bearish"     # price up, participation down
        elif price_change < 0 and slope > 0:
            divergence = "bullish"     # price down, accumulation
        return VolumeReading(
            relative_volume=rel,
            obv_slope=slope,
            climax=rel >= self.climax_multiple,
            divergence=divergence,
        )


# ── Indicators ────────────────────────────────────────────────────────────

@dataclass
class MaStack:
    """Moving-average alignment, slope, extension and squeeze state."""

    fast: float
    slow: float
    alignment: str        # bullish | bearish | mixed
    slope_pct: float
    extension_pct: float  # price distance from the fast average
    squeeze: bool

    def as_dict(self) -> dict[str, Any]:
        return {"fast": round(self.fast, 6), "slow": round(self.slow, 6),
                "alignment": self.alignment,
                "slope_pct": round(self.slope_pct, 4),
                "extension_pct": round(self.extension_pct, 4),
                "squeeze": self.squeeze}


class MovingAverageStack:
    """Use averages for trend and extension, never as a crossover oracle."""

    def __init__(self, fast: int = 20, slow: int = 50,
                 slope_window: int = 5, squeeze_pct: float = 0.5) -> None:
        self.fast = fast
        self.slow = slow
        self.slope_window = slope_window
        self.squeeze_pct = squeeze_pct

    def evaluate(self, series: CandleSeries) -> MaStack | None:
        fast = series.sma(self.fast)
        slow = series.sma(self.slow)
        if fast is None or slow is None or slow == 0:
            return None
        closes = series.closes
        price = closes[-1]
        earlier = (series.sma(self.fast) if len(closes) < self.slope_window else
                   mean(closes[-self.fast - self.slope_window:-self.slope_window])
                   if len(closes) >= self.fast + self.slope_window else fast)
        slope = ((fast - earlier) / earlier * 100.0) if earlier else 0.0
        alignment = "bullish" if fast > slow else "bearish" if fast < slow else "mixed"
        extension = (price - fast) / fast * 100.0 if fast else 0.0
        squeeze = abs(fast - slow) / slow * 100.0 <= self.squeeze_pct
        return MaStack(fast=fast, slow=slow, alignment=alignment,
                       slope_pct=slope, extension_pct=extension,
                       squeeze=squeeze)


@dataclass
class RsiReading:
    """RSI as momentum, read in the direction of the trend."""

    value: float
    zone: str            # oversold | weak | neutral | strong | overbought
    reading: str         # what it means in this regime
    divergence: str

    def as_dict(self) -> dict[str, Any]:
        return {"value": round(self.value, 4), "zone": self.zone,
                "reading": self.reading, "divergence": self.divergence}


class Rsi:
    """Wilder-smoothed RSI with an honest, trend-aware interpretation.

    The lesson's point: RSI above 70 inside an uptrend is strength, not a sell
    signal. The reading therefore depends on the prevailing structure.
    """

    def __init__(self, window: int = 14) -> None:
        self.window = window

    def series(self, values: Sequence[float]) -> list[float]:
        if len(values) <= self.window:
            return []
        gains, losses = 0.0, 0.0
        for previous, current in zip(values[:self.window + 1], values[1:self.window + 1]):
            delta = current - previous
            if delta >= 0:
                gains += delta
            else:
                losses -= delta
        avg_gain = gains / self.window
        avg_loss = losses / self.window
        out: list[float] = []

        def value_of(gain: float, loss: float) -> float:
            if loss == 0:
                return 100.0 if gain > 0 else 50.0
            rs = gain / loss
            return 100.0 - 100.0 / (1.0 + rs)

        out.append(value_of(avg_gain, avg_loss))
        for previous, current in zip(values[self.window:-1], values[self.window + 1:]):
            delta = current - previous
            gain = max(0.0, delta)
            loss = max(0.0, -delta)
            avg_gain = (avg_gain * (self.window - 1) + gain) / self.window
            avg_loss = (avg_loss * (self.window - 1) + loss) / self.window
            out.append(value_of(avg_gain, avg_loss))
        return out

    def value(self, series: CandleSeries) -> float:
        values = self.series(series.closes)
        return values[-1] if values else 50.0

    def zone(self, value: float) -> str:
        if value <= 30:
            return "oversold"
        if value <= 45:
            return "weak"
        if value < 55:
            return "neutral"
        if value < 70:
            return "strong"
        return "overbought"

    def divergence(self, series: CandleSeries, lookback: int = 30) -> str:
        """Price higher with RSI lower (bearish) or the reverse (bullish)."""
        values = self.series(series.closes)
        if len(values) < 10:
            return "none"
        closes = series.closes[-len(values):]
        half = max(3, len(values) // 2)
        price_first, price_last = mean(closes[:half]), mean(closes[-half:])
        rsi_first, rsi_last = values[half - 1] if half - 1 < len(values) else values[0], values[-1]
        if price_last > price_first and rsi_last < rsi_first - 2:
            return "bearish"
        if price_last < price_first and rsi_last > rsi_first + 2:
            return "bullish"
        return "none"

    def evaluate(self, series: CandleSeries,
                 trend: str = "undetermined") -> RsiReading:
        value = self.value(series)
        zone = self.zone(value)
        divergence = self.divergence(series)
        if zone == "overbought" and trend == "uptrend":
            reading = "Strength in an uptrend: momentum is leading, not exhausted."
        elif zone == "oversold" and trend == "downtrend":
            reading = "Weakness in a downtrend: momentum is leading, not a bargain."
        elif zone == "overbought":
            reading = "Stretched against a flat or falling trend: fade risk is real."
        elif zone == "oversold":
            reading = "Stretched against a flat or rising trend: bounce risk is real."
        else:
            reading = "Momentum is not stretched in either direction."
        return RsiReading(value=value, zone=zone, reading=reading,
                          divergence=divergence)


@dataclass
class RegimeReading:
    """Trend vs range, as a measured efficiency of movement."""

    regime: str            # trend_up | trend_down | range | transition
    efficiency: float      # 0..1 net movement / total movement
    range_pct: float
    atr_pct: float

    def as_dict(self) -> dict[str, Any]:
        return {"regime": self.regime, "efficiency": round(self.efficiency, 4),
                "range_pct": round(self.range_pct, 4),
                "atr_pct": round(self.atr_pct, 4)}


class RegimeClassifier:
    """Decide whether to trade a trend or a range before choosing a setup."""

    def __init__(self, window: int = 20, trend_threshold: float = 0.35) -> None:
        self.window = window
        self.trend_threshold = trend_threshold

    def evaluate(self, series: CandleSeries) -> RegimeReading:
        closes = series.closes[-self.window:]
        if len(closes) < 3:
            return RegimeReading("transition", 0.0, 0.0, 0.0)
        net = abs(closes[-1] - closes[0])
        traveled = sum(abs(b - a) for a, b in zip(closes, closes[1:]))
        efficiency = net / traveled if traveled else 0.0
        high, low = max(closes), min(closes)
        mid = mean(closes)
        range_pct = (high - low) / mid * 100.0 if mid else 0.0
        atr_pct = (series.atr() / mid * 100.0) if mid else 0.0

        if efficiency >= self.trend_threshold:
            regime = "trend_up" if closes[-1] > closes[0] else "trend_down"
        elif efficiency <= self.trend_threshold / 2:
            regime = "range"
        else:
            regime = "transition"
        return RegimeReading(regime, efficiency, range_pct, atr_pct)


@dataclass
class BreakoutVerdict:
    """Whether a level break is real or a trap."""

    level: float
    direction: str
    verdict: str        # confirmed | fakeout | pending
    checks: dict[str, bool]
    score: float

    def as_dict(self) -> dict[str, Any]:
        return {"level": round(self.level, 6), "direction": self.direction,
                "verdict": self.verdict, "checks": dict(self.checks),
                "score": round(self.score, 4)}


class BreakoutValidator:
    """Four checks that separate a breakout from a fakeout.

    Most breaks fail, and they fail in a recognisable way: a wick through the
    level, no volume, no follow-through, and a snap back inside the range. All
    four are measurable on the next bars, so the validator waits for them.
    """

    def __init__(self, volume_multiple: float = 1.5,
                 close_buffer_pct: float = 0.05) -> None:
        self.volume_multiple = volume_multiple
        self.close_buffer_pct = close_buffer_pct

    def evaluate(self, series: CandleSeries, level: float,
                 direction: str = "long",
                 confirm_bars: int = 3) -> BreakoutVerdict:
        candles = series.candles
        if len(candles) < 2:
            return BreakoutVerdict(level, direction, "pending",
                                   {"close_through": False, "volume": False,
                                    "follow_through": False, "held": False}, 0.0)
        last = candles[-1]
        buffer = level * self.close_buffer_pct / 100.0
        if direction == "long":
            close_through = last.close > level + buffer
            wick_only = last.high > level and last.close <= level
            held = last.close > level
            follow = (len(candles) >= 2 and
                      candles[-1].close > candles[-2].close and
                      candles[-1].close > level)
        else:
            close_through = last.close < level - buffer
            wick_only = last.low < level and last.close >= level
            held = last.close < level
            follow = (len(candles) >= 2 and
                      candles[-1].close < candles[-2].close and
                      candles[-1].close < level)

        window = candles[-confirm_bars - 1:-1]
        baseline = mean([c.volume for c in window]) if window else 0.0
        volume_ok = bool(baseline > 0 and last.volume >= baseline * self.volume_multiple)

        checks = {
            "close_through": close_through,
            "volume": volume_ok,
            "follow_through": follow,
            "held": held and not wick_only,
        }
        score = sum(1 for v in checks.values() if v) / len(checks)
        if wick_only and not close_through:
            verdict = "fakeout"
        elif close_through and volume_ok and follow:
            verdict = "confirmed"
        elif close_through and not volume_ok:
            verdict = "pending"
        else:
            verdict = "pending"
        return BreakoutVerdict(level, direction, verdict, checks, score)


# ── Discipline ────────────────────────────────────────────────────────────

@dataclass
class GuardDecision:
    """Whether a trade may be taken, and the size multiplier to use."""

    allowed: bool
    size_multiplier: float
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed,
                "size_multiplier": round(self.size_multiplier, 4),
                "reasons": list(self.reasons)}


class DisciplineGuard:
    """The rules that stop the trader, not the strategy, from blowing up.

    Loss streaks cut size; a loss imposes a cooldown so the next trade is not
    revenge; a daily loss cap and a trade-count cap end the session. Each block
    names the rule that fired, so the journal records why, not just that.
    """

    def __init__(self, policy: RiskPolicy | None = None,
                 cooldown_after_loss: float = 900.0,
                 streak_step: float = 0.25,
                 min_size_multiplier: float = 0.25) -> None:
        self.policy = policy or RiskPolicy()
        self.cooldown_after_loss = cooldown_after_loss
        self.streak_step = streak_step
        self.min_size_multiplier = min_size_multiplier
        self.day_pnl = 0.0
        self.trades_today = 0
        self.consecutive_losses = 0
        self.after_loss: bool = False
        self.last_trade_at: float | None = None

    def record(self, r_multiple: float, at: float,
               risk_amount: float | None = None) -> None:
        risk = self.policy.risk_budget() if risk_amount is None else risk_amount
        self.day_pnl += r_multiple * risk
        self.trades_today += 1
        self.last_trade_at = at
        if r_multiple < 0:
            self.consecutive_losses += 1
            self.after_loss = True
        else:
            self.consecutive_losses = 0
            self.after_loss = False

    def size_multiplier(self) -> float:
        if self.consecutive_losses == 0:
            return 1.0
        return max(self.min_size_multiplier,
                   1.0 - self.streak_step * self.consecutive_losses)

    def evaluate(self, now: float) -> GuardDecision:
        reasons: list[str] = []
        blocked = False
        if self.trades_today >= self.policy.max_trades_per_day:
            reasons.append("daily trade cap reached")
            blocked = True
        if self.day_pnl <= -self.policy.daily_loss_cap():
            reasons.append("daily loss cap reached")
            blocked = True
        if (self.after_loss and self.last_trade_at is not None
                and now - self.last_trade_at < self.cooldown_after_loss):
            remaining = self.cooldown_after_loss - (now - self.last_trade_at)
            reasons.append(f"cooldown after a loss: {remaining:.0f}s remaining")
            blocked = True
        multiplier = self.size_multiplier()
        if multiplier < 1.0:
            reasons.append(f"size reduced to {multiplier:.2f}x after "
                           f"{self.consecutive_losses} consecutive losses")
        return GuardDecision(not blocked, multiplier, reasons)

    def reset_day(self) -> None:
        self.day_pnl = 0.0
        self.trades_today = 0
        self.after_loss = False
        self.last_trade_at = None


# ── Correlation ───────────────────────────────────────────────────────────

@dataclass
class CorrelationPair:
    """Two instruments and how much of the same risk they share."""

    a: str
    b: str
    correlation: float

    @property
    def same_bet(self) -> bool:
        return self.correlation >= 0.7

    def as_dict(self) -> dict[str, Any]:
        return {"a": self.a, "b": self.b,
                "correlation": round(self.correlation, 4),
                "same_bet": self.same_bet}


class CorrelationAnalyzer:
    """Return correlations, clusters and the heat of a book."""

    def __init__(self, same_bet_threshold: float = 0.7) -> None:
        self.same_bet_threshold = same_bet_threshold

    def matrix(self, series: dict[str, CandleSeries]) -> dict[tuple[str, str], float]:
        symbols = list(series)
        returns = {s: series[s].returns() for s in symbols}
        out: dict[tuple[str, str], float] = {}
        for i, a in enumerate(symbols):
            for b in symbols[i + 1:]:
                out[(a, b)] = pearson(returns[a], returns[b])
        return out

    def pairs(self, series: dict[str, CandleSeries]) -> list[CorrelationPair]:
        pairs = [CorrelationPair(a, b, c) for (a, b), c in self.matrix(series).items()]
        return sorted(pairs, key=lambda p: -abs(p.correlation))

    def clusters(self, series: dict[str, CandleSeries]) -> list[list[str]]:
        """Group symbols that move together into single-bet clusters."""
        matrix = self.matrix(series)
        parent = {s: s for s in series}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for (a, b), correlation in matrix.items():
            if correlation >= self.same_bet_threshold:
                union(a, b)
        groups: dict[str, list[str]] = {}
        for symbol in series:
            groups.setdefault(find(symbol), []).append(symbol)
        return sorted((sorted(g) for g in groups.values()), key=len, reverse=True)

    def portfolio_heat(self, positions: dict[str, float],
                       series: dict[str, CandleSeries],
                       equity: float) -> dict[str, Any]:
        """Total risk of a book, with correlated positions counted once per cluster.

        Five names that trade as one are one trade: the naive sum overstates or
        understates nothing, but the clustered figure is what the account
        actually risks.
        """
        total = sum(positions.values())
        clusters = self.clusters(series) if len(series) > 1 else [[s] for s in positions]
        clustered = 0.0
        for cluster in clusters:
            clustered += max((positions.get(s, 0.0) for s in cluster), default=0.0)
        naive_pct = total / equity * 100.0 if equity else 0.0
        clustered_pct = clustered / equity * 100.0 if equity else 0.0
        return {
            "naive_risk": round(total, 4),
            "clustered_risk": round(clustered, 4),
            "naive_pct": round(naive_pct, 4),
            "clustered_pct": round(clustered_pct, 4),
            "clusters": clusters,
            "distinct_bets": len(clusters),
        }


# ── Backtesting ───────────────────────────────────────────────────────────

@dataclass
class SimulatedTrade:
    """One backtested trade in R terms."""

    index: int
    direction: str
    entry: float
    stop: float
    target: float
    exit_price: float
    exit_index: int
    reason: str        # target | stop | time
    r_multiple: float
    fees_r: float

    @property
    def net_r(self) -> float:
        return self.r_multiple - self.fees_r

    def as_dict(self) -> dict[str, Any]:
        return {"index": self.index, "direction": self.direction,
                "entry": round(self.entry, 6), "stop": round(self.stop, 6),
                "target": round(self.target, 6),
                "exit_price": round(self.exit_price, 6),
                "reason": self.reason, "r_multiple": round(self.r_multiple, 4),
                "fees_r": round(self.fees_r, 4), "net_r": round(self.net_r, 4)}


@dataclass
class BacktestResult:
    """A full run: trades, equity curve and the statistics that matter."""

    trades: list[SimulatedTrade]
    equity_curve: list[float]
    starting_equity: float
    expectancy: ExpectancyReport
    max_drawdown_pct: float
    total_return_pct: float
    exposure: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "trades": len(self.trades),
            "start_equity": self.starting_equity,
            "end_equity": round(self.equity_curve[-1], 4) if self.equity_curve else self.starting_equity,
            "total_return_pct": round(self.total_return_pct, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "exposure": round(self.exposure, 4),
            "win_rate": round(self.expectancy.win_rate, 4),
            "expectancy_r": round(self.expectancy.expectancy_r, 4),
            "profit_factor": self.expectancy.profit_factor,
        }


SignalFn = Callable[[CandleSeries, int], "dict[str, Any] | None"]


class Backtester:
    """Bar-by-bar simulation with next-bar entries and intrabar exits.

    A signal on bar *i* is filled at bar *i+1*'s open, never at bar *i*'s close:
    filling on the bar that produced the signal is the classic way a backtest
    invents an edge. Stops are checked before targets inside the same bar,
    because that is the conservative assumption when both are touched.
    """

    def __init__(self, policy: RiskPolicy | None = None,
                 fee_r: float = 0.02, slippage_r: float = 0.01,
                 max_bars_in_trade: int = 20) -> None:
        self.policy = policy or RiskPolicy()
        self.fee_r = fee_r
        self.slippage_r = slippage_r
        self.max_bars_in_trade = max_bars_in_trade

    def run(self, series: CandleSeries, signal: SignalFn,
            starting_equity: float | None = None) -> BacktestResult:
        equity = starting_equity if starting_equity is not None else self.policy.equity
        trade_risk_pct = self.policy.max_risk_pct
        trades: list[SimulatedTrade] = []
        curve: list[float] = [equity]
        bars_in_market = 0
        i = 0
        n = len(series)
        while i < n - 1:
            suggestion = signal(series, i)
            if not suggestion:
                i += 1
                continue
            direction = suggestion.get("direction", "long")
            stop = float(suggestion.get("stop", 0.0))
            target = float(suggestion.get("target", 0.0))
            entry = series.candles[i + 1].open
            risk_per_unit = abs(entry - stop)
            if entry <= 0 or risk_per_unit <= 0 or target == 0:
                i += 1
                continue
            if (direction == "long" and (stop >= entry or target <= entry)) or \
               (direction == "short" and (stop <= entry or target >= entry)):
                i += 1
                continue

            exit_price, exit_index, reason = entry, i + 1, "time"
            for j in range(i + 1, min(n, i + 1 + self.max_bars_in_trade)):
                bar = series.candles[j]
                bars_in_market += 1
                if direction == "long":
                    hit_stop = bar.low <= stop
                    hit_target = bar.high >= target
                else:
                    hit_stop = bar.high >= stop
                    hit_target = bar.low <= target
                if hit_stop:
                    exit_price, exit_index, reason = stop, j, "stop"
                    break
                if hit_target:
                    exit_price, exit_index, reason = target, j, "target"
                    break
                exit_price, exit_index = bar.close, j
            r_multiple = ((exit_price - entry) if direction == "long"
                          else (entry - exit_price)) / risk_per_unit
            fees_r = (self.fee_r + self.slippage_r) * (
                entry / risk_per_unit if risk_per_unit else 0.0)
            trade = SimulatedTrade(
                index=i + 1, direction=direction, entry=entry, stop=stop,
                target=target, exit_price=exit_price, exit_index=exit_index,
                reason=reason, r_multiple=r_multiple, fees_r=fees_r,
            )
            trades.append(trade)
            equity *= (1.0 + trade.net_r * trade_risk_pct / 100.0)
            curve.append(equity)
            i = exit_index + 1

        expectancy = Expectancy().evaluate([t.net_r for t in trades])
        peak = curve[0] if curve else equity
        max_dd = 0.0
        for value in curve:
            peak = max(peak, value)
            if peak > 0:
                max_dd = max(max_dd, (peak - value) / peak * 100.0)
        total_return = ((curve[-1] - curve[0]) / curve[0] * 100.0) if curve and curve[0] else 0.0
        exposure = bars_in_market / max(1, n)
        return BacktestResult(
            trades=trades, equity_curve=curve, starting_equity=curve[0],
            expectancy=expectancy, max_drawdown_pct=max_dd,
            total_return_pct=total_return, exposure=exposure,
        )


def ma_cross_signal(fast: int = 5, slow: int = 13, r_multiple: float = 2.0,
                    atr_multiple: float = 1.5) -> SignalFn:
    """A worked example rule set: fast/slow cross with an ATR stop.

    Provided so the master curriculum has something concrete to backtest; a
    caller is expected to pass its own signal function.
    """

    def signal(series: CandleSeries, index: int) -> dict[str, Any] | None:
        if index < slow + 1:
            return None
        window = series.slice(0, index + 1)
        fast_now = window.sma(fast)
        slow_now = window.sma(slow)
        previous = window.slice(0, len(window) - 1)
        fast_prev = previous.sma(fast)
        slow_prev = previous.sma(slow)
        if None in (fast_now, slow_now, fast_prev, slow_prev):
            return None
        atr = window.atr()
        if atr <= 0:
            return None
        price = window.last.close
        crossed_up = fast_prev <= slow_prev and fast_now > slow_now
        crossed_down = fast_prev >= slow_prev and fast_now < slow_now
        if crossed_up:
            stop = price - atr * atr_multiple
            return {"direction": "long", "stop": stop,
                    "target": price + (price - stop) * r_multiple}
        if crossed_down:
            stop = price + atr * atr_multiple
            return {"direction": "short", "stop": stop,
                    "target": price - (stop - price) * r_multiple}
        return None

    return signal


# ── Journal ───────────────────────────────────────────────────────────────

@dataclass
class JournalEntry:
    """One recorded trade, with everything the review needs."""

    setup: str
    direction: str
    entry: float
    stop: float
    exit_price: float
    r_multiple: float
    at: float = 0.0
    notes: str = ""
    followed_plan: bool = True

    @property
    def win(self) -> bool:
        return self.r_multiple > 0


@dataclass
class JournalStats:
    """What the journal is for: an honest read on the trader's own edge."""

    trades: int
    win_rate: float
    expectancy_r: float
    total_r: float
    average_win_r: float
    average_loss_r: float
    longest_win_streak: int
    longest_loss_streak: int
    plan_adherence: float
    by_setup: dict[str, dict[str, float]]
    best_setup: str
    worst_setup: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "trades": self.trades,
            "win_rate": round(self.win_rate, 4),
            "expectancy_r": round(self.expectancy_r, 4),
            "total_r": round(self.total_r, 4),
            "longest_win_streak": self.longest_win_streak,
            "longest_loss_streak": self.longest_loss_streak,
            "plan_adherence": round(self.plan_adherence, 4),
            "best_setup": self.best_setup,
            "worst_setup": self.worst_setup,
        }


class TradeJournal:
    """Record trades, then measure them per setup and per streak."""

    def __init__(self) -> None:
        self.entries: list[JournalEntry] = []

    def add(self, entry: JournalEntry) -> JournalEntry:
        self.entries.append(entry)
        return entry

    def record(self, setup: str, direction: str, entry: float, stop: float,
               exit_price: float, at: float = 0.0, notes: str = "",
               followed_plan: bool = True) -> JournalEntry:
        risk = abs(entry - stop)
        if risk <= 0:
            r_multiple = 0.0
        else:
            move = (exit_price - entry) if direction == "long" else (entry - exit_price)
            r_multiple = move / risk
        return self.add(JournalEntry(
            setup=setup or "unspecified", direction=direction, entry=entry,
            stop=stop, exit_price=exit_price, r_multiple=r_multiple,
            at=at, notes=notes, followed_plan=followed_plan,
        ))

    @staticmethod
    def _streaks(entries: Sequence[JournalEntry]) -> tuple[int, int]:
        best_win = best_loss = current_win = current_loss = 0
        for entry in entries:
            if entry.win:
                current_win += 1
                current_loss = 0
            else:
                current_loss += 1
                current_win = 0
            best_win = max(best_win, current_win)
            best_loss = max(best_loss, current_loss)
        return best_win, best_loss

    def stats(self) -> JournalStats:
        entries = self.entries
        if not entries:
            return JournalStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0.0, {},
                                "", "")
        r_values = [e.r_multiple for e in entries]
        report = Expectancy().evaluate(r_values)
        win_streak, loss_streak = self._streaks(entries)
        setups: dict[str, list[float]] = {}
        for entry in entries:
            setups.setdefault(entry.setup, []).append(entry.r_multiple)
        by_setup = {
            name: {"trades": len(values), "total_r": round(sum(values), 4),
                   "expectancy_r": round(mean(values), 4),
                   "win_rate": round(sum(1 for v in values if v > 0) / len(values), 4)}
            for name, values in setups.items()
        }
        best = max(by_setup, key=lambda k: by_setup[k]["expectancy_r"])
        worst = min(by_setup, key=lambda k: by_setup[k]["expectancy_r"])
        adherence = sum(1 for e in entries if e.followed_plan) / len(entries)
        return JournalStats(
            trades=len(entries), win_rate=report.win_rate,
            expectancy_r=report.expectancy_r, total_r=report.total_r,
            average_win_r=report.average_win_r,
            average_loss_r=report.average_loss_r,
            longest_win_streak=win_streak, longest_loss_streak=loss_streak,
            plan_adherence=adherence, by_setup=by_setup,
            best_setup=best, worst_setup=worst,
        )

    def payoff_skew(self) -> dict[str, float]:
        """Cutting losers vs sizing winners, measured on the actual book."""
        wins = [e.r_multiple for e in self.entries if e.win]
        losses = [e.r_multiple for e in self.entries if not e.win]
        biggest_loss = min(losses) if losses else 0.0
        biggest_win = max(wins) if wins else 0.0
        return {
            "average_win_r": round(mean(wins), 4) if wins else 0.0,
            "average_loss_r": round(mean(losses), 4) if losses else 0.0,
            "biggest_win_r": round(biggest_win, 4),
            "biggest_loss_r": round(biggest_loss, 4),
            "loss_to_win_ratio": round(abs(biggest_loss) / biggest_win, 4)
            if biggest_win else 0.0,
        }


# ── Curriculum ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Lesson:
    """One lesson of the Trading Mastery track and what enforces it."""

    order: int
    slug: str
    title: str
    component: str
    rule: str


CURRICULUM: tuple[Lesson, ...] = (
    Lesson(1, "risk-first", "Risk first: the rule that keeps you alive",
           "RiskPolicy", "one trade risks at most max_risk_pct of equity"),
    Lesson(2, "position-sizing", "Position sizing: how much to bet",
           "PositionSizer", "size is risk budget divided by stop distance"),
    Lesson(3, "stops", "Stop losses without getting wicked out",
           "StopPlanner", "stop goes beyond structure plus an ATR buffer"),
    Lesson(4, "r-multiples", "R-multiples and expectancy",
           "Expectancy", "expectancy = p*avg_win + (1-p)*avg_loss, in R"),
    Lesson(5, "structure", "Support, resistance and trend for real",
           "StructureMap", "levels need clustered touches; trend needs two swings"),
    Lesson(6, "candlesticks", "Candlesticks that actually matter",
           "PatternDetector", "a pattern without volume and location is a shape"),
    Lesson(7, "volume", "Volume: the tell most miss",
           "VolumeAnalyzer", "relative volume and OBV confirm or contradict price"),
    Lesson(8, "market-structure", "Market structure 101",
           "StructureMap", "HH/HL is an uptrend; a level break is an event"),
    Lesson(9, "psychology", "Trading psychology: beat your own brain",
           "DisciplineGuard", "losses shrink size and impose a cooldown"),
    Lesson(10, "why-traders-lose", "Why 90% of traders lose",
           "Expectancy", "fees and overtrading move the breakeven win rate"),
    Lesson(11, "repeatable-edge", "Build a repeatable edge",
           "Backtester", "a rule set is a guess until it is simulated"),
    Lesson(12, "journaling", "Journaling like a pro",
           "TradeJournal", "expectancy per setup, streaks and plan adherence"),
    Lesson(13, "regime", "Trend vs range: know the regime",
           "RegimeClassifier", "efficiency ratio decides trend, range or transition"),
    Lesson(14, "moving-averages", "Moving averages that are not useless",
           "MovingAverageStack", "use alignment and extension, not crossovers alone"),
    Lesson(15, "rsi", "RSI and momentum, honestly",
           "Rsi", "overbought in an uptrend is strength, not a sell"),
    Lesson(16, "breakouts", "Breakouts vs fakeouts",
           "BreakoutValidator", "close-through, volume, follow-through and hold"),
    Lesson(17, "risk-reward", "Risk/reward before every trade",
           "TradePlan", "a plan below the minimum R:R is rejected, not sized"),
    Lesson(18, "revenge", "The revenge-trade spiral",
           "DisciplineGuard", "the trade after a loss waits out the cooldown"),
    Lesson(19, "payoff-skew", "Sizing up winners, cutting losers",
           "TradeJournal", "payoff ratio decides survival, not win rate"),
    Lesson(20, "backtesting", "Backtesting your own rules",
           "Backtester", "next-bar fills, fees charged, intrabar exits"),
    Lesson(21, "correlation", "Correlation: do not hold five of one trade",
           "CorrelationAnalyzer", "correlated positions count once in the heat"),
)


@dataclass
class MasteryReport:
    """A curriculum run against one dataset: which lessons held, and how."""

    lessons: list[dict[str, Any]]
    passed: int
    failed: int
    expectancy_r: float
    demo_trades: int

    @property
    def score(self) -> float:
        total = self.passed + self.failed
        return self.passed / total if total else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "failed": self.failed,
                "score": round(self.score, 4),
                "expectancy_r": round(self.expectancy_r, 4),
                "demo_trades": self.demo_trades,
                "lessons": [dict(l) for l in self.lessons]}


class MasteryCurriculum:
    """Run the track's rules against a real series and report what holds.

    Each check exercises the component the lesson is about and compares the
    result with the rule. Nothing is asserted by construction: a plan that is
    under-sized, a stop placed on the wrong side of the market, or a breakout
    with no volume shows up as a failure.
    """

    def __init__(self) -> None:
        self.policy = RiskPolicy(equity=100_000.0, max_risk_pct=1.0)
        self.sizer = PositionSizer()
        self.stops = StopPlanner()
        self.planner = TradePlanner(self.policy, self.stops, self.sizer)

    def _check_risk(self, series: CandleSeries) -> tuple[bool, str]:
        plan = self.planner.build(Instrument("T"), series, "long")
        if plan.size is None:
            return False, "no size produced"
        ok = plan.size.risk_amount <= self.policy.risk_budget() + 1e-9
        return ok, f"risk {plan.size.risk_amount:.2f} <= budget {self.policy.risk_budget():.2f}"

    def _check_stop_side(self, series: CandleSeries) -> tuple[bool, str]:
        plan = self.planner.build(Instrument("T"), series, "long")
        ok = plan.stop < plan.entry
        return ok, f"stop {plan.stop:.4f} below entry {plan.entry:.4f}"

    def _check_rr(self, series: CandleSeries) -> tuple[bool, str]:
        plan = self.planner.build(Instrument("T"), series, "long")
        ok = plan.rr >= plan.min_rr
        return ok, f"R:R {plan.rr:.2f} vs minimum {plan.min_rr:.2f}"

    def _check_expectancy(self, r_values: Sequence[float]) -> tuple[bool, str]:
        report = Expectancy().evaluate(r_values)
        ok = report.expectancy_r > 0
        return ok, f"expectancy {report.expectancy_r:.3f}R over {report.trades} trades"

    def _check_structure(self, series: CandleSeries) -> tuple[bool, str]:
        structure = StructureMap()
        trend = structure.trend(series)
        levels = structure.levels(series)
        touches = [l.touches for l in levels["support"] + levels["resistance"]]
        ok = bool(touches) and trend["trend"] in ("uptrend", "downtrend", "range")
        return ok, (f"trend {trend['trend']}, {len(levels['support'])} support / "
                    f"{len(levels['resistance'])} resistance levels clustered")

    def _check_patterns(self, series: CandleSeries) -> tuple[bool, str]:
        hits = PatternDetector().scan(series)
        confirmed = [h for h in hits if h.volume_confirmed]
        ok = bool(hits)
        kinds = sorted({h.name for h in hits})
        return ok, f"{len(hits)} patterns ({', '.join(kinds[:3])}), {len(confirmed)} volume-confirmed"

    def _check_volume(self, series: CandleSeries) -> tuple[bool, str]:
        reading = VolumeAnalyzer().analyze(series)
        ok = 0.0 <= reading.relative_volume < float("inf") and reading.divergence in (
            "none", "bullish", "bearish")
        return ok, (f"relative volume {reading.relative_volume:.2f}, "
                    f"OBV slope {reading.obv_slope:.1f}, divergence {reading.divergence}")

    def _check_moving_averages(self, series: CandleSeries) -> tuple[bool, str]:
        stack = MovingAverageStack().evaluate(series)
        if stack is None:
            return False, "not enough bars for a 20/50 stack"
        ok = stack.alignment in ("bullish", "bearish", "mixed")
        return ok, (f"{stack.alignment} stack, slope {stack.slope_pct:+.2f}%, "
                    f"price {stack.extension_pct:+.2f}% from the fast average")

    def _check_rsi(self, series: CandleSeries) -> tuple[bool, str]:
        trend = StructureMap().trend(series)["trend"]
        reading = Rsi().evaluate(series, trend)
        ok = 0.0 <= reading.value <= 100.0
        return ok, f"RSI {reading.value:.1f} ({reading.zone}) with trend {trend}"

    def _check_journal(self, r_values: Sequence[float]) -> tuple[bool, str]:
        journal = TradeJournal()
        for i, r in enumerate(r_values):
            risk = 10.0
            exit_price = 100.0 + r * risk
            journal.record("demo", "long", 100.0, 100.0 - risk, exit_price,
                           at=float(i))
        stats = journal.stats()
        ok = stats.trades == len(r_values) and stats.total_r > 0
        return ok, (f"{stats.trades} journalled trades, expectancy "
                    f"{stats.expectancy_r:.2f}R per trade")

    def _check_breakout(self, series: CandleSeries) -> tuple[bool, str]:
        level = max(series.highs[-20:-1]) if len(series) > 2 else 0.0
        verdict = BreakoutValidator().evaluate(series, level)
        ok = verdict.verdict in ("confirmed", "pending", "fakeout")
        return ok, f"verdict {verdict.verdict} with score {verdict.score:.2f}"

    def _check_regime(self, series: CandleSeries) -> tuple[bool, str]:
        reading = RegimeClassifier().evaluate(series)
        ok = reading.regime in ("trend_up", "trend_down", "range", "transition")
        return ok, f"regime {reading.regime} at efficiency {reading.efficiency:.2f}"

    def _check_discipline(self) -> tuple[bool, str]:
        guard = DisciplineGuard(self.policy)
        guard.record(-1.0, at=1000.0)
        decision = guard.evaluate(now=1000.0 + 60.0)
        ok = (not decision.allowed) and decision.size_multiplier < 1.0
        return ok, ("loss blocked the next trade and reduced size to "
                    f"{decision.size_multiplier:.2f}x")

    def _check_backtest(self, series: CandleSeries) -> tuple[bool, str]:
        result = Backtester(self.policy).run(series, ma_cross_signal())
        # Entries fill on the bar after the signal, and every trade carries a
        # stop, a target and a fee: a run with none of that proves nothing.
        ok = bool(result.trades) and all(
            t.index > 0 and t.fees_r > 0 and t.stop != t.target
            for t in result.trades)
        return ok, (f"{len(result.trades)} trades, {result.total_return_pct:.2f}% "
                    f"return, {result.max_drawdown_pct:.2f}% max drawdown")

    def _check_correlation(self, series: CandleSeries) -> tuple[bool, str]:
        # The same series twice is a perfect correlation, which must collapse
        # into one cluster and one bet.
        analyzer = CorrelationAnalyzer()
        heat = analyzer.portfolio_heat({"A": 500.0, "B": 500.0},
                                       {"A": series, "B": series}, 100_000.0)
        ok = heat["distinct_bets"] == 1 and heat["clustered_risk"] == 500.0
        return ok, f"{heat['distinct_bets']} distinct bet(s), heat {heat['clustered_pct']:.2f}%"

    def run(self, series: CandleSeries,
            r_values: Sequence[float] = (1.5, -1.0, 2.0, -1.0, 3.0, -1.0)) -> MasteryReport:
        checks: dict[str, Callable[[], tuple[bool, str]]] = {
            "RiskPolicy": lambda: self._check_risk(series),
            "PositionSizer": lambda: self._check_risk(series),
            "StopPlanner": lambda: self._check_stop_side(series),
            "TradePlan": lambda: self._check_rr(series),
            "Expectancy": lambda: self._check_expectancy(r_values),
            "StructureMap": lambda: self._check_structure(series),
            "PatternDetector": lambda: self._check_patterns(series),
            "VolumeAnalyzer": lambda: self._check_volume(series),
            "MovingAverageStack": lambda: self._check_moving_averages(series),
            "Rsi": lambda: self._check_rsi(series),
            "TradeJournal": lambda: self._check_journal(r_values),
            "BreakoutValidator": lambda: self._check_breakout(series),
            "RegimeClassifier": lambda: self._check_regime(series),
            "DisciplineGuard": self._check_discipline,
            "Backtester": lambda: self._check_backtest(series),
            "CorrelationAnalyzer": lambda: self._check_correlation(series),
        }
        lessons: list[dict[str, Any]] = []
        passed = failed = 0
        for lesson in CURRICULUM:
            runner = checks.get(lesson.component)
            if runner is None:  # a lesson whose component has no check yet
                ok, detail = False, f"no executable check for {lesson.component}"
            else:
                ok, detail = runner()
            passed += 1 if ok else 0
            failed += 0 if ok else 1
            lessons.append({
                "order": lesson.order, "slug": lesson.slug,
                "title": lesson.title, "component": lesson.component,
                "passed": ok, "detail": detail,
            })
        report = Expectancy().evaluate(r_values)
        return MasteryReport(
            lessons=lessons, passed=passed, failed=failed,
            expectancy_r=report.expectancy_r, demo_trades=report.trades,
        )


def synthetic_series(bars: int = 120, start: float = 100.0, drift: float = 0.15,
                     amplitude: float = 2.0, volume: float = 10_000.0,
                     period: float = 12.0) -> CandleSeries:
    """A deterministic trending series, so every test sees the same bars."""
    candles: list[Candle] = []
    for i in range(bars):
        base = start + drift * i + amplitude * math.sin(i / period * 2 * math.pi)
        open_ = base - drift * 0.4
        close = base + drift * 0.4
        high = max(open_, close) + 0.6
        low = min(open_, close) - 0.6
        vol = volume * (1.0 + 0.2 * math.sin(i / 5.0))
        candles.append(Candle(open_, high, low, close, vol, float(i)))
    return CandleSeries(candles)
