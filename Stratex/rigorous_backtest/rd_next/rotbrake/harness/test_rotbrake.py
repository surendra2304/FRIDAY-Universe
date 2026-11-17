"""Synthetic tests for the TASK-STR-RD-020 harness (rotbrake.py).

These tests run ONLY on synthetic in-memory panels — they never touch
the real RD-013 panel and never execute the declared grid. They pin:
ranking causality, brake triggering/release on synthetic equity paths,
no look-ahead (truncation invariance + post-signal corruption),
turnover-cost arithmetic, episode accounting, period telescoping,
panel-hash refusal, and the bar evaluator's gates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rotbrake import (ASSETS, _verify, evaluate_bar, run_config, select,
                      summarise)

DATES = pd.date_range("2022-01-01", "2026-11-01", freq="D")


def make_closes(ret_by_asset: dict[str, np.ndarray]) -> dict[str, pd.Series]:
    closes = {}
    for a in ASSETS:
        rets = ret_by_asset[a]
        prices = 100.0 * np.cumprod(1.0 + rets)
        closes[a] = pd.Series(prices, index=DATES[:len(rets)])
    return closes


def const_rets(n: int, r: float) -> np.ndarray:
    return np.full(n, r)


def path_rets(segments: list[tuple[str, str, float]]) -> np.ndarray:
    """segments: (start_date, end_date_inclusive, daily_return)."""
    rets = np.zeros(len(DATES))
    idx = {d: i for i, d in enumerate(DATES)}
    for s, e, r in segments:
        rets[idx[pd.Timestamp(s)]: idx[pd.Timestamp(e)] + 1] = r
    return rets


N = len(DATES)


def test_frozen_prices_book_stays_cash():
    closes = make_closes({a: const_rets(N, 0.0) for a in ASSETS})
    res = run_config(closes, 63, 2)
    assert res["final_equity"] == 1.0
    assert res["transitions"] == []
    assert res["episodes"] == []
    assert res["total_cost_frac"] == 0.0
    s = summarise(res)
    assert s["oos_compounded"] == 0.0 and s["oos_periods"] > 100


def test_select_uses_only_past_bars():
    rng = np.random.default_rng(7)
    base = {a: rng.normal(0.0005, 0.02, N) for a in ASSETS}
    closes_a = make_closes(base)
    t = pd.Timestamp("2024-06-03")
    corrupted = {}
    for a in ASSETS:
        s = closes_a[a].copy()
        s[s.index > t] = s[s.index > t] * 5.0
        corrupted[a] = s
    assert select(closes_a, t, 63, 2) == select(corrupted, t, 63, 2)


def _random_panel(seed=7):
    rng = np.random.default_rng(seed)
    return make_closes({a: rng.normal(0.0005, 0.02, N) for a in ASSETS})


def test_truncation_invariance_no_lookahead():
    full = _random_panel()
    cut = pd.Timestamp("2025-03-01")
    trunc = {a: s[s.index <= cut] for a, s in full.items()}
    ra = run_config(full, 63, 3)
    rb = run_config(trunc, 63, 3)
    eq_a = {d: e for d, e in ra["equity_path"] if d <= cut}
    eq_b = {d: e for d, e in rb["equity_path"] if d <= cut}
    assert eq_a.keys() == eq_b.keys()
    for d in eq_a:
        assert eq_a[d] == eq_b[d], f"equity diverged at {d}"
    tr_a = [t for t in ra["transitions"] if pd.Timestamp(t["date"]) <= cut]
    tr_b = [t for t in rb["transitions"] if pd.Timestamp(t["date"]) <= cut]
    assert tr_a == tr_b
    ep_a = [e for e in ra["episodes"] if e["exit"] < cut]
    ep_b = [e for e in rb["episodes"] if e["exit"] < cut]
    assert len(ep_a) == len(ep_b) and len(ep_a) > 0
    for x, y in zip(ep_a, ep_b):
        assert x["asset"] == y["asset"] and x["entry"] == y["entry"] \
            and x["exit"] == y["exit"] and x["net"] == y["net"]


def test_brake_state_machine_on_synthetic_crash():
    # Identical path for every asset: long rise, sharp 7-day crash,
    # flat, then a steep recovery. The brake must halve, flatten,
    # re-enter probationary on a Monday, and finally release.
    rets = path_rets([
        ("2022-01-01", "2024-01-02", 0.001),
        ("2024-01-03", "2024-01-09", -0.04),
        ("2024-01-10", "2024-02-29", 0.0),
        ("2024-03-01", "2026-11-01", 0.015),
    ])
    closes = make_closes({a: rets for a in ASSETS})
    res = run_config(closes, 63, 2)
    tr = res["transitions"]
    assert len(tr) >= 4, tr
    assert (tr[0]["from"], tr[0]["to"]) == ("NORMAL", "HALVED")
    assert tr[0]["dd_at_signal"] <= -0.10
    assert (tr[1]["from"], tr[1]["to"]) == ("HALVED", "FLAT")
    assert tr[1]["dd_at_signal"] <= -0.15
    assert (tr[2]["from"], tr[2]["to"]) == ("FLAT", "HALVED")
    assert pd.Timestamp(tr[2]["date"]).weekday() == 0, "re-entry only on a Monday rebalance"
    # equity is frozen while FLAT (cash): constant between the flatten
    # close and the re-entry close (exclusive of the re-entry close,
    # which pays the re-entry cost)
    eq = dict(res["equity_path"])
    d_flat, d_re = pd.Timestamp(tr[1]["date"]), pd.Timestamp(tr[2]["date"])
    seg = [e for d, e in res["equity_path"] if d_flat <= d < d_re]
    assert len(seg) > 7 and all(abs(e - seg[0]) < 1e-12 for e in seg)
    # eventual full release on the braked book's own recovery
    assert any(t["from"] == "HALVED" and t["to"] == "NORMAL"
               and t["dd_at_signal"] >= -0.05 for t in tr[3:])
    assert (tr[-1]["to"]) == "NORMAL"


def test_brake_signal_ignores_future_prices():
    rets = path_rets([
        ("2022-01-01", "2024-01-02", 0.001),
        ("2024-01-03", "2024-01-09", -0.04),
        ("2024-01-10", "2026-11-01", 0.0),
    ])
    closes = make_closes({a: rets for a in ASSETS})
    res = run_config(closes, 63, 2)
    assert res["transitions"], "brake must fire on the engineered crash"
    first = res["transitions"][0]
    d0 = pd.Timestamp(first["date"])
    corrupted = {}
    for a in ASSETS:
        s = closes[a].copy()
        s[s.index > d0] = s[s.index > d0] * 37.0
        corrupted[a] = s
    res2 = run_config(corrupted, 63, 2)
    assert res2["transitions"][0] == first
    eq1 = {d: e for d, e in res["equity_path"] if d <= d0}
    eq2 = {d: e for d, e in res2["equity_path"] if d <= d0}
    assert eq1 == eq2


def test_turnover_cost_and_telescoping():
    # Crypto assets rise through 2022 at distinct rates, everything
    # frozen from 2023-01-01: the book builds top-3 crypto at the
    # first Monday (cost 8 bps), exits when the 63d window is fully
    # frozen (another 8 bps), and never trades again.
    rb = {}
    for a, r in [("BTCUSDT", 0.003), ("ETHUSDT", 0.002), ("SOLUSDT", 0.001),
                 ("BNBUSDT", 0.0005)]:
        rb[a] = path_rets([("2022-01-01", "2022-12-31", r),
                           ("2023-01-01", "2026-11-01", 0.0)])
    for a in ["GOLD", "SPX", "NDX"]:
        rb[a] = const_rets(N, 0.0)
    closes = make_closes(rb)
    res = run_config(closes, 63, 3)
    assert abs(res["total_cost_frac"] - 0.0016) < 1e-9, res["total_cost_frac"]
    assert abs(res["final_equity"] - (1 - 0.0008) ** 2) < 1e-9
    prod = float(np.prod([1.0 + p["net"] for p in res["periods"]]))
    assert abs(prod - res["final_equity"]) < 1e-9, "period returns must telescope"


def test_episode_accounting_single_winner():
    rb = {a: const_rets(N, -0.002) for a in ASSETS}
    rb["BTCUSDT"] = const_rets(N, 0.002)
    closes = make_closes(rb)
    res = run_config(closes, 63, 2)
    assert len(res["episodes"]) == 1
    ep = res["episodes"][0]
    assert ep["asset"] == "BTCUSDT"
    assert ep["entry"] == pd.Timestamp("2023-01-02")  # first rebalance
    s = closes["BTCUSDT"]
    expected = (s.loc[ep["exit"]] / s.loc[ep["entry"]]) * (1 - 16 / 20000) ** 2 - 1
    assert abs(ep["net"] - expected) < 1e-9
    assert summarise(res)["oos_episodes"] == 0  # entered in-sample


def test_episode_closes_on_deselection_monday():
    rb = {a: const_rets(N, -0.002) for a in ASSETS}
    rb["BTCUSDT"] = path_rets([("2022-01-01", "2025-06-30", 0.002),
                               ("2025-07-01", "2026-11-01", -0.005)])
    closes = make_closes(rb)
    res = run_config(closes, 63, 2)
    assert len(res["episodes"]) == 1
    ep = res["episodes"][0]
    assert ep["exit"].weekday() == 0 and ep["exit"] > pd.Timestamp("2025-07-01")
    s = closes["BTCUSDT"]
    expected = (s.loc[ep["exit"]] / s.loc[ep["entry"]]) * (1 - 16 / 20000) ** 2 - 1
    assert abs(ep["net"] - expected) < 1e-9
    # entry was 2023-01-02 (in-sample): episodes are attributed by
    # ENTRY date, so the OOS count is 0 even though the exit is OOS
    assert summarise(res)["oos_episodes"] == 0


def test_panel_hash_refusal(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "YH_GOLD_1d.csv"
        p.write_text("date,close\n2024-01-01,1.0\n")
        # sidecar disagrees with the file
        p.with_suffix(".csv.json").write_text(json.dumps({"csv_sha256": "0" * 64}))
        try:
            _verify(p)
            raise AssertionError("sidecar mismatch must refuse")
        except RuntimeError:
            pass
        # sidecar agrees with the file but not with the RD-013 record
        import hashlib
        own = hashlib.sha256(p.read_bytes()).hexdigest()
        p.with_suffix(".csv.json").write_text(json.dumps({"csv_sha256": own}))
        try:
            _verify(p)
            raise AssertionError("substituted panel must refuse")
        except RuntimeError:
            pass


def _row(**kw):
    base = {"oos_compounded": 0.5, "oos_period_pf": 1.5, "folds_positive": 5,
            "oos_max_drawdown_daily": -0.10, "max_asset_profit_share": 0.3,
            "t_stat_one_sided_p": 1e-9, "oos_episodes": 300,
            "oos_episode_pf": 1.4}
    base.update(kw)
    return base


def test_bar_evaluator():
    n = 3897
    alpha = 0.05 / n
    bar = evaluate_bar(_row(), n)
    assert bar["verdict"] == "MECHANICAL_PASS_X2_PENDING"
    bar2 = evaluate_bar(_row(), n, x2_row={"oos_compounded": 0.2,
                                           "oos_period_pf": 1.3})
    assert bar2["verdict"] == "PASS"
    assert evaluate_bar(_row(oos_episodes=199), n)["verdict"] == \
        "INSUFFICIENT_OOS_TRADES"
    # p within 2x of the threshold counts as FAILED (fail-closed band)
    assert evaluate_bar(_row(t_stat_one_sided_p=alpha * 0.75), n)["gates"]["g6_bonferroni"] is False
    assert evaluate_bar(_row(t_stat_one_sided_p=alpha * 0.4), n)["gates"]["g6_bonferroni"] is True
    assert evaluate_bar(_row(oos_max_drawdown_daily=-0.21), n)["gates"]["g4_max_dd_le_20pct_daily"] is False
    assert evaluate_bar(_row(oos_period_pf=1.19), n)["gates"]["g2_period_pf_ge_1_2"] is False
    assert evaluate_bar(_row(oos_episode_pf=1.19), n)["gates"]["g8_episodes_ge_200_and_episode_pf_ge_1_2"] is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} synthetic tests passed")
