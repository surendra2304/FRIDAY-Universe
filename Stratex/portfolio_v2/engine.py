"""Stratex live trading engine (OANDA practice account).

Usage:
    python3 -m friday.agents.stratex.engine --status    # account + open positions
    python3 -m friday.agents.stratex.engine --scan      # signals only, no orders
    python3 -m friday.agents.stratex.engine --run-once  # scan + place trades (default)

Behaviour:
  * Two validated daily strategies (see config.PORTFOLIO):
      - meanrev-d1 : RSI(3) extreme against the EMA(200) regime, ~70% win rate
      - breakout-d1: fresh 10-day Donchian break in the EMA(200) direction, 2:1 RR
  * One position per instrument (netting account), max_positions portfolio-wide,
    risk_pct of balance risked per trade via ATR-based stop distance.
  * Market orders carry server-side stop loss + take profit (GTC), so exits
    happen even if this process is not running.
  * Every action is appended to logs/stratex_trades.jsonl (audit trail).
"""
import argparse
import datetime
import json
import os

from .backtest import parse_candles
from .config import CREDENTIALS_FILE, EXEC, PORTFOLIO, PROJECT_ROOT, UNIVERSE, Config
from .oanda_client import OandaClient, OandaError
from .risk import position_units, quote_to_usd_rate
from .strategy import compute, protective_levels, signal_at

LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "stratex_trades.jsonl")
MIN_HISTORY = 260


