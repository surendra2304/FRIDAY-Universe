"""run_fxsession.py — the ONE declared run for TASK-STR-RD-018
(FX Asia-Range Fade), when the coordinator orders it.

Judges the frozen declaration (fxsession_declaration.json) against a
staged, provenance-verified panel. This script refuses to run if:
  - the declaration file's SHA-256 != --expected-declaration-sha256
    (the value frozen in the declaring PR / issue #35 claim);
  - the panel provenance does not verify (file hashes / row counts);
  - --declared-run is absent (the run protocol attestation: panel
    verified first, holdout trades/metrics never computed or
    inspected before this evaluation — declaration element H5).

It executes the engine at 1x costs (3 bps/side) and at the 2x shadow
(6 bps/side), assigns OOS folds by entry time per walkforward.FOLDS,
and applies every element of the declared bar. Output: a summary on
stdout and results.json in --out. Research only; demo only; nothing
here places or simulates a live order.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fxsession import Bar, Trade, generate_trades  # noqa: E402

FOLDS = [
    ("W1", "2024-07-01", "2025-01-01"),
    ("W2", "2025-01-01", "2025-07-01"),
    ("W3", "2025-07-01", "2026-01-01"),
    ("W4", "2026-01-01", "2026-07-01"),
    ("W5", "2026-07-01", "2026-11-01"),
]
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
SLIP_1X = 3.0
SLIP_2X = 6.0


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _date_bound(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def load_panel(panel_dir: Path) -> dict[str, list[Bar]]:
    prov_path = panel_dir / "panel_provenance.json"
    if not prov_path.exists():
        raise SystemExit("panel_provenance.json missing — panel not staged/verified")
    prov = json.loads(prov_path.read_text())
    panel: dict[str, list[Bar]] = {}
    for sym in SYMBOLS:
        name = f"{sym}.csv"
        meta = prov.get("files", {}).get(name)
        if meta is None:
            raise SystemExit(f"provenance missing entry for {name}")
        raw = (panel_dir / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
            raise SystemExit(f"hash mismatch for {name} — panel does not verify")
        bars: list[Bar] = []
        with (panel_dir / name).open(newline="") as fh:
            for row in csv.DictReader(fh):
                bars.append(Bar(
                    ts=_parse_ts(row["time"]),
                    open=float(row["open"]), high=float(row["high"]),
                    low=float(row["low"]), close=float(row["close"]),
                    complete=row["complete"].strip().lower() in ("true", "1"),
                ))
        if len(bars) != meta["rows"]:
            raise SystemExit(f"row-count mismatch for {name} — panel does not verify")
        bars.sort(key=lambda b: b.ts)
        panel[sym] = bars
    return panel


def metrics(trades: list[Trade]) -> dict:
    n = len(trades)
    if n == 0:
        return {"trades": 0, "expectancy_net": None, "profit_factor_net": None,
                "total_net": 0.0, "win_rate": None}
    rets = [t.ret_net for t in trades]
    pos = sum(r for r in rets if r > 0)
    neg = -sum(r for r in rets if r < 0)
    pf = (pos / neg) if neg > 0 else float("inf")
    return {"trades": n, "expectancy_net": sum(rets) / n,
            "profit_factor_net": pf, "total_net": sum(rets),
            "win_rate": sum(1 for r in rets if r > 0) / n}


def _betacf(a: float, b: float, x: float) -> float:
    MAXIT, EPS, FPMIN = 200, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(lbeta)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _t_cdf(t: float, df: int) -> float:
    """CDF of Student's t with df degrees of freedom."""
    x = df / (df + t * t)
    ib = _betainc(df / 2.0, 0.5, x)
    return 1.0 - 0.5 * ib if t >= 0 else 0.5 * ib


def t_test_one_sided_greater(rets: list[float]) -> float:
    """p-value for H1: mean > 0 (one-sided t-test)."""
    n = len(rets)
    if n < 2:
        return 1.0
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    if var <= 0.0:
        return 0.0 if mean > 0 else 1.0
    t = mean / math.sqrt(var / n)
    return 1.0 - _t_cdf(t, n - 1)


