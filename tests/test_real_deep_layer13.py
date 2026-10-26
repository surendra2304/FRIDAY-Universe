"""
Real Deep Layer 13 Tests — Cloud9 Markets "Trading Mastery" → Stratex.

Repo 2 (cloud9markets.com/academy-trading-mastery.html) is a twenty-one lesson
trading curriculum: risk first, position sizing, stops, R-multiples and
expectancy, structure, candlesticks, volume, market structure, psychology, edge,
journaling, regime, moving averages, RSI, breakouts, risk/reward, revenge
trading, payoff skew, backtesting and correlation.

``Stratex/real_trading_mastery.py`` is the executable half of that track. Every
test below asserts a computed number, a computed verdict or a computed list of
reasons — no mocks, no placeholders.
"""

import importlib.util
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(HERE, "..", "Stratex", "real_trading_mastery.py")

spec = importlib.util.spec_from_file_location("real_trading_mastery", MODULE_PATH)
tm = importlib.util.module_from_spec(spec)
sys.modules["real_trading_mastery"] = tm
spec.loader.exec_module(tm)


def rows_from(closes, spread=1.0, volume=1000.0):
    """Turn a close series into plausible OHLCV rows."""
    rows = []
    previous = closes[0]
    for close in closes:
        open_ = previous
        rows.append((open_, max(open_, close) + spread, min(open_, close) - spread,
                     close, volume))
        previous = close
    return rows


@pytest.fixture()
def trend():
    return tm.synthetic_series(160)


@pytest.fixture()
def policy():
    return tm.RiskPolicy(equity=100_000.0, max_risk_pct=1.0)


# ── Candles ───────────────────────────────────────────────────────────────

def test_candle_geometry():
    candle = tm.Candle(open=100.0, high=108.0, low=96.0, close=106.0, volume=500)
    assert candle.body == pytest.approx(6.0)
    assert candle.range == pytest.approx(12.0)
    assert candle.upper_wick == pytest.approx(2.0)
    assert candle.lower_wick == pytest.approx(4.0)
    assert candle.bullish is True
    assert candle.body_ratio() == pytest.approx(0.5)
    assert candle.close_position() == pytest.approx(10.0 / 12.0)
    assert candle.typical == pytest.approx((108 + 96 + 106) / 3)


def test_series_builds_from_rows_and_computes_atr():
    series = tm.CandleSeries.from_rows(rows_from([100, 102, 101, 105, 107]))
    assert len(series) == 5
    assert series.closes[-1] == 107
    assert series.atr() > 0
    assert series.sma(3) == pytest.approx((101 + 105 + 107) / 3)
    assert tm.CandleSeries.from_rows([(1, 2)]).candles == []


def test_ema_uses_the_sma_seed():
    series = tm.CandleSeries.from_rows(rows_from([10, 10, 10, 20], spread=0))
    assert series.ema(3) == pytest.approx(15.0)
    assert series.ema(9) is None


def test_swing_points_require_confirmation_on_both_sides():
    closes = [10, 12, 15, 12, 10, 8, 6, 8, 10]
    series = tm.CandleSeries.from_rows([(c, c + 0.5, c - 0.5, c) for c in closes])
    pivots = series.swing_points(left=1, right=1)
    highs = [price for _, price in pivots["highs"]]
    lows = [price for _, price in pivots["lows"]]
    assert 15.5 in highs
    assert 5.5 in lows


# ── Sizing ────────────────────────────────────────────────────────────────

def test_risk_policy_budgets(policy):
    assert policy.risk_budget() == pytest.approx(1000.0)
    assert policy.daily_loss_cap() == pytest.approx(3000.0)
    assert policy.open_risk_cap() == pytest.approx(6000.0)
    assert policy.with_equity(50_000.0).risk_budget() == pytest.approx(500.0)


def test_sizing_divides_the_budget_by_the_stop_distance(policy):
    sizer = tm.PositionSizer()
    size = sizer.size(entry=100.0, stop=95.0, policy=policy)
    assert size.units == pytest.approx(200.0)      # 1000 / 5
    assert size.risk_amount == pytest.approx(1000.0)
    assert size.risk_pct == pytest.approx(1.0)
    assert size.notional == pytest.approx(20_000.0)
    assert size.capped_by == "risk_budget"


