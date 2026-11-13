"""
oanda_demo/backtest.py — Historical validation of SMT-v2 on real OANDA candles.

Owner directive (2026-11-13): "make Stratex take profitable trades" — so the
strategy must prove itself on real history before it is allowed to trade.

Model:
  - Signals computed on bar close, filled at the NEXT bar open +/- half spread
    (costs included, conservative).
  - Intrabar SL/TP checks on raw high/low; when both are touched in the same
    bar the stop is assumed first (worst case).
  - Breakeven move at +1R (same rule the live trader applies).
  - 1% equity risk per trade, compounded — identical to live sizing.

Usage (from Stratex/):
    python3 -m oanda_demo.backtest --instruments EURUSD,GBPUSD,USDJPY \
        --granularity H1 --count 4000
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd

from exchanges.oanda_adapter import OandaExchangeAdapter
from oanda_demo.credentials import load_oanda_credentials
from oanda_demo.strategy import (
    DonchianConfig,
    DonchianTrendStrategy,
    MeanReversionConfig,
    MeanReversionStrategy,
    StratexTrendStrategy,
    StrategyConfig,
)

# Observed OANDA *practice* closeout spreads in PRICE units (2026-11-13
# live sampling — deliberately conservative vs top-of-book).
DEFAULT_SPREADS = {
    "EURUSD": 0.00035,
    "GBPUSD": 0.00055,
    "USDJPY": 0.036,
    "AUDUSD": 0.00094,
    "USDCAD": 0.00080,
    "NZDUSD": 0.00145,
    "EURJPY": 0.068,
    "EURGBP": 0.00048,
}

DATA_DIR = Path("data")
GRAN_TO_TF = {"M15": "15m", "M30": "30m", "H1": "1h", "H4": "4h", "D": "1d"}


def fetch_history(adapter: OandaExchangeAdapter, symbol: str, granularity: str,
                  pages: int = 2, per_page: int = 5000) -> List[Dict]:
    """Paginated candle fetch. The v3 API caps a single response at 5000
    candles, so we walk backwards with the exclusive `to` parameter."""
    oanda_sym = adapter.denormalize_symbol(symbol)
    rows: List[Dict] = []
    to = None
    for _ in range(max(1, pages)):
        params = {"granularity": granularity, "count": per_page, "price": "M"}
        if to:
            params["to"] = to
        data = adapter._request("GET", f"/instruments/{oanda_sym}/candles", params=params)
        candles = (data or {}).get("candles", [])
        if not candles:
            break
        rows = candles + rows                 # prepend the older page
        to = candles[0]["time"]               # `to` is exclusive
        if len(candles) < per_page:
            break
    out: Dict[str, Dict] = {}
    for c in rows:
        if not c.get("complete", True):
            continue
        m = c["mid"]
        out[c["time"]] = {
            "timestamp": c["time"],
            "open": float(m["o"]), "high": float(m["h"]),
            "low": float(m["l"]), "close": float(m["c"]),
            "volume": int(c.get("volume", 0) or 0),
        }
    return [out[k] for k in sorted(out)]


def run_backtest(
    strategy: StratexTrendStrategy,
    df: pd.DataFrame,
    instrument: str,
    spread: float,
    risk_pct: float = 0.01,
    start_equity: float = 100000.0,
) -> Dict:
    """Event-driven simulation; same signal path as the live trader."""
    cfg = strategy.cfg
    trailing = getattr(cfg, "trailing_atr", None) is not None
    rule_exit = getattr(cfg, "exit_rule", None) == "mr"
    d = strategy.add_indicators(df)
    trades: List[Dict] = []
    equity = start_equity
    peak = equity
    max_dd = 0.0
    pos = None

    for i in range(cfg.min_bars, len(d) - 1):
        row = d.iloc[i]
        nxt = d.iloc[i + 1]

        if pos is None:
            side, _ = strategy.signal_at(row)
            if not side:
                continue
            a = float(row["atr"])
            if a <= 0:
                continue
            # Apply the SAME spread filter the live trader uses, so the
            # backtest only counts entries that would actually be taken.
            max_spread_frac = getattr(cfg, "max_spread_frac_atr", None)
            if max_spread_frac is not None and spread > max_spread_frac * a:
                continue
            half = spread / 2.0
            entry = float(nxt["open"]) + (half if side == "LONG" else -half)
            if side == "LONG":
                sl = entry - cfg.sl_atr_mult * a
                tp = entry + cfg.tp_atr_mult * a if (not trailing and cfg.tp_atr_mult) else None
            else:
                sl = entry + cfg.sl_atr_mult * a
                tp = entry - cfg.tp_atr_mult * a if (not trailing and cfg.tp_atr_mult) else None
            risk_dist = abs(entry - sl)
            if risk_dist <= 0:
                continue
            pos = {
                "side": side, "entry": entry, "sl": sl, "tp": tp,
                "risk_dist": risk_dist, "be": False, "extreme": entry, "hold": 0,
                "risk_usd": equity * risk_pct,
                "entry_time": str(nxt.get("timestamp", i)),
            }
            continue

        hi, lo = float(nxt["high"]), float(nxt["low"])
        direction = 1 if pos["side"] == "LONG" else -1
        exit_price = None
        reason = ""

        if rule_exit:
            # Mean reversion: disaster stop first, then close-based rule exit.
            if direction == 1 and lo <= pos["sl"]:
                exit_price, reason = pos["sl"], "SL"
            elif direction == -1 and hi >= pos["sl"]:
                exit_price, reason = pos["sl"], "SL"
            else:
                pos["hold"] += 1
                c = float(nxt["close"])
                exit_level = float(nxt["ema_exit"])
                if direction == 1 and c > exit_level:
                    exit_price, reason = c, "RULE"
                elif direction == -1 and c < exit_level:
                    exit_price, reason = c, "RULE"
                elif pos["hold"] >= getattr(cfg, "max_hold_bars", 10):
                    exit_price, reason = c, "TIME"
        elif trailing:
            # Chandelier trail: update from the COMPLETED bar (row),
            # then apply to the bar being simulated (no look-ahead).
            if direction == 1:
                pos["extreme"] = max(pos["extreme"], float(row["close"]))
                new_sl = pos["extreme"] - cfg.trailing_atr * float(row["atr"])
                if new_sl > pos["sl"]:
                    pos["sl"] = new_sl
                if lo <= pos["sl"]:
                    exit_price, reason = pos["sl"], "TRAIL"
            else:
                pos["extreme"] = min(pos["extreme"], float(row["close"]))
                new_sl = pos["extreme"] + cfg.trailing_atr * float(row["atr"])
                if new_sl < pos["sl"]:
                    pos["sl"] = new_sl
                if hi >= pos["sl"]:
                    exit_price, reason = pos["sl"], "TRAIL"
        else:
            # Conservative order: stop first when both touch in one bar.
            if direction == 1:
                if lo <= pos["sl"]:
                    exit_price, reason = pos["sl"], "SL"
                elif pos["tp"] and hi >= pos["tp"]:
                    exit_price, reason = pos["tp"], "TP"
                elif not pos["be"] and hi >= pos["entry"] + cfg.breakeven_r * pos["risk_dist"]:
                    pos["sl"] = max(pos["sl"], pos["entry"])
                    pos["be"] = True
            else:
                if hi >= pos["sl"]:
                    exit_price, reason = pos["sl"], "SL"
                elif pos["tp"] and lo <= pos["tp"]:
                    exit_price, reason = pos["tp"], "TP"
                elif not pos["be"] and lo <= pos["entry"] - cfg.breakeven_r * pos["risk_dist"]:
                    pos["sl"] = min(pos["sl"], pos["entry"])
                    pos["be"] = True

        if exit_price is None:
            continue

        r_mult = direction * (exit_price - pos["entry"]) / pos["risk_dist"]
        pnl = pos["risk_usd"] * r_mult
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
        trades.append({
            "instrument": instrument,
            "side": pos["side"],
            "entry": round(pos["entry"], 6),
            "exit": round(exit_price, 6),
            "r": round(r_mult, 4),
            "pnl": round(pnl, 2),
            "reason": reason + ("+BE" if pos["be"] and reason == "SL" else ""),
            "entry_time": pos["entry_time"],
        })
        pos = None

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    return {
        "instrument": instrument,
        "bars": int(len(d)),
        "trades": len(trades),
        "wins": len(wins),
        "winrate_pct": round(100.0 * len(wins) / len(trades), 1) if trades else 0.0,
        "avg_r": round(sum(t["r"] for t in trades) / len(trades), 3) if trades else 0.0,
        "total_r": round(sum(t["r"] for t in trades), 2) if trades else 0.0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "return_pct": round(100.0 * (equity - start_equity) / start_equity, 3),
        "max_drawdown_pct": round(100.0 * max_dd, 2),
        "final_equity": round(equity, 2),
        "_trades": trades,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SMT-v2 backtest on OANDA history")
    parser.add_argument("--strategy", default="mr", choices=["smt", "donchian", "mr"],
                        help="smt = EMA-stack+RSI; donchian = breakout+trail; mr = RSI2 reversion")
    parser.add_argument("--entry-bars", type=int, default=55, help="donchian channel length")
    parser.add_argument("--instruments", default="EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,NZDUSD,EURJPY,EURGBP")
    parser.add_argument("--granularity", default="H1", choices=sorted(GRAN_TO_TF))
    parser.add_argument("--count", type=int, default=5000, help="candles per page")
    parser.add_argument("--pages", type=int, default=2, help="history pages (5000/page)")
    parser.add_argument("--risk-pct", type=float, default=0.01)
    parser.add_argument("--tp-atr", type=float, default=None, help="override tp_atr_mult")
    parser.add_argument("--extension", type=float, default=None, help="override max_extension_atr")
    parser.add_argument("--strength", type=float, default=None, help="override min_trend_strength")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    if args.strategy == "donchian":
        cfg = DonchianConfig()
        if args.entry_bars:
            cfg.entry_bars = args.entry_bars
        if args.tp_atr:
            cfg.tp_atr_mult = args.tp_atr
            cfg.trailing_atr = None
        strategy = DonchianTrendStrategy(cfg)
    elif args.strategy == "mr":
        cfg = MeanReversionConfig()
        strategy = MeanReversionStrategy(cfg)
    else:
        cfg = StrategyConfig()
        if args.tp_atr:
            cfg.tp_atr_mult = args.tp_atr
        if args.extension is not None:
            cfg.max_extension_atr = args.extension
        if args.strength is not None:
            cfg.min_trend_strength = args.strength
        strategy = StratexTrendStrategy(cfg)

    api_key, account_id, practice = load_oanda_credentials()
    adapter = OandaExchangeAdapter(api_key=api_key, account_id=account_id, practice=practice)
    tf = GRAN_TO_TF[args.granularity]

    results = []
    for sym in [s.strip() for s in args.instruments.split(",") if s.strip()]:
        candles = fetch_history(adapter, sym, args.granularity, pages=args.pages)
        if not candles or len(candles) < cfg.min_bars + 10:
            print(f"{sym}: insufficient candles ({len(candles) if candles else 0}) — skipped")
            continue
        df = pd.DataFrame(candles)
        res = run_backtest(strategy, df, sym, DEFAULT_SPREADS.get(sym, 0.0002),
                           risk_pct=args.risk_pct)
        results.append(res)
        print(
            f"{sym:8s} bars={res['bars']:5d} trades={res['trades']:3d} "
            f"win%={res['winrate_pct']:5.1f} avgR={res['avg_r']:6.3f} "
            f"totR={res['total_r']:7.2f} PF={res['profit_factor']} "
            f"ret%={res['return_pct']:7.3f} maxDD%={res['max_drawdown_pct']:5.2f}"
        )

    if not results:
        print("No results.")
        return 1

    agg_trades = sum(r["trades"] for r in results)
    agg_wins = sum(r["wins"] for r in results)
    agg_r = sum(r["total_r"] for r in results)
    print("-" * 72)
    print(
        f"TOTAL    trades={agg_trades} win%="
        f"{round(100.0 * agg_wins / agg_trades, 1) if agg_trades else 0.0} "
        f"totalR={round(agg_r, 2)}"
    )

    out_path = Path(args.json_out) if args.json_out else (
        DATA_DIR / f"oanda_demo_backtest_{args.granularity}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy.name,
        "granularity": args.granularity,
        "pages": args.pages,
        "risk_pct": args.risk_pct,
        "config": {
            "strategy": strategy.name,
            "sl_atr_mult": cfg.sl_atr_mult,
            "tp_atr_mult": getattr(cfg, "tp_atr_mult", None),
            "trailing_atr": getattr(cfg, "trailing_atr", None),
            "entry_bars": getattr(cfg, "entry_bars", None),
            "spreads": {s: DEFAULT_SPREADS.get(s) for s in args.instruments.split(",")},
        },
        "results": [{k: v for k, v in r.items() if k != "_trades"} for r in results],
        "aggregate": {
            "trades": agg_trades,
            "winrate_pct": round(100.0 * agg_wins / agg_trades, 1) if agg_trades else 0.0,
            "total_r": round(agg_r, 2),
        },
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
