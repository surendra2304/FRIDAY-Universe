"""
tests/test_forward_scorecard.py — TASK-STR-FWD-005 forward scorecard.

Pins the phase-3 forward measurement:
1. Windowing: only fills at/after an entrant's forward start count;
   pre-window fills are reported as excluded history, never blended.
2. Stats parity: the combined-stats helper reproduces
   forward_guard.strategy_stats exactly on single-strategy rows (the
   scorecard must never drift from the enforcer's arithmetic).
3. Kill criteria: expectancy/PF kills stay NOT_ACTIVE below 50 trades
   and trip at >= 50; the drawdown kill has no trade-count gate and
   uses 5% of account equity; sleeves are drawdown-only.
4. Bar distance: 8 weeks AND >= 100 trades, with trades/days to go.
5. Daily breaker: a UTC day losing >= 3% of day-start equity trips.
6. Reconciliation: baseline (reset boundary, USDT-only for Binance per
   the faucet rule) + ledger window net vs current exchange equity;
   discrepancies are flagged, never absorbed. Snapshot fallback is
   labelled when no live probe is supplied.
7. Discovery: strategies trading inside the window that no entrant
   claims appear as UNREGISTERED rows.
"""

import json

import pytest

from measurement import forward_guard, forward_scorecard as fsc

START = fsc.GLOBAL_FORWARD_START
DAY = 86400.0


def _fill(strategy="strategy_alpha", venue="binance_futures", net=10.0,
          exit_time=None, **overrides):
    row = {
        "strategy": strategy,
        "engine": "daemon",
        "venue": venue,
        "symbol": "ETHUSDT",
        "side": "LONG",
        "qty": 0.5,
        "entry_price": 2000.0,
        "exit_price": 2010.0,
        "entry_time": (exit_time or START) - 3600.0,
        "exit_time": START + 3600.0 if exit_time is None else exit_time,
        "gross_pnl": net + 0.5,
        "fees": 0.5,
        "fees_source": "broker",
        "net_pnl": net,
        "exit_reason": "TIME",
        "order_id": "OID",
        "recorded_at": "2026-11-15T06:00:00+00:00",
    }
    row.update(overrides)
    return row


def _entrant(strategies, sleeve=False, start=fsc.GLOBAL_FORWARD_START_ISO,
             venues=("binance_futures",), eid="alpha", lane="FORWARD"):
    return fsc._normalise([{
        "id": eid, "label": eid, "lane": lane, "sleeve": sleeve,
        "strategies": list(strategies), "window_start": start,
        "venues": list(venues),
    }])[0]


def _snapshot(ts, total, venues):
    return {
        "record_type": "EQUITY_SNAPSHOT", "ts": ts,
        "timestamp": "2026-11-15T00:00:00+00:00", "engine": "daemon",
        "trigger": "hourly", "total_equity": total, "venues": venues,
        "excluded_venues": [],
    }


def _boundary(ts, post):
    return {
        "record_type": "RESET_BOUNDARY", "ts": ts,
        "timestamp": "2026-11-14T13:03:53+00:00", "actor": "owner",
        "venues_pre": {}, "venues_post": post, "note": "",
    }


# 1. windowing -------------------------------------------------------------
def test_pre_window_fills_excluded_and_counted():
    fills = [
        _fill(net=100.0, exit_time=START - 3600.0),   # before window
        _fill(net=5.0, exit_time=START + 3600.0),     # inside window
    ]
    card = fsc.score_entrant(_entrant(["strategy_alpha"]), fills,
                             equity_usd=10000.0, now=START + DAY)
    assert card["closed_trades"] == 1
    assert card["net_pnl"] == 5.0
    assert card["pre_window_fills_excluded"] == 1


def test_zero_trade_entrant_states_zero_plainly():
    card = fsc.score_entrant(_entrant(["strategy_alpha"]), [],
                             equity_usd=10000.0, now=START + DAY)
    assert card["closed_trades"] == 0
    assert card["verdict"] == "NO_TRADES_YET"
    assert card["bar"]["trades_to_go"] == 100
    assert card["kill"]["expectancy"]["status"] == "NOT_ACTIVE"
    assert card["kill"]["expectancy"]["trades_until_active"] == 50


# 2. stats parity with the enforcer ---------------------------------------
def test_combined_stats_matches_forward_guard():
    nets = [12.0, -5.0, 3.5, -20.0, 7.25, -1.0, 0.0, 44.0, -13.5, 2.0]
    rows = [_fill(net=n, exit_time=START + 3600.0 * (i + 1))
            for i, n in enumerate(nets)]
    mine = fsc._combined_stats(rows)
    guard = forward_guard.strategy_stats(rows, "strategy_alpha")
    assert mine["trades"] == guard["trades"] == len(nets)
    assert mine["net_pnl"] == pytest.approx(guard["net_pnl"])
    assert mine["expectancy"] == pytest.approx(guard["expectancy"])
    assert mine["profit_factor"] == pytest.approx(guard["profit_factor"])
    assert mine["max_drawdown_usd"] == pytest.approx(guard["max_drawdown_usd"])


