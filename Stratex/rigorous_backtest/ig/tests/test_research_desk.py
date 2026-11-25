"""Tests for TASK-IG-STR-05 research_desk (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.research_desk import (analyse, pattern_match, plan,
                              risk_checklist, run_desk, scan)

SETUP = {"symbol": "BTCUSDT", "timeframe": "4h", "direction": "long",
         "entry_ref": 100.0, "invalidation": 95.0, "target": 112.5}
CTX = {"BTCUSDT": {"adv_quote": 5e7, "spread_bps": 3.0}}


def _uptrend_candles(n=40):
    return [{"high": 100 + i * 0.6, "low": 99 + i * 0.6,
             "close": 99.5 + i * 0.6} for i in range(n)]


def test_scan_filters_and_flags():
    out = scan([SETUP, {**SETUP, "symbol": "THIN"}],
               {"BTCUSDT": CTX["BTCUSDT"],
                "THIN": {"adv_quote": 10.0, "spread_bps": 90.0}},
               min_adv_quote=1e6, max_spread_bps=20.0)
    assert [s["symbol"] for s in out["kept"]] == ["BTCUSDT"]
    assert out["dropped"][0]["symbol"] == "THIN"
    out2 = scan([SETUP], {}, min_adv_quote=1e6)
    assert out2["kept"][0]["scan_flags"] == ["context_missing"]


def test_analyse_uptrend_alignment_and_rr():
    a = analyse(SETUP, _uptrend_candles())
    assert a["trend"] == "up" and a["aligned"] is True
    assert abs(a["rr_ratio"] - 2.5) < 1e-9
    short = analyse({**SETUP, "direction": "short"}, _uptrend_candles())
    assert short["aligned"] is False
    few = analyse(SETUP, _uptrend_candles(5))
    assert few["trend"] == "unknown"


def test_plan_sizing_math():
    p = plan(SETUP, equity=10000.0, risk_per_trade_pct=0.001)
    assert p["risk_amount"] == 10.0
    assert abs(p["units"] - 2.0) < 1e-12  # 10 / (100-95)
    assert "not an order" in p["status"]


def test_checklist_pass_and_failures():
    p = plan(SETUP, 10000.0, 0.001)
    ok = risk_checklist(p, SETUP, max_risk_pct=0.001)
    assert ok["passed"] is True
    # risk above the cap fails closed
    big = plan(SETUP, 10000.0, 0.01)
    over = risk_checklist(big, SETUP, max_risk_pct=0.001)
    assert over["passed"] is False
    assert any(i["name"] == "risk_within_cap" and not i["ok"]
               for i in over["items"])
    # invalidation on the wrong side fails
    bad = {**SETUP, "invalidation": 105.0}
    pb = plan({**bad, "target": 112.5}, 10000.0, 0.001)
    wrong = risk_checklist(pb, bad, max_risk_pct=0.001)
    assert wrong["passed"] is False
    # poor R:R fails
    lowrr = {**SETUP, "target": 105.0}
    pl = plan(lowrr, 10000.0, 0.001)
    assert risk_checklist(pl, lowrr, 0.001)["passed"] is False


def test_run_desk_memo_shape():
    memo = run_desk([SETUP], CTX, {"BTCUSDT": _uptrend_candles()},
                    equity=10000.0, risk_per_trade_pct=0.001,
                    max_risk_pct=0.001, min_adv_quote=1e6,
                    max_spread_bps=20.0)
    assert memo["type"] == "memo" and memo["research_only"] is True
    assert memo["summary"]["setups_in"] == 1
    assert memo["summary"]["plans_drafted"] == 1
    assert memo["summary"]["checklists_passed"] == 1
    assert memo["summary"]["pattern_matches_found"] == \
        memo["pattern_matches"]["BTCUSDT"]["matches_found"]
    assert memo["plans"][0]["status"].startswith("DRAFT")
    assert memo["plans"][0]["equity"] == 10000.0


# --- TASK-STR-067: pattern comparison -------------------------------

_SHAPE = [1.00, 1.01, 1.02, 1.03, 1.04, 1.05, 1.045, 1.04, 1.035, 1.03]
_DAY = 86400
_EPOCH = 1778000000  # fixed base so timestamps are deterministic


def _planted_candles(n=200):
    """200 daily candles, flat at 100 except three planted windows that
    copy the current window's shape at other levels, each followed by a
    known 10-bar forward move: +3% (j=20), -3% (j=80), +3% (j=140).
    Current window = last 10 bars, same shape at level 100."""
    closes = [100.0] * n
    for j, level in ((20, 90.0), (80, 110.0), (140, 95.0)):
        for k, mult in enumerate(_SHAPE):
            closes[j + k] = level * mult
        end = closes[j + 9]
        drift = 0.03 if j != 80 else -0.03
        for k in range(1, 11):
            closes[j + 9 + k] = end * (1 + drift * k / 10.0)
    for k, mult in enumerate(_SHAPE):
        closes[n - 10 + k] = 100.0 * mult
    return [{"high": c, "low": c, "close": c,
             "time": _EPOCH + i * _DAY} for i, c in enumerate(closes)]


def test_pattern_match_finds_planted_patterns():
    out = pattern_match(_planted_candles(), "long")
    assert out["status"] == "ok"
    assert out["lookback_applied"] is True
    assert out["matches_found"] == 3
    by_start = {m["start_index"]: m for m in out["matches"]}
    assert sorted(by_start) == [20, 80, 140]
    assert out["current_window"]["start_index"] == 190
    # every match's outcome window ends before the current window starts
    for m in out["matches"]:
        assert m["end_index"] + 10 <= 190
        assert m["similarity"] > 0.99
    assert abs(by_start[20]["forward_return_pct"] - 3.0) < 1e-9
    assert abs(by_start[80]["forward_return_pct"] + 3.0) < 1e-9
    assert by_start[20]["forward_direction"] == "up"
    assert by_start[80]["forward_direction"] == "down"
    assert by_start[20]["success"] is True
    assert by_start[80]["success"] is False
    assert out["successes"] == 2
    assert abs(out["success_rate"] - 2 / 3) < 1e-12


def test_pattern_match_short_direction_flips_success():
    out = pattern_match(_planted_candles(), "short")
    assert out["successes"] == 1
    assert abs(out["success_rate"] - 1 / 3) < 1e-12


def test_pattern_match_lookback_excludes_old_windows():
    out = pattern_match(_planted_candles(), "long", lookback_days=60)
    starts = [m["start_index"] for m in out["matches"]]
    assert 140 in starts
    assert 20 not in starts and 80 not in starts
    assert all(s >= 130 for s in starts)


def test_pattern_match_insufficient_history():
    few = [{"high": 100.0, "low": 100.0, "close": 100.0}
           for _ in range(25)]
    out = pattern_match(few, "long")
    assert out["status"] == "insufficient_history"
    assert out["matches"] == [] and out["success_rate"] is None
    assert "reason" in out


def test_run_desk_pattern_section():
    memo = run_desk([SETUP], CTX, {"BTCUSDT": _planted_candles()},
                    equity=10000.0, risk_per_trade_pct=0.001,
                    max_risk_pct=0.001)
    pm = memo["pattern_matches"]["BTCUSDT"]
    assert pm["matches_found"] == 3
    assert abs(pm["success_rate"] - 2 / 3) < 1e-12
    assert memo["summary"]["pattern_matches_found"] == 3


# --- TASK-STR-069: hardened checklist -------------------------------

_GOOD_EVIDENCE = {
    "clean_data_retest": True,
    "trade_count": 120,
    "max_drawdown_pct": 8.0,
    "total_return_pct": 24.0,
    "tiny_size_incubated": True,
    "repainting": False,
    "bot_built_by_us": True,
}
_HARDENED = ["clean_data_retest", "min_trades", "drawdown_vs_return",
             "tiny_size_incubation", "repainting_check", "bot_provenance"]


def test_hardened_checklist_no_evidence_unevaluated():
    # Pre-STR-069 behaviour is preserved: a plan with no backtest
    # evidence still passes, and the six items are named unevaluated
    # instead of being guessed at.
    p = plan(SETUP, 10000.0, 0.001)
    out = risk_checklist(p, SETUP, max_risk_pct=0.001)
    assert out["passed"] is True
    assert out["unevaluated"] == _HARDENED
    assert all(i["evaluated"] for i in out["items"]
               if i["name"] not in _HARDENED)


def test_hardened_checklist_good_evidence_passes():
    p = plan(SETUP, 10000.0, 0.001)
    out = risk_checklist(p, SETUP, max_risk_pct=0.001,
                         evidence=_GOOD_EVIDENCE)
    assert out["passed"] is True
    assert out["unevaluated"] == []


def test_hardened_checklist_each_item_fails():
    p = plan(SETUP, 10000.0, 0.001)
    cases = [
        ("clean_data_retest", {"clean_data_retest": False}),
        ("min_trades", {"trade_count": 49}),
        ("drawdown_vs_return",
         {"max_drawdown_pct": 13.0, "total_return_pct": 24.0}),
        ("tiny_size_incubation", {"tiny_size_incubated": False}),
        ("repainting_check", {"repainting": True}),
        ("bot_provenance", {"bot_built_by_us": False}),
    ]
    for name, ev in cases:
        out = risk_checklist(p, SETUP, max_risk_pct=0.001, evidence=ev)
        assert out["passed"] is False, name
        assert any(i["name"] == name and not i["ok"]
                   for i in out["items"]), name


def test_hardened_checklist_boundaries():
    p = plan(SETUP, 10000.0, 0.001)
    # Exactly 50 trades passes; drawdown exactly half the return passes.
    out = risk_checklist(p, SETUP, max_risk_pct=0.001,
                         evidence={"trade_count": 50,
                                   "max_drawdown_pct": 12.0,
                                   "total_return_pct": 24.0})
    assert out["passed"] is True
    # Zero return fails the robustness gate: nothing to be robust against.
    out2 = risk_checklist(p, SETUP, max_risk_pct=0.001,
                          evidence={"max_drawdown_pct": 5.0,
                                    "total_return_pct": 0.0})
    assert out2["passed"] is False


def test_run_desk_threads_backtest_evidence():
    memo = run_desk([SETUP], CTX, {"BTCUSDT": _uptrend_candles()},
                    equity=10000.0, risk_per_trade_pct=0.001,
                    max_risk_pct=0.001,
                    backtest_evidence={"BTCUSDT": _GOOD_EVIDENCE})
    assert memo["checklists"][0]["passed"] is True
    assert memo["checklists"][0]["unevaluated"] == []
    memo2 = run_desk([SETUP], CTX, {"BTCUSDT": _uptrend_candles()},
                     equity=10000.0, risk_per_trade_pct=0.001,
                     max_risk_pct=0.001,
                     backtest_evidence={"BTCUSDT": {"trade_count": 10}})
    assert memo2["checklists"][0]["passed"] is False
    assert "min_trades" not in memo2["checklists"][0]["unevaluated"]
