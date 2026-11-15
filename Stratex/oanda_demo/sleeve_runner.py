"""
oanda_demo/sleeve_runner.py — governed sleeve engine for OANDA legs.

TASK-STR-FWD-002 (sleeve extension, owner approval 2026-11-15): the
forex leg of the RD-002 Stage-C best-per-class portfolio sleeve —
tsmom2_dual/roc90_ema200 @ FOREX28 1d — trades on the OANDA practice
account through THIS runner, and nothing else trades through it.

Governance: the leg is registered in config_strategy.
PRODUCTION_STRATEGY_REGISTRY ("sleeve_tsmom2_dual", status VALIDATED,
sleeve="best_per_class") — the single governance source shared with
the Binance daemon. This runner refuses entries unless that entry is
VALIDATED. It is a SEPARATE engine from oanda_demo.trader (FX-MR-v4):
separate state, separate pause/kill files, and it never touches the
FX-MR-v4 engine's pause (STRATEX_OANDA_ENTRIES_PAUSED / its data dir).

Safety rails:
  * Practice account only (the adapter enforces practice-only itself).
  * 1% of equity risk per trade; 25% notional cap; free-margin gate.
  * Shared-account daily breaker: account NAV down 3% on the day ->
    no new entries (same basis as the other forward entrants).
  * Sleeve pause: STRATEX_SLEEVE_ENTRIES_PAUSED env or the
    sleeve_entries_paused file in this runner's data dir — the file
    is what the daemon's forward guard writes when the sleeve-level
    kill rule (combined sleeve drawdown > 5% of equity) breaches.
  * OANDA nets per instrument: an instrument with ANY open trade
    (this runner's, FX-MR-v4's, or anyone's) is never traded, so a
    sleeve order can never merge into a foreign position.
  * Every close is booked into the phase-2 measurement fill ledger
    (measurement/fill_ledger.append_fill) tagged with BOTH the sleeve
    identity ("sleeve": "best_per_class") and the component strategy
    ("strategy_sleeve_tsmom2_dual"), with realised PnL read back from
    the broker's own closed-trade record.

Bars: OANDA daily candles requested with dailyAlignment=0 /
alignmentTimezone=UTC (UTC-midnight-aligned, complete candles only)
— the judged research bars were Yahoo calendar-day bars; the
alignment convention matches, the price source is the venue's own
(disclosed in the registry entry and the task board entry).

Usage (from the Stratex/ directory):
    python3 -m oanda_demo.sleeve_runner --status
    python3 -m oanda_demo.sleeve_runner --once [--dry-run]
    python3 -m oanda_demo.sleeve_runner --loop --interval 300
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

try:
    from logger import get_logger
except Exception:  # pragma: no cover - fallback when run outside Stratex/
    import logging

    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)

from config_strategy import FOREX28_SYMBOLS, PRODUCTION_STRATEGY_REGISTRY
from exchanges.oanda_adapter import OandaExchangeAdapter
from oanda_demo import sleeve_signals
from oanda_demo.credentials import load_oanda_credentials

logger = get_logger("oanda_sleeve_runner")

COMPONENT_KEY = "sleeve_tsmom2_dual"
STRATEGY_TAG = "strategy_sleeve_tsmom2_dual"
SLEEVE_TAG = "best_per_class"
TIMEFRAME = "1d"
HISTORY_BARS = 400
RISK_PER_TRADE_PCT = 0.01      # phase-3 per-trade risk cap
MAX_NOTIONAL_PCT = 0.25        # per-position notional cap (as trader)
DAILY_LOSS_LIMIT_PCT = 0.03    # shared-account daily breaker
REENTRY_COOLDOWN_S = 3600      # per-instrument cooldown after a close
MAX_OPEN_TRADES = 28           # one per FOREX28 instrument at most

DATA_DIR = Path(os.getenv("STRATEX_SLEEVE_OANDA_DIR", "data/sleeve_oanda"))
STATE_FILE = DATA_DIR / "sleeve_state.json"
PAUSE_FILE = DATA_DIR / "sleeve_entries_paused"
KILL_FILE = DATA_DIR / "sleeve_kill_switch"


def sleeve_entries_paused() -> bool:
    """This runner's OWN pause (never the FX-MR-v4 engine's)."""
    if os.getenv("STRATEX_SLEEVE_ENTRIES_PAUSED", "").lower() in ("1", "true", "yes"):
        return True
    return PAUSE_FILE.exists()


def governance_ok() -> bool:
    entry = PRODUCTION_STRATEGY_REGISTRY.get(COMPONENT_KEY) or {}
    return entry.get("status") == "VALIDATED" and entry.get("sleeve") == SLEEVE_TAG


def _rfc3339_to_unix(ts: str) -> float:
    ts = (ts or "").strip()
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return datetime.fromisoformat(ts[:23] + "+00:00").timestamp()


class SleeveRunner:
    """Runs exactly one governed sleeve leg on the OANDA practice account."""

    def __init__(self, adapter: Optional[OandaExchangeAdapter] = None,
                 dry_run: bool = False, state_file: Optional[Path] = None,
                 data_dir: Optional[Path] = None):
        if adapter is None:
            api_key, account_id, practice = load_oanda_credentials()
            adapter = OandaExchangeAdapter(
                api_key=api_key, account_id=account_id, practice=practice
            )
        self.adapter = adapter
        self.account_id = getattr(adapter, "account_id", "")
        self.dry_run = dry_run
        self.data_dir = data_dir or DATA_DIR
        self.state_file = state_file or (self.data_dir / "sleeve_state.json")
        self.pause_file = self.data_dir / "sleeve_entries_paused"
        self.kill_file = self.data_dir / "sleeve_kill_switch"

    # -- state ------------------------------------------------------------
    def _load_state(self) -> Dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_state(self, state: Dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _paused(self) -> bool:
        if os.getenv("STRATEX_SLEEVE_ENTRIES_PAUSED", "").lower() in ("1", "true", "yes"):
            return True
        return self.pause_file.exists()

    # -- market data --------------------------------------------------------
    def _daily_candles(self, symbol: str) -> List[Dict]:
        """Complete UTC-midnight-aligned daily candles (see module doc)."""
        oanda_sym = self.adapter.denormalize_symbol(
            self.adapter.normalize_symbol(symbol)
        )
        data = self.adapter._request(
            "GET", f"/instruments/{oanda_sym}/candles",
            params={
                "granularity": "D",
                "count": HISTORY_BARS,
                "price": "M",
                "dailyAlignment": 0,
                "alignmentTimezone": "UTC",
            },
        )
        if not data or "candles" not in data:
            return []
        out = []
        for c in data["candles"]:
            if not c.get("complete", False):
                continue
            mid = c.get("mid", {})
            ts = _rfc3339_to_unix(str(c.get("time", "")))
            out.append(
                {
                    "timestamp": int(ts),
                    "open": float(mid.get("o", 0)),
                    "high": float(mid.get("h", 0)),
                    "low": float(mid.get("l", 0)),
                    "close": float(mid.get("c", 0)),
                    "volume": int(c.get("volume", 0)),
                }
            )
        return out

    # -- sizing ---------------------------------------------------------------
    @staticmethod
    def _quote_to_usd(quote: str, pricing: Dict[str, Dict[str, float]]) -> float:
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

    def _position_units(self, symbol: str, sl_dist: float,
                        pricing: Dict[str, Dict[str, float]],
                        equity: float, free_margin: float,
                        margin_rate: float) -> int:
        quote = symbol[3:]
        conv = self._quote_to_usd(quote, pricing)
        mid = pricing.get(symbol, {}).get("mid", 0)
        if conv <= 0 or sl_dist <= 0 or mid <= 0:
            return 0
        risk_usd = equity * RISK_PER_TRADE_PCT
        units = int(risk_usd / (sl_dist * conv))
        max_units_notional = int((equity * MAX_NOTIONAL_PCT) / mid)
        lev = (1.0 / margin_rate) if margin_rate and margin_rate > 0 else 20.0
        max_units_margin = int((free_margin * 0.5) * lev / mid)
        return max(0, min(units, max_units_notional, max_units_margin))

    # -- ledger booking ---------------------------------------------------------
    def _book_close(self, trade_id: str, meta: Dict) -> None:
        """Book a detected close into the measurement fill ledger."""
        try:
            data = self.adapter._request(
                "GET", f"/accounts/{self.account_id}/trades/{trade_id}"
            )
            trade = (data or {}).get("trade") or {}
            realized = float(trade.get("realizedPL") or 0.0)
            exit_price = float(trade.get("averageClosePrice") or trade.get("price") or 0.0)
            exit_time = _rfc3339_to_unix(str(trade.get("closeTime") or ""))
            from measurement import fill_ledger

            row = fill_ledger.append_fill(
                {
                    "engine": "oanda_sleeve",
                    "venue": "oanda",
                    "strategy": STRATEGY_TAG,
                    "sleeve": SLEEVE_TAG,
                    "component": COMPONENT_KEY,
                    "symbol": meta["symbol"],
                    "side": meta["side"],
                    "qty": abs(float(meta["units"])),
                    "entry_price": float(meta["entry_price"]),
                    "exit_price": exit_price,
                    "gross_pnl": realized,
                    "fees": 0.0,
                    "fees_source": "broker_realized_pl_spread_embedded",
                    "net_pnl": realized,
                    "entry_time": float(meta["entry_time"]),
                    "exit_time": exit_time or time.time(),
                    "exit_reason": "BROKER_CLOSE",
                    "order_id": str(meta.get("order_id", "")),
                    "entry_order_id": str(meta.get("order_id", "")),
                }
            )
            if row is not None:
                logger.info(
                    f"[SLEEVE] booked close {meta['symbol']} trade {trade_id} "
                    f"net=${realized:+.2f} (strategy={STRATEGY_TAG}, sleeve={SLEEVE_TAG})"
                )
        except Exception as exc:
            logger.error(f"[SLEEVE] close booking FAILED for trade {trade_id}: {exc}")

    # -- core scan ------------------------------------------------------------
    def run_once(self) -> Dict:
        summary: Dict = {"ts": datetime.now(timezone.utc).isoformat(),
                         "component": COMPONENT_KEY, "actions": []}
        if self.kill_file.exists():
            summary["halted"] = "sleeve kill switch present"
            logger.warning("[SLEEVE] kill switch active — skipping scan")
            return summary
        if not governance_ok():
            summary["halted"] = "governance: component not VALIDATED sleeve member"
            logger.warning("[SLEEVE] governance refusal — component not VALIDATED")
            return summary

        acct = self.adapter.get_account_summary()
        if not acct:
            summary["error"] = "account summary unavailable"
            return summary
        equity = float(acct.get("equity", 0))
        free_margin = float(acct.get("margin_available", 0))
        margin_rate = float(acct.get("margin_rate", 0) or 0)
        summary["equity"] = round(equity, 2)

        state = self._load_state()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if state.get("day") != today:
            state["day"] = today
            state["day_start_nav"] = equity
        day_start = float(state.get("day_start_nav", equity)) or equity
        daily_dd = (equity - day_start) / day_start if day_start else 0.0
        summary["daily_pnl_pct"] = round(daily_dd * 100, 2)

        own: Dict[str, Dict] = state.setdefault("own_trades", {})

        # Close detection + booking (runs even while entries are paused).
        trades = self.adapter.open_trades()
        current_ids = {str(t["id"]) for t in trades}
        for tid in list(own):
            if tid not in current_ids:
                meta = own.pop(tid)
                if not self.dry_run:
                    self._book_close(tid, meta)
                summary.setdefault("closes", []).append(tid)
                state.setdefault("cooldowns", {})[meta["symbol"]] = (
                    time.time() + REENTRY_COOLDOWN_S
                )
        summary["own_open_trades"] = len(own)
        summary["account_open_trades"] = len(trades)

        if self._paused():
            summary["entries_paused"] = True
            logger.info("[SLEEVE] entries paused (sleeve pause) — closes booked only")
            self._save_state(state)
            return summary
        if daily_dd <= -DAILY_LOSS_LIMIT_PCT:
            summary["blocked"] = f"daily loss limit ({daily_dd*100:.1f}%)"
            self._save_state(state)
            return summary
        if len(own) >= MAX_OPEN_TRADES:
            summary["blocked"] = f"max open sleeve trades ({MAX_OPEN_TRADES})"
            self._save_state(state)
            return summary

        occupied = {t["instrument"] for t in trades}  # netting protection
        pricing = self.adapter.get_pricing(list(FOREX28_SYMBOLS) + ["USDJPY"])
        if not pricing:
            summary["error"] = "pricing unavailable"
            self._save_state(state)
            return summary

        now = time.time()
        cooldowns = state.get("cooldowns", {})
        for symbol in FOREX28_SYMBOLS:
            if symbol in occupied:
                continue
            if now < float(cooldowns.get(symbol, 0) or 0):
                continue
            candles = self._daily_candles(symbol)
            if len(candles) < sleeve_signals.WARMUP_BARS + 1:
                continue
            df = pd.DataFrame(candles)
            df.index = pd.to_datetime(df["timestamp"], unit="s", utc=True)
            sig = sleeve_signals.evaluate_last_bar(df)
            summary["evaluated"] = summary.get("evaluated", 0) + 1
            if sig is None:
                continue
            mid = pricing.get(symbol, {}).get("mid", 0)
            if mid <= 0:
                continue
            if sig["side"] == "BUY":
                stop = mid - sig["sl_dist"]
                take = mid + sig["tp_dist"]
            else:
                stop = mid + sig["sl_dist"]
                take = mid - sig["tp_dist"]
            units = self._position_units(
                symbol, sig["sl_dist"], pricing, equity, free_margin, margin_rate
            )
            if units < 1:
                continue
            summary["actions"].append(
                f"{sig['side']} {symbol} {units}u @~{mid:.5f} SL {stop:.5f} TP {take:.5f}"
            )
            logger.info(
                f"[SLEEVE] SIGNAL {sig['side']} {symbol} units={units} mid={mid:.5f} "
                f"sl={stop:.5f} tp={take:.5f} atr={sig['atr']:.5f} (strategy={STRATEGY_TAG})"
            )
            if self.dry_run:
                summary["actions"][-1] = "[DRY] " + summary["actions"][-1]
                continue
            try:
                result = self.adapter.place_order(
                    symbol, sig["side"], "MARKET", units,
                    stop_loss=stop, take_profit=take,
                )
            except Exception as exc:
                logger.warning(f"[SLEEVE] order failed for {symbol}: {exc}")
                summary["actions"].append(f"ORDER FAILED {symbol}: {exc}")
                continue
            trade_id = str(getattr(result, "trade_id", "") or "")
            if trade_id:
                own[trade_id] = {
                    "symbol": symbol,
                    "side": sig["side"],
                    "units": units,
                    "entry_price": float(getattr(result, "price", mid) or mid),
                    "entry_time": time.time(),
                    "order_id": str(getattr(result, "order_id", "") or ""),
                }
            occupied.add(symbol)
            if len(own) >= MAX_OPEN_TRADES:
                break

        self._save_state(state)
        return summary

    def status(self) -> Dict:
        return {
            "component": COMPONENT_KEY,
            "strategy_tag": STRATEGY_TAG,
            "sleeve": SLEEVE_TAG,
            "governance_ok": governance_ok(),
            "entries_paused": self._paused(),
            "account": self.adapter.get_account_summary(),
            "own_open_trades": len(self._load_state().get("own_trades", {})),
            "watchlist": list(FOREX28_SYMBOLS),
            "timeframe": TIMEFRAME,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stratex OANDA sleeve runner")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    runner = SleeveRunner(dry_run=args.dry_run)
    if args.status:
        print(json.dumps(runner.status(), indent=2, default=str))
        return 0
    if args.loop:
        logger.info("[SLEEVE] loop mode starting (component=%s)", COMPONENT_KEY)
        while True:
            try:
                out = runner.run_once()
                logger.info(f"[SLEEVE] scan: {json.dumps(out, default=str)}")
            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.warning(f"[SLEEVE] scan error: {exc}")
            time.sleep(max(30, args.interval))
        return 0
    out = runner.run_once()
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
