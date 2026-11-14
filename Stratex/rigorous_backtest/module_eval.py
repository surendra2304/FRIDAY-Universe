"""Evaluation of production strategy modules through their own get_signal().

The modules under test are imported READ-ONLY. Each is evaluated with the
exact function production calls, on real candles, under the MODULE
simulation convention (see simulator.py). Integrity guards:

- Feature causality: when a module (or the shared features module) provides
  add_features(), its output on a truncated series must match its output on
  the full series over the overlap — otherwise the features peek into the
  future and the strategy is UNTESTABLE (non-causal features).
- Execution sampling: get_signal() must run cleanly on sampled bars under
  the chosen pipeline before a full extraction is attempted.
- Compute guard: per-bar call cost is measured and projected; a module whose
  full extraction would exceed the budget is UNTESTABLE (compute-bound)
  rather than silently truncated.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .data_feed import Dataset
from .simulator import Costs, simulate_module
from .walkforward import oos_report

WARMUP_BARS = 260
WINDOW = 500


class ModuleProblem(RuntimeError):
    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


def _load_module(module_name: str, file_path: Path, search_paths: list[str]):
    for p in search_paths:
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ModuleProblem("BROKEN", f"cannot create import spec for {file_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001 - recorded as the verdict
        raise ModuleProblem("BROKEN", f"import failed: {type(exc).__name__}: {exc}") from exc
    return mod


def _extract(res) -> tuple[str, float, float] | None:
    if res is None:
        return None
    if isinstance(res, dict):
        side = res.get("side")
        sl = res.get("sl", res.get("stop_loss"))
        tp = res.get("tp", res.get("take_profit"))
    else:
        side = getattr(res, "side", None)
        sl = getattr(res, "sl", getattr(res, "stop_loss", None))
        tp = getattr(res, "tp", getattr(res, "take_profit", None))
    if side in ("BUY", "LONG"):
        side = "LONG"
    elif side in ("SELL", "SHORT"):
        side = "SHORT"
    else:
        return None
    if sl is None or tp is None:
        return None
    try:
        sl_f, tp_f = float(sl), float(tp)
    except (TypeError, ValueError):
        return None
    if sl_f <= 0 or tp_f <= 0:
        return None
    return side, sl_f, tp_f


def _features_causal(fn, df: pd.DataFrame) -> bool:
    """True when fn's features on truncated data match full-data features."""
    try:
        full = fn(df.copy())
    except Exception:
        return False
    for k in (1500, 6000):
        if len(df) <= k + 50:
            continue
        try:
            trunc = fn(df.iloc[:k].copy())
        except Exception:
            return False
        shared = [c for c in trunc.columns if c in full.columns
                  and pd.api.types.is_numeric_dtype(full[c])]
        if not shared:
            return False
        a = trunc[shared].to_numpy(dtype=float)
        b = full[shared].iloc[:k].to_numpy(dtype=float)
        if not np.allclose(a, b, rtol=1e-9, atol=1e-12, equal_nan=True):
            return False
    return True