# 3. kill criteria ----------------------------------------------------------
def test_expectancy_kill_not_active_below_50_trades():
    fills = [_fill(net=-2.0, exit_time=START + 60.0 * (i + 1)) for i in range(49)]
    card = fsc.score_entrant(_entrant(["strategy_alpha"]), fills,
                             equity_usd=100000.0, now=START + DAY)
    assert card["kill"]["expectancy"]["status"] == "NOT_ACTIVE"
    assert card["verdict"] != "KILL_TRIPPED"


def test_expectancy_and_pf_kill_trip_at_50_plus():
    fills = [_fill(net=-2.0, exit_time=START + 60.0 * (i + 1)) for i in range(55)]
    card = fsc.score_entrant(_entrant(["strategy_alpha"]), fills,
                             equity_usd=100000.0, now=START + DAY)
    assert card["kill"]["expectancy"]["status"] == "TRIPPED"
    assert card["kill"]["profit_factor"]["status"] == "TRIPPED"
    assert card["verdict"] == "KILL_TRIPPED"


def test_drawdown_kill_has_no_trade_gate():
    # 3 trades, curve: +0, -300, -350 -> peak-to-trough 650 > 5% of 10000.
    fills = [
        _fill(net=-300.0, exit_time=START + 60.0),
        _fill(net=-350.0, exit_time=START + 120.0),
        _fill(net=10.0, exit_time=START + 180.0),
    ]
    card = fsc.score_entrant(_entrant(["strategy_alpha"]), fills,
                             equity_usd=10000.0, now=START + DAY)
    assert card["kill"]["drawdown"]["status"] == "TRIPPED"
    assert card["kill"]["drawdown"]["limit_usd"] == 500.0
    assert card["verdict"] == "KILL_TRIPPED"


def test_sleeve_is_drawdown_only():
    # 60 losing trades: expectancy/PF would kill a strategy; a sleeve
    # with a shallow combined curve must NOT trip on them.
    fills = [_fill(strategy="leg_a", net=-1.0, exit_time=START + 60.0 * (i + 1))
             for i in range(60)]
    card = fsc.score_entrant(_entrant(["leg_a"], sleeve=True, eid="sleeve"),
                             fills, equity_usd=100000.0, now=START + DAY)
    assert "expectancy" not in card["kill"]
    assert card["kill"]["drawdown"]["status"] == "SAFE"
    assert card["verdict"] != "KILL_TRIPPED"


def test_sleeve_drawdown_breach_trips():
    fills = [
        _fill(strategy="leg_a", net=-400.0, exit_time=START + 60.0),
        _fill(strategy="leg_b", net=-300.0, exit_time=START + 120.0),
    ]
    ent = _entrant(["leg_a", "leg_b"], sleeve=True, eid="sleeve")
    card = fsc.score_entrant(ent, fills, equity_usd=10000.0, now=START + DAY)
    assert card["kill"]["drawdown"]["status"] == "TRIPPED"
    assert card["verdict"] == "KILL_TRIPPED"


def test_pf_infinite_serializes_as_null():
    fills = [_fill(net=5.0, exit_time=START + 60.0 * (i + 1)) for i in range(3)]
    card = fsc.build_forward_scorecard(
        fills=fills, snapshots=[], entrants=[_entrant(["strategy_alpha"])],
        probe={}, now=START + DAY)
    assert card["entrants"][0]["profit_factor"] is None
    json.dumps(card)  # must not raise / emit Infinity


# 4. bar distance -----------------------------------------------------------
def test_bar_distance_and_projection():
    fills = [_fill(net=1.0, exit_time=START + 3600.0 * (i + 1)) for i in range(40)]
    card = fsc.score_entrant(_entrant(["strategy_alpha"]), fills,
                             equity_usd=10000.0, now=START + 28 * DAY)
    assert card["bar"]["days_in_window"] == 28.0
    assert card["bar"]["trades_to_go"] == 60
    assert card["bar"]["days_to_go"] == 28.0
    assert card["bar"]["bar_met"] is False
    assert card["bar"]["projected_100_trade_date"] is not None


def test_bar_met():
    fills = [_fill(net=1.0, exit_time=START + 3600.0 * (i + 1)) for i in range(120)]
    card = fsc.score_entrant(_entrant(["strategy_alpha"]), fills,
                             equity_usd=10000.0, now=START + 60 * DAY)
    assert card["bar"]["bar_met"] is True
    assert card["verdict"] == "BAR_MET"