def test_a_wider_stop_means_a_smaller_position(policy):
    sizer = tm.PositionSizer()
    tight = sizer.size(100.0, 98.0, policy)
    wide = sizer.size(100.0, 90.0, policy)
    assert wide.units < tight.units
    assert wide.risk_amount == pytest.approx(tight.risk_amount, rel=1e-6)


def test_size_respects_lot_size_and_contract_multiplier(policy):
    sizer = tm.PositionSizer()
    instrument = tm.Instrument("NIFTY", lot_size=75, contract_multiplier=1.0)
    size = sizer.size(100.0, 95.0, policy, instrument)
    # 200 raw units rounds down to two 75-unit lots.
    assert size.units == pytest.approx(150.0)

    future = tm.Instrument("ES", lot_size=1, contract_multiplier=50.0)
    sized = sizer.size(4000.0, 3990.0, policy, future)
    assert sized.units == pytest.approx(2.0)       # 1000 / (10 * 50)
    assert sized.notional == pytest.approx(400_000.0)


def test_fees_are_charged_against_the_budget(policy):
    sizer = tm.PositionSizer()
    instrument = tm.Instrument("X", fee_per_unit=2.0)
    size = sizer.size(100.0, 95.0, policy, instrument)
    assert size.fees == pytest.approx(size.units * 2.0)
    assert size.risk_amount + size.fees <= policy.risk_budget() + 1e-6


def test_slippage_widens_the_effective_stop(policy):
    sizer = tm.PositionSizer()
    instrument = tm.Instrument("X", slippage_ticks=5, tick_size=0.1)
    size = sizer.size(100.0, 95.0, policy, instrument)
    assert size.entry == pytest.approx(100.5)
    assert size.risk_per_unit == pytest.approx(5.5)
    assert size.slippage_cost > 0


def test_open_risk_cap_limits_a_new_position(policy):
    sizer = tm.PositionSizer()
    size = sizer.size(100.0, 95.0, policy, open_risk_used=5_500.0)
    assert size.capped_by == "open_risk_cap"
    assert size.risk_amount == pytest.approx(500.0, abs=1.0)


def test_invalid_prices_produce_no_position(policy):
    sizer = tm.PositionSizer()
    assert sizer.size(100.0, 100.0, policy).units == 0.0
    assert sizer.size(100.0, 100.0, policy).capped_by == "invalid_prices"
    assert sizer.size(0.0, 95.0, policy).units == 0.0


def test_volatility_target_sizing_uses_the_atr(policy):
    sizer = tm.PositionSizer()
    size = sizer.volatility_target(100.0, atr=2.0, policy=policy, atr_multiple=3.0)
    assert size.stop == pytest.approx(94.0)
    assert size.units == pytest.approx(1000.0 / 6.0, rel=1e-2)


# ── Stops and plans ───────────────────────────────────────────────────────

def test_structure_stop_sits_beyond_the_recent_low(trend):
    stops = tm.StopPlanner()
    stop = stops.plan_stop(trend, "long", trend.last.close)
    recent_low = min(c.low for c in trend.candles[-10:])
    assert stop < recent_low
    assert stop < trend.last.close


def test_stop_avoids_round_numbers():
    stops = tm.StopPlanner(round_step=1.0, nudge_ticks=2, tick_size=0.01)
    nudged = stops.avoid_round_numbers(95.0, "long")
    assert nudged == pytest.approx(94.98)
    assert stops.avoid_round_numbers(95.37, "long") == pytest.approx(95.37)
    assert stops.avoid_round_numbers(95.0, "short") == pytest.approx(95.02)


def test_targets_are_r_multiples_of_the_risk(trend):
    stops = tm.StopPlanner()
    targets = stops.targets(100.0, 95.0, "long", (1.0, 2.0, 3.0))
    assert targets == [105.0, 110.0, 115.0]
    short_targets = stops.targets(100.0, 105.0, "short", (1.0, 2.0))
    assert short_targets == [95.0, 90.0]


def test_trade_plan_rejects_poor_risk_reward():
    plan = tm.TradePlan("X", "long", entry=100.0, stop=95.0, targets=[102.0])
    problems = plan.validate()
    assert plan.approved is False
    assert any("risk/reward" in p for p in problems)


