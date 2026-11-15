#!/usr/bin/env python3
"""TASK-STR-RD-017 — tests for the funding-carry paper simulator.

Run: python3 -m pytest test_carry_paper_sim.py -q
     (or plain: python3 test_carry_paper_sim.py)

Covers the declaration's sanity checks:
  T3 frozen-price zero-cost identity (funding sum == PnL),
  funding sign convention (short perp receives positive rates),
  entry-cost math vs the RD-009 model (0.19% of one-leg notional),
  ledger hash-chain verification,
  symbol-drop trigger on a fabricated funding flip,
  regime-turn confirmation on a fabricated print series.
All bundles are synthetic; no network is touched.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import carry_paper_sim as sim  # noqa: E402

T0 = 1794600000000  # a fixed epoch ms (2026-11-13T02:40:00Z-ish)


def bundle(ts, prices, prints=None):
    syms = {}
    for sym in sim.SYMBOLS:
        spot, mark = prices.get(sym, (100.0, 100.0))
        syms[sym] = {"spot": spot, "mark": mark,
                     "last_funding_rate": 0.0001,
                     "next_funding_ms": ts + 8 * 3600 * 1000,
                     "prints": (prints or {}).get(sym, [])}
    return {"fetched_at_ms": ts, "symbols": syms, "errors": {}}


class FakeTransport:
    def __init__(self, bundles):
        self.bundles = list(bundles)

    def __call__(self, transport, since_map, state_dir):
        return self.bundles.pop(0), "fake"


def run_polls(state_dir, bundles):
    fake = FakeTransport(bundles)
    orig = sim.fetch_bundle
    sim.fetch_bundle = fake
    try:
        results = [sim.poll(state_dir, "fake") for _ in bundles]
    finally:
        sim.fetch_bundle = orig
    return results


def test_t3_frozen_price_funding_identity():
    """Frozen prices, one print: book PnL == funding cash - entry cost;
    with entry cost zeroed the identity is exact (RD-009 S1 analogue)."""
    with tempfile.TemporaryDirectory() as td:
        b1 = bundle(T0, {})
        print1 = {"funding_time_ms": T0 + 1000, "rate": 0.001,
                  "mark_at_print": 100.0}
        b2 = bundle(T0 + 2000, {}, prints={"BTCUSDT": [print1]})
        res = run_polls(td, [b1, b2])
        assert res[0]["status"] == "started", res
        rep = sim.report(td)
        btc = rep["positions"]["BTCUSDT"]
        q = sim.NOTIONAL / 100.0
        assert abs(btc["funding_cash"] - q * 100.0 * 0.001) < 1e-9
        last = rep["last_mark"]
        # frozen prices -> basis 0 -> net == funding - entry costs (30)
        expect_net = q * 100.0 * 0.001 - 30 * sim.entry_cost()
        assert abs(last["net_1x"] - expect_net) < 1e-6, last
        # T2 identity holds per symbol
        for sym, d in rep["T2_decomposition_identity"].items():
            assert abs(d["diff"]) < 1e-6, (sym, d)


def test_funding_sign_short_receives_positive():
    with tempfile.TemporaryDirectory() as td:
        b1 = bundle(T0, {})
        neg = {"funding_time_ms": T0 + 1000, "rate": -0.002,
               "mark_at_print": 100.0}
        b2 = bundle(T0 + 2000, {}, prints={"ETHUSDT": [neg]})
        run_polls(td, [b1, b2])
        rep = sim.report(td)
        q = sim.NOTIONAL / 100.0
        assert abs(rep["positions"]["ETHUSDT"]["funding_cash"]
                   - (-q * 100.0 * 0.002)) < 1e-9


def test_entry_cost_math():
    assert abs(sim.entry_cost()
               - sim.NOTIONAL * 0.0019) < 1e-12  # 0.19% of notional


def test_ledger_chain_verifies_and_replay_matches():
    with tempfile.TemporaryDirectory() as td:
        run_polls(td, [bundle(T0, {}),
                       bundle(T0 + 3600_000, {"BTCUSDT": (101.0, 101.0)})])
        led = sim.Ledger(td)  # raises on any hash/chain mismatch
        book = sim.Book.from_ledger(led)
        assert book.started and not book.ended
        assert book.pos["BTCUSDT"].status == "open"


def test_symbol_drop_on_flip():
    """A symbol paying > 5% of notional in funding within 30d drops."""
    with tempfile.TemporaryDirectory() as td:
        b1 = bundle(T0, {})
        # q = 10 units at price 100; a -6% print costs 60 > 50 (5%).
        flip = {"funding_time_ms": T0 + 1000, "rate": -0.06,
                "mark_at_print": 100.0}
        b2 = bundle(T0 + 2000, {}, prints={"SOLUSDT": [flip]})
        res = run_polls(td, [b1, b2])
        rep = sim.report(td)
        assert rep["positions"]["SOLUSDT"]["status"] == "closed"
        assert any(k["type"] == "SYMBOL_DROP" for k in rep["kill_trips"])


def test_no_drop_on_small_flip():
    with tempfile.TemporaryDirectory() as td:
        b1 = bundle(T0, {})
        small = {"funding_time_ms": T0 + 1000, "rate": -0.01,
                 "mark_at_print": 100.0}
        b2 = bundle(T0 + 2000, {}, prints={"SOLUSDT": [small]})
        run_polls(td, [b1, b2])
        rep = sim.report(td)
        assert rep["positions"]["SOLUSDT"]["status"] == "open"


def _prints_series(rates_by_day):
    """Fabricate 8h prints for BTC from a per-day rate list."""
    prints = []
    for day, rate in enumerate(rates_by_day):
        for k in range(3):
            prints.append({"funding_time_ms": T0 + day * 86400_000
                           + k * 8 * 3600_000 + 1000,
                           "rate": rate, "mark_at_print": 100.0})
    return prints


def test_regime_turn_confirmation():
    """+ rates for 20 days, then - rates: after the negative sign
    persists 14 daily snapshots vs the sign 14 snapshots earlier,
    a REGIME_TURN is confirmed."""
    with tempfile.TemporaryDirectory() as td:
        rates = [0.001] * 20 + [-0.001] * 40
        prints = _prints_series(rates)
        bundles = [bundle(T0, {})]
        # one poll per day; hand each day's prints with that day's poll
        for day in range(60):
            day_prints = [p for p in prints
                          if T0 + day * 86400_000 <= p["funding_time_ms"]
                          < T0 + (day + 1) * 86400_000]
            bundles.append(bundle(T0 + (day + 1) * 86400_000 - 1000, {},
                                  prints={"BTCUSDT": day_prints}))
        run_polls(td, bundles)
        led = sim.Ledger(td)
        turns = [r for r in led.rows if r["type"] == "REGIME_TURN"]
        assert turns, "expected a confirmed regime turn"
        assert turns[0]["symbol"] == "BTCUSDT"


def test_first_poll_since_is_now_not_zero():
    """Regression: the first poll must not request funding history from
    epoch (since=0 pulled 100 prints/symbol + a kline each and timed
    out the live transport on 2026-11-15; ledger seq 1 ERROR)."""
    captured = {}

    class CapFake:
        def __call__(self, transport, since_map, state_dir):
            captured.update(since_map)
            return bundle(T0, {}), "fake"

    orig = sim.fetch_bundle
    sim.fetch_bundle = CapFake()
    try:
        with tempfile.TemporaryDirectory() as td:
            sim.poll(td, "fake")
    finally:
        sim.fetch_bundle = orig
    assert captured, "no since map captured"
    assert all(v > 1_700_000_000_000 for v in captured.values()), captured


def test_regime_flip_back_not_confirmed():
    """A flip that reverses within days must NOT confirm a turn."""
    with tempfile.TemporaryDirectory() as td:
        rates = [0.001] * 30 + [-0.001] * 5 + [0.001] * 25
        prints = _prints_series(rates)
        bundles = [bundle(T0, {})]
        for day in range(60):
            day_prints = [p for p in prints
                          if T0 + day * 86400_000 <= p["funding_time_ms"]
                          < T0 + (day + 1) * 86400_000]
            bundles.append(bundle(T0 + (day + 1) * 86400_000 - 1000, {},
                                  prints={"BTCUSDT": day_prints}))
        run_polls(td, bundles)
        led = sim.Ledger(td)
        turns = [r for r in led.rows if r["type"] == "REGIME_TURN"]
        assert not turns, f"unconfirmed flip produced a turn: {turns}"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc!r}")
    sys.exit(1 if failed else 0)
