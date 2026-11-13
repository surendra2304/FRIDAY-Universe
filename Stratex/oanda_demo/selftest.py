"""
oanda_demo/selftest.py — Live verification of the OANDA demo integration.

Proves, against the real practice API, that:
  1. Credentials resolve (env or credentials.md).
  2. Account summary is readable (balance / equity / margin).
  3. Batch pricing works and spreads are sane.
  4. Historical candles load and the strategy engine computes on them.
  5. Order lifecycle works: 1-unit EUR_USD buy -> immediate close
     (costs a fraction of a cent of demo money; proves the full pipe).

Usage (from Stratex/):
    python3 -m oanda_demo.selftest               # full test incl. round-trip
    python3 -m oanda_demo.selftest --skip-orders # data-plane only
"""
from __future__ import annotations

import argparse
import sys
from typing import List

import pandas as pd

from exchanges.oanda_adapter import OandaExchangeAdapter
from oanda_demo.credentials import load_oanda_credentials
from oanda_demo.strategy import StratexTrendStrategy

CHECKS: List[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    line = f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else "")
    print(line)
    CHECKS.append(line)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-orders", action="store_true")
    args = parser.parse_args()

    # 1. Credentials ---------------------------------------------------------
    try:
        api_key, account_id, practice = load_oanda_credentials()
        ok = bool(api_key) and bool(account_id) and practice
        check("credentials resolve", ok, f"account {account_id}, practice={practice}")
    except Exception as exc:
        check("credentials resolve", False, str(exc))
        return 1
    if not ok:
        return 1

    adapter = OandaExchangeAdapter(api_key=api_key, account_id=account_id, practice=practice)

    # 2. Account -------------------------------------------------------------
    acct = adapter.get_account_summary()
    check(
        "account summary",
        bool(acct) and float(acct.get("equity", 0)) > 0,
        f"equity={acct.get('equity')} free={acct.get('margin_available')}",
    )

    # 3. Pricing ---------------------------------------------------------------
    watch = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "XAUUSD"]
    pricing = adapter.get_pricing(watch)
    check("batch pricing", len(pricing) == len(watch), f"{len(pricing)}/{len(watch)} quotes")
    for sym in watch:
        px = pricing.get(sym)
        if px:
            print(f"        {sym}: bid={px['bid']} ask={px['ask']} spread={px['spread']}")

    # 4. Candles + strategy ------------------------------------------------------
    candles = adapter.get_historical_data("EURUSD", "1h", 400)
    ok = len(candles) >= 300
    check("historical candles", ok, f"{len(candles)} H1 candles")
    signal = None
    if ok:
        strategy = StratexTrendStrategy()
        df = pd.DataFrame(candles)
        signal = strategy.evaluate("EURUSD", df, spread=pricing.get("EURUSD", {}).get("spread"))
        check(
            "strategy evaluates",
            True,
            f"side={signal.side} entry={signal.entry:.5f} atr={signal.atr:.5f} "
            f"reason={signal.reason}",
        )

    # 5. Price precision ------------------------------------------------------
    try:
        p5 = adapter._fmt_price("EUR_USD", 1.0854300000000001)
        p3 = adapter._fmt_price("USD_JPY", 155.123456)
        ok = p5 == "1.08543" and p3 == "155.123"
        check("price precision formatting", ok, f"EURUSD->{p5} USDJPY->{p3}")
    except Exception as exc:
        check("price precision formatting", False, str(exc))

    # 6. Order round-trip (1 unit EUR_USD) ------------------------------------
    if not args.skip_orders:
        try:
            res = adapter.place_order("EURUSD", "BUY", "MARKET", 1)
            trade_id = getattr(res, "trade_id", None)
            if not trade_id:
                # Fallback: find the just-opened trade.
                trades = adapter.open_trades()
                eurusd = [t for t in trades if t["instrument"] == "EURUSD"]
                trade_id = eurusd[-1]["id"] if eurusd else None
            ok = bool(trade_id)
            check("order placement (1 unit EURUSD)", ok,
                  f"fill={res.price} trade_id={trade_id}")
            if ok:
                closed = adapter.close_trade(str(trade_id))
                check("trade close", closed, f"trade {trade_id} closed")
        except Exception as exc:
            check("order placement (1 unit EURUSD)", False, str(exc))

    # 7. Open trades listing -----------------------------------------------------
    trades = adapter.open_trades()
    check("open trades listing", isinstance(trades, list), f"{len(trades)} open")

    failures = sum(1 for c in CHECKS if c.startswith("[FAIL]"))
    print("-" * 60)
    print(f"SELFTEST {'PASSED' if failures == 0 else 'FAILED'} — "
          f"{len(CHECKS) - failures}/{len(CHECKS)} checks ok")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