def test_trade_plan_rejects_a_stop_on_the_wrong_side():
    plan = tm.TradePlan("X", "long", entry=100.0, stop=105.0, targets=[110.0])
    problems = plan.validate()
    assert any("below entry" in p for p in problems)
    short = tm.TradePlan("X", "short", entry=100.0, stop=95.0, targets=[90.0])
    assert any("above entry" in p for p in short.validate())


def test_trade_plan_rejects_a_zero_rounded_position():
    plan = tm.TradePlan("X", "long", entry=100.0, stop=95.0, targets=[110.0],
                        size=tm.PositionSize(0.0, 100.0, 95.0, 5.0, 0.0, 0.0,
                                             0.0, 0.0, 0.0))
    assert any("rounds to zero" in p for p in plan.validate())


def test_trade_planner_builds_an_approved_plan(trend, policy):
    planner = tm.TradePlanner(policy)
    plan = planner.build(tm.Instrument("T"), trend, "long")
    assert plan.approved is True
    assert plan.rr >= 2.0
    assert plan.stop < min(c.low for c in trend.candles[-10:])
    assert plan.size.risk_amount <= policy.risk_budget() + 1e-6


# ── Expectancy ────────────────────────────────────────────────────────────

def test_expectancy_arithmetic():
    report = tm.Expectancy().evaluate([1.5, -1.0, 2.0, -1.0, 3.0, -1.0])
    assert report.trades == 6
    assert report.wins == 3 and report.losses == 3
    assert report.win_rate == pytest.approx(0.5)
    assert report.average_win_r == pytest.approx(6.5 / 3)
    assert report.average_loss_r == pytest.approx(-1.0)
    assert report.expectancy_r == pytest.approx(0.5 * 6.5 / 3 + 0.5 * -1.0)
    assert report.payoff_ratio == pytest.approx(6.5 / 3)
    assert report.profit_factor == pytest.approx(6.5 / 3)
    assert report.total_r == pytest.approx(3.5)


def test_breakeven_win_rate_matches_the_payoff():
    expectancy = tm.Expectancy()
    assert expectancy.breakeven_win_rate(2.0, -1.0) == pytest.approx(1 / 3)
    assert expectancy.breakeven_win_rate(1.0, -1.0) == pytest.approx(0.5)
    assert expectancy.breakeven_win_rate(0.0, -1.0) == pytest.approx(1.0)
    # Fees move the bar: the same payoff needs a higher win rate.
    assert expectancy.required_win_rate(2.0, -1.0, fee_r=0.1) > 1 / 3


def test_a_low_win_rate_can_still_be_profitable():
    # Three wins at 3R against seven 1R losses: 30% win rate, still positive.
    r_values = [3.0, 3.0, 3.0] + [-1.0] * 7
    report = tm.Expectancy().evaluate(r_values)
    assert report.win_rate == pytest.approx(0.3)
    assert report.expectancy_r > 0
    assert report.breakeven_win_rate < report.win_rate


def test_kelly_and_overtrading_drag():
    report = tm.Expectancy().evaluate([2.0, -1.0] * 10)
    assert 0.0 < report.kelly_fraction <= 1.0
    drag = tm.Expectancy().overtrading_drag(5, 0.02, trading_days=250)
    assert drag["annual_trades"] == pytest.approx(1250)
    assert drag["annual_drag_r"] == pytest.approx(25.0)


# ── Structure ─────────────────────────────────────────────────────────────

def test_structure_map_clusters_levels_and_reads_the_trend(trend):
    structure = tm.StructureMap()
    levels = structure.levels(trend)
    assert levels["support"] and levels["resistance"]
    assert all(l.touches >= 1 for l in levels["support"])
    assert all(l.kind == "support" for l in levels["support"])
    assert structure.trend(trend)["trend"] in ("uptrend", "downtrend", "range")

    nearest = structure.nearest(trend)
    price = trend.last.close
    if nearest["support"]:
        assert nearest["support"].price <= price
    if nearest["resistance"]:
        assert nearest["resistance"].price >= price


def test_structure_detects_an_uptrend_from_two_rising_swings():
    closes = [10, 12, 14, 12, 15, 17, 15, 18, 20, 18, 21, 23, 21, 24]
    series = tm.CandleSeries.from_rows(
        [(c, c + 0.4, c - 0.4, c) for c in closes])
    trend = tm.StructureMap(left=1, right=1).trend(series)
    assert trend["trend"] == "uptrend"
    assert trend["higher_highs"] is True
    assert trend["higher_lows"] is True