# 5. daily breaker ----------------------------------------------------------
def test_daily_breaker_trips_at_3pct():
    day2 = START + DAY  # 2026-11-16, inside window
    snaps = [_snapshot(START - 3600.0, 20000.0, {"binance_futures": 10000.0, "oanda": 10000.0})]
    fills = [_fill(net=-700.0, exit_time=day2 + 3600.0)]  # 3.5% of 20000
    out = fsc.daily_breaker(fills, snaps, START, now=day2 + 7200.0)
    assert out["status"] == "TRIPPED"
    assert out["tripped_days"] == [fsc._utc_day(day2)]


def test_daily_breaker_safe_below_3pct():
    day2 = START + DAY
    snaps = [_snapshot(START - 3600.0, 20000.0, {"binance_futures": 10000.0, "oanda": 10000.0})]
    fills = [_fill(net=-500.0, exit_time=day2 + 3600.0)]  # 2.5%
    out = fsc.daily_breaker(fills, snaps, START, now=day2 + 7200.0)
    assert out["status"] == "SAFE"
    assert out["worst_day"]["loss_pct_of_start_equity"] == 2.5


# 6. reconciliation ---------------------------------------------------------
def test_reconciliation_reconciled_via_boundary_and_probe():
    snaps = [_boundary(START - DAY, {"binance_futures_usdt_only": 5000.0,
                                     "binance_futures_reported": 10583.43})]
    fills = [_fill(net=50.0, exit_time=START + 3600.0)]
    probe = {"binance_futures": {"equity": 5050.0, "unrealized": 0.0,
                                 "source": "test", "ts": "now"}}
    out = fsc.reconcile_venue("binance_futures", fills, snaps, snaps,
                              probe, START, now=START + DAY)
    assert out["baseline_equity"] == 5000.0  # USDT-only, NOT the reported 10583.43
    assert out["status"] == "RECONCILED"
    assert out["unexplained"] == 0.0


def test_reconciliation_discrepancy_is_flagged_not_absorbed():
    snaps = [_boundary(START - DAY, {"binance_futures_usdt_only": 5000.0})]
    fills = [_fill(net=50.0, exit_time=START + 3600.0)]
    probe = {"binance_futures": {"equity": 5200.0, "unrealized": 0.0,
                                 "source": "test", "ts": "now"}}
    out = fsc.reconcile_venue("binance_futures", fills, snaps, snaps,
                              probe, START, now=START + DAY)
    assert out["status"] == "DISCREPANCY"
    assert out["unexplained"] == 150.0


def test_reconciliation_snapshot_fallback_is_labelled():
    snaps = [
        _boundary(START - DAY, {"oanda_nav": 10000.0033}),
        _snapshot(START + 3600.0, 15000.0, {"binance_futures": 5000.0, "oanda": 10000.0}),
    ]
    out = fsc.reconcile_venue("oanda", [], snaps, snaps, {}, START, now=START + DAY)
    assert out["baseline_equity"] == 10000.0033
    assert out["current_equity"] == 10000.0
    assert "latest_snapshot" in out["current_method"]


def test_reconciliation_unrealized_explains_gap():
    snaps = [_boundary(START - DAY, {"binance_futures_usdt_only": 5000.0})]
    probe = {"binance_futures": {"equity": 5120.0, "unrealized": 120.0,
                                 "source": "test", "ts": "now"}}
    out = fsc.reconcile_venue("binance_futures", [], snaps, snaps,
                              probe, START, now=START + DAY)
    assert out["unexplained"] == 120.0
    assert out["unexplained_ex_unrealized"] == 0.0
    assert out["status"] == "RECONCILED"


# 7. discovery --------------------------------------------------------------
def test_unregistered_strategy_in_window_is_surfaced():
    fills = [_fill(strategy="strategy_mystery", net=3.0, exit_time=START + 3600.0)]
    card = fsc.build_forward_scorecard(
        fills=fills, snapshots=[], entrants=[_entrant(["strategy_alpha"])],
        probe={}, now=START + DAY)
    ids = [e["id"] for e in card["entrants"]]
    assert "unregistered:strategy_mystery" in ids


def test_load_entrants_returns_sane_defaults():
    entrants = fsc.load_entrants()
    assert isinstance(entrants, list) and entrants
    for e in entrants:
        assert e["window_start_epoch"] > 0
        assert "strategies" in e and "lane" in e


