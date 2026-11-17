"""Synthetic end-to-end smoke tests for run_xsrev.py's JUDGE path
(TASK-STR-RD-019; added by the PR #897 F1 fix).

The supervisor review found the original runner could not execute
against the programme code on origin/main at all (invented imports,
wrong signatures, wrong result keys) and that its judge path had
never been smoke-run — test_xsrev.py covers xsrev.py only. These
tests close that hole: they drive the runner's real judging
functions (judge_all / judge_level / bonferroni / temporal_holdout)
over synthetic simulator.Trade lists through the REAL programme
code imported from this repository (rigorous_backtest.walkforward
.oos_report, rd.common.check_bar / holdout_check, simulator
.trade_metrics), and they exercise main()'s refusal paths as a
subprocess.

ALL fixtures are synthetic trades with invented returns. No real
panel, no real trades, no backtest: this is mechanics coverage of
the judging code only (the same synthetic-debugging use the
declaration allows). The family's actual W5 holdout has never been
computed or inspected — nothing here touches it.

Run:  python3 -m pytest -q test_xsrev_judge_smoke.py
(from Stratex/rigorous_backtest/rd19/ inside a full checkout)
"""
from __future__ import annotations

import subprocess
import sys
from datetime import timedelta
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR))
import run_xsrev  # noqa: E402

REPO_ROOT = HARNESS_DIR.parents[2]  # rd19 -> rigorous_backtest -> Stratex -> repo
PROG = run_xsrev.load_programme(REPO_ROOT)
SYMBOLS = run_xsrev.EXPECTED_SYMBOLS

# A return cycle with mean +1.125%/trade and PF 4.0 (per 4 trades:
# gross profit 0.060, gross loss 0.015).
WIN_CYCLE = [0.030, 0.020, 0.010, -0.015]
# A losing cycle, mean -0.925%/trade.
LOSE_CYCLE = [-0.030, -0.010, 0.005, -0.002]

FOLD_START = {fid: s for fid, s, _ in PROG.FOLDS}


def make_trades(plan: dict) -> list:
    """plan: {fold_id: {symbol: [net_return, ...]}} -> SimTrade list
    with entry times spread inside the fold window."""
    import pandas as pd
    trades = []
    for fid, by_symbol in plan.items():
        start = pd.Timestamp(FOLD_START[fid], tz="UTC")
        for sym, rets in by_symbol.items():
            for i, r in enumerate(rets):
                entry = start + timedelta(hours=12 * i + 1)
                trades.append(PROG.SimTrade(
                    sym, entry, entry + timedelta(hours=6), "LONG",
                    100.0, 100.0 * (1.0 + r), float(r),
                    "TP" if r > 0 else "SL"))
    return trades


def cycle(cyc: list, n: int) -> list:
    return [cyc[i % len(cyc)] for i in range(n)]