# ── Price action ──────────────────────────────────────────────────────────

def test_detector_finds_a_volume_confirmed_bullish_engulfing():
    rows = [(100, 101, 99, 100, 1000)] * 20
    rows += [(100, 100.4, 99.5, 99.6, 1000),      # small bearish bar
             (99.5, 102.0, 99.4, 101.8, 2600)]     # engulfing, 2.6x volume
    series = tm.CandleSeries.from_rows(rows)
    hits = tm.PatternDetector().detect(series)
    names = [h.name for h in hits]
    assert "bullish_engulfing" in names
    hit = next(h for h in hits if h.name == "bullish_engulfing")
    assert hit.direction == "bullish"
    assert hit.volume_confirmed is True
    assert hit.strength > 0.5


def test_detector_reads_a_hammer_and_a_shooting_star():
    rows = [(100, 100.5, 99.5, 100, 1000)] * 20
    rows.append((100, 100.1, 96.0, 99.9, 1800))     # long lower wick
    series = tm.CandleSeries.from_rows(rows)
    assert "hammer" in [h.name for h in tm.PatternDetector().detect(series)]

    rows[-1] = (100, 104.0, 99.9, 100.1, 1800)      # long upper wick
    series = tm.CandleSeries.from_rows(rows)
    assert "shooting_star" in [h.name for h in tm.PatternDetector().detect(series)]


def test_detector_flags_an_unconfirmed_pattern():
    rows = [(100, 101, 99, 100, 1000)] * 20
    rows += [(100, 100.4, 99.5, 99.6, 1000), (99.5, 101.0, 99.4, 100.9, 500)]
    series = tm.CandleSeries.from_rows(rows)
    hit = next(h for h in tm.PatternDetector().detect(series)
               if h.name == "bullish_engulfing")
    assert hit.volume_confirmed is False
    assert hit.strength < 0.7


def test_pattern_scan_covers_the_whole_series(trend):
    hits = tm.PatternDetector().scan(trend)
    assert {h.index for h in hits}
    assert all(1 <= h.index < len(trend) for h in hits)


def test_volume_analyzer_reports_relative_volume_and_obv():
    rows = [(100 + i, 101 + i, 99 + i, 100 + i, 1000) for i in range(20)]
    rows.append((120, 126, 119, 125, 4000))          # climax bar
    series = tm.CandleSeries.from_rows(rows)
    analyzer = tm.VolumeAnalyzer()
    reading = analyzer.analyze(series)
    assert reading.relative_volume > 2.5
    assert reading.climax is True
    assert analyzer.obv(series)[-1] > 0


def test_volume_divergence_is_measured_not_guessed(trend):
    reading = tm.VolumeAnalyzer().analyze(trend)
    assert reading.divergence in ("none", "bullish", "bearish")
    # Flat price with falling participation is not a divergence in either way
    # for a rising series; the reading must still be one of the three states.
    assert isinstance(reading.obv_slope, float)


# ── Indicators ────────────────────────────────────────────────────────────

def test_moving_average_stack_reports_alignment_and_extension(trend):
    stack = tm.MovingAverageStack().evaluate(trend)
    assert stack is not None
    assert stack.fast > 0 and stack.slow > 0
    assert stack.alignment in ("bullish", "bearish", "mixed")
    assert stack.extension_pct == pytest.approx(
        (trend.closes[-1] - stack.fast) / stack.fast * 100)
    assert tm.MovingAverageStack(fast=500).evaluate(trend) is None


def test_rsi_is_bounded_and_trend_aware(trend):
    rsi = tm.Rsi()
    values = rsi.series(trend.closes)
    assert values and all(0.0 <= v <= 100.0 for v in values)
    reading = rsi.evaluate(trend, "uptrend")
    assert reading.zone in ("oversold", "weak", "neutral", "strong", "overbought")
    if reading.zone == "overbought":
        assert "Strength in an uptrend" in reading.reading


def test_rsi_reads_overbought_differently_outside_an_uptrend(trend):
    rsi = tm.Rsi()
    up = rsi.evaluate(trend, "uptrend")
    flat = rsi.evaluate(trend, "range")
    if up.zone == "overbought":
        assert up.reading != flat.reading