# 8. registry-shape resolution (mirrors deployed config_strategy) -----------
def test_entrants_from_registry_real_shape():
    registry = {
        "ichimoku_trend": {"status": "VALIDATED", "forward_protocol": True},
        "dow_effect": {"status": "VALIDATED", "forward_protocol": True},
        "sleeve_shock_breakout": {"status": "VALIDATED", "sleeve": "best_per_class"},
        "sleeve_tsmom2_dual": {"status": "VALIDATED", "sleeve": "best_per_class"},
        "watch_bollinger": {"forward_protocol": True, "forward_lane": "FORWARD_TEST"},
        "watch_excluded": {"forward_protocol": False, "forward_lane": "FORWARD_TEST"},
        "adx_ema": {"status": "OBSERVE_ONLY"},
    }
    entrants = fsc._normalise(fsc._entrants_from_registry(registry))
    by_id = {e["id"]: e for e in entrants}
    assert set(by_id) == {
        "ichimoku_trend", "dow_effect", "sleeve:best_per_class", "watch_bollinger",
    }
    assert by_id["ichimoku_trend"]["lane"] == "FORWARD"
    assert by_id["watch_bollinger"]["lane"] == "FORWARD_TEST"
    # Both ledger spellings claimed (daemon module name + bare key).
    assert by_id["ichimoku_trend"]["strategies"] == [
        "strategy_ichimoku_trend", "ichimoku_trend",
    ]
    sleeve = by_id["sleeve:best_per_class"]
    assert sleeve["sleeve"] is True
    assert "strategy_sleeve_shock_breakout" in sleeve["strategies"]
    assert "sleeve_tsmom2_dual" in sleeve["strategies"]
    assert sleeve["venues"] == ["binance_futures", "oanda"]


def test_dual_spelling_fills_match_one_entrant():
    fills = [
        _fill(strategy="strategy_ichimoku_trend", net=7.0, exit_time=START + 60.0),
        _fill(strategy="ichimoku_trend", net=3.0, exit_time=START + 120.0),
    ]
    ent = fsc._normalise(fsc._entrants_from_registry(
        {"ichimoku_trend": {"forward_protocol": True}}))[0]
    card = fsc.score_entrant(ent, fills, equity_usd=10000.0, now=START + DAY)
    assert card["closed_trades"] == 2
    assert card["net_pnl"] == 10.0


# 9. fx_mr_v4 entrant completeness (TASK-STR-FWD-008) -----------------------
def test_fx_mr_v4_in_default_entrants_with_oanda_practice_venue():
    # The FALLBACK set must be complete: if the registry import ever
    # fails on the server, fx_mr_v4 must still be a tracked entrant —
    # before this it existed only in the registry path, so the fallback
    # silently dropped it and its closes landed UNREGISTERED.
    defaults = fsc._normalise(fsc.DEFAULT_ENTRANTS)
    by_id = {e["id"]: e for e in defaults}
    assert "fx_mr_v4" in by_id
    fx = by_id["fx_mr_v4"]
    assert fx["venues"] == ["oanda_practice"]
    assert fx["strategies"] == ["strategy_fx_mr_v4", "fx_mr_v4"]
    assert fx["lane"] == "FORWARD"
    assert fx["sleeve"] is False


def test_registry_fx_mr_v4_venue_is_oanda_practice_not_binance():
    # The engine writes fills with venue "oanda_practice" (its
    # VENUE_NAME). The registry entry declares that spelling in
    # "venue" but (before the fix) had no "forward_venues", so the
    # resolver defaulted the entrant to binance_futures.
    registry = {
        "fx_mr_v4": {
            "status": "VALIDATED",
            "forward_protocol": True,
            "venue": "oanda_practice",
            "engine": "oanda_demo",
        },
    }
    entrants = fsc._normalise(fsc._entrants_from_registry(registry))
    assert len(entrants) == 1
    assert entrants[0]["id"] == "fx_mr_v4"
    assert entrants[0]["venues"] == ["oanda_practice"]
    assert entrants[0]["strategies"] == ["strategy_fx_mr_v4", "fx_mr_v4"]


def test_registry_forward_venues_field_still_wins_over_venue():
    registry = {
        "alpha": {
            "forward_protocol": True,
            "venue": "some_venue",
            "forward_venues": ["explicit_venue"],
        },
    }
    entrants = fsc._normalise(fsc._entrants_from_registry(registry))
    assert entrants[0]["venues"] == ["explicit_venue"]


def test_live_registry_resolves_fx_mr_v4_on_oanda_practice():
    # Against the real config_strategy registry (the production
    # resolution path): fx_mr_v4 must arrive with its real venue.
    entrants = fsc.load_entrants()
    by_id = {e["id"]: e for e in entrants}
    assert "fx_mr_v4" in by_id
    assert by_id["fx_mr_v4"]["venues"] == ["oanda_practice"]
