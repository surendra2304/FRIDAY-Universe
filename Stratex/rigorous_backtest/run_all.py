"""End-to-end runner for the rigorous backtest programme (TASK-STR-BT-001).

Phases:
  governed   — bb_reversion, factory_winner_1..5 (deployed modules),
               supertrend, adx_ema, each on its governed timeframe.
  factory    — the 204-variant walk-forward selection re-run, plus the
               original five variants' out-of-sample record.
  discovery  — the wider strategy library on its inferred timeframe.
  validate   — replication check: this harness's factory simulator vs the
               legacy mass_backtester function, on real data, zero friction.
  assemble   — merge phase outputs into the final results JSON + summary.

Every phase writes a JSON artifact (write-verified) and prints a compact
summary. Data is fetched fresh from the Binance Vision archive (or read
from a hash-verified cache) — see data_feed.py. Nothing here writes to
production code, config or governance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import pandas as pd

from .data_feed import Dataset, load_dataset, resample_dataset
from .factory_eval import evaluate_factory
from .module_eval import evaluate_module
from .simulator import Costs
from .walkforward import oos_report

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
COSTS = Costs()  # 5 bps fee + 3 bps spread/slippage per side (16 bps RT)

GOVERNED = [
    # (module_name, timeframe)
    ("strategy_bb_reversion", "15m"),
    ("strategy_factory_winner_1", "5m"),
    ("strategy_factory_winner_2", "5m"),
    ("strategy_factory_winner_3", "5m"),
    ("strategy_factory_winner_4", "5m"),
    ("strategy_factory_winner_5", "15m"),
    ("strategy_supertrend", "15m"),
    ("strategy_adx_ema", "4h"),
]
ORIGINAL_FIVE_VARIANT_IDS = [182, 181, 183, 184, 187]  # winners #1..#5 in factory_results.md


def write_verified(path: Path, payload: dict) -> str:
    blob = json.dumps(payload, indent=2, default=str).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()
    for attempt in range(5):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
            if hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                return digest
        except OSError:
            pass
        time.sleep(1 + attempt)
    raise RuntimeError(f"could not write verified artifact: {path}")


def load_all_datasets(cache_dir: Path | None) -> dict[str, dict[str, Dataset]]:
    datasets: dict[str, dict[str, Dataset]] = {}
    plan = {"5m": ("2023-12", "2026-10"), "15m": ("2023-10", "2026-10"),
            "1h": ("2023-10", "2026-10")}
    for tf, (sm, em) in plan.items():
        datasets[tf] = {}
        for sym in SYMBOLS:
            ds = load_dataset(sym, tf, sm, em, cache_dir=cache_dir)
            datasets[tf][sym] = ds
            print(f"[data] {ds.key}: {len(ds.df)} bars, gaps={ds.manifest['gap_audit']['missing_bars']}, "
                  f"sha={ds.manifest['csv_sha256'][:12]}", flush=True)
    datasets["4h"] = {sym: resample_dataset(ds, "4h") for sym, ds in datasets["1h"].items()}
    datasets["1d"] = {sym: resample_dataset(ds, "1d") for sym, ds in datasets["1h"].items()}
    return datasets


def provenance_block(datasets: dict[str, dict[str, Dataset]]) -> dict:
    out = {}
    for tf, per in datasets.items():
        for sym, ds in per.items():
            out[ds.key] = ds.manifest
    return out


def phase_governed(stratex_root: Path, datasets, out_dir: Path) -> dict:
    rows = []
    search_paths = [str(stratex_root), str(stratex_root / "strategies")]
    for module_name, tf in GOVERNED:
        file_path = stratex_root / f"{module_name}.py"
        print(f"[governed] {module_name} on {tf} ...", flush=True)
        row = evaluate_module(module_name, file_path, search_paths, datasets[tf], COSTS)
        row["scope"] = "governed"
        rows.append(row)
        po = row.get("pooled_oos") or {}
        print(f"[governed] {module_name}: status={row['status']} trades={po.get('trades')} "
              f"exp={po.get('expectancy_net')} pf={po.get('profit_factor_net')}", flush=True)
    payload = {"phase": "governed", "costs": COSTS.describe(), "rows": rows}
    write_verified(out_dir / "phase_governed.json", payload)
    return payload


def phase_factory(stratex_root: Path, datasets, out_dir: Path) -> dict:
    variants = json.loads((stratex_root / "research" / "strategy_factory" /
                           "strategy_variations.json").read_text(encoding="utf-8"))
    factory_datasets = {tf: datasets[tf] for tf in ("5m", "15m", "1h")}
    print(f"[factory] evaluating {len(variants)} variants walk-forward ...", flush=True)
    result = evaluate_factory(variants, factory_datasets, COSTS)
    variant_trades = result.pop("variant_trades")
    original_five = []
    name_by_id = {v["id"]: v["name"] for v in variants}
    for vid in ORIGINAL_FIVE_VARIANT_IDS:
        rep = oos_report(variant_trades[vid])
        original_five.append({"variant_id": vid, "name": name_by_id[vid], **rep})
    payload = {
        "phase": "factory",
        "costs": COSTS.describe(),
        "variants_tried": len(variants),
        "selection_rule": "per fold: rank all variants on in-sample trades only (net PF, then win rate — the legacy sort key); top 5 judged on the fold's out-of-sample trades only",
        "folds": result["folds"],
        "procedure_pooled_oos": result["procedure_pooled_oos"],
        "original_five_oos": original_five,
    }
    write_verified(out_dir / "phase_factory.json", payload)
    print(f"[factory] procedure pooled OOS: {payload['procedure_pooled_oos']}", flush=True)
    return payload


def _infer_primary_timeframe(file_path: Path) -> str:
    """Mirror of the registry's docstring inference (read-only replica)."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")[:4000]
    except OSError:
        return "1h"
    for tf in ("5m", "15m", "1h", "4h", "1d"):
        if tf in text:
            return tf
    return "1h"


