"""Tests for TASK-IG-STR-05 research_desk (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.research_desk import analyse, plan, risk_checklist, run_desk, scan

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
    assert memo["summary"] == {"setups_in": 1, "plans_drafted": 1,
                               "checklists_passed": 1}
    assert memo["plans"][0]["status"].startswith("DRAFT")
    assert memo["plans"][0]["equity"] == 10000.0
