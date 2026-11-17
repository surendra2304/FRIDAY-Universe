"""Synthetic tests for the TASK-STR-RD-019 harness (xsrev.py).

Hand-built panels only — the declared run never touches these.
Covers: daily aggregation exactness + incomplete-day drop; the
Wilder ATR recursion against hand-computed values; the signal grid;
ranking order and the (score, symbol) tie-break; the volume-climax
gate (pass, fail, exact-median boundary, zero baseline, NO
substitution); the thin-rebalance rule; entry at the next bar's
open with signal-bar-ATR brackets; exit semantics (SL at level,
gap-through fills at the open, TP, stop-before-target, TIME at the
close of j+5, END_OF_DATA); the one-position skip rule; cost
arithmetic at 16 and 32 bps; the common-index abort; and
no-lookahead (truncation invariance + future-bar mutation
invariance for picks and trades).

Run: python3 -m pytest test_xsrev.py  (or plain: python3
test_xsrev.py — the __main__ runner executes every test_* function).
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import xsrev  # noqa: E402
from xsrev import Pick  # noqa: E402

DAY0 = datetime(2023, 10, 1, tzinfo=timezone.utc)


def dbar(i: int, o=100.0, h=101.0, l=99.0, c=100.0, v=1000.0) -> dict:
    return {"time": DAY0 + timedelta(days=i), "open": o, "high": h,
            "low": l, "close": c, "volume": v}


def flat_panel(symbols, n, price=100.0, vol=1000.0):
    return {s: [dbar(i, o=price, h=price + 1, l=price - 1, c=price, v=vol)
                for i in range(n)] for s in symbols}


SYMS8 = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]


# ------------------------------------------------------------ aggregation
def test_aggregation_exact_and_incomplete_day_dropped():
    bars = []
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for day, count in ((0, 96), (1, 95), (2, 96)):
        for k in range(count):
            bars.append({"time": t0 + timedelta(days=day, minutes=15 * k),
                         "open": 100.0, "high": 100.0 + k, "low": 99.0,
                         "close": 100.0 + 0.01 * k, "volume": 2.0})
    out = xsrev.aggregate_daily(bars)
    assert len(out) == 2, out
    d0 = out[0]
    assert d0["time"] == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert d0["open"] == 100.0 and d0["low"] == 99.0
    assert math.isclose(d0["high"], 195.0)
    assert math.isclose(d0["close"], 100.95)
    assert math.isclose(d0["volume"], 192.0)
    assert out[1]["time"] == datetime(2024, 1, 3, tzinfo=timezone.utc)


# ------------------------------------------------------------------- ATR
def test_atr_hand_computed():
    bars = [dbar(0, h=10.0, l=8.0, c=9.0),
            dbar(1, h=11.0, l=9.0, c=10.0),
            dbar(2, h=13.0, l=10.0, c=12.0)]
    a = xsrev.atr_series(bars)
    assert math.isclose(a[0], 2.0)                      # TR0 = h - l
    assert math.isclose(a[1], 2.0)                      # TR = 2
    assert math.isclose(a[2], 2.0 + (3.0 - 2.0) / 14.0)  # TR = 3, Wilder


# -------------------------------------------------------------- signal grid
def test_signal_grid():
    panel = flat_panel(SYMS8, 100)
    picks, stats = xsrev.generate_picks(panel)
    idx = {p.signal_index for p in picks}
    assert idx == {64, 69, 74, 79, 84, 89, 94}, idx
    assert stats["signal_bars"] == 7


# ---------------------------------------------------------------- ranking
def test_ranking_tails_and_tiebreak():
    panel = flat_panel(SYMS8, 80)
    j = 69
    closes = {"AAA": 90.0, "BBB": 92.0, "CCC": 95.0, "DDD": 95.0,
              "EEE": 105.0, "FFF": 105.0, "GGG": 108.0, "HHH": 110.0}
    for s, c in closes.items():
        panel[s][j] = dbar(j, o=c, h=c + 1, l=c - 1, c=c)
    picks, _ = xsrev.generate_picks(panel)
    at = {p.symbol: p for p in picks if p.signal_index == j}
    longs = {s for s, p in at.items() if p.side == "LONG"}
    shorts = {s for s, p in at.items() if p.side == "SHORT"}
    # CCC beats DDD for the last long slot on the symbol tie-break;
    # FFF beats EEE for the first short slot the same way.
    assert longs == {"AAA", "BBB", "CCC"}, longs
    assert shorts == {"FFF", "GGG", "HHH"}, shorts
    assert math.isclose(at["AAA"].score, -0.10)


# -------------------------------------------------------------------- gate
def _gate_panel():
    """8 symbols x 80 days; at j=69 AAA is the top long pick WITH a
    volume climax, BBB the second long pick WITHOUT one."""
    panel = flat_panel(SYMS8, 80)
    j = 69
    panel["AAA"][j] = dbar(j, o=90.0, h=91.0, l=89.0, c=90.0)
    panel["BBB"][j] = dbar(j, o=92.0, h=93.0, l=91.0, c=92.0)
    panel["CCC"][j] = dbar(j, o=95.0, h=96.0, l=94.0, c=95.0)
    for m in range(j - 4, j + 1):  # AAA ranking window: 5x volume
        b = dict(panel["AAA"][m])
        b["volume"] = 5000.0
        panel["AAA"][m] = b
    return panel, j


def test_gate_climax_pass_and_fail():
    panel, j = _gate_panel()
    picks, stats = xsrev.generate_picks(panel)
    at = {p.symbol: p for p in picks if p.signal_index == j}
    assert at["AAA"].climax is True
    assert math.isclose(at["AAA"].v_win, 25000.0)
    assert math.isclose(at["AAA"].v_base, 5000.0)
    assert at["BBB"].climax is False  # flat volume: v_win == v_base
    assert stats["picks_climax"] >= 1 and stats["picks_gated_out"] >= 1


def test_gate_no_substitution():
    panel, j = _gate_panel()
    # DDD (4th ranked, not a pick) gets a huge climax — it must NOT
    # be promoted into BBB's gated-out slot.
    for m in range(j - 4, j + 1):
        b = dict(panel["DDD"][m])
        b["volume"] = 99999.0
        panel["DDD"][m] = b
    trades, _ = xsrev.simulate(panel)
    entered = {t.symbol for t in trades
               if t.entry_time == panel["AAA"][j + 1]["time"]}
    assert entered == {"AAA"}, entered


def test_gate_baseline_zero_blocks():
    panel = flat_panel(SYMS8, 80)
    j = 69
    panel["AAA"][j] = dbar(j, o=90.0, h=91.0, l=89.0, c=90.0)
    for m in range(0, j - 4):  # zero baseline volume
        b = dict(panel["AAA"][m])
        b["volume"] = 0.0
        panel["AAA"][m] = b
    for m in range(j - 4, j + 1):
        b = dict(panel["AAA"][m])
        b["volume"] = 5000.0
        panel["AAA"][m] = b
    picks, _ = xsrev.generate_picks(panel)
    at = {p.symbol: p for p in picks if p.signal_index == j}
    assert at["AAA"].v_base == 0.0 and at["AAA"].climax is False


def test_gate_median_exact_boundary():
    panel = flat_panel(SYMS8, 80)
    j = 69
    # Baseline windows (bars 5..64) sums 100,200,...,1200 -> median 650.
    for s, win_vol, mult in (("AAA", 195.0, None), ("HHH", 194.98, None)):
        for w in range(12):
            for m in range(5 + 5 * w, 10 + 5 * w):
                b = dict(panel[s][m])
                b["volume"] = 20.0 * (w + 1)
                panel[s][m] = b
        for m in range(j - 4, j + 1):
            b = dict(panel[s][m])
            b["volume"] = win_vol
            panel[s][m] = b
    panel["AAA"][j] = dbar(j, o=90.0, h=91.0, l=89.0, c=90.0, v=195.0)
    panel["HHH"][j] = dbar(j, o=110.0, h=111.0, l=109.0, c=110.0, v=194.98)
    picks, _ = xsrev.generate_picks(panel)
    at = {p.symbol: p for p in picks if p.signal_index == j}
    assert math.isclose(at["AAA"].v_base, 650.0)
    assert math.isclose(at["AAA"].v_win, 975.0)  # exactly 1.5x -> passes
    assert at["AAA"].climax is True
    assert at["HHH"].climax is False             # 974.9 < 975 -> fails


def test_thin_rebalance_no_picks():
    panel = flat_panel(SYMS8, 90)
    for s in ("AAA", "BBB", "CCC"):  # NaN volume inside the warmup
        b = dict(panel[s][10])
        b["volume"] = float("nan")
        panel[s][10] = b
    picks, stats = xsrev.generate_picks(panel)
    assert all(p.signal_index not in (64, 69, 74) for p in picks)
    assert any(p.signal_index == 79 for p in picks)
    assert stats["rebalances_thin"] >= 3


def test_index_mismatch_aborts():
    panel = flat_panel(SYMS8, 80)
    panel["HHH"] = panel["HHH"][:-1] + [
        dbar(79, o=100.0, h=101.0, l=99.0, c=100.0)]
    panel["HHH"][79]["time"] = DAY0 + timedelta(days=500)
    try:
        xsrev.generate_picks(panel)
    except ValueError:
        return
    raise AssertionError("mismatched index did not abort")


# ------------------------------------------------------- execution semantics
def _pick(j, side="LONG", atr=2.0, sym="AAA"):
    return Pick(sym, j, DAY0 + timedelta(days=j), side, 0.0, atr,
                0.0, 0.0, True)


def test_entry_next_bar_open_levels_and_time_exit():
    bars = [dbar(i) for i in range(12)]
    bars[3] = dbar(3, o=100.0, h=101.0, l=99.0, c=100.0)
    bars[7] = dbar(7, o=100.0, h=101.0, l=99.0, c=103.0)
    trades, st = xsrev.simulate_symbol(bars, "AAA", [_pick(2)])
    assert st["entered"] == 1 and len(trades) == 1
    t = trades[0]
    assert t.entry_price == 100.0 and t.entry_time == bars[3]["time"]
    assert t.stop == 96.0 and t.target == 108.0  # signal-bar ATR = 2.0
    assert t.exit_reason == "TIME" and t.exit_price == 103.0
    assert t.exit_time == bars[7]["time"]        # close of j+5


def test_exit_stop_loss_at_level():
    bars = [dbar(i) for i in range(12)]
    bars[4] = dbar(4, o=100.0, h=101.0, l=95.5, c=99.0)
    trades, _ = xsrev.simulate_symbol(bars, "AAA", [_pick(2)])
    assert trades[0].exit_reason == "SL" and trades[0].exit_price == 96.0
    assert trades[0].exit_time == bars[4]["time"]


def test_exit_gap_through_stop_fills_at_open():
    bars = [dbar(i) for i in range(12)]
    bars[4] = dbar(4, o=94.0, h=95.0, l=93.0, c=94.0)
    trades, _ = xsrev.simulate_symbol(bars, "AAA", [_pick(2)])
    assert trades[0].exit_reason == "SL" and trades[0].exit_price == 94.0


def test_exit_take_profit_at_level():
    bars = [dbar(i) for i in range(12)]
    bars[4] = dbar(4, o=100.0, h=109.0, l=99.0, c=105.0)
    trades, _ = xsrev.simulate_symbol(bars, "AAA", [_pick(2)])
    assert trades[0].exit_reason == "TP" and trades[0].exit_price == 108.0


def test_exit_stop_before_target_same_bar():
    bars = [dbar(i) for i in range(12)]
    bars[4] = dbar(4, o=100.0, h=110.0, l=95.0, c=100.0)
    trades, _ = xsrev.simulate_symbol(bars, "AAA", [_pick(2)])
    assert trades[0].exit_reason == "SL" and trades[0].exit_price == 96.0


def test_exit_end_of_data():
    bars = [dbar(i) for i in range(10)]
    trades, _ = xsrev.simulate_symbol(bars, "AAA", [_pick(7)])
    t = trades[0]  # entry bar 8; j+5 = 12 beyond data (n = 10)
    assert t.exit_reason == "END_OF_DATA"
    assert t.exit_time == bars[9]["time"] and t.exit_price == 100.0


def test_short_brackets_mirrored():
    bars = [dbar(i) for i in range(12)]
    bars[4] = dbar(4, o=100.0, h=105.0, l=99.0, c=101.0)
    trades, _ = xsrev.simulate_symbol(bars, "AAA", [_pick(2, side="SHORT")])
    t = trades[0]
    assert t.stop == 104.0 and t.target == 92.0
    assert t.exit_reason == "SL" and t.exit_price == 104.0


def test_one_position_skip_rule():
    bars = [dbar(i) for i in range(20)]
    picks = [_pick(2), _pick(4), _pick(8)]  # #2's entry (bar 5) is
    trades, st = xsrev.simulate_symbol(bars, "AAA", picks)  # inside
    assert st["entered"] == 2 and st["skipped_open"] == 1   # #1's window
    assert len(trades) == 2


# -------------------------------------------------------------------- costs
def test_cost_arithmetic_both_levels():
    r = xsrev.COSTS.per_side_rate
    assert math.isclose(r, 0.0008)
    exp_long = (110.0 * (1 - r) - 100.0 * (1 + r)) / (100.0 * (1 + r))
    assert math.isclose(xsrev.net_return("LONG", 100.0, 110.0, xsrev.COSTS),
                        exp_long, rel_tol=1e-12)
    exp_short = (100.0 * (1 - r) - 90.0 * (1 + r)) / (100.0 * (1 - r))
    assert math.isclose(xsrev.net_return("SHORT", 100.0, 90.0, xsrev.COSTS),
                        exp_short, rel_tol=1e-12)
    assert xsrev.COSTS.describe()["round_trip_bps"] == 16.0
    assert xsrev.COSTS_2X.describe()["round_trip_bps"] == 32.0
    assert xsrev.net_return("LONG", 100.0, 110.0, xsrev.COSTS_2X) < \
        xsrev.net_return("LONG", 100.0, 110.0, xsrev.COSTS)


# -------------------------------------------------------------- no lookahead
def _varied_panel(n=120):
    import random
    rng = random.Random(1907)
    panel = {}
    for s in SYMS8:
        price = 100.0
        bars = []
        for i in range(n):
            price *= 1.0 + rng.uniform(-0.03, 0.03)
            vol = 1000.0 * (1.0 + (i % 7)) * rng.uniform(0.5, 2.0)
            bars.append(dbar(i, o=price, h=price * 1.01, l=price * 0.99,
                             c=price, v=vol))
        panel[s] = bars
    return panel


def test_no_lookahead_truncation_and_mutation():
    full = _varied_panel(120)
    picks_full, _ = xsrev.generate_picks(full)
    trunc = {s: b[:90] for s, b in full.items()}
    picks_trunc, _ = xsrev.generate_picks(trunc)
    expect = [p for p in picks_full if p.signal_index <= 84]
    assert [p.as_dict() for p in picks_trunc] == \
        [p.as_dict() for p in expect], "truncation changed earlier picks"
    mutant = {s: [dict(b) for b in bars] for s, bars in full.items()}
    for s in mutant:
        for i in range(100, 120):
            mutant[s][i]["close"] *= 3.0
            mutant[s][i]["volume"] *= 1000.0
    picks_mut, _ = xsrev.generate_picks(mutant)
    early = [p.as_dict() for p in picks_full if p.signal_index <= 99]
    early_mut = [p.as_dict() for p in picks_mut if p.signal_index <= 99]
    assert early == early_mut, "future bars changed earlier picks"
    trades_full, _ = xsrev.simulate(full)
    trades_trunc, _ = xsrev.simulate(trunc)
    key = lambda t: (t.symbol, str(t.entry_time), t.exit_price,
                     t.exit_reason)
    assert {key(t) for t in trades_trunc} <= {key(t) for t in trades_full}


if __name__ == "__main__":
    tests = [(k, v) for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)
