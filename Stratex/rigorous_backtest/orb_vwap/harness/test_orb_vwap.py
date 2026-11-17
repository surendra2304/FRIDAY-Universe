#!/usr/bin/env python3
"""Synthetic tests for the ORB/VWAP harness (TASK-STR-DISC-004).

Every test runs on hand-built synthetic bars — no panel, no network,
no backtest. Coverage: opening-range construction on session
boundaries (first-two-bars only, missing bar, zero-height), VWAP
computation (hand-computed value, through-candidate inclusivity,
zero-volume undefined), the VWAP veto (long + short, veto consumes
the session), candidate-on-final-bar rejection, flat-by-close on
full and early-close sessions, no look-ahead (entry bar extremes
ignored; later bars never change the entry), stop-before-target,
gap fills at the open, level arithmetic (stop = opposite end,
target = 2.0R), first-close-beyond-only, one trade per
symbol-session + multi-symbol independence, cost arithmetic
(16/32 bps), breadth-gate arithmetic, temporal-holdout arithmetic,
the exact "insufficient OOS trades" verdict, DST session grouping
by ET date, and the declaration-hash pin. Also: the pull tool's
Alpaca pagination, on a mocked two-page response (no network) —
the continuation cursor must go out as the `page_token` request
parameter, not the response field name `next_page_token`.

Run: python3 test_orb_vwap.py   (also pytest-compatible)
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nyse_calendar  # noqa: E402
import orb_vwap  # noqa: E402
import pull_orb_panel  # noqa: E402
from orb_vwap import (session_trade, session_vwap_through,  # noqa: E402
                      generate_trades, judge, net_return,
                      breadth_check, temporal_holdout)

ET = ZoneInfo("America/New_York")
DAY = date(2026, 8, 3)  # a Monday, EDT


def _bar(day, start, o, h, l, c, v=1000, symbol="TEST"):
    return {"symbol": symbol, "start_et": start, "date_et": day,
            "open": o, "high": h, "low": l, "close": c, "volume": v}


def make_session(day, specs, symbol="TEST"):
    """specs: (o, h, l, c) or (o, h, l, c, v), from 09:30 ET, 15m steps."""
    bars = []
    t = datetime.combine(day, time(9, 30), tzinfo=ET)
    for spec in specs:
        o, h, l, c = spec[:4]
        v = spec[4] if len(spec) > 4 else 1000
        bars.append(_bar(day, t, o, h, l, c, v, symbol))
        t += timedelta(minutes=15)
    return bars


def pad(bars, price, n_total=26, vol=1000):
    t = bars[-1]["start_et"] + timedelta(minutes=15)
    while len(bars) < n_total:
        bars.append(_bar(bars[-1]["date_et"], t, price, price, price,
                         price, vol, bars[-1]["symbol"]))
        t += timedelta(minutes=15)
    return bars


# Base long setup: range 99–102 (bars 1–2), candidate bar 3 closes
# 102.5 with VWAP 101.0556 -> entry 102.5, stop 99, R 3.5, target 109.5.
BASE = [(100, 101, 99, 100.5), (100.5, 102, 100, 101),
        (101.5, 103, 100.5, 102.5)]


def test_range_uses_first_two_bars_only():
    sess = make_session(DAY, BASE + [(104, 120, 103, 105)])
    sess = pad(sess, 104)
    t = session_trade(sess, "TEST")
    assert t is not None
    assert t["range_high"] == 102 and t["range_low"] == 99, t
    assert t["stop_price"] == 99 and t["entry_price"] == 102.5


def test_missing_opening_bar_no_trade():
    # Session starts at 09:45: the declared first two candles
    # (09:30 + 09:45) are not both present -> no trade, even though
    # a later close breaks the would-be range.
    bars = []
    t = datetime.combine(DAY, time(9, 45), tzinfo=ET)
    for spec in [(100.5, 102, 100, 101), (101.5, 103, 100.5, 102.5)]:
        bars.append(_bar(DAY, t, *spec))
        t += timedelta(minutes=15)
    bars = pad(bars, 104)
    assert len(bars) >= 4 and bars[0]["start_et"].time() == time(9, 45)
    assert session_trade(bars, "TEST") is None


def test_zero_height_range_no_trade():
    sess = make_session(DAY, [(100, 100, 100, 100), (100, 100, 100, 100),
                              (100, 101, 100, 100.8)])
    sess = pad(sess, 100.8)
    assert session_trade(sess, "TEST") is None


def test_vwap_hand_computed_and_inclusive():
    sess = make_session(DAY, [(100, 101, 99, 100.5, 100),
                              (100.5, 102, 100, 101, 300),
                              (101.5, 103, 100.5, 102.5, 200)])
    sess = pad(sess, 104)
    expected = ((101 + 99 + 100.5) / 3 * 100 + (102 + 100 + 101) / 3 * 300
                + (103 + 100.5 + 102.5) / 3 * 200) / 600
    assert abs(session_vwap_through(sess, 2) - expected) < 1e-9
    # Excluding the candidate bar gives a materially different VWAP:
    assert abs(session_vwap_through(sess, 1) - expected) > 0.1
    t = session_trade(sess, "TEST")
    assert t is not None and abs(t["vwap_at_entry"] - expected) < 1e-9


def test_vwap_veto_long_and_veto_consumes_session():
    # Candidate bar's own TP (104.17) far above its close, on huge
    # volume: VWAP through the candidate (inclusive) = ~104.10 > close
    # 102.5 -> veto. Through bar 2 only it would be ~100.58 -> the
    # inclusivity is what vetoes.
    sess = make_session(DAY, [(100, 101, 99, 100.5, 1000),
                              (100.5, 102, 100, 101, 1000),
                              (102, 110, 100, 102.5, 100000),
                              (103, 103.6, 102.9, 103.5, 10_000_000)])
    assert session_vwap_through(sess, 1) < 102.5
    assert session_vwap_through(sess, 2) > 102.5
    # Bar 4 would pass the filter if scanning continued (VWAP ~103.34
    # < its close 103.5) — the veto must still consume the session.
    assert session_vwap_through(sess, 3) < 103.5
    sess = pad(sess, 100.8)
    assert session_trade(sess, "TEST") is None


def test_short_entry_and_levels():
    sess = make_session(DAY, [(100, 101, 98.5, 99), (99, 100.5, 98, 98.6),
                              (98.4, 99, 97, 97.5)])
    sess = pad(sess, 96)
    t = session_trade(sess, "TEST")
    assert t is not None and t["side"] == "SHORT"
    assert t["entry_price"] == 97.5 and t["stop_price"] == 101
    assert abs(t["risk_r"] - 3.5) < 1e-12
    assert abs(t["target_price"] - 90.5) < 1e-12


def test_short_vwap_veto():
    sess = make_session(DAY, [(100, 101, 98.5, 99, 1000),
                              (99, 100.5, 98, 98.6, 1000),
                              (98, 100, 90, 97.5, 100000)])
    sess = pad(sess, 96)
    # VWAP ~95.90 < close 97.5: a short needs close < VWAP -> vetoed.
    assert session_trade(sess, "TEST") is None


def test_entry_on_final_bar_rejected():
    inside = (100.5, 101.5, 99.5, 100.8)
    specs = BASE[:2] + [inside] * 23 + [(102.5, 103.5, 102, 103)]
    sess = make_session(DAY, specs)
    assert len(sess) == 26
    assert session_trade(sess, "TEST") is None


def test_entry_on_penultimate_bar_allowed():
    inside = (100.5, 101.5, 99.5, 100.8)
    specs = BASE[:2] + [inside] * 22 + [BASE[2], (104, 104, 104, 104)]
    sess = make_session(DAY, specs)
    assert len(sess) == 26
    t = session_trade(sess, "TEST")
    assert t is not None and t["exit_reason"] == "SESSION_CLOSE"
    assert t["exit_price"] == 104


def test_flat_by_close_full_session():
    sess = pad(make_session(DAY, BASE), 104)
    t = session_trade(sess, "TEST")
    assert t is not None and t["exit_reason"] == "SESSION_CLOSE"
    assert t["exit_price"] == 104
    assert t["exit_time"] == "2026-08-03T19:45:00+00:00"  # 15:45 ET start


def test_flat_by_close_early_close_session():
    # Session shape follows nyse_calendar (the declared convention).
    day = date(2025, 12, 24)
    starts = nyse_calendar.expected_bar_starts(day)
    specs = BASE + [(104, 104, 104, 104)] * (len(starts) - 3)
    sess = [_bar(day, datetime.combine(day, s, tzinfo=ET), *spec[:4])
            for s, spec in zip(starts, specs)]
    t = session_trade(sess, "TEST")
    assert t is not None and t["exit_reason"] == "SESSION_CLOSE"
    assert t["exit_price"] == 104
    # Final bar start 11:45 ET (EST, UTC-5) under the calendar's
    # declared early-close convention -> 16:45 UTC.
    assert starts[-1] == time(11, 45)
    assert t["exit_time"] == "2025-12-24T16:45:00+00:00"


def test_no_lookahead_entry_bar_extremes_ignored():
    # Candidate bar dips to 98 (below the 99 stop) but closes 102.5:
    # the entry bar's own extremes must never trigger an exit.
    sess = make_session(DAY, [BASE[0], BASE[1], (101.5, 103, 98, 102.5)])
    sess = pad(sess, 104)
    t = session_trade(sess, "TEST")
    assert t is not None and t["exit_reason"] == "SESSION_CLOSE"


def test_no_lookahead_future_bars_do_not_change_entry():
    calm = pad(make_session(DAY, BASE), 104)
    wild = make_session(DAY, BASE + [(105, 115, 104, 112)])
    wild = pad(wild, 104)
    t1, t2 = session_trade(calm, "TEST"), session_trade(wild, "TEST")
    for k in ("entry_price", "vwap_at_entry", "stop_price",
              "target_price", "range_high", "range_low", "entry_time"):
        assert t1[k] == t2[k], k
    assert t1["exit_reason"] == "SESSION_CLOSE"
    assert t2["exit_reason"] == "TP"


def test_stop_before_target_same_bar():
    sess = make_session(DAY, BASE + [(104, 110, 98.5, 105)])
    sess = pad(sess, 104)
    t = session_trade(sess, "TEST")
    assert t["exit_reason"] == "SL" and t["exit_price"] == 99


def test_gap_through_stop_fills_at_open():
    sess = make_session(DAY, BASE + [(98.0, 99.5, 97.5, 99.0)])
    sess = pad(sess, 104)
    t = session_trade(sess, "TEST")
    assert t["exit_reason"] == "SL" and t["exit_price"] == 98.0


def test_gap_through_target_fills_at_open():
    sess = make_session(DAY, BASE + [(110.5, 111, 109.8, 110.8)])
    sess = pad(sess, 104)
    t = session_trade(sess, "TEST")
    assert t["exit_reason"] == "TP" and t["exit_price"] == 110.5


def test_first_close_beyond_only():
    sess = make_session(DAY, [BASE[0], BASE[1],
                              (100.8, 101.8, 100.2, 101.0),
                              (100.9, 101.6, 100.4, 100.8),
                              BASE[2]])
    sess = pad(sess, 104)
    t = session_trade(sess, "TEST")
    assert t is not None
    assert t["entry_time"] == "2026-08-03T14:30:00+00:00"  # 10:30 ET bar


def test_one_trade_per_symbol_session_multi_symbol():
    aapl_d1 = pad(make_session(DAY, BASE + [(103, 104, 102.5, 103.5)],
                               symbol="AAPL"), 104)
    aapl_d2 = pad(make_session(date(2026, 8, 4), BASE, symbol="AAPL"), 104)
    msft_veto = pad(make_session(DAY, [(100, 101, 99, 100.5, 1000),
                                       (100.5, 102, 100, 101, 1000),
                                       (102, 110, 100, 102.5, 100000)],
                                 symbol="MSFT"), 100.8)
    tsla_d1 = pad(make_session(DAY, BASE, symbol="TSLA"), 104)
    bars = {"AAPL": aapl_d1 + aapl_d2, "MSFT": msft_veto, "TSLA": tsla_d1}
    trades = generate_trades(bars)
    assert len(trades) == 3, trades
    counts = {}
    for t in trades:
        counts[t["symbol"]] = counts.get(t["symbol"], 0) + 1
    assert counts == {"AAPL": 2, "TSLA": 1}, counts


def test_cost_arithmetic():
    r = 0.0008  # (5 + 3) bps per side at 1x
    exp_long = (101 * (1 - r) - 100 * (1 + r)) / (100 * (1 + r))
    assert abs(net_return("LONG", 100, 101, 1.0) - exp_long) < 1e-12
    r2 = 0.0016  # 2x shadow
    exp_2x = (101 * (1 - r2) - 100 * (1 + r2)) / (100 * (1 + r2))
    assert abs(net_return("LONG", 100, 101, 2.0) - exp_2x) < 1e-12
    exp_short = (100 * (1 - r) - 99 * (1 + r)) / (100 * (1 - r))
    assert abs(net_return("SHORT", 100, 99, 1.0) - exp_short) < 1e-12
    flat = net_return("LONG", 100, 100, 1.0)  # round trip ~ -16 bps
    assert -0.0017 < flat < -0.0015, flat


def test_zero_volume_vwap_undefined():
    sess = make_session(DAY, [(100, 101, 99, 100.5, 0),
                              (100.5, 102, 100, 101, 0),
                              (101.5, 103, 100.5, 102.5, 0)])
    sess = pad(sess, 104, vol=0)
    assert session_vwap_through(sess, 2) is None
    assert session_trade(sess, "TEST") is None


def test_breadth_gate_arithmetic():
    concentrated = [{"symbol": "AAPL", "net_return": 0.10},
                    {"symbol": "MSFT", "net_return": 0.05},
                    {"symbol": "TSLA", "net_return": -0.02}]
    b = breadth_check(concentrated)
    assert b["passes"] is False
    assert abs(b["max_symbol_profit_share"] - 0.10 / 0.15) < 1e-12
    spread = [{"symbol": s, "net_return": 0.06}
              for s in ("AAPL", "MSFT", "TSLA")]
    assert breadth_check(spread)["passes"] is True


def _fake_trades(day_iso, n, ret):
    return [{"entry_time": day_iso, "net_return": ret} for _ in range(n)]


def test_temporal_holdout_arithmetic():
    d = (_fake_trades("2024-08-01T14:00:00+00:00", 5, 0.01)
         + _fake_trades("2025-02-03T14:00:00+00:00", 5, 0.01)
         + _fake_trades("2025-08-01T14:00:00+00:00", 5, 0.01)
         + _fake_trades("2026-02-02T14:00:00+00:00", 5, 0.01))
    h = _fake_trades("2026-08-03T14:00:00+00:00", 25, 0.004)
    out = temporal_holdout(d + h)
    assert out["passes"] is True, out["checks"]
    bad_h = temporal_holdout(
        d + _fake_trades("2026-08-03T14:00:00+00:00", 25, -0.004))
    assert bad_h["checks"]["H2_holdout_expectancy_gt_0"] is False
    small_h = temporal_holdout(
        d + _fake_trades("2026-08-03T14:00:00+00:00", 10, 0.004))
    assert small_h["checks"]["H1_holdout_size_gte_20"] is False
    conc = (_fake_trades("2024-08-01T14:00:00+00:00", 5, 0.10)
            + _fake_trades("2025-02-03T14:00:00+00:00", 5, 0.001)
            + _fake_trades("2025-08-01T14:00:00+00:00", 5, 0.001)
            + _fake_trades("2026-02-02T14:00:00+00:00", 5, 0.001) + h)
    out4 = temporal_holdout(conc)
    assert out4["checks"]["H4_max_fold_profit_share_lte_0.80"] is False


def test_insufficient_oos_trades_verdict():
    bars = {"AAPL": pad(make_session(DAY, BASE, symbol="AAPL"), 104)}
    res = judge(bars, entering_trials=3893, label="synthetic")
    assert res["verdict"] == "insufficient OOS trades", res["verdict"]
    assert res["trial_accounting"]["final_N"] == 3894
    assert abs(res["trial_accounting"]["bonferroni_alpha"]
               - 0.05 / 3894) < 1e-15
    assert res["bar_checks"]["min_oos_trades_200"] is False


def test_dst_session_grouping():
    est = _bar(date(2026, 3, 6),
               datetime.combine(date(2026, 3, 6), time(9, 30), tzinfo=ET),
               100, 101, 99, 100.5)
    edt = _bar(date(2026, 3, 9),
               datetime.combine(date(2026, 3, 9), time(9, 30), tzinfo=ET),
               100, 101, 99, 100.5)
    assert est["start_et"].utcoffset() == timedelta(hours=-5)
    assert edt["start_et"].utcoffset() == timedelta(hours=-4)
    sessions = orb_vwap.group_sessions([est, edt])
    assert set(sessions) == {date(2026, 3, 6), date(2026, 3, 9)}


def test_declaration_hash_pinned():
    decl = Path(__file__).resolve().parent.parent / "orb_vwap_declaration.json"
    digest = hashlib.sha256(decl.read_bytes()).hexdigest()
    assert digest == orb_vwap.DECLARATION_SHA256, digest


def test_pull_pagination_sends_cursor_as_page_token():
    # Regression test for the DISC-004 harness transport erratum
    # (proven live 2026-11-17, runprep-orb/PROOF_PULL.md): fetch_bars
    # sent the continuation cursor back under the RESPONSE field name
    # "next_page_token". Alpaca's REQUEST parameter is "page_token";
    # as shipped, page 2 was rejected with HTTP 400
    # "unexpected query parameter(s): next_page_token" and the tool
    # exited 4 — no multi-page pull could ever complete. The response
    # side (reading payload["next_page_token"]) is correct and stays.
    page1 = {"bars": [{"t": "2026-10-01T13:30:00Z", "o": 1.0, "h": 1.0,
                       "l": 1.0, "c": 1.0, "v": 10}],
             "next_page_token": "CURSOR-XYZ"}
    page2 = {"bars": [{"t": "2026-10-01T13:45:00Z", "o": 2.0, "h": 2.0,
                       "l": 2.0, "c": 2.0, "v": 20}],
             "next_page_token": None}
    seen_urls = []

    class _Resp:
        def __init__(self, payload):
            self._buf = io.BytesIO(json.dumps(payload).encode())

        def read(self, *args):
            return self._buf.read(*args)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=None):
        seen_urls.append(req.full_url)
        return _Resp(page1 if len(seen_urls) == 1 else page2)

    real_urlopen = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        bars = pull_orb_panel.fetch_bars(
            "AAPL", "2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z",
            "kid", "sec")
    finally:
        urllib.request.urlopen = real_urlopen

    # Pagination completed: exactly two requests, both pages' bars.
    assert len(seen_urls) == 2, seen_urls
    assert [b["c"] for b in bars] == [1.0, 2.0], bars
    # Page 2 must carry the cursor as Alpaca's page_token request
    # parameter — and must NOT carry it as next_page_token.
    query = urllib.parse.parse_qs(urllib.parse.urlparse(seen_urls[1]).query)
    assert query.get("page_token") == ["CURSOR-XYZ"], query
    assert "next_page_token" not in query, query


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001 — report and continue
            failures += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} synthetic tests passed")
    sys.exit(1 if failures else 0)
