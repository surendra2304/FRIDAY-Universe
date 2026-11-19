"""TASK-STR-FWD-006: decided sizing package — unit coverage.

Covers the four mechanisms the package introduced:
  * forward_guard mark-to-market drawdown (closed + unrealized),
    per-strategy venue-equity denomination, sleeve MTM combined;
  * the daemon heat-cap budget function and open-risk aggregation;

Everything is offline: fake adapters/engines only, no network, no
orders. The pre-FWD-006 behaviour with default arguments is pinned
where the package promised no change (closed-only, composite basis).

The sleeve runner / OANDA trader budget tests that once sat here were
removed in TASK-REL-054 with the oanda_demo package they exercised.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from measurement import forward_guard


def _rows(strategy, pnls):
    return [
        {"strategy": strategy, "net_pnl": p, "exit_time": float(i + 1)}
        for i, p in enumerate(pnls)
    ]


# ----------------------------------------------------------------------
# forward_guard: mark-to-market drawdown
# ----------------------------------------------------------------------

def test_closed_only_default_unchanged():
    rows = _rows("s", [100.0, -50.0])
    stats = forward_guard.strategy_stats(rows, "s")
    assert stats["max_drawdown_usd"] == 50.0
    assert stats["unrealized_pnl"] == 0.0
    assert stats["mtm_net_pnl"] == 50.0


def test_unrealized_deepens_drawdown_but_not_performance_stats():
    rows = _rows("s", [100.0, -50.0])
    stats = forward_guard.strategy_stats(rows, "s", unrealized_pnl=-80.0)
    # Closed curve peaked at +100; MTM endpoint is -30 -> DD 130.
    assert stats["max_drawdown_usd"] == 130.0
    assert stats["current_drawdown_usd"] == 130.0
    # Performance statistics stay closed-trades-only by design.
    assert stats["expectancy"] == 25.0
    assert stats["profit_factor"] == 2.0
    assert stats["net_pnl"] == 50.0
    assert stats["mtm_net_pnl"] == -30.0


def test_mtm_breach_trips_kill_where_closed_only_would_not():
    # 60 winning closed trades: the closed curve never draws down.
    rows = _rows("s", [15.0] * 60)
    closed_only = forward_guard.evaluate(rows, 10_000.0, ["s"])[0]
    assert not closed_only["breached"]
    # An open book $600 underwater: MTM drawdown $600 > 5% of $10k.
    mtm = forward_guard.evaluate(
        rows, 10_000.0, ["s"], unrealized_by_strategy={"s": -600.0}
    )[0]
    assert mtm["breached"]
    assert any("venue equity" in r for r in mtm["reasons"])


def test_equity_by_strategy_denominates_the_limit():
    rows = _rows("s", [100.0, -300.0])  # closed DD $300
    # Composite basis $20k -> limit $1,000: no breach.
    wide = forward_guard.evaluate(rows, 20_000.0, ["s"])[0]
    assert not wide["breached"]
    # Venue basis $5k -> limit $250: breach.
    narrow = forward_guard.evaluate(
        rows, 20_000.0, ["s"], equity_by_strategy={"s": 5_000.0}
    )[0]
    assert narrow["breached"]
    assert narrow["drawdown_limit_usd"] == 250.0


def test_sleeve_mtm_combines_components():
    rows = _rows("a", [100.0]) + _rows("b", [-50.0])
    # Combined closed DD is $50 on a $20k basis (limit $1,000): fine.
    ok = forward_guard.evaluate_sleeves(rows, 20_000.0, {"sl": ["a", "b"]})[0]
    assert not ok["breached"]
    # Component b $1,200 underwater -> combined MTM DD $1,250 > $1,000.
    hit = forward_guard.evaluate_sleeves(
        rows,
        20_000.0,
        {"sl": ["a", "b"]},
        unrealized_by_component={"b": -1_200.0},
    )[0]
    assert hit["breached"]
    assert hit["unrealized_pnl"] == -1_200.0
    assert hit["max_drawdown_usd"] == 1_250.0


# ----------------------------------------------------------------------
# daemon: heat-cap budget + open-risk aggregation
# ----------------------------------------------------------------------

def test_heat_capped_risk_amount():
    from autonomy.run_daemon import heat_capped_risk_amount

    # No open risk: full per-trade budget (0.1% of 10,000 = 10).
    assert heat_capped_risk_amount(10_000.0, 0.001, 0.0, 0.02) == 10.0
    # Open risk $195 of a $200 cap: only $5 of budget remains.
    assert heat_capped_risk_amount(10_000.0, 0.001, 195.0, 0.02) == 5.0
    # At/over the cap: nothing new may open.
    assert heat_capped_risk_amount(10_000.0, 0.001, 200.0, 0.02) == 0.0
    assert heat_capped_risk_amount(10_000.0, 0.001, 250.0, 0.02) < 0.0


class _FakeEngine:
    def __init__(self, positions, attribution):
        self.positions = positions
        self.position_strategy = attribution


def _daemon_with_book():
    from autonomy.run_daemon import StratexTradingEngine

    eng = StratexTradingEngine.__new__(StratexTradingEngine)
    eng.max_stop_pct = 0.03
    pos = {
        "binance_futures:BTCUSDT": SimpleNamespace(
            quantity=2.0, entry_price=100.0, stop_loss=95.0,
            mark_price=97.0, unrealized_pnl=-6.0, side="LONG",
        ),
        "binance_futures:ETHUSDT": SimpleNamespace(
            quantity=1.0, entry_price=50.0, stop_loss=0.0,
            mark_price=49.0, unrealized_pnl=0.0, side="LONG",
        ),
        "binance_futures:SOLUSDT": SimpleNamespace(
            quantity=5.0, entry_price=20.0, stop_loss=19.0,
            mark_price=21.0, unrealized_pnl=5.0, side="LONG",
        ),
    }
    attr = {
        "binance_futures:BTCUSDT": "strategy_alpha",
        "binance_futures:ETHUSDT": "strategy_alpha",
        "binance_futures:SOLUSDT": "strategy_beta",
    }
    eng.engine = _FakeEngine(pos, attr)
    return eng


def test_strategy_open_risk_aggregation():
    eng = _daemon_with_book()
    # alpha: BTC 2 x |100-95| = 10; ETH has no stop -> 1 x 50 x 3% = 1.5.
    assert eng._strategy_open_risk("strategy_alpha") == 11.5
    assert eng._strategy_open_risk("strategy_beta") == 5.0
    assert eng._strategy_open_risk("strategy_gamma") == 0.0
    # Venue filter excludes nothing here (all binance) but must not crash.
    assert eng._strategy_open_risk("strategy_alpha", "binance_futures") == 11.5
    assert eng._strategy_open_risk("strategy_alpha", "oanda") == 0.0


def test_open_unrealized_by_strategy():
    eng = _daemon_with_book()
    out = eng._open_unrealized_by_strategy()
    # BTC carries a broker figure (-6); ETH's is 0 -> derived from the
    # mark: (49 - 50) x 1 = -1. alpha total -7; beta +5.
    assert out["strategy_alpha"] == -7.0
    assert out["strategy_beta"] == 5.0
