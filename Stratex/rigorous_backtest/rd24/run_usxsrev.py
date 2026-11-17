#!/usr/bin/env python3
"""Declared runner for TASK-STR-RD-024 — family `us_xs_reversal`.

Executes the frozen run procedure of declaration/USXSREV_DECLARATION.md:
verify the panel's provenance (hashes, declared parameters, data-gate
record) -> run each frozen cell ONCE at 1x and 2x costs -> hash-pin the
trade lists -> compute metrics and judge -> write the run record.

Refuses (exit 2) if the provenance does not verify: a panel that fails
verification is not run, per the declaration. This script is NOT run
against real data by the declaring package — no panel exists yet and
the project's Alpaca keys are installed with the SRS execution.

Usage:
  python3 run_usxsrev.py --panel-dir DIR --n-final N --out DIR
    --panel-dir  contains panel.csv, dividends.csv, provenance.json,
                 iex_panel.csv (gate check 2 companion, addendum v1)
    --n-final    the FINAL global trial counter read from the
                 rd-reconcile ledger at run time (frozen method:
                 Bonferroni alpha = 0.05 / N_final)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usxsrev as U  # noqa: E402

DECLARED_FEED = "sip"
DECLARED_ADJUSTMENT = "split"
DECLARED_START = "2023-01-01T00:00:00Z"
DECLARED_END = "2026-11-01T00:00:00Z"
FEED_RATIO_MIN = 5.0  # gate check 2 AS AMENDED by USXSREV_ADDENDUM_V1.md:
# the declaration's frozen absolute floor (median daily volume >=
# 2,000,000) is superseded by a relative SIP-vs-IEX discriminator —
# every symbol's SIP median daily volume must be >= FEED_RATIO_MIN x
# its IEX median over the identical span, and so must the universe
# aggregate. The declaration file itself is unchanged.
GATE_KEYS = ["session_census", "sip_feed_check", "split_check",
             "cross_source_spot_check", "dividend_calendar_check"]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def refuse(msg: str) -> None:
    print(f"REFUSED: {msg}", file=sys.stderr)
    sys.exit(2)


def load_and_verify(panel_dir: Path):
    panel_csv = panel_dir / "panel.csv"
    div_csv = panel_dir / "dividends.csv"
    prov_path = panel_dir / "provenance.json"
    for p in (panel_csv, div_csv, prov_path):
        if not p.exists():
            refuse(f"missing {p.name}")
    prov = json.loads(prov_path.read_text())
    if prov.get("feed") != DECLARED_FEED:
        refuse(f"provenance feed {prov.get('feed')!r} != declared 'sip'")
    if prov.get("adjustment") != DECLARED_ADJUSTMENT:
        refuse("provenance adjustment != declared 'split'")
    if prov.get("start") != DECLARED_START or prov.get("end") != DECLARED_END:
        refuse("provenance span != declared 2023-01-01 -> 2026-11-01 (UTC)")
    if sorted(prov.get("universe", [])) != sorted(U.UNIVERSE):
        refuse("provenance universe != the frozen 30-name list")
    if sha256_file(panel_csv) != prov.get("panel_sha256"):
        refuse("panel.csv SHA-256 does not match the provenance record")
    if sha256_file(div_csv) != prov.get("dividends_sha256"):
        refuse("dividends.csv SHA-256 does not match the provenance record")
    gate = prov.get("gate") or {}
    missing = [k for k in GATE_KEYS if gate.get(k) != "pass"]
    if missing:
        refuse(f"data gate not passed for: {missing}")
    raw = pd.read_csv(panel_csv, parse_dates=["date"])
    counts = raw.groupby("symbol").size().to_dict()
    declared_counts = prov.get("per_symbol_counts") or {}
    for sym in U.UNIVERSE:
        if counts.get(sym) != declared_counts.get(sym):
            refuse(f"bar count for {sym} does not match provenance "
                   f"({counts.get(sym)} != {declared_counts.get(sym)})")
    # gate check 2, enforced mechanically, AS AMENDED by
    # USXSREV_ADDENDUM_V1.md (relative SIP-vs-IEX discriminator,
    # clauses (a)-(d) of its section 3)
    med_vol = raw.groupby("symbol")["volume"].median().to_dict()
    iex_csv = panel_dir / "iex_panel.csv"
    if not iex_csv.exists():
        refuse("missing iex_panel.csv (gate check 2 companion, "
               "addendum v1)")
    if sha256_file(iex_csv) != prov.get("iex_panel_sha256"):
        refuse("iex_panel.csv SHA-256 does not match the provenance "
               "record")
    iex_raw = pd.read_csv(iex_csv)
    iex_counts = iex_raw.groupby("symbol").size().to_dict()
    for sym in U.UNIVERSE:
        if iex_counts.get(sym) != counts.get(sym):
            refuse(f"IEX bar count for {sym} does not match the SIP "
                   f"panel ({iex_counts.get(sym)} != "
                   f"{counts.get(sym)})")
    iex_med = iex_raw.groupby("symbol")["volume"].median().to_dict()
    ratios = {s: med_vol[s] / iex_med[s] for s in U.UNIVERSE}
    low = [s for s, r in ratios.items() if r < FEED_RATIO_MIN]
    if low:
        refuse(f"SIP/IEX median-volume ratio below {FEED_RATIO_MIN} "
               f"for: {low}")
    agg_ratio = sum(med_vol.values()) / sum(iex_med.values())
    if agg_ratio < FEED_RATIO_MIN:
        refuse(f"universe aggregate SIP/IEX median-volume ratio "
               f"{agg_ratio:.2f} below {FEED_RATIO_MIN}")
    panel: dict[str, pd.DataFrame] = {}
    for sym, g in raw.groupby("symbol"):
        df = g.copy()
        df["ts"] = pd.to_datetime(df["date"], utc=True).dt.normalize()
        df = df.set_index("ts").sort_index()
        panel[str(sym)] = df[["open", "high", "low", "close", "volume"]] \
            .astype(float)
    div_raw = pd.read_csv(div_csv, parse_dates=["ex_date"])
    dividends: dict[str, list] = {}
    for _, row in div_raw.iterrows():
        ex = pd.to_datetime(row["ex_date"], utc=True).normalize()
        dividends.setdefault(str(row["symbol"]), []).append(
            (ex, float(row["amount"])))
    return panel, dividends, prov


def trades_to_frame(trades) -> pd.DataFrame:
    return pd.DataFrame([{
        "symbol": t.symbol,
        "entry_time": t.entry_time.isoformat(),
        "exit_time": t.exit_time.isoformat(),
        "side": t.side,
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "net_return": t.net_return,
        "exit_reason": t.exit_reason,
        "borrow_charge": t.borrow_charge,
        "dividend_adjustment": t.dividend_adjustment,
    } for t in trades])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel-dir", required=True)
    ap.add_argument("--n-final", required=True, type=int,
                    help="final global trial counter from the ledger")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    panel_dir = Path(args.panel_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    panel, dividends, prov = load_and_verify(panel_dir)

    # Step 3 of the frozen procedure: execute once, hash-pin the
    # trade lists BEFORE any metric is computed from them.
    cell_trades: dict[str, dict[str, list]] = {}
    trade_list_sha: dict[str, str] = {}
    for cell, lookback in U.CELLS.items():
        cell_trades[cell] = {}
        for level, costs in (("1x", U.COSTS_1X), ("2x", U.COSTS_2X)):
            trades, _entries = U.run_cell(panel, dividends, lookback, costs)
            cell_trades[cell][level] = trades
            f = out_dir / f"trades_{cell}_{level}.csv"
            trades_to_frame(trades).to_csv(f, index=False)
            trade_list_sha[f"{cell}_{level}"] = sha256_file(f)

    # DSR reporting input: per-trade Sharpe dispersion across this
    # family's two cells (reported, not judged — see declaration).
    srs = []
    for cell in U.CELLS:
        oos = U.trades_in_window(cell_trades[cell]["1x"],
                                 U.FOLDS[0][1], U.FOLDS[-1][2])
        st = U.trade_stats(oos)
        if st["sharpe_per_trade"] is not None:
            srs.append(st["sharpe_per_trade"])
    sr_std = float(pd.Series(srs).std(ddof=1)) if len(srs) == 2 else None

    # Steps 4-6: metrics, the single temporal-holdout evaluation
    # (inside judge_cell), verdicts, full report.
    results = {
        "task": "TASK-STR-RD-024",
        "family": "us_xs_reversal",
        "n_final": args.n_final,
        "bonferroni_alpha": 0.05 / max(1, args.n_final),
        "harness_sha256": sha256_file(Path(U.__file__)),
        "provenance": {
            "panel_sha256": prov.get("panel_sha256"),
            "dividends_sha256": prov.get("dividends_sha256"),
            "feed": prov.get("feed"), "adjustment": prov.get("adjustment"),
            "start": prov.get("start"), "end": prov.get("end"),
        },
        "trade_list_sha256": trade_list_sha,
        "run_procedure_note": "trade lists were written and hash-pinned "
                              "before any metric was computed; the W5 "
                              "temporal holdout was evaluated exactly "
                              "once, by this run (H5 burn clause).",
        "cells": {},
    }
    for cell in U.CELLS:
        judged = U.judge_cell(cell_trades[cell]["1x"],
                              cell_trades[cell]["2x"],
                              U.UNIVERSE, args.n_final,
                              dsr_sr_std=sr_std)
        oos_1x = U.trades_in_window(cell_trades[cell]["1x"],
                                    U.FOLDS[0][1], U.FOLDS[-1][2])
        legs = {}
        for name, subset in (
                ("full_book", oos_1x),
                ("long_leg", [t for t in oos_1x if t.side == "LONG"]),
                ("short_leg", [t for t in oos_1x if t.side == "SHORT"])):
            m = U.trade_metrics(subset)
            legs[name] = {"trades": m["trades"],
                          "expectancy_net": m["expectancy_net"],
                          "profit_factor_net": m["profit_factor_net"]}
        results["cells"][cell] = {**judged, "leg_reporting_1x": legs}
    (out_dir / "results.json").write_text(
        json.dumps(results, indent=2, default=str))
    print(json.dumps({c: results["cells"][c]["verdict"] for c in U.CELLS},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
