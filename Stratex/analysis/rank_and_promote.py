#!/usr/bin/env python3
"""rank_and_promote.py — OOS-disciplined strategy ranking + live integration artifacts.

Reads the server's backtest_results/stage_results.csv and:
  1. Ranks strategies by OOS expectancy (>= 30 OOS trades required by the
     registry's promotion policy; >= 15 for daily-TF strategies is accepted
     with a reduced evidence grade, clearly labeled).
  2. Requires OOS profit_factor >= 1.0 and net_pnl > 0 and IS net_pnl >= 0
     (a strategy that only works OOS or only IS is not promoted).
  3. Emits:
       - state/strategy_priors.json update proposal (win-rate priors from
         measured OOS win rates, blended 2/3 measured + 1/3 module prior to
         avoid overfitting single-window stats)
       - allowlist proposal for STRATEX_STRATEGY_ALLOWLIST
       - a promotion report with the exact numbers.

Nothing here edits live state directly: the proposal is printed and saved
to backtest_results/promotion_proposal.json; activation happens only after
owner-approved merge + deploy (fleet rule: no unauthorized live changes).

Usage (server): /opt/friday_universe/venv/bin/python rank_and_promote.py [--dry]
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

RESULTS = "/opt/friday_universe/backtest_results/stage_results.csv"
PROPOSAL_OUT = "/opt/friday_universe/backtest_results/promotion_proposal.json"
MODULE_PRIORS = {
    "strategy_multi_month": 0.40, "strategy_kama_adaptive": 0.42,
    "strategy_ehlers_hma": 0.42, "strategy_choppiness_breakout": 0.40,
    "strategy_kaufman_efficiency": 0.42, "strategy_bbi_blend": 0.42,
    "strategy_supertrend_atr": 0.42,
    # batch-1 (ZAI Agent 2 earlier)
    "strategy_donchian_turtle": 0.38, "strategy_vol_regime": 0.38,
    "strategy_momentum_rotation": 0.40, "strategy_pullback_ema": 0.40,
    # legacy strategies with module priors
    "strategy_channel_breakout": 0.37, "strategy_adx_trend": 0.41,
    "strategy_breakout_vol": 0.38, "strategy_atr_breakout": 0.39,
    "strategy_breakout_retest": 0.40, "strategy_fast_ema_cross": 0.55,
    "strategy_rsi_extreme": 0.53, "strategy_mean_reversion_scalper": 0.52,
    "strategy_vwap_scalper": 0.55, "strategy_scalping_breakout": 0.58,
    "strategy_rsi_divergence_scalper": 0.53,
}
MIN_TRADES_FULL = 30    # registry policy: full evidence
MIN_TRADES_DAILY = 15   # daily TF trades fewer times; reduced grade (labeled)
MIN_PF = 1.0


def load_rows():
    with open(RESULTS) as f:
        return list(csv.DictReader(f))


def _f(row, key):
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def main():
    rows = [r for r in load_rows() if not (r.get("error") or "").strip()]
    by = defaultdict(dict)
    for r in rows:
        by[(r["strategy"], r["symbol"], r["tf"])][r["tag"]] = r

    # Aggregate per (strategy, tf): sum OOS trades, weighted win rate, IS/OOS pnl
    agg = defaultdict(lambda: {"oos_trades": 0, "oos_wins": 0, "oos_pnl": 0.0,
                                "is_trades": 0, "is_pnl": 0.0, "pf_sum": 0.0,
                                "pf_n": 0, "symbols": 0})
    for (strat, sym, tf), tags in by.items():
        oos = tags.get("OOS")
        is_ = tags.get("IS")
        if not oos:
            continue
        a = agg[(strat, tf)]
        a["oos_trades"] += int(_f(oos, "trades"))
        a["oos_wins"] += _f(oos, "win_rate") * _f(oos, "trades")
        a["oos_pnl"] += _f(oos, "net_pnl")
        a["symbols"] += 1
        if is_:
            a["is_trades"] += int(_f(is_, "trades"))
            a["is_pnl"] += _f(is_, "net_pnl")
        pf = _f(oos, "profit_factor")
        if pf and pf < 50:  # ignore inf
            a["pf_sum"] += pf
            a["pf_n"] += 1

    candidates = []
    for (strat, tf), a in agg.items():
        if a["oos_trades"] == 0:
            continue
        min_trades = MIN_TRADES_DAILY if tf == "1d" else MIN_TRADES_FULL
        grade = "B (reduced: daily TF, fewer trades)" if (tf == "1d" and a["oos_trades"] < MIN_TRADES_FULL) else "A"
        if a["oos_trades"] < min_trades:
            continue
        wr = a["oos_wins"] / a["oos_trades"]
        avg_pf = a["pf_sum"] / a["pf_n"] if a["pf_n"] else 0.0
        exp_per_trade = a["oos_pnl"] / a["oos_trades"]
        candidates.append({
            "strategy": strat, "tf": tf, "grade": grade,
            "oos_trades": a["oos_trades"], "oos_win_rate": round(wr, 4),
            "oos_net_pnl": round(a["oos_pnl"], 2),
            "oos_expectancy_per_trade": round(exp_per_trade, 2),
            "avg_oos_pf": round(avg_pf, 3), "is_net_pnl": round(a["is_pnl"], 2),
            "symbols": a["symbols"],
            "promotable": bool(a["oos_pnl"] > 0 and avg_pf >= MIN_PF and a["is_pnl"] >= 0),
        })

    candidates.sort(key=lambda c: c["oos_expectancy_per_trade"], reverse=True)

    print("=" * 96)
    print(f"{'strategy':38s} {'tf':3s} {'grade':9s} {'oos_t':>6s} {'wr':>6s} "
          f"{'exp/t':>7s} {'pf':>6s} {'oos_pnl':>9s} {'is_pnl':>9s} {'promote':>8s}")
    print("=" * 96)
    for c in candidates:
        print(f"{c['strategy']:38s} {c['tf']:3s} {c['grade']:9s} {c['oos_trades']:6d} "
              f"{c['oos_win_rate']:6.2f} {c['oos_expectancy_per_trade']:7.2f} "
              f"{c['avg_oos_pf']:6.2f} {c['oos_net_pnl']:9.0f} {c['is_net_pnl']:9.0f} "
              f"{'YES' if c['promotable'] else 'no':>8s}")

    promotable = [c for c in candidates if c["promotable"]]

    # Priors proposal: blend measured OOS win rate with module prior
    priors = {}
    for c in promotable:
        base = MODULE_PRIORS.get(c["strategy"], 0.45)
        measured = c["oos_win_rate"]
        blended = round(min(0.70, max(0.20, 0.67 * measured + 0.33 * base)), 4)
        priors[c["strategy"]] = blended

    proposal = {
        "generated_at_ist": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "policy": "OOS net>0, avg OOS PF>=1.0, IS net>=0, min trades 30 (15 daily-TF, grade B)",
        "promotable": [{k: c[k] for k in ("strategy", "tf", "grade", "oos_trades",
                                          "oos_win_rate", "avg_oos_pf",
                                          "oos_net_pnl", "is_net_pnl")} for c in promotable],
        "strategy_priors_proposal": priors,
        "allowlist_proposal": sorted(priors.keys()),
        "activation": "Owner-approved merge + exact-head deploy; then set "
                      "STRATEX_STRATEGY_ALLOWLIST env + strategy_priors.json",
    }
    with open(PROPOSAL_OUT, "w") as f:
        json.dump(proposal, f, indent=2)
    print(f"\nproposal written: {PROPOSAL_OUT}")
    print(f"promotable strategies: {len(promotable)}")
    for c in promotable:
        print(f"  + {c['strategy']} ({c['tf']}): prior proposal {priors[c['strategy']]}")


if __name__ == "__main__":
    main()
