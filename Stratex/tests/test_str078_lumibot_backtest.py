"""TASK-STR-078: Lumibot wrapper backtest must actually trade.

Regression test for a real defect found 2026-11-25 by Muse 18 while
verifying the STR-078 repo-side mapping: LumibotBacktest.run() read the
signals as ``dict[int, int]`` (``signals.get(symbol, {}).get(i, 0)``) while
generate_signals() returns ``dict[str, list[int]]`` — so every bar read
sig == 0, the backtest never opened a position, and every metric came
back 0.0 on any input. The fix indexes the signal list.
"""
import pytest

from app.agents.real_lumibot import LumibotBacktest, LumibotManager


def _rising(n=60):
    return [100.0 + i * 0.5 + (i % 7) * 0.3 for i in range(n)]


def test_sma_crossover_trades_on_rising_series():
    result = LumibotBacktest.run(
        {"close": _rising()}, strategy_type="sma_crossover", initial_cash=100000.0
    )
    assert result["trade_count"] > 0, "SMA crossover placed no trades on a rising series"
    assert result["trades"][0]["action"] == "BUY"
    assert result["portfolio_values"][-1] != 100000.0
    assert result["total_return"] != 0.0


def test_signals_are_lists_indexed_by_bar():
    signals = LumibotBacktest.generate_signals(
        {"close": _rising()}, strategy_type="sma_crossover"
    )
    assert isinstance(signals["close"], list)
    assert len(signals["close"]) == 60
    assert 1 in signals["close"], "rising series must emit a BUY signal after bar 30"


def test_backtest_rejects_empty_input():
    result = LumibotBacktest.run({}, strategy_type="sma_crossover")
    assert "error" in result


def test_manager_backtest_trades():
    mgr = LumibotManager()
    result = mgr.run_backtest(
        {"close": _rising()}, strategy_type="sma_crossover", initial_cash=100000.0
    )
    assert result["trade_count"] > 0
    assert "metrics" in result