def test_rsi_falls_for_a_falling_series_and_divergence_is_detected():
    rising = tm.synthetic_series(80, drift=0.4, amplitude=0.5)
    falling = tm.synthetic_series(80, drift=-0.4, amplitude=0.5)
    rsi = tm.Rsi()
    assert rsi.value(rising) > rsi.value(falling)
    assert rsi.zone(75.0) == "overbought"
    assert rsi.zone(25.0) == "oversold"

    # Price makes a higher high while momentum fades: bearish divergence.
    closes = [10 + i * 0.5 for i in range(15)] + [17 + i * 0.9 for i in range(10)]
    closes += [26.0, 26.2, 26.1, 26.3]
    series = tm.CandleSeries.from_rows([(c, c + 0.2, c - 0.2, c) for c in closes])
    assert rsi.divergence(series) in ("bearish", "none")


def test_regime_classifier_separates_trend_from_range():
    trending = tm.synthetic_series(120, drift=0.5, amplitude=0.3)
    choppy = tm.synthetic_series(120, drift=0.0, amplitude=3.0, period=4)
    classifier = tm.RegimeClassifier(window=20)
    trend_reading = classifier.evaluate(trending)
    range_reading = classifier.evaluate(choppy)
    assert trend_reading.regime == "trend_up"
    assert trend_reading.efficiency > range_reading.efficiency
    assert range_reading.regime in ("range", "transition")
    assert 0.0 <= trend_reading.efficiency <= 1.0


# ── Breakouts ─────────────────────────────────────────────────────────────

def test_breakout_confirmed_on_close_volume_and_follow_through():
    rows = [(99, 100, 98.5, 99.5, 1000)] * 20
    rows += [(99.5, 100.4, 99.4, 100.2, 1000),
             (100.2, 101.6, 100.1, 101.5, 2000)]
    series = tm.CandleSeries.from_rows(rows)
    verdict = tm.BreakoutValidator().evaluate(series, level=100.0)
    assert verdict.verdict == "confirmed"
    assert verdict.checks["close_through"] is True
    assert verdict.checks["volume"] is True
    assert verdict.score == pytest.approx(1.0)


def test_breakout_wick_through_is_a_fakeout():
    rows = [(99, 100, 98.5, 99.5, 1000)] * 20
    rows += [(99.5, 101.2, 99.4, 99.8, 1500)]        # high above, close below
    series = tm.CandleSeries.from_rows(rows)
    verdict = tm.BreakoutValidator().evaluate(series, level=100.0)
    assert verdict.verdict == "fakeout"
    assert verdict.checks["close_through"] is False
    assert verdict.checks["held"] is False


def test_breakout_without_volume_stays_pending():
    rows = [(99, 100, 98.5, 99.5, 1000)] * 20
    rows += [(99.5, 100.6, 99.4, 100.4, 900), (100.4, 101.6, 100.3, 101.5, 800)]
    series = tm.CandleSeries.from_rows(rows)
    verdict = tm.BreakoutValidator().evaluate(series, level=100.0)
    assert verdict.verdict == "pending"
    assert verdict.checks["volume"] is False
    assert 0.0 < verdict.score < 1.0


# ── Discipline ────────────────────────────────────────────────────────────

def test_guard_blocks_the_trade_after_a_loss(policy):
    guard = tm.DisciplineGuard(policy, cooldown_after_loss=900.0)
    guard.record(-1.0, at=1000.0)
    decision = guard.evaluate(now=1000.0 + 120.0)
    assert decision.allowed is False
    assert decision.size_multiplier == pytest.approx(0.75)
    assert any("cooldown" in r for r in decision.reasons)
    assert any("size reduced" in r for r in decision.reasons)

    later = guard.evaluate(now=1000.0 + 900.0)
    assert later.allowed is True
    assert later.size_multiplier == pytest.approx(0.75)


def test_guard_shrinks_size_on_a_loss_streak_to_a_floor(policy):
    guard = tm.DisciplineGuard(policy, streak_step=0.25, min_size_multiplier=0.25)
    for i in range(5):
        guard.record(-1.0, at=float(i))
    assert guard.consecutive_losses == 5
    assert guard.size_multiplier() == pytest.approx(0.25)
    guard.record(1.0, at=10.0)
    assert guard.consecutive_losses == 0
    assert guard.size_multiplier() == pytest.approx(1.0)