def fold_of(ts: datetime) -> str | None:
    for fid, s, e in FOLDS:
        if _date_bound(s) <= ts < _date_bound(e):
            return fid
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel-dir", required=True)
    ap.add_argument("--declaration", required=True)
    ap.add_argument("--expected-declaration-sha256", required=True)
    ap.add_argument("--programme-trials", type=int, required=True,
                    help="programme executed-trial counter at run time; "
                         "N_run = this + 1 (this family's single cell)")
    ap.add_argument("--declared-run", action="store_true",
                    help="attest the run protocol (H5): panel verified "
                         "first; holdout never previously computed/inspected")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if not args.declared_run:
        raise SystemExit("refusing to judge: --declared-run attestation required (H5)")

    decl_raw = Path(args.declaration).read_bytes()
    digest = hashlib.sha256(decl_raw).hexdigest()
    if digest != args.expected_declaration_sha256:
        raise SystemExit(f"declaration hash mismatch: {digest} != "
                         f"{args.expected_declaration_sha256}")
    decl = json.loads(decl_raw)
    if decl.get("task_id") != "TASK-STR-RD-018" or decl.get("cells") != 1:
        raise SystemExit("declaration identity/cell check failed")

    panel = load_panel(Path(args.panel_dir))

    trades_1x: list[Trade] = []
    trades_2x: list[Trade] = []
    for sym in SYMBOLS:
        trades_1x.extend(generate_trades(panel[sym], sym, SLIP_1X))
        trades_2x.extend(generate_trades(panel[sym], sym, SLIP_2X))

    oos = [t for t in trades_1x if fold_of(t.entry_time) is not None]
    oos2 = [t for t in trades_2x if fold_of(t.entry_time) is not None]
    per_fold = {fid: metrics([t for t in oos if fold_of(t.entry_time) == fid])
                for fid, _, _ in FOLDS}
    per_symbol = {sym: metrics([t for t in oos if t.symbol == sym])
                  for sym in SYMBOLS}
    pooled = metrics(oos)
    pooled2 = metrics(oos2)

    pos_folds = sum(1 for m in per_fold.values()
                    if (m["expectancy_net"] or 0.0) > 0 and m["trades"] > 0)

    dev_oos = [t for t in oos if fold_of(t.entry_time) != "W5"]
    hold = [t for t in oos if fold_of(t.entry_time) == "W5"]
    m_dev, m_hold = metrics(dev_oos), metrics(hold)
    fold_profits = {fid: per_fold[fid]["total_net"] for fid, _, _ in FOLDS}
    total_pos_folds = sum(p for p in fold_profits.values() if p > 0)
    fold_conc = (max(fold_profits.values()) / total_pos_folds
                 if total_pos_folds > 0 else 1.0)
    holdout = {
        "H1_holdout_trades_gte_20": m_hold["trades"] >= 20,
        "H2_holdout_expectancy_gt_0": (m_hold["expectancy_net"] or 0.0) > 0,
        "H3_dev_oos_expectancy_gt_0": (m_dev["expectancy_net"] or 0.0) > 0,
        "H4_fold_concentration_lte_0.80": total_pos_folds > 0 and fold_conc <= 0.80,
        "H5_burn_clause": "ATTESTED_BY_RUN_PROTOCOL (--declared-run)",
        "holdout_metrics": m_hold, "dev_oos_metrics": m_dev,
        "max_fold_profit_share": fold_conc,
    }
    holdout_pass = all(holdout[k] for k in
                       ("H1_holdout_trades_gte_20", "H2_holdout_expectancy_gt_0",
                        "H3_dev_oos_expectancy_gt_0",
                        "H4_fold_concentration_lte_0.80"))

    pos_syms = [s for s in SYMBOLS
                if per_symbol[s]["trades"] >= 20
                and (per_symbol[s]["expectancy_net"] or 0.0) > 0]
    sym_profits = {s: per_symbol[s]["total_net"] for s in SYMBOLS}
    total_pos_syms = sum(p for p in sym_profits.values() if p > 0)
    max_sym_share = (max(sym_profits.values()) / total_pos_syms
                     if total_pos_syms > 0 else 1.0)
    breadth_pass = len(pos_syms) >= 2 and total_pos_syms > 0 and max_sym_share <= 0.80

    n_run = args.programme_trials + 1
    alpha = 0.05 / n_run
    p_value = t_test_one_sided_greater([t.ret_net for t in oos])

    pf = pooled["profit_factor_net"]
    checks = {
        "pooled_expectancy_gt_0": (pooled["expectancy_net"] or 0.0) > 0,
        "pooled_pf_gte_1.2_finite": pf is not None and pf != float("inf") and pf >= 1.2,
        "min_oos_trades_200": pooled["trades"] >= 200,
        "positive_folds_gte_4_of_5": pos_folds >= 4,
        "cost_shadow_2x": ((pooled2["expectancy_net"] or 0.0) > 0
                           and pooled2["profit_factor_net"] is not None
                           and pooled2["profit_factor_net"] != float("inf")
                           and pooled2["profit_factor_net"] >= 1.2),
        "bonferroni": p_value < alpha,
        "temporal_holdout_v1": holdout_pass,
        "breadth": breadth_pass,
    }

    if pooled["trades"] < 200:
        verdict = "INSUFFICIENT_OOS_TRADES"
    elif all(checks.values()):
        verdict = "PROVEN"
    else:
        verdict = "FAIL"
    delete = (verdict == "FAIL" and pf is not None and pf < 1.2)

    result = {
        "task_id": "TASK-STR-RD-018",
        "declaration_sha256": digest,
        "n_run": n_run, "bonferroni_alpha": alpha, "bonferroni_p_value": p_value,
        "pooled_oos": pooled, "pooled_oos_2x_costs": pooled2,
        "per_fold": per_fold, "per_symbol_oos": per_symbol,
        "positive_folds": pos_folds,
        "temporal_holdout": holdout,
        "breadth": {"positive_symbols_min20": pos_syms,
                    "max_symbol_profit_share": max_sym_share,
                    "passes": breadth_pass},
        "checks": checks, "verdict": verdict,
        "delete_per_owner_rule": delete,
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps(result, indent=2, default=str))
    print(f"\nVERDICT: {verdict}" + (" — DELETE (OOS PF < 1.2)" if delete else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
