#!/usr/bin/env python3
"""
Stratex/scripts/pepperstone_shakedown.py — TASK-STR-PEP-001 demo shakedown.

THE GATE: no strategy trades Pepperstone until this script passes
end-to-end against the Pepperstone DEMO account (5376835, $10,000
virtual). It is NOT run as part of the adapter PR — it needs the owner's
Spotware Open API authorization first (his cTrader ID sign-in + approve
tap), which issues the credentials the env names below carry.

What it proves, in order (each check prints PASS/FAIL; exit 0 only if
every check passes):
  0. Environment present (names only — values are never printed) and
     TRADING_MODE is not LIVE.
  1. Connect + application auth + account auth; the resolved account is
     a DEMO account (isLive == False) and, when
     PEPPERSTONE_CTRADER_ACCOUNT_NUMBER is set, its traderLogin matches.
  2. Balance read: the broker balance equals the expected demo balance
     (default 10000.00, override with
     PEPPERSTONE_SHAKEDOWN_EXPECTED_BALANCE_USD) within $0.01 — this
     empirically proves the moneyDigits scaling.
  3. The 11 required instruments resolve against the broker's own
     symbol list; their real Pepperstone names, digits, lotSize and
     minVolume are printed. Copper/platinum are reported as
     informational (the comm7 panel was judged on 7 futures legs; HG/PL
     availability decides whether those panels keep all 7 legs).
  4. Price-scale sanity: XAUUSD last M1 trendbar close within 2% of the
     live spot bid (proves the trendbar /100000 scaling).
  5. Pre-trade reconcile: no EURUSD position may already be open.
  6. One tiny protected trade: 0.01-lot EURUSD BUY market order with a
     50-pip stop distance and a 100-pip take-profit distance. The
     adapter's own read-back verification must pass (it halts the venue
     and raises otherwise), and an INDEPENDENT reconcile read confirms
     the position carries SL/TP at the intended levels.
  7. Balance reconciliation: adapter.reconcile_balance() against the
     pre-trade balance minus the round-trip commission band passes.
  8. Disconnect simulation: the transport is dropped abruptly; a fresh
     session re-authenticates and the position is found still standing
     with the same SL/TP (broker-side protection survives disconnects).
  9. The test position is closed through the adapter; a final reconcile
     shows no EURUSD position, and the final balance is the start
     balance minus only the commissions (within tolerance).

Usage:
  python Stratex/scripts/pepperstone_shakedown.py [--dry-run]
  --dry-run stops after check 4 (no orders are placed) and its verdict
  is labelled DRY-RUN ONLY — it does NOT clear the gate below.

Env (names only): PEPPERSTONE_CTRADER_CLIENT_ID,
PEPPERSTONE_CTRADER_CLIENT_SECRET, PEPPERSTONE_CTRADER_ACCESS_TOKEN,
PEPPERSTONE_CTRADER_REFRESH_TOKEN (optional),
PEPPERSTONE_CTRADER_ACCOUNT_ID (optional),
PEPPERSTONE_CTRADER_ACCOUNT_NUMBER (optional),
PEPPERSTONE_SHAKEDOWN_EXPECTED_BALANCE_USD (optional, default 10000).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from exchanges import ctrader_openapi as oa  # noqa: E402
from exchanges.pepperstone_ctrader_adapter import PepperstoneCTraderAdapter  # noqa: E402

REQUIRED_ENV = [
    "PEPPERSTONE_CTRADER_CLIENT_ID",
    "PEPPERSTONE_CTRADER_CLIENT_SECRET",
    "PEPPERSTONE_CTRADER_ACCESS_TOKEN",
]

# Research-side name -> what the comm7/idx7 panels need it for.
REQUIRED_INSTRUMENTS = {
    "XAUUSD": "gold (GC)",
    "XAGUSD": "silver (SI)",
    "XTIUSD": "WTI crude (CL)",
    "XBRUSD": "Brent crude (BZ)",
    "XNGUSD": "natural gas (NG)",
    "US500": "S&P 500 index",
    "USTEC": "Nasdaq 100 index (NAS100)",
    "US30": "Dow 30 index",
    "DE40": "DAX 40 index (GER40)",
    "UK100": "FTSE 100 index",
    "JP225": "Nikkei 225 index (JPN225)",
}
INFORMATIONAL_INSTRUMENTS = {
    "XCUUSD": "copper (HG) — comm7 panel leg, availability UNVERIFIED",
    "XPTUSD": "platinum (PL) — comm7 panel leg, availability UNVERIFIED",
}

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def verdict(dry_run: bool = False) -> int:
    failed = [n for n, ok, _ in RESULTS if not ok]
    print("\n================ SHAKEDOWN VERDICT ================")
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if failed:
        print(f"OVERALL: FAIL ({len(failed)} check(s) failed). "
              "No strategy may trade this venue.")
        return 1
    if dry_run:
        # TASK-STR-PEP-002 (PR #1097 review condition): a dry run must
        # never print the gate-clearing banner — the order-path checks
        # were not run, so the gate has NOT been passed.
        print("OVERALL: DRY-RUN ONLY — the read-only checks passed, but "
              "the order-path checks (5-9) were NOT run. This does NOT "
              "clear the fail-closed gate: no strategy may trade this "
              "venue until a full shakedown passes end-to-end.")
        return 0
    print("OVERALL: PASS — the Pepperstone demo venue clears the "
          "fail-closed gate. Activation wiring (engine + env) is still a "
          "separate reviewed step.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="stop after the read-only checks (no orders)")
    args = parser.parse_args()

    # -- Check 0: environment -------------------------------------------
    missing = [n for n in REQUIRED_ENV if not os.getenv(n)]
    if not check("env credentials present (names only)", not missing,
                 f"missing: {', '.join(missing)}" if missing else "all set"):
        return verdict(args.dry_run)
    if not check("TRADING_MODE is not LIVE",
                 os.environ.get("TRADING_MODE", "TESTNET").upper() != "LIVE"):
        return verdict(args.dry_run)

    expected_balance = float(
        os.getenv("PEPPERSTONE_SHAKEDOWN_EXPECTED_BALANCE_USD", "10000.00")
    )
    adapter = PepperstoneCTraderAdapter()

    # -- Check 1: connect + auth -----------------------------------------
    try:
        adapter._ensure_connected()
        check("connect + application auth + account auth", True,
              f"ctid={adapter.account_id}")
    except Exception as e:
        check("connect + application auth + account auth", False, str(e))
        return verdict(args.dry_run)
    trader = adapter._trader
    check("account is DEMO (trader record loaded)",
          bool(trader) and not adapter.halted,
          f"login={trader.get('trader_login')} broker={trader.get('broker_name')}")
    account_number = os.getenv("PEPPERSTONE_CTRADER_ACCOUNT_NUMBER", "")
    if account_number:
        check("traderLogin matches the expected account number",
              str(trader.get("trader_login")) == str(account_number),
              f"expected {account_number}, broker says {trader.get('trader_login')}")

    # -- Check 2: balance + moneyDigits ----------------------------------
    summary = adapter.get_account_summary()
    balance = float(summary.get("balance", 0.0))
    if not check("balance read proves moneyDigits scaling",
                 abs(balance - expected_balance) <= 0.01,
                 f"broker balance={balance:.2f}, expected={expected_balance:.2f}, "
                 f"moneyDigits={trader.get('money_digits')}"):
        return verdict(args.dry_run)

    # -- Check 3: instruments ---------------------------------------------
    unresolved = []
    for symbol, purpose in REQUIRED_INSTRUMENTS.items():
        try:
            record = adapter._resolve_symbol(symbol)
            details = adapter._symbol_details(int(record["symbol_id"]))
            print(f"       {symbol:8s} -> broker name "
                  f"{record.get('symbol_name')!r} digits={details.get('digits')} "
                  f"lotSize={details.get('lot_size')} "
                  f"minVolume={details.get('min_volume')}  ({purpose})")
        except Exception as e:
            unresolved.append(symbol)
            print(f"       {symbol:8s} -> UNRESOLVED ({purpose}): {e}")
    check("all 11 required instruments resolve", not unresolved,
          f"unresolved: {', '.join(unresolved)}" if unresolved else "11/11")
    for symbol, purpose in INFORMATIONAL_INSTRUMENTS.items():
        try:
            record = adapter._resolve_symbol(symbol)
            print(f"       INFO {symbol}: available as "
                  f"{record.get('symbol_name')!r} ({purpose})")
        except Exception:
            print(f"       INFO {symbol}: NOT available ({purpose}) — the "
                  "comm7 panels lose this leg; activation decides the panel "
                  "composition.")

    # -- Check 4: trendbar price scale -------------------------------------
    try:
        candles = adapter.get_historical_data("XAUUSD", "1m", 5)
        ticker = adapter.get_ticker("XAUUSD")
        last_close = candles[-1]["close"] if candles else 0.0
        ok = last_close > 0 and ticker.bid > 0 and \
            abs(last_close - ticker.bid) / ticker.bid < 0.02
        check("trendbar /100000 scale matches live spot", ok,
              f"last M1 close={last_close:.2f}, spot bid={ticker.bid:.2f}")
    except Exception as e:
        check("trendbar /100000 scale matches live spot", False, str(e))

    if args.dry_run:
        print("\n--dry-run: stopping before any order placement.")
        return verdict(args.dry_run)

    # -- Check 5: pre-trade reconcile ---------------------------------------
    eur_id = int(adapter._resolve_symbol("EURUSD")["symbol_id"])
    pre_positions = adapter._fetch_positions_raw()
    eur_open = [p for p in pre_positions
                if int((p.get("trade_data", {}) or {}).get("symbol_id", -1)) == eur_id]
    if not check("no EURUSD position already open", not eur_open,
                 f"{len(eur_open)} EURUSD position(s) open"):
        return verdict(args.dry_run)
    start_balance = balance

    # -- Check 6: tiny protected trade + independent read-back --------------
    bid, ask = adapter._spot(eur_id)
    stop_loss = round(ask - 0.0050, 5)
    take_profit = round(ask + 0.0100, 5)
    position_id = None
    try:
        result = adapter.place_order(
            "EURUSD", "BUY", "MARKET", 0.01,
            stop_loss=stop_loss, take_profit=take_profit,
        )
        positions = adapter.get_positions_or_none() or []
        eur_positions = [p for p in positions if p.symbol == "EURUSD"]
        position_id = int(eur_positions[0].position_id) if eur_positions else None
        ok = result.status == "FILLED" and position_id is not None \
            and not adapter.halted
        check("0.01-lot EURUSD BUY filled with adapter read-back verified",
              ok, f"status={result.status} position={position_id} "
                  f"fill={result.avg_price}")
    except Exception as e:
        check("0.01-lot EURUSD BUY filled with adapter read-back verified",
              False, str(e))
        return verdict(args.dry_run)

    # Independent confirmation straight off a fresh reconcile (not the
    # adapter's cached view of its own order).
    raw = adapter._read_back_position(position_id)
    tol = 3.0 * 10 ** -5
    sl_ok = raw is not None and raw.get("stop_loss") is not None \
        and abs(float(raw["stop_loss"]) - stop_loss) <= tol + 1e-9
    tp_ok = raw is not None and raw.get("take_profit") is not None \
        and abs(float(raw["take_profit"]) - take_profit) <= tol + 1e-9
    if not check("independent reconcile confirms SL/TP at intended levels",
                 bool(sl_ok and tp_ok),
                 f"broker sl={None if raw is None else raw.get('stop_loss')} "
                 f"tp={None if raw is None else raw.get('take_profit')} "
                 f"(intended {stop_loss}/{take_profit})"):
        return verdict(args.dry_run)

    # -- Check 7: balance reconciliation -------------------------------------
    try:
        rec = adapter.reconcile_balance(start_balance, tolerance=0.50)
        check("balance reconciliation within commission band", bool(rec["ok"]),
              f"broker={rec['broker_balance']:.2f} start={start_balance:.2f} "
              f"diff={rec['diff']:+.2f}")
    except Exception as e:
        check("balance reconciliation within commission band", False, str(e))

    # -- Check 8: disconnect simulation ---------------------------------------
    intended_sl = float(raw["stop_loss"])
    intended_tp = float(raw["take_profit"])
    try:
        transport = adapter._get_transport()
        transport.close()  # abrupt drop, no graceful logout
        adapter._on_disconnect("shakedown simulated drop")
        time.sleep(3)
        adapter._transport = oa.OpenApiTransport(
            adapter.host, adapter.port,
            on_event=adapter._on_event, on_disconnect=adapter._on_disconnect,
        )
        adapter._account_authorized = False
        raw_after = adapter._read_back_position(position_id)
        ok = raw_after is not None \
            and abs(float(raw_after.get("stop_loss") or 0) - intended_sl) <= tol \
            and abs(float(raw_after.get("take_profit") or 0) - intended_tp) <= tol \
            and not adapter.halted
        check("protection survives a disconnect (fresh session read-back)",
              bool(ok),
              f"sl={None if raw_after is None else raw_after.get('stop_loss')} "
              f"tp={None if raw_after is None else raw_after.get('take_profit')}")
    except Exception as e:
        check("protection survives a disconnect (fresh session read-back)",
              False, str(e))

    # -- Check 9: close + final state ------------------------------------------
    try:
        adapter.close_position_by_id(position_id)
        remaining = [p for p in adapter._fetch_positions_raw()
                     if int((p.get("trade_data", {}) or {}).get("symbol_id", -1)) == eur_id]
        final = adapter.get_account_summary()
        final_balance = float(final.get("balance", 0.0))
        # Round trip on 0.01 lot EURUSD costs ~$0.06 commission total.
        ok = not remaining and abs(final_balance - start_balance) <= 0.50
        check("test position closed; account flat; balance sane", ok,
              f"final balance={final_balance:.2f} "
              f"(start {start_balance:.2f}, delta {final_balance - start_balance:+.2f})")
    except Exception as e:
        check("test position closed; account flat; balance sane", False, str(e))

    return verdict(args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