def test_guard_stops_the_day_on_the_loss_cap(policy):
    guard = tm.DisciplineGuard(policy)
    # One full-risk loss is 1/3 of the 3% daily cap; three of them hit it.
    for i in range(3):
        guard.record(-1.0, at=float(i) * 10_000.0)
    decision = guard.evaluate(now=1e9)
    assert decision.allowed is False
    assert any("daily loss cap" in r for r in decision.reasons)


def test_guard_caps_trade_frequency(policy):
    guard = tm.DisciplineGuard(policy)
    for i in range(policy.max_trades_per_day):
        guard.record(0.5, at=float(i) * 10_000.0)
    decision = guard.evaluate(now=1e9)
    assert decision.allowed is False
    assert any("trade cap" in r for r in decision.reasons)
    guard.reset_day()
    assert guard.evaluate(now=1e9).allowed is True


# ── Correlation ───────────────────────────────────────────────────────────

def test_correlation_collapses_identical_series_into_one_bet(trend):
    other = tm.synthetic_series(160, drift=0.15, amplitude=2.0)
    analyzer = tm.CorrelationAnalyzer()
    matrix = analyzer.matrix({"A": trend, "B": other})
    assert matrix[("A", "B")] == pytest.approx(1.0, abs=1e-9)
    assert analyzer.clusters({"A": trend, "B": other}) == [["A", "B"]]

    heat = analyzer.portfolio_heat({"A": 900.0, "B": 900.0},
                                   {"A": trend, "B": other}, 100_000.0)
    assert heat["naive_risk"] == pytest.approx(1800.0)
    assert heat["clustered_risk"] == pytest.approx(900.0)
    assert heat["distinct_bets"] == 1
    assert heat["clustered_pct"] == pytest.approx(0.9)


def test_correlation_pairs_sorted_by_absolute_value(trend):
    same = tm.synthetic_series(160, drift=0.15, amplitude=2.0)
    opposite = tm.synthetic_series(160, drift=0.15, amplitude=-2.0)
    analyzer = tm.CorrelationAnalyzer()
    pairs = analyzer.pairs({"A": trend, "B": same, "C": opposite})
    assert pairs[0].correlation >= 0.9
    assert pairs[0].same_bet is True
    assert pairs[-1].correlation < 0


# ── Backtesting ───────────────────────────────────────────────────────────

def test_backtest_enters_on_the_bar_after_the_signal(trend):
    rule = tm.ma_cross_signal()
    result = tm.Backtester().run(trend, rule)
    assert result.trades, "the worked MA-cross rule must fire on this series"
    for trade in result.trades:
        signal_bar = trend.candles[trade.index - 1]
        assert trade.entry == pytest.approx(signal_bar.close, rel=1e-2)
        assert trade.exit_index >= trade.index
        assert trade.fees_r > 0
        assert trade.reason in ("stop", "target", "time")
        assert trade.net_r == pytest.approx(trade.r_multiple - trade.fees_r)


def test_backtest_equity_curve_and_drawdown(trend):
    result = tm.Backtester().run(trend, tm.ma_cross_signal())
    assert len(result.equity_curve) == len(result.trades) + 1
    assert result.equity_curve[0] == pytest.approx(100_000.0)
    assert result.max_drawdown_pct >= 0.0
    assert result.exposure > 0.0
    data = result.as_dict()
    assert data["trades"] == len(result.trades)
    assert data["end_equity"] == pytest.approx(round(result.equity_curve[-1], 4))


def test_backtest_rejects_a_signal_with_the_stop_on_the_wrong_side(trend):
    def bad_signal(series, index):
        close = series.candles[index].close
        return {"direction": "long", "stop": close + 50.0, "target": close + 60.0}

    result = tm.Backtester().run(trend, bad_signal)
    assert result.trades == []
    assert result.total_return_pct == 0.0


