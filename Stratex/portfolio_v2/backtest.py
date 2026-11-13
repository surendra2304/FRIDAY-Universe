"""Backtest Stratex v2 on real OANDA history.

Usage:
    python3 -m friday.agents.stratex.backtest
    python3 -m friday.agents.stratex.backtest --count 3000 --pairs EUR_USD,XAU_USD

Honesty rules baked in:
  * entry fills at the NEXT candle open after the signal (no lookahead);
  * typical practice spreads are charged on every trade;
  * if a bar touches both SL and TP, the SL is assumed to fill first (conservative).
"""
import argparse

from .config import EXEC, PORTFOLIO, UNIVERSE, Config
from .oanda_client import OandaClient
from .strategy import compute, protective_levels, signal_at

# Typical practice-account spread per instrument, in price units (charged once per trade).
SPREAD_COST = {
    "EUR_USD": 0.00012, "GBP_USD": 0.00015, "USD_JPY": 0.015, "AUD_USD": 0.00016,
    "USD_CAD": 0.00016, "USD_CHF": 0.00017, "NZD_USD": 0.00022, "EUR_JPY": 0.018,
    "GBP_JPY": 0.025, "EUR_GBP": 0.00014, "AUD_JPY": 0.020, "XAU_USD": 0.30,
}


def parse_candles(raw):
    """OANDA candle response -> [{t,o,h,l,c}] keeping only COMPLETE candles."""
    out = []
    for c in raw.get("candles", []):
        if not c.get("complete"):
            continue
        out.append({
            "t": float(c["time"]),
            "o": float(c["mid"]["o"]),
            "h": float(c["mid"]["h"]),
            "l": float(c["mid"]["l"]),
            "c": float(c["mid"]["c"]),
        })
    return out


def simulate(inst, candles, cfg):
    """Run the strategy over `candles`; returns a list of trade records in R units."""
    ind = compute(candles, cfg)
    trades = []
    start = max(cfg["ema_macro"], cfg["ema_trend"]) + 2
    i, n = start, len(candles)
    while i < n - 1:
        sig = signal_at(ind, i, cfg)
        if not sig:
            i += 1
            continue
        entry_i = i + 1
        entry = candles[entry_i]["o"]  # fill at next candle open (no lookahead)
        stop, target = protective_levels(sig["side"], entry, sig["atr"], cfg)
        cost = SPREAD_COST.get(inst, 0.0002)
        exit_price, outcome, exit_time, j = None, None, None, entry_i
        while j < n:
            bar = candles[j]
            if sig["side"] == "long":
                if bar["l"] <= stop:
                    exit_price, outcome, exit_time = stop, "SL", bar["t"]
                    break
                if bar["h"] >= target:
                    exit_price, outcome, exit_time = target, "TP", bar["t"]
                    break
            else:
                if bar["h"] >= stop:
                    exit_price, outcome, exit_time = stop, "SL", bar["t"]
                    break
                if bar["l"] <= target:
                    exit_price, outcome, exit_time = target, "TP", bar["t"]
                    break
            j += 1
        if exit_price is None:
            exit_price, outcome, exit_time = candles[-1]["c"], "OPEN", candles[-1]["t"]
        move = (exit_price - entry) if sig["side"] == "long" else (entry - exit_price)
        pnl = move - cost
        trades.append({
            "instrument": inst,
            "side": sig["side"],
            "outcome": outcome,
            "entry_time": candles[entry_i]["t"],
            "exit_time": exit_time,
            "r": pnl / abs(entry - stop),
        })
        i = j + 1 + cfg.get("cooldown_bars", 0)  # one position at a time + cooldown
    return trades


def summarize(trades):
    if not trades:
        return {"n": 0, "win_pct": 0.0, "total_r": 0.0, "avg_r": 0.0,
                "profit_factor": 0.0, "max_dd_r": 0.0}
    rs = [t["r"] for t in trades]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    cum = peak = dd = 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    return {
        "n": len(rs),
        "win_pct": round(100.0 * len(wins) / len(rs), 1),
        "total_r": round(sum(rs), 2),
        "avg_r": round(sum(rs) / len(rs), 3),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else float("inf"),
        "max_dd_r": round(dd, 2),
    }


def main():
    ap = argparse.ArgumentParser(description="Stratex backtest on real OANDA candles")
    ap.add_argument("--count", type=int, default=5000, help="candles per instrument (max 5000)")
    ap.add_argument("--pairs", type=str, default=",".join(UNIVERSE))
    args = ap.parse_args()

    config = Config()
    client = OandaClient(config.api_key, config.environment)
    pairs = [p for p in args.pairs.split(",") if p]

    print(f"=== Stratex backtest | daily candles | last {args.count} candles/pair ===")
    data = {}
    for inst in pairs:
        try:
            raw = client.candles(inst, granularity="D", count=args.count, price="M")
        except Exception as exc:
            print(f"{inst:8s} SKIP ({exc})")
            continue
        candles = parse_candles(raw)
        if len(candles) < 260:
            print(f"{inst:8s} SKIP (only {len(candles)} complete candles)")
            continue
        data[inst] = candles
        print(f"{inst:8s} {len(candles)} daily candles loaded")

    grand = []
    for strat_name, cfg in PORTFOLIO.items():
        print(f"\n--- {strat_name} ({cfg['mode']}, sl={cfg['sl_atr']}ATR tp={cfg['tp_atr']}ATR) ---")
        strat_trades = []
        for inst, candles in data.items():
            trades = simulate(inst, candles, cfg)
            s = summarize(trades)
            strat_trades.extend(trades)
            print(f"{inst:8s} trades={s['n']:4d}  win={s['win_pct']:5.1f}%  "
                  f"totalR={s['total_r']:+8.2f}  avgR={s['avg_r']:+.3f}  "
                  f"PF={s['profit_factor']}  maxDD={s['max_dd_r']}R")
        s = summarize(strat_trades)
        grand.extend(strat_trades)
        print(f"{strat_name:8s} trades={s['n']:4d}  win={s['win_pct']:5.1f}%  "
              f"totalR={s['total_r']:+8.2f}  avgR={s['avg_r']:+.3f}  "
              f"PF={s['profit_factor']}  maxDD={s['max_dd_r']}R")

    total = summarize(grand)
    years = max(len(c) for c in data.values()) / 252.0 if data else 1.0
    print("\n" + "=" * 80)
    print(f"COMBINED  trades={total['n']}  win={total['win_pct']}%  "
          f"totalR={total['total_r']:+.2f}  avgR={total['avg_r']:+.3f}  "
          f"PF={total['profit_factor']}  maxDD={total['max_dd_r']}R")
    print(f"~{total['n'] / years:.0f} trades/year | expectancy {total['avg_r']:+.3f}R/trade | "
          f"~{total['total_r'] / years:+.2f}R/year -> at 1% risk/trade ~{total['total_r'] / years:+.1f}%/year")


if __name__ == "__main__":
    main()
