"""Shared helpers for TASK-STR-RD-001 stage runners."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..data_feed import Dataset, load_dataset, resample_dataset
from ..simulator import Costs, Trade, trade_metrics
from ..walkforward import FOLDS, oos_report, trades_in_window

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
COSTS = Costs()  # harness standard: 16 bps round trip

# Pre-registered promotion bar (Anti-Overfit Law). A strategy/variant earns
# the name PROMOTION CANDIDATE only if ALL of these hold on pooled
# walk-forward OOS trades, AND it then passes the holdout check in
# holdout_check(). Anything else is reported as noise / watchlist.
PROMOTION_BAR = {
    "expectancy_net_gt": 0.0,
    "profit_factor_net_gte": 1.2,
    "min_oos_trades": 200,
    "min_positive_folds": 4,   # of 5
    "folds_total": 5,
}

_TF_PLAN = {"5m": ("2023-12", "2026-10"), "15m": ("2023-10", "2026-10"),
            "1h": ("2023-10", "2026-10")}


def load_timeframe(tf: str, cache_dir: Path | None) -> dict[str, Dataset]:
    """Load one timeframe for all symbols (1h-derived for 4h/1d/2h/6h)."""
    if tf in _TF_PLAN:
        sm, em = _TF_PLAN[tf]
        return {sym: load_dataset(sym, tf, sm, em, cache_dir=cache_dir)
                for sym in SYMBOLS}
    if tf in ("4h", "1d"):
        base = load_timeframe("1h", cache_dir)
        return {sym: resample_dataset(ds, tf) for sym, ds in base.items()}
    if tf in ("2h", "6h"):
        base = load_timeframe("1h", cache_dir)
        return {sym: resample_custom(ds, tf) for sym, ds in base.items()}
    raise ValueError(f"unsupported timeframe {tf}")


_MINUTES = {"1h": 60, "2h": 120, "4h": 240, "6h": 360, "1d": 1440}


def resample_custom(ds: Dataset, target_tf: str) -> Dataset:
    """1h -> 2h/6h resample with the harness's documented derivation rule
    (UTC-aligned, complete buckets only, parent hash recorded). Mirrors
    data_feed.resample_dataset for timeframes the harness does not list."""
    dst_min = _MINUTES[target_tf]
    rule = f"{dst_min}min"
    agg = ds.df.resample(rule, origin="start_day").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum"})
    counts = ds.df["close"].resample(rule, origin="start_day").count()
    agg = agg[counts == dst_min // 60].dropna()
    from ..data_feed import gap_audit
    manifest = {
        "source": f"resampled_from:{ds.manifest.get('source')}",
        "derived_from_csv_sha256": ds.manifest.get("csv_sha256"),
        "derived_from": ds.key,
        "symbol": ds.symbol,
        "timeframe": target_tf,
        "resample_rule": f"{rule} origin=start_day, complete buckets only",
        "fetched_at_utc": ds.manifest.get("fetched_at_utc"),
        "rows": int(len(agg)),
        "first_bar_utc": agg.index[0].isoformat() if len(agg) else None,
        "last_bar_utc": agg.index[-1].isoformat() if len(agg) else None,
        "gap_audit": gap_audit(agg, target_tf) if target_tf in
                     ("1m", "5m", "15m", "1h", "4h", "1d") else
                     {"expected_bars": None, "actual_bars": int(len(agg)),
                      "missing_bars": None,
                      "gap_spans": [], "note": "gap audit grid not defined for custom tf; complete-bucket rule enforced at construction"},
    }
    return Dataset(ds.symbol, target_tf, agg, manifest)


def trades_to_json(trades: list[Trade]) -> list[dict]:
    return [{
        "symbol": t.symbol,
        "entry_time": t.entry_time.isoformat(),
        "exit_time": t.exit_time.isoformat(),
        "side": t.side,
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "net_return": t.net_return,
        "exit_reason": t.exit_reason,
    } for t in trades]


def trades_from_json(rows: list[dict]) -> list[Trade]:
    return [Trade(r["symbol"], pd.Timestamp(r["entry_time"]),
                  pd.Timestamp(r["exit_time"]), r["side"], r["entry_price"],
                  r["exit_price"], r["net_return"], r["exit_reason"])
            for r in rows]


def full_report(trades: list[Trade]) -> dict:
    """Pooled OOS + per-fold + per-symbol OOS metrics (harness standard)."""
    rep = oos_report(trades)
    per_symbol = {}
    for sym in SYMBOLS:
        st = [t for t in trades if t.symbol == sym]
        per_symbol[sym] = oos_report(st)["pooled_oos"]
    return {**rep, "per_symbol_oos": per_symbol}


def positive_folds(report: dict) -> int:
    n = 0
    for fid, _, _ in FOLDS:
        e = report["per_fold"][fid].get("expectancy_net")
        if e is not None and e > 0:
            n += 1
    return n


def check_bar(report: dict) -> dict:
    """Apply the pre-registered promotion bar to a full_report()."""
    po = report["pooled_oos"]
    pf = po.get("profit_factor_net")
    checks = {
        "expectancy_net_gt_0": (po.get("expectancy_net") or 0.0) > PROMOTION_BAR["expectancy_net_gt"],
        "profit_factor_net_gte_1.2": pf is not None and pf != float("inf") and pf >= PROMOTION_BAR["profit_factor_net_gte"],
        "min_oos_trades_200": (po.get("trades") or 0) >= PROMOTION_BAR["min_oos_trades"],
        "positive_folds_gte_4_of_5": positive_folds(report) >= PROMOTION_BAR["min_positive_folds"],
    }
    return {"bar": PROMOTION_BAR, "checks": checks,
            "passes_bar": all(checks.values())}


def holdout_check(report: dict) -> dict:
    """Per-symbol holdout: a pooled positive must not be one symbol's luck.

    Pass requires: expectancy > 0 on at least 2 of 3 symbols (each with
    >= 20 OOS trades) AND no single symbol contributing more than 80% of
    total net profit.
    """
    per = report["per_symbol_oos"]
    pos_syms = [s for s, m in per.items()
                if (m.get("trades") or 0) >= 20 and (m.get("expectancy_net") or 0) > 0]
    profits = {}
    for s, m in per.items():
        e = m.get("expectancy_net")
        profits[s] = (e * m["trades"]) if e is not None else 0.0
    total_pos = sum(p for p in profits.values() if p > 0)
    max_share = (max(profits.values()) / total_pos) if total_pos > 0 else 1.0
    return {
        "symbols_positive_min20trades": pos_syms,
        "max_symbol_profit_share": max_share,
        "passes": len(pos_syms) >= 2 and max_share <= 0.80,
    }


def wf_select_judge(variant_trades: dict[str, list[Trade]]) -> dict:
    """Factory-style honest selection, within a family: per fold, rank all
    variants on in-sample trades only (net PF, then win rate — the legacy
    sort key), take the TOP 1, judge it on the fold's OOS trades only.
    Returns the procedure's pooled OOS metrics + per-fold picks."""
    procedure_trades: list[Trade] = []
    picks = []
    for fid, start, end in FOLDS:
        rows = []
        for name, trades in variant_trades.items():
            m = trade_metrics(trades_in_window(trades, None, start))
            if m["trades"] > 0 and m["profit_factor_net"] is not None:
                rows.append((name, m))
        rows.sort(key=lambda r: (r[1]["profit_factor_net"] if r[1]["profit_factor_net"] != float("inf") else 1e18,
                                 r[1]["win_rate"] or 0.0), reverse=True)
        if not rows:
            picks.append({"fold": fid, "pick": None})
            continue
        name, ism = rows[0]
        oos = trades_in_window(variant_trades[name], start, end)
        procedure_trades.extend(oos)
        picks.append({"fold": fid, "pick": name,
                      "is": {k: ism[k] for k in ("trades", "win_rate", "expectancy_net", "profit_factor_net")},
                      "oos": trade_metrics(oos)})
    return {"procedure_pooled_oos": trade_metrics(procedure_trades),
            "picks": picks, "variants_considered": len(variant_trades)}


def dump_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift(1)),
        abs(df["low"] - df["close"].shift(1)),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    return 100.0 - (100.0 / (1.0 + rs))


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder-smoothed ADX, replicating strategy_adx_ema.compute_adx."""
    plus_dm = df["high"].diff()
    minus_dm = -df["low"].diff()
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift(1)),
        abs(df["low"] - df["close"].shift(1)),
    ], axis=1).max(axis=1)
    tr_s = tr.ewm(alpha=1 / period, adjust=False).mean()
    pdi = pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / tr_s * 100
    mdi = pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / tr_s * 100
    dx = (abs(pdi - mdi) / (pdi + mdi + 1e-9)) * 100
    return dx.ewm(alpha=1 / period, adjust=False).mean()
