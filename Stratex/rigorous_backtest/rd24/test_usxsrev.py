"""Synthetic tests for the us_xs_reversal harness (TASK-STR-RD-024).

Mechanics only, on fabricated data — per the declaration's run
procedure, harness development/debugging uses synthetic bars or the
pre-OOS segment, never the holdout. No real panel is touched.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usxsrev as U  # noqa: E402

RUNNER = Path(__file__).resolve().parent / "run_usxsrev.py"


def sessions(n, start="2023-01-02"):
    return pd.bdate_range(start, periods=n, tz="UTC")


def frame_from_closes(idx, closes, spread=0.001):
    closes = np.asarray(closes, dtype=float)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    highs = np.maximum(opens, closes) * (1 + spread)
    lows = np.minimum(opens, closes) * (1 - spread)
    return pd.DataFrame({"open": opens, "high": highs, "low": lows,
                         "close": closes, "volume": 5_000_000.0},
                        index=idx)


def flat_frame(idx, price=100.0):
    n = len(idx)
    return pd.DataFrame({"open": [price] * n, "high": [price * 1.0001] * n,
                         "low": [price * 0.9999] * n, "close": [price] * n,
                         "volume": [5_000_000.0] * n}, index=idx)


# ------------------------------------------------------------------
# Scores
# ------------------------------------------------------------------
def test_score_plain_trailing_return():
    idx = sessions(30)
    panel = {
        "AAA": frame_from_closes(idx, 100 * 1.01 ** np.arange(30)),
        "BBB": frame_from_closes(idx, 100 * 0.99 ** np.arange(30)),
    }
    scores, _ = U.score_frame(panel, {}, 5)
    j = 20
    assert scores["AAA"].iloc[j] == pytest.approx(1.01 ** 5 - 1)
    assert scores["BBB"].iloc[j] == pytest.approx(0.99 ** 5 - 1)


def test_score_dividend_addback_restores_total_return():
    idx = sessions(30)
    closes = np.full(30, 100.0)
    closes[15:] = 98.0  # ex-date at session 15, dividend 2.0
    panel = {"AAA": frame_from_closes(idx, closes)}
    divs = {"AAA": [(idx[15], 2.0)]}
    with_div, _ = U.score_frame(panel, divs, 5)
    without, _ = U.score_frame(panel, {}, 5)
    j = 17  # window (12, 17] contains ex session 15
    assert without["AAA"].iloc[j] == pytest.approx(98 / 100 - 1)
    assert with_div["AAA"].iloc[j] == pytest.approx(0.0, abs=1e-12)
    # before the ex-date enters the window there is nothing to add back
    j0 = 14
    assert with_div["AAA"].iloc[j0] == pytest.approx(
        without["AAA"].iloc[j0])


def test_score_staleness_invalidates():
    idx = sessions(40)
    full = frame_from_closes(idx, 100 * 1.005 ** np.arange(40))
    short = frame_from_closes(idx[:21], 100 * 1.005 ** np.arange(21))
    panel = {"AAA": full, "BBB": short}
    scores, _ = U.score_frame(panel, {}, 5)
    # BBB's last real close is session 20; at j=22 age is 2 (valid),
    # at j=30 age is 10 (invalid)
    assert pd.notna(scores["BBB"].iloc[22])
    assert pd.isna(scores["BBB"].iloc[30])


# ------------------------------------------------------------------
# Entries
# ------------------------------------------------------------------
def ramp_panel(n_sym=8, n=40):
    idx = sessions(n)
    rates = np.linspace(-0.004, 0.004, n_sym)
    panel = {}
    for i, r in enumerate(rates):
        panel[f"S{i}"] = frame_from_closes(
            idx, 100 * (1 + r) ** np.arange(n))
    return panel, rates


def test_entries_picks_and_cadence():
    panel, rates = ramp_panel()
    entries = U.generate_entries(panel, {}, 5, warmup=10, rebalance=5, k=3)
    all_bars = sorted({b for v in entries.values() for b, _ in v})
    assert all_bars and all(b % 5 == 0 and b >= 10 for b in all_bars)
    at10_long = {s for s, v in entries.items() if (10, "LONG") in v}
    at10_short = {s for s, v in entries.items() if (10, "SHORT") in v}
    # trailing returns increase with the rate: lowest 3 long, top 3 short
    assert at10_long == {"S0", "S1", "S2"}
    assert at10_short == {"S5", "S6", "S7"}


def test_entries_skip_when_too_few_valid():
    panel, _ = ramp_panel(n_sym=5)  # 5 < 2k = 6
    entries = U.generate_entries(panel, {}, 5, warmup=10, rebalance=5, k=3)
    assert all(len(v) == 0 for v in entries.values())


def test_entries_no_lookahead():
    panel, _ = ramp_panel()
    base = U.generate_entries(panel, {}, 5, warmup=10, rebalance=5, k=3)
    mutated = {s: df.copy() for s, df in panel.items()}
    for s, df in mutated.items():
        c = df["close"].to_numpy().copy()
        c[21:] = c[21:] * 3.0  # drastic change strictly after session 20
        mutated[s] = frame_from_closes(df.index, c)
    after = U.generate_entries(mutated, {}, 5, warmup=10, rebalance=5, k=3)
    for s in panel:
        assert [e for e in base[s] if e[0] <= 20] == \
               [e for e in after[s] if e[0] <= 20]


# ------------------------------------------------------------------
# Simulation
# ------------------------------------------------------------------
def test_sim_flat_time_exit_and_costs():
    idx = sessions(20)
    df = flat_frame(idx, 100.0)
    atr = np.full(20, 1.0)
    trades = U.simulate_entries(df, [(0, "LONG")], atr, U.SPEC, "AAA",
                                U.COSTS_1X)
    assert len(trades) == 1
    t = trades[0]
    assert t.entry_time == idx[1]          # open of signal_bar + 1
    assert t.entry_price == 100.0
    assert t.exit_time == idx[5]           # close of entry_bar + 4
    assert t.exit_reason == "TIME"
    r = U.COSTS_1X.per_side_rate
    expected = (1 - r) / (1 + r) - 1
    assert t.net_return == pytest.approx(expected)
    assert t.borrow_charge == 0.0


def test_sim_stop_loss_level_and_gap():
    idx = sessions(20)
    df = flat_frame(idx, 100.0)
    atr = np.full(20, 1.0)  # SL at 98, TP at 104 for a long from 100
    # intraday dip to the stop: fill at the level
    df.loc[idx[3], "low"] = 97.5
    trades = U.simulate_entries(df, [(0, "LONG")], atr, U.SPEC, "AAA",
                                U.COSTS_1X)
    assert trades[0].exit_reason == "SL"
    assert trades[0].exit_price == pytest.approx(98.0)
    assert trades[0].exit_time == idx[3]
    # gap through the stop: fill at the open
    df2 = flat_frame(idx, 100.0)
    df2.loc[idx[3], ["open", "high", "low", "close"]] = [96.0, 96.5, 95.5, 96.0]
    trades2 = U.simulate_entries(df2, [(0, "LONG")], atr, U.SPEC, "AAA",
                                 U.COSTS_1X)
    assert trades2[0].exit_reason == "SL"
    assert trades2[0].exit_price == pytest.approx(96.0)


def test_sim_take_profit_and_stop_first():
    idx = sessions(20)
    atr = np.full(20, 1.0)
    df = flat_frame(idx, 100.0)
    df.loc[idx[2], "high"] = 105.0  # TP touched, SL untouched
    trades = U.simulate_entries(df, [(0, "LONG")], atr, U.SPEC, "AAA",
                                U.COSTS_1X)
    assert trades[0].exit_reason == "TP"
    assert trades[0].exit_price == pytest.approx(104.0)
    # both levels inside one bar -> stop first (worst case)
    df2 = flat_frame(idx, 100.0)
    df2.loc[idx[2], "high"] = 105.0
    df2.loc[idx[2], "low"] = 97.0
    trades2 = U.simulate_entries(df2, [(0, "LONG")], atr, U.SPEC, "AAA",
                                 U.COSTS_1X)
    assert trades2[0].exit_reason == "SL"


def test_sim_short_borrow_charge():
    # entry session is a Friday; TIME exit 4 sessions later (Thursday)
    idx = pd.bdate_range("2023-01-05", periods=10, tz="UTC")  # Thu start
    df = flat_frame(idx, 100.0)
    atr = np.full(10, 1.0)
    shorts = U.simulate_entries(df, [(0, "SHORT")], atr, U.SPEC, "AAA",
                                U.COSTS_1X)
    longs = U.simulate_entries(df, [(0, "LONG")], atr, U.SPEC, "AAA",
                               U.COSTS_1X)
    t = shorts[0]
    days = (t.exit_time - t.entry_time).days
    assert days == 6  # Fri -> Thu across a weekend
    assert t.borrow_charge == pytest.approx(0.0025 * 6 / 360)
    assert longs[0].borrow_charge == 0.0
    price_only = U._net_return("SHORT", 100.0, 100.0, U.COSTS_1X)
    assert t.net_return == pytest.approx(price_only - t.borrow_charge)


def test_sim_dividend_adjustment_signs():
    idx = sessions(20)
    df = flat_frame(idx, 100.0)
    atr = np.full(20, 1.0)
    divs = [(idx[3], 1.5)]  # ex-date inside the holding window (1, 5]
    long_t = U.simulate_entries(df, [(0, "LONG")], atr, U.SPEC, "AAA",
                                U.COSTS_1X, dividends_sym=divs)[0]
    short_t = U.simulate_entries(df, [(0, "SHORT")], atr, U.SPEC, "AAA",
                                 U.COSTS_1X, dividends_sym=divs)[0]
    assert long_t.dividend_adjustment == pytest.approx(1.5 / 100)
    assert short_t.dividend_adjustment == pytest.approx(-1.5 / 100)
    plain = U.simulate_entries(df, [(0, "LONG")], atr, U.SPEC, "AAA",
                               U.COSTS_1X)[0]
    assert long_t.net_return == pytest.approx(
        plain.net_return + 1.5 / 100)


def test_sim_one_position_at_a_time():
    idx = sessions(30)
    df = flat_frame(idx, 100.0)
    atr = np.full(30, 1.0)
    trades = U.simulate_entries(df, [(0, "LONG"), (2, "LONG"), (10, "LONG")],
                                atr, U.SPEC, "AAA", U.COSTS_1X)
    # the (2, ...) entry falls inside the first position (bars 1..5)
    assert [t.entry_time for t in trades] == [idx[1], idx[11]]


def test_atr_wilder_constant_range():
    idx = sessions(30)
    df = flat_frame(idx, 100.0)
    df["high"] = 101.0
    df["low"] = 99.0
    a = U.atr_wilder(df)
    assert a.iloc[-1] == pytest.approx(2.0, abs=1e-9)


# ------------------------------------------------------------------
# Judging
# ------------------------------------------------------------------
def mk_trade(sym, entry_iso, ret, side="LONG"):
    e = pd.Timestamp(entry_iso, tz="UTC")
    return U.Trade(sym, e, e + pd.Timedelta(days=5), side, 100.0, 100.0,
                   ret, "TIME")


FOLD_DATES = {"W1": "2024-08-15", "W2": "2025-02-15", "W3": "2025-08-15",
              "W4": "2026-02-15", "W5": "2026-08-15"}


def test_fold_attribution():
    trades = [mk_trade("AAA", "2024-08-15", 0.01),
              mk_trade("AAA", "2026-08-15", 0.02),
              mk_trade("AAA", "2023-08-15", 0.03)]  # pre-OOS: excluded
    rep = U.fold_report(trades, [f for f, _, _ in U.FOLDS], ["AAA"])
    assert rep["per_fold"]["W1"]["trades"] == 1
    assert rep["per_fold"]["W5"]["trades"] == 1
    assert rep["pooled_oos"]["trades"] == 2


def test_holdout2_breadth_concentration_subset():
    syms = ["A", "B", "C", "D", "E", "F"]
    trades = []
    for s in syms:
        for i in range(25):
            trades.append(mk_trade(s, "2024-08-15", 0.01))
    rep = U.fold_report(trades, [f for f, _, _ in U.FOLDS], syms)
    ho = U.holdout2(rep, syms)
    assert ho["untouched_subset"] == ["C", "F"]  # sorted[2::3]
    assert ho["breadth_positive_share"] == 1.0
    assert ho["passes"] is True
    # one symbol carrying everything fails the concentration cap
    trades2 = [mk_trade("A", "2024-08-15", 0.05) for _ in range(25)] + \
              [mk_trade(s, "2024-08-15", 0.0001)
               for s in syms[1:] for _ in range(25)]
    rep2 = U.fold_report(trades2, [f for f, _, _ in U.FOLDS], syms)
    ho2 = U.holdout2(rep2, syms)
    assert ho2["max_symbol_profit_share"] > 0.5
    assert ho2["passes"] is False


def test_temporal_holdout_h1_h4():
    syms = ["AAA"]
    fold_ids = [f for f, _, _ in U.FOLDS]

    def build(h_n, h_ret, d_spec):
        trades = []
        for fid, (n, r) in d_spec.items():
            trades += [mk_trade("AAA", FOLD_DATES[fid], r) for _ in range(n)]
        trades += [mk_trade("AAA", FOLD_DATES["W5"], h_ret)
                   for _ in range(h_n)]
        rep = U.fold_report(trades, fold_ids, syms)
        return U.temporal_holdout(trades, rep)

    even = {"W1": (25, 0.005), "W2": (25, 0.005),
            "W3": (25, 0.005), "W4": (25, 0.005)}
    th = build(25, 0.01, even)
    assert th["passes"] is True
    th_small = build(10, 0.01, even)          # H1: only 10 holdout trades
    assert th_small["checks"]["H1_holdout_size_gte_20"] is False
    assert th_small["passes"] is False
    th_conc = build(25, 0.01, {"W1": (25, 0.001)})  # H4: W5 carries > 80%
    assert th_conc["checks"]["H4_fold_concentration_lte_0.80"] is False
    th_neg = build(25, -0.01, even)           # H2: holdout negative
    assert th_neg["checks"]["H2_holdout_positive"] is False


def synth_book(symbols, per_symbol=60, win=0.006, loss=-0.002):
    trades = []
    fids = list(FOLD_DATES)
    for s in symbols:
        for i in range(per_symbol):
            fid = fids[i % 5]
            ret = win if i % 2 == 0 else loss
            trades.append(mk_trade(s, FOLD_DATES[fid], ret))
    return trades


def test_judge_pass_fail_insufficient():
    syms = ["A", "B", "C", "D", "E", "F"]
    good = synth_book(syms)
    judged = U.judge_cell(good, good, syms, n_final=3896)
    assert judged["verdict"] == "PASS"
    assert judged["checks"]["bonferroni_pass"] is True
    bad = synth_book(syms, win=0.002, loss=-0.004)  # PF 0.5
    judged_bad = U.judge_cell(bad, bad, syms, n_final=3896)
    assert judged_bad["verdict"] == "FAIL"
    few = synth_book(syms, per_symbol=8)            # 48 trades < 200
    judged_few = U.judge_cell(few, few, syms, n_final=3896)
    assert judged_few["verdict"] == "insufficient OOS trades"


# ------------------------------------------------------------------
# Runner: provenance refusal + synthetic end-to-end
# ------------------------------------------------------------------
def write_synthetic_panel(tmp_path, bad_sha=False):
    idx = pd.bdate_range("2023-01-02", "2026-10-30", tz="UTC")
    rng = np.random.default_rng(7)
    rows = []
    for s_i, sym in enumerate(U.UNIVERSE):
        steps = rng.normal(0.0002, 0.01, len(idx))
        closes = 100 * np.exp(np.cumsum(steps)) * (1 + s_i * 0.01)
        opens = np.concatenate([[closes[0]], closes[:-1]])
        for d, o, c in zip(idx, opens, closes):
            rows.append({"date": d.strftime("%Y-%m-%d"), "symbol": sym,
                         "open": o, "high": max(o, c) * 1.001,
                         "low": min(o, c) * 0.999, "close": c,
                         "volume": 5_000_000})
    panel = pd.DataFrame(rows)
    pdir = tmp_path / "panel"
    pdir.mkdir()
    panel.to_csv(pdir / "panel.csv", index=False)
    pd.DataFrame([{"symbol": "AAPL", "ex_date": "2024-05-10",
                   "amount": 0.25}]).to_csv(pdir / "dividends.csv",
                                            index=False)
    prov = {
        "feed": "sip", "adjustment": "split",
        "start": "2023-01-01T00:00:00Z", "end": "2026-11-01T00:00:00Z",
        "universe": U.UNIVERSE,
        "panel_sha256": hashlib.sha256(
            (pdir / "panel.csv").read_bytes()).hexdigest(),
        "dividends_sha256": hashlib.sha256(
            (pdir / "dividends.csv").read_bytes()).hexdigest(),
        "per_symbol_counts": {s: int((panel["symbol"] == s).sum())
                              for s in U.UNIVERSE},
        "gate": {"session_census": "pass", "sip_feed_check": "pass",
                 "split_check": "pass", "cross_source_spot_check": "pass",
                 "dividend_calendar_check": "pass"},
    }
    if bad_sha:
        prov["panel_sha256"] = "0" * 64
    (pdir / "provenance.json").write_text(json.dumps(prov))
    return pdir


def test_runner_end_to_end_synthetic(tmp_path):
    pdir = write_synthetic_panel(tmp_path)
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(RUNNER), "--panel-dir",
                        str(pdir), "--n-final", "3896", "--out", str(out)],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr
    results = json.loads((out / "results.json").read_text())
    assert set(results["cells"]) == {"rev5_r5", "rev10_r5"}
    for cell, rec in results["cells"].items():
        assert rec["verdict"] in ("PASS", "FAIL", "insufficient OOS trades")
        assert "leg_reporting_1x" in rec
    # verify each recorded hash against the file it names
    for key, sha in results["trade_list_sha256"].items():
        cell, level = key.rsplit("_", 1)
        f = out / f"trades_{cell}_{level}.csv"
        assert hashlib.sha256(f.read_bytes()).hexdigest() == sha


def test_runner_refuses_bad_provenance(tmp_path):
    pdir = write_synthetic_panel(tmp_path, bad_sha=True)
    r = subprocess.run([sys.executable, str(RUNNER), "--panel-dir",
                        str(pdir), "--n-final", "3896", "--out",
                        str(tmp_path / "out2")],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 2
    assert "REFUSED" in r.stderr