def phase_discovery(stratex_root: Path, datasets, out_dir: Path) -> dict:
    search_paths = [str(stratex_root), str(stratex_root / "strategies")]
    governed_names = {name for name, _ in GOVERNED} | {"strategy_factory_winners"}
    try:
        sys.path.insert(0, str(stratex_root))
        from config_strategy import PRODUCTION_STRATEGY_REGISTRY as _REG
    except Exception:
        _REG = {}

    def gov_status(module_name: str) -> str:
        key = module_name[len("strategy_"):] if module_name.startswith("strategy_") else module_name
        entry = _REG.get(key)
        return str(entry.get("status") or "UNREGISTERED").upper() if entry else "UNREGISTERED"

    candidates: list[tuple[str, Path]] = []
    for fp in sorted(stratex_root.glob("strategy_*.py")):
        if fp.stem not in governed_names:
            candidates.append((fp.stem, fp))
    strat_dir = stratex_root / "strategies"
    for fp in sorted(strat_dir.glob("*.py")):
        if fp.stem.startswith("__") or fp.stem == "strategy_registry":
            continue
        candidates.append((fp.stem, fp))

    rows = []
    for module_name, fp in candidates:
        tf = _infer_primary_timeframe(fp)
        if tf == "1m":
            rows.append({"strategy": module_name, "label": "BACKTEST-OOS", "scope": "discovery",
                         "status": "UNTESTABLE", "governance_status": gov_status(module_name),
                         "reason": "1m strategy: no 1m dataset in this programme (compute/scope); "
                                   "1m taker friction also exceeds these strategies' target geometry per config notes"})
            continue
        print(f"[discovery] {module_name} on {tf} ...", flush=True)
        try:
            row = evaluate_module(module_name, fp, search_paths, datasets[tf], COSTS)
        except Exception as exc:  # noqa: BLE001 - harness-level guard; recorded
            row = {"strategy": module_name, "label": "BACKTEST-OOS", "status": "BROKEN",
                   "reason": f"harness-level failure: {type(exc).__name__}: {exc}"}
        row["scope"] = "discovery"
        row["governance_status"] = gov_status(module_name)
        rows.append(row)
        po = row.get("pooled_oos") or {}
        print(f"[discovery] {module_name}: status={row['status']} trades={po.get('trades')} "
              f"exp={po.get('expectancy_net')} pf={po.get('profit_factor_net')}", flush=True)
    payload = {"phase": "discovery", "costs": COSTS.describe(), "rows": rows}
    write_verified(out_dir / "phase_discovery.json", payload)
    return payload