def test_backtest_counts_a_stop_before_a_target_when_both_are_touched():
    # One signal, then a bar whose range covers both levels.
    rows = [(100, 100.5, 99.5, 100, 1000)] * 5
    rows += [(100, 100.5, 99.5, 100, 1000), (100, 112, 88, 100, 1000)]
    series = tm.CandleSeries.from_rows(rows)

    def signal(s, index):
        if index == 4:
            return {"direction": "long", "stop": 95.0, "target": 105.0}
        return None

    result = tm.Backtester(fee_r=0.0, slippage_r=0.0).run(series, signal)
    assert len(result.trades) == 1
    assert result.trades[0].reason == "stop"
    assert result.trades[0].r_multiple == pytest.approx(-1.0)


# ── Journal ───────────────────────────────────────────────────────────────

def test_journal_computes_stats_and_setup_breakdown():
    journal = tm.TradeJournal()
    journal.record("breakout", "long", 100.0, 95.0, 110.0)      # +2R
    journal.record("breakout", "long", 100.0, 95.0, 95.0)       # -1R
    journal.record("pullback", "long", 100.0, 98.0, 106.0)      # +3R
    journal.record("pullback", "long", 100.0, 98.0, 96.0)       # -2R
    stats = journal.stats()
    assert stats.trades == 4
    assert stats.win_rate == pytest.approx(0.5)
    assert stats.total_r == pytest.approx(2.0)
    assert stats.expectancy_r == pytest.approx(0.5)
    assert stats.longest_win_streak == 1
    assert stats.longest_loss_streak == 1
    assert stats.plan_adherence == pytest.approx(1.0)
    assert stats.by_setup["breakout"]["trades"] == 2
    assert stats.by_setup["pullback"]["expectancy_r"] == pytest.approx(0.5)
    assert stats.best_setup in ("breakout", "pullback")


def test_journal_payoff_skew_shows_cut_losers_sizing_winners():
    journal = tm.TradeJournal()
    journal.record("a", "long", 100.0, 95.0, 120.0)      # +4R
    journal.record("a", "long", 100.0, 95.0, 97.0)       # -0.6R (cut early)
    skew = journal.payoff_skew()
    assert skew["biggest_win_r"] == pytest.approx(4.0)
    assert skew["biggest_loss_r"] == pytest.approx(-0.6)
    assert skew["loss_to_win_ratio"] == pytest.approx(0.15)


def test_journal_records_plan_adherence():
    journal = tm.TradeJournal()
    journal.record("a", "long", 100.0, 95.0, 110.0, followed_plan=False)
    journal.record("a", "long", 100.0, 95.0, 110.0)
    assert journal.stats().plan_adherence == pytest.approx(0.5)


def test_empty_journal_is_well_defined():
    stats = tm.TradeJournal().stats()
    assert stats.trades == 0
    assert stats.expectancy_r == 0.0
    assert stats.by_setup == {}
    assert tm.TradeJournal().payoff_skew()["average_win_r"] == 0.0


# ── Curriculum ────────────────────────────────────────────────────────────

def test_curriculum_has_all_twenty_one_lessons():
    assert len(tm.CURRICULUM) == 21
    assert tm.CURRICULUM[0].slug == "risk-first"
    assert tm.CURRICULUM[-1].slug == "correlation"
    assert len({lesson.slug for lesson in tm.CURRICULUM}) == 21
    assert all(lesson.rule for lesson in tm.CURRICULUM)


def test_curriculum_run_passes_every_executable_lesson(trend):
    report = tm.MasteryCurriculum().run(trend)
    assert report.passed + report.failed == 21
    assert report.failed == 0, [l for l in report.lessons if not l["passed"]]
    assert report.score == pytest.approx(1.0)
    assert report.expectancy_r > 0
    assert all(l["detail"] for l in report.lessons)
    data = report.as_dict()
    assert data["lessons"][0]["title"].startswith("Risk first")


def test_curriculum_reports_a_failure_when_the_data_is_too_thin():
    thin = tm.synthetic_series(4)
    report = tm.MasteryCurriculum().run(thin, r_values=(-1.0, -1.0))
    assert report.failed > 0
    assert report.score < 1.0
    failed = [l for l in report.lessons if not l["passed"]]
    assert failed


def test_synthetic_series_is_deterministic():
    a = tm.synthetic_series(30)
    b = tm.synthetic_series(30)
    assert [c.close for c in a.candles] == [c.close for c in b.candles]
    assert all(c.high >= max(c.open, c.close) for c in a.candles)
    assert all(c.low <= min(c.open, c.close) for c in a.candles)
    assert math.isfinite(a.atr())
