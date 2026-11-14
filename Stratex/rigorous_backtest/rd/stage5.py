"""STAGE 5 — synthesis (TASK-STR-RD-001).

Aggregates EVERYTHING this programme tested (plus the BT-001 governed /
factory baselines for context) into one ranked evidence table, applies
the pre-registered promotion bar + holdout check uniformly, and emits
the verdict. Code, not prose: the candidate list in the final report is
whatever this script computes — if it is empty, the report says NONE.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .common import PROMOTION_BAR, dump_json


def folds_positive(per_fold: dict | None) -> int | None:
    if not per_fold:
        return None
    n = 0
    for f in ("W1", "W2", "W3", "W4", "W5"):
        m = per_fold.get(f) or {}
        e = m.get("expectancy_net")
        if e is not None and e > 0:
            n += 1
    return n


def bar_from(pooled: dict | None, fp: int | None) -> bool | None:
    if not pooled or pooled.get("trades") in (None, 0):
        return None
    return bool((pooled.get("expectancy_net") or -9) > PROMOTION_BAR["expectancy_net_gt"] - 1
                and (pooled.get("expectancy_net") or -9) > 0
                and (pooled.get("profit_factor_net") or 0) >= PROMOTION_BAR["profit_factor_net_gte"]
                and pooled["trades"] >= PROMOTION_BAR["min_oos_trades"]
                and (fp is not None and fp >= PROMOTION_BAR["positive_folds_gte"]))


def row(source, name, pooled, per_fold=None, holdout_pass=None, note=""):
    pooled = pooled or {}
    fp = folds_positive(per_fold)
    return {
        "source": source, "name": name,
        "oos_trades": pooled.get("trades"),
        "win_rate": pooled.get("win_rate"),
        "expectancy_net": pooled.get("expectancy_net"),
        "profit_factor_net": pooled.get("profit_factor_net"),
        "max_drawdown_net": pooled.get("max_drawdown_net"),
        "folds_positive": fp,
        "passes_bar": bar_from(pooled, fp),
        "holdout_passes": holdout_pass,
        "note": note,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stratex-root", default=".")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    root = Path(args.stratex_root).resolve()
    out_dir = Path(args.out_dir)
    table: list[dict] = []

    # ---- BT-001 baselines (context) ----
    gov = json.loads((root / "rigorous_backtest" / "results" /
                      "phase_governed.json").read_text())
    for r in gov["rows"]:
        if r.get("status") == "EVALUATED":
            table.append(row("BT-001 governed", r["strategy"], r["pooled_oos"],
                             r["per_fold"], note=r.get("governance_status") or ""))
    fac = json.loads((root / "rigorous_backtest" / "results" /
                      "phase_factory.json").read_text())
    table.append(row("BT-001 factory", "honest_204_variant_selection",
                     fac["procedure_pooled_oos"], None,
                     note="the factory's own procedure, honestly re-run"))

    # ---- Stage 1: discovery (58) ----
    disc_path = out_dir / "phase_rd_discovery.json"
    if disc_path.exists():
        disc = json.loads(disc_path.read_text())
        for r in disc["rows"]:
            table.append(row("RD stage1 discovery", r["strategy"],
                             r.get("pooled_oos"), r.get("per_fold"),
                             note=f"status={r.get('status')} gov={r.get('governance_status')}"))

    # ---- Stage 2: adx_ema ----
    for part, key in (("stage2_partA.json", "configs"),
                      ("stage2_partB.json", "rows"),
                      ("stage2_partC.json", "rows"),
                      ("stage2_partD.json", "rows")):
        p = out_dir / part
        if not p.exists():
            continue
        payload = json.loads(p.read_text())
        for c in payload[key]:
            rep = c["report"]
            table.append(row(f"RD stage2 {part[6]}", f"adx_ema/{c['config']}",
                             rep["pooled_oos"], rep["per_fold"],
                             holdout_pass=(c.get("holdout") or {}).get("passes")))
    # ---- Stage 3: new families ----
    for p in sorted((out_dir / "stage3_rows").glob("*.json")):
        r = json.loads(p.read_text())
        rep = r["report"]
        table.append(row("RD stage3 new", f"{r['family']}/{r['variant']}",
                         rep["pooled_oos"], rep["per_fold"],
                         holdout_pass=(r.get("holdout") or {}).get("passes"),
                         note=f"tf={r['timeframe']}"))

    evaluated = [t for t in table if t["oos_trades"]]
    evaluated.sort(key=lambda t: (t["expectancy_net"] is not None,
                                  t["expectancy_net"] or -9), reverse=True)
    candidates = [t for t in evaluated
                  if t["passes_bar"] and t["holdout_passes"]]
    bar_only = [t for t in evaluated if t["passes_bar"] and not t["holdout_passes"]]
    synthesis = {
        "stage": 5,
        "promotion_bar": PROMOTION_BAR,
        "total_rows": len(table),
        "total_evaluated_with_trades": len(evaluated),
        "promotion_candidates": candidates,
        "passed_bar_failed_or_no_holdout": bar_only,
        "ranked_table": evaluated,
        "unevaluated_rows": [t for t in table if not t["oos_trades"]],
    }
    dump_json(out_dir / "stage5_synthesis.json", synthesis)
    print(f"[stage5] rows={len(table)} evaluated={len(evaluated)} "
          f"candidates={len(candidates)} bar_only={len(bar_only)}")
    for t in evaluated[:15]:
        print(f"  {t['expectancy_net']:+.4%} PF={t['profit_factor_net']} "
              f"n={t['oos_trades']} folds+={t['folds_positive']} "
              f"{t['source']} {t['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