def phase_validate(stratex_root: Path, datasets, out_dir: Path) -> dict:
    """Replication check vs the legacy mass_backtester on real data."""
    import types

    stub = types.ModuleType("data_client")

    class _StubClient:  # pragma: no cover - import stub only
        pass

    stub.MarketDataClient = _StubClient
    sys.modules.setdefault("data_client", stub)
    sys.path.insert(0, str(stratex_root))
    spec = importlib.util.spec_from_file_location(
        "legacy_mass_backtester",
        stratex_root / "research" / "strategy_factory" / "mass_backtester.py")
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    from .factory_eval import compute_atr, variant_signals, simulate_variant

    variants = json.loads((stratex_root / "research" / "strategy_factory" /
                           "strategy_variations.json").read_text(encoding="utf-8"))
    by_id = {v["id"]: v for v in variants}
    zero = Costs(0.0, 0.0)
    checks = []
    for vid in (182, 181, 183, 184, 187, 139, 60, 12):
        v = by_id[vid]
        ds = datasets[v["timeframe"]]["BTCUSDT"]
        legacy_pnls = legacy.backtest_strategy_on_df(ds.df.copy(), v, friction_bps=0.0)
        ls, ss = variant_signals(ds.df, v["type"], v["params"])
        atr = compute_atr(ds.df, 14).to_numpy()
        mine = simulate_variant(ds.df, ls, ss, atr, v["exits"]["sl_atr"],
                                v["exits"]["tp_atr"], "BTCUSDT", zero)
        mine_pnls = [t.net_return for t in mine]
        # The legacy function drops a position still open at the end; this
        # harness closes it. Compare on the common prefix.
        k = min(len(legacy_pnls), len(mine_pnls))
        max_dev = max((abs(a - b) for a, b in zip(legacy_pnls[:k], mine_pnls[:k])), default=0.0)
        checks.append({"variant_id": vid, "legacy_trades": len(legacy_pnls),
                       "harness_trades": len(mine_pnls), "compared": k,
                       "max_abs_deviation": max_dev,
                       "match": bool(max_dev < 1e-9 and abs(len(legacy_pnls) - len(mine_pnls)) <= 1)})
    payload = {"phase": "validate", "checks": checks,
               "all_match": all(c["match"] for c in checks)}
    write_verified(out_dir / "phase_validate.json", payload)
    print(f"[validate] all_match={payload['all_match']}", flush=True)
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stratex-root", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--cache-dir", default="")
    ap.add_argument("--phase", choices=["governed", "factory", "discovery", "validate", "all"],
                    default="all")
    args = ap.parse_args()
    stratex_root = Path(args.stratex_root)
    out_dir = Path(args.out_dir)
    cache_dir = Path(args.cache_dir) if args.cache_dir else None

    datasets = load_all_datasets(cache_dir)
    write_verified(out_dir / "data_provenance.json",
                   {"datasets": provenance_block(datasets), "costs": COSTS.describe()})

    if args.phase in ("validate", "all"):
        phase_validate(stratex_root, datasets, out_dir)
    if args.phase in ("governed", "all"):
        phase_governed(stratex_root, datasets, out_dir)
    if args.phase in ("factory", "all"):
        phase_factory(stratex_root, datasets, out_dir)
    if args.phase in ("discovery", "all"):
        phase_discovery(stratex_root, datasets, out_dir)
    print("[done]", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
