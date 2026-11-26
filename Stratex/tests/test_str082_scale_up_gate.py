"""TASK-STR-082 leg 1: scale-up gate unit coverage.

Covers the six frozen conditions in measurement/scale_up_gate.py:
three months profitable, 50+ trades, drawdown under 10%, consistent
rules (fail-closed when unverified), never after a big win, never to
recover losses. Everything is offline: synthetic fill-ledger rows
only, no network, no orders.

Fixed "now" is 2026-11-25 08:30 UTC (14:00 IST), so the window is
the calendar months Sep / Oct / Nov 2026.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from measurement import scale_up_gate

EQUITY = 10_000.0
NOW = datetime.datetime(2026, 11, 25, 8, 30, tzinfo=datetime.timezone.utc).timestamp()
# Big-win threshold: 10 x 0.1% x $10,000 = $100.
BIG_WIN = 100.0


def _month_rows(year, month, pnls):
    rows = []
    for i, p in enumerate(pnls):
        ts = datetime.datetime(
            year, month, (i % 28) + 1, 12, 0, tzinfo=datetime.timezone.utc
        ).timestamp()
        rows.append({"strategy": "s", "net_pnl": float(p), "exit_time": ts})
    return rows


def _passing_rows():
    """60 trades, every month profitable, DD $5, ends at peak."""
    return (
        _month_rows(2026, 9, [10.0] * 20)
        + _month_rows(2026, 10, [10.0] * 19 + [-5.0])
        + _month_rows(2026, 11, [10.0] * 20)
    )


def _decide(rows, **kw):
    kw.setdefault("rule_change_times", [])
    return scale_up_gate.evaluate_scale_up(rows, EQUITY, "s", NOW, **kw)


def test_allows_when_every_condition_holds():
    res = _decide(_passing_rows())
    assert res["allowed"], res["reasons"]
    assert res["reasons"] == []
    assert res["trades"] == 60
    assert [m["profitable"] for m in res["months"]] == [True, True, True]
    assert [m["net_pnl"] for m in res["months"]] == [200.0, 185.0, 200.0]
    assert res["max_drawdown_usd"] == 5.0
    assert res["drawdown_limit_usd"] == 1_000.0
    assert res["current_drawdown_usd"] == 0.0
    assert res["rules_consistent"] is True
    assert res["big_win_threshold_usd"] == BIG_WIN


def test_denies_losing_month():
    rows = (
        _month_rows(2026, 9, [10.0] * 20)
        + _month_rows(2026, 10, [10.0] * 10 + [-15.0] * 10)
        + _month_rows(2026, 11, [10.0] * 20)
    )
    res = _decide(rows)
    assert not res["allowed"]
    assert any("not profitable in each of the last 3 months" in r for r in res["reasons"])
    assert any("2026-10" in r for r in res["reasons"])


def test_denies_empty_month():
    rows = _month_rows(2026, 9, [10.0] * 20) + _month_rows(2026, 10, [10.0] * 20)
    res = _decide(rows)
    assert not res["allowed"]
    assert any("2026-11" in r for r in res["reasons"])


def test_denies_fewer_than_50_trades():
    rows = (
        _month_rows(2026, 9, [10.0] * 17)
        + _month_rows(2026, 10, [10.0] * 16)
        + _month_rows(2026, 11, [10.0] * 16)
    )
    res = _decide(rows)
    assert not res["allowed"]
    assert any("49 closed trades" in r and "minimum 50" in r for r in res["reasons"])


def test_exactly_50_trades_passes_the_count():
    rows = (
        _month_rows(2026, 9, [10.0] * 17)
        + _month_rows(2026, 10, [10.0] * 16 + [-5.0])
        + _month_rows(2026, 11, [10.0] * 16)
    )
    res = _decide(rows)
    assert res["allowed"], res["reasons"]
    assert res["trades"] == 50


def test_denies_drawdown_at_or_over_10pct():
    rows = (
        _month_rows(2026, 9, [100.0] * 19 + [-1_500.0] + [1_500.0])
        + _month_rows(2026, 10, [10.0] * 20)
        + _month_rows(2026, 11, [10.0] * 20)
    )
    res = _decide(rows)
    assert not res["allowed"]
    assert any("drawdown $1500.00" in r for r in res["reasons"])
    assert res["max_drawdown_usd"] == 1_500.0


def test_denies_when_rule_history_not_supplied():
    res = scale_up_gate.evaluate_scale_up(
        _passing_rows(), EQUITY, "s", NOW, rule_change_times=None
    )
    assert not res["allowed"]
    assert res["rules_consistent"] is None
    assert any("rule-change history not supplied" in r for r in res["reasons"])


def test_denies_rule_change_inside_window():
    change = datetime.datetime(2026, 10, 15, tzinfo=datetime.timezone.utc).timestamp()
    res = _decide(_passing_rows(), rule_change_times=[change])
    assert not res["allowed"]
    assert res["rules_consistent"] is False
    assert res["rule_changes_in_window"] == [change]
    assert any("rules changed 1 time(s)" in r for r in res["reasons"])


def test_allows_rule_change_before_window():
    change = datetime.datetime(2026, 8, 15, tzinfo=datetime.timezone.utc).timestamp()
    res = _decide(_passing_rows(), rule_change_times=[change])
    assert res["allowed"], res["reasons"]
    assert res["rules_consistent"] is True
    assert res["rule_changes_in_window"] == []


def test_denies_big_win_as_most_recent_trade():
    rows = (
        _month_rows(2026, 9, [10.0] * 20)
        + _month_rows(2026, 10, [10.0] * 19 + [-5.0])
        + _month_rows(2026, 11, [10.0] * 19 + [150.0])
    )
    res = _decide(rows)
    assert not res["allowed"]
    assert res["last_trade_pnl"] == 150.0
    assert any("big win" in r for r in res["reasons"])


def _late_nov_row(pnl):
    # 08:00 UTC on Nov 25 — inside the window (NOW is 08:30 UTC).
    ts = datetime.datetime(2026, 11, 25, 8, 0, tzinfo=datetime.timezone.utc).timestamp()
    return [{"strategy": "s", "net_pnl": float(pnl), "exit_time": ts}]


def test_big_win_threshold_boundary():
    base = (
        _month_rows(2026, 9, [10.0] * 20)
        + _month_rows(2026, 10, [10.0] * 19 + [-5.0])
        + _month_rows(2026, 11, [10.0] * 19)
    )
    # Exactly at the $100 threshold: a big win, denied.
    at = _decide(base + _late_nov_row(100.0))
    assert not at["allowed"]
    assert at["last_trade_pnl"] == 100.0
    # Just under it: allowed.
    under = _decide(base + _late_nov_row(99.0))
    assert under["allowed"], under["reasons"]


def test_denies_scaling_to_recover_losses():
    rows = (
        _month_rows(2026, 9, [10.0] * 20)
        + _month_rows(2026, 10, [10.0] * 19 + [-5.0])
        + _month_rows(2026, 11, [10.0] * 19 + [-30.0])
    )
    res = _decide(rows)
    assert not res["allowed"]
    assert res["current_drawdown_usd"] == 30.0
    assert any("recover losses" in r for r in res["reasons"])


def test_rows_outside_window_do_not_count():
    # A losing August (before the window) must not deny the gate;
    # an August loss also must not enter the drawdown.
    rows = _month_rows(2026, 8, [-5_000.0]) + _passing_rows()
    res = _decide(rows)
    assert res["allowed"], res["reasons"]
    assert res["trades"] == 60
    assert res["rows_excluded_outside_window"] == 1