def log_event(event):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    event["ts"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def ensure_account_id(client, config):
    """Use configured account id, else discover + persist it into credentials.md."""
    if config.account_id:
        return config.account_id
    accounts = client.list_accounts().get("accounts", [])
    if not accounts:
        raise OandaError("no OANDA accounts visible for this token")
    account_id = accounts[0]["id"]
    with open(CREDENTIALS_FILE, "a", encoding="utf-8") as fh:
        fh.write(f"OANDA_ACCOUNT_ID={account_id}\n")
    config.account_id = account_id
    return account_id


def instrument_meta(client, account_id, instrument):
    """(displayPrecision, pip_size) with a safe fallback if the API call fails."""
    try:
        details = client.instruments(account_id, [instrument])["instruments"][0]
        return int(details["displayPrecision"]), 10 ** int(details["pipLocation"])
    except Exception:
        precision = 3 if "JPY" in instrument else (2 if "XAU" in instrument else 5)
        pip = 0.01 if "JPY" in instrument else (0.1 if "XAU" in instrument else 0.0001)
        return precision, pip


def fmt_price(price, precision):
    return f"{price:.{precision}f}"


def find_signal(candles, cfg):
    """Newest-first signal search over the last `stale_bars` + 1 closed candles."""
    ind = compute(candles, cfg)
    n = len(candles)
    for back in range(0, cfg["stale_bars"] + 1):
        i = n - 1 - back
        if i < 1:
            break
        sig = signal_at(ind, i, cfg)
        if sig:
            return sig, ind, i
    return None, ind, None


def place_trade(client, account_id, instrument, side, units, stop, target, precision,
                strategy_name):
    order = {
        "order": {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(units if side == "long" else -units),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
            "stopLossOnFill": {"price": fmt_price(stop, precision), "timeInForce": "GTC"},
            "takeProfitOnFill": {"price": fmt_price(target, precision), "timeInForce": "GTC"},
            "clientExtensions": {
                "id": strategy_name, "tag": "stratex", "comment": strategy_name,
            },
        }
    }
    return client.create_order(account_id, order)


def run(mode="run-once"):
    config = Config()
    client = OandaClient(config.api_key, config.environment)
    account_id = ensure_account_id(client, config)

    summary = client.account_summary(account_id)["account"]
    balance = float(summary["balance"])
    currency = summary["currency"]
    open_trades = client.open_trades(account_id).get("trades", [])
    positions = {t["instrument"] for t in open_trades}
    print(f"[stratex] account {account_id} | balance {summary['balance']} {currency} "
          f"| NAV {summary['NAV']} | open positions: {len(open_trades)}")
    for t in open_trades:
        print(f"  open: {t['instrument']:8s} {int(float(t['currentUnits'])):+8d} units "
              f"| unrealized {t['unrealizedPL']} {currency} | tradeID {t['id']} "
              f"| opened {t.get('openTime', '?')}")

    if mode == "status":
        return

    slots = EXEC["max_positions"] - len(open_trades)
    if slots <= 0:
        print(f"[stratex] max_positions={EXEC['max_positions']} reached - managing only")
        return

    placed = 0
    candle_cache = {}
    for strat_name, cfg in PORTFOLIO.items():
        if placed >= slots:
            break
        for instrument in UNIVERSE:
            if placed >= slots:
                break
            if instrument in positions:
                continue
            try:
                if instrument not in candle_cache:
                    raw = client.candles(instrument, granularity=cfg["granularity"],
                                         count=cfg["candle_count"], price="M")
                    candle_cache[instrument] = parse_candles(raw)
                candles = candle_cache[instrument]
                if len(candles) < MIN_HISTORY:
                    continue
                sig, _ind, sig_i = find_signal(candles, cfg)
                if not sig:
                    continue
                bars_ago = len(candles) - 1 - sig_i
                print(f"[signal] {instrument} {sig['side'].upper()} via {strat_name} "
                      f"(strength {sig['strength']}, fired {bars_ago}d ago)")
                if mode == "scan":
                    continue

                prices = client.pricing(account_id, [instrument])["prices"][0]
                entry = float(prices["asks"][0]["price"] if sig["side"] == "long"
                              else prices["bids"][0]["price"])
                stop, target = protective_levels(sig["side"], entry, sig["atr"], cfg)
                precision, _pip = instrument_meta(client, account_id, instrument)
                tick = 10 ** (-precision)
                if sig["side"] == "long":
                    stop = min(round(stop, precision), entry - tick)
                    target = max(round(target, precision), entry + tick)
                else:
                    stop = max(round(stop, precision), entry + tick)
                    target = min(round(target, precision), entry - tick)

                quote_ccy = instrument.split("_")[1]
                rate = quote_to_usd_rate(client, account_id, quote_ccy)
                units = position_units(balance, EXEC["risk_pct"], entry, stop, rate)
                if units <= 0:
                    print(f"[skip  ] {instrument}: computed units below minimum")
                    continue

                resp = place_trade(client, account_id, instrument, sig["side"], units,
                                   stop, target, precision, strat_name)
                fill = resp.get("orderFillTransaction", {}) or {}
                trade_id = (fill.get("tradeOpened") or {}).get("tradeID")
                fill_price = fill.get("price")
                print(f"[trade ] {instrument} {sig['side'].upper()} {units} units "
                      f"@ {fill_price or fmt_price(entry, precision)} "
                      f"| SL {fmt_price(stop, precision)} TP {fmt_price(target, precision)} "
                      f"| {strat_name} | tradeID {trade_id}")
                log_event({"action": "open", "instrument": instrument, "side": sig["side"],
                           "units": units, "entry": fill_price or fmt_price(entry, precision),
                           "sl": fmt_price(stop, precision),
                           "tp": fmt_price(target, precision),
                           "trade_id": trade_id, "strategy": strat_name})
                placed += 1
                positions.add(instrument)
            except OandaError as exc:
                print(f"[error ] {instrument}: {exc}")
                log_event({"action": "error", "instrument": instrument,
                           "detail": str(exc)[:400]})

    print(f"[stratex] {mode} done - new trades this run: {placed}")


def main():
    ap = argparse.ArgumentParser(description="Stratex trading engine (OANDA practice)")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--scan", action="store_true", help="show signals only, place no orders")
    group.add_argument("--status", action="store_true", help="account and positions only")
    args = ap.parse_args()
    if args.status:
        run("status")
    elif args.scan:
        run("scan")
    else:
        run("run-once")


if __name__ == "__main__":
    main()
