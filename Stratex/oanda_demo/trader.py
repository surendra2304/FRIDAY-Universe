"""
oanda_demo/trader.py — Live OANDA demo (practice) trading engine for Stratex.

Owner directive (2026-11-13): implement OANDA demo trading and make Stratex
take profitable trades.

What one scan (--once) does:
  1. Pull the real account state (balance / equity / margin).
  2. Daily-loss circuit breaker (-3% NAV) and max-position governor.
  3. Manage open trades: move stops to breakeven at +1R (OANDA-side,
     survives restarts), detect closes, apply per-instrument cooldowns.
  4. Scan the watchlist with SMT-v2 (trend + momentum + ATR risk box).
  5. Size each entry to 1% account risk, capped by notional (10% equity)
     and free margin, then fire a MARKET order with native SL/TP attached.
  6. Log to data/oanda_demo_trades.csv and notify the owner on Telegram.

Usage (from the Stratex/ directory):
    python3 -m oanda_demo.trader --status          # account + open trades
    python3 -m oanda_demo.trader --once            # one scan (act on signals)
    python3 -m oanda_demo.trader --once --dry-run  # signals only, no orders
    python3 -m oanda_demo.trader --loop --interval 300
    python3 -m oanda_demo.trader --flatten         # emergency: close all trades

Credentials: OANDA_API_KEY / OANDA_ACCOUNT_ID env vars, else credentials.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

try:
    from logger import get_logger
except Exception:  # pragma: no cover - fallback when run outside Stratex/
    import logging

    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)

from exchanges.oanda_adapter import OandaExchangeAdapter
from oanda_demo.credentials import load_oanda_credentials
from oanda_demo.strategy import (
    DonchianTrendStrategy,
    MeanReversionStrategy,
    Signal,
    StratexTrendStrategy,
)

logger = get_logger("oanda_demo_trader")

# --- Tunables (kept conservative: this is real-order demo trading) ----------
# FX-only: the practice account trades 68 currency pairs (no metals/indices).
WATCHLIST = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "EURJPY", "EURGBP",
]
RISK_PER_TRADE_PCT = 0.01      # 1% of equity risked per trade
MAX_OPEN_TRADES = 4            # concurrent positions across the watchlist
MAX_NOTIONAL_PCT = 0.25        # notional cap: 25% of equity per position
MAX_LEVERAGE = 50.0            # OANDA demo margin rate 2% on majors
DAILY_LOSS_LIMIT_PCT = 0.03    # -3% NAV day: stop opening new trades
REENTRY_COOLDOWN_S = 3600      # 60 min cooldown per instrument after a close
BREAKEVEN_R = 1.0              # SMT mode: move stop to entry at +1R
STRATEGY_NAME = os.getenv("STRATEX_OANDA_STRATEGY", "mr").lower()
# NOTE: timeframes use the adapter's granularity-map keys ("15m","1h","4h","1d")
# — anything else silently falls back to M15 in get_historical_data.
_DEFAULT_TF = {"mr": "1d", "donchian": "4h", "smt": "4h"}
TIMEFRAME = os.getenv("STRATEX_OANDA_TF", _DEFAULT_TF.get(STRATEGY_NAME, "4h"))
HISTORY_BARS = 400

DATA_DIR = Path(os.getenv("STRATEX_OANDA_DATA_DIR", "data"))
STATE_FILE = DATA_DIR / "oanda_demo_state.json"
TRADES_CSV = DATA_DIR / "oanda_demo_trades.csv"
KILL_SWITCH = DATA_DIR / "oanda_demo_kill_switch"


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _rfc3339_to_unix(ts: str) -> float:
    """OANDA timestamps can carry nanoseconds; Python 3.10 needs truncation."""
    ts = (ts or "").strip()
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return datetime.fromisoformat(ts[:23] + "+00:00").timestamp()


def build_default_strategy():
    """Strategy selected by env (STRATEX_OANDA_STRATEGY). Default: MR —
    the only strategy class that survived 20y/2.9y validation on the FX
    practice basket (see data/oanda_demo_backtest_*.json)."""
    if STRATEGY_NAME == "smt":
        return StratexTrendStrategy()
    if STRATEGY_NAME == "donchian":
        return DonchianTrendStrategy()
    return MeanReversionStrategy()


class OandaDemoTrader:
    """Risk-first OANDA practice-account trading engine."""

    def __init__(
        self,
        adapter: Optional[OandaExchangeAdapter] = None,
        strategy: Optional[StratexTrendStrategy] = None,
        timeframe: str = TIMEFRAME,
        dry_run: bool = False,
        state_file: Optional[Path] = None,
    ):
        if adapter is None:
            api_key, account_id, practice = load_oanda_credentials()
            adapter = OandaExchangeAdapter(
                api_key=api_key, account_id=account_id, practice=practice
            )
        self.adapter = adapter
        self.strategy = strategy or build_default_strategy()
        self.timeframe = timeframe
        self.dry_run = dry_run
        self.state_file = state_file or STATE_FILE

    # -- state ------------------------------------------------------------
    def _load_state(self) -> Dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_state(self, state: Dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _quote_to_usd(quote: str, pricing: Dict[str, Dict[str, float]]) -> float:
        """Convert one unit of quote currency to account USD."""
        if quote == "USD":
            return 1.0
        if quote == "JPY":
            px = pricing.get("USDJPY")
            return 1.0 / px["mid"] if px else 0.0
        for cand in (quote + "USD", "USD" + quote):
            px = pricing.get(cand)
            if px:
                return px["mid"] if cand.startswith(quote) else 1.0 / px["mid"]
        return 0.0

    def _position_units(
        self,
        symbol: str,
        signal: Signal,
        pricing: Dict[str, Dict[str, float]],
        equity: float,
        free_margin: float,
    ) -> int:
        """Units so that SL hit = RISK_PER_TRADE_PCT of equity (capped)."""
        quote = symbol[3:]
        conv = self._quote_to_usd(quote, pricing)
        sl_dist = abs(signal.entry - signal.stop)
        if conv <= 0 or sl_dist <= 0:
            return 0
        risk_usd = equity * RISK_PER_TRADE_PCT
        units = int(risk_usd / (sl_dist * conv))
        mid = pricing.get(symbol, {}).get("mid", 0) or signal.entry
        if mid <= 0:
            return 0
        max_units_notional = int((equity * MAX_NOTIONAL_PCT) / mid)
        max_units_margin = int((free_margin * 0.5) * MAX_LEVERAGE / mid)
        return max(0, min(units, max_units_notional, max_units_margin))

    def _log_trade_csv(self, row: Dict) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            new_file = not TRADES_CSV.exists()
            with open(TRADES_CSV, "a", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
                if new_file:
                    writer.writeheader()
                writer.writerow(row)
        except OSError as exc:
            logger.warning(f"[OANDA-DEMO] trade csv write failed: {exc}")

    def _telegram(self, text: str) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat = os.getenv("TELEGRAM_CHAT_ID", "")
        if not token or not chat:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": text},
                timeout=8,
            )
        except Exception:
            pass

    # -- core scan ----------------------------------------------------------
    def run_once(self) -> Dict:
        summary: Dict = {"ts": datetime.now(timezone.utc).isoformat(), "actions": []}
        if KILL_SWITCH.exists():
            summary["halted"] = "kill switch present"
            logger.warning("[OANDA-DEMO] kill switch active — skipping scan")
            return summary

        acct = self.adapter.get_account_summary()
        if not acct:
            summary["error"] = "account summary unavailable"
            return summary
        equity = float(acct.get("equity", 0))
        free_margin = float(acct.get("margin_available", 0))
        summary["equity"] = round(equity, 2)
        summary["free_margin"] = round(free_margin, 2)

        state = self._load_state()
        today = _utc_day()
        if state.get("day") != today:
            state["day"] = today
            state["day_start_nav"] = equity
        day_start = float(state.get("day_start_nav", equity)) or equity
        daily_dd = (equity - day_start) / day_start if day_start else 0.0
        summary["daily_pnl_pct"] = round(daily_dd * 100, 2)

        trades = self.adapter.open_trades()
        summary["open_trades"] = len(trades)
        self._manage_open_trades(trades, pricing=None, state=state, summary=summary)

        # Re-read trades after management (SL updates) for accurate counts.
        trades = self.adapter.open_trades()
        open_instruments = {t["instrument"] for t in trades}

        pricing = self.adapter.get_pricing(WATCHLIST + ["USDJPY"])
        if not pricing:
            summary["error"] = "pricing unavailable"
            self._save_state(state)
            return summary
        summary["spreads"] = {s: round(p["spread"], 6) for s, p in pricing.items()}

        blockers: List[str] = []
        if len(trades) >= MAX_OPEN_TRADES:
            blockers.append(f"max open trades ({MAX_OPEN_TRADES})")
        if daily_dd <= -DAILY_LOSS_LIMIT_PCT:
            blockers.append(f"daily loss limit ({daily_dd*100:.1f}%)")
        now = time.time()
        cooldowns = state.get("cooldowns", {})

        for symbol in WATCHLIST:
            if symbol in open_instruments:
                continue
            cd_until = cooldowns.get(symbol, 0)
            if isinstance(cd_until, (int, float)) and now < float(cd_until):
                continue
            if blockers:
                break

            candles = self.adapter.get_historical_data(symbol, self.timeframe, HISTORY_BARS)
            if not candles:
                continue
            df = pd.DataFrame(candles)
            spread = pricing.get(symbol, {}).get("spread")
            signal = self.strategy.evaluate(symbol, df, spread=spread)

            if not signal.side:
                continue

            units = self._position_units(symbol, signal, pricing, equity, free_margin)
            if units < 1:
                continue

            side_word = "BUY" if signal.side == "LONG" else "SELL"
            exit_txt = (
                f"TP {signal.take:.5f} (R:R {signal.rr:.2f})" if signal.take
                else f"trail {getattr(self.strategy.cfg, 'trailing_atr', '?')}xATR"
            )
            summary["actions"].append(
                f"{side_word} {symbol} {units}u @~{signal.entry:.5f} "
                f"SL {signal.stop:.5f} {exit_txt}"
            )
            logger.info(
                f"[OANDA-DEMO] SIGNAL {side_word} {symbol} units={units} "
                f"entry~{signal.entry:.5f} sl={signal.stop:.5f} tp={signal.take:.5f} "
                f"rr={signal.rr:.2f} reason={signal.reason}"
            )
            if self.dry_run:
                summary["actions"][-1] = "[DRY] " + summary["actions"][-1]
                continue

            try:
                result = self.adapter.place_order(
                    symbol, side_word, "MARKET", units,
                    stop_loss=signal.stop, take_profit=signal.take,
                )
            except Exception as exc:
                logger.warning(f"[OANDA-DEMO] order failed for {symbol}: {exc}")
                summary["actions"].append(f"ORDER FAILED {symbol}: {exc}")
                continue

            row = {
                "ts": summary["ts"],
                "strategy": self.strategy.name,
                "symbol": symbol,
                "side": side_word,
                "units": units,
                "price": result.price,
                "sl": signal.stop,
                "tp": signal.take or "",
                "order_id": result.order_id,
                "trade_id": getattr(result, "trade_id", "") or "",
                "status": result.status,
                "timeframe": self.timeframe,
            }
            self._log_trade_csv(row)
            self._telegram(
                f"Stratex OANDA demo: {side_word} {units} {symbol} @ {result.price}\n"
                f"SL {signal.stop:.5f} | {exit_txt}\n"
                f"Risk 1% of ${equity:,.0f} equity"
            )
            open_instruments.add(symbol)
            trades = self.adapter.open_trades()  # refresh count
            if len(trades) >= MAX_OPEN_TRADES:
                blockers.append(f"max open trades ({MAX_OPEN_TRADES})")

        self._save_state(state)
        return summary

    # -- trade management -----------------------------------------------------
    def _manage_open_trades(
        self,
        trades: List[Dict],
        pricing: Optional[Dict[str, Dict[str, float]]],
        state: Dict,
        summary: Dict,
    ) -> None:
        """Breakeven moves at +1R; close detection -> cooldowns."""
        known: set = set(state.get("known_trade_ids", []))
        current_ids = {t["id"] for t in trades}

        # Trades that disappeared since last scan -> closed: instrument cooldown.
        if known:
            now = time.time()
            cooldowns = state.setdefault("cooldowns", {})
            for gone_id in known - current_ids:
                summary.setdefault("closes", []).append(gone_id)
                self._telegram(f"Stratex OANDA demo: trade {gone_id} closed.")
        state["known_trade_ids"] = sorted(current_ids)

        # Remember id -> instrument so future closes can arm the cooldown.
        id_map: Dict[str, str] = state.setdefault("trade_instruments", {})
        for t in trades:
            id_map[t["id"]] = t["instrument"]
        if known:
            cooldowns = state.setdefault("cooldowns", {})
            for gone_id in known - current_ids:
                instrument = id_map.get(gone_id, "")
                if instrument:
                    cooldowns[instrument] = time.time() + REENTRY_COOLDOWN_S

        # Exit management: rule exit (MR), chandelier trail (Donchian), or
        # breakeven (SMT).
        rule_exit = getattr(self.strategy.cfg, "exit_rule", None) == "mr"
        trailing_mult = getattr(self.strategy.cfg, "trailing_atr", None)
        if pricing is None:
            need = [t["instrument"] for t in trades]
            pricing = self.adapter.get_pricing(need) if need else {}

        for t in trades:
            if not t["price"]:
                continue

            if rule_exit:
                # --- MR rule exit: close when close re-crosses EMA5, or time stop.
                candles = self.adapter.get_historical_data(
                    t["instrument"], self.timeframe, HISTORY_BARS
                )
                if not candles:
                    continue
                d = self.strategy.add_indicators(pd.DataFrame(candles))
                open_ts = _rfc3339_to_unix(t.get("open_time", ""))
                since = d[d["timestamp"] >= open_ts] if open_ts else d
                if since.empty:
                    continue
                held = len(since) - 1
                last = d.iloc[-1]
                c = float(last["close"])
                exit_level = float(last["ema_exit"])
                max_hold = getattr(self.strategy.cfg, "max_hold_bars", 10)
                direction = 1.0 if t["units"] > 0 else -1.0
                trigger = (
                    (direction > 0 and c > exit_level)
                    or (direction < 0 and c < exit_level)
                    or held >= max_hold
                )
                if not trigger:
                    continue
                closed = False
                if not self.dry_run:
                    try:
                        closed = self.adapter.close_trade(t["id"])
                    except Exception as exc:
                        logger.warning(f"[OANDA-DEMO] rule-exit close failed {t['id']}: {exc}")
                if closed or self.dry_run:
                    why = "RULE" if held < max_hold else "TIME"
                    summary.setdefault("rule_exits", []).append(t["id"])
                    logger.info(
                        f"[OANDA-DEMO] MR {why} exit on {t['instrument']} "
                        f"trade {t['id']} (close {c:.5f} vs EMA5 {exit_level:.5f})"
                    )
                continue

            if trailing_mult is not None:
                # --- chandelier trailing stop ---
                candles = self.adapter.get_historical_data(
                    t["instrument"], self.timeframe, HISTORY_BARS
                )
                if not candles:
                    continue
                d = self.strategy.add_indicators(pd.DataFrame(candles))
                open_ts = _rfc3339_to_unix(t.get("open_time", ""))
                since = d[d["timestamp"] >= open_ts] if open_ts else d
                if since.empty:
                    continue
                atr_now = float(d.iloc[-1]["atr"])
                if atr_now <= 0:
                    continue
                if t["units"] > 0:
                    extreme = float(since["close"].max())
                    new_sl = extreme - trailing_mult * atr_now
                    improve = new_sl > t["stop_loss"] if t["stop_loss"] else True
                else:
                    extreme = float(since["close"].min())
                    new_sl = extreme + trailing_mult * atr_now
                    improve = new_sl < t["stop_loss"] if t["stop_loss"] else False
                if not improve:
                    continue
                ok = False
                if not self.dry_run:
                    try:
                        ok = self.adapter.update_trade_stop_loss(
                            t["instrument"], t["id"], new_sl
                        )
                    except Exception as exc:
                        logger.warning(f"[OANDA-DEMO] trail update failed {t['id']}: {exc}")
                if ok or self.dry_run:
                    summary.setdefault("trailed", []).append(t["id"])
                    logger.info(
                        f"[OANDA-DEMO] chandelier trail on {t['instrument']} "
                        f"trade {t['id']} -> {new_sl:.5f} (extreme {extreme:.5f})"
                    )
                continue

            # --- SMT breakeven at +1R ---
            if not t["stop_loss"]:
                continue
            direction = 1.0 if t["units"] > 0 else -1.0
            px = pricing.get(t["instrument"])
            if not px:
                continue
            risk_dist = abs(t["price"] - t["stop_loss"])
            if risk_dist <= 0:
                continue
            progress_r = direction * (px["mid"] - t["price"]) / risk_dist
            if progress_r < BREAKEVEN_R:
                continue
            # Stop not yet at/beyond entry -> move to breakeven.
            if (direction > 0 and t["stop_loss"] < t["price"]) or (
                direction < 0 and t["stop_loss"] > t["price"]
            ):
                ok = False
                if not self.dry_run:
                    try:
                        ok = self.adapter.update_trade_stop_loss(
                            t["instrument"], t["id"], t["price"]
                        )
                    except Exception as exc:
                        logger.warning(f"[OANDA-DEMO] SL update failed {t['id']}: {exc}")
                if ok or self.dry_run:
                    summary.setdefault("breakeven", []).append(t["id"])
                    logger.info(
                        f"[OANDA-DEMO] breakeven stop set on {t['instrument']} "
                        f"trade {t['id']} at {t['price']}"
                    )

    # -- utilities ------------------------------------------------------------
    def status(self) -> Dict:
        acct = self.adapter.get_account_summary()
        trades = self.adapter.open_trades()
        state = self._load_state()
        return {
            "account": acct,
            "open_trades": trades,
            "daily_day": state.get("day"),
            "day_start_nav": state.get("day_start_nav"),
            "timeframe": self.timeframe,
            "watchlist": WATCHLIST,
        }

    def flatten(self) -> Dict:
        """Close every open trade (emergency control)."""
        trades = self.adapter.open_trades()
        results = {}
        for t in trades:
            try:
                results[t["id"]] = self.adapter.close_trade(t["id"])
            except Exception as exc:
                results[t["id"]] = f"error: {exc}"
        self._telegram(f"Stratex OANDA demo FLATTEN: closed {len(trades)} trades.")
        return {"closed": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Stratex OANDA demo trader")
    parser.add_argument("--once", action="store_true", help="run a single scan")
    parser.add_argument("--loop", action="store_true", help="run forever")
    parser.add_argument("--interval", type=int, default=300, help="loop seconds")
    parser.add_argument("--status", action="store_true", help="print account status")
    parser.add_argument("--flatten", action="store_true", help="close all open trades")
    parser.add_argument("--dry-run", action="store_true", help="no real orders")
    args = parser.parse_args()

    trader = OandaDemoTrader(dry_run=args.dry_run)

    if args.status:
        print(json.dumps(trader.status(), indent=2, default=str))
        return 0
    if args.flatten:
        print(json.dumps(trader.flatten(), indent=2, default=str))
        return 0
    if args.loop:
        logger.info("[OANDA-DEMO] loop mode starting")
        while True:
            try:
                out = trader.run_once()
                logger.info(f"[OANDA-DEMO] scan: {json.dumps(out, default=str)}")
            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.warning(f"[OANDA-DEMO] scan error: {exc}")
            time.sleep(max(30, args.interval))
        return 0
    if args.once or not any(vars(args).values()):
        out = trader.run_once()
        print(json.dumps(out, indent=2, default=str))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
