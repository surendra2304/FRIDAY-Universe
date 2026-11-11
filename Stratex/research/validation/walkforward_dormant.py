"""
research/validation/walkforward_dormant.py — Walk-forward validation of dormant strategies.

Batch 2 task 1 (owner directive 2026-11-11): validate the two dormant strategy
files with REAL exchange data and honest walk-forward splits, and promote them
into PRODUCTION_STRATEGY_REGISTRY only if they clear BOTH promotion bars:

    * >= 30 out-of-sample trades (statistical floor)
    * net profit factor >= 1.0 across ALL aggregated OOS trades

Method (matches the repo's evidence standard):
  * Real Binance USDT-M futures candles only (same provenance-verified cache
    pipeline as research/strategy_factory/mass_backtester.py — sha256 sidecar,
    fail-closed on any mismatch). No synthetic data, ever.
  * 3-fold walk-forward: each fold trains nothing (these are fixed rule
    strategies) but tests strictly out-of-sample on a LATER slice than the
    previous fold, so every reported trade is OOS by construction.
  * 8 bps round-trip futures friction (3 bps/side fee + 1 bps/side slippage),
    identical to the mass backtester's friction model.
  * Next-candle-open execution, conservative intrabar SL/TP resolution
    (SL wins ties), risk-per-trade 1%, one open trade per fold run.

Usage:
    python research/validation/walkforward_dormant.py            # both strategies
    python research/validation/walkforward_dormant.py trend_pullback

Output:
    research/validation/walkforward_dormant_report.json  (machine evidence)
    research/validation/walkforward_dormant_report.md    (human evidence)
Exit code 0 always — a failed validation is a RESULT, not an error.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

STRATEX_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STRATEX_ROOT))

from backtest_engine import BacktestEngine  # noqa: E402

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
TIMEFRAMES = ["15m", "1h"]
DAYS = 120           # history per symbol/timeframe
FOLDS = 3            # walk-forward folds
WARMUP = 220         # >= 210 bars both dormant strategies require
FEE_PER_SIDE = 0.0003   # 3 bps/side
SLIP_PER_SIDE = 0.0001  # 1 bps/side  -> 8 bps round trip
RISK_PER_TRADE = 0.01
INITIAL_BALANCE = 10_000.0
MIN_OOS_TRADES = 30
MIN_NET_PF = 1.0

FAPI_BASE = "https://fapi.binance.com/fapi/v1/klines"
CACHE_DIR = STRATEX_ROOT / "data_cache" / "walkforward_dormant"

STRATEGY_FILES = {
    "trend_pullback": "strategy_trend_pullback",
    "volatility_breakout": "strategy_volatility_breakout",
}

REPORT_JSON = Path(__file__).resolve().parent / "walkforward_dormant_report.json"
REPORT_MD = Path(__file__).resolve().parent / "walkforward_dormant_report.md"


def _fetch_futures_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Fetch REAL USDT-M futures candles from the public REST endpoint.

    Same integrity standard as the mass backtester: cached files are only
    trusted when a sha256 provenance sidecar matches; any mismatch fails
    closed. No synthetic data is ever generated.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{symbol}_{interval}_{days}d.csv"
    sidecar = cache.with_suffix(cache.suffix + ".json")
    if cache.exists() and sidecar.exists():
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        if meta.get("sha256") == hashlib.sha256(cache.read_bytes()).hexdigest():
            df = pd.read_csv(cache, index_col=0, parse_dates=True)
            if hasattr(df.index, "as_unit"):
                df.index = df.index.as_unit("us")
            if meta.get("rows") == len(df):
                print(f"[WFD] cached verified {symbol} {interval}: {len(df)} bars "
                      f"(source={meta.get('source')}, sha256={meta['sha256'][:12]})")
                return df
        print(f"[WFD] cache mismatch for {cache.name} — refetching")

    start_ms = int((datetime.now(timezone.utc) - pd.Timedelta(days=days)).timestamp() * 1000)
    rows: list[list] = []
    cursor = start_ms
    ban_backoff = 60  # seconds to wait on 429/418; doubles each ban, capped at 15 min
    while True:
        try:
            resp = requests.get(
                FAPI_BASE,
                params={"symbol": symbol, "interval": interval, "startTime": cursor, "limit": 1000},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (429, 418):
                print(f"[WFD] rate-limited ({status}) fetching {symbol} {interval} — backing off {ban_backoff}s")
                time.sleep(ban_backoff)
                ban_backoff = min(ban_backoff * 2, 900)
                continue
            raise
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        last_open = int(batch[-1][0])
        if len(batch) < 1000 or last_open > datetime.now(timezone.utc).timestamp() * 1000:
            break
        cursor = last_open + 1
        time.sleep(0.6)  # stay well inside the public rate limit (weight 5/1000 per min)

    if not rows:
        raise RuntimeError(f"no real candles returned for {symbol} {interval} — refusing to fabricate")

    df = pd.DataFrame(rows, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "qav", "trades", "tbb", "tbq", "ignore",
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").set_index("timestamp")
    if hasattr(df.index, "as_unit"):
        df.index = df.index.as_unit("us")

    csv_bytes = df.to_csv().encode("utf-8")
    meta = {
        "symbol": symbol,
        "timeframe": interval,
        "days": days,
        "source": FAPI_BASE,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": len(df),
        "sha256": hashlib.sha256(csv_bytes).hexdigest(),
    }
    cache.write_bytes(csv_bytes)
    sidecar.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[WFD] fetched verified {symbol} {interval}: {len(df)} bars "
          f"(source={FAPI_BASE}, sha256={meta['sha256'][:12]})")
    return df


def _net_pf(trades: list[dict]) -> float | None:
    wins = sum(t["net_pnl"] for t in trades if t["net_pnl"] > 0)
    losses = sum(t["net_pnl"] for t in trades if t["net_pnl"] <= 0)
    if not trades:
        return None
    if losses == 0:
        return float("inf") if wins > 0 else None
    return wins / abs(losses)


def _slice_folds(n: int, folds: int) -> list[tuple[int, int]]:
    """Later-and-later OOS test slices; slices never overlap and never repeat."""
    slice_size = (n - WARMUP) // (folds + 1)
    if slice_size < 50:
        raise ValueError(f"not enough bars for {folds} folds (n={n})")
    out = []
    start = WARMUP
    for _ in range(folds):
        end = min(n, start + slice_size)
        out.append((start, end))
        start = end
    return out


def validate_strategy(name: str, module) -> dict:
    """Run the full walk-forward for one strategy across symbols/timeframes."""
    per_run = []
    all_oos_trades: list[dict] = []
    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            df = _fetch_futures_klines(sym, tf, DAYS).copy()
            df = df.reset_index().rename(columns={"index": "timestamp"})
            if "timestamp" not in df.columns:
                df["timestamp"] = pd.to_datetime(df.index)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)
            fold_stats = []
            for fold_idx, (s, e) in enumerate(_slice_folds(len(df), FOLDS), 1):
                test_slice = df.iloc[s - WARMUP: e].reset_index(drop=True)
                engine = BacktestEngine(
                    test_slice,
                    [module],
                    fee_rate=FEE_PER_SIDE,
                    slippage_rate=SLIP_PER_SIDE,
                    initial_balance=INITIAL_BALANCE,
                    risk_per_trade=RISK_PER_TRADE,
                    max_open_trades=1,
                    symbol=sym,
                    long_only=False,           # futures: both sides
                    intrabar_resolution="conservative",
                    warmup=WARMUP,
                )
                trades, _eq = engine.run()
                for t in trades:
                    t["fold"] = fold_idx
                    t["oos"] = True
                all_oos_trades.extend(trades)
                pf = _net_pf(trades)
                fold_stats.append({
                    "fold": fold_idx,
                    "bars": len(test_slice),
                    "range": [str(test_slice["timestamp"].iloc[0]),
                              str(test_slice["timestamp"].iloc[-1])],
                    "trades": len(trades),
                    "win_rate": round(sum(1 for t in trades if t["net_pnl"] > 0) / len(trades), 4) if trades else None,
                    "net_pf": round(pf, 4) if pf is not None and pf != float("inf") else pf,
                    "net_pnl": round(sum(t["net_pnl"] for t in trades), 2),
                })
            per_run.append({
                "symbol": sym,
                "timeframe": tf,
                "folds": fold_stats,
            })
    total_trades = len(all_oos_trades)
    wins = [t for t in all_oos_trades if t["net_pnl"] > 0]
    agg_pf = _net_pf(all_oos_trades)
    win_rate = round(len(wins) / total_trades, 4) if total_trades else None
    net_pnl = round(sum(t["net_pnl"] for t in all_oos_trades), 2)
    avg_win = round(sum(t["net_pnl"] for t in wins) / len(wins), 4) if wins else None
    avg_loss = round(sum(t["net_pnl"] for t in all_oos_trades if t["net_pnl"] <= 0) / max(1, total_trades - len(wins)), 4)
    promote = bool(total_trades >= MIN_OOS_TRADES and agg_pf is not None and agg_pf >= MIN_NET_PF)
    return {
        "strategy": name,
        "oos_trades": total_trades,
        "win_rate": win_rate,
        "net_pf": round(agg_pf, 4) if agg_pf is not None and agg_pf != float("inf") else agg_pf,
        "net_pnl_usd": net_pnl,
        "avg_win_usd": avg_win,
        "avg_loss_usd": avg_loss,
        "promote": promote,
        "promotion_bars": {"min_oos_trades": MIN_OOS_TRADES, "min_net_pf": MIN_NET_PF},
        "per_symbol_timeframe": per_run,
    }


def _merge_report(new_results: list[dict]) -> dict:
    """Merge new per-strategy results into any existing report (union by name)."""
    report: dict = {}
    if REPORT_JSON.exists():
        try:
            report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report = {}
    merged: dict[str, dict] = {r["strategy"]: r for r in (report.get("results") or [])}
    for r in new_results:
        merged[r["strategy"]] = r
    for r in merged.values():
        # Normalize the verdict to a real bool: a numpy bool_ previously slipped
        # through json.dumps(default=str) as the STRING 'False', which is
        # truthy after a round-trip and flipped the rendered verdict.
        if isinstance(r.get("promote"), str):
            r["promote"] = r["promote"].strip().lower() == "true"
    report["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["method"] = {
        "data": "real Binance USDT-M futures candles, provenance-verified cache",
        "folds": FOLDS,
        "warmup_bars": WARMUP,
        "friction_round_trip_bps": (FEE_PER_SIDE + SLIP_PER_SIDE) * 2 * 10_000,
        "execution": "next-candle-open, conservative intrabar SL/TP",
        "risk_per_trade": RISK_PER_TRADE,
    }
    report["results"] = list(merged.values())
    return report


def _write_report(report: dict) -> None:
    REPORT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Walk-Forward Validation — Dormant Strategies",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        f"Method: real futures candles, {FOLDS} strictly-later OOS folds, "
        f"{(FEE_PER_SIDE + SLIP_PER_SIDE) * 2 * 10_000:.0f} bps round-trip friction, "
        "next-open fills, conservative SL/TP resolution.",
        "",
        "| strategy | OOS trades | win rate | net PF | net PnL | verdict |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["results"]:
        lines.append(
            f"| {r['strategy']} | {r['oos_trades']} | {r['win_rate']} | "
            f"{r['net_pf']} | ${r['net_pnl_usd']} | "
            f"{'PROMOTE' if r['promote'] else 'STAY DORMANT'} |"
        )
    lines += ["", "Per-symbol/timeframe fold detail in `walkforward_dormant_report.json`.", ""]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> int:
    targets = argv or list(STRATEGY_FILES)
    for name in targets:
        mod_name = STRATEGY_FILES.get(name)
        if mod_name is None:
            print(f"[WFD] unknown strategy {name!r}; choices: {list(STRATEGY_FILES)}")
            continue
        print(f"[WFD] walk-forward validating {name} ({SYMBOLS} x {TIMEFRAMES}, {FOLDS} folds, {DAYS}d)...")
        module = importlib.import_module(mod_name)
        res = validate_strategy(name, module)
        print(
            f"[WFD] {name}: OOS trades={res['oos_trades']} win_rate={res['win_rate']} "
            f"net_pf={res['net_pf']} net=${res['net_pnl_usd']} -> "
            f"{'PROMOTE' if res['promote'] else 'STAY DORMANT'}"
        )
        # Incremental write: a timeout/interruption after one strategy still
        # leaves that strategy's evidence in the report (merge by name).
        _write_report(_merge_report([res]))
    print(f"[WFD] report -> {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
