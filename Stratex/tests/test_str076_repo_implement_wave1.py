"""TASK-STR-076: REPO-IMPLEMENT wave 1 — day-trader-skill + tradermonty adapted,
agiprolabs / OpenTerminal / NautilusTrader / TradingAgents reference-only.

The adapted chain (scanner -> entry -> exit plan -> Time Machine replay ->
budget sizing -> risk check) must run end-to-end on real bars and must fail
closed: no bars / stale feed / no trigger / refused plan / failed sizing /
failed risk all return BLOCKED or WAITING, never GO, and the module never
places an order. The reference-only guard proves the upstream packages are
absent from every Stratex production path (AST import scan, not string
matching, so docstring URLs do not count).
"""

import math
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import repo_wave1 as w1

STRATEX_DIR = Path(__file__).resolve().parents[1]

# 12 real BTCUSDT 5m bars fetched read-only from the live Stratex-Server
# (Binance demo-fapi public klines, 2026-11-24): [ts_ms, o, h, l, c, v].
LIVE_BARS_RAW = [
    (1795510800000, 60222.20, 60233.20, 59891.30, 59978.00, 2528.290),
    (1795511100000, 59978.00, 59998.50, 59823.40, 59833.40, 1386.861),
    (1795511400000, 59833.30, 59996.40, 59731.90, 59847.10, 1412.418),
    (1795511700000, 59847.10, 60039.30, 59809.90, 59973.80, 667.959),
    (1795512000000, 59973.90, 59999.00, 59827.90, 59909.10, 526.924),
    (1795512300000, 59909.10, 59943.00, 59822.80, 59942.90, 511.481),
    (1795512600000, 59942.90, 60056.60, 59927.50, 59970.00, 454.644),
    (1795512900000, 59970.00, 60090.10, 59963.50, 60077.70, 435.785),
    (1795513200000, 60077.70, 60219.00, 60066.80, 60157.20, 768.084),
    (1795513500000, 60157.20, 60200.00, 59957.30, 60009.00, 749.227),
    (1795513800000, 60009.00, 60075.10, 59882.90, 59937.30, 501.848),
    (1795514100000, 59937.30, 59973.50, 59886.70, 59963.90, 331.486),
]


def _bar(ts, o, h, l, c, v=100.0):
    return w1.Bar(ts=ts, open=o, high=h, low=l, close=c, volume=v)


def _orb_bars():
    """Synthetic 5m bars: OR (first 3) high 102, low 98; bar 4 closes 103."""
    base = 1_795_510_800
    bars = [
        _bar(base + 0 * 300, 100, 102, 98, 100, 100),
        _bar(base + 1 * 300, 100, 101, 99, 100, 110),
        _bar(base + 2 * 300, 100, 100, 98, 99, 90),
        _bar(base + 3 * 300, 99, 104, 99, 103, 150),
        _bar(base + 4 * 300, 103, 105, 102, 104, 120),
        _bar(base + 5 * 300, 104, 106, 103, 105, 130),
        _bar(base + 6 * 300, 105, 105, 103, 104, 100),
        _bar(base + 7 * 300, 104, 105, 102, 103, 100),
        _bar(base + 8 * 300, 103, 104, 101, 102, 100),
        _bar(base + 9 * 300, 102, 103, 100, 101, 100),
        _bar(base + 10 * 300, 101, 102, 100, 101, 100),
        _bar(base + 11 * 300, 101, 102, 99, 100, 100),
    ]
    return bars


# --- bars -----------------------------------------------------------------

def test_bars_from_binance_list_klines():
    bars = w1.bars_from_candles([list(r) for r in LIVE_BARS_RAW])
    assert len(bars) == 12
    assert bars[0].ts == 1795510800.0
    assert bars[0].close == 59978.00
    assert bars[-1].close == 59963.90


