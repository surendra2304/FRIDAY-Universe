"""Module-faithful evaluation for TASK-STR-RD-002 (governed + discovery).

Reuses module_eval's integrity machinery verbatim (module loading,
feature-pipeline causality checks, execution sampling, compute
projection) but generalizes the judgement: per-symbol asset-class
costs, panel fold profiles, and — for adx_ema_production — the
production signal filters from rd.stage2 (LONG_ONLY + BTC 4h regime
gate). One (module-config, panel, timeframe) cell = one trial.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from ..data_feed import Dataset
from ..module_eval import (WARMUP_BARS, WINDOW, ModuleProblem, _extract,
                           _features_causal, _load_module, _try_pipeline)
from ..simulator import simulate_module
from ..rd.stage2 import apply_filters, btc_gate_series
from .costs2 import costs_for
from .stats2 import fold_report

SEARCH_PATHS_SUB = ["", "strategies"]  # resolved against stratex root


def _pipelines(mod, first_df):
    import importlib
    pipelines = []
    own = getattr(mod, "add_features", None)
    if callable(own):
        pipelines.append(("module.add_features", own))
    try:
        shared = importlib.import_module("features")
        if callable(getattr(shared, "add_features", None)):
            pipelines.append(("features.add_features (shared)",
                              shared.add_features))
    except Exception:
        pass
    pipelines.append(("identity (raw OHLCV)", None))
    problems = []
    for name, fn in pipelines:
        if fn is not None and not _features_causal(fn, first_df):
            problems.append(f"pipeline '{name}': features NOT causal")
            continue
        try:
            work = _try_pipeline(mod, first_df, name, fn)
            return (name, fn), work, problems
        except ModuleProblem as mp:
            problems.append(f"pipeline '{name}': {mp.reason}")
    return None, None, problems


def eval_module_cell(module_name: str, file_path: Path, stratex_root: Path,
                     datasets: dict[str, Dataset], panel: str,
                     max_seconds_per_symbol: float = 300.0,
                     signal_filter=None) -> dict:
    """Evaluate one module over one panel cell. Returns (status, trades,
    detail). signal_filter: optional fn(signals, sym, ds) -> signals."""
    search_paths = [str(stratex_root), str(stratex_root / "strategies")]
    try:
        mod = _load_module(module_name, file_path, search_paths)
    except ModuleProblem as mp:
        return mp.status, [], {"reason": mp.reason}
    get_signal = getattr(mod, "get_signal", None)
    if get_signal is None or not callable(get_signal):
        return "NOT_EVALUABLE", [], {"reason": "no callable get_signal(df)"}
    first = next(iter(datasets.values()))
    chosen, _work, problems = _pipelines(mod, first.df)
    if chosen is None:
        status = "UNTESTABLE" if any("NOT causal" in p for p in problems) \
            else "BROKEN"
        return status, [], {"reason": "; ".join(problems)}
    pipeline_name, pipeline_fn = chosen
    all_trades = []
    per_symbol = {}
    unbracketed = 0
    for sym, ds in datasets.items():
        work = pipeline_fn(ds.df.copy()) if pipeline_fn is not None else ds.df
        n = len(work)
        signals = []
        t0 = time.time()
        probe_end = min(n - 1, WARMUP_BARS + 2000)
        for i in range(WARMUP_BARS, probe_end):
            res = get_signal(work.iloc[max(0, i - WINDOW + 1): i + 1].copy())
            ex = _extract(res)
            if ex is not None:
                signals.append((i, ex[0], ex[1], ex[2]))
            elif res is not None:
                side = res.get("side") if isinstance(res, dict) else \
                    getattr(res, "side", None)
                if side in ("BUY", "SELL", "LONG", "SHORT"):
                    unbracketed += 1
        elapsed = time.time() - t0
        calls = max(1, probe_end - WARMUP_BARS)
        projected = elapsed / calls * max(0, n - 1 - WARMUP_BARS)
        if projected > max_seconds_per_symbol:
            return "UNTESTABLE", [], {
                "reason": f"compute-bound: projected {projected:.0f}s/symbol "
                          f"> budget {max_seconds_per_symbol:.0f}s",
                "feature_pipeline": pipeline_name}
        for i in range(probe_end, n - 1):
            res = get_signal(work.iloc[max(0, i - WINDOW + 1): i + 1].copy())
            ex = _extract(res)
            if ex is not None:
                signals.append((i, ex[0], ex[1], ex[2]))
            elif res is not None:
                side = res.get("side") if isinstance(res, dict) else \
                    getattr(res, "side", None)
                if side in ("BUY", "SELL", "LONG", "SHORT"):
                    unbracketed += 1
        if signal_filter is not None:
            signals = signal_filter(signals, sym, ds)
        trades = simulate_module(ds.df, signals, sym, costs_for(panel, sym))
        per_symbol[sym] = len(trades)
        all_trades.extend(trades)
    return ("EVALUATED" if all_trades else "NO_TRADES"), all_trades, {
        "feature_pipeline": pipeline_name,
        "trades_by_symbol": per_symbol,
        "signals_without_bracket": unbracketed}


def adx_production_filter(gate_ok: pd.Series):
    """LONG_ONLY + BTC-regime gate, applied at signal level (production)."""
    def _f(signals, sym, ds):
        return apply_filters(signals, sym, gate_ok, ds.df.index,
                             long_only=True, gate=True)
    return _f


def make_row(module_name, config, panel, tf, status, trades, detail,
             symbols, profile):
    from .stats2 import check_bar2, holdout2, trade_stats
    rep = fold_report(trades, profile, symbols)
    hold = holdout2(rep, symbols)
    po = rep["pooled_oos"]
    start = pd.Timestamp(rep["per_fold"][profile[0]]["oos_start"], tz="UTC")
    oos_trades = [t for t in trades if t.entry_time >= start]
    return {
        "family": "governed" if config != "discovery" else "discovery",
        "variant": f"{module_name}:{config}" if config != "discovery"
                   else module_name,
        "module": module_name, "config": config,
        "panel": panel, "timeframe": tf, "status": status,
        "detail": detail, "symbols": symbols, "report": rep,
        "holdout": hold, "bar": check_bar2(rep, hold),
        "trade_stats": trade_stats(oos_trades),
        "pooled_trades_total": len(trades),
    }
