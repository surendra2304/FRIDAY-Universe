"""Tests for TASK-IG-STR-05 research_desk (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.research_desk import (FRAMEWORK_LENSES, PROMPT_LIBRARY, analyse,
                              chaos_lens, fractals_lens,
                              game_theory_lens, pattern_match, plan,
                              risk_checklist, risk_manager_pass, run_desk,
                              scan, scenario_analysis)

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


# --- TASK-STR-080: prompt set completion (prompts 1 + 3) -----------

def _downtrend_candles(n=40):
    return [{"high": 123 - i * 0.6, "low": 122 - i * 0.6,
             "close": 122.5 - i * 0.6} for i in range(n)]


def _flat_candles(n=40):
    return [{"high": 100.0, "low": 100.0, "close": 100.0}
            for _ in range(n)]


def test_prompt_library_has_all_three_prompts():
    assert sorted(PROMPT_LIBRARY) == ["prompt_1", "prompt_2", "prompt_3"]
    for key, entry in PROMPT_LIBRARY.items():
        assert entry["id"] == key
        for field in ("title", "verbatim_derived", "source",
                      "board_task", "implements"):
            assert entry[field], "%s missing %s" % (key, field)
        assert "DRSGKJXDAU4" in entry["source"]
    assert PROMPT_LIBRARY["prompt_1"]["board_task"] == "TASK-STR-080"
    assert PROMPT_LIBRARY["prompt_2"]["board_task"] == "TASK-STR-067"
    assert PROMPT_LIBRARY["prompt_3"]["board_task"] == "TASK-STR-080"
    import ig.research_desk as desk
    for entry in PROMPT_LIBRARY.values():
        assert callable(getattr(desk, entry["implements"]))


def test_scenario_analysis_commits():
    up = scenario_analysis(_uptrend_candles())
    assert up["status"] == "ok" and up["commit"] == "bullish"
    assert up["scenarios"]["bullish"]["share"] == 1.0
    assert up["close_call"] is False and up["margin"] == 1.0
    down = scenario_analysis(_downtrend_candles())
    assert down["commit"] == "bearish"
    assert down["scenarios"]["bearish"]["share"] == 1.0
    flat = scenario_analysis(_flat_candles())
    assert flat["commit"] == "sideways"
    assert flat["scenarios"]["sideways"]["share"] == 1.0
    assert flat["evidence"]["net_return_pct"] == 0.0


def test_scenario_analysis_shares_sum_to_one_and_flag_tracks_margin():
    for series in (_uptrend_candles(), _downtrend_candles(),
                   _flat_candles()):
        out = scenario_analysis(series)
        shares = [s["share"] for s in out["scenarios"].values()]
        assert abs(sum(shares) - 1.0) < 1e-12
        ranked = sorted(shares, reverse=True)
        assert abs(out["margin"] - (ranked[0] - ranked[1])) < 1e-12
        assert out["close_call"] is (out["margin"] < 0.05)


def test_scenario_analysis_insufficient_history():
    out = scenario_analysis(_flat_candles(10))
    assert out["status"] == "insufficient_history"
    assert out["commit"] is None
    assert "reason" in out


def test_risk_manager_pass_one_to_three_long():
    out = risk_manager_pass(SETUP, equity=10000.0,
                            risk_per_trade_pct=0.001)
    assert out["status"] == "ok" and out["passed"] is True
    assert out["stop_loss"] == 95.0
    assert out["take_profit"] == 115.0  # 100 + 3 * (100 - 95)
    assert abs(out["rr_ratio"] - 3.0) < 1e-12
    assert out["risk_amount"] == 10.0
    assert abs(out["units"] - 2.0) < 1e-12  # 10 / 5, same as plan()
    assert [c["name"] for c in out["checks"]] == [
        "stop_on_correct_side", "target_beyond_entry", "rr_is_target",
        "sizing_positive"]
    assert all(c["ok"] for c in out["checks"])


def test_risk_manager_pass_short_mirror_and_custom_rr():
    short = {**SETUP, "direction": "short", "invalidation": 105.0,
             "target": 87.5}
    out = risk_manager_pass(short, equity=10000.0,
                            risk_per_trade_pct=0.001)
    assert out["passed"] is True
    assert out["stop_loss"] == 105.0
    assert out["take_profit"] == 85.0  # 100 - 3 * (105 - 100)
    assert abs(out["rr_ratio"] - 3.0) < 1e-12
    two = risk_manager_pass(SETUP, 10000.0, 0.001, rr_target=2.0)
    assert two["take_profit"] == 110.0
    assert abs(two["rr_ratio"] - 2.0) < 1e-12


def test_risk_manager_pass_rejects_bad_setups():
    wrong_side = risk_manager_pass(
        {**SETUP, "invalidation": 105.0}, 10000.0, 0.001)
    assert wrong_side["status"] == "invalid_setup"
    assert wrong_side["passed"] is False
    assert wrong_side["stop_loss"] is None
    zero_risk = risk_manager_pass(
        {**SETUP, "invalidation": 100.0}, 10000.0, 0.001)
    assert zero_risk["status"] == "invalid_setup"
    bad_dir = risk_manager_pass(
        {**SETUP, "direction": "sideways"}, 10000.0, 0.001)
    assert bad_dir["status"] == "invalid_setup"
    bad_equity = risk_manager_pass(SETUP, 0.0, 0.001)
    assert bad_equity["status"] == "invalid_setup"


def test_run_desk_scenario_and_risk_sections():
    memo = run_desk([SETUP], CTX, {"BTCUSDT": _uptrend_candles()},
                    equity=10000.0, risk_per_trade_pct=0.001,
                    max_risk_pct=0.001)
    sc = memo["scenario_analyses"]["BTCUSDT"]
    assert sc["commit"] == "bullish"
    assert memo["summary"]["scenario_commits"] == {"BTCUSDT": "bullish"}
    rp = memo["risk_manager_passes"]["BTCUSDT"]
    assert rp["passed"] is True
    assert rp["take_profit"] == 115.0
    assert abs(rp["rr_ratio"] - 3.0) < 1e-12
    assert memo["summary"]["risk_passes_passed"] == 1


# --- TASK-STR-079: framework lenses (Chaos / Game Theory / Fractals) ---

def test_framework_lenses_library():
    assert sorted(FRAMEWORK_LENSES) == ["chaos", "fractals",
                                        "game_theory"]
    for key, entry in FRAMEWORK_LENSES.items():
        assert entry["id"] == key
        for field in ("title", "framing", "questions", "source",
                      "board_task", "implements"):
            assert entry[field], "%s missing %s" % (key, field)
        assert len(entry["questions"]) == 3
        assert "DUYHoUdD5vk" in entry["source"]
        assert entry["board_task"] == "TASK-STR-079"
    assert FRAMEWORK_LENSES["chaos"]["source"].startswith(
        "stratex package S-02")
    assert FRAMEWORK_LENSES["game_theory"]["source"].startswith(
        "stratex package S-03")
    assert FRAMEWORK_LENSES["fractals"]["source"].startswith(
        "stratex package S-04")
    import ig.research_desk as desk
    for entry in FRAMEWORK_LENSES.values():
        assert callable(getattr(desk, entry["implements"]))


def test_chaos_lens_flat_series_is_calm():
    out = chaos_lens(_flat_candles())
    assert out["status"] == "ok"
    assert out["sensitivity"]["label"] == "low"
    assert out["sensitivity"]["spread_pct"] == 0.0
    assert out["tail_moves"]["count"] == 0
    assert out["evidence"]["conditions_present"] == []
    assert len(out["questions"]) == 3
    assert all(q["question"] and q["answer"] and "evidence" in q
               for q in out["questions"])


def test_chaos_lens_planted_series_is_highly_sensitive():
    # The planted series has three similar windows whose forwards are
    # +3% / -3% / +3%: similar starts, divergent outcomes.
    out = chaos_lens(_planted_candles())
    assert out["status"] == "ok"
    assert out["sensitivity"]["similar_windows"] == 3
    assert abs(out["sensitivity"]["spread_pct"] - 6.0) < 1e-9
    assert out["sensitivity"]["label"] == "high"


def _break_candles():
    """40 daily candles: 30 flat at 100, then a violent 10-bar tail
    ending at a new low — volatility expansion + range break."""
    closes = [100.0] * 30 + [102.0, 98.0, 102.0, 98.0, 102.0,
                             98.0, 102.0, 98.0, 102.0, 96.0]
    return [{"high": c, "low": c, "close": c} for c in closes]


def test_chaos_lens_names_probability_shift_conditions():
    out = chaos_lens(_break_candles())
    assert out["status"] == "ok"
    by_name = {c["name"]: c
               for c in out["probability_shift_conditions"]}
    assert by_name["volatility_expansion"]["present"] is True
    assert by_name["range_break"]["present"] is True
    assert "broke below the low" in by_name["range_break"]["evidence"]
    assert set(out["evidence"]["conditions_present"]) == {
        "volatility_expansion", "range_break"}
    assert out["tail_moves"]["count"] > 0


def test_chaos_lens_insufficient_history():
    out = chaos_lens(_flat_candles(10))
    assert out["status"] == "insufficient_history"
    assert out["sensitivity"] is None
    assert "reason" in out


def test_game_theory_lens_crowded_longs_and_trap():
    out = game_theory_lens(_uptrend_candles(), SETUP)
    assert out["status"] == "ok"
    assert out["crowded_side"] == "longs"
    assert out["trap"]["trapped_side"] == "longs"
    # Window is the last 30 bars (i=10..39): low 105.0, high 123.4.
    assert out["trap"]["trigger"] == 105.0
    assert out["trap"]["move_pct"] < 0
    clusters = {c["side"]: c for c in out["stop_clusters"]}
    assert clusters["shorts"]["level"] == 123.4
    assert clusters["longs"]["level"] == 105.0
    # The setup question: entry 100 chases beyond the trap level
    # 105.0, and invalidation 95 sits beyond a stop-cluster level.
    assert len(out["questions"]) == 4
    assert "chases beyond the trap level" in out["questions"][3]["answer"]
    assert "invalidation sits beyond a stop-cluster level" in \
        out["questions"][3]["answer"]


def test_game_theory_lens_crowded_shorts():
    out = game_theory_lens(_downtrend_candles())
    assert out["crowded_side"] == "shorts"
    assert out["trap"]["trapped_side"] == "shorts"
    # Window is the last 30 bars (i=10..39): high 117.0, low 98.6.
    assert out["trap"]["trigger"] == 117.0
    assert out["trap"]["move_pct"] > 0
    assert len(out["questions"]) == 3  # no setup supplied


def test_game_theory_lens_flat_is_uncrowded():
    out = game_theory_lens(_flat_candles())
    assert out["crowded_side"] == "neither"
    assert out["trap"] is None
    assert "no crowded side to trap" in out["questions"][2]["answer"]


def test_game_theory_lens_insufficient_history():
    out = game_theory_lens(_flat_candles(10))
    assert out["status"] == "insufficient_history"
    assert out["crowded_side"] is None
    assert "reason" in out


def test_fractals_lens_uptrend_is_self_similar():
    out = fractals_lens(_uptrend_candles(100))
    assert out["status"] == "ok"
    assert out["self_similar"] is True
    assert out["agreement"] == 1.0
    assert out["majority_direction"] == "up"
    assert out["breaks"] == []
    assert all(d["direction"] == "up"
               for d in out["directions"].values())


def _mixed_scale_candles():
    """100-bar uptrend whose last 5 bars fall ~0.4%/bar: the 5-bar
    scale turns down while 10/30/60 stay up."""
    candles = _uptrend_candles(100)
    base = candles[95]["close"]
    for k in range(5):
        c = base * (1 - 0.004 * k)
        candles[95 + k] = {"high": c, "low": c, "close": c}
    return candles


def test_fractals_lens_mixed_scales_break():
    out = fractals_lens(_mixed_scale_candles())
    assert out["status"] == "ok"
    assert out["self_similar"] is False
    assert out["majority_direction"] == "up"
    assert abs(out["agreement"] - 0.75) < 1e-12
    assert [b["scale"] for b in out["breaks"]] == [5]
    assert out["directions"][5]["direction"] == "down"
    assert out["directions"][60]["direction"] == "up"
    smallest = out["questions"][2]
    assert "5-bar net" in smallest["answer"]
    assert "60-bar net" in smallest["answer"]


def test_fractals_lens_insufficient_history():
    out = fractals_lens(_uptrend_candles(40))
    assert out["status"] == "insufficient_history"
    assert out["self_similar"] is None
    assert "reason" in out


def test_run_desk_framework_lens_sections():
    memo = run_desk([SETUP], CTX, {"BTCUSDT": _planted_candles()},
                    equity=10000.0, risk_per_trade_pct=0.001,
                    max_risk_pct=0.001)
    lenses = memo["framework_lenses"]["BTCUSDT"]
    assert sorted(lenses) == ["chaos", "fractals", "game_theory"]
    assert all(lens["status"] == "ok" for lens in lenses.values())
    assert lenses["chaos"]["sensitivity"]["label"] == "high"
    # The planted series is up at 10/30/60 bars but down at 5 bars
    # (the current window's shape dips at its end) — a real break.
    assert lenses["fractals"]["self_similar"] is False
    assert lenses["fractals"]["majority_direction"] == "up"
    assert [b["scale"] for b in lenses["fractals"]["breaks"]] == [5]
    assert memo["summary"]["framework_lenses_issued"] == 1
    # The lenses change nothing else: same plan + checklist as before.
    assert memo["summary"]["plans_drafted"] == 1
    assert memo["summary"]["checklists_passed"] == 1