def test_bars_from_dict_candles_and_malformed_skipped():
    candles = [
        {"timestamp": 1000, "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 5},
        {"timestamp": 2000, "open": "bad", "high": 11, "low": 9, "close": 10.5},
        {"timestamp": 1500, "open": 10, "high": 12, "low": 10, "close": 11, "volume": 7},
    ]
    bars = w1.bars_from_candles(candles)
    assert [b.ts for b in bars] == [1000.0, 1500.0]


# --- scanner / entry / exit -------------------------------------------------

def test_opening_range_high_low():
    assert w1.opening_range(_orb_bars()) == (102.0, 98.0)
    assert w1.opening_range(_orb_bars()[:2]) is None


def test_scan_orb_triggered_on_first_close_above_high():
    scan = w1.scan_orb(_orb_bars(), "BTCUSDT")
    assert scan["status"] == "triggered"
    assert scan["entry"] == 103.0
    assert scan["or_high"] == 102.0


def test_scan_orb_wick_above_high_does_not_trigger():
    bars = _orb_bars()
    bars[3] = _bar(bars[3].ts, 99, 104, 99, 101, 150)  # wick to 104, close 101
    # Every later bar also closes at or below the range high (102).
    for i in range(4, len(bars)):
        bars[i] = _bar(bars[i].ts, 101, 101.5, 100, 101, 120)
    scan = w1.scan_orb(bars, "BTCUSDT")
    assert scan["status"] == "waiting"


def test_scan_orb_waiting_when_no_close_above():
    bars = [_bar(1_795_510_800 + i * 300, 100, 101, 99, 100, 100) for i in range(12)]
    assert w1.scan_orb(bars, "BTCUSDT")["status"] == "waiting"


def test_exit_plan_or_mid_stop_and_2r_target():
    plan = w1.exit_plan(103.0, 102.0, 98.0)
    assert plan["status"] == "planned"
    assert plan["stop"] == 100.0  # or-mid (102+98)/2
    assert plan["target"] == 109.0  # 103 + 2 * 3
    assert plan["risk"] == 3.0


def test_exit_plan_refused_when_stop_at_or_above_entry():
    assert w1.exit_plan(100.0, 102.0, 98.0)["status"] == "refused"


# --- time machine / sizing / risk ------------------------------------------

def test_timemachine_deterministic_and_outcomes_sum_to_one():
    bars = _orb_bars()
    r1 = w1.timemachine(bars, 103.0, 100.0, 109.0, replays=500, seed=19)
    r2 = w1.timemachine(bars, 103.0, 100.0, 109.0, replays=500, seed=19)
    assert r1 == r2
    assert r1["status"] == "ok"
    assert 0.0 <= r1["green_pct"] <= 1.0
    assert abs(r1["target_pct"] + r1["stop_pct"] + r1["neither_pct"] - 1.0) < 0.01


def test_size_position_floor_of_the_smallest_cap():
    s = w1.size_position(10_000.0, 103.0, 100.0)
    # by_loss 50/3=16.67, by_cap 10000*.02/103=1.94, by_order 500/103=4.85,
    # by_cash ~92.4 -> smallest is by_cap, quantised to 0.001 units.
    assert s["status"] == "sized"
    assert s["qty"] == pytest.approx(1.941)
    assert s["risk_usd"] == pytest.approx(5.82)  # rounded to cents by sizing


def test_size_position_whole_units_restores_upstream_rule():
    s = w1.size_position(10_000.0, 103.0, 100.0, whole_units=True)
    assert s["status"] == "sized"
    assert s["qty"] == 1
    assert s["risk_usd"] == 3.0


def test_size_position_btc_scale_fractional_units():
    # Live E2E case: entry 60296.60, stop 59982.55, budget 10556.99.
    # Whole-unit sizing refuses this (0.0035 units floors to 0); the
    # venue minimum quantity 0.001 makes it a 0.003-unit trade.
    s = w1.size_position(10_556.99, 60296.60, 59982.55)
    assert s["status"] == "sized"
    assert s["qty"] == pytest.approx(0.003)
    assert s["risk_usd"] == pytest.approx(0.003 * 314.05, abs=0.01)


def test_size_position_zero_is_a_refusal():
    s = w1.size_position(10_000.0, 103.0, 102.9, max_loss_per_trade_usd=0.00005)
    assert s["status"] == "refused"


def test_risk_check_pass_and_block_reasons():
    ok = w1.risk_check("BTCUSDT", "BUY", 1, 103.0, 100.0, 10_000.0, 10_000.0)
    assert ok["verdict"] == "PASS"
    blocked = w1.risk_check("BTCUSDT", "BUY", 1, 103.0, None, 10_000.0, 10_000.0,
                            blocked=("BTCUSDT",))
    assert blocked["verdict"] == "BLOCK"
    assert any("blocked" in r for r in blocked["reasons"])
    assert any("stop" in r for r in blocked["reasons"])
    over_loss = w1.risk_check("BTCUSDT", "BUY", 100, 103.0, 100.0, 10_000.0, 10_000.0)
    assert over_loss["verdict"] == "BLOCK"
    assert any("loss" in r for r in over_loss["reasons"])


# --- full chain --------------------------------------------------------------

def test_chain_go_on_trigger_bars():
    now = _orb_bars()[-1].ts + 60
    d = w1.run_day_trader_chain("BTCUSDT", _orb_bars(), 10_000.0, 10_000.0, now=now)
    assert d["verdict"] == "GO"
    assert d["entry"] == 103.0 and d["stop"] == 100.0 and d["target"] == 109.0
    assert d["qty"] == pytest.approx(1.941)
    assert 0.0 <= d["timemachine_green_pct"] <= 1.0


def test_chain_blocked_on_no_data():
    d = w1.run_day_trader_chain("BTCUSDT", [], 10_000.0, 10_000.0)
    assert d["verdict"] == "BLOCKED" and d["reason"] == "no-data"


def test_chain_blocked_on_stale_feed():
    bars = _orb_bars()
    now = bars[-1].ts + 10_000  # last bar ~2.8h old, over the 900s cap
    d = w1.run_day_trader_chain("BTCUSDT", bars, 10_000.0, 10_000.0, now=now)
    assert d["verdict"] == "BLOCKED" and d["reason"] == "stale-feed"


def test_chain_waiting_when_no_trigger():
    bars = [_bar(1_795_510_800 + i * 300, 100, 101, 99, 100, 100) for i in range(12)]
    d = w1.run_day_trader_chain("BTCUSDT", bars, 10_000.0, 10_000.0,
                                now=bars[-1].ts + 60)
    assert d["verdict"] == "WAITING"


def test_chain_blocked_when_sizing_refuses():
    # Max loss per trade so small the stop is too far away for any unit
    # (by_loss 0.002/3 < the 0.001 venue minimum quantity).
    d = w1.run_day_trader_chain("BTCUSDT", _orb_bars(), 10_000.0, 10_000.0,
                                now=_orb_bars()[-1].ts + 60,
                                config={"max_loss_per_trade_usd": 0.002})
    assert d["verdict"] == "BLOCKED"
    assert "sizing refused" in d["reason"]


def test_chain_runs_on_real_live_bars_without_crashing():
    bars = w1.bars_from_candles([list(r) for r in LIVE_BARS_RAW])
    d = w1.run_day_trader_chain("BTCUSDT", bars, 10_556.99, 10_556.99,
                                now=bars[-1].ts + 60)
    assert d["verdict"] in ("GO", "WAITING", "BLOCKED")
    assert "steps" in d and d["steps"]["feed"]["bars"] == 12


# --- journal / postmortem / digest ------------------------------------------

def _thesis(**kw):
    base = dict(thesis_id="th1", symbol="BTCUSDT", direction="LONG",
                entry=100.0, stop=97.0, target=106.0, exit_price=104.0,
                exit_reason="TARGET", source_skill="test")
    base.update(kw)
    return w1.Thesis(**base)


def test_journal_r_multiple_and_pnl():
    t = _thesis(exit_price=104.0)
    assert t.r_multiple == pytest.approx(4 / 3)
    assert t.pnl == pytest.approx(4.0)
    assert t.won is True
    gap = _thesis(thesis_id="th2", entry=100.0, stop=100.0, exit_price=90.0)
    assert gap.r_multiple is None  # no positive risk -> excluded from R averages


def test_postmortem_categories():
    assert w1.postmortem(_thesis())["category"] == "true_positive"
    loser = _thesis(thesis_id="th2", exit_price=96.0, exit_reason="STOP")
    assert w1.postmortem(loser, realized_5d=0.05)["category"] == "false_positive"
    assert w1.postmortem(loser, realized_5d=-0.05,
                         realized_20d=0.04)["category"] == "missed_opportunity"
    assert w1.postmortem(loser, realized_5d=-0.05,
                         realized_20d=-0.04)["category"] == "regime_mismatch"


def test_weekly_digest_metrics():
    theses = [_thesis(thesis_id="a", exit_price=104.0),   # +4, R 1.333
              _thesis(thesis_id="b", exit_price=97.0, exit_reason="STOP"),  # -3, R -1
              _thesis(thesis_id="c", exit_price=101.0, exit_reason="TIME")]  # +1, R .333
    d = w1.weekly_digest(theses)
    assert d["trades"] == 3 and d["wins"] == 2 and d["losses"] == 1
    assert d["win_rate"] == pytest.approx(0.6667)  # rounded to 4dp by the digest
    assert d["profit_factor"] == pytest.approx(1.6667)  # rounded to 4dp
    assert d["mean_r"] == pytest.approx(0.2222)  # rounded to 4dp


def test_journal_record_to_ledger_never_raises_without_ledger(tmp_path):
    journal = w1.TradeJournal()
    journal.record(_thesis())
    # No advisory_ledger importable from this standalone path: must be False, not raise.
    assert journal.record_to_ledger(_thesis(), filepath=str(tmp_path / "x.jsonl")) in (True, False)


# --- reference-only guardrail -------------------------------------------------

def test_guard_flags_a_banned_upstream_import(tmp_path):
    (tmp_path / "bad.py").write_text("import nautilus_trader\n")
    (tmp_path / "ok.py").write_text("# mentions nautilus_trader in a comment\nx = 1\n")
    violations = w1.guard_reference_only_absent(tmp_path)
    assert len(violations) == 1
    assert violations[0]["file"] == "bad.py"


def test_guard_proves_upstream_absent_from_stratex():
    if not (STRATEX_DIR / "repo_wave1.py").exists():
        pytest.skip("Stratex tree not present in this checkout layout")
    violations = w1.guard_reference_only_absent(STRATEX_DIR)
    assert violations == [], f"upstream packages in production paths: {violations}"


def test_reference_only_registry_covers_all_four():
    assert set(w1.WAVE1_REFERENCE_ONLY) == {
        "agiprolabs/claude-trading-skills", "ErTasselli/openterminal",
        "nautechsystems/nautilus_trader", "TauricResearch/TradingAgents"}
    assert set(w1.WAVE1_ADAPTED) == {
        "Jakeschincariol/day-trader-skill", "tradermonty/claude-trading-skills"}
    for entry in w1.WAVE1_REFERENCE_ONLY.values():
        assert entry["fit"] == "reference-only" and entry["license"]


# --- allowlist load scan ------------------------------------------------------

def test_scan_allowlist_covers_every_symbol():
    bars = w1.bars_from_candles([list(r) for r in LIVE_BARS_RAW])
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    out = w1.scan_allowlist(symbols, bars, 10_556.99, 10_556.99,
                            now=bars[-1].ts + 60,
                            config={"timemachine_replays": 100})
    assert out["symbols"] == 3
    assert set(out["results"]) == set(symbols)
    assert sum(out["counts"].values()) == 3
    assert out["elapsed_sec"] >= 0


def test_run_wave1_cycle_returns_decision_and_ledger_flag():
    bars = _orb_bars()
    d = w1.run_wave1_cycle("BTCUSDT", bars, 10_000.0, 10_000.0,
                           now=bars[-1].ts + 60,
                           ledger_filepath="/tmp/wave1-nope.jsonl")
    assert d["verdict"] == "GO"
    assert isinstance(d["ledger_appended"], bool)