def _try_pipeline(mod, df: pd.DataFrame, pipeline_name: str, fn) -> pd.DataFrame:
    work = fn(df.copy()) if fn is not None else df
    get_signal = mod.get_signal
    n = len(work)
    samples = [WARMUP_BARS + 10, n // 3, n // 2, (2 * n) // 3, n - 5]
    errors = 0
    for i in samples:
        if i <= 0 or i >= n:
            continue
        try:
            get_signal(work.iloc[max(0, i - WINDOW + 1): i + 1].copy())
        except Exception:
            errors += 1
    if errors > len(samples) // 2:
        raise ModuleProblem("BROKEN", f"get_signal raised on {errors}/{len(samples)} sampled bars under pipeline '{pipeline_name}'")
    return work


def evaluate_module(module_name: str, file_path: Path, search_paths: list[str],
                    datasets: dict[str, Dataset], costs: Costs,
                    max_seconds_per_symbol: float = 900.0) -> dict:
    """Evaluate one module across the given symbol datasets (single timeframe).

    Returns a result row dict. Never raises for module-level problems: they
    are reported as statuses instead (BROKEN / UNTESTABLE / NOT_EVALUABLE).
    """
    base = {"strategy": module_name, "label": "BACKTEST-OOS"}
    try:
        mod = _load_module(module_name, file_path, search_paths)
    except ModuleProblem as mp:
        return {**base, "status": mp.status, "reason": mp.reason}
    get_signal = getattr(mod, "get_signal", None)
    if get_signal is None or not callable(get_signal):
        return {**base, "status": "NOT_EVALUABLE",
                "reason": "module exposes no callable get_signal(df)"}

    # Candidate feature pipelines, in preference order.
    pipelines: list[tuple[str, object]] = []
    own_features = getattr(mod, "add_features", None)
    if callable(own_features):
        pipelines.append(("module.add_features", own_features))
    try:
        shared = importlib.import_module("features")
        if callable(getattr(shared, "add_features", None)):
            pipelines.append(("features.add_features (shared)", shared.add_features))
    except Exception:
        pass
    pipelines.append(("identity (raw OHLCV)", None))

    first_symbol = next(iter(datasets.values()))
    chosen = None
    chosen_work = None
    problems: list[str] = []
    for name, fn in pipelines:
        if fn is not None and not _features_causal(fn, first_symbol.df):
            problems.append(f"pipeline '{name}': features are NOT causal (truncated != full) — rejected")
            continue
        try:
            chosen_work = _try_pipeline(mod, first_symbol.df, name, fn)
            chosen = (name, fn)
            break
        except ModuleProblem as mp:
            problems.append(f"pipeline '{name}': {mp.reason}")
    if chosen is None:
        status = "UNTESTABLE" if any("NOT causal" in p for p in problems) else "BROKEN"
        return {**base, "status": status, "reason": "; ".join(problems)}
    pipeline_name, pipeline_fn = chosen

    all_trades = []
    per_symbol = {}
    unbracketed_signals = 0
    for sym, ds in datasets.items():
        work = pipeline_fn(ds.df.copy()) if pipeline_fn is not None else ds.df
        n = len(work)
        signals: list[tuple[int, str, float, float]] = []
        t0 = time.time()
        probe_end = min(n - 1, WARMUP_BARS + 2000)
        for i in range(WARMUP_BARS, probe_end):
            res = get_signal(work.iloc[max(0, i - WINDOW + 1): i + 1].copy())
            ex = _extract(res)
            if ex is not None:
                signals.append((i, ex[0], ex[1], ex[2]))
            elif res is not None:
                side = res.get("side") if isinstance(res, dict) else getattr(res, "side", None)
                if side in ("BUY", "SELL", "LONG", "SHORT"):
                    unbracketed_signals += 1
        elapsed = time.time() - t0
        calls = max(1, probe_end - WARMUP_BARS)
        projected = elapsed / calls * max(0, n - 1 - WARMUP_BARS)
        if projected > max_seconds_per_symbol:
            return {**base, "status": "UNTESTABLE",
                    "reason": f"compute-bound: projected {projected:.0f}s/symbol > budget {max_seconds_per_symbol:.0f}s",
                    "feature_pipeline": pipeline_name}
        for i in range(probe_end, n - 1):
            res = get_signal(work.iloc[max(0, i - WINDOW + 1): i + 1].copy())
            ex = _extract(res)
            if ex is not None:
                signals.append((i, ex[0], ex[1], ex[2]))
            elif res is not None:
                side = res.get("side") if isinstance(res, dict) else getattr(res, "side", None)
                if side in ("BUY", "SELL", "LONG", "SHORT"):
                    unbracketed_signals += 1
        trades = simulate_module(ds.df, signals, sym, costs)
        per_symbol[sym] = len(trades)
        all_trades.extend(trades)

    report = oos_report(all_trades)
    status = "EVALUATED" if report["pooled_oos"]["trades"] > 0 else "NO_TRADES"
    return {
        **base,
        "status": status,
        "feature_pipeline": pipeline_name,
        "timeframe": first_symbol.timeframe,
        "symbols": sorted(datasets.keys()),
        "trades_by_symbol": per_symbol,
        "signals_without_bracket": unbracketed_signals,
        "data_provenance": {ds.key: {
            "source": ds.manifest.get("source"),
            "csv_sha256": ds.manifest.get("csv_sha256") or ds.manifest.get("derived_from_csv_sha256"),
            "rows": ds.manifest.get("rows"),
            "gap_missing_bars": (ds.manifest.get("gap_audit") or {}).get("missing_bars"),
        } for ds in datasets.values()},
        **report,
    }