def pass_plan(per_fold_per_symbol: int = 24, w5_cycle=None,
              w5_per_symbol: int | None = None) -> dict:
    plan = {}
    for fid, _, _ in PROG.FOLDS:
        n = per_fold_per_symbol
        cyc = WIN_CYCLE
        if fid == "W5":
            if w5_per_symbol is not None:
                n = w5_per_symbol
            if w5_cycle is not None:
                cyc = w5_cycle
        plan[fid] = {sym: cycle(cyc, n)
                     for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT")}
    return plan


def judge(plan):
    trades = make_trades(plan)
    by_tag = {"programme_16bps": trades,
              "shadow_32bps": make_trades(plan)}
    return run_xsrev.judge_all(by_tag, SYMBOLS, 3894, PROG)


# ------------------------------------------------------------ verdicts
def test_pass_shape_all_components_both_levels():
    judged, verdict, _ = judge(pass_plan())
    assert verdict == "PASS"
    for tag in ("programme_16bps", "shadow_32bps"):
        j = judged[tag]
        assert j["pooled_oos"]["trades"] == 360
        assert j["passes_all"] is True
        assert all(j["checks"].values()), j["checks"]
        assert j["bar"]["passes_bar"] is True
        assert j["holdout"]["passes"] is True
        assert j["temporal_holdout"]["passes"] is True
        assert j["bonferroni"]["passes"] is True
        assert j["bonferroni"]["alpha"] == 0.05 / 3894


def test_fail_shape_negative_expectancy():
    plan = {fid: {sym: cycle(LOSE_CYCLE, 24)
                  for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT")}
            for fid, _, _ in PROG.FOLDS}
    judged, verdict, _ = judge(plan)
    assert verdict == "FAIL"
    for tag in ("programme_16bps", "shadow_32bps"):
        assert judged[tag]["passes_all"] is False
        assert judged[tag]["checks"]["expectancy_net_gt_0"] is False


def test_insufficient_oos_trades_exact_verdict():
    plan = {"W1": {sym: cycle(WIN_CYCLE, 20)
                   for sym in ("BTCUSDT", "ETHUSDT")}}
    judged, verdict, _ = judge(plan)
    assert judged["programme_16bps"]["pooled_oos"]["trades"] == 40
    assert verdict == "insufficient OOS trades"  # exactly the phrase


def test_overlay_fails_when_w5_negative_but_bar_passes():
    judged, verdict, _ = judge(pass_plan(w5_cycle=LOSE_CYCLE))
    assert verdict == "FAIL"
    for tag in ("programme_16bps", "shadow_32bps"):
        j = judged[tag]
        # the pooled bar still passes — the overlay is the ONLY
        # failing component, which is exactly what F2 added it for
        assert j["bar"]["passes_bar"] is True
        assert j["temporal_holdout"]["checks"][
            "H2_holdout_expectancy_gt_0"] is False
        assert j["checks"]["temporal_holdout_v1"] is False
        assert j["passes_all"] is False


def test_overlay_fails_when_holdout_too_small():
    judged, verdict, _ = judge(pass_plan(w5_per_symbol=4))
    assert verdict == "FAIL"
    for tag in ("programme_16bps", "shadow_32bps"):
        th = judged[tag]["temporal_holdout"]
        assert th["holdout_metrics"]["trades"] == 12
        assert th["checks"]["H1_holdout_trades_gte_20"] is False
        assert th["passes"] is False


def test_bonferroni_uses_oos_returns_not_a_phantom_key():
    # regression for F1 defect (vii): the original read rep["_rets"],
    # which exists nowhere, and would have failed every run silently.
    trades = make_trades(pass_plan())
    bf = run_xsrev.bonferroni(trades, 3894, PROG)
    assert bf["n"] == 360
    assert bf["t_stat"] is not None and bf["t_stat"] > 5
    assert bf["p_value"] is not None and bf["p_value"] < bf["alpha"]
    assert bf["passes"] is True


# ------------------------------------------------- main() refusal paths
def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HARNESS_DIR / "run_xsrev.py"), *argv],
        capture_output=True, text=True, timeout=120)


def test_trial_floor_minimum_enforced_before_any_load(tmp_path):
    # a nonexistent --repo proves the refusal fires before any load
    r = run_cli("--repo", str(tmp_path / "no_such_repo"),
                "--trial-floor", "3893", "--declared-run",
                "--out", str(tmp_path / "out"))
    assert r.returncode == 2
    assert "3894" in r.stderr


def test_declared_run_attestation_required(tmp_path):
    r = run_cli("--repo", str(tmp_path / "no_such_repo"),
                "--trial-floor", "3894",
                "--out", str(tmp_path / "out"))
    assert r.returncode == 2
    assert "--declared-run" in r.stderr


def test_results_exists_refusal(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "RESULTS.md").write_text("already ran", encoding="utf-8")
    r = run_cli("--repo", str(tmp_path / "no_such_repo"),
                "--trial-floor", "3894", "--declared-run",
                "--out", str(out))
    assert r.returncode == 2
    assert "RESULTS.md" in r.stderr


def test_declaration_missing_aborts(tmp_path):
    r = run_cli("--repo", str(tmp_path), "--trial-floor", "3894",
                "--declared-run", "--out", str(tmp_path / "out"))
    assert r.returncode == 2
    assert "declaration not found" in r.stderr


def test_declaration_hash_mismatch_aborts(tmp_path):
    decl = tmp_path / run_xsrev.DECLARATION_REL
    decl.parent.mkdir(parents=True)
    decl.write_text("{}", encoding="utf-8")
    r = run_cli("--repo", str(tmp_path), "--trial-floor", "3894",
                "--declared-run", "--out", str(tmp_path / "out"))
    assert r.returncode == 2
    assert "SHA-256 mismatch" in r.stderr


def test_floor_constant_is_the_declared_minimum():
    assert run_xsrev.MIN_TRIAL_FLOOR == 3894
